import os
import subprocess
import requests
import json
from google import genai

# Konfiguration (Lokal eintragen oder als Umgebungsvariable setzen)
GEMINI_API_KEY = "DEIN_GEMINI_API_KEY"
DISCORD_WEBHOOK_URL = "DEINE_DISCORD_WEBHOOK_URL" # Oder Telegram Bot Token/Chat ID

# Die URL des Videos, das du lokal herunterladen willst
VIDEO_URL = "https://www.youtube.com/watch?v=..." 

OUTPUT_FILE = "raw_video.mp4"
HIGHLIGHT_FILE = "highlight.mp4"
FINAL_OUTPUT = "final_clip.mp4"

def download_video_locally():
    print("⬇️ Lade Video lokal herunter (mit deinen Browser-Cookies)...")
    # Da du lokal bist, kannst du yt-dlp ganz normal mit deinen echten Browser-Cookies nutzen:
    # z.B. --cookies-from-browser chrome
    subprocess.run([
        "yt-dlp", 
        "--cookies-from-browser", "chrome",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]", 
        "-o", OUTPUT_FILE, 
        VIDEO_URL
    ], check=True)

def analyze_with_gemini():
    print("🧠 Analysiere Video mit Gemini...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    uploaded_file = client.files.upload(file=OUTPUT_FILE)
    
    prompt = """
    Analysiere dieses Video. Suche nach dem actionreichsten Moment.
    Beachte folgende Regeln:
    1. Der Clip MUSS exakt eine Länge von 30 Sekunden haben.
    2. Gib mir den Startzeitpunkt im Format HH:MM:SS zurück.
    Antworte ausschliesslich in folgendem JSON-Format:
    {"start": "00:01:20", "description": "Epischer Action-Moment"}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[uploaded_file, prompt]
    )
    
    client.files.delete(name=uploaded_file.name)
    
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    data = json.loads(clean_text)
    return data["start"]

def cut_and_process_clip(start_time):
    print(f"✂️ Schneide Clip ab {start_time} (exakt 30 Sekunden)...")
    cmd = [
        "ffmpeg", "-y", 
        "-ss", start_time, 
        "-i", OUTPUT_FILE, 
        "-t", "30", 
        "-c:v", "libx264", "-c:a", "aac", 
        HIGHLIGHT_FILE
    ]
    subprocess.run(cmd, check=True)
    os.rename(HIGHLIGHT_FILE, FINAL_OUTPUT)

def send_to_discord():
    print("📤 Sende Clip an Discord...")
    with open(FINAL_OUTPUT, "rb") as video_file:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data={"content": "🎮 **Dein lokaler Highlight-Clip!** (Erstellt mit Gemini & FFmpeg)"},
            files={"file": video_file}
        )
    print("Discord Antwort:", response.status_code)

if __name__ == "__main__":
    download_video_locally()
    start_time = analyze_with_gemini()
    cut_and_process_clip(start_time)
    send_to_discord()
