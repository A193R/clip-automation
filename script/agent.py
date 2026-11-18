import os
import subprocess
import requests
import json
from google import genai

# Konfiguration aus GitHub Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

INPUT_FILE = "raw_video.mp4"

def analyze_with_gemini():
    print("🧠 Analysiere Video mit Gemini für Clips und Untertitel...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    uploaded_file = client.files.upload(file=INPUT_FILE)
    
    prompt = """
    Analysiere dieses Video gründlich. Finde so viele spannende Highlight-Momente wie möglich.
    Beachte folgende Regeln:
    1. Jeder Clip MUSS exakt 60 Sekunden lang sein.
    2. Bewerte jeden Clip mit einem Rating von 1 bis 10.
    3. Gib mir für jeden Clip den Startzeitpunkt (HH:MM:SS), das Rating, eine kurze Beschreibung und eine Liste von Untertiteln mit Start- und Endzeit innerhalb des 60-Sekunden-Clips (relativ von 00:00:00 bis 00:01:00) und dem gesprochenen Text zurück.
    
    Antworte ausschließlich im folgenden JSON-Array-Format:
    [
      {
        "start": "00:01:20",
        "rating": 9,
        "description": "Epischer Action-Moment",
        "subtitles": [
          {"start_time": "00:00:00", "end_time": "00:00:03", "text": "Schau dir das an!"},
          {"start_time": "00:00:03", "end_time": "00:00:06", "text": "Das ist unglaublich heftig!"}
        ]
      }
    ]
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[uploaded_file, prompt]
    )
    
    client.files.delete(name=uploaded_file.name)
    
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    clips_data = json.loads(clean_text)
    return clips_data

def create_srt_file(subtitles, srt_filename):
    """Erstellt aus den Gemini-Daten eine standardmäßige .srt Untertiteldatei."""
    with open(srt_filename, "w", encoding="utf-8") as f:
        for idx, sub in enumerate(subtitles, start=1):
            start = sub["start_time"].replace(".", ",") + ",000" if "," not in sub["start_time"] else sub["start_time"]
            end = sub["end_time"].replace(".", ",") + ",000" if "," not in sub["end_time"] else sub["end_time"]
            
            if len(start.split(":")) == 2:
                start = "00:" + start
            if len(end.split(":")) == 2:
                end = "00:" + end
                
            f.write(f"{idx}\n{start} --> {end}\n{sub['text']}\n\n")

def process_clip_to_vertical_with_subtitles(clip_data, index):
    start_time = clip_data["start"]
    print(f"✂️ Verarbeite Clip {index+1} (Start: {start_time}) im 9:16 Format (Facecam oben, Gameplay unten)...")
    
    highlight_file = f"highlight_{index}.mp4"
    srt_file = f"subtitles_{index}.srt"
    final_output = f"final_clip_{index}.mp4"
    
    # 1. SRT-Datei generieren, falls Untertitel vorhanden sind
    if "subtitles" in clip_data and clip_data["subtitles"]:
        create_srt_file(clip_data["subtitles"], srt_file)
    
    # 2. Schritt: 60 Sekunden ausschneiden
    cmd_cut = [
        "ffmpeg", "-y", 
        "-ss", start_time, 
        "-i", INPUT_FILE, 
        "-t", "60", 
        "-c:v", "libx264", "-c:a", "aac", 
        highlight_file
    ]
    subprocess.run(cmd_cut, check=True)
    
    # 3. Schritt: 9:16 Split-Layout (Facecam oben, Gameplay unten) + Untertitel einbrennen
    if os.path.exists(srt_file):
        vf_filter = (
            "[0:v]split=2[top][bottom];"
            "[top]crop=iw:ih/2:0:0,scale=1080:960[top_scaled];"
            "[bottom]crop=iw:ih/2:0:ih/2,scale=1080:960[bottom_scaled];"
            "[top_scaled][bottom_scaled]vstack=inputs=2[stacked];"
            f"[stacked]subtitles={srt_file}:force_style='FontSize=24,PrimaryColour=&H00FFFF&,Outline=2,Alignment=2'"
        )
    else:
        vf_filter = (
            "[0:v]split=2[top][bottom];"
            "[top]crop=iw:ih/2:0:0,scale=1080:960[top_scaled];"
            "[bottom]crop=iw:ih/2:0:ih/2,scale=1080:960[bottom_scaled];"
            "[top_scaled][bottom_scaled]vstack=inputs=2"
        )

    cmd_format = [
        "ffmpeg", "-y",
        "-i", highlight_file,
        "-filter_complex", vf_filter,
        "-c:v", "libx264", "-c:a", "aac",
        final_output
    ]
    subprocess.run(cmd_format, check=True)
    
    return final_output

def send_to_telegram(output_file, rating, description):
    print(f"📤 Sende Clip (Rating: {rating}/10) an Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    
    caption = f"🔥📱 **Highlight-Clip**\n⭐ **Rating:** {rating}/10\n📝 {description}"
    
    with open(output_file, "rb") as video_file:
        response = requests.post(
            url, 
            data={
                "chat_id": TELEGRAM_CHAT_ID, 
                "caption": caption
            }, 
            files={"video": video_file}
        )
    print("Telegram Antwort:", response.status_code)

if __name__ == "__main__":
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Die Datei {INPUT_FILE} wurde nicht im Repository gefunden!")
    
    clips = analyze_with_gemini()
    
    for index, clip in enumerate(clips):
        rating = clip.get("rating", 5)
        description = clip.get("description", "Keine Beschreibung")
        
        final_clip = process_clip_to_vertical_with_subtitles(clip, index)
        send_to_telegram(final_clip, rating, description)
