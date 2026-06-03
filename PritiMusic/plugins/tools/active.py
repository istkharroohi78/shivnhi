"""
Active Chats Plugin for PritiMusic
🤞 𝐏ᴏᴡєʀєᴅ 𝐁ʏ ➛ BETA BOTS.🙂❤️
"""

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from unidecode import unidecode

from PritiMusic import app
from PritiMusic.misc import SUDOERS
from PritiMusic.utils.database import (
    get_active_chats,
    get_active_video_chats,
)
from PritiMusic.utils.database.clonedb import get_served_chats_clone, clonebotdb

POWERED_BY = "🤞 **𝐏ᴏᴡєʀєᴅ 𝐁ʏ ➛ BETA BOTS.🙂❤️**"

# --- HELPER ---
async def get_chat_link(chat_id: int) -> str:
    try:
        chat = await app.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        return f"https://t.me/c/{str(chat_id)[4:]}/1"
    except:
        return f"https://t.me/c/{str(chat_id)[4:]}/1"

# --- MAIN BOT COMMANDS ---

@app.on_message(filters.command(["activevc", "vc", "activevoice"]) & SUDOERS)
async def active_voice_chats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching active voice chats...**")
    served_chats = await get_active_chats()
    if not served_chats:
        return await mystic.edit_text(f"📭 **No active voice chats.**\n\n{POWERED_BY}")
    
    text, j = "🎤 **Active Voice Chats:**\n\n", 0
    for chat_id in served_chats:
        try:
            chat = await app.get_chat(int(chat_id)) # Int casting
            link = await get_chat_link(int(chat_id))
            text += f"**{j + 1}.** [{unidecode(chat.title)[:25]}]({link}) `[{chat_id}]`\n"
            j += 1
        except: continue
    await mystic.edit_text(f"{text}\n{POWERED_BY}", disable_web_page_preview=True)

@app.on_message(filters.command(["activevideo", "av", "activev"]) & SUDOERS)
async def active_video_chats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching active video chats...**")
    served_chats = await get_active_video_chats()
    if not served_chats:
        return await mystic.edit_text(f"📭 **No active video chats.**\n\n{POWERED_BY}")
    
    text, j = "📹 **Active Video Chats:**\n\n", 0
    for chat_id in served_chats:
        try:
            chat = await app.get_chat(int(chat_id))
            link = await get_chat_link(int(chat_id))
            text += f"**{j + 1}.** [{unidecode(chat.title)[:25]}]({link}) `[{chat_id}]`\n"
            j += 1
        except: continue
    await mystic.edit_text(f"{text}\n{POWERED_BY}", disable_web_page_preview=True)

# --- CLONE COMMANDS ---

@app.on_message(filters.command(["cvc"]) & SUDOERS)
async def clone_vc_stats(_, message: Message):
    mystic = await message.reply_text("🔄 **Fetching active clone voice chats...**")
    all_clones = await clonebotdb.find({}).to_list(length=None)
    
    # 🔴 FIX: Convert all active chats to strict integers
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
        # 🔴 FIX: Strict integer comparison
        ids = [int(c["chat_id"]) for c in served]
        
        # Checking intersection properly
        active_in_this = list(set(active_chats_ints).intersection(set(ids)))
        
        if active_in_this:
            has_active = True
            
            # Bot Details Fetching
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

# --- TOTAL VC COMMAND (NEW) ---

@app.on_message(filters.command(["tvc", "totalvc"]) & SUDOERS)
async def total_vc_chats(_, message: Message):
    # Safe counting logic
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
        f"*(Includes Main Bot and Clones IF database is shared)*\n\n"
        f"{POWERED_BY}"
    )
    await message.reply_text(text)

# --- ASTATS & CALLBACKS ---

@app.on_message(filters.command(["astats"]) & SUDOERS)
async def astats(_, message: Message):
    raw_vc = await get_active_chats()
    raw_vvc = await get_active_video_chats()
    
    tvc = len(raw_vc) if raw_vc else 0
    tvvc = len(raw_vvc) if raw_vvc else 0
    
    text = (
        f"📊 **PritiMusic Stats**\n\n"
        f"🌐 **Total Active VC:** `{tvc}`\n"
        f"🌐 **Total Active VVC:** `{tvvc}`\n"
        f"*(Note: Count relies on global database)*\n\n"
        f"{POWERED_BY}"
    )
    
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎤 Active VC", callback_data="activevc_cb"), InlineKeyboardButton("📹 Active VVC", callback_data="activev_cb")],
            [InlineKeyboardButton("🤖 Clone VC", callback_data="cvc_cb"), InlineKeyboardButton("🤖 Clone VVC", callback_data="cvvc_cb")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
    )

# Callback handlers for buttons
@app.on_callback_query(filters.regex("activevc_cb") & SUDOERS)
async def cb_vc(c, q): 
    await active_voice_chats(c, q.message)

@app.on_callback_query(filters.regex("activev_cb") & SUDOERS)
async def cb_vvc(c, q): 
    await active_video_chats(c, q.message)

@app.on_callback_query(filters.regex("cvc_cb") & SUDOERS)
async def cb_cvc(c, q): 
    await clone_vc_stats(c, q.message)

@app.on_callback_query(filters.regex("cvvc_cb") & SUDOERS)
async def cb_cvvc(c, q): 
    await clone_vvc_stats(c, q.message)

@app.on_callback_query(filters.regex("close") & SUDOERS)
async def cb_close(_, q): 
    await q.message.delete()
