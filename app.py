import streamlit as st
import re
import requests
import os
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI Mindmap Bài Giảng", page_icon="🧠", layout="wide")

# CSS Giao diện
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .main { background: #f8fafc; }
    .stButton>button { 
        width: 100%; 
        border-radius: 12px; 
        height: 3.2em; 
        font-weight: 700;
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        color: white;
        border: none;
        box-shadow: 0 4px 14px rgba(124, 58, 237, 0.3);
    }
    .guide-box {
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 AI Bài Giảng - Mindmap Trực Quan & Đẹp Mắt")
st.caption("Biến mọi video bài giảng / Audio MP3 thành Sơ đồ tư duy sinh động!")

api_key = st.secrets.get("GEMINI_API_KEY", None)

with st.sidebar:
    st.header("⚙️ Cấu hình")
    if not api_key:
        api_key = st.text_input("🔑 Nhập Gemini API Key:", type="password")
    else:
        st.success("✅ Hệ thống đã sẵn sàng")
        
    chunk_time = st.slider("Độ dài chia đoạn phụ đề (phút):", min_value=10, max_value=30, value=15)

tab1, tab2 = st.tabs(["🎥 Qua Link YouTube (Có phụ đề)", "🎙️ Tải File Âm Thanh (Không phụ đề)"])

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def render_mindmap_svg(mermaid_code):
    # Render Mermaid chuẩn không bao giờ trắng màn hình + Có nút tải ảnh
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
        #wrapper {{
          position: relative;
          width: 100%;
          height: 650px;
          background: #ffffff;
          border-radius: 16px;
          border: 1px solid #e2e8f0;
          overflow: hidden;
        }}
        #container {{
          width: 100%;
          height: 100%;
        }}
        .dl-btn {{
          position: absolute;
          top: 12px;
          right: 12px;
          z-index: 99;
          background: #4f46e5;
          color: white;
          border: none;
          padding: 8px 14px;
          border-radius: 8px;
          font-weight: bold;
          font-size: 12px;
          cursor: pointer;
          box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }}
      </style>
    </head>
    <body>
      <div id="wrapper">
        <button class="dl-btn" onclick="downloadSVG()">📸 Tải Ảnh Sơ Đồ</button>
        <div id="container">
          <pre class="mermaid">
          {clean_code}
          </pre>
        </div>
      </div>

      <script>
        mermaid.initialize({{ 
          startOnLoad: true, 
          theme: 'forest',
          flowchart: {{ useMaxWidth: false, htmlLabels: true, curve: 'basis' }}
        }});

        setTimeout(function() {{
          var svg = document.querySelector("#container svg");
          if(svg) {{
            svg.style.width = '100%';
            svg.style.height = '100%';
            svgPanZoom(svg, {{
              zoomEnabled: true,
              controlIconsEnabled: true,
              fit: true,
              center: true
            }});
          }}
        }}, 800);

        function downloadSVG() {{
          var svg = document.querySelector("#container svg");
          if(!svg) return;
          var serializer = new XMLSerializer();
          var source = serializer.serializeToString(svg);
          var svgBlob = new Blob([source], {{type: "image/svg+xml;charset=utf-8"}});
          var svgUrl = URL.createObjectURL(svgBlob);
          var downloadLink = document.createElement("a");
          downloadLink.href = svgUrl;
          downloadLink.download = "mindmap-bai-giang.svg";
          document.body.appendChild(downloadLink);
          downloadLink.click();
          document.body.removeChild(downloadLink);
        }}
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=670, scrolling=False)

# PROMPT VẼ SƠ ĐỒ CÂY AN TOÀN CHỐNG LỖI 100%
PROMPT_MAP = """
Từ nội dung tóm tắt trên, hãy tạo mã Mermaid flowchart dạng sơ đồ cây từ trái sang phải (`graph LR`).

YÊU CẦU BẮT BUỘC:
1. Bắt đầu bằng dòng: `graph LR`
2. Giữ nguyên tiếng Việt có dấu.
3. Cú pháp tạo nút an toàn: D["1. Khái Niệm"] --> D1["Nội dung ý 1"]
4. TUYỆT ĐỐI KHÔNG dùng dấu ngoặc tròn (), ngoặc nhọn {}, ngoặc vuông [] bên trong đoạn chữ tiếng Việt (ngoại trừ ngoặc của ID nút).
5. Chỉ trả về mã Mermaid trong khối ```mermaid ... ```.
"""

