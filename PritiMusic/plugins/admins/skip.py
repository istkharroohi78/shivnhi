import asyncio
from pyrogram import filters, Client
from pyrogram.types import Message

import config
from PritiMusic import app
from PritiMusic.core.call import Lucky
from PritiMusic.misc import db

# ✅ Imports Updated
from PritiMusic.utils.database import get_loop, is_active_chat
from PritiMusic.utils.decorators.admins import AdminRightsCheck
from PritiMusic.utils.inline import close_markup
from PritiMusic.utils.stream.autoclear import auto_clean
from config import BANNED_USERS

@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    # 1. Queue check
    check = db.get(chat_id)
    if not check:
        return await message.reply_text(_["queue_2"])
    
    # 2. Loop check (Agar loop on hai, toh skip allow nahi hoga)
    loop = await get_loop(chat_id)
    if loop != 0:
        return await message.reply_text(_["admin_8"])

    # 3. Multi-skip logic (e.g., /skip 3)
    skip_count = 1
    if len(message.command) > 1:
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            if 1 <= state <= len(check):
                skip_count = state
            else:
                return await message.reply_text(_["admin_11"].format(len(check)))
        else:
            return await message.reply_text(_["admin_11"].format(len(check)-1))

    # 4. Actual Skip Logic (Synced with change_stream)
    try:
        # Agar skip_count 1 se zyada hai, toh hum pehle ke songs uda denge
        if skip_count > 1:
            for x in range(skip_count - 1):
                try:
                    popped = check.pop(0)
                    if popped:
                        await auto_clean(popped)
                except:
                    pass
        
        # Ab last wale ko change_stream ke through skip karenge
        # Lucky.change_stream() automatically head pop karta hai aur next start karta hai
        pytgcalls_client = Lucky.one
        if chat_id in Lucky.active_clients and Lucky.active_clients[chat_id]:
            pytgcalls_client = Lucky.active_clients[chat_id][0]
            
        await Lucky.change_stream(pytgcalls_client, chat_id)
        
    except Exception as e:
        # Error handling
        try:
            await message.reply_text(
                text=_["admin_6"].format(message.from_user.mention, message.chat.title),
                reply_markup=close_markup(_)
            )
            await Lucky.stop_stream(chat_id)
        except:
            pass
