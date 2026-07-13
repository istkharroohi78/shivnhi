import os
import random
import asyncio
import math  # 🟢 Math import kiya live animation ke liye
from logging import getLogger
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters, enums
from pyrogram.enums import ButtonStyle
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

# MoviePy for Video Editing
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip
import moviepy.video.fx.all as vfx # 🟢 VFX import kiya live glow ke liye

from PritiMusic import app 

LOGGER = getLogger(__name__)

welcome_state = {}  
last_welcome_msg = {}  

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
# 2. GLOW IMAGE & VIDEO PROCESSING
# ==========================================
def create_circular_pfp(pic_path, size=(300, 300)):
    """DP ko gol banata hai aur glowing cyan/white border deta hai"""
    pfp = Image.open(pic_path).convert("RGBA")
    pfp = pfp.resize(size, Image.Resampling.LANCZOS)
    
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((5, 5, size[0]-5, size[1]-5), fill=255) 
    pfp.putalpha(mask)
    
    os.makedirs("downloads", exist_ok=True)
    temp_path = f"downloads/temp_circle_{random.randint(1000,9999)}.png"
    pfp.save(temp_path)
    return temp_path

def draw_text_with_glow(draw, position, text, font, text_color, glow_color):
    """Text ko 3 layers me draw karta hai taaki Neon Glow effect aaye"""
    x, y = position
    # Layer 1: Thick Outer Glow
    draw.text((x, y), text, fill=glow_color, font=font, anchor="ma", align="center", stroke_width=6, stroke_fill=glow_color)
    # Layer 2: Medium Stroke
    draw.text((x, y), text, fill=glow_color, font=font, anchor="ma", align="center", stroke_width=3, stroke_fill=(0, 0, 0))
    # Layer 3: Main Bright Text
    draw.text((x, y), text, fill=text_color, font=font, anchor="ma", align="center", stroke_width=1, stroke_fill=(255, 255, 255))

def create_text_images(uname, user_id):
    """Transparent background par Neon Glowing text generate karta hai"""
    img_center = Image.new('RGBA', (800, 350), (255, 255, 255, 0))
    draw_c = ImageDraw.Draw(img_center)
    
    img_left = Image.new('RGBA', (400, 150), (255, 255, 255, 0))
    draw_l = ImageDraw.Draw(img_left)
    
    try:
        font_large = ImageFont.truetype("PritiMusic/assets/font.ttf", 55)
        font_small = ImageFont.truetype("PritiMusic/assets/font.ttf", 35) 
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    # --- Center Text (Main Info & BETA BOTS) ---
    # User Name (White text with Electric Blue Glow)
    text_main = f"WELCOME @{uname}\nID: {user_id}"
    draw_text_with_glow(draw_c, (400, 30), text_main, font_large, (255, 255, 255), (0, 150, 255))
    
    # BETA BOTS (Gold text with Orange/Yellow Glow)
    text_beta = "BETA BOTS"
    draw_text_with_glow(draw_c, (400, 180), text_beta, font_small, (255, 255, 0), (255, 100, 0))
    
    # --- Bottom Left (the shiv) ---
    # the shiv (Cyan text with Deep Purple/Blue Glow)
    text_shiv = "the shiv"
    # Anchor 'la' means left-aligned for bottom corner
    draw_l.text((20, 50), text_shiv, fill=(0, 255, 255), font=font_small, anchor="la", stroke_width=3, stroke_fill=(138, 43, 226)) 
    
    path_center = f"downloads/temp_center_{random.randint(1000,9999)}.png"
    path_left = f"downloads/temp_left_{random.randint(1000,9999)}.png"
    
    img_center.save(path_center)
    img_left.save(path_left)
    
    return path_center, path_left

