import streamlit as st
import re
import requests
import os
import yt_dlp
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI YouTube Mindmap Generator", page_icon="🧠", layout="wide")

st.title("🧠 AI Bài Giảng - Tóm Tắt & Vẽ Sơ Đồ Tư Duy")
st.caption("Xử lý mọi video YouTube (có phụ đề hoặc không có phụ đề)!")

# Sidebar nhập API Key và Cấu hình
with st.sidebar:
    st.header("⚙️ Cấu hình")
    api_key = st.text_input("Nhập Gemini API Key:", type="password")
    chunk_time = st.slider("Độ dài mỗi đoạn (phút):", min_value=10, max_value=30, value=15)
    st.markdown("---")
    st.info("💡 *Hỗ trợ:* Video không phụ đề sẽ được tự động chuyển đổi qua Gemini Audio.")

# Input Link YouTube
youtube_url = st.text_input("👇 Dán link YouTube bài giảng vào đây:", placeholder="https://www.youtube.com/watch?v=...")

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

if st.button("🚀 Bắt đầu tạo Mindmap", type="primary"):
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
            status = st.status("🔍 Đang xử lý dữ liệu...", expanded=True)
            
            # CHẾ ĐỘ 1: THỬ LẤY PHỤ ĐỀ SẴN CÓ
            status.write("🌐 1. Kiểm tra phụ đề YouTube...")
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

            # NẾU CÓ PHỤ ĐỀ
            if transcript_data:
                status.write("🧩 2. Đang phân tích phụ đề...")
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

                status.write("🧠 3. AI đang tóm tắt...")
                summaries = []
                for i, (time_lbl, text) in enumerate(chunks):
                    prompt = f"Tóm tắt ý chính bài giảng đoạn {time_lbl}:\n\"{text}\"\nGiữ mốc thời gian {time_lbl} ở đầu các ý."
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    summaries.append(res.text)

                combined = "\n\n".join(summaries)

            # CHẾ ĐỘ 2: VIDEO KHÔNG CÓ PHỤ ĐỀ (DÙNG GIẢ LẬP ĐỂ TẢI AUDIO & DÙNG GEMINI AUDIO)
            else:
                status.write("🎧 Video không có phụ đề. Đang tải âm thanh bài giảng...")
                
                # Dọn dẹp file tạm cũ nếu có
                for f in os.listdir('.'):
                    if f.startswith('temp_audio'):
                        os.remove(f)
                    
                ydl_opts = {
                    'format': 'm4a/bestaudio/best',
                    'outtmpl': 'temp_audio.%(ext)s',
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'ios', 'web']
                        }
                    },
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([youtube_url])
                    
                    # Tìm file audio vừa tải
                    downloaded_file = [f for f in os.listdir('.') if f.startswith('temp_audio')][0]
                    
                    status.write("🎙️ Đang gửi âm thanh sang AI Gemini để phân tích...")
                    uploaded_file = client.files.upload(file=downloaded_file)
                    
                    prompt_audio = "Hãy nghe toàn bộ audio bài giảng này và tóm tắt lại các ý chính chi tiết kèm theo mốc thời gian."
                    res_audio = client.models.generate_content(model="gemini-2.5-flash", contents=[uploaded_file, prompt_audio])
                    combined = res_audio.text
                    
                    # Dọn dẹp file tạm
                    os.remove(downloaded_file)
                except Exception as e:
                    status.update(label="❌ Lỗi xử lý âm thanh!", state="error")
                    st.error(f"Lỗi: {str(e)}")
                    st.stop()

            # DỰNG MERMAID MINDMAP
            status.write("🎨 Đang vẽ Sơ đồ tư duy...")
            prompt_map = f"Từ tóm tắt sau:\n{combined}\n\nHãy tạo mã Mermaid mindmap chuẩn. Chỉ trả về mã trong ```mermaid ... ```."
            
            res_map = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_map)
            clean_mermaid = re.sub(r'```mermaid\s*', '', res_map.text)
            clean_mermaid = re.sub(r'```\s*$', '', clean_mermaid).strip()

            status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

            # Hiển thị kết quả
            st.subheader("📌 Sơ Đồ Tư Duy Bài Giảng")
            html_code = f"""
            <div class="mermaid" style="background-color: white; padding: 20px; border-radius: 10px;">
            {clean_mermaid}
            </div>
            <script type="module">
              import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
              mermaid.initialize({{ startOnLoad: true }});
            </script>
            """
            components.html(html_code, height=600, scrolling=True)

            with st.expander("📄 Xem bản tóm tắt chi tiết"):
                st.write(combined)
