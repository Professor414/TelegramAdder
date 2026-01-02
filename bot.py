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
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ដាក់ក្នុង Render Environment Variables

if not BOT_TOKEN:
    raise ValueError("⚠️ សូមដាក់ BOT_TOKEN ក្នុង Environment Variables!")

SESSION_DIR = "bot_sessions"
SCRAPE_DIR = "scraped"

os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(SCRAPE_DIR, exist_ok=True)

# ===================== STATES =====================
GROUP_LINK, USER_LIST, SCRAPE_LINK = range(3)

# ===================== CLIENT STORAGE =====================
clients = {}

# ===================== BOT HANDLERS =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 សួស្តី បង! នេះជា TS Drama Adder Bot 🚀\n\n"
        "បញ្ជា:\n"
        "/login - ចូលគណនី Telegram\n"
        "/add - បញ្ចូលសមាជិកចូល group\n"
        "/scrape - ទាញ username ពី group/channel\n"
        "/coolfast - ប្តូរ IP (PIA VPN)\n"
        "/reset - លុប session & ចូលថ្មី\n"
        "/cancel - បោះបង់\n\n"
        "វាយ /login ដើម្បីចាប់ផ្តើម!"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in clients:
        try:
            await clients[user_id].disconnect()
        except:
            pass
        del clients[user_id]
    await update.message.reply_text("❌ បានបោះបង់!")
    return ConversationHandler.END

# ===================== LOGIN =====================
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 បញ្ចូលលេខទូរស័ព្ទ (ឧ. +85512345678):")
    context.user_data["login_step"] = "phone"

async def handle_login_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text("📩 បានផ្ញើ OTP! បញ្ចូលលេខ OTP:")
        except Exception as e:
            await update.message.reply_text(f"❌ មានបញ្ហា: {e}")

    elif step == "code":
        code = text
        client = clients[user_id]
        try:
            await client.sign_in(context.user_data["phone"], code)
            await update.message.reply_text("✅ ចូលជោគជ័យ! ឥឡូវប្រើ /add ឬ /scrape បានហើយ 🚀")
            del context.user_data["login_step"]
        except SessionPasswordNeededError:
            context.user_data["login_step"] = "2fa"
            await update.message.reply_text("🔐 គណនីមាន 2FA! បញ្ចូលពាក្យសម្ងាត់ 2FA:")
        except Exception as e:
            await update.message.reply_text(f"❌ មានបញ្ហា: {e}")

    elif step == "2fa":
        password = text
        client = clients[user_id]
        try:
            await client.sign_in(password=password)
            await update.message.reply_text("✅ 2FA ជោគជ័យ! ឥឡូវ ready ហើយ 🚀")
            del context.user_data["login_step"]
        except Exception as e:
            await update.message.reply_text(f"❌ មានបញ្ហា: {e}")

# ===================== ADD MEMBERS =====================
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in clients or not await clients[user_id].is_user_authorized():
        await update.message.reply_text("⚠️ សូមវាយ /login មុន!")
        return ConversationHandler.END
    await update.message.reply_text("🔗 បញ្ចូល Link Group ដែលចង់បញ្ចូលសមាជិក:")
    return GROUP_LINK

async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["group"] = update.message.text.strip()
    await update.message.reply_text("📋 បញ្ចូល list username (មួយបន្ទាត់មួយ)\nឬ send file .txt:")
    return USER_LIST

