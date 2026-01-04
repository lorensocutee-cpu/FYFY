# =========================================================
# TELEGRAM → INSTAGRAM ULTRA LOOP BOT (WINDOWS + LINUX)
# =========================================================

import sys
import asyncio
import time
import json
import os
import sqlite3
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from instabot import Bot

# ================= WINDOWS ASYNC FIX =================
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= CONFIG =================
TG_BOT_TOKEN = "8524877041:AAEiBD7SBIHx17nC5v825dPtHFtoLrsNKj8"
OWNER_TG_ID = 8312119030
SEND_DELAY = 0.35   # 🔥 ULTRA SPEED (LOCKED)
DB_FILE = "bot_data.db"

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB_FILE)

def init_db():
    c = db()
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS ig_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    c.commit()
    c.close()

init_db()

def set_state(k, v):
    c = db()
    c.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (k, json.dumps(v)))
    c.commit()
    c.close()

def get_state(k, d=None):
    c = db()
    cur = c.cursor()
    cur.execute("SELECT value FROM state WHERE key=?", (k,))
    r = cur.fetchone()
    c.close()
    return json.loads(r[0]) if r else d

# ================= GLOBAL STATE =================
STATE = {
    "ig": get_state("ig", []),
    "active": get_state("active", None),
    "groups": [],
    "targets": [],
    "message": None,
    "count": 0,
    "running": False,
    "step": None
}

# ================= HELP =================
HELP_TEXT = """
🤖 *Instagram Ultra Loop Bot*

/start   – Bot online
/help    – Show commands

/slogin  – Add IG account (sessionid)
/igs     – List IG accounts
/setig n – Switch IG account

/attack  – Start message setup
/stop    – Stop loop
/status  – Bot status
"""

# ================= IG UTILS =================
def ig_login(sessionid):
    bot = Bot()
    bot.api.session = requests.Session()
    bot.api.session.cookies.set("sessionid", sessionid, domain=".instagram.com")
    return bot

def fetch_groups(bot):
    r = bot.api.session.get("https://i.instagram.com/api/v1/direct_v2/inbox/")
    threads = r.json()["inbox"]["threads"]
    out = []
    for t in threads:
        title = t.get("thread_title") or "DM"
        out.append((t["thread_id"], title))
    return out

def send_with_retry(bot, msg, tid, retries=3):
    for _ in range(retries):
        try:
            bot.send_message(msg, thread_id=tid)
            return True
        except Exception:
            time.sleep(0.4)
    return False

# ================= LOOP ENGINE =================
async def sender_loop(bot):
    sent = 0
    while STATE["running"]:
        for tid in STATE["targets"]:
            send_with_retry(bot, STATE["message"], tid)
            sent += 1

            if STATE["count"] > 0 and sent >= STATE["count"]:
                STATE["running"] = False
                return

            await asyncio.sleep(SEND_DELAY)

# ================= COMMANDS =================
async def start(update: Update, ctx):
    await update.message.reply_text("✅ Bot Online\n/help")

async def help_cmd(update: Update, ctx):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

async def slogin(update: Update, ctx):
    STATE["step"] = "slogin"
    await update.message.reply_text("Send Instagram sessionid")

async def igs(update: Update, ctx):
    if not STATE["ig"]:
        await update.message.reply_text("No IG accounts added")
        return
    msg = ["📱 IG ACCOUNTS:"]
    for i in range(len(STATE["ig"])):
        active = " ✅" if STATE["active"] == i else ""
        msg.append(f"{i+1}. Account {i+1}{active}")
    await update.message.reply_text("\n".join(msg))

async def setig(update: Update, ctx):
    n = int(ctx.args[0]) - 1
    STATE["active"] = n
    set_state("active", n)
    await update.message.reply_text(f"✅ Active IG set to {n+1}")

async def attack(update: Update, ctx):
    if STATE["active"] is None:
        await update.message.reply_text("❌ Add IG first using /slogin")
        return

    bot = ig_login(STATE["ig"][STATE["active"]])
    STATE["groups"] = fetch_groups(bot)

    msg = ["📂 *AVAILABLE CHATS*\n"]
    for i, g in enumerate(STATE["groups"], 1):
        msg.append(f"{i}. {g[1]}")
    msg.append("\nReply with numbers (1,3,5 or 1-4)")
    STATE["step"] = "select"
    await update.message.reply_text("\n".join(msg), parse_mode="Markdown")

async def stop(update: Update, ctx):
    STATE["running"] = False
    await update.message.reply_text("🛑 Stopped")

async def status(update: Update, ctx):
    await update.message.reply_text(
        f"Running: {STATE['running']}\n"
        f"Targets: {len(STATE['targets'])}\n"
        f"Count: {STATE['count']}\n"
        f"Speed: {SEND_DELAY}s"
    )

# ================= TEXT ROUTER =================
async def text_router(update: Update, ctx):
    step = STATE["step"]

    if step == "slogin":
        STATE["ig"].append(update.message.text.strip())
        set_state("ig", STATE["ig"])
        STATE["step"] = None
        await update.message.reply_text("✅ IG account added")
        return

    if step == "select":
        t = update.message.text.replace(" ", "")
        if "-" in t:
            a, b = map(int, t.split("-"))
            sel = list(range(a, b+1))
        else:
            sel = list(map(int, t.split(",")))
        STATE["targets"] = [STATE["groups"][i-1][0] for i in sel]
        STATE["step"] = "payload"
        await update.message.reply_text("Send message or upload .txt file")
        return

    if step == "payload":
        if update.message.document:
            f = await update.message.document.get_file()
            p = "payload.txt"
            await f.download_to_drive(p)
            STATE["message"] = open(p, encoding="utf-8").read()
            os.remove(p)
        else:
            STATE["message"] = update.message.text
        STATE["step"] = "count"
        await update.message.reply_text("Send count (0 = infinite)")
        return

    if step == "count":
        STATE["count"] = int(update.message.text)
        STATE["step"] = None
        STATE["running"] = True
        bot = ig_login(STATE["ig"][STATE["active"]])
        asyncio.create_task(sender_loop(bot))
        await update.message.reply_text("🚀 Ultra attack started")
        return

# ================= MAIN =================
def main():
    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("slogin", slogin))
    app.add_handler(CommandHandler("igs", igs))
    app.add_handler(CommandHandler("setig", setig))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.ALL, text_router))
    app.run_polling()

if __name__ == "__main__":
    main()
