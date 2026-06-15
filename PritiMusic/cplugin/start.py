import time
import random
import asyncio
import logging
from pyrogram import filters, Client
from pyrogram.enums import ChatType, ParseMode, ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, Message, InputMediaPhoto, InputMediaVideo, InlineKeyboardButton
from youtubesearchpython.__future__ import VideosSearch

import config
from PritiMusic import app
from PritiMusic.misc import _boot_
from PritiMusic.plugins.sudo.sudoers import sudoers_list
from PritiMusic.utils.formatters import get_readable_time

# Config Imports
from config import BANNED_USERS, OWNER_ID, START_IMG_URL, CMBOT, EFFECT_ID

# Module Imports
from PritiMusic.utils.decorators.language import LanguageStart, languageCB
from strings import get_string
from PritiMusic.utils.database.clonedb import get_owner_id_from_db, get_cloned_support_chat, get_cloned_support_channel
from PritiMusic.utils.database import add_served_user_clone, add_served_chat_clone
from PritiMusic.utils.database import clonebotdb

# Extra Import for Transfer Logic
from PritiMusic.core.mongo import mongodb
cloneownerdb = mongodb.cloneownerdb

# Initialize logging
LOG = logging.getLogger(__name__)

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

# 🔘 Smart Button Creator (Now with user_id support)
def create_btn(text, cb=None, url=None, user_id=None, style=ButtonStyle.PRIMARY, no_emoji=False):
    kwargs = {"text": text, "style": style}
    if cb: kwargs["callback_data"] = cb
    if url: kwargs["url"] = url
    if user_id: kwargs["user_id"] = user_id
    if not no_emoji: kwargs["icon_custom_emoji_id"] = random.choice(PREMIUM_EMOJIS)
    return InlineKeyboardButton(**kwargs)

# =====================================================================
# INTERNAL BUTTON HELPERS
# =====================================================================

def make_start_panel(bot_username, owner_url, 
                     txt_add, txt_support, txt_channel, txt_owner, txt_help, 
                     support_chat, support_channel,
                     custom_btn=None, btn_pos="TOP"):
    
    s_map = get_style_map()
    buttons = []

    # 1. Add to Group
    if txt_add != "HIDDEN":
        buttons.append([create_btn(text=txt_add, url=f"https://t.me/{bot_username}?startgroup=true", style=s_map[1])])

    # 2. Help Button
    if txt_help != "HIDDEN":
        buttons.append([create_btn(text=txt_help, cb="settings_back_helper", style=s_map[1])])

    # 3. Support & Channel (Row of 2)
    row_support = []
    if txt_support != "HIDDEN":
        row_support.append(create_btn(text=txt_support, url=support_chat, style=s_map[2]))
    if txt_channel != "HIDDEN":
        row_support.append(create_btn(text=txt_channel, url=support_channel, style=s_map[2]))
    if row_support:
        buttons.append(row_support)

    # 4. Owner Button
    if txt_owner != "HIDDEN":
        buttons.append([create_btn(text=txt_owner, url=owner_url, style=s_map[1])])

    # --- Custom Button Logic ---
    if custom_btn and custom_btn.get("text"):
        btn_url = custom_btn.get("url", "").strip()
        
        # Agar URL mein http ya tg format nahi hai, toh https laga do
        if btn_url and not btn_url.startswith(("http://", "https://", "tg://")):
            btn_url = f"https://{btn_url}"
        elif not btn_url:
            btn_url = "https://t.me/Telegram"
            
        # Custom button ko alag color code (s_map[3]) de dete hain randomly 
        c_btn = create_btn(text=custom_btn["text"], url=btn_url, style=s_map[3])
        
        if btn_pos in ["UP", "TOP"]:
            buttons.insert(0, [c_btn])
        elif btn_pos in ["DOWN", "BOTTOM"]:
            buttons.append([c_btn])
        elif btn_pos in ["MID", "MIDDLE"]:
            if len(buttons) >= 1:
                buttons.insert(1, [c_btn])
            else:
                buttons.append([c_btn])
        elif btn_pos == "LEFT":
             if buttons and isinstance(buttons[0], list): buttons[0].insert(0, c_btn)
             else: buttons.insert(0, [c_btn])
        elif btn_pos == "RIGHT":
             if buttons and isinstance(buttons[0], list): buttons[0].append(c_btn)
             else: buttons.insert(0, [c_btn])
        else:
            buttons.insert(0, [c_btn])

    return InlineKeyboardMarkup(buttons)