async def get_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    usernames = []

    if update.message.document:
        file = await update.message.document.get_file()
        path = await file.download_to_drive()
        try:
            with open(path, "r", encoding="utf-8") as f:
                usernames = [line.strip().lstrip('@') for line in f if line.strip()]
        except:
            await update.message.reply_text("❌ មិនអាចអាន file បាន")
            return USER_LIST
        os.remove(path)
    else:
        text = update.message.text
        usernames = [line.strip().lstrip('@') for line in text.splitlines() if line.strip()]

    if not usernames:
        await update.message.reply_text("⚠️ គ្មាន username! សូមបញ្ចូលម្តងទៀត")
        return USER_LIST

    await update.message.reply_text(f"🚀 ចាប់ផ្តើមបញ្ចូល {len(usernames)} នាក់...")

    client = clients[user_id]
    try:
        group = await client.get_entity(context.user_data["group"])
    except Exception as e:
        await update.message.reply_text(f"❌ Link group មិនត្រឹមត្រូវ: {e}")
        return ConversationHandler.END

    success = failed = 0
    for username in usernames:
        try:
            user = await client.get_entity(username)
            if user.bot:
                await update.message.reply_text(f"🤖 រំលង bot: @{username}")
                failed += 1
                continue
            await client(InviteToChannelRequest(group, [user]))
            success += 1
            await update.message.reply_text(f"🟢 បញ្ចូលជោគជ័យ: @{username}")
            await asyncio.sleep(random.uniform(8, 12))
        except UserAlreadyParticipantError:
            await update.message.reply_text(f"⏩ មានក្នុង group ហើយ: @{username}")
            failed += 1
        except UserPrivacyRestrictedError:
            await update.message.reply_text(f"🚫 Privacy បិទ: @{username}")
            failed += 1
        except FloodWaitError as e:
            await update.message.reply_text(f"⏳ FloodWait {e.seconds} វិនាទី → វាយ /coolfast ដើម្បីប្តូរ IP")
            break
        except Exception as e:
            await update.message.reply_text(f"❌ បញ្ហា @{username}: {e}")
            failed += 1

    await update.message.reply_text(f"🏁 បញ្ចប់! ✅ {success} | ❌ {failed}")
    return ConversationHandler.END

# ===================== SCRAPE =====================
async def scrape_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in clients or not await clients[user_id].is_user_authorized():
        await update.message.reply_text("⚠️ សូមវាយ /login មុន!")
        return ConversationHandler.END
    await update.message.reply_text("🔗 បញ្ចូល Link Group/Channel ដែលចង់ទាញ username:")
    return SCRAPE_LINK

async def do_scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text.strip()
    client = clients[user_id]

    try:
        entity = await client.get_entity(link)
        title = getattr(entity, "title", getattr(entity, "username", "មិនដឹងឈ្មោះ"))
        await update.message.reply_text(f"🔍 កំពុងទាញពី {title}...")

        users = []
        async for user in client.iter_participants(entity):
            if user.username and not user.bot:
                users.append(user.username.lstrip('@'))

        if not users:
            await update.message.reply_text("⚠️ គ្មាន user ណាមាន username")
            return ConversationHandler.END

        chunks = [users[i:i+100] for i in range(0, len(users), 100)]
        base = re.sub(r'\W+', '', title)[:15]
        for idx, chunk in enumerate(chunks):
            fname = os.path.join(SCRAPE_DIR, f"{base}_{idx+1}.txt")
            with open(fname, "w", encoding="utf-8") as f:
                f.write("\n".join(chunk))
            await update.message.reply_document(open(fname, "rb"), caption=f"ផ្នែក {idx+1} ({len(chunk)} នាក់)")

        await update.message.reply_text(f"✅ ទាញបាន {len(users)} username រួចរាល់!")
    except Exception as e:
        await update.message.reply_text(f"❌ មានបញ្ហា: {e}")

    return ConversationHandler.END

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
            await update.message.reply_text("❌ បើក PIA app និងវាយ: piactl background enable")
            return
        new = random.choice(regions)
        pia.set_region(new)
        pia.connect()
        await update.message.reply_text(f"🌍 ប្តូរ IP ទៅ {new} រួចរាល់! រង់ចាំ 30 វិនាទី")
    except Exception as e:
        await update.message.reply_text(f"❌ PIA មានបញ្ហា: {e}")

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
    await update.message.reply_text("🗑️ បានលុប session រួចរាល់! វាយ /login ម្តងទៀត")

# ===================== MAIN =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
            USER_LIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_users),
                MessageHandler(filters.Document.ALL, get_users),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    scrape_conv = ConversationHandler(
        entry_points=[CommandHandler("scrape", scrape_start)],
        states={
            SCRAPE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_scrape)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(add_conv)
    app.add_handler(scrape_conv)
    app.add_handler(CommandHandler("coolfast", cool_fast))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login_message))

    print("🤖 Bot កំពុងដំណើរការ 24/7 លើ Render...")
    app.run_polling()

if __name__ == "__main__":
    main()
