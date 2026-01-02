import asyncio
import os
import random
import re
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, UserAlreadyParticipantError,
    SessionPasswordNeededError, PeerFloodError
)
from telethon.tl.functions.channels import InviteToChannelRequest

try:
    from piapy import PiaVpn
    PIA_AVAILABLE = True
except ImportError:
    PIA_AVAILABLE = False

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
)

# ===================== CONFIG =====================
API_ID = 26259970
API_HASH = "c85456a99e831d0823cf8c353419d554"
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ដាក់ក្នុង Render Environment Variables!!

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN មិនបានដាក់!")

SESSION_DIR = "bot_sessions"
SCRAPE_DIR = "scraped"

os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(SCRAPE_DIR, exist_ok=True)

# ===================== STATES =====================
GROUP_LINK, USER_LIST, SCRAPE_LINK = range(3)

clients = {}

# ===================== BOT HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 សួស្តី បង! Bot កំពុង run 24 ម៉ោង 🚀\n\n"
        "/login - ចូលគណនី\n"
        "/add - បញ្ចូលសមាជិក\n"
        "/scrape - ទាញ username\n"
        "/coolfast - ប្តូរ IP\n"
        "/reset - លុប session\n"
        "/cancel - បោះបង់"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in clients:
        try:
            await clients[user_id].disconnect()
        except:
            pass
        del clients[user_id]
    await update.message.reply_text("❌ បោះបង់!")
    return ConversationHandler.END

# ===================== LOGIN =====================
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 បញ្ចូលលេខទូរស័ព្ទ (+855...):")
    context.user_data["login_step"] = "phone"

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if "login_step" not in context.user_data:
        return

    step = context.user_data["login_step"]

    if step == "phone":
        phone = text
        session_path = os.path.join(SESSION_DIR, str(user_id))
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        try:
            await client.send_code_request(phone)
            clients[user_id] = client
            context.user_data["phone"] = phone
            context.user_data["login_step"] = "code"
            await update.message.reply_text("📩 បានផ្ញើ OTP! បញ្ចូល OTP:")
        except Exception as e:
            await update.message.reply_text(f"❌ បញ្ហា: {e}")

    elif step == "code":
        code = text
        client = clients[user_id]
        try:
            await client.sign_in(context.user_data["phone"], code)
            await update.message.reply_text("✅ ចូលជោគជ័យ! ប្រើ /add ឬ /scrape")
            del context.user_data["login_step"]
        except SessionPasswordNeededError:
            context.user_data["login_step"] = "2fa"
            await update.message.reply_text("🔐 បញ្ចូល 2FA Password:")
        except Exception as e:
            await update.message.reply_text(f"❌ បញ្ហា: {e}")

    elif step == "2fa":
        password = text
        client = clients[user_id]
        try:
            await client.sign_in(password=password)
            await update.message.reply_text("✅ 2FA ជោគជ័យ! Ready 🚀")
            del context.user_data["login_step"]
        except Exception as e:
            await update.message.reply_text(f"❌ បញ្ហា: {e}")

# ===================== ADD & SCRAPE (ដដែលដូចមុន – សង្ខេប) =====================
# (ដាក់កូដ add_start, get_group, get_users, scrape_start, do_scrape ដូចកូដមុន)

# ===================== OTHER =====================
async def cool_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PIA_AVAILABLE:
        await update.message.reply_text("❌ មិនបាន install piapy")
        return
    try:
        pia = PiaVpn()
        pia.disconnect()
        regions = pia.regions()
        if not regions:
            await update.message.reply_text("❌ បើក PIA app + piactl background enable")
            return
        new = random.choice(regions)
        pia.set_region(new)
        pia.connect()
        await update.message.reply_text(f"🌍 ប្តូរ IP ទៅ {new} រួចរាល់!")
    except Exception as e:
        await update.message.reply_text(f"❌ PIA បញ្ហា: {e}")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in clients:
        try:
            await clients[user_id].disconnect()
        except:
            pass
        del clients[user_id]
    session_file = os.path.join(SESSION_DIR, str(user_id) + ".session")
    if os.path.exists(session_file):
        os.remove(session_file)
    await update.message.reply_text("🗑️ លុប session រួច! វាយ /login ថ្មី")

# ===================== MAIN =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers (ដូចកូដមុន)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("coolfast", cool_fast))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login))

    print("🤖 Bot run 24/7 on Render!")
    app.run_polling(drop_pending_updates=True)  # សំខាន់សម្រាប់ run 24h

if __name__ == "__main__":
    main()
