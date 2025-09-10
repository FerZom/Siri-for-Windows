import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import speech_recognition as sr
from plyer import notification
import pystray
from PIL import Image, ImageTk
from rapidfuzz import fuzz
import webbrowser
import stanza
import requests
import schedule
import time
import sqlite3
from datetime import datetime
import logging
import re
import wikipediaapi
import sympy as sp
try:
    from gtts import gTTS
    from pydub import AudioSegment
    import playsound
    GTTS_AVAILABLE = True
except ImportError as e:
    GTTS_AVAILABLE = False
    logging.error(f"gTTS or pydub import failed: {e}")
    notification.notify(title="Asistan", message="Sesli yanıt için gTTS veya pydub eksik, pyttsx3 kullanılacak.", app_name="Asistan")
import pyttsx3
import uuid
from dotenv import load_dotenv
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from joblib import Memory
import datetime as dt
import base64
import urllib.parse

# ---------------- LOGGING ----------------
logging.basicConfig(filename="assistant.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------- AYARLAR ----------------
ICON_ON_PATH = r"C:\Users\berat\OneDrive\Desktop\bilgisayarsiri\aktif.png"
ICON_OFF_PATH = r"C:\Users\berat\OneDrive\Desktop\bilgisayarsiri\pasif.png"
WEATHER_API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"  # OpenWeatherMap API anahtarınızı buraya ekleyin
MUSIC_FOLDER = r"C:\Users\berat\Music"  # Müzik klasörünüz
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
load_dotenv()
XAI_API_KEY = "API_ADDRESS"
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SPOTIFY_CLIENT_ID = "CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "CLIENT_SECRET"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"


try:
    nlp = stanza.Pipeline(lang='tr', processors='tokenize,pos,ner')
    logging.info("Stanza Turkish model loaded successfully")
except Exception as e:
    logging.error(f"Failed to load Stanza model: {e}")
    nlp = None
    notification.notify(title="Asistan", message="Türkçe NLP modeli yüklenemedi, basit eşleme kullanılacak.", app_name="Asistan")

# Önbellekleme için joblib
cachedir = "./cache"
memory = Memory(cachedir, verbose=0)
cached_nlp = memory.cache(nlp.process) if nlp else None

wiki = wikipediaapi.Wikipedia(
    user_agent="MyTurkishAssistant/1.0 (beratardiic@gmail.com)",  # Burayı kendi bilgilerinizle değiştirin
    language='tr'
)
recognizer = sr.Recognizer()
mic_list = list(dict.fromkeys(sr.Microphone.list_microphone_names()))
selected_mic_index = 0
listening = False
categories = {}
tray_icon = None
command_history = []
engine = pyttsx3.init() if not GTTS_AVAILABLE else None
engine.say("Merhaba")
engine.runAndWait()
volume_level = 1.0  # Varsayılan ses seviyesi (0.0 - 1.0)
stop_event = threading.Event()
tts_cache = {}  # gTTS önbelleği
spotify_token = None
spotify_token_expiry = None

# Grok API istemcisi
grok_client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1") if XAI_API_KEY else None

# Basit bilgi tabanı
KNOWLEDGE_BASE = {
    "türkiye'nin başkenti": "Türkiye'nin başkenti Ankara'dır.",
    "dünyanın en yüksek dağı": "Dünyanın en yüksek dağı Everest Dağı'dır.",
    "istanbul'un nüfusu": "İstanbul'un nüfusu yaklaşık 15 milyon civarındadır.",
}

# Fikir danışmanlığı tabanı
IDEA_BASE = {
    "proje": "Projen için şu adımları deneyebilirsin: 1) Hedeflerini netleştir, 2) Bir plan oluştur, 3) Küçük adımlarla başla. Daha fazla detay verirsen, özel öneriler sunabilirim!",
    "zaman yönetimi": "Zaman yönetimi için Pomodoro tekniğini kullanabilirsin: 25 dakika çalışma, 5 dakika mola. Önemli görevleri sabah halletmek de faydalı olabilir.",
    "motivasyon": "Motivasyonun düşükse, küçük bir hedef belirle ve başardığında kendini ödüllendir. İlham verici bir kitap veya podcast da yardımcı olabilir!"
}

# ---------------- SPOTIFY API ----------------
def get_spotify_token():
    global spotify_token, spotify_token_expiry
    if spotify_token and spotify_token_expiry and spotify_token_expiry > datetime.now():
        return spotify_token
    try:
        # Kullanıcı yetkilendirme için tarayıcı aç
        auth_url = (
            f"https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}"
            f"&response_type=code&redirect_uri={urllib.parse.quote(SPOTIFY_REDIRECT_URI)}"
            "&scope=user-modify-playback-state%20user-read-playback-state"
        )
        webbrowser.open(auth_url)
        code = ctk.CTkInputDialog(text="Spotify yetkilendirme kodunu girin (tarayıcıdan kopyalayın):", title="Spotify Yetkilendirme").get_input()
        if not code:
            raise Exception("Yetkilendirme kodu sağlanmadı")
        
        # Token alma
        auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        headers = {"Authorization": f"Basic {auth_base64}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI
        }
        response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        spotify_token = token_data["access_token"]
        spotify_token_expiry = datetime.now() + dt.timedelta(seconds=token_data["expires_in"])
        logging.info("Spotify token alındı")
        return spotify_token
    except Exception as e:
        logging.error(f"Spotify token alma hatası: {e}")
        notification.notify(title="Asistan", message=f"Spotify yetkilendirme hatası: {e}", app_name="Asistan")
        return None

def play_spotify_song(song_name):
    if stop_event.is_set():
        return
    try:
        token = get_spotify_token()
        if not token:
            raise Exception("Spotify token alınamadı")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Şarkı arama
        search_url = f"https://api.spotify.com/v1/search?q={urllib.parse.quote(song_name)}&type=track&limit=1"
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        tracks = response.json().get("tracks", {}).get("items", [])
        if not tracks:
            raise Exception("Şarkı bulunamadı")
        
        track_uri = tracks[0]["uri"]
        
        # Şarkıyı çal
        play_url = "https://api.spotify.com/v1/me/player/play"
        data = {"uris": [track_uri]}
        response = requests.put(play_url, headers=headers, json=data)
        response.raise_for_status()
        message = f"{song_name} Spotify'da çalınıyor"
        notification.notify(title="Asistan", message=message, app_name="Asistan")
        speak(message)
        logging.info(f"Spotify şarkı çalındı: {song_name}")
    except Exception as e:
        notification.notify(title="Asistan", message=f"Spotify şarkı çalma hatası: {e}", app_name="Asistan")
        logging.error(f"Spotify şarkı çalma hatası: {e}")

# ---------------- VERİTABANI ----------------
def init_db():
    try:
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS commands
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      command TEXT,
                      category TEXT,
                      timestamp TEXT,
                      count INTEGER DEFAULT 1)''')
        c.execute('''CREATE TABLE IF NOT EXISTS reminders
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      reminder_text TEXT,
                      reminder_time TEXT)''')
        conn.commit()
        conn.close()
        logging.info("Database initialized")
    except Exception as e:
        logging.error(f"Database initialization error: {e}")
        notification.notify(title="Asistan", message="Veritabanı başlatılamadı.", app_name="Asistan")

def log_command(command, category):
    try:
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("SELECT count FROM commands WHERE command = ? AND category = ?", (command, category))
        result = c.fetchone()
        if result:
            c.execute("UPDATE commands SET count = count + 1, timestamp = ? WHERE command = ? AND category = ?",
                      (datetime.now().isoformat(), command, category))
        else:
            c.execute("INSERT INTO commands (command, category, timestamp, count) VALUES (?, ?, ?, 1)",
                      (command, category, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        command_history.append((command, category))
        logging.info(f"Command logged: {command} (Category: {category})")
        display_log()
    except Exception as e:
        logging.error(f"Database error: {e}")

def get_favorite_command():
    try:
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("SELECT command FROM commands ORDER BY count DESC LIMIT 1")
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Error getting favorite command: {e}")
        return None

def get_command_log(filter_text="", sort_by="timestamp"):
    try:
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        query = f"SELECT command, category, timestamp, count FROM commands WHERE command LIKE ? ORDER BY {sort_by} DESC"
        c.execute(query, (f"%{filter_text}%",))
        logs = c.fetchall()
        conn.close()
        return logs
    except Exception as e:
        logging.error(f"Error fetching command log: {e}")
        return []

def add_reminder(text, reminder_time):
    if stop_event.is_set():
        return
    try:
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("INSERT INTO reminders (reminder_text, reminder_time) VALUES (?, ?)", (text, reminder_time))
        conn.commit()
        conn.close()
        schedule.every().day.at(reminder_time).do(lambda: notify_reminder(text))
        logging.info(f"Reminder added: {text} at {reminder_time}")
    except Exception as e:
        logging.error(f"Error adding reminder: {e}")

def notify_reminder(text):
    if stop_event.is_set():
        return
    notification.notify(title="Asistan Hatırlatıcı", message=text, app_name="Asistan")
    speak(f"Hatırlatıcı: {text}")

def export_logs_to_csv():
    try:
        import csv
        logs = get_command_log()
        with open("command_log.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Komut", "Kategori", "Zaman", "Sıklık"])
            writer.writerows(logs)
        notification.notify(title="Asistan", message="Loglar command_log.csv dosyasına dışa aktarıldı.", app_name="Asistan")
        logging.info("Logs exported to command_log.csv")
    except Exception as e:
        notification.notify(title="Asistan", message=f"Log dışa aktarma hatası: {e}", app_name="Asistan")
        logging.error(f"Log export error: {e}")

# ---------------- TTS ----------------
def speak(text):
    if stop_event.is_set():
        return
    try:
        if GTTS_AVAILABLE:
            if text in tts_cache:
                audio = AudioSegment.from_file(tts_cache[text])
            else:
                tts = gTTS(text=text, lang='tr')
                temp_file = f"temp_{uuid.uuid4()}.mp3"
                tts.save(temp_file)
                audio = AudioSegment.from_mp3(temp_file)
                tts_cache[text] = temp_file
            audio = audio + (20 * (volume_level - 1))  # Ses seviyesini ayarla
            temp_file = f"temp_{uuid.uuid4()}_vol.mp3"
            audio.export(temp_file, format="mp3")
            playsound.playsound(temp_file)
            if text not in tts_cache:
                os.remove(temp_file)
            logging.info(f"Spoken: {text}")
        else:
            engine.say(text)
            engine.runAndWait()
            logging.info(f"Fallback to pyttsx3: {text}")
    except Exception as e:
        logging.error(f"TTS error: {e}")
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            logging.info(f"Fallback to pyttsx3: {text}")
        except Exception as e2:
            notification.notify(title="Asistan", message="Sesli yanıt oluşturulamadı.", app_name="Asistan")
            logging.error(f"pyttsx3 fallback error: {e2}")

# ---------------- SES KONTROLÜ ----------------
def set_volume(level):
    global volume_level
    volume_level = max(0.0, min(1.0, level))
    notification.notify(title="Asistan", message=f"Ses seviyesi: {int(volume_level * 100)}%", app_name="Asistan")
    speak(f"Ses seviyesi yüzde {int(volume_level * 100)} olarak ayarlandı")
    logging.info(f"Volume set to: {volume_level}")

# ---------------- E-POSTA GÖNDERME ----------------
def send_email(recipient, subject, body="Bu bir test e-postasıdır."):
    if stop_event.is_set():
        return
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = recipient
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())
        message = f"E-posta gönderildi: {recipient} - {subject}"
        notification.notify(title="Asistan", message=message, app_name="Asistan")
        speak(message)
        logging.info(message)
    except Exception as e:
        notification.notify(title="Asistan", message=f"E-posta gönderme hatası: {e}", app_name="Asistan")
        logging.error(f"Email sending error: {e}")

# ---------------- TAKVİM ENTEGRASYONU ----------------
def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def add_calendar_event(summary, start_time):
    if stop_event.is_set():
        return
    try:
        service = get_calendar_service()
        event = {
            'summary': summary,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Europe/Istanbul'},
            'end': {'dateTime': (start_time + dt.timedelta(hours=1)).isoformat(), 'timeZone': 'Europe/Istanbul'},
        }
        event = service.events().insert(calendarId='primary', body=event).execute()
        message = f"Etkinlik eklendi: {summary} - {start_time}"
        notification.notify(title="Asistan", message=message, app_name="Asistan")
        speak(message)
        logging.info(message)
    except Exception as e:
        notification.notify(title="Asistan", message=f"Takvim etkinliği ekleme hatası: {e}", app_name="Asistan")
        logging.error(f"Calendar event error: {e}")

# ---------------- YEREL MÜZİK ÇALMA ----------------
def play_local_music(song_name):
    if stop_event.is_set():
        return
    try:
        for file in os.listdir(MUSIC_FOLDER):
            if song_name.lower() in file.lower() and file.endswith('.mp3'):
                song_path = os.path.join(MUSIC_FOLDER, file)
                audio = AudioSegment.from_mp3(song_path)
                audio = audio + (20 * (volume_level - 1))
                temp_file = f"temp_{uuid.uuid4()}_local.mp3"
                audio.export(temp_file, format="mp3")
                playsound.playsound(temp_file)
                os.remove(temp_file)
                message = f"Yerel şarkı çalınıyor: {song_name}"
                notification.notify(title="Asistan", message=message, app_name="Asistan")
                speak(message)
                logging.info(message)
                return
        raise Exception("Şarkı bulunamadı")
    except Exception as e:
        notification.notify(title="Asistan", message=f"Yerel şarkı çalma hatası: {e}", app_name="Asistan")
        logging.error(f"Local music error: {e}")

# ---------------- GROK API ----------------
def query_grok(question, context=None, max_tokens=500, temperature=0.7):
    """
    Gelişmiş Grok sorgu fonksiyonu
    """
    if stop_event.is_set():
        return None
    try:
        if not grok_client:
            raise Exception("Grok API anahtarı eksik")
        
        # Context ekleme (önceki konuşmaları hatırlamak için)
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        
        # Türkçe prompt optimizasyonu
        enhanced_prompt = f"""
        Sen Türkçe konuşan bir yapay zeka asistanısın. 
        Aşağıdaki soruya dostane ve yardımsever bir şekilde yanıt ver:
        
        {question}
        
        Yanıtını Türkçe ve anlaşılır bir şekilde ver.
        """
        
        messages.append({"role": "user", "content": enhanced_prompt})
        
        response = grok_client.chat.completions.create(
            model="grok-3",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9
        )
        
        answer = response.choices[0].message.content.strip()
        logging.info(f"Grok response: {question} -> {answer[:100]}...")
        return answer
        
    except Exception as e:
        logging.error(f"Grok API error: {e}")
        return f"Üzgünüm, Grok API'sine bağlanırken hata oluştu: {str(e)}"

# ---------------- KOMUTLAR ----------------
def handle_command(command):
    if stop_event.is_set():
        return
    command_lower = command.lower()
    open_actions = ["aç", "başlat", "çalıştır", "göster"]
    search_actions = ["ara", "arama", "google", "bul"]
    weather_actions = ["hava", "hava durumu"]
    reminder_actions = ["hatırlat", "hatırlatıcı", "ekle"]
    system_actions = ["kapat", "yeniden başlat", "uyku"]
    math_actions = ["artı", "eksi", "çarpı", "bölü", "çöz", "türev", "integral"]
    question_actions = ["nedi", "nedir", "kimdi", "kimdir", "neresi", "nere"]
    idea_actions = ["fikir", "öneri", "ne yapayım", "nasıl yapayım"]
    stop_actions = ["dur", "sus", "iptal et"]
    email_actions = ["e-posta", "email", "gönder"]
    music_actions = ["çal", "şarkı", "müzik"]
    calendar_actions = ["etkinlik", "takvim", "ekle"]

    # Stanza ile NLP
    doc = cached_nlp(command_lower) if nlp else None

    # Kategori belirle
    category = "Bilinmeyen"
    if any(fuzz.partial_ratio(act, command_lower) >= 70 for act in open_actions):
        category = "Uygulama Açma"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in search_actions):
        category = "Arama"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in weather_actions):
        category = "Hava Durumu"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in reminder_actions):
        category = "Hatırlatıcı"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in system_actions):
        category = "Sistem"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in math_actions):
        category = "Matematik"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in question_actions):
        category = "Soru-Cevap"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in idea_actions):
        category = "Fikir Danışmanlığı"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in stop_actions):
        category = "Durdurma"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in email_actions):
        category = "E-posta Gönderme"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in music_actions):
        category = "Müzik Çalma"
    elif any(fuzz.partial_ratio(act, command_lower) >= 70 for act in calendar_actions):
        category = "Takvim"

    log_command(command, category)

    # Durdurma/iptal komutları
    for action in stop_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            stop_event.set()
            notification.notify(title="Asistan", message="İşlem durduruldu.", app_name="Asistan")
            speak("İşlem durduruldu")
            stop_event.clear()
            logging.info("Command execution stopped")
            return

    # Ses kontrolü
    if "sesi" in command_lower and any(word in command_lower for word in ["kıs", "yükselt", "yüzde"]):
        try:
            percentage = re.search(r'yüzde\s*(\d+)', command_lower)
            if percentage:
                level = int(percentage.group(1)) / 100.0
                set_volume(level)
                return
            elif "kıs" in command_lower:
                set_volume(volume_level - 0.1)
                return
            elif "yükselt" in command_lower:
                set_volume(volume_level + 0.1)
                return
        except Exception as e:
            notification.notify(title="Asistan", message="Ses seviyesi ayarlanamadı.", app_name="Asistan")
            logging.error(f"Volume control error: {e}")
            return

    # Fikir danışmanlığı
    for action in idea_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            query = command_lower
            for act in idea_actions:
                query = query.replace(act, "")
            query = query.strip()
            response = IDEA_BASE.get(query, "Fikir için daha fazla detay verebilir misin? Öneriler sunabilirim!")
            notification.notify(title="Asistan", message=response, app_name="Asistan")
            speak(response)
            logging.info(f"Idea suggestion: {query} -> {response}")
            return

    # Soru-cevap (Wikipedia ve Grok)
    for key in KNOWLEDGE_BASE:
        if fuzz.partial_ratio(key, command_lower) >= 80:
            answer = KNOWLEDGE_BASE[key]
            notification.notify(title="Asistan", message=answer, app_name="Asistan")
            speak(answer)
            logging.info(f"Question answered (local): {key} -> {answer}")
            return
    if doc:
        for sent in doc.sentences:
            for word in sent.words:
                if word.text in question_actions:
                    question = command_lower.replace(word.text, "").strip()
                    try:
                        page = wiki.page(question)
                        if page.exists():
                            answer = page.summary[:200] + "..." if len(page.summary) > 200 else page.summary
                        else:
                            answer = query_grok(question) or KNOWLEDGE_BASE.get(question, "Bu soruya yanıt verebilecek bilgim yok.")
                        notification.notify(title="Asistan", message=answer, app_name="Asistan")
                        speak(answer)
                        logging.info(f"Question answered: {question} -> {answer}")
                        return
                    except Exception as e:
                        logging.error(f"Wikipedia error: {e}")
                        answer = query_grok(question) or "Wikipedia’dan bilgi alınamadı."
                        notification.notify(title="Asistan", message=answer, app_name="Asistan")
                        speak(answer)
                        return

    # Matematiksel işlemler
    for action in math_actions:
        if action in command_lower:
            try:
                if action in ["artı", "eksi", "çarpı", "bölü"]:
                    numbers = [float(n) for n in re.findall(r'\d+\.?\d*', command_lower)]
                    if len(numbers) >= 2:
                        if action == "artı":
                            result = numbers[0] + numbers[1]
                        elif action == "eksi":
                            result = numbers[0] - numbers[1]
                        elif action == "çarpı":
                            result = numbers[0] * numbers[1]
                        elif action == "bölü":
                            result = numbers[0] / numbers[1]
                        message = f"Sonuç: {result}"
                        notification.notify(title="Asistan", message=message, app_name="Asistan")
                        speak(message)
                        logging.info(f"Math operation: {command_lower} -> {result}")
                        return
                elif action == "çöz":
                    x = sp.Symbol('x')
                    expr = command_lower.replace("çöz", "").replace("kare", "**2").replace("artı", "+").replace("eksi", "-").strip()
                    eq = sp.sympify(expr)
                    solutions = sp.solve(eq, x)
                    message = f"Çözüm: {solutions}"
                    notification.notify(title="Asistan", message=message, app_name="Asistan")
                    speak(message)
                    logging.info(f"Equation solved: {expr} -> {solutions}")
                    return
                elif action == "türev":
                    x = sp.Symbol('x')
                    expr = command_lower.replace("türev", "").replace("kare", "**2").replace("artı", "+").replace("eksi", "-").strip()
                    deriv = sp.diff(sp.sympify(expr), x)
                    message = f"Türev: {deriv}"
                    notification.notify(title="Asistan", message=message, app_name="Asistan")
                    speak(message)
                    logging.info(f"Derivative: {expr} -> {deriv}")
                    return
                elif action == "integral":
                    x = sp.Symbol('x')
                    expr = command_lower.replace("integral", "").replace("kare", "**2").replace("artı", "+").replace("eksi", "-").strip()
                    integ = sp.integrate(sp.sympify(expr), x)
                    message = f"İntegral: {integ}"
                    notification.notify(title="Asistan", message=message, app_name="Asistan")
                    speak(message)
                    logging.info(f"Integral: {expr} -> {integ}")
                    return
            except Exception as e:
                notification.notify(title="Asistan", message="Matematik işlemi yapılamadı, lütfen ifadeyi net belirtin.", app_name="Asistan")
                logging.error(f"Math error: {e}")
                return

    # İnternet arama
    for action in search_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            query = command_lower
            for act in search_actions:
                query = query.replace(act, "")
            query = query.strip()
            if query:
                try:
                    webbrowser.open(f"https://www.google.com/search?q={query}")
                    notification.notify(title="Asistan", message=f"{query} aranıyor...", app_name="Asistan")
                    speak(f"{query} aranıyor")
                    logging.info(f"Search executed: {query}")
                except Exception as e:
                    notification.notify(title="Asistan", message=f"Arama hatası: {e}", app_name="Asistan")
                    logging.error(f"Search error: {e}")
                return

    # Hava durumu
    for action in weather_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            city = None
            if doc:
                for sent in doc.sentences:
                    for word in sent.words:
                        if word.ner.startswith("B-LOC") or word.ner.startswith("I-LOC"):
                            city = word.text
                            break
                    if city:
                        break
            if not city:
                words = command_lower.split()
                for word in words:
                    if word not in weather_actions and word not in ["için", "ne", "nasıl"]:
                        city = word
                        break
                city = city or "Istanbul"
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=tr"
                response = requests.get(url).json()
                if response.get("cod") != 200:
                    raise Exception(response.get("message", "Hata"))
                temp = response["main"]["temp"]
                desc = response["weather"][0]["description"]
                message = f"{city} için hava durumu: {desc}, {temp}°C"
                notification.notify(title="Asistan", message=message, app_name="Asistan")
                speak(message)
                logging.info(f"Weather fetched: {message}")
            except Exception as e:
                notification.notify(title="Asistan", message=f"Hava durumu alınamadı: {e}", app_name="Asistan")
                logging.error(f"Weather error: {e}")
            return

    # Hatırlatıcı
    for action in reminder_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            reminder_text = None
            reminder_time = None
            if doc:
                for sent in doc.sentences:
                    for word in sent.words:
                        if word.upos == "NOUN" and not reminder_text:
                            reminder_text = word.text
                        elif word.text.count(":") == 1 and word.text.replace(":", "").isdigit():
                            reminder_time = word.text
            if not reminder_text or not reminder_time:
                reminder_text = command_lower
                for act in reminder_actions:
                    reminder_text = reminder_text.replace(act, "")
                reminder_text = reminder_text.strip()
                reminder_time = "10:00"
            if reminder_text and reminder_time:
                add_reminder(reminder_text, reminder_time)
                message = f"Hatırlatıcı eklendi: {reminder_text} saat {reminder_time}"
                notification.notify(title="Asistan", message=message, app_name="Asistan")
                speak(message)
                logging.info(f"Reminder set: {message}")
            else:
                notification.notify(title="Asistan", message="Hatırlatıcı için metin ve saat belirtin.", app_name="Asistan")
                logging.warning("Invalid reminder command")
            return

    # Sistem komutları
    for action in system_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            if messagebox.askyesno("Onay", f"Bilgisayarı {action} yapmak istediğinize emin misiniz?"):
                try:
                    if action == "kapat":
                        os.system("shutdown /s /t 1")
                    elif action == "yeniden başlat":
                        os.system("shutdown /r /t 1")
                    elif action == "uyku":
                        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                    notification.notify(title="Asistan", message=f"Sistem {action} komutu işleniyor", app_name="Asistan")
                    speak(f"Sistem {action} yapılıyor")
                    logging.info(f"System command executed: {action}")
                except Exception as e:
                    notification.notify(title="Asistan", message=f"Sistem komutu başarısız: {e}", app_name="Asistan")
                    logging.error(f"System command error: {e}")
                return

    # E-posta gönderme
    for action in email_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            recipient = None
            subject = None
            if doc:
                for sent in doc.sentences:
                    for word in sent.words:
                        if word.ner.startswith("B-PER") or word.ner.startswith("I-PER"):
                            recipient = word.text + "@example.com"
                        elif word.upos == "NOUN" and not subject:
                            subject = word.text
            if not recipient or not subject:
                recipient = command_lower.split("adresine")[1].split()[0] if "adresine" in command_lower else "test@example.com"
                subject = command_lower.split("hakkında")[1].strip() if "hakkında" in command_lower else "Test"
            send_email(recipient, subject)
            return

    # Müzik çalma
    for action in music_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            song_name = command_lower
            for act in music_actions:
                song_name = song_name.replace(act, "")
            song_name = song_name.strip()
            if song_name:
                try:
                    # Önce Spotify’da dene
                    play_spotify_song(song_name)
                except Exception:
                    # Spotify başarısızsa yerel müzik çal
                    play_local_music(song_name)
                return

    # Takvim etkinliği
    for action in calendar_actions:
        if fuzz.partial_ratio(action, command_lower) >= 70:
            summary = None
            time_str = None
            if doc:
                for sent in doc.sentences:
                    for word in sent.words:
                        if word.upos == "NOUN" and not summary:
                            summary = word.text
                        elif word.text.count(":") == 1 and word.text.replace(":", "").isdigit():
                            time_str = word.text
            if not summary or not time_str:
                summary = command_lower
                for act in calendar_actions:
                    summary = summary.replace(act, "")
                summary = summary.strip()
                time_str = "10:00"
            try:
                start_time = datetime.strptime(f"{datetime.now().date()} {time_str}", "%Y-%m-%d %H:%M")
                add_calendar_event(summary, start_time)
            except Exception as e:
                notification.notify(title="Asistan", message=f"Takvim etkinliği ekleme hatası: {e}", app_name="Asistan")
                logging.error(f"Calendar event error: {e}")
            return

    # Favori komut
    if fuzz.partial_ratio("en sevdiğim", command_lower) >= 70 or fuzz.partial_ratio("favori", command_lower) >= 70:
        fav_command = get_favorite_command()
        if fav_command:
            handle_command(fav_command)
            return

    # Uygulama/Dosya/Klasör açma
    for cat, app_list in categories.items():
        for app in app_list:
            if not app['active']:
                continue
            triggers = [app['command'].lower()] + [alias.lower() for alias in app.get('aliases', [])]
            for trigger in triggers:
                if fuzz.partial_ratio(trigger, command_lower) >= 70:
                    if any(fuzz.partial_ratio(act, command_lower) >= 70 for act in open_actions):
                        try:
                            os.startfile(app['path'])
                            notification.notify(title="Asistan", message=f"{app['name']} açılıyor", app_name="Asistan")
                            speak(f"{app['name']} açılıyor")
                            logging.info(f"App opened: {app['name']}")
                        except Exception as e:
                            notification.notify(title="Asistan", message=f"{app['name']} açılamadı: {e}", app_name="Asistan")
                            logging.error(f"App open error: {e}")
                        return

    # BURASI DEĞİŞTİ: Tanınmayan komutlar için Grok'a yönlendir
    ###############################################################
    # GROK FALLBACK - Tanınmayan tüm komutlar için
    ###############################################################
    try:
        # Önce kullanıcıya düşündüğümüzü söyleyelim
        notification.notify(title="Asistan", message="Düşünüyorum...", app_name="Asistan")
        speak("Biraz düşüneyim")
        
        # Grok API'sini kullan
        grok_response = query_grok(command)
        
        if grok_response:
            notification.notify(title="Asistan", message=grok_response, app_name="Asistan")
            speak(grok_response)
            logging.info(f"Grok response to unknown command: {command} -> {grok_response}")
        else:
            notification.notify(title="Asistan", message="Bu soruya yanıt veremiyorum", app_name="Asistan")
            speak("Bu soruya yanıt veremiyorum")
            logging.warning(f"Grok failed for command: {command}")
            
    except Exception as e:
        notification.notify(title="Asistan", message=f"Hata oluştu: {str(e)}", app_name="Asistan")
        speak("Üzgünüm, bir hata oluştu")
        logging.error(f"Grok fallback error: {e}")

# ---------------- DİNLEME ----------------
def listen_loop():
    global listening
    r = sr.Recognizer()
    with sr.Microphone(device_index=selected_mic_index) as source:
        while listening:
            if stop_event.is_set():
                continue
            try:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=5, phrase_time_limit=10)
                command = r.recognize_google(audio, language='tr-TR').lower()
                if "asistan" in command:
                    notification.notify(title="Asistan", message="Dinliyorum...", app_name="Asistan")
                    speak("Dinliyorum")
                    audio = r.listen(source, timeout=5, phrase_time_limit=10)
                    cmd = r.recognize_google(audio, language='tr-TR')
                    handle_command(cmd)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                notification.notify(title="Asistan", message=f"Servise ulaşılamıyor: {e}", app_name="Asistan")
                logging.error(f"Speech recognition error: {e}")
            except Exception as e:
                notification.notify(title="Asistan", message=f"Hata oluştu: {e}", app_name="Asistan")
                logging.error(f"General error: {e}")
            time.sleep(0.1)

def run_scheduler():
    while True:
        if not stop_event.is_set():
            schedule.run_pending()
        time.sleep(1)

# ---------------- TRAY ----------------
def toggle_listening(icon, item):
    global listening
    if not listening:
        listening = True
        icon.icon = Image.open(ICON_ON_PATH)
        threading.Thread(target=listen_loop, daemon=True).start()
    else:
        listening = False
        stop_event.set()
        icon.icon = Image.open(ICON_OFF_PATH)
        stop_event.clear()

def stop(icon, item):
    global listening
    listening = False
    stop_event.set()
    icon.stop()

def open_menu(icon, item):
    def show_root():
        if not root.winfo_viewable():
            root.deiconify()
            root.lift()
    threading.Thread(target=show_root).start()

def start_assistant():
    global selected_mic_index, tray_icon, listening
    mic_name = mic_combo.get()
    try:
        selected_mic_index = mic_list.index(mic_name)
    except ValueError:
        selected_mic_index = None
    listening = True
    stop_event.clear()
    root.withdraw()
    
    threading.Thread(target=listen_loop, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    notification.notify(title="Asistan", message="Asistan sizi dinliyor (tepsiden kontrol edebilirsiniz)", app_name="Asistan")
    speak("Asistan başlatıldı")
    logging.info("Assistant started")

    menu = pystray.Menu(
        pystray.MenuItem("🤖 Asistan", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🎙️ Dinlemeyi Başlat/Durdur", toggle_listening),
        pystray.MenuItem("📂 Menüyü Aç", open_menu),
        pystray.MenuItem("❌ Çıkış", stop)
    )

    tray_icon = pystray.Icon("Asistan", Image.open(ICON_OFF_PATH), "Asistan", menu)
    threading.Thread(target=tray_icon.run, daemon=True).start()

# ---------------- UYGULAMA/DOSYA/KLASÖR EKLEME ----------------
def add_app():
    path = filedialog.askopenfilename(title="Uygulama veya Dosya Seç")
    if path:
        name = os.path.basename(path)
        add_item(name, path)

def add_folder():
    path = filedialog.askdirectory(title="Klasör Seç")
    if path:
        name = os.path.basename(path)
        add_item(name, path)

def add_item(name, path):
    cmd_word = ctk.CTkInputDialog(text=f"{name} için tetikleme kelimesi girin:", title="Tetikleme Kelimesi").get_input()
    if not cmd_word:
        return
    alias_input = ctk.CTkInputDialog(text=f"{name} için ek aliaslar (virgülle ayır):", title="Aliaslar").get_input()
    aliases = [a.strip() for a in alias_input.split(",")] if alias_input else []
    category_input = ctk.CTkInputDialog(text=f"Kategori girin (varsayılan: Genel):", title="Kategori").get_input()
    category = category_input.strip() if category_input else "Genel"
    app_data = {"name": name, "path": path, "command": cmd_word, "aliases": aliases, "active": True, "frame": None, "category": category}
    if category not in categories:
        categories[category] = []
        tabview.add(category)
    categories[category].append(app_data)
    insert_app_in_frame(app_data)
    logging.info(f"Item added: {name} in category {category}")

def insert_app_in_frame(app_data):
    cat = app_data['category']
    frame = ctk.CTkFrame(tabview.tab(cat))
    frame.pack(fill="x", pady=2, padx=2)
    app_data['frame'] = frame

    def toggle_active():
        app_data['active'] = not app_data['active']
        btn_active.configure(text="✅" if app_data['active'] else "❌")

    btn_active = ctk.CTkButton(frame, text="✅", width=32, command=toggle_active)
    btn_active.pack(side="left", padx=5)

    label_name = ctk.CTkLabel(frame, text=app_data['name'], width=150, anchor="w")
    label_name.pack(side="left", padx=5)

    label_cmd = ctk.CTkLabel(frame, text=f"({app_data['command']})", anchor="w")
    label_cmd.pack(side="left", padx=5)

    def move_up():
        app_list = categories[cat]
        idx = app_list.index(app_data)
        if idx > 0:
            app_list[idx], app_list[idx-1] = app_list[idx-1], app_list[idx]
            refresh_tab(cat)

    def move_down():
        app_list = categories[cat]
        idx = app_list.index(app_data)
        if idx < len(app_list) - 1:
            app_list[idx], app_list[idx+1] = app_list[idx+1], app_list[idx]
            refresh_tab(cat)

    btn_down = ctk.CTkButton(frame, text="↓", width=32, command=move_down)
    btn_down.pack(side="right", padx=5)
    btn_up = ctk.CTkButton(frame, text="↑", width=32, command=move_up)
    btn_up.pack(side="right", padx=5)

def refresh_tab(cat):
    for child in tabview.tab(cat).winfo_children():
        child.destroy()
    for app in categories[cat]:
        insert_app_in_frame(app)

def remove_app():
    all_frames = []
    for tab_name in tabview.get():
        if tab_name != "Log":
            all_frames.extend([child for child in tabview.tab(tab_name).winfo_children() if isinstance(child, ctk.CTkFrame)])
    if all_frames:
        frame_to_remove = all_frames[-1]
        for cat, app_list in categories.items():
            for app in app_list[:]:
                if app['frame'] == frame_to_remove:
                    app_list.remove(app)
                    frame_to_remove.destroy()
                    if not app_list:
                        tabview.delete(cat)
                    logging.info(f"Item removed from category {cat}")
                    return

# ---------------- LOG SAYFASI ----------------
def display_log():
    for child in tabview.tab("Log").winfo_children():
        child.destroy()
    
    filter_frame = ctk.CTkFrame(tabview.tab("Log"))
    filter_frame.pack(fill="x", pady=5)
    ctk.CTkLabel(filter_frame, text="Filtrele (Komut):").pack(side="left", padx=5)
    filter_entry = ctk.CTkEntry(filter_frame, width=200)
    filter_entry.pack(side="left", padx=5)
    sort_var = ctk.StringVar(value="timestamp")
    ctk.CTkOptionMenu(filter_frame, values=["timestamp", "count"], variable=sort_var, width=100).pack(side="left", padx=5)
    
    def update_log():
        logs = get_command_log(filter_entry.get(), sort_var.get())
        log_frame = ctk.CTkFrame(tabview.tab("Log"))
        log_frame.pack(fill="both", expand=True)
        headers = ["Komut", "Kategori", "Zaman", "Sıklık"]
        for i, header in enumerate(headers):
            ctk.CTkLabel(log_frame, text=header, font=("Arial", 12, "bold")).grid(row=0, column=i, padx=5, pady=2, sticky="w")
        for i, (command, category, timestamp, count) in enumerate(logs, 1):
            ctk.CTkLabel(log_frame, text=command, width=200, anchor="w").grid(row=i, column=0, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(log_frame, text=category, width=100, anchor="w").grid(row=i, column=1, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(log_frame, text=timestamp, width=200, anchor="w").grid(row=i, column=2, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(log_frame, text=str(count), width=50, anchor="w").grid(row=i, column=3, padx=5, pady=2, sticky="w")

    ctk.CTkButton(filter_frame, text="Filtrele/Sırala", command=update_log).pack(side="left", padx=5)
    ctk.CTkButton(filter_frame, text="CSV’ye Aktar", command=export_logs_to_csv).pack(side="left", padx=5)
    
    ctk.CTkLabel(filter_frame, text="Ses Seviyesi:").pack(side="left", padx=5)
    volume_slider = ctk.CTkSlider(filter_frame, from_=0, to=1, command=lambda value: set_volume(value), width=100)
    volume_slider.set(volume_level)
    volume_slider.pack(side="left", padx=5)
    
    update_log()

# ---------------- CUSTOM TKINTER ----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.title("Asistan Menüsü")
root.geometry("600x500")

ctk.CTkLabel(root, text="Mikrofon Seçimi:", font=("Arial", 14)).pack(pady=(10,0))
mic_combo = ctk.CTkComboBox(root, values=mic_list)
mic_combo.pack(pady=5)
mic_combo.set(mic_list[0] if mic_list else "")

ctk.CTkLabel(root, text="Öğeler:", font=("Arial", 14)).pack(pady=(15,0))
tabview = ctk.CTkTabview(root, height=200)
tabview.pack(pady=5, fill="both", expand=True)
tabview.add("Log")
display_log()

frame_buttons = ctk.CTkFrame(root)
frame_buttons.pack(pady=5)
ctk.CTkButton(frame_buttons, text="Uygulama/Dosya Ekle", command=add_app).grid(row=0, column=0, padx=5)
ctk.CTkButton(frame_buttons, text="Klasör Ekle", command=add_folder).grid(row=0, column=1, padx=5)
ctk.CTkButton(frame_buttons, text="Kaldır", command=remove_app).grid(row=0, column=2, padx=5)
ctk.CTkButton(frame_buttons, text="Asistanı Başlat", command=start_assistant).grid(row=0, column=3, padx=5)

init_db()
root.mainloop()