import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ButtonStyle
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI, LOGGER_ID, OWNER_ID
from PritiMusic import app
# Import your existing user/chat fetch functions
from PritiMusic.utils.database import get_served_users, get_served_chats

# ==========================================
# DATABASE SETUP
# ==========================================
dbclient = AsyncIOMotorClient(MONGO_DB_URI)
db = dbclient.MahiMusic
promo_msgs_db = db.promo_messages
promo_toggle_db = db.promo_settings
broadcast_time_db = db.promo_time

async def is_promo_on() -> bool:
    chat = await promo_toggle_db.find_one({"_id": "promo_toggle"})
    if not chat:
        return False
    return chat.get("status", False)

async def set_promo_status(status: bool):
    await promo_toggle_db.update_one({"_id": "promo_toggle"}, {"$set": {"status": status}}, upsert=True)

async def save_promo_msg(chat_id: int, message_id: int):
    await promo_msgs_db.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "timestamp": int(time.time())
    })

async def get_old_promo_msgs():
    # 48 hours = 172800 seconds
    time_limit = int(time.time()) - 172800 
    return promo_msgs_db.find({"timestamp": {"$lt": time_limit}})

async def delete_promo_record(chat_id: int, message_id: int):
    await promo_msgs_db.delete_one({"chat_id": chat_id, "message_id": message_id})


# ==========================================
# PROMO DETAILS (TEXT & IMAGE)
# ==========================================
PROMO_IMAGE = "https://files.catbox.moe/u4db8r.jpg"
PROMO_TEXT = """
⊚ ᴛʜɪꜱ ɪꜱ ✶ 🎀 ᴍᴀʜɪ ᴍᴜꜱɪᴄ ᴄʟᴏɴᴇ🎀 ✶

➻ ᴧ ᴘʀєᴍɪᴜᴍ ᴅєꜱɪɢηєᴅ ϻᴜꜱɪᴄ ᴘʟᴧʏєʀ ʙσᴛ ꜰσʀ ᴛєʟєɢʀᴧϻ ɢʀσᴜᴘ & ᴄʜᴧηηєʟ. 
🎧 24x7 ᴍᴜꜱɪᴄ • ꜱᴍᴏᴏᴛʜ ᴀɴᴅ ꜰᴀꜱᴛ ᴘʟᴀʏʙᴀᴄᴋ

⚡️ ᴇɴᴊᴏʏ ᴜɴʟɪᴍɪᴛᴇᴅ ꜱᴏɴɢꜱ, qᴜɪᴄᴋ ʀᴇꜱᴘᴏɴꜱᴇ, ᴀɴᴅ ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ.

ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ, ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ, ᴀɴᴅ ꜱᴇɴᴅ /play song name ᴛᴏ ꜱᴛᴀʀᴛ ᴛʜᴇ ᴍᴜꜱɪᴄ.
"""
PROMO_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🎵Aᴅᴅ ᴍᴇ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ🎧", url="https://t.me/clone_MUSICrobot", style=ButtonStyle.SUCCESS)]]
)


# ==========================================
# CORE BROADCAST FUNCTION
# ==========================================
async def run_broadcast():
    # Timer reset taaki manual run ke baad auto-loop turant na chal jaye
    await broadcast_time_db.update_one({"_id": "last_run"}, {"$set": {"time": int(time.time())}}, upsert=True)
    
    users = await get_served_users()
    chats = await get_served_chats()

    u_success, u_failed = 0, 0
    g_success, g_failed = 0, 0

    # Broadcast to Users
    for user in users:
        try:
            msg = await app.send_photo(
                chat_id=user["user_id"],
                photo=PROMO_IMAGE,
                caption=PROMO_TEXT,
                reply_markup=PROMO_BUTTON
            )
            await save_promo_msg(user["user_id"], msg.id)
            u_success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except (UserIsBlocked, InputUserDeactivated):
            u_failed += 1
        except Exception:
            u_failed += 1
        await asyncio.sleep(0.5)

    # Broadcast to Groups
    for chat in chats:
        try:
            msg = await app.send_photo(
                chat_id=chat["chat_id"],
                photo=PROMO_IMAGE,
                caption=PROMO_TEXT,
                reply_markup=PROMO_BUTTON
            )
            await save_promo_msg(chat["chat_id"], msg.id)
            g_success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            g_failed += 1
        await asyncio.sleep(0.5)

    return u_success, u_failed, g_success, g_failed


