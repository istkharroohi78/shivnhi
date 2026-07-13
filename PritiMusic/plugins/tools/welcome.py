import os
import random
import asyncio
import math
import re
from logging import getLogger
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters, enums
from pyrogram.enums import ButtonStyle
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

# MoviePy for Video Editing (V1 Syntax)
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip
import moviepy.video.fx.all as vfx 

from PritiMusic import app 

LOGGER = getLogger(__name__)

welcome_state = {}  
last_welcome_msg = {}  
custom_welcomes = {}  # Store custom welcomes and settings

# ==========================================
# 1. AUTO DELETE MESSAGE FUNCTION
# ==========================================
async def auto_delete_message(message, delay_seconds):
    try:
        await asyncio.sleep(delay_seconds)
        await message.delete()
    except Exception:
        pass

# ==========================================
# 2. BUTTON & TEXT PARSER HELPERS
# ==========================================
def parse_custom_text(text):
    """Text me se [Button Name | Link | Color] format ko parse karta hai"""
    if not text:
        return "", None
        
    buttons = []
    
    def replacer(match):
        btn_text = match.group(1).strip()
        btn_url = match.group(2).strip()
        btn_color_str = (match.group(3) or "").strip().lower()
        
        # 🟢 Button Color Logic
        b_style = ButtonStyle.PRIMARY # Default Blue
        if btn_color_str in ["red", "danger"]:
            b_style = ButtonStyle.DANGER
        elif btn_color_str in ["green", "success"]:
            b_style = ButtonStyle.SUCCESS
        elif btn_color_str in ["gray", "secondary"]:
            b_style = ButtonStyle.SECONDARY
            
        buttons.append([InlineKeyboardButton(btn_text, url=btn_url, style=b_style)])
        return "" # Remove button syntax from main text
        
    # Regex handles both [Name | Link] and [Name | Link | Color]
    clean_text = re.sub(r'\[([^\]\|]+)\|\s*([^\]\|]+?)(?:\|\s*([^\]]+))?\]', replacer, text)
    
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return clean_text.strip(), markup

def format_custom_text(text, user, chat_title, count):
    if not text: return ""
    text = text.replace("{mention}", user.mention)
    text = text.replace("{id}", str(user.id))
    text = text.replace("{count}", str(count))
    text = text.replace("{chatname}", chat_title)
    return text

# ==========================================
# 3. GLOW IMAGE & VIDEO PROCESSING
# ==========================================
def create_circular_pfp(pic_path, size=(300, 300)):
    pfp = Image.open(pic_path).convert("RGBA")
    pfp = pfp.resize(size, Image.Resampling.LANCZOS)
    
    glow_size = (size[0] + 40, size[1] + 40)
    glow_img = Image.new("RGBA", glow_size, (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow_img)
    
    for i in range(15, 0, -2):
        glow_color = (0, 255, 255, int(50 / i)) if i % 2 == 0 else (255, 0, 128, int(50 / i))
        draw_glow.ellipse((20-i, 20-i, glow_size[0]-20+i, glow_size[1]-20+i), fill=None, outline=glow_color, width=4)

    draw_glow.ellipse((20, 20, glow_size[0]-20, glow_size[1]-20), fill=None, outline=(255, 255, 255, 255), width=3)
    
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255) 
    
    pfp_masked = Image.new("RGBA", size)
    pfp_masked.paste(pfp, (0, 0), mask=mask)
    glow_img.paste(pfp_masked, (20, 20), mask=pfp_masked)
    
    os.makedirs("downloads", exist_ok=True)
    temp_path = f"downloads/temp_circle_{random.randint(1000,9999)}.png"
    glow_img.save(temp_path)
    return temp_path

def draw_text_with_glow(draw, position, text, font, text_color, glow_color):
    x, y = position
    draw.text((x, y), text, fill=glow_color, font=font, anchor="ma", align="center", stroke_width=6, stroke_fill=glow_color)
    draw.text((x, y), text, fill=text_color, font=font, anchor="ma", align="center", stroke_width=1, stroke_fill=(255, 255, 255))

def create_text_images(uname, user_id):
    img_center = Image.new('RGBA', (800, 450), (255, 255, 255, 0))
    draw_c = ImageDraw.Draw(img_center)
    img_left = Image.new('RGBA', (400, 150), (255, 255, 255, 0))
    draw_l = ImageDraw.Draw(img_left)
    
    try:
        font_large = ImageFont.truetype("PritiMusic/assets/font.ttf", 55)
        font_small = ImageFont.truetype("PritiMusic/assets/font.ttf", 35) 
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    draw_c.line((100, 20, 700, 20), fill=(255, 0, 128), width=3)
    text_main = f"WELCOME @{uname}\nID: {user_id}\nBETA BOTS"
    draw_text_with_glow(draw_c, (400, 50), text_main, font_large, (255, 255, 255), (0, 150, 255))
    draw_c.line((100, 380, 700, 380), fill=(255, 0, 128), width=3)
    
    text_shiv = "THE SHIV"
    draw_l.text((20, 50), text_shiv, fill=(0, 255, 255), font=font_small, anchor="la", stroke_width=3, stroke_fill=(138, 43, 226)) 
    
    path_center = f"downloads/temp_center_{random.randint(1000,9999)}.png"
    path_left = f"downloads/temp_left_{random.randint(1000,9999)}.png"
    img_center.save(path_center); img_left.save(path_left)
    return path_center, path_left

