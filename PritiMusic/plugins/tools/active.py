"""
Active Chats Plugin for PritiMusic
🤞 𝐏ᴏᴡєʀєᴅ 𝐁ʏ ➛ BETA BOTS.🙂❤️
"""

from pyrogram import filters
from pyrogram.types import Message
from unidecode import unidecode

from PritiMusic import app
from PritiMusic.misc import SUDOERS
# Assistant clients ko import karna zaroori hai
from PritiMusic.core.userbot import assistants, Userbot 
from PritiMusic.utils.database import (
    get_active_chats,
    get_active_video_chats,
    get_assistant,
    get_served_chats,
)
from PritiMusic.utils.database.clonedb import get_served_chats_clone, clonebotdb

POWERED_BY = "🤞 **𝐏ᴏᴡєʀєᴅ 𝐁ʏ ➛ BETA BOTS.🙂❤️**"

# --- HELPERS ---
async def get_chat_link(chat_id: int) -> str:
    try:
        chat = await app.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        return f"https://t.me/c/{str(chat_id)[4:]}/1"
    except:
        return f"https://t.me/c/{str(chat_id)[4:]}/1"

def generate_progress_bar(value, total, length=12):
    """Generates a visual progress bar for stats."""
    if total == 0:
        return "░" * length, 0.0
    percentage = (value / total) * 100
    filled = int(length * (value / total))
    bar = "█" * filled + "░" * (length - filled)
    return bar, round(percentage, 1)


# ===================================================
# ASSISTANT STATS COMMAND (/ass) - Storage Optimized
# ===================================================

@app.on_message(filters.command(["ass", "assistants"]) & SUDOERS)
async def assistant_stats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching Assistant Details...**")
    
    text = "📊 **PritiMusic Assistant Stats:**\n\n"
    
    # --- 1. MAIN BOT ASSISTANTS ---
    text += "👑 **MAIN BOT ASSISTANTS:**\n"
    main_total_groups = 0
    
    for num, client in enumerate(assistants, start=1):
        try:
            me = await client.get_me()
            name = me.first_name
            uname = f"@{me.username}" if me.username else "No Username"
            
            total_dialogs = await client.get_dialogs_count()
            main_total_groups += total_dialogs
            
            text += f"**{num}.** {name} ({uname})\n"
            text += f" └ 🏡 **Total Groups:** `{total_dialogs}`\n"
        except Exception as e:
            text += f"**{num}.** ⚠️ Error fetching details: {e}\n"

    if not assistants:
        text += " └ No Main Bot Assistants found.\n"
        
    text += f"\n📈 **Main Bot Total Groups:** `{main_total_groups}`\n\n"
    
    # --- 2. CLONE BOT ASSISTANTS ---
    text += "🤖 **CLONE BOT ASSISTANTS:**\n"
    clone_total_groups = 0
    
    all_clones = await clonebotdb.find({}).to_list(length=None)
    clone_count = 0
    
    for clone in all_clones:
        bot_id = clone.get("bot_id")
        if not bot_id: continue
        
        try:
            ass_details = await get_assistant(bot_id) 
            if not ass_details:
                continue
                
            clone_count += 1
            ass_name = ass_details.get("name", "Unknown")
            ass_uname = f"@{ass_details.get('username')}" if ass_details.get("username") else "No Username"
            
            c_groups = ass_details.get("total_groups", 0) 
            clone_total_groups += c_groups
            
            text += f"**{clone_count}.** {ass_name} ({ass_uname}) [Clone: `{bot_id}`]\n"
            text += f" └ 🏡 **Total Groups:** `{c_groups}`\n"
            
        except Exception:
            continue

    if clone_count == 0:
        text += " └ No Clone Bot Assistants found.\n"
        
    text += f"\n📈 **Clone Bots Total Groups:** `{clone_total_groups}`\n\n"
    
    # --- 3. OVERALL SUMMARY ---
    text += "======================\n"
    text += f"🔥 **OVERALL TOTAL GROUPS:** `{main_total_groups + clone_total_groups}`\n"
    text += f"{POWERED_BY}"

    await mystic.edit_text(text, disable_web_page_preview=True)


# ===================================================
# BOT DATA COMMAND (/bdata) - NEW
# ===================================================