def make_gp_panel(bot_username, txt_add, txt_support, support_chat):
    s_map = get_style_map()
    buttons = [
        [
            create_btn(text=txt_add, url=f"https://t.me/{bot_username}?startgroup=true", style=s_map[2]),
            create_btn(text=txt_support, url=support_chat, style=s_map[2]),
        ]
    ]
    return InlineKeyboardMarkup(buttons)

# =====================================================================
# Database Helpers
# =====================================================================

async def get_start_image(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_image")

async def get_start_caption(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_caption")

async def get_start_button(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_button")

async def get_start_btn_pos(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_btn_pos", "TOP")

async def get_start_video(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_video")

async def get_start_sticker(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_sticker")

async def get_start_animation(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_animation")

async def get_start_reaction(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_reaction")

async def get_start_effect(bot_id):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    return d.get("start_effect")

async def get_custom_btn_text(bot_id, key, default_text):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    val = d.get(f"btn_{key}", default_text)
    return val

# ✅ Helper to Add Random Content
async def add_start_content(bot_id, key, value):
    d = await clonebotdb.find_one({"bot_id": bot_id}) or {}
    current = d.get(key)
    
    if current:
        if isinstance(current, dict):
            current = f"{current['text']} - {current['url']}" 

        if value in current:
            return False 
        final_value = f"{current}|||{value}"
    else:
        final_value = value
        
    await clonebotdb.update_one({"bot_id": bot_id}, {"$set": {key: final_value}}, upsert=True)
    return True

# --- General Helpers ---

def get_random_start_image():
    if START_IMG_URL:
        if isinstance(START_IMG_URL, list):
            return random.choice(START_IMG_URL)
        return START_IMG_URL
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg"

def format_link(val):
    if not val or str(val).strip() in ["", "none", "None"]:
        return "https://t.me/Telegram" 
    val = str(val).strip()
    if val.startswith("@"):
        val = val[1:] 
    if val.startswith(("https://", "http://", "tg://")):
        return val
    return f"https://t.me/{val}"

def get_mention_html(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

# =====================================================================
# START COMMAND (PRIVATE)
# =====================================================================

@Client.on_message(filters.command("start") & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    a = await client.get_me()
    bot_id = a.id
    await add_served_user_clone(message.from_user.id, bot_id)

    # 1. Loading Animation
    raw_sticker, raw_animation = await asyncio.gather(
        get_start_sticker(bot_id),
        get_start_animation(bot_id)
    )
    
    custom_sticker = random.choice(raw_sticker.split("|||")) if raw_sticker else None
    custom_animation = random.choice(raw_animation.split("|||")) if raw_animation else None
    
    loading = None

    if custom_sticker:
        try:
            loading = await message.reply_sticker(custom_sticker)
            await asyncio.sleep(2)
        except:
            pass
    elif custom_animation:
        try:
            loading = await message.reply_animation(custom_animation)
            await asyncio.sleep(2)
        except:
             pass
    else:
        anim_frames = ["<b>ʟᴏᴀᴅɪɴɢ</b>", "<b>ʟᴏᴀᴅɪɴɢ.</b>", "<b>ʟᴏᴀᴅɪɴɢ..</b>", "<b>ʟᴏᴀᴅɪɴɢ...</b>"]
        try:
            loading = await message.reply_text(anim_frames[0])
            for frame in anim_frames[1:]:
                await asyncio.sleep(0.3)
                try:
                    await loading.edit_text(frame, parse_mode=ParseMode.HTML)
                except:
                    pass
        except:
            pass

    # ✅ Optimized: Fetch All Data in Parallel (Fastest Way)
    (
        C_BOT_OWNER_ID,
        raw_support,
        raw_channel,
        txt_add,
        txt_support,
        txt_channel,
        txt_owner,
        txt_help,
        raw_custom_btn,
        btn_pos,
        raw_video,
        raw_img,
        raw_caption,
        raw_reaction,
        raw_effect
    ) = await asyncio.gather(
        get_owner_id_from_db(bot_id),
        get_cloned_support_chat(bot_id),
        get_cloned_support_channel(bot_id),
        get_custom_btn_text(bot_id, "add", _["S_B_3"]),
        get_custom_btn_text(bot_id, "support", _["S_B_9"]),
        get_custom_btn_text(bot_id, "channel", _["S_B_6"]),
        get_custom_btn_text(bot_id, "owner", _["C_B_2"]),
        get_custom_btn_text(bot_id, "help", _["S_B_4"]),
        get_start_button(bot_id),
        get_start_btn_pos(bot_id),
        get_start_video(bot_id),
        get_start_image(bot_id),
        get_start_caption(bot_id),
        get_start_reaction(bot_id),
        get_start_effect(bot_id),
    )

    C_SUPPORT_CHAT = format_link(raw_support)
    C_SUPPORT_CHANNEL = format_link(raw_channel)
    OWNER_URL = f"tg://openmessage?user_id={C_BOT_OWNER_ID}" if C_BOT_OWNER_ID else "https://t.me/Telegram"

    # ✅ 1. RANDOM REACTION LOGIC (Custom or Default)
    if raw_reaction:
        reaction_emoji = random.choice(raw_reaction.split("|||"))
    else:
        # Default Random Reactions
        reaction_emoji = random.choice(["🔥", "❤️", "🥰", "😍", "👍", "⚡", "🎉"])
    
    try:
        await message.react(reaction_emoji)
    except:
        pass

    try:
        if loading: await loading.delete()
    except:
        pass

    # Inline Arguments
    s_map = get_style_map()
    if len(message.text.split()) > 1:
        arg = message.text.split(None, 1)[1]
        
        if arg.startswith("help"):
            keyboard = InlineKeyboardMarkup([[create_btn(text=_["S_B_9"], url=C_SUPPORT_CHAT, style=s_map[1])]])
            return await message.reply_photo(
                photo=get_random_start_image(),
                caption=_["help_1"].format(C_SUPPORT_CHAT),
                reply_markup=keyboard,
                has_spoiler=True
            )
        if arg.startswith("sud"):
            return await sudoers_list(client=client, message=message, _=_)
        if arg.startswith("inf"):
            m = await message.reply_text("🔎")
            q = arg.replace("info_", "", 1)
            try:
                results = await VideosSearch(f"https://www.youtube.com/watch?v={q}", limit=1).next()
                result = results["result"][0]
                thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                caption = _["start_6"].format(result["title"], result["duration"], result["viewCount"]["short"], result["publishedTime"], result["channel"]["link"], result["channel"]["name"], a.mention)
                
                key = InlineKeyboardMarkup([
                    [
                        create_btn(text=_["S_B_8"], url=result["link"], style=s_map[2]), 
                        create_btn(text=_["S_B_9"], url=C_SUPPORT_CHAT, style=s_map[2])
                    ]
                ])
                await m.delete()
                return await message.reply_photo(photo=thumbnail, caption=caption, reply_markup=key, has_spoiler=True)
            except Exception as e:
                LOG.error(e)
                return await m.edit_text("❌ Error fetching info.")

    # Custom Button Data Logic
    custom_button_data = None
    if raw_custom_btn:
        if isinstance(raw_custom_btn, dict):
            custom_button_data = raw_custom_btn
        elif isinstance(raw_custom_btn, str):
            chosen_str = random.choice(raw_custom_btn.split("|||"))
            if "-" in chosen_str:
                txt, url = chosen_str.split("-", 1)
                custom_button_data = {"text": txt.strip(), "url": url.strip()}
    
    # Generate Buttons using Internal Function
    markup = make_start_panel(a.username, OWNER_URL,
                              txt_add, txt_support, txt_channel, txt_owner, txt_help,
                              C_SUPPORT_CHAT, C_SUPPORT_CHANNEL,
                              custom_button_data, btn_pos)

    # Media & Caption Logic
    start_video = random.choice(raw_video.split("|||")) if raw_video else None
    start_img = random.choice(raw_img.split("|||")) if raw_img else None
    custom_caption = random.choice(raw_caption.split("|||")) if raw_caption else None
    
    user_mention = get_mention_html(message.from_user.id, message.from_user.first_name)
    bot_mention = get_mention_html(a.id, a.first_name)
    
    if custom_caption:
        try:
            caption = custom_caption.format(
                name=user_mention,
                firstname=message.from_user.first_name,
                botname=bot_mention,
                username=a.username
            )
        except:
            caption = custom_caption
    else:
        formatted_text = (
            f"Hey {user_mention} 👋\n\n"
            f"⦿ THIS IS {bot_mention} !\n\n"
            f"➻ A FAST & POWERFUL TELEGRAM MUSIC PLAYER BOT.\n\n"
            f"──────────────────\n"
            f"✦ POWERED BY » {bot_mention}"
        )
        caption = f"<blockquote expandable>{formatted_text}</blockquote>"

    # 🔥 FIX: Removed message_effect_id entirely to prevent Pyrogram TypeError
    if start_video:
        try:
            return await message.reply_video(start_video, caption=caption, reply_markup=markup, has_spoiler=True, parse_mode=ParseMode.HTML)
        except:
            pass
    
    photo = start_img if start_img else get_random_start_image()
    await message.reply_photo(photo, caption=caption, reply_markup=markup, has_spoiler=True, parse_mode=ParseMode.HTML)

# =====================================================================
# START COMMAND (GROUP)
# =====================================================================

@Client.on_message(filters.command("start") & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    a = await client.get_me()
    bot_id = a.id
    uptime = get_readable_time(int(time.time() - _boot_))
    
    # Optimized Group Fetch
    raw_support, txt_add, txt_support, raw_video, raw_img = await asyncio.gather(
        get_cloned_support_chat(a.id),
        get_custom_btn_text(a.id, "add", _["S_B_1"]),
        get_custom_btn_text(a.id, "support", _["S_B_2"]),
        get_start_video(bot_id),
        get_start_image(bot_id)
    )

    C_SUPPORT_CHAT = format_link(raw_support)

    markup = make_gp_panel(a.username, txt_add, txt_support, C_SUPPORT_CHAT)
    
    caption = _["start_1"].format(a.mention, uptime)
    
    start_video = random.choice(raw_video.split("|||")) if raw_video else None
    start_img = random.choice(raw_img.split("|||")) if raw_img else None
    
    if start_video:
        try:
            return await message.reply_video(start_video, caption=caption, reply_markup=markup, has_spoiler=True)
        except:
            pass
    
    photo = start_img if start_img else get_random_start_image()
    await message.reply_photo(photo, caption=caption, reply_markup=markup, has_spoiler=True)
    await add_served_chat_clone(message.chat.id, a.id)

# =====================================================================
# CALLBACKS & FAST ACTIONS (Super Fast Back Button)
# =====================================================================

@Client.on_callback_query(filters.regex("settingsback_home") & ~BANNED_USERS)
@languageCB
async def home_back_handler(client, CallbackQuery, _):
    a = await client.get_me()
    bot_id = a.id

    # ✅ SUPER FAST: Fetching all Database values in ONE GO using asyncio.gather
    (
        C_BOT_OWNER_ID,
        raw_support,
        raw_channel,
        txt_add,
        txt_support,
        txt_channel,
        txt_owner,
        txt_help,
        raw_custom_btn,
        btn_pos,
        raw_video,
        raw_img,
        raw_caption,
        raw_effect
    ) = await asyncio.gather(
        get_owner_id_from_db(bot_id),
        get_cloned_support_chat(bot_id),
        get_cloned_support_channel(bot_id),
        get_custom_btn_text(bot_id, "add", _["S_B_3"]),
        get_custom_btn_text(bot_id, "support", _["S_B_9"]),
        get_custom_btn_text(bot_id, "channel", _["S_B_6"]),
        get_custom_btn_text(bot_id, "owner", _["C_B_2"]),
        get_custom_btn_text(bot_id, "help", _["S_B_4"]),
        get_start_button(bot_id),
        get_start_btn_pos(bot_id),
        get_start_video(bot_id),
        get_start_image(bot_id),
        get_start_caption(bot_id),
        get_start_effect(bot_id),
    )

    C_SUPPORT_CHAT = format_link(raw_support)
    C_SUPPORT_CHANNEL = format_link(raw_channel)
    OWNER_URL = f"tg://openmessage?user_id={C_BOT_OWNER_ID}" if C_BOT_OWNER_ID else "https://t.me/Telegram"

    custom_button_data = None
    if raw_custom_btn:
        if isinstance(raw_custom_btn, dict):
            custom_button_data = raw_custom_btn
        elif isinstance(raw_custom_btn, str):
            chosen_str = random.choice(raw_custom_btn.split("|||"))
            if "-" in chosen_str:
                txt, url = chosen_str.split("-", 1)
                custom_button_data = {"text": txt.strip(), "url": url.strip()}
    
    markup = make_start_panel(a.username, OWNER_URL,
                              txt_add, txt_support, txt_channel, txt_owner, txt_help,
                              C_SUPPORT_CHAT, C_SUPPORT_CHANNEL,
                              custom_button_data, btn_pos)

    start_video = random.choice(raw_video.split("|||")) if raw_video else None
    start_img = random.choice(raw_img.split("|||")) if raw_img else None
    custom_caption = random.choice(raw_caption.split("|||")) if raw_caption else None
    
    user_mention = get_mention_html(CallbackQuery.from_user.id, CallbackQuery.from_user.first_name)
    bot_mention = get_mention_html(a.id, a.first_name)
    
    if custom_caption:
        try:
            caption = custom_caption.format(name=user_mention, firstname=CallbackQuery.from_user.first_name, botname=bot_mention, username=a.username)
        except:
            caption = custom_caption
    else:
        formatted_text = (f"Hey {user_mention} 👋\n\n⦿ THIS IS {bot_mention} !\n\n➻ A FAST & POWERFUL TELEGRAM MUSIC PLAYER BOT.\n\n──────────────────\n✦ POWERED BY » {bot_mention}")
        caption = f"<blockquote expandable>{formatted_text}</blockquote>"

    try:
        if start_video:
            await CallbackQuery.edit_message_media(media=InputMediaVideo(media=start_video, caption=caption), reply_markup=markup)
        else:
            photo = start_img if start_img else get_random_start_image()
            await CallbackQuery.edit_message_media(media=InputMediaPhoto(media=photo, caption=caption), reply_markup=markup)
    except Exception as e:
        try:
            await CallbackQuery.message.delete()
        except:
            pass
        # 🔥 FIX: Removed message_effect_id entirely here as well
        if start_video:
            await CallbackQuery.message.reply_video(start_video, caption=caption, reply_markup=markup, has_spoiler=True, parse_mode=ParseMode.HTML)
        else:
            photo = start_img if start_img else get_random_start_image()
            await CallbackQuery.message.reply_photo(photo, caption=caption, reply_markup=markup, has_spoiler=True, parse_mode=ParseMode.HTML)

# =====================================================================
# MANAGEMENT & SETTINGS
# =====================================================================

@Client.on_message(filters.command(["transfer", "transferowner"]) & ~BANNED_USERS)
async def transfer_owner(client, message):
    bot_id = (await client.get_me()).id
    user = message.from_user

    current_owner_id = await get_owner_id_from_db(bot_id)
    if user.id not in [OWNER_ID, current_owner_id]:
        return await message.reply_text("❌ **Access Denied:** Only the Bot Owner can transfer ownership.")

    new_owner = None
    if message.reply_to_message:
        new_owner = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            new_owner = await client.get_users(message.command[1])
        except:
            return await message.reply_text("❌ User not found! Check Username or ID.")
    else:
        return await message.reply_text("❌ **Usage:**\nReply to a user or type `/transfer @username`.")

    if new_owner.is_bot:
        return await message.reply_text("❌ You cannot make a bot the owner.")
    if new_owner.id == user.id:
        return await message.reply_text("❌ You are already the owner.")

    await clonebotdb.update_one({"bot_id": bot_id}, {"$set": {"user_id": new_owner.id}})
    await cloneownerdb.update_one({"bot_id": bot_id}, {"$set": {"user_id": new_owner.id}}, upsert=True)

    await message.reply_text(f"✅ **Ownership Transferred!**\n👑 New Owner: {new_owner.mention}")

@Client.on_message(filters.command("viewstartsettings") & ~BANNED_USERS)
async def view_start_settings(client, message):
    bot_id = (await client.get_me()).id
    pos = await get_start_btn_pos(bot_id)
    await message.reply_text(f"⚙️ **Settings Viewed**\nButton Position: `{pos}`")

@Client.on_message(filters.command("resetstartsetting") & ~BANNED_USERS)
async def reset_start_settings(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {
        "start_image": "", "start_video": "", "start_sticker": "", 
        "start_animation": "", "start_caption": "", "start_button": "", 
        "start_btn_pos": "", "start_reaction": "", "start_effect": ""
    }})
    await message.reply_text("🔄 All Start Settings Reset!")

# =====================================================================
# START REACTION & EFFECT SETTERS
# =====================================================================

@Client.on_message(filters.command(["setstartreaction", "addstartreaction"]) & ~BANNED_USERS)
async def set_start_reaction_cmd(client, message):
    bot_id = (await client.get_me()).id
    if len(message.command) < 2:
        return await message.reply_text("❌ **Usage:** `/setstartreaction 🔥`\nYou can add multiple.")
    
    emoji = message.command[1]
    await add_start_content(bot_id, "start_reaction", emoji)
    await message.reply_text(f"✅ Start Reaction Added: {emoji}")

@Client.on_message(filters.command(["delstartreaction", "resetstartreaction"]) & ~BANNED_USERS)
async def del_start_reaction_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_reaction": ""}})
    await message.reply_text("✅ Start Reaction Deleted (Default Random will be used)!")

@Client.on_message(filters.command(["setstarteffect", "addstarteffect"]) & ~BANNED_USERS)
async def set_start_effect_cmd(client, message):
    bot_id = (await client.get_me()).id
    if len(message.command) < 2:
        return await message.reply_text("❌ **Usage:** `/setstarteffect 🔥` or ID\n\nSupported: 🔥, 👍, 👎, ❤️, 🎉, 💩")
    
    EFFECT_MAP = {
        "🔥": "5104841245755180586",
        "👍": "5107584321108051014",
        "👎": "5104858069142078462",
        "❤️": "5044134455711629726",
        "🎉": "5046509860389126442",
        "💩": "5046589136895476101"
    }
    
    arg = message.command[1]
    effect_id = EFFECT_MAP.get(arg, arg) # Use ID from map, or use raw input if not in map
    
    # ✅ Using add_start_content to allow Multiple Effects
    await add_start_content(bot_id, "start_effect", effect_id)
    await message.reply_text(f"✅ Start Effect Added!")

@Client.on_message(filters.command(["delstarteffect", "resetstarteffect"]) & ~BANNED_USERS)
async def del_start_effect_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_effect": ""}})
    await message.reply_text("✅ Start Effect Deleted (Default Random will be used)!")

# =====================================================================
# MEDIA SETTERS (Supports Adding Multiple)
# =====================================================================

@Client.on_message(filters.command(["setstartimg", "addstartimg"]) & ~BANNED_USERS)
async def set_start_image_cmd(client, message):
    bot_id = (await client.get_me()).id
    if message.reply_to_message and message.reply_to_message.photo:
        await add_start_content(bot_id, "start_image", message.reply_to_message.photo.file_id)
        await message.reply_text("✅ Start Image Added to Random List!")
    else:
        await message.reply_text("Reply to a photo.")

@Client.on_message(filters.command(["delstartimg", "resetstartimg"]) & ~BANNED_USERS)
async def del_start_image_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_image": ""}})
    await message.reply_text("✅ Start Images Deleted!")

@Client.on_message(filters.command(["setstartvideo", "addstartvideo"]) & ~BANNED_USERS)
async def set_start_video_cmd(client, message):
    bot_id = (await client.get_me()).id
    if message.reply_to_message and message.reply_to_message.video:
        await add_start_content(bot_id, "start_video", message.reply_to_message.video.file_id)
        await message.reply_text("✅ Start Video Added to Random List!")
    else:
        await message.reply_text("Reply to a video.")

@Client.on_message(filters.command(["delstartvideo", "resetstartvideo"]) & ~BANNED_USERS)
async def del_start_video_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_video": ""}})
    await message.reply_text("✅ Start Videos Deleted!")

@Client.on_message(filters.command(["setstartsticker", "addstartsticker"]) & ~BANNED_USERS)
async def set_start_sticker_cmd(client, message):
    bot_id = (await client.get_me()).id
    if message.reply_to_message and message.reply_to_message.sticker:
        await add_start_content(bot_id, "start_sticker", message.reply_to_message.sticker.file_id)
        await message.reply_text("✅ Sticker Added to Random List!")
    else:
        await message.reply_text("Reply to a sticker.")

@Client.on_message(filters.command(["delstartsticker", "resetstartsticker"]) & ~BANNED_USERS)
async def del_start_sticker_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_sticker": ""}})
    await message.reply_text("✅ Stickers Deleted!")

@Client.on_message(filters.command(["setstartanimation", "addstartanimation"]) & ~BANNED_USERS)
async def set_start_animation_cmd(client, message):
    bot_id = (await client.get_me()).id
    if message.reply_to_message and message.reply_to_message.animation:
        await add_start_content(bot_id, "start_animation", message.reply_to_message.animation.file_id)
        await message.reply_text("✅ Animation Added to Random List!")
    else:
        await message.reply_text("Reply to a GIF.")

@Client.on_message(filters.command(["delstartanimation", "resetstartanimation"]) & ~BANNED_USERS)
async def del_start_animation_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_animation": ""}})
    await message.reply_text("✅ Animations Deleted!")

# =====================================================================
# CAPTION & BUTTON (Multi/Random Supported)
# =====================================================================

@Client.on_message(filters.command(["setstartcaption", "addstartcaption"]) & ~BANNED_USERS)
async def set_start_caption_cmd(client, message):
    bot_id = (await client.get_me()).id
    if message.reply_to_message:
        text = message.reply_to_message.text.html if message.reply_to_message.text else message.reply_to_message.caption.html
        await add_start_content(bot_id, "start_caption", text)
        await message.reply_text("✅ Caption Added to Random List!")
    else:
        await message.reply_text("Reply to a text to add as Caption.")

@Client.on_message(filters.command(["delstartcaption", "resetstartcaption"]) & ~BANNED_USERS)
async def del_start_caption_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_caption": ""}})
    await message.reply_text("✅ Captions Deleted!")

@Client.on_message(filters.command(["setstartbutton", "addstartbutton"]) & ~BANNED_USERS)
async def set_start_button_cmd(client, message):
    bot_id = (await client.get_me()).id
    data = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    
    if not data or "-" not in data: 
        return await message.reply_text("Format: `/addstartbutton Text - URL`")
    
    txt, url = data.split("-", 1)
    btn_str = f"{txt.strip()} - {url.strip()}"
    
    await add_start_content(bot_id, "start_button", btn_str)
    await message.reply_text("✅ Button Added to Random List!")

@Client.on_message(filters.command(["delstartbutton", "resetstartbutton"]) & ~BANNED_USERS)
async def del_start_button_cmd(client, message):
    bot_id = (await client.get_me()).id
    await clonebotdb.update_one({"bot_id": bot_id}, {"$unset": {"start_button": ""}})
    await message.reply_text("✅ Custom Buttons Deleted!")

@Client.on_message(filters.command("setbtnpos") & ~BANNED_USERS)
async def set_btn_pos_cmd(client, message):
    bot_id = (await client.get_me()).id
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/setbtnpos [UP/DOWN/MID]`")
    
    raw_pos = message.command[1].upper()
    valid_pos = ["UP", "TOP", "DOWN", "BOTTOM", "MID", "MIDDLE", "LEFT", "RIGHT"]
    
    if raw_pos in valid_pos:
        if raw_pos == "TOP": raw_pos = "UP"
        if raw_pos == "BOTTOM": raw_pos = "DOWN"
        if raw_pos == "MIDDLE": raw_pos = "MID"
        
        await clonebotdb.update_one({"bot_id": bot_id}, {"$set": {"start_btn_pos": raw_pos}}, upsert=True)
        await message.reply_text(f"✅ Button Position: **{raw_pos}**")
    else:
        await message.reply_text("❌ Invalid! Use: UP, DOWN, MID")