def generate_dynamic_welcome_video(pic_path, user_id, uname):
    bg_video_path = "PritiMusic/assets/car_entry_template.mp4" 
    audio_path = "PritiMusic/assets/welcome_song.mp3"  
    output_path = f"downloads/welcome_vid_{user_id}.mp4"
    if not os.path.exists(bg_video_path): return None

    try:
        bg_clip = VideoFileClip(bg_video_path).without_audio()
        circular_pic_path = create_circular_pfp(pic_path)
        center_text_path, left_text_path = create_text_images(uname, user_id)
        
        start_time = 0.08  
        dp_clip = (ImageClip(circular_pic_path).set_start(start_time).set_duration(bg_clip.duration - start_time)
                   .set_position(("center", 120)).crossfadein(1.5).fx(vfx.resize, lambda t: 1 + 0.02 * math.sin(t * 5))) 

        def floating(t): return ("center", 500 - int(t * 12) + int(2 * math.sin(t * 8))) 
        center_text_clip = (ImageClip(center_text_path).set_start(start_time + 0.2).set_duration(bg_clip.duration - (start_time + 0.2))
                            .set_position(floating).crossfadein(1.0).fx(vfx.resize, lambda t: 1 + 0.015 * math.sin(t * 6)))

        def slide_in(t): return (20 + int(10 * math.sin(t * 3)), "bottom")
        left_text_clip = (ImageClip(left_text_path).set_start(start_time + 0.5).set_duration(bg_clip.duration - (start_time + 0.5))
                          .set_position(slide_in).crossfadein(1.0))

        final_video = CompositeVideoClip([bg_clip, dp_clip, center_text_clip, left_text_clip])

        if os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            main_line_audio = audio_clip.subclip(0, min(audio_clip.duration, final_video.duration))
            final_video = final_video.set_audio(main_line_audio)

        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac" if os.path.exists(audio_path) else None, preset="ultrafast", threads=4, logger=None)
        
        bg_clip.close(); dp_clip.close(); center_text_clip.close(); left_text_clip.close()
        if os.path.exists(audio_path): audio_clip.close()
        final_video.close()
        
        for path in [circular_pic_path, center_text_path, left_text_path]:
            if os.path.exists(path): os.remove(path)
        return output_path
    except Exception: return None

# ==========================================
# 4. COMMAND HANDLERS
# ==========================================
@app.on_message(filters.command("welcome") & filters.group)
async def toggle_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴇɴᴀʙʟᴇ ᴡᴇʟᴄᴏᴍᴇ!**")

    if len(message.command) != 2 or message.command[1].lower() not in ["on", "off"]:
        return await message.reply("**ᴜsᴀɢᴇ:**\n**⦿ /welcome [on|off]**")

    if message.command[1].lower() == "on":
        welcome_state[message.chat.id] = True
        await message.reply(f"**ᴇɴᴀʙʟᴇᴅ ᴡᴇʟᴄᴏᴍᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ɪɴ {message.chat.title}**")
    else:
        welcome_state[message.chat.id] = False
        await message.reply(f"**ᴅɪsᴀʙʟᴇᴅ ᴡᴇʟᴄᴏᴍᴇ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ ɪɴ {message.chat.title}**")