def generate_dynamic_welcome_video(pic_path, user_id, uname):
    """DP, Text aur Song mix karke LIVE ANIMATED final video banata hai"""
    bg_video_path = "PritiMusic/assets/car_entry_template.mp4" 
    audio_path = "PritiMusic/assets/main_chahta_hoon.mp3" 
    output_path = f"downloads/welcome_vid_{user_id}.mp4"

    if not os.path.exists(bg_video_path):
        LOGGER.error("Background Template Video not found!")
        return None

    try:
        bg_clip = VideoFileClip(bg_video_path)
        circular_pic_path = create_circular_pfp(pic_path)
        center_text_path, left_text_path = create_text_images(uname, user_id)
        
        start_time = 0.08  # Car entry speed
        
        # 1. 🟢 DP Clip with LIVE PULSE (Heartbeat effect)
        # math.sin(t*5) isko dheere-dheere bada aur chota karega
        dp_clip = (ImageClip(circular_pic_path)
                   .set_start(start_time) 
                   .set_duration(bg_clip.duration - start_time)
                   .set_position(("center", 120))
                   .crossfadein(1.5)
                   .fx(vfx.resize, lambda t: 1 + 0.02 * math.sin(t * 5))) 

        # 2. 🟢 Center Text Clip (Upward float + Breathing effect)
        def floating_and_breathing(t):
            # Float up + slight horizontal vibration
            return ("center", 500 - int(t * 12) + int(2 * math.sin(t * 8))) 

        center_text_clip = (ImageClip(center_text_path)
                            .set_start(start_time + 0.2)
                            .set_duration(bg_clip.duration - (start_time + 0.2))
                            .set_position(floating_and_breathing)
                            .crossfadein(1.0)
                            .fx(vfx.resize, lambda t: 1 + 0.015 * math.sin(t * 6)))

        # 3. 🟢 Bottom Left 'the shiv' Clip (Sliding in and glowing)
        def slide_in(t):
            return (20 + int(10 * math.sin(t * 3)), "bottom")

        left_text_clip = (ImageClip(left_text_path)
                          .set_start(start_time + 0.5)
                          .set_duration(bg_clip.duration - (start_time + 0.5))
                          .set_position(slide_in)
                          .crossfadein(1.0))

        # Clips Merge Karein
        final_video = CompositeVideoClip([bg_clip, dp_clip, center_text_clip, left_text_clip])

        # ==========================================
        # 🎵 AUDIO ADD KARNE KA LOGIC
        # ==========================================
        if os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            audio_start_time = 45  # 🔥 Song ki main line ka time (seconds)
            
            audio_end_time = audio_start_time + final_video.duration
            if audio_end_time > audio_clip.duration:
                audio_end_time = audio_clip.duration
                
            main_line_audio = audio_clip.subclip(audio_start_time, audio_end_time)
            final_video = final_video.set_audio(main_line_audio)
        else:
            LOGGER.warning("Song file 'main_chahta_hoon.mp3' not found!")

        # Final Render
        final_video.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            logger=None
        )
        
        # Memory Cleanup (CRITICAL)
        bg_clip.close()
        dp_clip.close()
        center_text_clip.close()
        left_text_clip.close()
        if os.path.exists(audio_path):
            audio_clip.close()
        final_video.close()
        
        # Temp Files Cleanup
        for path in [circular_pic_path, center_text_path, left_text_path]:
            if os.path.exists(path):
                os.remove(path)

        return output_path
        
    except Exception as e:
        LOGGER.error(f"Error in video generation: {e}")
        return None

# ==========================================
# 3. COMMAND & EVENT HANDLERS
# ==========================================
@app.on_message(filters.command("welcome") & filters.group)
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


@app.on_chat_member_updated(filters.group, group=-3)
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
        os.makedirs("downloads", exist_ok=True)
        pic_path = "PritiMusic/assets/upic.png" 
        
        if user.photo:
            try:
                pic_path = await client.download_media(user.photo.big_file_id, file_name=f"downloads/pp{user.id}.png")
            except Exception:
                pass

        uname = user.username or user.first_name
        
        welcome_vid = generate_dynamic_welcome_video(pic_path, user.id, uname)
        
        caption = f"**⎊─────☵ ᴡᴇʟᴄᴏᴍᴇ ☵─────⎊**\n\n**☉ ɴᴀᴍᴇ ⧽** {user.mention}\n**☉ ɪᴅ ⧽** `{user.id}`\n**☉ ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs ⧽** {count}\n\n**⎉──────▢✭ 侖 ✭▢──────⎉**"
        
        styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("๏ ᴠɪᴇᴡ ɴᴇᴡ ᴍᴇᴍʙᴇʀ ๏", url=f"tg://openmessage?user_id={user.id}", style=random.choice(styles))],
        ])

        if welcome_vid and os.path.exists(welcome_vid):
            msg = await client.send_video(chat_id, video=welcome_vid, caption=caption, reply_markup=markup)
        else:
            msg = await client.send_message(chat_id, text=caption, reply_markup=markup)

        last_welcome_msg[chat_id] = msg
        
        asyncio.create_task(auto_delete_message(msg, 120))
        
        if welcome_vid and os.path.exists(welcome_vid):
            os.remove(welcome_vid) 
        if pic_path and os.path.exists(pic_path) and "assets" not in pic_path:
            os.remove(pic_path) 

    except Exception as e:
        LOGGER.error(f"Welcome Error: {e}")
