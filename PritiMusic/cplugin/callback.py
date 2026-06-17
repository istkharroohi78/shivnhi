import random
import asyncio
from pyrogram import filters, Client
from pyrogram.types import CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup

import config
from PritiMusic import app, YouTube
from PritiMusic.core.call import Lucky
from PritiMusic.misc import SUDOERS, db
from PritiMusic.utils.database import (
    get_active_chats, get_lang, get_upvote_count, is_active_chat,
    is_music_playing, is_nonadmin_chat, music_off, music_on, set_loop, get_assistant
)
from PritiMusic.utils.database.autoplay import is_autoplay_group, add_autoplay_group, remove_autoplay_group
from PritiMusic.utils.decorators.language import languageCB
from PritiMusic.utils.formatters import seconds_to_min
from PritiMusic.utils.inline import close_markup, stream_markup, stream_markup_timer, stream_markup2, stream_markup_timer2, panel_markup_1, panel_markup_2, panel_markup_3, panel_markup_4, panel_markup_5
from PritiMusic.utils.stream.autoclear import auto_clean
from PritiMusic.utils.thumbnails import get_thumb
from config import BANNED_USERS, STREAM_IMG_URL, PLAYLIST_IMG_URL, votemode, adminlist
from strings import get_string
from PritiMusic.utils.inline.start import private_panel

# ✅ Import Styles
from button import styled_button, ButtonStyle

checker = {}
upvoters = {}

def get_random_img(img_list):
    if img_list:
        return random.choice(img_list) if isinstance(img_list, list) else img_list
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg"

# =====================================================================
# CALLBACK HANDLERS
# =====================================================================

# 🟢 THE FIX 1: @app ko @Client mein badal diya
@Client.on_callback_query(filters.regex("settingsback_helper") & ~BANNED_USERS)
@languageCB
async def settings_back_helper(client: Client, CallbackQuery, _):
    await CallbackQuery.answer()
    img = get_random_img(config.START_IMG_URL)
    await CallbackQuery.edit_message_media(
        media=InputMediaPhoto(media=img, caption=_["start_2"].format(CallbackQuery.from_user.mention, app.mention)),
        reply_markup=InlineKeyboardMarkup(private_panel(_))
    )

