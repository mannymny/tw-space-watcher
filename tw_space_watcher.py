import os
import time
import requests
from bs4 import BeautifulSoup
import subprocess
import re
import json
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from threading import Thread

load_dotenv()

TWITTER_URL_BASE = os.getenv("TWITTER_URL_BASE", "https://twitter.com")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
USERS = os.getenv("USERS", "").split(",")

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

RECORDINGS_DIR = "recordings"
LOGS_DIR = "logs"
DOWNLOADED_RECORD = "downloaded.json"

os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
if not os.path.exists(DOWNLOADED_RECORD):
    with open(DOWNLOADED_RECORD, "w") as f:
        json.dump({}, f)

with open(DOWNLOADED_RECORD, "r") as f:
    downloaded = json.load(f)

def save_downloaded():
    with open(DOWNLOADED_RECORD, "w") as f:
        json.dump(downloaded, f, indent=2)

def log(username, message):
    print(f"[{username}] {message}")
    with open(f"{LOGS_DIR}/{username}.log", "a") as f:
        f.write(f"[{time.ctime()}] {message}\n")

def send_email(username, title):
    subject = f"New Space recorded: @{username}"
    body = f"A new Space was recorded from @{username}:\n\nTitle: {title}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        log(username, f"📧 Email sent: {title}")
    except Exception as e:
        log(username, f"❌ Email error: {e}")

def get_space_url(username):
    """Scrape Twitter profile for active Space URL"""
    url = f"{TWITTER_URL_BASE}/{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if "/i/spaces/" in a["href"]:
            return f"{TWITTER_URL_BASE}{a['href']}"
    return None

def wait_for_space_end(username):
    log(username, "⏳ Waiting for Space to end...")
    while get_space_url(username):
        time.sleep(CHECK_INTERVAL)
    log(username, "✅ Space ended.")

def try_download_recording(space_url, username):
    log(username, f"⬇️ Attempting to download from {space_url}")
    try:
        result = subprocess.run([
            "yt-dlp",
            space_url,
            "-o", f"{RECORDINGS_DIR}/{username}_%(title).80s.%(ext)s",
            "--print", "title",
            "--no-playlist",
            "--quiet"
        ], capture_output=True, text=True)

        title = result.stdout.strip()
        key = f"{username}|{title}"

        if not title:
            log(username, "❌ Title not found. Skipping.")
            return

        if key in downloaded:
            log(username, "⏭️ Already downloaded. Skipping.")
            return

        subprocess.run([
            "yt-dlp",
            space_url,
            "-o", f"{RECORDINGS_DIR}/{username}_%(title).80s.%(ext)s",
            "--no-playlist",
            "--quiet"
        ])
        downloaded[key] = True
        save_downloaded()
        send_email(username, title)
        log(username, f"✅ Downloaded '{title}'")
    except Exception as e:
        log(username, f"❌ Download error: {e}")

def process_user(username):
    log(username, "👀 Monitoring user...")
    while True:
        space_url = get_space_url(username)
        if space_url:
            log(username, f"🎙️ Space detected: {space_url}")
            wait_for_space_end(username)
            try_download_recording(space_url, username)
        time.sleep(CHECK_INTERVAL)

def main():
    threads = []
    for user in USERS:
        user = user.strip()
        if not user:
            continue
        thread = Thread(target=process_user, args=(user,))
        thread.start()
        threads.append(thread)

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
