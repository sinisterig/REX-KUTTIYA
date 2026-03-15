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

MSG_DELAY = int(os.getenv("MSG_DELAY", 20))
GROUP_DELAY = int(os.getenv("GROUP_DELAY", 4))

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

@app.route("/dashboard")
def dashboard():
    html = """
    <html>
    <head>
        <title>SINISTERS | SX⁷</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body { background-color: #0d1117; font-family: monospace; margin: 0; padding: 20px; color: #00ff88; }
            .header { text-align: center; font-size: 28px; font-weight: bold; margin-bottom: 30px; border: 2px solid #00ff88; padding: 10px; }
            .container { display: flex; flex-direction: row; gap: 20px; align-items: flex-start; }
            .panel { flex: 1; min-width: 300px; border: 2px solid #00ff88; background-color: #111827; padding: 15px; height: 80vh; overflow-y: auto; }
            .panel-title { font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #00ff88; padding-bottom: 5px; }
            .log-line { margin-bottom: 6px; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <div class="header">✦ SINISTERS | SX⁷ ✦</div>
        <div class="container">
    """
    for user in USERS:
        html += f'<div class="panel"><div class="panel-title">{user}</div>'
        for line in logs_ui[user]:
            html += f'<div class="log-line">{line}</div>'
        html += "</div>"
    html += """
        </div>
        <script>
        function scrollPanels() {
            document.querySelectorAll('.panel').forEach(function(panel) {
                panel.scrollTop = panel.scrollHeight;
            });
        }
        window.onload = scrollPanels;
        setInterval(scrollPanels, 1500);
        </script>
    </body>
    </html>
    """
    return html

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
    if message.startswith("⏳ ROUND"):
        header = logs_ui[user][0] if logs_ui[user] else f"🍸 ID - {user}"
        logs_ui[user] = [header, message]
        log(f"{user} | {message}", message)
        return
    logs_ui[user].append(message)
    if len(logs_ui[user]) < 2:
        log(f"{user} | {message}", message)
        return
    header = logs_ui[user][0]
    round_line = logs_ui[user][1]
    body = logs_ui[user][2:]
    if len(body) > MAX_PANEL_LINES:
        body.pop(0)
    logs_ui[user] = [header, round_line] + body
    log(f"{user} | {message}", message)

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
                proxy = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else None
                accounts.append((username, password, proxy))
    return accounts[:5]

def load_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]

def load_message_blocks(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    raw_blocks = content.split(",")
    blocks = []
    for block in raw_blocks:
        cleaned = block.strip("\n")
        if cleaned.strip():
            blocks.append(cleaned)
    return blocks

def build_layout():
    layout = Layout()
    layout.split_column(Layout(name="header", size=6), Layout(name="body"))
    layout["body"].split_row(*[Layout(name=user) for user in USERS])
    header_layout = Layout()
    header_layout.split_column(
        Layout(Panel(Align.center("[bold bright_green]SINISTERS | SX⁷[/bold bright_green]"), border_style="bright_green"), size=3),
        Layout(Panel(Align.center("[bold bright_green]MAHABHARAT | ASTRA[/bold bright_green]"), border_style="bright_green"), size=3),
    )
    layout["header"].update(header_layout)
    return layout

def render_layout(layout):
    for user in USERS:
        content = "\n".join(logs_ui[user])
        panel = Panel(
            content,
            title=f"[bold bright_green]{user}[/bold bright_green]",
            border_style="bright_green",
            padding=(0, 1),
            expand=True
        )
        layout["body"][user].update(panel)

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
        cl.private_request(f"direct_v2/threads/{thread_id}/update_title/", data={"title": title})
        return True
    except RateLimitError:
        return False
    except Exception:
        return False

async def worker(username, password, proxy, cl):
    round_number = 1
    while True:
        try:
            threads = await asyncio.to_thread(cl.direct_threads, amount=100)
        except Exception:
            await asyncio.sleep(60)
            continue
        groups = [t for t in threads if getattr(t, "is_group", False)]
        total = len(groups)
        if total == 0:
            await asyncio.sleep(60)
            continue
        ui_log(username, f"⏳ ROUND {round_number} | GCS → {total}")
        titles = load_lines(TITLE_FILE) if os.path.exists(TITLE_FILE) else []
        active_title = None
        if titles:
            rename_index = (round_number - 1) // 5
            title_index = rename_index % len(titles)
            active_title = titles[title_index]
        active_block = None
        if MESSAGE_BLOCKS:
            block_index = (round_number - 1) % len(MESSAGE_BLOCKS)
            active_block = MESSAGE_BLOCKS[block_index]
        for index, thread in enumerate(groups, start=1):
            gid = thread.id
            if active_block:
                try:
                    await asyncio.to_thread(cl.direct_send, active_block, thread_ids=[gid])
                except Exception:
                    pass
                await asyncio.sleep(MSG_DELAY)
                ui_log(username, f"📨 → GC {index}/{total}")
            if active_title:
                current_title = thread.thread_title or ""
                if current_title != active_title:
                    try:
                        success = await asyncio.to_thread(rename_thread, cl, gid, active_title)
                        if success:
                            ui_log(username, f"💠 → {active_title}")
                        else:
                            ui_log(username, "⚠ Rename failed")
                    except Exception:
                        ui_log(username, "⚠ Rename error")
                else:
                    ui_log(username, f"💠 OK → {active_title}")
        ui_log(username, f"✔ ROUND {round_number} Complete")
        round_number += 1
        await asyncio.sleep(90)

async def main():
    ACCOUNTS = load_accounts(ACC_FILE)
    global MESSAGE_BLOCKS
    MESSAGE_BLOCKS = load_message_blocks(MESSAGE_FILE) if os.path.exists(MESSAGE_FILE) else []
    clients = []
    for username, password, proxy in ACCOUNTS:
        cl = await login(username, password, proxy)
        if cl:
            USERS.append(username)
            ui_log(username, f"🍸 ID - {username}")
            clients.append((username, password, proxy, cl))
    if not USERS:
        return
    layout = build_layout()
    for u, p, pr, cl in clients:
        asyncio.create_task(worker(u, p, pr, cl))
    with Live(layout, console=console, refresh_per_second=5, screen=True) as live:
        while True:
            render_layout(layout)
            live.refresh()
            await asyncio.sleep(0.2)

if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    threading.Thread(target=self_ping_loop, daemon=True).start()
    asyncio.run(main())
