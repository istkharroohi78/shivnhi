import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch

from PritiMusic import app
from PritiMusic.utils.database import clonebotdb

# Config se URL lenge, na mile toh default set kar denge
try:
    from config import YOUTUBE_IMG_URL
except ImportError:
    YOUTUBE_IMG_URL = "https://te.legra.ph/file/b8a0c1a00db3e57522b53.jpg"

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    return image.resize((newWidth, newHeight))


# Yahan user_id aur client parameters add kar diye hain taaki Autoplay break na ho
async def get_thumb(videoid, user_id, client):
    # Fetching Bot and Owner details for dynamic watermark
    bot_username = "SizzuMusicBot"
    owner_name = "Itzz_Istkhar"
    bot_id = "default"

    if client:
        try:
            me = await client.get_me()
            bot_username = me.username if me.username else me.first_name
            bot_id = me.id
            
            # Database se owner fetch karna
            bot_data = await clonebotdb.find_one({"bot_id": bot_id})
            if bot_data and bot_data.get("user_id"):
                owner = await client.get_users(bot_data.get("user_id"))
                owner_name = owner.first_name if owner.first_name else "OWNER"
        except Exception:
            pass

    os.makedirs("cache", exist_ok=True)
    # Cache file clonebots ke hisaab se separate save hogi
    file_name = f"cache/{videoid}_{bot_id}.png"
    
    if os.path.isfile(file_name):
        return file_name

    try:
        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        data = await results.next()
        result = data["result"][0]
        
        title = result.get("title", "Unknown Title")
        title = re.sub(r"\W+", " ", title).title()
        duration = result.get("duration", "Unknown")
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        views = result.get("viewCount", {}).get("short", "Unknown")

        # Thumbnail Image Download
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    async with aiofiles.open(f"cache/thumb{videoid}.png", mode="wb") as f:
                        await f.write(await resp.read())

        youtube = Image.open(f"cache/thumb{videoid}.png").convert("RGBA")

        # --- NEON PINK DESIGN APPLYING ---
        GLOW_COLOR = "#ff0099"  # Neon Pink
        BORDER_COLOR = "#FF1493"  # Deep Pink

        image1 = changeImageSize(1280, 720, youtube)
        image1 = image1.filter(ImageFilter.GaussianBlur(20))
        image1 = ImageEnhance.Brightness(image1).enhance(0.4)

        thumb_width = 840
        thumb_height = 460
        youtube_thumb = youtube.resize((thumb_width, thumb_height))

        mask = Image.new("L", (thumb_width, thumb_height), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([(0, 0), (thumb_width, thumb_height)], radius=20, fill=255)
        youtube_thumb.putalpha(mask)
        
        center_x = 640
        center_y_img = 300
        thumb_x = center_x - (thumb_width // 2)
        thumb_y = center_y_img - (thumb_height // 2)
        thumb_x2 = thumb_x + thumb_width
        thumb_y2 = thumb_y + thumb_height

        glow_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        draw_glow = ImageDraw.Draw(glow_layer)
        glow_expand = 20
        draw_glow.rounded_rectangle(
            [(thumb_x - glow_expand, thumb_y - glow_expand),
             (thumb_x2 + glow_expand, thumb_y2 + glow_expand)],
            radius=30, fill=GLOW_COLOR
        )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(30))
        image1.paste(glow_layer, (0, 0), glow_layer)
        
        border_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        draw_border = ImageDraw.Draw(border_layer)
        border_expand = 5
        draw_border.rounded_rectangle(
            [(thumb_x - border_expand, thumb_y - border_expand),
             (thumb_x2 + border_expand, thumb_y2 + border_expand)],
            radius=25, fill=BORDER_COLOR
        )
        image1.paste(border_layer, (0, 0), border_layer)

        image1.paste(youtube_thumb, (thumb_x, thumb_y), youtube_thumb)

        draw = ImageDraw.Draw(image1)

        # Fonts - PritiMusic ke assets path
        try:
            font_title = ImageFont.truetype("PritiMusic/assets/font.ttf", 45)
            font_details = ImageFont.truetype("PritiMusic/assets/font2.ttf", 30)
            font_watermark = ImageFont.truetype("PritiMusic/assets/font2.ttf", 25)
        except:
            font_title = ImageFont.load_default()
            font_details = ImageFont.load_default()
            font_watermark = ImageFont.load_default()

        def get_text_width(text, font):
            try:
                return draw.textlength(text, font=font)
            except AttributeError:
                return draw.textsize(text, font=font)[0]

        # Title Limit
        if len(title) > 35:
            title = title[:35] + "..."

        w_title = get_text_width(title, font_title)
        text_y_pos = thumb_y2 + 50

        # Title Draw
        draw.text(
            ((1280 - w_title) / 2, text_y_pos),
            text=title, fill="white", font=font_title, stroke_width=1, stroke_fill="black"
        )

        # Dynamic Bot Username from client (or SizzuMusicBot fallback)
        stats_text = f"YouTube : {views} | Time : {duration} | Player : @{bot_username}"
        w_stats = get_text_width(stats_text, font_details)
        draw.text(
            ((1280 - w_stats) / 2, text_y_pos + 70),
            text=stats_text, fill=BORDER_COLOR, font=font_details, stroke_width=1, stroke_fill="black"
        )

        # Top Right Dynamic Owner Name from clonebotdb
        w_classy = get_text_width(owner_name, font_watermark)
        draw.text(
            (1280 - w_classy - 30, 30),
            text=owner_name, fill="yellow", font=font_watermark, stroke_width=1, stroke_fill="black"
        )

        # Blue Colored Bottom Left Watermark
        draw.text(
            (30, 680),
            text="@betabot_hub", fill="#00BFFF", font=font_watermark, stroke_width=1, stroke_fill="black"
        )

        # Saving Image
        image1.convert("RGB").save(file_name, "PNG")

        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        return file_name

    except Exception as e:
        print(f"Thumb Error: {e}")
        return YOUTUBE_IMG_URL


async def get_qthumb(vidid):
    try:
        url = f"https://www.youtube.com/watch?v={vidid}"
        results = VideosSearch(url, limit=1)
        data = await results.next()
        return data["result"][0]["thumbnails"][0]["url"].split("?")[0]
    except:
        return YOUTUBE_IMG_URL
        