# --- TAB 1: YOUTUBE ---
with tab1:
    youtube_url = st.text_input("👇 Dán link YouTube bài giảng vào đây:", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("🚀 Tạo Mindmap từ Link", type="primary"):
        if not api_key:
            st.error("❌ Vui lòng nhập Gemini API Key!")
        elif not youtube_url:
            st.warning("⚠️ Vui lòng dán link YouTube!")
        else:
            video_id = extract_video_id(youtube_url)
            if not video_id:
                st.error("❌ Link YouTube không hợp lệ!")
            else:
                client = genai.Client(api_key=api_key)
                status = st.status("🔍 Đang lấy phụ đề từ YouTube...", expanded=True)
                
                proxy_list = []
                try:
                    res = requests.get("https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt", timeout=5)
                    proxy_list = [f"http://{p.strip()}" for p in res.text.split("\n") if p.strip()][:10]
                except:
                    pass

                transcript_data = None
                for proxy in [None] + proxy_list:
                    try:
                        proxies = {"http": proxy, "https": proxy} if proxy else None
                        ytt_api = YouTubeTranscriptApi(proxies=proxies)
                        transcript_list = ytt_api.list_transcripts(video_id)
                        try:
                            transcript = transcript_list.find_transcript(['vi', 'en'])
                        except:
                            transcript = transcript_list.find_generated_transcript(['vi', 'en'])
                        transcript_data = transcript.fetch()
                        break
                    except:
                        continue

                if transcript_data:
                    status.write("🧩 Đang nhóm dữ liệu văn bản...")
                    chunk_sec = chunk_time * 60
                    chunks, current_chunk, current_start = [], [], 0
                    
                    for item in transcript_data:
                        text_str = item.get('text', '') if isinstance(item, dict) else item.text
                        start_sec = item.get('start', 0) if isinstance(item, dict) else item.start
                        
                        current_chunk.append(text_str)
                        if start_sec - current_start >= chunk_sec:
                            start_m, end_m = int(current_start // 60), int(start_sec // 60)
                            time_lbl = f"[{start_m//60:02d}:{start_m%60:02d} - {end_m//60:02d}:{end_m%60:02d}]"
                            chunks.append((time_lbl, " ".join(current_chunk)))
                            current_chunk, current_start = [], start_sec
                            
                    if current_chunk:
                        start_m = int(current_start // 60)
                        last_sec = transcript_data[-1].get('start', 0) if isinstance(transcript_data[-1], dict) else transcript_data[-1].start
                        end_m = int(last_sec // 60)
                        time_lbl = f"[{start_m//60:02d}:{start_m%60:02d} - {end_m//60:02d}:{end_m%60:02d}]"
                        chunks.append((time_lbl, " ".join(current_chunk)))

                    status.write("🧠 AI đang tóm tắt nội dung bài giảng...")
                    summaries = []
                    for i, (time_lbl, text) in enumerate(chunks):
                        prompt = f"Tóm tắt ý chính bài giảng đoạn {time_lbl} bằng tiếng Việt chuẩn:\n\"{text}\"\nGiữ mốc thời gian {time_lbl} ở đầu các ý."
                        res = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
                        summaries.append(res.text)

                    combined = "\n\n".join(summaries)

                    status.write("🎨 Đang vẽ sơ đồ tư duy...")
                    prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                    res_map = client.models.generate_content(model="gemini-3.6-flash", contents=prompt_map)

                    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                    st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                    render_mindmap_svg(res_map.text)

                    with st.expander("📄 Xem bản tóm tắt chi tiết"):
                        st.write(combined)
                else:
                    status.update(label="❌ Không tìm thấy phụ đề!", state="error")
                    st.error("Video này không có phụ đề sẵn. Vui lòng chuyển sang tab 'Tải File Âm Thanh' để xử lý nhé!")

# --- TAB 2: AUDIO ---
with tab2:
    st.markdown("""
    <div class="guide-box">
        <h4>💡 Hướng dẫn tải MP3 từ YouTube (Chỉ mất 10 giây):</h4>
        <ol>
            <li>Mở YouTube và <b>Copy link video</b> bài giảng bạn muốn tóm tắt.</li>
            <li>Truy cập trang web: <a href="https://y2meta.nu" target="_blank"><b>y2meta.nu</b></a> hoặc <a href="https://y2mate.is" target="_blank"><b>y2mate.is</b></a>.</li>
            <li>Dán link YouTube vào ô tìm kiếm &rarr; Chọn tab <b>MP3</b> &rarr; Bấm <b>Download</b> về máy.</li>
            <li>Kéo thả file MP3 vừa tải vào khung bên dưới để tạo Mindmap!</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader("📂 Tải file MP3 / M4A / WAV bài giảng lên đây:", type=["mp3", "m4a", "wav", "mp4"])

    if st.button("🚀 Phân Tích Audio & Tạo Mindmap", type="primary"):
        if not api_key:
            st.error("❌ Vui lòng nhập Gemini API Key!")
        elif not uploaded_file:
            st.warning("⚠️ Vui lòng tải file âm thanh lên trước!")
        else:
            client = genai.Client(api_key=api_key)
            status = st.status("🎙️ Đang tải file lên Gemini...", expanded=True)
            
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                status.write("🧠 Gemini đang lắng nghe bài giảng...")
                gemini_file = client.files.upload(file=temp_path)
                
                prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại các ý chính chi tiết bằng tiếng Việt có mốc thời gian."
                res_audio = client.models.generate_content(model="gemini-3.6-flash", contents=[gemini_file, prompt_audio])
                combined = res_audio.text
                
                status.write("🎨 Đang vẽ sơ đồ tư duy...")
                prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                res_map = client.models.generate_content(model="gemini-3.6-flash", contents=prompt_map)

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
