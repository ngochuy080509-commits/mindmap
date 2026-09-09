import streamlit as st
import re
import requests
import os
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI Mindmap Bài Giảng", page_icon="🧠", layout="wide")

# CSS làm đẹp giao diện Streamlit
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    div[data-testid="stStatusWidget"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 AI Bài Giảng - Tóm Tắt & Vẽ Sơ Đồ Tư Duy")
st.caption("Biến mọi bài giảng YouTube / MP3 thành sơ đồ tư duy đẹp mắt, dễ học!")

# Sidebar nhập API Key và Cấu hình
with st.sidebar:
    st.header("⚙️ Cấu hình")
    api_key = st.text_input("Nhập Gemini API Key:", type="password")
    chunk_time = st.slider("Độ dài chia đoạn phụ đề (phút):", min_value=10, max_value=30, value=15)
    st.markdown("---")
    st.info("💡 **Mẹo:** Nếu video không có phụ đề, hãy tải file MP3 bài giảng về máy rồi tải lên ở Tab 2!")

# TAB CHỌN CHẾ ĐỘ
tab1, tab2 = st.tabs(["🎥 Qua Link YouTube (Có phụ đề)", "🎙️ Tải File Âm Thanh (Không phụ đề)"])

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def render_beautiful_mindmap(mermaid_code):
    # Dựng HTML rendering Mermaid cực đẹp + hỗ trợ Pan/Zoom SVG
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
          box-shadow: 0 4px 12px rgba(0,0,0,0.05);
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
          background: rgba(0,0,0,0.6);
          color: white;
          padding: 4px 10px;
          border-radius: 20px;
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
        <div class="hint">🔍 Dùng chuột/ngón tay để kéo & Phóng to / Thu nhỏ</div>
      </div>

      <script>
        mermaid.initialize({{ 
          startOnLoad: true, 
          theme: 'neutral',
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
        }}, 1000);
      </script>
    </body>
    </html>
    """
    components.html(html_code, height=670, scrolling=False)

# PROMPT VẼ SƠ ĐỒ CÂY ĐẸP
PROMPT_MAP_STYLE = """
Từ nội dung tóm tắt trên, hãy tạo mã Mermaid flowchart dạng sơ đồ cây từ trái sang phải (dùng `graph LR`).
Yêu cầu bắt buộc:
1. Sử dụng cú pháp `graph LR`.
2. Bắt đầu bằng Chủ đề chính ở gốc.
3. Phân nhánh rõ ràng thành các Ý lớn -> Ý nhỏ -> Chi tiết.
4. Rút gọn nhãn các nút cho ngắn gọn, súc tích (dưới 10 từ mỗi nút).
5. Tuyệt đối KHÔNG dùng các ký tự đặc biệt như dấu ngoặc tròn `()`, ngoặc vuông `[]`, dấu ngoặc nháy trong tên nút ngoại trừ ngoặc của ID nút.
6. Trả về ĐÚNG mã mermaid trong khối ```mermaid ... ```.
"""

# --- TAB 1: XỬ LÝ LINK YOUTUBE CÓ PHỤ ĐỀ ---
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
                    prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP_STYLE}"
                    res_map = client.models.generate_content(model="gemini-3.6-flash", contents=prompt_map)
                    clean_mermaid = re.sub(r'```mermaid\s*', '', res_map.text)
                    clean_mermaid = re.sub(r'```\s*$', '', clean_mermaid).strip()

                    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                    st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                    render_beautiful_mindmap(clean_mermaid)

                    with st.expander("📄 Xem bản tóm tắt chi tiết"):
                        st.write(combined)
                else:
                    status.update(label="❌ Không tìm thấy phụ đề!", state="error")
                    st.error("Video này không có phụ đề sẵn. Vui lòng chuyển sang tab 'Tải File Âm Thanh' để xử lý nhé!")

# --- TAB 2: UPLOAD FILE ÂM THANH TRỰC TIẾP ---
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
                status.write("🧠 Gemini đang lắng nghe và tóm tắt bài giảng...")
                gemini_file = client.files.upload(file=temp_path)
                
                prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại các ý chính chi tiết kèm theo mốc thời gian."
                res_audio = client.models.generate_content(model="gemini-3.6-flash", contents=[gemini_file, prompt_audio])
                combined = res_audio.text
                
                status.write("🎨 Đang thiết kế sơ đồ tư duy...")
                prompt_map = f"Từ tóm tắt sau:\n{combined}\n\n{PROMPT_MAP_STYLE}"
                res_map = client.models.generate_content(model="gemini-3.6-flash", contents=prompt_map)
                clean_mermaid = re.sub(r'```mermaid\s*', '', res_map.text)
                clean_mermaid = re.sub(r'```\s*$', '', clean_mermaid).strip()

                status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
                render_beautiful_mindmap(clean_mermaid)

                with st.expander("📄 Xem bản tóm tắt chi tiết"):
                    st.write(combined)
            except Exception as e:
                status.update(label="❌ Lỗi xử lý!", state="error")
                st.error(f"Đã xảy ra lỗi: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
