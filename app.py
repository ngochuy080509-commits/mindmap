import streamlit as st
import re
import os
import time
import subprocess
import json
from google import genai
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI Mindmap Bài Giảng", page_icon="🧠", layout="wide")

# CSS GIAO DIỆN
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .main { background: #f8fafc; }
    
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
    
    .warning-box { 
        background-color: #fffbebf8; border: 1px solid #fde68a; 
        padding: 18px; border-radius: 12px; margin-top: 15px; 
    }

    .alert-compress-box { 
        background-color: #eff6ff; border: 1px solid #bfdbfe; 
        padding: 16px; border-radius: 12px; margin-bottom: 20px; 
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 AI Bài Giảng - Mindmap Trực Quan & Đẹp Mắt")
st.caption("Biến mọi video bài giảng YouTube hoặc Audio MP3 thành Sơ đồ tư duy sinh động!")

api_key = st.secrets.get("GEMINI_API_KEY", None)

with st.sidebar:
    st.header("⚙️ Cấu hình")
    if not api_key:
        api_key = st.text_input("🔑 Nhập Gemini API Key:", type="password")
    else:
        st.success("✅ Hệ thống đã sẵn sàng")
        
    chunk_time = st.slider("Độ dài chia đoạn phụ đề (phút):", min_value=10, max_value=30, value=15)

tab1, tab2 = st.tabs(["🎥 Qua Link YouTube (Tự động)", "🎙️ Tải File Âm Thanh (MP3 / WAV)"])

MODEL_NAME = "gemini-3.6-flash"

def generate_content_with_retry(client, contents, max_retries=10, status_container=None):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=MODEL_NAME, contents=contents)
        except Exception as e:
            err_msg = str(e).lower()
            if "503" in err_msg or "unavailable" in err_msg or "high demand" in err_msg or "overloaded" in err_msg:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 4
                    if status_container:
                        status_container.write(f"⏳ Server Google đang bận, tự động thử lại lần {attempt + 1}/{max_retries} (chờ {wait_time}s)...")
                    time.sleep(wait_time)
                    continue
            raise e

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
        #wrapper {{ position: relative; width: 100%; height: 650px; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; }}
        #container {{ width: 100%; height: 100%; }}
        .dl-btn {{ 
            position: absolute; top: 12px; right: 12px; z-index: 99; 
            background: #4f46e5; color: white; border: none; padding: 10px 16px; 
            border-radius: 8px; font-weight: bold; font-size: 13px; cursor: pointer; 
            box-shadow: 0 4px 10px rgba(0,0,0,0.15); transition: 0.2s; text-decoration: none; display: inline-block;
        }}
        .dl-btn:hover {{ background: #4338ca; transform: scale(1.03); }}
      </style>
    </head>
    <body>
      <div id="wrapper">
        <button class="dl-btn" onclick="downloadImage()">📸 Tải Ảnh Mindmap</button>
        <div id="container"><pre class="mermaid">{clean_code}</pre></div>
      </div>
      <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'forest', flowchart: {{ useMaxWidth: false, htmlLabels: true, curve: 'basis' }} }});
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
          
          var serializer = new XMLSerializer();
          var svgString = serializer.serializeToString(svg);
          var svgBlob = new Blob([svgString], {{type: "image/svg+xml;charset=utf-8"}});
          var url = URL.createObjectURL(svgBlob);
          
          var win = window.open();
          if (win) {{
            win.document.write('<p style="font-family:sans-serif; text-align:center;"><b>Chạm và giữ vào ảnh bên dưới để Lưu về máy:</b></p><img src="' + url + '" style="max-width:100%;"/>');
          }} else {{
            var a = document.createElement("a");
            a.href = url;
            a.download = "mindmap-bai-giang.svg";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
          }}
        }}
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=670, scrolling=False)

PROMPT_MAP = """
Từ nội dung tóm tắt trên, hãy tạo mã Mermaid flowchart dạng sơ đồ cây từ trái sang phải (`graph LR`).
YÊU CẦU BẮT BUỘC:
1. Bắt đầu bằng dòng: `graph LR`
2. Giữ nguyên tiếng Việt có dấu.
3. Cú pháp tạo nút an toàn: D["1. Khái Niệm"] --> D1["Nội dung ý 1"]
4. TUYỆT ĐỐI KHÔNG dùng dấu ngoặc tròn (), ngoặc nhọn {}, ngoặc vuông [] bên trong đoạn chữ tiếng Việt (ngoại trừ ngoặc của ID nút).
5. Chỉ trả về mã Mermaid trong khối ```mermaid ... ```.
"""