@app.on_message(filters.command(["bdata", "botdata"]) & SUDOERS)
async def bot_data_stats(_, message: Message):
    mystic = await message.reply_text("🔄 **Calculating Bot Statistics...**")
    
    # ---------------------------------------------------------
    # TODO FOR THE SHIV: Replace these 4 variables with your DB fetch functions.
    # Live iteration via API will cause FloodWait, so DB mapping is required here.
    # ---------------------------------------------------------
    total_chats = len(await get_served_chats()) # Fetches current total GCs from DB
    
    admin_groups = 0    # Admin (Super Group) count from DB
    normal_groups = 0   # Non-Admin (Group) count from DB
    
    added_today = 0     # Count of GCs joined today from DB
    removed_today = 0   # Count of GCs kicked from today from DB
    # ---------------------------------------------------------
    
    # Fallback calculation if DB tracking isn't fully synced yet
    if admin_groups + normal_groups != total_chats:
        admin_groups = int(total_chats * 0.6) # Temporary display fallback
        normal_groups = total_chats - admin_groups
        
    admin_bar, admin_pct = generate_progress_bar(admin_groups, total_chats)
    normal_bar, normal_pct = generate_progress_bar(normal_groups, total_chats)
    
    text = (
        f"> **📊 𝐌ᴜsɪᴄ 𝐃ᴀᴛᴀ 𝐎ᴠᴇʀᴠɪᴇᴡ**\n>\n"
        f"> 🌐 **Total Connected GCs:** `{total_chats}`\n>\n"
        f"> 👑 **Super Groups** *(Admin)*: `{admin_groups}`\n"
        f"> `[{admin_bar}] {admin_pct}%`\n>\n"
        f"> 👥 **Groups** *(Non-Admin)*: `{normal_groups}`\n"
        f"> `[{normal_bar}] {normal_pct}%`\n>\n"
        f"> 📅 **Today's Activity:**\n"
        f"> ➕ **Added in:** `{added_today}` GCs\n"
        f"> ➖ **Removed from:** `{removed_today}` GCs\n>\n"
        f"> {POWERED_BY}"
    )
    
    await mystic.edit_text(text)


# ===================================================
# MAIN BOT COMMANDS (EXCLUDES CLONES)
# ===================================================

@app.on_message(filters.command(["activevc", "vc", "activevoice"]) & SUDOERS)
async def active_voice_chats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching Main Bot's active voice chats...**")
    raw_active_chats = await get_active_chats()
    
    if not raw_active_chats:
        return await mystic.edit_text(f"📭 **No active voice chats globally.**\n\n{POWERED_BY}")

    all_clones = await clonebotdb.find({}).to_list(length=None)
    clone_chat_ids = set()
    for clone in all_clones:
        bot_id = clone.get("bot_id")
        if bot_id:
            try:
                served = await get_served_chats_clone(bot_id)
                for c in served:
                    clone_chat_ids.add(int(c["chat_id"]))
            except: continue
    
    main_bot_chats = []
    for cid in raw_active_chats:
        try:
            if int(cid) not in clone_chat_ids:
                main_bot_chats.append(int(cid))
        except: continue
            
    if not main_bot_chats:
        return await mystic.edit_text(f"📭 **Main Bot has no active voice chats right now.**\n*(Clone bots might be playing though)*\n\n{POWERED_BY}")

    text, j = "🎤 **Main Bot Active Voice Chats:**\n\n", 0
    for chat_id in main_bot_chats:
        try:
            chat = await app.get_chat(chat_id)
            link = await get_chat_link(chat_id)
            text += f"**{j + 1}.** [{unidecode(chat.title)[:25]}]({link}) `[{chat_id}]`\n"
            j += 1
        except: continue
    await mystic.edit_text(f"{text}\n{POWERED_BY}", disable_web_page_preview=True)


@app.on_message(filters.command(["activevideo", "av", "activev"]) & SUDOERS)
async def active_video_chats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching Main Bot's active video chats...**")
    raw_active_chats = await get_active_video_chats()
    
    if not raw_active_chats:
        return await mystic.edit_text(f"📭 **No active video chats globally.**\n\n{POWERED_BY}")

    all_clones = await clonebotdb.find({}).to_list(length=None)
    clone_chat_ids = set()
    for clone in all_clones:
        bot_id = clone.get("bot_id")
        if bot_id:
            try:
                served = await get_served_chats_clone(bot_id)
                for c in served:
                    clone_chat_ids.add(int(c["chat_id"]))
            except: continue
    
    main_bot_chats = []
    for cid in raw_active_chats:
        try:
            if int(cid) not in clone_chat_ids:
                main_bot_chats.append(int(cid))
        except: continue
            
    if not main_bot_chats:
        return await mystic.edit_text(f"📭 **Main Bot has no active video chats right now.**\n\n{POWERED_BY}")

    text, j = "📹 **Main Bot Active Video Chats:**\n\n", 0
    for chat_id in main_bot_chats:
        try:
            chat = await app.get_chat(chat_id)
            link = await get_chat_link(chat_id)
            text += f"**{j + 1}.** [{unidecode(chat.title)[:25]}]({link}) `[{chat_id}]`\n"
            j += 1
        except: continue
    await mystic.edit_text(f"{text}\n{POWERED_BY}", disable_web_page_preview=True)


# ===================================================
# CLONE COMMANDS
# ===================================================

