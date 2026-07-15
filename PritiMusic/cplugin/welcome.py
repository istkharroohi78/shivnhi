import os
import re
import random
import asyncio
from logging import getLogger
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pyrogram import Client, filters, enums
from pyrogram.enums import ButtonStyle
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

LOGGER = getLogger(__name__)

# --- In-Memory Database ---
welcome_state = {}  # {chat_id: True/False}
last_welcome_msg = {}  # {chat_id: message_id}
custom_welcomes = {}  # {chat_id: data}
weltime_state = {}  # {chat_id: seconds_to_delete}


# 🔥 1. BUTTON PARSER (Colors: red, green, blue)
def parse_buttons(text):
    if not text:
        return text, None
    
    clean_text = ""
    buttons = []
    
    available_styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
    color_map = {
        "red": ButtonStyle.DANGER,
        "green": ButtonStyle.SUCCESS,
        "blue": ButtonStyle.PRIMARY
    }
    
    for line in text.split("\n"):
        if re.search(r'\[.+?\]\(buttonurl:.+?\)', line, re.IGNORECASE):
            row = []
            parts = line.split("|")
            for part in parts:
                match = re.search(r'\[(.+?)\]\(buttonurl:([^\s\)]+)(?:\s+color:(red|green|blue))?\)', part, re.IGNORECASE)
                if match:
                    btn_name = match.group(1).strip()
                    btn_url = match.group(2).strip()
                    color_str = match.group(3)
                    
                    btn_style = color_map[color_str.lower()] if color_str else random.choice(available_styles)
                    row.append(InlineKeyboardButton(btn_name, url=btn_url, style=btn_style))
                else:
                    match_fallback = re.search(r'\[(.+?)\]\(buttonurl:(.+?)\)', part, re.IGNORECASE)
                    if match_fallback:
                        btn_name = match_fallback.group(1).strip()
                        btn_url = match_fallback.group(2).strip()
                        row.append(InlineKeyboardButton(btn_name, url=btn_url, style=random.choice(available_styles)))
                        
            if row:
                buttons.append(row)
        else:
            clean_text += line + "\n"
            
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return clean_text.strip(), markup


# 🔥 2. AUTO-DELETE MESSAGE (Chat se hatane ke liye)
async def auto_delete_message(message, delay_seconds):
    try:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
            await message.delete()
    except Exception:
        pass


# 🔥 3. AUTO-DELETE FILE (Server storage bachane ke liye 6 min baad)
async def delayed_file_delete(file_paths, delay_seconds):
    try:
        await asyncio.sleep(delay_seconds)
        for path in file_paths:
            if path and os.path.exists(path) and "assets" not in path:
                os.remove(path)
    except Exception:
        pass


def create_circular_pfp(pfp, size=(447, 447), brightness=1.3):
    pfp = pfp.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    pfp = ImageEnhance.Brightness(pfp).enhance(brightness)
    
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    
    pfp.putalpha(mask)
    return pfp


def generate_welcome_image(pic_path, user_id, uname):
    bg_path = "PritiMusic/assets/wel2.png"
    font_path = "PritiMusic/assets/font.ttf"
    
    if not os.path.exists(bg_path):
        LOGGER.warning("Background image 'wel2.png' not found in 'assets' folder.")
        return None

    background = Image.open(bg_path).convert("RGBA")
    
    try:
        pfp = Image.open(pic_path).convert("RGBA")
    except Exception:
        if os.path.exists("PritiMusic/assets/upic.png"):
            pfp = Image.open("PritiMusic/assets/upic.png").convert("RGBA") 
        else:
            pfp = Image.new("RGBA", (447, 447), (255, 255, 255, 0)) 
        
    pfp = create_circular_pfp(pfp)
    draw = ImageDraw.Draw(background)
    
    try:
        font = ImageFont.truetype(font_path, size=40) 
    except Exception:
        font = ImageFont.load_default()
        
    draw.text((730, 250), f'STATUS: MEMBER', fill=(255, 255, 255), font=font)
    draw.text((730, 330), f'ID: {user_id}', fill=(255, 255, 255), font=font)
    draw.text((730, 380), f"USERNAME: {uname}", fill=(255, 255, 255), font=font)
    
    pfp_position = (151, 139)
    background.paste(pfp, pfp_position, pfp)
    
    os.makedirs("downloads", exist_ok=True)
    output_path = f"downloads/welcome_{user_id}.png"
    background.save(output_path)
    return output_path


