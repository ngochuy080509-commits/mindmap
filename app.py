import os
import sys
import subprocess

# TỰ ĐỘNG ÉP STREAMLIT CÀI THƯ VIỆN NẾU THIẾU
try:
    from google import genai
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai", "youtube-transcript-api", "requests"])
    from google import genai

import streamlit as st
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit.components.v1 as components

# CẤU HÌNH TRANG STREAMLIT
st.set_page_config(page_title="AI YouTube Mindmap Generator", page_icon="🧠", layout="wide")

st.title("🧠 AI Bài Giảng - Tóm Tắt & Vẽ Sơ Đồ Tư Duy")
st.caption("Biến video bài giảng YouTube 2-3 tiếng thành Mindmap trực quan chỉ trong vài giây!")

# Sidebar nhập API Key và Cấu hình
with st.sidebar:
    st.header("⚙️ Cấu hình")
    api_key = st.text_input("Nhập Gemini API Key:", type="password")
    chunk_time = st.slider("Độ dài mỗi đoạn (phút):", min_value=10, max_value=30, value=15)
    st.markdown("---")
    st.info("💡 **Mẹo:** Bạn chỉ cần dán link YouTube có phụ đề (tiếng Việt/Anh) là hệ thống tự vẽ Mindmap.")

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
            
            # 1. Lấy phụ đề qua Proxy
            status.write("🌐 Đang kết nối lấy phụ đề bài giảng...")
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
                # 2. Gom nhóm văn bản
                status.write("🧩 Đang chia nhỏ nội dung bài giảng...")
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

                # 3. Tóm tắt bằng Gemini
                status.write("🧠 AI đang tóm tắt nội dung...")
                summaries = []
                for i, (time_lbl, text) in enumerate(chunks):
                    prompt = f"Tóm tắt ý chính bài giảng đoạn {time_lbl}:\n\"{text}\"\nGiữ mốc thời gian {time_lbl} ở đầu các ý."
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    summaries.append(res.text)

                # 4. Dựng Mermaid Mindmap
                status.write("🎨 Đang vẽ Sơ đồ tư duy...")
                combined = "\n\n".join(summaries)
                prompt_map = f"Từ tóm tắt sau:\n{combined}\n\nHãy tạo mã Mermaid mindmap chuẩn. Chỉ trả về mã trong ```mermaid ... ```."
                
                res_map = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_map)
                clean_mermaid = re.sub(r'```mermaid\s*', '', res_map.text)
                clean_mermaid = re.sub(r'```\s*$', '', clean_mermaid).strip()

                status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

                # Hiển thị kết quả ra giao diện
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
            else:
                status.update(label="❌ Không lấy được phụ đề!", state="error")
                st.error("Không thể tự động lấy phụ đề từ video này. Hãy đảm bảo video có bật phụ đề (tiếng Việt/Anh).")
