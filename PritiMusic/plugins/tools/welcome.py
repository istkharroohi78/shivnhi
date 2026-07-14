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

# MoviePy for Video Editing (Ensure ffmpeg is installed on Heroku/Server)
try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip
    import moviepy.video.fx.all as vfx 
except ImportError:
    VideoFileClip = ImageClip = CompositeVideoClip = AudioFileClip = None
    vfx = None

# Placeholder dictionaries and structures
welcome_state = {}  
last_welcome_msg = {}  
custom_welcomes = {}

# Logger setup
class MockLOGGER:
    @staticmethod
    def error(msg): print(f"ERROR: {msg}")
    @staticmethod
    def warning(msg): print(f"WARNING: {msg}")
LOGGER = MockLOGGER()

# ==========================================
# 1. AUTO DELETE MESSAGE FUNCTION (8 MINS)
# ==========================================
async def auto_delete_message(message, delay_seconds):
    try:
        await asyncio.sleep(delay_seconds)
        # In a real environment with app instance: await app.delete_messages(message.chat.id, message.id)
        await message.delete()
        print(f"DEBUG: Deleted message {message.id} after {delay_seconds} seconds.")
    except Exception as e:
        pass

# ==========================================
# 2. BUTTON & TEXT PARSER HELPERS
# ==========================================
def parse_custom_text(text):
    if not text:
        return "", None
    buttons = []
    def replacer(match):
        btn_text = match.group(1).strip()
        btn_url = match.group(2).strip()
        btn_color_str = (match.group(3) or "").strip().lower()
        
        b_style = ButtonStyle.PRIMARY
        if btn_color_str in ["red", "danger"]: b_style = ButtonStyle.DANGER
        elif btn_color_str in ["green", "success"]: b_style = ButtonStyle.SUCCESS
        elif btn_color_str in ["gray", "secondary"]: b_style = ButtonStyle.SECONDARY
            
        buttons.append([InlineKeyboardButton(btn_text, url=btn_url, style=b_style)])
        return "" 
        
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
    
    glow_size = (size[0] + 80, size[1] + 80)
    glow_img = Image.new("RGBA", glow_size, (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow_img)
    
    # Yellow outer
    draw_glow.ellipse((10, 10, glow_size[0]-10, glow_size[1]-10), fill=None, outline=(255, 255, 0, 100), width=10)
    # Pink inner facets
    draw_glow.ellipse((20, 20, glow_size[0]-20, glow_size[1]-20), fill=None, outline=(255, 0, 128, 150), width=8)
    # Blue inner core circle
    draw_glow.ellipse((30, 30, glow_size[0]-30, glow_size[1]-30), fill=None, outline=(0, 150, 255, 255), width=6)
    # Core warm yellow pulse core
    draw_glow.ellipse((40, 40, glow_size[0]-40, glow_size[1]-40), fill=None, outline=(255, 200, 0, 255), width=4)
    
    draw_glow.text((glow_size[0]//2 - 30, 20), "♥ ♥", fill=(255, 0, 128, 255), font=None)
    draw_glow.text((20, glow_size[1]//2 - 30), "★", fill=(255, 0, 128, 255), font=None)
    draw_glow.text((glow_size[0] - 60, glow_size[1]//2 + 20), "★", fill=(255, 255, 0, 255), font=None)
    
    draw_glow.ellipse((40, 40, glow_size[0]-40, glow_size[1]-40), fill=None, outline=(255, 255, 255, 255), width=2)
    
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255) 
    
    pfp_masked = Image.new("RGBA", size)
    pfp_masked.paste(pfp, (0, 0), mask=mask)
    
    glow_img.paste(pfp_masked, (40, 40), mask=pfp_masked)
    
    os.makedirs("downloads", exist_ok=True)
    temp_path = f"downloads/temp_circle_{random.randint(1000,9999)}.png"
    glow_img.save(temp_path)
    return temp_path

def draw_text_with_glow(draw, position, text, font, text_color, glow_color, stroke_width=6, stroke_fill=None):
    x, y = position
    if stroke_fill is None: stroke_fill = glow_color
    
    for i in range(15, 0, -3):
        alpha = int(50 / (i/2))
        current_glow_color = (glow_color[0], glow_color[1], glow_color[2], alpha)
        draw.text((x, y), text, fill=None, font=font, anchor="ma", align="center", stroke_width=i, stroke_fill=current_glow_color)

    draw.text((x, y), text, fill=text_color, font=font, anchor="ma", align="center", stroke_width=1, stroke_fill=(255, 255, 255, 255))

def create_text_images(uname, user_id, count, chat_title, specific_data_box_text):
    img_right = Image.new('RGBA', (600, 600), (255, 255, 255, 0))
    draw_r = ImageDraw.Draw(img_right)
    
    try:
        font_large = ImageFont.truetype("PritiMusic/assets/font.ttf", 60)
        font_placeholder = ImageFont.truetype("PritiMusic/assets/alt_font.ttf", 60)
        font_medium = ImageFont.truetype("PritiMusic/assets/font.ttf", 45) 
        font_small = ImageFont.truetype("PritiMusic/assets/alt_font.ttf", 25)
    except Exception:
        font_large = font_placeholder = ImageFont.load_default()
        font_medium = font_small = ImageFont.load_default()
        
    draw_r.line((100, 20, 500, 20), fill=(255, 0, 128), width=3)
    
    draw_text_with_glow(draw_r, (300, 60), "Name", font_placeholder, (255, 255, 255), (255, 0, 128), stroke_fill=(255, 0, 128, 100))
    draw_text_with_glow(draw_r, (300, 140), specific_data_box_text, font_large, (255, 255, 255), (255, 0, 128))
    
    draw_text_with_glow(draw_r, (300, 220), "username", font_placeholder, (255, 255, 255), (0, 255, 255), stroke_fill=(0, 255, 255, 100))
    draw_text_with_glow(draw_r, (300, 300), f"@{uname}"[:20] if uname else "", font_medium, (255, 255, 255), (0, 255, 255))
    
    draw_text_with_glow(draw_r, (300, 380), "ID", font_placeholder, (255, 255, 255), (255, 0, 128), stroke_fill=(255, 0, 128, 100))
    draw_text_with_glow(draw_r, (300, 460), f"{user_id}", font_medium, (255, 255, 255), (255, 0, 128))
    
    draw_r.line((100, 560, 500, 560), fill=(255, 0, 128), width=3)
    
    img_databox = Image.new('RGBA', (600, 300), (255, 255, 255, 0))
    draw_db = ImageDraw.Draw(img_databox)
    
    draw_db.line((200, 20, 400, 20), fill=(255, 255, 255, 150), width=2)
    draw_db.rectangle((180, 40, 420, 260), outline=(255, 255, 255, 255), width=2)
    
    db_text_lines = [
        "°͜͡• °*°°°* ... Shiv... ♪♫♥",
        f"☉ ɴᴀᴍᴇ ⧽ {specific_data_box_text}", 
        f"☉ ɪᴅ ⧽ `{user_id}`",
        f"☉ ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ⧽ {count}",
    ]
    y_pos = 60
    for line in db_text_lines:
        draw_db.text((210, y_pos), line, fill=(255, 255, 255, 255), font=font_small, anchor="la")
        y_pos += 40 
    
    draw_db.line((200, 280, 400, 280), fill=(255, 255, 255, 150), width=2)
    draw_db.text((300, 275), "★", fill=(255, 255, 255, 255), font=None, anchor="mm") 
    
    path_right = f"downloads/temp_right_{random.randint(1000,9999)}.png"
    path_databox = f"downloads/temp_databox_{random.randint(1000,9999)}.png"
    
    img_right.save(path_right)
    img_databox.save(path_databox)
    
    return path_right, path_databox

def generate_dynamic_welcome_video(pic_path, user_id, uname, count, chat_title, specific_data_box_text):
    bg_video_path = "PritiMusic/assets/car_entry_template.mp4" 
    audio_path = "PritiMusic/assets/welcome_song.mp3" 
    output_path = f"downloads/welcome_vid_{user_id}.mp4"

    if not os.path.exists(bg_video_path):
        LOGGER.error("Background Template Video not found!")
        return None

    try:
        bg_clip = VideoFileClip(bg_video_path).without_audio()
        circular_pic_path = create_circular_pfp(pic_path, size=(280, 280))
        right_text_path, databox_text_path = create_text_images(uname, user_id, count, chat_title, specific_data_box_text)
        
        start_time = 0.08  
        
        dp_clip = (ImageClip(circular_pic_path)
                   .set_start(start_time) 
                   .set_duration(bg_clip.duration - start_time)
                   .set_position(("left", 160))
                   .crossfadein(1.5)
                   .fx(vfx.resize, lambda t: 1 + 0.02 * math.sin(t * 5))) 

        right_text_clip = (ImageClip(right_text_path)
                            .set_start(start_time + 0.2)
                            .set_duration(bg_clip.duration - (start_time + 0.2))
                            .set_position(("right", 160))
                            .crossfadein(1.0)
                            .fx(vfx.resize, lambda t: 1 + 0.015 * math.sin(t * 6)))

        databox_clip = (ImageClip(databox_text_path)
                          .set_start(start_time + 0.5)
                          .set_duration(bg_clip.duration - (start_time + 0.5))
                          .set_position(("right", 460))
                          .crossfadein(1.0))

        final_video = CompositeVideoClip([bg_clip, dp_clip, right_text_clip, databox_clip])

        if os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            main_line_audio = audio_clip.subclip(0, min(audio_clip.duration, final_video.duration))
            final_video = final_video.set_audio(main_line_audio)
        else:
            LOGGER.warning("welcome_song.mp3 nahi mila! Video bina audio ke save ho rhi hai.")

        final_video.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac" if os.path.exists(audio_path) else None,
            preset="ultrafast",
            threads=4,
            logger=None
        )
        
        # Memory Cleanup
        bg_clip.close()
        dp_clip.close()
        right_text_clip.close()
        databox_clip.close()
        if os.path.exists(audio_path):
            audio_clip.close()
        final_video.close()
        
        for path in [circular_pic_path, right_text_path, databox_text_path]:
            if os.path.exists(path):
                os.remove(path)

        return output_path
        
    except Exception as e:
        LOGGER.error(f"Error in video generation: {e}")
        return None

# ==========================================
# 4. COMMAND HANDLERS
# ==========================================
@Client.on_message(filters.command("welcome") & filters.group)
async def toggle_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴇɴᴀʙʟᴇ ᴡᴇʟᴄᴏᴍᴇ!**")

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


@Client.on_message(filters.command("set_welcome") & filters.group)
async def set_custom_welcome(client, message):
    user = await client.get_chat_member(message.chat.id, message.from_user.id)
    if user.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        return await message.reply("**sᴏʀʀʏ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ sᴇᴛ ᴄᴜsᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ!**")

    args = message.command[1:]
    if args:
        state = args[0].lower()
        if state in ["off", "disable"]:
            if message.chat.id in custom_welcomes:
                del custom_welcomes[message.chat.id]
                await message.reply("**✅ Custom Welcome disabled.**")
            return

    if not message.reply_to_message:
         return await message.reply("Reply to content (Text/Photo/GIF/Sticker/etc) to set it as group welcome.")

    reply = message.reply_to_message
    
    welcome_data = {
         "type": "text" if reply.text else "sticker" if reply.sticker else "media",
         "text": reply.text or reply.caption or "Hello {mention}, welcome!",
         "timer": 480, 
         "buttons": None,
         "media_id": reply.sticker.file_id if reply.sticker else None
    }
    
    custom_welcomes[message.chat.id] = welcome_data
    await message.reply("**✅ Is group ke liye Custom Welcome successfully set ho gaya hai!**")


# ==========================================
# 5. NEW MEMBER EVENT HANDLER (FIXED)
# ==========================================
@Client.on_chat_member_updated(filters.group, group=-3)
async def greet_new_member(client, member: ChatMemberUpdated):
    chat_id = member.chat.id
    
    if welcome_state.get(chat_id, True) == False:
        return

    # Check for accurate JOIN condition
    old = member.old_chat_member
    new = member.new_chat_member

    was_member = old and old.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.RESTRICTED]
    is_member = new and new.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.RESTRICTED]

    if was_member or not is_member:
        return

    user = new.user
    count = await client.get_chat_members_count(chat_id)

    # Delete previous welcome message
    if chat_id in last_welcome_msg:
        try:
            await last_welcome_msg[chat_id].delete()
        except Exception:
            pass

    chat_title = member.chat.title
    custom_data = custom_welcomes.get(chat_id)

    # 🟢 CUSTOM WELCOME LOGIC
    if custom_data:
        raw_text = custom_data["text"]
        clean_text, reply_markup = parse_custom_text(raw_text)
        final_text = format_custom_text(clean_text, user, chat_title, count)
        
        m_type = custom_data["type"]
        m_id = custom_data["media_id"]
        del_time = custom_data.get("timer", 480) 
        
        try:
            if m_type == "sticker": 
                msg = await client.send_sticker(chat_id, sticker=m_id, reply_markup=reply_markup)
            elif m_type == "text":
                msg = await client.send_message(chat_id, text=final_text, reply_markup=reply_markup)
            else:
                return

            last_welcome_msg[chat_id] = msg
            
            if del_time > 0:
                asyncio.create_task(auto_delete_message(msg, del_time))
            return  
        except Exception as e:
            LOGGER.error(f"Custom Welcome Error: {e}")

    # 🟢 DYNAMIC VIDEO WELCOME LOGIC (FIXED ASYNC THREADING)
    try:
        os.makedirs("downloads", exist_ok=True)
        pic_path = "PritiMusic/assets/upic.png" 
        
        if user.photo:
            try:
                pic_path = await client.download_media(user.photo.big_file_id, file_name=f"downloads/pp{user.id}.png")
            except Exception:
                pass

        uname = user.username or user.first_name
        specific_data_box_text = "°͜͡• °*°°°* ... Shiv... ♪♫♥"
        
        # Async blocking fix
        welcome_vid = await asyncio.to_thread(
            generate_dynamic_welcome_video, 
            pic_path, user.id, uname, count, chat_title, specific_data_box_text
        )
        
        caption = f"**⎊─────☵ ᴡᴇʟᴄᴏᴍᴇ ☵─────⎊**\n\n**☉ ɴᴀᴍᴇ ⧽** {user.mention}\n**☉ ɪᴅ ⧽** `{user.id}`\n**☉ ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ⧽** {count}\n\n**⎉──────▢✭ 侖 ✭▢──────⎉**"
        
        styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("๏ our bots ๏", url=f"https://t.me/betabot_hub/6701", style=random.choice(styles))],
        ])

        if welcome_vid and os.path.exists(welcome_vid):
            msg = await client.send_video(chat_id, video=welcome_vid, caption=caption, reply_markup=markup)
        else:
            msg = await client.send_message(chat_id, text=caption, reply_markup=markup)

        last_welcome_msg[chat_id] = msg
        asyncio.create_task(auto_delete_message(msg, 480))
        
        # Cleanup
        if welcome_vid and os.path.exists(welcome_vid):
            os.remove(welcome_vid) 
        if pic_path and os.path.exists(pic_path) and "assets" not in pic_path:
            os.remove(pic_path) 

    except Exception as e:
        LOGGER.error(f"Welcome Error: {e}")
