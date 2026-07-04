import time
import random
import asyncio
from pyrogram import filters
from pyrogram.enums import ChatType, ChatAction, ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, Message, InlineKeyboardButton
# 👇 Nayi library yahan update kar di gayi hai
from youtubesearchpython.__future__ import VideosSearch

import config
from PritiMusic import app
from PritiMusic.misc import _boot_
from PritiMusic.plugins.sudo.sudoers import sudoers_list
from PritiMusic.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from PritiMusic.utils.decorators.language import LanguageStart
from PritiMusic.utils.formatters import get_readable_time
from PritiMusic.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS, START_IMG_URL, CMBOT
from strings import get_string

# 🔥 PREMIUM EMOJIS LIST 🔥
PREMIUM_EMOJIS = [
    "5422831825178206894", 
    "5368324170673489600",
    "5206607081334906820",
    "5206380668048496464"
]

# 🎨 Dynamic Color Generator (Random Styles)
def get_style_map():
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
    random.shuffle(styles)
    # Row me buttons ke hisaab se random color assign hoga
    return {1: styles[0], 2: styles[1], 3: styles[2]}

# 🔘 Smart Button Creator
def create_btn(text, cb=None, url=None, user_id=None, style=ButtonStyle.PRIMARY, no_emoji=False):
    kwargs = {"text": text, "style": style}
    if cb: kwargs["callback_data"] = cb
    if url: kwargs["url"] = url
    if user_id: kwargs["user_id"] = user_id
    if not no_emoji: kwargs["icon_custom_emoji_id"] = random.choice(PREMIUM_EMOJIS)
    return InlineKeyboardButton(**kwargs)

# Telegram Message Effect IDs
EFFECT_ID = [
    5046509860389126442,
    5107584321108051014,
    5104841245755180586,
    5159385139981059251,
]


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    loading_1 = await message.reply_text(random.choice(CMBOT))
    await add_served_user(message.from_user.id)
    
    await loading_1.edit_text("<b>ᴌᴏᴀᴅɪɴɢ....</b>")
    await asyncio.sleep(0.3)

    await loading_1.edit_text("<b>ꜱᴛᴀʀᴛɪɴɢ..ʙᴀʙʏ.❤️❤️</b>")
    await asyncio.sleep(0.3)

    await loading_1.edit_text("<b>ɪ ᴀᴍ ᴀʟɪᴠᴇ ʙᴀʙʏ❤️😌🫣🫣</b>")
    await asyncio.sleep(0.5)

    await loading_1.edit_text("<b>BETA ʙᴏᴛs🫣🫣.</b>")
    await asyncio.sleep(0.5)

    await loading_1.delete()
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            await app.send_chat_action(message.chat.id, ChatAction.TYPING)
            # Sticker Before Image in /start help
            await message.reply_sticker("CAACAgUAAxkBAAFJgZ1qBGwx9Z9vW5BhG3dw0l1A5j4CyQACXRYAAuc-wVWs4--9DGlDKzsE")
            return await message.reply_photo(
                random.choice(START_IMG_URL),
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"✦ {message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n<b>✦ ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n<b>✦ ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}",
                )
            return
        if name[0:3] == "inf":
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            
            # --- FIX APPLIED HERE ---
            try:
                results = VideosSearch(query, limit=1)
                search_data = await results.next()
                
                if not search_data or not search_data.get("result"):
                    return await m.edit_text("❌ Track details not found. The video might be restricted or deleted.")

                # Getting the first result safely
                result = search_data["result"][0]
                
                title = result.get("title", "Unknown Title")
                duration = result.get("duration", "Unknown Duration")
                views = result.get("viewCount", {}).get("short", "0")
                
                # Handle thumbnail safely
                thumbnails = result.get("thumbnails", [])
                thumbnail = thumbnails[0]["url"].split("?")[0] if thumbnails else random.choice(START_IMG_URL)
                
                channellink = result.get("channel", {}).get("link", "")
                channel = result.get("channel", {}).get("name", "Unknown Channel")
                link = result.get("link", query)
                published = result.get("publishedTime", "Unknown Date")

                searched_text = _["start_6"].format(
                    title, duration, views, published, channellink, channel, app.mention
                )
                
                # ✅ Random Colors applied to track info buttons
                s_map = get_style_map()
                key = InlineKeyboardMarkup(
                    [
                        [
                            create_btn(text=_["S_B_8"], url=link, style=s_map[2]),
                            create_btn(text=_["S_B_9"], url=config.SUPPORT_CHAT, style=s_map[2]),
                        ],
                    ]
                )
                await m.delete()
                await app.send_photo(
                    chat_id=message.chat.id,
                    photo=thumbnail,
                    caption=searched_text,
                    reply_markup=key,
                )
                if await is_on_off(2):
                    return await app.send_message(
                        chat_id=config.LOGGER_ID,
                        text=f"✦ {message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.\n\n✦ <b>ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n✦ <b>ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}",
                    )
            except Exception as e:
                return await m.edit_text(f"❌ An error occurred while fetching track info: `{e}`")
            # --- FIX ENDS HERE ---

    else:
        out = private_panel(_)
        await app.send_chat_action(message.chat.id, ChatAction.TYPING)
        
        # 👉 Yahan Sticker Send Hoga (Start Image se pehle)
        await message.reply_sticker("CAACAgUAAxkBAAFJgZ1qBGwx9Z9vW5BhG3dw0l1A5j4CyQACXRYAAuc-wVWs4--9DGlDKzsE")
        
        # 👉 Uske baad Start Image Send Hogi
        await message.reply_photo(
            random.choice(START_IMG_URL),
            caption=_["start_2"].format(message.from_user.mention, app.mention),
            reply_markup=InlineKeyboardMarkup(out),
        )
        if await is_on_off(2):
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=f"✦ {message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n✦ <b>ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n✦ <b>ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}",
            )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    await message.reply_photo(
        random.choice(START_IMG_URL),
        caption=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
    )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass
            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)
                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                await message.reply_text(
                    text=_["start_3"].format(
                        message.from_user.mention,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()
        except Exception as ex:
            print(ex)