@app.on_message(filters.command("set_welcome") & filters.group)
async def set_custom_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**Sirf Admins custom welcome set kar sakte hain!**")

    if not message.reply_to_message:
        return await message.reply(
            "**🛠 Custom Welcome Set Karne Ka Tarika:**\n\n"
            "Apne text, photo, GIF, sticker par reply karke command dein.\n"
            "Timer set karne ke liye: `/set_welcome 5` (5 min) ya `/set_welcome off` (delete nahi hoga).\n\n"
            "**Placeholders:**\n"
            "`{mention}`, `{id}`, `{count}`, `{chatname}`\n\n"
            "**Buttons Format:**\n"
            "`[Button Naam | https://link.com | red]`\n"
            "*(Colors: red, green, blue, gray)*"
        )

    # 🟢 TIMER LOGIC
    args = message.command[1:]
    delete_time = 480  # Default 8 mins in seconds
    
    if args:
        arg = args[0].lower()
        if arg == "off" or arg == "0":
            delete_time = 0
        elif arg.isdigit():
            delete_time = int(arg) * 60  # Convert minutes to seconds

    reply = message.reply_to_message
    media_type = "text"
    media_id = None

    if reply.photo:
        media_type = "photo"
        media_id = reply.photo.file_id
    elif reply.animation:
        media_type = "animation"
        media_id = reply.animation.file_id
    elif reply.sticker:
        media_type = "sticker"
        media_id = reply.sticker.file_id
    elif reply.video:
        media_type = "video"
        media_id = reply.video.file_id

    raw_text = reply.text or reply.caption or ""

    custom_welcomes[message.chat.id] = {
        "type": media_type,
        "media_id": media_id,
        "raw_text": raw_text,
        "delete_time": delete_time
    }
    
    del_msg = f"**{int(delete_time/60)} minute baad delete hoga.**" if delete_time > 0 else "**Auto-delete OFF kar diya gaya hai.**"
    await message.reply(f"**✅ Custom Welcome Set Ho Gaya!**\n{del_msg}")


# ==========================================
# 5. NEW MEMBER EVENT HANDLER
# ==========================================
@app.on_chat_member_updated(filters.group, group=-3)
async def greet_new_member(client, member: ChatMemberUpdated):
    chat_id = member.chat.id
    if welcome_state.get(chat_id, True) == False: return
    if not (member.new_chat_member and not member.old_chat_member and member.new_chat_member.status != enums.ChatMemberStatus.BANNED): return

    user = member.new_chat_member.user
    count = await client.get_chat_members_count(chat_id)

    if chat_id in last_welcome_msg:
        try: await last_welcome_msg[chat_id].delete()
        except Exception: pass

    chat_title = member.chat.title
    custom_data = custom_welcomes.get(chat_id)

    # 🟢 CUSTOM WELCOME LOGIC
    if custom_data:
        raw_text = custom_data["raw_text"]
        clean_text, reply_markup = parse_custom_text(raw_text)
        final_text = format_custom_text(clean_text, user, chat_title, count)
        
        m_type = custom_data["type"]
        m_id = custom_data["media_id"]
        del_time = custom_data.get("delete_time", 480)
        
        try:
            if m_type == "text":
                msg = await client.send_message(chat_id, text=final_text, reply_markup=reply_markup)
            elif m_type == "photo":
                msg = await client.send_photo(chat_id, photo=m_id, caption=final_text, reply_markup=reply_markup)
            elif m_type == "animation":
                msg = await client.send_animation(chat_id, animation=m_id, caption=final_text, reply_markup=reply_markup)
            elif m_type == "sticker":
                msg = await client.send_sticker(chat_id, sticker=m_id, reply_markup=reply_markup)
            elif m_type == "video":
                msg = await client.send_video(chat_id, video=m_id, caption=final_text, reply_markup=reply_markup)
                
            last_welcome_msg[chat_id] = msg
            
            if del_time > 0:
                asyncio.create_task(auto_delete_message(msg, del_time))
            return  
        except Exception as e:
            LOGGER.error(f"Custom Welcome Error: {e}")

    # 🟢 DEFAULT VIDEO WELCOME LOGIC
    try:
        os.makedirs("downloads", exist_ok=True)
        pic_path = "PritiMusic/assets/upic.png" 
        if user.photo:
            try: pic_path = await client.download_media(user.photo.big_file_id, file_name=f"downloads/pp{user.id}.png")
            except Exception: pass

        uname = user.username or user.first_name
        welcome_vid = generate_dynamic_welcome_video(pic_path, user.id, uname)
        
        caption = f"**⎊─────☵ ᴡᴇʟᴄᴏᴍᴇ ☵─────⎊**\n\n**☉ ɴᴀᴍᴇ ⧽** {user.mention}\n**☉ ɪᴅ ⧽** `{user.id}`\n**☉ ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ⧽** {count}\n\n**⎉──────▢✭ 侖 ✭▢──────⎉**"
        
        # Default button using Pyrogram Styles
        styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("๏ our bots ๏", url=f"https://t.me/betabot_hub/6701", style=random.choice(styles))]])

        if welcome_vid and os.path.exists(welcome_vid):
            msg = await client.send_video(chat_id, video=welcome_vid, caption=caption, reply_markup=markup)
        else:
            msg = await client.send_message(chat_id, text=caption, reply_markup=markup)

        last_welcome_msg[chat_id] = msg
        asyncio.create_task(auto_delete_message(msg, 480)) # Default 8 mins
        
        if welcome_vid and os.path.exists(welcome_vid): os.remove(welcome_vid) 
        if pic_path and os.path.exists(pic_path) and "assets" not in pic_path: os.remove(pic_path) 

    except Exception as e:
        LOGGER.error(f"Welcome Error: {e}")