# ==========================================
# COMMAND: ON / OFF / RUN (OWNER ONLY)
# ==========================================
@app.on_message(filters.command(["selfpromo"]) & filters.user(OWNER_ID))
async def promo_toggle_cmd(client, message: Message):
    if len(message.command) != 2:
        return await message.reply_text(
            "**Usage Options:**\n"
            "`/selfpromo on` - Start auto 24-hour broadcast\n"
            "`/selfpromo off` - Stop auto broadcast\n"
            "`/selfpromo run` - Instantly broadcast right now (Bypasses ON/OFF)"
        )
    
    state = message.command[1].lower()
    
    if state == "on":
        await set_promo_status(True)
        await message.reply_text("✅ **Auto Self Promo Started!**\nBot will broadcast every 24 hours.")
        
    elif state == "off":
        await set_promo_status(False)
        await message.reply_text("❌ **Auto Self Promo Stopped!**")
        
    elif state == "run":
        status_msg = await message.reply_text("🔄 **Manual Broadcast Started...** Please wait.")
        u_success, u_failed, g_success, g_failed = await run_broadcast()
        
        stats_text = f"""
📢 **Manual Self Promo Completed**

👥 **Users Stats:**
✅ Success: {u_success}
❌ Blocked/Failed: {u_failed}

🏘 **Groups Stats:**
✅ Success: {g_success}
❌ Failed: {g_failed}

*Note: These messages will also auto-delete after 48 hours.*
"""
        await status_msg.edit_text(stats_text)
        if LOGGER_ID:
            await app.send_message(LOGGER_ID, stats_text)
            
    else:
        await message.reply_text("**Invalid argument.** Use `on`, `off`, or `run`.")


# ==========================================
# BACKGROUND TASK: 24H LOOP & 48H DELETE
# ==========================================
async def auto_promo_task():
    while not await asyncio.sleep(3600): # Har 1 ghante mein check karega
        try:
            # 1. DELETE OLD MESSAGES (48 HOURS OLD)
            old_messages = await get_old_promo_msgs()
            async for doc in old_messages:
                try:
                    await app.delete_messages(chat_id=doc["chat_id"], message_ids=doc["message_id"])
                except Exception:
                    pass
                await delete_promo_record(doc["chat_id"], doc["message_id"])
                await asyncio.sleep(1) # API Flood se bachne ke liye

            # 2. CHECK IF PROMO IS ON
            if not await is_promo_on():
                continue

            # 3. CHECK IF 24 HOURS HAVE PASSED SINCE LAST BROADCAST
            last_run_data = await broadcast_time_db.find_one({"_id": "last_run"})
            last_run = last_run_data["time"] if last_run_data else 0
            if (int(time.time()) - last_run) < 86400: # 86400 seconds = 24 hours
                continue

            # 4. RUN BROADCAST
            u_success, u_failed, g_success, g_failed = await run_broadcast()

            # --- SEND STATS TO LOGGER ---
            stats_text = f"""
📢 **Auto Self Promo Completed**

👥 **Users Stats:**
✅ Success: {u_success}
❌ Blocked/Failed: {u_failed}

🏘 **Groups Stats:**
✅ Success: {g_success}
❌ Failed: {g_failed}
"""
            if LOGGER_ID:
                await app.send_message(LOGGER_ID, stats_text)

        except Exception as e:
            print(f"Self Promo Error: {e}")

# TASK KO BOT START HOTE HI RUN KARNE KE LIYE
asyncio.create_task(auto_promo_task())
