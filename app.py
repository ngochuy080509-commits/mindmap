import streamlit as st
import re
import os
import time
import subprocess
import json
import random
from google import genai
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI Mindmap Bài Giảng", page_icon="🧠", layout="wide")

# TÊN MODEL CHUẨN CỦA GOOGLE
MODEL_NAME = "gemini-3.6-flash"

# CSS GIAO DIỆN & ẨN NÚT HỆ THỐNG (MANAGE APP)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .main { background: #f8fafc; }
    
    /* Ẩn giao diện quản trị của Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp > header {display: none;}
    div[data-testid="stStatusWidget"] {visibility: hidden;}
    [data-testid="manage-app-button"] {display: none !important;}

    .stButton>button { 
        width: 100%; border-radius: 12px; height: 3.2em; font-weight: 700;
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        color: white; border: none; box-shadow: 0 4px 14px rgba(124, 58, 237, 0.3);
        transition: all 0.3s ease;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4); }

    .guide-box {
        background-color: #f0fdf4; border: 1px solid #bbf7d0;
        padding: 16px; border-radius: 12px; margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 AI Bài Giảng - Mindmap Trực Quan")
st.caption("Biến mọi video bài giảng YouTube hoặc Audio MP3 thành Sơ đồ tư duy sinh động!")

# XỬ LÝ DANH SÁCH API KEY (SOLUTION 2: XOAY VÒNG KEY)
raw_keys = st.secrets.get("GEMINI_KEYS", [])
if isinstance(raw_keys, str):
    available_keys = [raw_keys]
else:
    available_keys = list(raw_keys)

single_key = st.secrets.get("GEMINI_API_KEY", None)
if single_key and single_key not in available_keys:
    available_keys.append(single_key)

with st.sidebar:
    st.header("⚙️ Cấu hình API")
    user_key = st.text_input("🔑 Nhập Key cá nhân (nếu có):", type="password")
    
    if user_key:
        active_keys_pool = [user_key]
        st.success("✅ Đang sử dụng Key cá nhân của bạn!")
    elif available_keys:
        active_keys_pool = available_keys
        st.success(f"🟢 Hệ thống sẵn sàng ({len(available_keys)} Key dự phòng).")
    else:
        active_keys_pool = []
        st.warning("⚠️ Chưa tìm thấy API Key nào trong Secrets!")

tab1, tab2 = st.tabs(["🎥 Qua Link YouTube", "🎙️ Tải File Âm Thanh"])

# HÀM GỌI API THÔNG MINH - TỰ ĐỔI KEY KHI BỊ CẠN QUOTA (LỖI 429)
def generate_content_with_retry(contents, keys_pool, max_retries=8, status_container=None):
    if not keys_pool:
        st.error("❌ Không tìm thấy API Key khả dụng. Vui lòng kiểm tra lại cấu hình!")
        return None

    keys_to_try = list(keys_pool)
    random.shuffle(keys_to_try)
    
    for attempt in range(max_retries):
        current_key = keys_to_try[attempt % len(keys_to_try)]
        client = genai.Client(api_key=current_key)
        
        try:
            return client.models.generate_content(model=MODEL_NAME, contents=contents)
        except Exception as e:
            err_msg = str(e).lower()
            if any(k in err_msg for k in ["429", "resource_exhausted", "quota", "503", "unavailable", "overloaded"]):
                if status_container:
                    status_container.write(f"🔄 Key hiện tại cạn lượt, đang chuyển sang Key dự phòng khác (Lần thử {attempt + 1}/{max_retries})...")
                time.sleep(2)
                continue
            else:
                st.error(f"❌ Lỗi API từ Gemini: {str(e)}")
                raise e

    st.error("❌ Tất cả API Key đều đang tạm thời hết lượt (Quota Exceeded). Vui lòng thử lại sau vài phút hoặc nhập Key cá nhân!")
    return None

def render_mindmap_svg(mermaid_code):
    clean_code = re.sub(r'```mermaid\s*', '', mermaid_code)
    clean_code = re.sub(r'```\s*$', '', clean_code).strip()
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
      <style>
        #wrapper {{ position: relative; width: 100%; height: 720px; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; }}
        #container {{ width: 100%; height: 100%; }}
        .dl-btn {{ 
            position: absolute; top: 14px; right: 14px; z-index: 99; 
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white; border: none; padding: 10px 18px; 
            border-radius: 10px; font-weight: bold; font-size: 13px; cursor: pointer; 
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3); transition: 0.2s;
        }}
        .dl-btn:hover {{ transform: scale(1.03); }}
      </style>
    </head>
    <body>
      <div id="wrapper">
        <button class="dl-btn" onclick="downloadImage()">📸 Tải Ảnh Mindmap</button>
        <div id="container"><pre class="mermaid">{clean_code}</pre></div>
      </div>
      <script>
        mermaid.initialize({{ 
            startOnLoad: true, 
            theme: 'base',
            themeVariables: {{
                fontFamily: 'Plus Jakarta Sans, sans-serif',
                primaryColor: '#e0e7ff',
                primaryTextColor: '#1e1b4b',
                primaryBorderColor: '#6366f1',
                lineColor: '#818cf8',
                secondaryColor: '#f3e8ff',
                tertiaryColor: '#ecfdf5'
            }},
            flowchart: {{ useMaxWidth: false, htmlLabels: true, curve: 'basis' }} 
        }});

        setTimeout(function() {{
          var svg = document.querySelector("#container svg");
          if(svg) {{ 
            svg.style.width = '100%'; 
            svg.style.height = '100%'; 
            svgPanZoom(svg, {{ zoomEnabled: true, controlIconsEnabled: true, fit: true, center: true }}); 
          }}
        }}, 800);

        function downloadImage() {{
          var svg = document.querySelector("#container svg");
          if (!svg) return;
          
          var bbox = svg.getBBox();
          var width = Math.max(bbox.width + 120, 1800);
          var height = Math.max(bbox.height + 120, 1400);

          var svgClone = svg.cloneNode(true);
          svgClone.setAttribute("width", width);
          svgClone.setAttribute("height", height);
          
          var serializer = new XMLSerializer();
          var svgString = serializer.serializeToString(svgClone);
          var svgBlob = new Blob([svgString], {{type: "image/svg+xml;charset=utf-8"}});
          var url = URL.createObjectURL(svgBlob);
          
          var img = new Image();
          img.onload = function() {{
            var canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            var ctx = canvas.getContext("2d");
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, width, height);
            ctx.drawImage(img, 0, 0);
            
            var pngUrl = canvas.toDataURL("image/png");
            var win = window.open();
            if (win) {{
              win.document.write('<div style="text-align:center; font-family:sans-serif; padding:10px;">' +
                '<h3 style="color:#4f46e5;">📌 Sơ đồ tư duy chi tiết của bạn</h3>' +
                '<p style="color:#666;">Chạm giữ vào hình bên dưới để <b>Lưu ảnh</b> nhé</p>' +
                '<img src="' + pngUrl + '" style="max-width:100%; height:auto; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.1);"/>' +
                '</div>');
            }}
          }};
          img.src = url;
        }}
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=740, scrolling=False)

PROMPT_MAP = """
Dựa vào bài giảng trên, hãy lập một Sơ đồ tư duy (Mindmap) cực kỳ CHI TIẾT và BAO QUÁT TOÀN BỘ NỘI DUNG.

YÊU CẦU BẮT BUỘC VỀ CẤU TRÚC:
1. Dùng mã Mermaid flowchart dạng từ trái sang phải: `graph LR`
2. Cấu trúc nhánh sâu 3-4 cấp độ:
   - Cấp 1: Chủ đề chính bài giảng
   - Cấp 2: Các Chương / Phần kiến thức lớn
   - Cấp 3: Ý chính / Lý thuyết / Công thức / Mốc quan trọng
   - Cấp 4: Ví dụ minh họa / Chi tiết phụ / Lưu ý
3. Sử dụng icon emoji hợp lý ở đầu mỗi nút để sơ đồ sinh động (VD: 📚, 🔑, 💡, ⚡, 🎯).

QUY TẮC CÚ PHÁP MERMAID AN TOÀN (RẤT QUAN TRỌNG):
- Khai báo nút dạng: ID["Icon + Nội dung"]
- TUYỆT ĐỐI KHÔNG dùng các ký tự: ngoặc tròn (), ngoặc nhọn {}, ngoặc vuông [], dấu nháy đôi " bên trong phần văn bản hiển thị.
- Giữ nguyên tiếng Việt có dấu.
- Chỉ trả về mã Mermaid trong khối ```mermaid ... ```.
"""

def get_yt_audio_or_sub(url):
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "vi,en",
        "--sub-format", "json3",
        "-o", "yt_sub",
        url
    ]
    subprocess.run(cmd, capture_output=True)
    
    sub_file = None
    for file in os.listdir("."):
        if file.startswith("yt_sub") and file.endswith(".json3"):
            sub_file = file
            break
            
    if sub_file:
        try:
            with open(sub_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            os.remove(sub_file)
            
            lines = []
            for event in data.get("events", []):
                for seg in event.get("segs", []):
                    utf8_text = seg.get("utf8", "").strip()
                    if utf8_text and utf8_text != "\n":
                        lines.append(utf8_text)
            return " ".join(lines), "sub"
        except:
            pass

    audio_out = "yt_audio.mp3"
    if os.path.exists(audio_out):
        os.remove(audio_out)
        
    cmd_audio = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "9",
        "-o", audio_out,
        url
    ]
    subprocess.run(cmd_audio, capture_output=True)
    if os.path.exists(audio_out):
        return audio_out, "audio"
        
    return None, None

# --- TAB 1: YOUTUBE ---
with tab1:
    youtube_url = st.text_input("👇 Dán link YouTube bài giảng vào đây:", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("🚀 Tạo Mindmap từ Link YouTube", type="primary"):
        if not active_keys_pool:
            st.error("❌ Vui lòng cấu hình API Key!")
        elif not youtube_url:
            st.warning("⚠️ Vui lòng dán link YouTube!")
        else:
            status = st.status("⏳ Chờ một chút nhé, AI đang tải nội dung video...", expanded=True)
            result_data, result_type = get_yt_audio_or_sub(youtube_url)
            
            if result_type == "sub":
                status.write("📝 Đã lấy xong dữ liệu, đang phân tích bài giảng...")
                prompt = f"Phân tích và tóm tắt đầy đủ, chi tiết từng phần bài giảng sau bằng tiếng Việt:\n\"{result_data[:40000]}\""
                res = generate_content_with_retry(prompt, active_keys_pool, status_container=status)
                
                if res and res.text:
                    combined = res.text
                    status.write("🎨 Đang thiết kế sơ đồ tư duy phân cấp chi tiết...")
                    prompt_map = f"Từ tóm tắt bài giảng sau:\n{combined}\n\n{PROMPT_MAP}"
                    res_map = generate_content_with_retry(prompt_map, active_keys_pool, status_container=status)

                    if res_map and res_map.text:
                        status.update(label="✅ Hoàn tất! Xem sơ đồ bên dưới nhé.", state="complete", expanded=False)
                        st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                        render_mindmap_svg(res_map.text)

                        with st.expander("📄 Xem bản tóm tắt chi tiết"):
                            st.write(combined)

            elif result_type == "audio":
                try:
                    status.write("🎙️ Đang phân tích âm thanh video...")
                    # Dùng ngẫu nhiên 1 client key để upload file
                    init_client = genai.Client(api_key=random.choice(active_keys_pool))
                    gemini_file = init_client.files.upload(file=result_data)
                    
                    while gemini_file.state.name == "PROCESSING":
                        time.sleep(3)
                        gemini_file = init_client.files.get(name=gemini_file.name)
                        
                    status.write("🧠 AI đang tổng hợp toàn bộ ý chính...")
                    prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại chi tiết đầy đủ các phần bằng tiếng Việt."
                    res_audio = generate_content_with_retry([gemini_file, prompt_audio], active_keys_pool, status_container=status)
                    
                    if res_audio and res_audio.text:
                        combined = res_audio.text
                        status.write("🎨 Đang thiết kế sơ đồ tư duy phân cấp chi tiết...")
                        prompt_map = f"Từ tóm tắt bài giảng sau:\n{combined}\n\n{PROMPT_MAP}"
                        res_map = generate_content_with_retry(prompt_map, active_keys_pool, status_container=status)

                        if res_map and res_map.text:
                            status.update(label="✅ Hoàn tất! Xem sơ đồ bên dưới nhé.", state="complete", expanded=False)
                            st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                            render_mindmap_svg(res_map.text)

                            with st.expander("📄 Xem bản tóm tắt chi tiết"):
                                st.write(combined)
                finally:
                    if os.path.exists(result_data):
                        os.remove(result_data)
            else:
                status.update(label="❌ Lỗi kết nối video!", state="error")
                st.error("Không thể kết nối đến video YouTube này. Bạn kiểm tra lại đường link nha!")

# --- TAB 2: FILE AUDIO ---
with tab2:
    st.markdown("""
    <div class="guide-box">
        <h4 style="color: #15803d; margin-top:0;">🎵 Tải trực tiếp file MP3:</h4>
        <p style="color: #166534; margin-bottom: 0;">Nếu bạn có sẵn file ghi âm bài giảng MP3/WAV, chỉ cần thả vào ô bên dưới để AI tự động tạo Mindmap nha!</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader("📂 Tải file âm thanh bài giảng (MP3, M4A, WAV):", type=["mp3", "m4a", "wav", "mp4"])

    if st.button("🚀 Phân Tích Audio & Tạo Mindmap", type="primary"):
        if not active_keys_pool:
            st.error("❌ Vui lòng cấu hình API Key!")
        elif not uploaded_file:
            st.warning("⚠️ Vui lòng tải file âm thanh lên trước!")
        else:
            status = st.status("⏳ Đang tải file lên, chờ một chút nhé...", expanded=True)
            file_ext = os.path.splitext(uploaded_file.name)[1]
            temp_path = f"temp_input{file_ext}"
            
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                init_client = genai.Client(api_key=random.choice(active_keys_pool))
                gemini_file = init_client.files.upload(file=temp_path)
                status.write("✅ Đã nhận file, đang xử lý...")
                
                while gemini_file.state.name == "PROCESSING":
                    time.sleep(3)
                    gemini_file = init_client.files.get(name=gemini_file.name)
                    
                if gemini_file.state.name == "FAILED":
                    raise Exception("Không thể xử lý file âm thanh này.")

                status.write("🎧 AI đang lắng nghe và tóm tắt bài giảng...")
                prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại chi tiết đầy đủ các phần bằng tiếng Việt."
                res_audio = generate_content_with_retry([gemini_file, prompt_audio], active_keys_pool, status_container=status)
                
                if res_audio and res_audio.text:
                    combined = res_audio.text
                    status.write("🎨 Đang thiết kế sơ đồ tư duy phân cấp chi tiết...")
                    prompt_map = f"Từ tóm tắt bài giảng sau:\n{combined}\n\n{PROMPT_MAP}"
                    res_map = generate_content_with_retry(prompt_map, active_keys_pool, status_container=status)

                    if res_map and res_map.text:
                        status.update(label="✅ Hoàn tất! Xem sơ đồ bên dưới nhé.", state="complete", expanded=False)
                        st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                        render_mindmap_svg(res_map.text)

                        with st.expander("📄 Xem bản tóm tắt chi tiết"):
                            st.write(combined)
            except Exception as e:
                status.update(label="❌ Có lỗi xảy ra!", state="error")
                st.error(f"Lỗi: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
