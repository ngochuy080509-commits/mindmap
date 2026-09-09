import streamlit as st
import re
import requests
import os
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI Mindmap Bài Giảng", page_icon="🎨", layout="wide")

st.title("🎨 AI Bài Giảng - Sơ Đồ Tư Duy Dễ Học")
st.caption("Biến mọi bài giảng YouTube / MP3 thành sơ đồ tư duy trực quan!")

# Sidebar
with st.sidebar:
    st.header("⚙️ Cấu hình")
    api_key = st.text_input("Nhập Gemini API Key:", type="password")
    chunk_time = st.slider("Độ dài chia đoạn phụ đề (phút):", min_value=10, max_value=30, value=15)

tab1, tab2 = st.tabs(["🎥 Qua Link YouTube (Có phụ đề)", "🎙️ Tải File Âm Thanh (Không phụ đề)"])

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def render_mindmap(mermaid_code):
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
      <style>
        #container {{
          width: 100%;
          height: 650px;
          background: #ffffff;
          border-radius: 12px;
          border: 1px solid #e0e0e0;
          overflow: hidden;
          position: relative;
        }}
        .mermaid {{
          width: 100%;
          height: 100%;
        }}
        .hint {{
          position: absolute;
          bottom: 10px;
          right: 15px;
          background: #4a5568;
          color: white;
          padding: 4px 12px;
          border-radius: 15px;
          font-size: 12px;
          pointer-events: none;
        }}
      </style>
    </head>
    <body>
      <div id="container">
        <div class="mermaid">
        {mermaid_code}
        </div>
        <div class="hint">🔍 Dùng chuột/ngón tay để phóng to & kéo</div>
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
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=670, scrolling=False)

# PROMPT VẼ SƠ ĐỒ CÂY AN TOÀN CHỐNG LỖI
PROMPT_MAP = """
Từ nội dung tóm tắt trên, hãy tạo mã Mermaid flowchart đơn giản dạng sơ đồ cây từ trái sang phải (`graph LR`).

Quy tắc bắt buộc để KHÔNG BỊ LỖI:
1. Bắt đầu bằng dòng: `graph LR`
2. Tạo các nút nối với nhau dạng: `A[Gốc] --> B[Nhánh 1]`
3. KHÔNG sử dụng các ký tự đặc biệt như: (), [], {}, "", '', :, ;, &, <, > bên trong nội dung chữ.
4. Chỉ viết ngắn gọn các từ, không rườm rà.
5. Chỉ trả về duy nhất đoạn mã mermaid nằm trong khối ```mermaid ... ```.
"""

# --- TAB 1: YOUTUBE ---
with tab1:
    youtube_url = st.text_input("👇 Dán link YouTube bài giảng vào đây:", placeholder="https://www.youtube.com/watch?v=...")

    if st.button("🚀 Tạo Mindmap từ Link", type="primary"):
        if not api_key:
            st.error("❌ Vui lòng nhập Gemini API Key ở thanh bên trái!")
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

                    status.write("🧠 AI đang tóm tắt nội dung...")
                    summaries = []
                    for i, (time_lbl, text) in enumerate(chunks):
                        prompt = f"Tóm tắt ý chính bài giảng đoạn {time_lbl}:\n\"{text}\"\nGiữ mốc thời gian {time_lbl} ở đầu các ý."
                        res = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
                        summaries.append(res.text)

                    combined = "\n\n".join(summaries)

                    status.write("🎨 Đang thiết kế sơ đồ tư duy...")
                    prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                    res_map = client.models.generate_content(model="gemini-3.6-flash", contents=prompt_map)
                    clean_mermaid = re.sub(r'```mermaid\s*', '', res_map.text)
                    clean_mermaid = re.sub(r'```\s*$', '', clean_mermaid).strip()

                    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                    st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                    render_mindmap(clean_mermaid)

                    with st.expander("📄 Xem bản tóm tắt chi tiết"):
                        st.write(combined)
                else:
                    status.update(label="❌ Không tìm thấy phụ đề!", state="error")
                    st.error("Video này không có phụ đề sẵn. Vui lòng chuyển sang tab 'Tải File Âm Thanh' để xử lý nhé!")

# --- TAB 2: AUDIO ---
with tab2:
    uploaded_file = st.file_uploader("📂 Tải file MP3 / M4A / WAV bài giảng lên đây:", type=["mp3", "m4a", "wav", "mp4"])

    if st.button("🚀 Phân Tích Audio & Tạo Mindmap", type="primary"):
        if not api_key:
            st.error("❌ Vui lòng nhập Gemini API Key ở thanh bên trái!")
        elif not uploaded_file:
            st.warning("⚠️ Vui lòng tải file âm thanh lên trước!")
        else:
            client = genai.Client(api_key=api_key)
            status = st.status("🎙️ Đang tải file lên Gemini...", expanded=True)
            
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                status.write("🧠 Gemini đang nghe bài giảng...")
                gemini_file = client.files.upload(file=temp_path)
                
                prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại các ý chính chi tiết kèm theo mốc thời gian."
                res_audio = client.models.generate_content(model="gemini-3.6-flash", contents=[gemini_file, prompt_audio])
                combined = res_audio.text
                
                status.write("🎨 Đang vẽ sơ đồ tư duy...")
                prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP}"
                res_map = client.models.generate_content(model="gemini-3.6-flash", contents=prompt_map)
                clean_mermaid = re.sub(r'```mermaid\s*', '', res_map.text)
                clean_mermaid = re.sub(r'```\s*$', '', clean_mermaid).strip()

                status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                render_mindmap(clean_mermaid)

                with st.expander("📄 Xem bản tóm tắt chi tiết"):
                    st.write(combined)
            except Exception as e:
                status.update(label="❌ Lỗi xử lý!", state="error")
                st.error(f"Đã xảy ra lỗi: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