def get_yt_audio_or_sub(url):
    """Sử dụng yt-dlp để vượt rào chống bot của YouTube"""
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
    
    # Kiểm tra xem có file phụ đề json nào được tải xuống không
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

    # Nếu không lấy được phụ đề, tải thẳng audio nhẹ về để Gemini tự nghe
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
        if not api_key:
            st.error("❌ Vui lòng nhập Gemini API Key!")
        elif not youtube_url:
            st.warning("⚠️ Vui lòng dán link YouTube!")
        else:
            client = genai.Client(api_key=api_key)
            status = st.status("🔍 Đang kết nối và xử lý Video YouTube...", expanded=True)
            
            result_data, result_type = get_yt_audio_or_sub(youtube_url)
            
            if result_type == "sub":
                status.write("🧠 Đã vượt rào YouTube thành công! AI đang tóm tắt nội dung...")
                prompt = f"Tóm tắt các ý chính bài giảng sau bằng tiếng Việt chuẩn:\n\"{result_data[:30000]}\""
                res = generate_content_with_retry(client, prompt, status_container=status)
                combined = res.text

                status.write("🎨 Đang vẽ sơ đồ tư duy...")
                prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                res_map = generate_content_with_retry(client, prompt_map, status_container=status)

                status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                render_mindmap_svg(res_map.text)

                with st.expander("📄 Xem bản tóm tắt chi tiết"):
                    st.write(combined)

            elif result_type == "audio":
                try:
                    status.write("🎙️ YouTube không cho cào chữ, đã tự động tải audio về để Gemini nghe trực tiếp...")
                    gemini_file = client.files.upload(file=result_data)
                    
                    while gemini_file.state.name == "PROCESSING":
                        time.sleep(3)
                        gemini_file = client.files.get(name=gemini_file.name)
                        
                    status.write("🧠 AI đang lắng nghe và tóm tắt bài giảng...")
                    prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại các ý chính chi tiết bằng tiếng Việt."
                    res_audio = generate_content_with_retry(client, [gemini_file, prompt_audio], status_container=status)
                    combined = res_audio.text
                    
                    status.write("🎨 Đang vẽ sơ đồ tư duy...")
                    prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                    res_map = generate_content_with_retry(client, prompt_map, status_container=status)

                    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                    st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                    render_mindmap_svg(res_map.text)

                    with st.expander("📄 Xem bản tóm tắt chi tiết"):
                        st.write(combined)
                finally:
                    if os.path.exists(result_data):
                        os.remove(result_data)
            else:
                status.update(label="❌ Lỗi tải dữ liệu video!", state="error")
                st.error("Không thể kết nối đến video YouTube này. Vui lòng kiểm tra lại đường link!")

# --- TAB 2: FILE AUDIO ---
with tab2:
    st.markdown("""
    <div class="guide-box">
        <h4 style="color: #15803d; margin-top:0;">🎵 Tải trực tiếp file MP3:</h4>
        <p style="color: #166534; margin-bottom: 0;">Nếu bạn có sẵn file ghi âm bài giảng MP3/WAV, chỉ cần thả trực tiếp vào ô bên dưới để AI tự động tạo Mindmap!</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader("📂 Tải file âm thanh bài giảng lên đây (MP3, M4A, WAV):", type=["mp3", "m4a", "wav", "mp4"])

    if st.button("🚀 Phân Tích Audio & Tạo Mindmap", type="primary"):
        if not api_key:
            st.error("❌ Vui lòng nhập Gemini API Key!")
        elif not uploaded_file:
            st.warning("⚠️ Vui lòng tải file âm thanh lên trước!")
        else:
            client = genai.Client(api_key=api_key)
            status = st.status("📥 Đang tải file âm thanh lên Server Gemini...", expanded=True)
            
            file_ext = os.path.splitext(uploaded_file.name)[1]
            temp_path = f"temp_input{file_ext}"
            
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                gemini_file = client.files.upload(file=temp_path)
                status.write("✅ Tải file lên thành công! Đang chờ Server xử lý...")
                
                while gemini_file.state.name == "PROCESSING":
                    time.sleep(3)
                    gemini_file = client.files.get(name=gemini_file.name)
                    
                if gemini_file.state.name == "FAILED":
                    raise Exception("Lỗi xử lý file âm thanh trên Server Google.")

                status.write("🧠 AI đang lắng nghe và phân tích bài giảng...")
                prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại các ý chính chi tiết bằng tiếng Việt có mốc thời gian."
                
                res_audio = generate_content_with_retry(client, [gemini_file, prompt_audio], status_container=status)
                combined = res_audio.text
                
                status.write("🎨 Đang vẽ sơ đồ tư duy...")
                prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                res_map = generate_content_with_retry(client, prompt_map, status_container=status)

                status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                render_mindmap_svg(res_map.text)

                with st.expander("📄 Xem bản tóm tắt chi tiết"):
                    st.write(combined)
            except Exception as e:
                status.update(label="❌ Lỗi xử lý!", state="error")
                st.error(f"Đã xảy ra lỗi: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