# 🔴 Toggle Welcome
@Client.on_message(filters.command("welcome") & filters.group)
async def toggle_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴇɴᴀʙʟᴇ ᴡᴇʟᴄᴏᴍᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ!**")

    if len(message.command) != 2 or message.command[1].lower() not in ["on", "off"]:
        return await message.reply("**ᴜsᴀɢᴇ:**\n**⦿ /welcome [on|off]**")

    state = message.command[1].lower()
    chat_id = message.chat.id

    if state == "on":
        welcome_state[chat_id] = True
        await message.reply(f"**ᴇɴᴀʙʟᴇᴅ ᴡᴇʟᴄᴏᴍᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ɪɴ {message.chat.title}**")
    else:
        welcome_state[chat_id] = False
        await message.reply(f"**ᴅɪsᴀʙʟᴇᴅ ᴡᴇʟᴄᴏᴍᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ɪɴ {message.chat.title}**")


# 🔴 Set Custom Welcome
@Client.on_message(filters.command("set_welcome") & filters.group)
async def set_custom_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ!**")

    cmd_text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
    
    if not message.reply_to_message and not cmd_text:
        example_text = (
            "**⚠️ ᴡᴇʟᴄᴏᴍᴇ sᴇᴛ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ᴋɪsɪ ᴍᴇssᴀɢᴇ (Pʜᴏᴛᴏ/Vɪᴅᴇᴏ/Gɪғ) ᴘᴀʀ ʀᴇᴘʟʏ ᴋᴀʀᴇɪɴ ʏᴀ ᴄᴏᴍᴍᴀɴᴅ ᴋᴇ sᴀᴀᴛʜ ᴛᴇxᴛ ʟɪᴋʜᴇɪɴ!**\n\n"
            "**👇 ᴄᴏᴘʏ-ᴘᴀsᴛᴇ ᴇxᴀᴍᴘʟᴇ:**\n"
            "`/set_welcome ❖ Hᴇʟʟᴏ {mention}!\n"
            "❖ Wᴇʟᴄᴏᴍᴇ ᴛᴏ ᴏᴜʀ ɢʀᴏᴜᴘ.\n"
            "❖ Yᴏᴜ ᴀʀᴇ ᴏᴜʀ {count}ᴛʜ ᴍᴇᴍʙᴇʀ.\n\n"
            "[❤ Dᴇᴠᴇʟᴏᴘᴇʀ](buttonurl:https://t.me/THE_SHIV color:red) | [✅ Uᴘᴅᴀᴛᴇs](buttonurl:https://t.me/Channel color:green)\n"
            "[🛠 Sᴜᴘᴘᴏʀᴛ](buttonurl:https://t.me/Support color:blue)`\n\n"
            "**💡 Tɪᴘ:** Uᴘᴀʀ ᴡᴀʟᴇ ᴄᴏᴅᴇ ᴋᴏ ᴄᴏᴘʏ ᴋᴀʀᴋᴇ ʙʜᴇᴊ ᴅᴇɪɴ, ᴀᴀᴘᴋᴀ ᴡᴇʟᴄᴏᴍᴇ sᴇᴛ ʜᴏ ᴊᴀʏᴇɢᴀ!\n"
            "⏱️ **Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ:** Wᴇʟᴄᴏᴍᴇ ᴋᴏ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ `/weltime 5` sᴇᴛ ᴋᴀʀᴇɪɴ."
        )
        return await message.reply(example_text)

    reply = message.reply_to_message
    msg_type = "text"
    file_id = None
    
    raw_text = cmd_text
    if reply:
        if not raw_text:
            raw_text = reply.text.markdown if reply.text else (reply.caption.markdown if reply.caption else "")
        
        if reply.photo:
            msg_type, file_id = "photo", reply.photo.file_id
        elif reply.video:
            msg_type, file_id = "video", reply.video.file_id
        elif reply.animation:
            msg_type, file_id = "animation", reply.animation.file_id
        elif reply.sticker:
            msg_type, file_id = "sticker", reply.sticker.file_id

    clean_text, custom_markup = parse_buttons(raw_text)
    markup = custom_markup if custom_markup else (reply.reply_markup if reply else None)

    custom_welcomes[message.chat.id] = {"type": msg_type, "file_id": file_id, "text": clean_text, "markup": markup}
    await message.reply("**✅ ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ᴡɪᴛʜ ʙᴜᴛᴛᴏɴs sᴇᴛ sᴜᴄᴄᴇssғᴜʟʟʏ!**")


# 🔴 Clear Custom Welcome
@Client.on_message(filters.command("cwelcome") & filters.group)
async def clear_custom_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ!**")

    chat_id = message.chat.id
    
    if chat_id in custom_welcomes:
        del custom_welcomes[chat_id]
        await message.reply("**✅ ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ᴄʟᴇᴀʀᴇᴅ!\n\nɴᴏᴡ ᴅᴇғᴀᴜʟᴛ ɪᴍᴀɢᴇ ᴡᴇʟᴄᴏᴍᴇ ᴡɪʟʟ ʙᴇ ᴜsᴇᴅ.**")
    else:
        await message.reply("**⚠️ ɴᴏ ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ɪs sᴇᴛ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.**")


