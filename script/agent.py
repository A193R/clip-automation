import os
import subprocess
import requests
import json
from google import genai

# Konfiguration aus GitHub Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# URL zum Video oder VOD
VIDEO_URL = "https://www.youtube.com/watch?v=p2NUAp4X-TQ" 

OUTPUT_FILE = "raw_video.mp4"
HIGHLIGHT_FILE = "highlight.mp4"
FINAL_OUTPUT = "final_clip.mp4"

def download_video(video_url):
    print("⬇️ Lade Video herunter mit authentifizierten Cookies...")
    # Schreibe die Cookies aus den GitHub Secrets temporär in eine Datei
    cookies_content = os.environ.get("YOUTUBE_COOKIES")
    if cookies_content:
        with open("cookies.txt", "w") as f:
            f.write(cookies_content)
    
    # yt-dlp Befehl mit Cookie-Parameter ausführen
    subprocess.run([
        "yt-dlp", 
        "--cookies", "cookies.txt",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]", 
        "-o", OUTPUT_FILE, 
        video_url
    ], check=True))

def analyze_with_gemini():
    print("🧠 Analysiere Video mit Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Videodatei hochladen
    uploaded_file = client.files.upload(file=OUTPUT_FILE)
    
    prompt = """
    Analysiere dieses Video gründlich. Suche nach dem absolut besten Moment, der sich perfekt als Hook eignet.
    Berücksichtige dabei:
    - Auffällige gesprochene Sätze oder spannender Text.
    - Audio-Spitzen (plötzliche laute Reaktionen, Schreie, Gelächter).
    - Visuelle Action-Momente.
    
    Regel: Der gesuchte Highlight-Clip soll als Hook dienen und exakt 60 Sekunden lang sein.
    Gib mir den Startzeitpunkt dieses Moments im Format HH:MM:SS zurück.
    
    Antworte ausschließlich im folgenden JSON-Format:
    {"start": "00:01:20", "description": "Spannender Highlight-Moment"}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[uploaded_file, prompt]
    )
    
    # Aufräumen bei Google
    client.files.delete(name=uploaded_file.name)
    
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    data = json.loads(clean_text)
    return data["start"]

def cut_format_and_arrange(start_time):
    print(f"✂️ Schneide 60-Sekunden-Highlight ab {start_time} aus...")
    
    cmd_cut = [
        "ffmpeg", "-y", 
        "-ss", start_time, 
        "-i", OUTPUT_FILE, 
        "-t", "60", 
        "-c:v", "libx264", "-c:a", "aac", 
        HIGHLIGHT_FILE
    ]
    subprocess.run(cmd_cut, check=True)
    
    os.rename(HIGHLIGHT_FILE, FINAL_OUTPUT)

def send_to_telegram():
    print("📤 Sende Clip an Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    with open(FINAL_OUTPUT, "rb") as video_file:
        response = requests.post(
            url, 
            data={
                "chat_id": TELEGRAM_CHAT_ID, 
                "caption": "🔥📱 **Automatisierter Highlight-Clip mit Gemini & FFmpeg!**"
            }, 
            files={"video": video_file}
        )
    print("Telegram Antwort:", response.status_code)

if __name__ == "__main__":
    download_video(VIDEO_URL)
    start_time = analyze_with_gemini()
    cut_format_and_arrange(start_time)
    send_to_telegram()
