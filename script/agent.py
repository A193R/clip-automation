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
VIDEO_URL = "https://www.youtube.com/watch?v=2f7qEDc-DEA" 
OUTPUT_FILE = "raw_video.mp4"
HIGHLIGHT_FILE = "highlight.mp4"
FINAL_OUTPUT = "final_clip.mp4"

def download_video(video_url):
    print("⬇️ Lade Video herunter (mit yt-dlp Fallback-Parametern)...")
    subprocess.run([
        "yt-dlp", 
        "--extractor-args", "youtube:player_client=android,web",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]", 
        "-o", OUTPUT_FILE, 
        video_url
    ], check=True)

def analyze_with_gemini():
    print("🧠 Analysiere Video mit Gemini (Text, Audio/Lautstärke & visuelle Highlights)...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Videodatei hochladen
    uploaded_file = client.files.upload(file=OUTPUT_FILE)
    
    # Erweiteter Prompt für Text, laute Reaktionen / Audio und Hook-Auswahl
    prompt = """
    Analysiere dieses Video gründlich. Suche nach dem absolut besten Moment, der sich perfekt als Hook eignet.
    Berücksichtige dabei:
    - Auffällige gesprochene Sätze oder spannender Text (Keywords, Dialoge).
    - Audio-Spitzen (plötzliche laute Reaktionen, Schreie, Gelächter, laute Soundeffekte).
    - Visuelle Action-Momente.
    
    Regel: Der gesuchte Highlight-Clip soll als Hook dienen und exakt 60 Sekunden lang sein.
    Gib mir den Startzeitpunkt dieses Moments im Format HH:MM:SS zurück.
    
    Antworte ausschließlich im folgenden JSON-Format:
    {"start": "00:01:20", "description": "Spannender Dialog / Lauter Reziehungs-Moment als Hook"}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[uploaded_file, prompt]
    )
    
    # Aufräumen bei Google
    client.files.delete(name=uploaded_file.name)
    
    # JSON parsen
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    data = json.loads(clean_text)
    return data["start"]

def cut_and_arrange_clip(start_time):
    print(f"✂️ Schneide 60-Sekunden-Highlight ab {start_time} aus...")
    
    # 1. Schritt: Den 60-sekündigen Highlight-Clip ausschneiden (-t 60 für exakt 60 Sekunden)
    cmd_cut = [
        "ffmpeg", "-y", 
        "-ss", start_time, 
        "-i", OUTPUT_FILE, 
        "-t", "60", 
        "-b:v", "1500k", # Bitrate optimiert fürs Telegram-Größenlimit
        "-c:v", "libx264", "-c:a", "aac", 
        HIGHLIGHT_FILE
    ]
    subprocess.run(cmd_cut, check=True)
    
    print("🔗 Setze das Highlight als Hook an den Anfang des Gesamt-Videos...")
    
    # 2. Schritt: Concat-Liste erstellen (Zuerst das 60s-Highlight, dann das komplette Originalvideo)
    with open("list.txt", "w") as f:
        f.write(f"file '{HIGHLIGHT_FILE}'\n")
        f.write(f"file '{OUTPUT_FILE}'\n")
        
    # 3. Schritt: Beide Teile nahtlos zusammenfügen
    cmd_concat = [
        "ffmpeg", "-y", 
        "-f", "concat", 
        "-safe", "0", 
        "-i", "list.txt", 
        "-c:v", "libx264", "-c:a", "aac", 
        FINAL_OUTPUT
    ]
    subprocess.run(cmd_concat, check=True)

def send_to_telegram():
    print("📤 Sende Clip an Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    with open(FINAL_OUTPUT, "rb") as video_file:
        response = requests.post(
            url, 
            data={
                "chat_id": TELEGRAM_CHAT_ID, 
                "caption": "🔥 **Automatischer 60s-Highlight-Clip (als Hook an den Anfang gesetzt)!**"
            }, 
            files={"video": video_file}
        )
    print("Telegram Antwort:", response.status_code)

if __name__ == "__main__":
    download_video()
    start_time = analyze_with_gemini()
    cut_and_arrange_clip(start_time)
    send_to_telegram()