# 🟢 THE FIX 2: @app ko @Client mein badla taaki CLONE BOTS bhi buttons sunein!
@Client.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client: Client, CallbackQuery, _):
    bot = await client.get_me()
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat = callback_request.split("|")
    
    if "_" in str(chat):
        bet = chat.split("_")
        chat, counter = bet[0], bet[1]
    
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    
    mention = CallbackQuery.from_user.mention
    user_id = CallbackQuery.from_user.id
    user_name = CallbackQuery.from_user.first_name
    
    # Auth Check
    is_non_admin = await is_nonadmin_chat(chat_id)
    if not is_non_admin:
        if CallbackQuery.from_user.id not in SUDOERS:
            admins = adminlist.get(chat_id)
            if not admins or CallbackQuery.from_user.id not in admins:
                return await CallbackQuery.answer(_["admin_14"], show_alert=True)

    if command == "UpVote":
        if chat_id not in votemode: votemode[chat_id] = {}
        if chat_id not in upvoters: upvoters[chat_id] = {}
        
        voters = (upvoters[chat_id]).get(CallbackQuery.message.id, [])
        if CallbackQuery.from_user.id in voters:
            voters.remove(CallbackQuery.from_user.id)
            votemode[chat_id][CallbackQuery.message.id] = max(0, votemode[chat_id].get(CallbackQuery.message.id, 1) - 1)
        else:
            voters.append(CallbackQuery.from_user.id)
            votemode[chat_id][CallbackQuery.message.id] = votemode[chat_id].get(CallbackQuery.message.id, 0) + 1
            
        upvote = await get_upvote_count(chat_id)
        get_upvotes = votemode[chat_id][CallbackQuery.message.id]
        
        if get_upvotes >= upvote:
            await CallbackQuery.edit_message_text(_["admin_37"].format(upvote))
        else:
            upl = InlineKeyboardMarkup([[styled_button(text=f"👍 {get_upvotes}", callback_data=f"ADMIN UpVote|{chat_id}_{counter}", style=ButtonStyle.PRIMARY)]])
            await CallbackQuery.answer(_["admin_40"], show_alert=True)
            await CallbackQuery.edit_message_reply_markup(reply_markup=upl)

    elif command == "Pause":
        if not await is_music_playing(chat_id): return await CallbackQuery.answer(_["admin_1"], show_alert=True)
        await CallbackQuery.answer()
        await music_off(chat_id)
        await Lucky.pause_stream(chat_id)
        buttons = [[styled_button("ʀᴇsᴜᴍᴇ ▷", callback_data=f"ADMIN Resume|{chat_id}", style=ButtonStyle.SUCCESS), styled_button("ʀᴇᴘʟᴀʏ ↺", callback_data=f"ADMIN Replay|{chat_id}", style=ButtonStyle.PRIMARY)]]
        await CallbackQuery.message.reply_photo(photo=get_random_img(PLAYLIST_IMG_URL), caption=_["admin_2"].format(mention), reply_markup=InlineKeyboardMarkup(buttons))

    elif command == "Resume":
        if await is_music_playing(chat_id): return await CallbackQuery.answer(_["admin_3"], show_alert=True)
        await CallbackQuery.answer()
        await music_on(chat_id)
        await Lucky.resume_stream(chat_id)
        buttons = [[styled_button("sᴋɪᴘ ‣‣I", callback_data=f"ADMIN Skip|{chat_id}", style=ButtonStyle.PRIMARY), styled_button("sᴛᴏᴘ ▢", callback_data=f"ADMIN Stop|{chat_id}", style=ButtonStyle.DANGER)], [styled_button("ᴘᴀᴜsᴇ II", callback_data=f"ADMIN Pause|{chat_id}", style=ButtonStyle.SECONDARY)]]
        await CallbackQuery.message.reply_photo(photo=get_random_img(PLAYLIST_IMG_URL), caption=_["admin_4"].format(mention), reply_markup=InlineKeyboardMarkup(buttons))

    elif command in ["Stop", "End"]:
        await CallbackQuery.answer()
        await Lucky.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await CallbackQuery.message.reply_photo(photo=get_random_img(PLAYLIST_IMG_URL), caption=_["admin_5"].format(mention), reply_markup=close_markup(_))
        try: await CallbackQuery.message.delete()
        except: pass

    elif command == "Autoplay":
        state = await is_autoplay_group(chat_id)
        if state:
            await remove_autoplay_group(chat_id)
            await CallbackQuery.answer("🔴 Autoplay Disabled!", show_alert=True)
            await CallbackQuery.message.reply_text(f"**🎧 𝐀𝐮𝐭𝐨𝐩𝐥𝐚𝐲 𝐒𝐲𝐬𝐭𝐞𝐦**\nStatus: Disabled 🔴\nʙʏ : {mention}", reply_markup=close_markup(_))
        else:
            await add_autoplay_group(chat_id)
            await CallbackQuery.answer("🟢 Autoplay Enabled!", show_alert=True)
            await CallbackQuery.message.reply_text(f"**🎧 𝐀𝐮𝐭𝐨𝐩𝐥𝐚𝐲 𝐒𝐲𝐬𝐭𝐞𝐦**\nStatus: Enabled 🟢\nʙʏ : {mention}", reply_markup=close_markup(_))

    elif command in ["Skip", "Replay"]:
        check = db.get(chat_id)
        if not check: return await CallbackQuery.answer("Queue khali hai!", show_alert=True)
        
        await CallbackQuery.answer()
        
        if command == "Skip":
            popped = check.pop(0)
            if popped: await auto_clean(popped)
            if not check:
                await CallbackQuery.message.reply_text(_["admin_6"].format(mention, CallbackQuery.message.chat.title), reply_markup=close_markup(_))
                return await Lucky.stop_stream(chat_id)
            
            # 🟢 THE FIX 3: Safe Skip logic for clones (Same as our updated skip.py)
            clients = await Lucky.get_active_clients(chat_id)
            pytgcalls_client = clients[0] if clients else Lucky.one
            await Lucky.change_stream(pytgcalls_client, chat_id)
            return await CallbackQuery.edit_message_text(f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄", reply_markup=close_markup(_))
            
        else: # Replay Logic
            db[chat_id][0]["played"] = 0
            img = await get_thumb(check[0]["vidid"], user_id, user_name) or get_random_img(PLAYLIST_IMG_URL)
            await Lucky.skip_stream(chat_id, check[0]["file"], video=True if check[0]["streamtype"]=="video" else False)
            
            run = await CallbackQuery.message.reply_photo(
                photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{check[0]['vidid']}", check[0]['title'][:23], check[0]['dur'], check[0]['by']),
                reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id))
            )
            if chat_id in db and db[chat_id]:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            await CallbackQuery.edit_message_text(f"➻ sᴛʀᴇᴀᴍ ʀᴇᴩʟᴀʏᴇᴅ 🎄", reply_markup=close_markup(_))

# --- TIMER MARKUP UPDATER ---
async def markup_timer():
    while True:
        await asyncio.sleep(300)
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id): continue
                playing = db.get(chat_id)
                if not playing or int(playing[0].get("seconds", 0)) == 0: continue
                mystic = playing[0].get("mystic")
                if not mystic: continue
                
                try: language = await get_lang(chat_id); _ = get_string(language)
                except: _ = get_string("en")
                
                markup = playing[0].get("markup", "stream")
                buttons = stream_markup_timer(_, chat_id, seconds_to_min(playing[0]["played"]), playing[0]["dur"]) if markup == "stream" else stream_markup_timer2(_, chat_id, seconds_to_min(playing[0]["played"]), playing[0]["dur"])
                await mystic.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            except: continue

asyncio.create_task(markup_timer())