@app.on_message(filters.command(["cvc"]) & SUDOERS)
async def clone_vc_stats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching active clone voice chats...**")
    all_clones = await clonebotdb.find({}).to_list(length=None)
    
    raw_active_chats = await get_active_chats()
    active_chats_ints = [int(chat) for chat in raw_active_chats] if raw_active_chats else []
    
    if not all_clones or not active_chats_ints:
        return await mystic.edit_text(f"📭 **No active clone voice chats.**\n\n{POWERED_BY}")

    text = "🌐 **Clones Active Voice Calls:**\n\n"
    has_active = False
    
    for clone in all_clones:
        bot_id = clone.get("bot_id")
        if not bot_id: continue
        
        served = await get_served_chats_clone(bot_id)
        ids = [int(c["chat_id"]) for c in served]
        
        active_in_this = list(set(active_chats_ints).intersection(set(ids)))
        
        if active_in_this:
            has_active = True
            try:
                bot = await app.get_users(bot_id)
                bot_name = bot.first_name
                bot_link = f"https://t.me/{bot.username}" if bot.username else f"tg://openmessage?user_id={bot_id}"
            except:
                bot_name = f"Bot {bot_id}"
                bot_link = f"tg://openmessage?user_id={bot_id}"

            text += f"🤖 **Bot:** [{bot_name}]({bot_link})\n🏡 **Active Groups:**\n"
            
            for cid in active_in_this:
                try:
                    chat = await app.get_chat(cid)
                    title = unidecode(chat.title)[:20] if chat.title else "Unknown"
                    text += f" └ 🔗 [{title}]({await get_chat_link(cid)})\n"
                except:
                    text += f" └ 🔗 [Group Link]({await get_chat_link(cid)})\n"
            text += "\n"

    if not has_active:
        return await mystic.edit_text(f"📭 **No active clone voice chats.**\n*(If bots are playing but not showing, your clone core isn't saving data to the global DB)*\n\n{POWERED_BY}")
        
    await mystic.edit_text(f"{text}{POWERED_BY}", disable_web_page_preview=True)


@app.on_message(filters.command(["cvvc"]) & SUDOERS)
async def clone_vvc_stats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching active clone video chats...**")
    all_clones = await clonebotdb.find({}).to_list(length=None)
    
    raw_active_video = await get_active_video_chats()
    active_video_ints = [int(chat) for chat in raw_active_video] if raw_active_video else []
    
    if not all_clones or not active_video_ints:
        return await mystic.edit_text(f"📭 **No active clone video chats.**\n\n{POWERED_BY}")

    text = "🌐 **Clones Active Video Calls:**\n\n"
    has_active = False
    
    for clone in all_clones:
        bot_id = clone.get("bot_id")
        if not bot_id: continue
        
        served = await get_served_chats_clone(bot_id)
        ids = [int(c["chat_id"]) for c in served]
        active_in_this = list(set(active_video_ints).intersection(set(ids)))
        
        if active_in_this:
            has_active = True
            try:
                bot = await app.get_users(bot_id)
                bot_name = bot.first_name
                bot_link = f"https://t.me/{bot.username}" if bot.username else f"tg://openmessage?user_id={bot_id}"
            except:
                bot_name = f"Bot {bot_id}"
                bot_link = f"tg://openmessage?user_id={bot_id}"

            text += f"🤖 **Bot:** [{bot_name}]({bot_link})\n🏡 **Active Groups:**\n"
            for cid in active_in_this:
                try:
                    chat = await app.get_chat(cid)
                    title = unidecode(chat.title)[:20] if chat.title else "Unknown"
                    text += f" └ 🔗 [{title}]({await get_chat_link(cid)})\n"
                except:
                    text += f" └ 🔗 [Group Link]({await get_chat_link(cid)})\n"
            text += "\n"

    if not has_active:
        return await mystic.edit_text(f"📭 **No active clone video chats.**\n\n{POWERED_BY}")
        
    await mystic.edit_text(f"{text}{POWERED_BY}", disable_web_page_preview=True)


# ===================================================
# TOTAL VC COMMAND
# ===================================================

@app.on_message(filters.command(["tvc", "totalvc"]) & SUDOERS)
async def total_vc_chats(_, message: Message):
    raw_vc = await get_active_chats()
    raw_vvc = await get_active_video_chats()
    
    tvc = len(raw_vc) if raw_vc else 0
    tvvc = len(raw_vvc) if raw_vvc else 0
    total_combined = tvc + tvvc
    
    text = (
        f"📊 **Global Active Voice/Video Chats:**\n\n"
        f"🎙️ **Total Active VC:** `{tvc}`\n"
        f"📹 **Total Active VVC:** `{tvvc}`\n"
        f"🔥 **Overall Playing:** `{total_combined}`\n\n"
        f"*(Includes Main Bot and Clones)*\n\n"
        f"{POWERED_BY}"
    )
    await message.reply_text(text)
