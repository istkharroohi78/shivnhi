import asyncio
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ButtonStyle
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI, LOGGER_ID, SUDOERS, OWNER_ID
from PritiMusic import app
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
    time_limit = int(time.time()) - 172800 # 48 hours
    return promo_msgs_db.find({"timestamp": {"$lt": time_limit}})

async def delete_promo_record(chat_id: int, message_id: int):
    await promo_msgs_db.delete_one({"chat_id": chat_id, "message_id": message_id})


# ==========================================
# PROMO DETAILS
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
    await broadcast_time_db.update_one({"_id": "last_run"}, {"$set": {"time": int(time.time())}}, upsert=True)
    
    users = await get_served_users()
    chats = await get_served_chats()

    u_success, u_failed = 0, 0
    g_success, g_failed = 0, 0

    # Broadcast to Users
    for user in users:
        user_id = user["user_id"] if isinstance(user, dict) else user
        try:
            msg = await app.send_photo(
                chat_id=int(user_id),
                photo=PROMO_IMAGE,
                caption=PROMO_TEXT,
                reply_markup=PROMO_BUTTON
            )
            await save_promo_msg(int(user_id), msg.id)
            u_success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            u_failed += 1
        await asyncio.sleep(0.5)

    # Broadcast to Groups
    for chat in chats:
        chat_id = chat["chat_id"] if isinstance(chat, dict) else chat
        try:
            msg = await app.send_photo(
                chat_id=int(chat_id),
                photo=PROMO_IMAGE,
                caption=PROMO_TEXT,
                reply_markup=PROMO_BUTTON
            )
            await save_promo_msg(int(chat_id), msg.id)
            g_success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            g_failed += 1
        await asyncio.sleep(0.5)

    return u_success, u_failed, g_success, g_failed


# ==========================================
# COMMAND: ON / OFF / RUN
# ==========================================
# 🟢 FIX: Filter hata diya gaya hai taaki debug message aa sake
@app.on_message(filters.command(["selfpromo", "promo"], prefixes=["/", "!", "."]))
async def promo_toggle_cmd(client, message: Message):
    user_id = message.from_user.id
    
    # Check kar rahe hain ki command dene wala Owner ya Sudoer hai ya nahi
    sudo_list = [int(x) for x in SUDOERS] if isinstance(SUDOERS, list) else []
    owner_id_int = int(OWNER_ID) if OWNER_ID else 0
    
    if user_id not in sudo_list and user_id != owner_id_int:
        return await message.reply_text(
            f"❌ **Access Denied!**\n"
            f"Mujhe laga aap owner ho, par aapki User ID `{user_id}` config.py ke `SUDOERS` ya `OWNER_ID` mein nahi hai."
        )

    if len(message.command) != 2:
        return await message.reply_text(
            "**Usage Options:**\n"
            "`/selfpromo on` - Start auto 24-hour broadcast\n"
            "`/selfpromo off` - Stop auto broadcast\n"
            "`/selfpromo run` - Instantly broadcast right now"
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
        try:
            u_success, u_failed, g_success, g_failed = await run_broadcast()
            stats_text = f"📢 **Manual Promo Completed**\n\n👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}"
            await status_msg.edit_text(stats_text)
            if LOGGER_ID:
                await app.send_message(LOGGER_ID, stats_text)
        except Exception as e:
            await status_msg.edit_text(f"❌ Error in broadcast: {e}")
            
    else:
        await message.reply_text("**Invalid argument.** Use `/selfpromo on`, `off`, or `run`.")


# ==========================================
# BACKGROUND TASK: 24H LOOP & 48H DELETE
# ==========================================
async def auto_promo_task():
    while True:
        try:
            # 1. DELETE OLD MESSAGES (48 HOURS OLD)
            old_messages = await get_old_promo_msgs()
            async for doc in old_messages:
                try:
                    await app.delete_messages(chat_id=doc["chat_id"], message_ids=doc["message_id"])
                except Exception:
                    pass
                await delete_promo_record(doc["chat_id"], doc["message_id"])
                await asyncio.sleep(1)

            # 2. CHECK IF PROMO IS ON
            if await is_promo_on():
                # 3. CHECK IF 24 HOURS HAVE PASSED
                last_run_data = await broadcast_time_db.find_one({"_id": "last_run"})
                last_run = last_run_data["time"] if last_run_data else 0
                
                if (int(time.time()) - last_run) >= 86400: # 86400s = 24 hours
                    u_success, u_failed, g_success, g_failed = await run_broadcast()
                    stats_text = f"📢 **Auto Promo Completed**\n\n👥 **Users:** ✅ {u_success} | ❌ {u_failed}\n🏘 **Groups:** ✅ {g_success} | ❌ {g_failed}"
                    if LOGGER_ID:
                        await app.send_message(LOGGER_ID, stats_text)

        except Exception as e:
            pass # Background task errors ignored for smooth running
            
        # 1 ghante baad wapas check karega
        await asyncio.sleep(3600)

# Task Start Hook
try:
    asyncio.get_event_loop().create_task(auto_promo_task())
except:
    pass