# 🔴 Set Auto-Delete Time
@Client.on_message(filters.command("weltime") & filters.group)
async def set_weltime(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ!**")

    if len(message.command) != 2:
        return await message.reply("**ᴜsᴀɢᴇ:**\n**⦿ /weltime [minutes|off]** (e.g., /weltime 5)")

    val = message.command[1].lower()
    
    if val == "off":
        weltime_state[message.chat.id] = 0
        return await message.reply("**✅ ᴡᴇʟᴄᴏᴍᴇ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴅɪsᴀʙʟᴇᴅ.**")

    try:
        minutes = int(val)
        weltime_state[message.chat.id] = minutes * 60
        await message.reply(f"**✅ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇs ᴡɪʟʟ ɴᴏᴡ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴀғᴛᴇʀ {minutes} ᴍɪɴᴜᴛᴇs.**")
    except ValueError:
        pass


# 🔴 Chat Member Updated Event
@Client.on_chat_member_updated(filters.group, group=-3)
async def greet_new_member(client, member: ChatMemberUpdated):
    chat_id = member.chat.id
    
    if welcome_state.get(chat_id, True) == False:
        return

    if not (member.new_chat_member and not member.old_chat_member and member.new_chat_member.status != enums.ChatMemberStatus.BANNED):
        return

    user = member.new_chat_member.user
    count = await client.get_chat_members_count(chat_id)

    if chat_id in last_welcome_msg:
        try:
            await last_welcome_msg[chat_id].delete()
        except Exception:
            pass

    try:
        welcome_img = None
        pic_path = None
        
        # Agar admin ne custom welcome set kiya hai
        if chat_id in custom_welcomes:
            custom = custom_welcomes[chat_id]
            formatted_text = custom["text"].replace("{mention}", user.mention).replace("{id}", str(user.id)).replace("{username}", f"@{user.username}" if user.username else "None").replace("{count}", str(count))
            
            if custom["type"] == "text":
                msg = await client.send_message(chat_id, text=formatted_text, reply_markup=custom["markup"])
            elif custom["type"] == "photo":
                msg = await client.send_photo(chat_id, photo=custom["file_id"], caption=formatted_text, reply_markup=custom["markup"])
            elif custom["type"] == "video":
                msg = await client.send_video(chat_id, video=custom["file_id"], caption=formatted_text, reply_markup=custom["markup"])
            elif custom["type"] == "animation":
                msg = await client.send_animation(chat_id, animation=custom["file_id"], caption=formatted_text, reply_markup=custom["markup"])
            elif custom["type"] == "sticker":
                msg = await client.send_sticker(chat_id, sticker=custom["file_id"], reply_markup=custom["markup"])
                
        # Agar custom nahi hai to default Image Welcome
        else:
            pic_path = "PritiMusic/assets/upic.png"
            if user.photo:
                try:
                    os.makedirs("downloads", exist_ok=True)
                    pic_path = await client.download_media(user.photo.big_file_id, file_name=f"downloads/pp{user.id}.png")
                except Exception:
                    pass

            welcome_img = generate_welcome_image(pic_path, user.id, user.username or "None")
            
            # Clone bot ka apna username nikalne ke liye
            bot_info = await client.get_me()
            bot_username = bot_info.username
            
            caption = f"""
**⎊─────☵ ᴡᴇʟᴄᴏᴍᴇ ☵─────⎊**

**▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬**

**☉ ɴᴀᴍᴇ ⧽** {user.mention}
**☉ ɪᴅ ⧽** `{user.id}`
**☉ ᴜ_ɴᴀᴍᴇ ⧽** @{user.username or "None"}
**☉ ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ⧽** {count}

**▬▭▬▭▬▭▬▭▬▭▬▭▬▭▬**

**⎉──────▢✭ 侖 ✭▢──────⎉**
"""
            styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("๏ ᴠɪᴇᴡ ɴᴇᴡ ᴍᴇᴍʙᴇʀ ๏", url=f"tg://openmessage?user_id={user.id}", style=random.choice(styles))],
                [InlineKeyboardButton("✙ ᴋɪᴅɴᴀᴘ ᴍᴇ ✙", url=f"https://t.me/{bot_username}?startgroup=true", style=random.choice(styles))],
            ])

            if welcome_img:
                msg = await client.send_photo(chat_id, photo=welcome_img, caption=caption, reply_markup=markup)
            else:
                msg = await client.send_message(chat_id, text=caption, reply_markup=markup)

        last_welcome_msg[chat_id] = msg
        
        # 🔥 SERVER STORAGE CLEANUP (6 min / 360 sec delay)
        files_to_delete = [welcome_img, pic_path]
        asyncio.create_task(delayed_file_delete(files_to_delete, 360))
            
        # 🔥 CHAT MESSAGE CLEANUP (User set time, default 5 mins / 300 seconds)
        delay = weltime_state.get(chat_id, 300) 
        asyncio.create_task(auto_delete_message(msg, delay))

    except Exception as e:
        LOGGER.error(f"Welcome Error: {e}")
