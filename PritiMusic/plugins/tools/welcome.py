import os
import random
import asyncio 
from logging import getLogger
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pyrogram import Client, filters, enums
from pyrogram.enums import ButtonStyle
from pyrogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

# App import
from PritiMusic import app 

LOGGER = getLogger(__name__)

# --- Safely Import MoviePy for Video ---
try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    LOGGER.error("MoviePy not found! Video nahi banegi, fallback to image.")
    MOVIEPY_AVAILABLE = False
    VideoFileClip = ImageClip = CompositeVideoClip = None

# --- In-Memory Database ---
welcome_state = {}  
last_welcome_msg = {}  

# --- Auto Delete Task ---
async def auto_delete_message(message, delay_seconds):
    try:
        await asyncio.sleep(delay_seconds)
        await message.delete()
    except Exception:
        pass


# --- Image / PFP Processing ---
def create_circular_pfp(pfp, size=(447, 447), brightness=1.3):
    try:
        resample_filter = Image.Resampling.LANCZOS
    except AttributeError:
        resample_filter = Image.LANCZOS
        
    pfp = pfp.resize(size, resample_filter).convert("RGBA")
    pfp = ImageEnhance.Brightness(pfp).enhance(brightness)
    
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    
    pfp.putalpha(mask)
    return pfp

# --- Transparent Text Overlay Generator ---
def create_text_overlay(user_id, uname, video_size):
    """Video ke upar text lagane ke liye ek transparent image banata hai"""
    img = Image.new("RGBA", video_size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    font_path = "PritiMusic/assets/font.ttf"
    
    try:
        font = ImageFont.truetype(font_path, size=40)
    except Exception:
        font = ImageFont.load_default()
        
    # Same coordinates as your image script
    draw.text((730, 250), f'STATUS: MEMBER', fill=(255, 255, 255), font=font)
    draw.text((730, 330), f'ID: {user_id}', fill=(255, 255, 255), font=font)
    draw.text((730, 380), f"USERNAME: {uname}", fill=(255, 255, 255), font=font)
    
    temp_text_path = f"downloads/temp_text_{user_id}.png"
    img.save(temp_text_path)
    return temp_text_path

# --- LIVE VIDEO GENERATOR ---
def generate_welcome_video(pic_path, user_id, uname):
    if not MOVIEPY_AVAILABLE:
        return None

    # Ab hum wel2.mp4 background video use karenge
    bg_video_path = "PritiMusic/assets/wel2.mp4"
    if not os.path.exists(bg_video_path):
        LOGGER.warning("Background video 'wel2.mp4' not found in assets!")
        return None

    try:
        # 1. Load Background Video
        bg_clip = VideoFileClip(bg_video_path).without_audio()
        video_size = bg_clip.size
        
        # 2. Process PFP Image
        try:
            pfp = Image.open(pic_path).convert("RGBA")
        except Exception:
            pfp = Image.new("RGBA", (447, 447), (255, 255, 255, 0))
            
        pfp = create_circular_pfp(pfp)
        temp_pfp_path = f"downloads/temp_pfp_{user_id}.png"
        pfp.save(temp_pfp_path)
        
        # 3. Create PFP Clip & Position it exactly where you wanted
        pfp_clip = (ImageClip(temp_pfp_path)
                    .set_duration(bg_clip.duration)
                    .set_position((151, 139))) # Aapke coordinates
                    
        # 4. Create Text Overlay Clip
        temp_text_path = create_text_overlay(user_id, uname, video_size)
        text_clip = (ImageClip(temp_text_path)
                     .set_duration(bg_clip.duration)
                     .set_position(("center", "center")))
                     
        # 5. Merge Everything
        final_video = CompositeVideoClip([bg_clip, pfp_clip, text_clip])
        
        output_path = f"downloads/welcome_vid_{user_id}.mp4"
        
        # Render Video
        final_video.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio=False, 
            preset="ultrafast", 
            logger=None
        )
        
        # Cleanup memory and temp files
        bg_clip.close()
        pfp_clip.close()
        text_clip.close()
        final_video.close()
        os.remove(temp_pfp_path)
        os.remove(temp_text_path)
        
        return output_path
        
    except Exception as e:
        LOGGER.error(f"Video Generation Error: {e}")
        return None


# --- Welcome Toggle Command ---
@app.on_message(filters.command("welcome") & filters.group)
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


# --- Welcome Event Handler ---
@app.on_chat_member_updated(filters.group, group=-3)
async def greet_new_member(client, member: ChatMemberUpdated):
    chat_id = member.chat.id
    
    if welcome_state.get(chat_id, True) == False:
        return

    # 🔥 FIXED: Correct Pyrogram Join Detection Logic
    old = member.old_chat_member
    new = member.new_chat_member
    was_member = old and old.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.RESTRICTED]
    is_member = new and new.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.RESTRICTED]

    if was_member or not is_member:
        return

    user = new.user
    count = await client.get_chat_members_count(chat_id)

    if chat_id in last_welcome_msg:
        try:
            await last_welcome_msg[chat_id].delete()
        except Exception:
            pass

    try:
        pic_path = "PritiMusic/assets/upic.png"
        if user.photo:
            try:
                os.makedirs("downloads", exist_ok=True)
                pic_path = await client.download_media(user.photo.big_file_id, file_name=f"downloads/pp{user.id}.png")
            except Exception:
                pass

        uname = user.username or "None"
        
        # 🔥 Async thread me video banayega taaki bot hang na ho
        welcome_media = await asyncio.to_thread(generate_welcome_video, pic_path, user.id, uname)
        
        bot_username = app.username if hasattr(app, "username") and app.username else "PritiMusicBot"
        
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

        # Agar video successful ban gayi toh bhejo
        if welcome_media and os.path.exists(welcome_media):
            msg = await client.send_video(chat_id, video=welcome_media, caption=caption, reply_markup=markup)
        else:
            # Video fail hone par normal message bhejo
            msg = await client.send_message(chat_id, text=caption, reply_markup=markup)

        last_welcome_msg[chat_id] = msg
        
        # 120 seconds delete timer
        asyncio.create_task(auto_delete_message(msg, 120))
        
        # Files Cleanup
        if welcome_media and os.path.exists(welcome_media):
            os.remove(welcome_media)
        if pic_path and os.path.exists(pic_path) and "assets" not in pic_path:
            os.remove(pic_path)

    except Exception as e:
        LOGGER.error(f"Welcome Error: {e}")
