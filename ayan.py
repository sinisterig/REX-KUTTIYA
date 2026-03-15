import asyncio
import uuid
import os
import json
import threading
import requests
import time
from collections import defaultdict
from flask import Flask, jsonify, Response
from instagrapi import Client
from instagrapi.exceptions import RateLimitError
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.align import Align
from dotenv import load_dotenv

load_dotenv()

ACC_FILE = os.getenv("ACC_FILE", "acc.txt")
MESSAGE_FILE = os.getenv("MESSAGE_FILE", "text.txt")
TITLE_FILE = os.getenv("TITLE_FILE", "nc.txt")

MSG_DELAY = 30
RENAME_DELAY = 180

THREAD_ID = os.getenv("THREAD_ID")  

DOC_ID = os.getenv("DOC_ID", "29088580780787855")
IG_APP_ID = os.getenv("IG_APP_ID", "936619743392459")

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("PORT", os.getenv("FLASK_PORT", 5000)))

SELF_URL = os.getenv("SELF_URL")
SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", 100))

app = Flask(__name__)
LOG_BUFFER = []

logs_ui = defaultdict(list)
console = Console()
USERS = []
MESSAGE_BLOCKS = []

@app.route('/')
def home():
    return "alive"

@app.route('/status')
def status():
    return jsonify({user: logs_ui[user] for user in USERS})

@app.route('/logs')
def logs_route():
    output = []
    header_text = "✦  SINISTERS | SX⁷  ✦"
    output.append(header_text)
    output.append("=" * len(header_text))
    output.append("")
    for user in USERS:
        output.append(f"[ {user} ]")
        output.append("-" * (len(user) + 4))
        for line in logs_ui[user]:
            output.append(line)
        output.append("")
    return Response("\n".join(output), mimetype="text/plain")

def log(console_message, clean_message=None):
    LOG_BUFFER.append(clean_message if clean_message else console_message)

def self_ping_loop():
    while True:
        if SELF_URL:
            try:
                requests.get(SELF_URL, timeout=10)
                log("🔁 Self ping successful")
            except Exception as e:
                log(f"⚠ Self ping failed: {e}")
        time.sleep(SELF_PING_INTERVAL)

MAX_PANEL_LINES = 35

def ui_log(user, message):
    logs_ui[user].append(message)
    if len(logs_ui[user]) > MAX_PANEL_LINES:
        logs_ui[user].pop(0)

def start_flask():
    import logging
    logg = logging.getLogger('werkzeug')
    logg.disabled = True
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)

def load_accounts(path):
    accounts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) >= 2:
                username = parts[0].strip()
                password = parts[1].strip()
                proxy = parts[2].strip() if len(parts) >= 3 else None
                accounts.append((username, password, proxy))
    return accounts[:5]

def load_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]

def load_message_blocks(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return [x.strip() for x in content.split(",") if x.strip()]

def setup_mobile_fingerprint(cl):
    cl.set_user_agent("Instagram 312.0.0.22.114 Android")
    uuids = {
        "phone_id": str(uuid.uuid4()),
        "uuid": str(uuid.uuid4()),
        "client_session_id": str(uuid.uuid4()),
        "advertising_id": str(uuid.uuid4()),
        "device_id": "android-" + uuid.uuid4().hex[:16]
    }
    cl.set_uuids(uuids)
    cl.private.headers.update({
        "X-IG-App-ID": IG_APP_ID,
        "X-IG-Device-ID": uuids["uuid"],
        "X-IG-Android-ID": uuids["device_id"],
    })

async def login(username, password, proxy):
    cl = Client()
    if proxy:
        cl.set_proxy(proxy)
    setup_mobile_fingerprint(cl)
    session_file = f"session_{username}.json"

    try:
        if os.path.exists(session_file):
            cl.load_settings(session_file)

        cl.login(username, password)
        cl.dump_settings(session_file)
        return cl
    except Exception:
        return None

def rename_thread(cl, thread_id, title):
    try:
        cl.private_request(
            f"direct_v2/threads/{thread_id}/update_title/",
            data={"title": title}
        )
        return True
    except RateLimitError:
        return False
    except Exception:
        return False


async def sender_loop(clients):
    msg_index = 0
    rename_index = 0
    last_rename = time.time()

    titles = load_lines(TITLE_FILE) if os.path.exists(TITLE_FILE) else []
    global MESSAGE_BLOCKS
    MESSAGE_BLOCKS = load_message_blocks(MESSAGE_FILE)

    while True:

        for user, cl in clients:

            if MESSAGE_BLOCKS:
                msg = MESSAGE_BLOCKS[msg_index % len(MESSAGE_BLOCKS)]

                try:
                    await asyncio.to_thread(
                        cl.direct_send,
                        msg,
                        thread_ids=[THREAD_ID]
                    )
                    ui_log(user, "📨 ")

                except Exception:
                    ui_log(user, "⚠ message failed")

                msg_index += 1

            now = time.time()

            if now - last_rename >= RENAME_DELAY and titles:

                title = titles[rename_index % len(titles)]

                success = await asyncio.to_thread(
                    rename_thread,
                    cl,
                    THREAD_ID,
                    title
                )

                if success:
                    ui_log(user, f"💠 → {title}")
                else:
                    ui_log(user, "⚠ rename failed")

                rename_index += 1
                last_rename = time.time()

            await asyncio.sleep(MSG_DELAY)


async def main():

    ACCOUNTS = load_accounts(ACC_FILE)

    clients = []

    for username, password, proxy in ACCOUNTS:

        cl = await login(username, password, proxy)

        if cl:
            USERS.append(username)
            ui_log(username, f"🍸 ID - {username}")
            clients.append((username, cl))

    if not clients:
        return

    await sender_loop(clients)


if __name__ == "__main__":

    threading.Thread(target=start_flask, daemon=True).start()
    threading.Thread(target=self_ping_loop, daemon=True).start()

    asyncio.run(main())
