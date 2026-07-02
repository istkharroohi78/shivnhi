import os
import re
import random
import aiofiles
import aiohttp
import math
from PIL import (Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps)
# Nayi library yahan update kar di gayi hai 👇
from youtubesearchpython.__future__ import VideosSearch
from PritiMusic import app

# --- HELPER FUNCTIONS ---
def get_glowing_circle(image):
    img = image.convert("RGBA")
    size = min(img.size)
    img = ImageOps.fit(img, (size, size), centering=(0.5, 0.5))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    circular_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    circular_img.paste(img, (0, 0), mask)
    offset = 50
    glow_size = size + (offset * 2)
    glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow)
    draw_glow.ellipse((5, 5, glow_size-5, glow_size-5), fill=(255, 255, 0, 60))
    draw_glow.ellipse((15, 15, glow_size-15, glow_size-15), fill=(255, 255, 255, 80))
    draw_glow.ellipse((25, 25, glow_size-25, glow_size-25), fill=(255, 105, 180, 150))
    draw_glow.ellipse((35, 35, glow_size-35, glow_size-35), fill=(255, 255, 255, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(15))
    draw_border = ImageDraw.Draw(glow)
    draw_border.ellipse((offset - 4, offset - 4, size + offset + 4, size + offset + 4), outline="white", width=8)
    glow.paste(circular_img, (offset, offset), circular_img)
    return glow, offset

def draw_text_with_glow(draw, position, text, font, fill, glow_fill):
    x, y = position
    for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
        draw.text((x + dx, y + dy), text, font=font, fill=glow_fill)
    draw.text((x, y), text, font=font, fill=fill)

async def download_user_photo(user_id):
    try:
        async for photo in app.get_chat_photos(user_id, limit=1):
            return await app.download_media(photo.file_id, file_name=f"cache/{user_id}.jpg")
    except: return None
    return None

# --- MAIN THUMBNAIL FUNCTION ---
async def get_thumb(videoid, user_id, user_name):
    os.makedirs("cache", exist_ok=True)
    final_path = f"cache/{videoid}_{user_id}.png"
    if os.path.exists(final_path): return final_path

    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        data = await results.next()
        result = data["result"][0]
        title = re.sub(r"\W+", " ", result["title"]).title()
        duration = result.get("duration", "00:00")
        views = result.get("viewCount", {}).get("short", "Unknown")
        channel = result.get("channel", {}).get("name", "Unknown Artist")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(result["thumbnails"][0]["url"].split("?")[0]) as resp:
                f = await aiofiles.open(f"cache/temp_{videoid}.jpg", mode="wb")
                await f.write(await resp.read())
                await f.close()

        bg = Image.open(f"cache/temp_{videoid}.jpg").convert("RGBA").resize((1920, 1080))
        background = bg.filter(ImageFilter.GaussianBlur(25)).point(lambda p: p * 0.35)
        
        black_card = Image.new("RGBA", background.size, (0, 0, 0, 0))
        draw_card = ImageDraw.Draw(black_card)
        draw_card.rounded_rectangle((40, 40, 1880, 940), radius=60, fill=(0, 0, 0, 255), outline=(132, 224, 240, 200), width=6)
        background = Image.alpha_composite(background, black_card)
        draw = ImageDraw.Draw(background, "RGBA")
        
        try:
            f1 = ImageFont.truetype("PritiMusic/assets/font.ttf", 65)
            f2 = ImageFont.truetype("PritiMusic/assets/font2.ttf", 45)
            br = ImageFont.truetype("PritiMusic/assets/font2.ttf", 55)
            f_small = ImageFont.truetype("PritiMusic/assets/font2.ttf", 30)
        except:
            f1 = f2 = br = f_small = ImageFont.load_default()

        # Images
        yt_img_glowing, yt_offset = get_glowing_circle(bg.resize((500, 500)))
        background.paste(yt_img_glowing, (80 - yt_offset, 250 - yt_offset), yt_img_glowing)
        
        u_photo = await download_user_photo(user_id)
        if u_photo:
            # YAHAN CHANGE KIYA HAI: Blur value ko 6 kar diya hai 👇
            u_img_blurred = Image.open(u_photo).resize((450, 450)).filter(ImageFilter.GaussianBlur(6))
            u_img_glowing, u_offset = get_glowing_circle(u_img_blurred)
            background.paste(u_img_glowing, (1350 - u_offset, 250 - u_offset), u_img_glowing)

        # Texts
        draw.text((650, 300), (title[:22] + "...") if len(title) > 22 else title, fill="white", font=f1)
        draw.text((650, 400), f"Artist: {channel}", fill=(200, 200, 200), font=f2)
        draw.text((650, 470), f"Views: {views}", fill=(150, 150, 150), font=f2)
        draw.text((650, 530), f"Duration: {duration}", fill=(150, 150, 150), font=f2)

        # --- UNIFORM DYNAMIC WAVEFORM ---
        bar_count = 64; bar_width = 5; bar_gap = 12
        total_width = bar_count * bar_gap
        # Waveform thoda upar kiya (780 se 760 kiya)
        start_x = (1920 - total_width) / 2; base_y = 760 
        
        # Har video ka wave alag ho but x-axis par constant/barabar feel de
        random.seed(videoid) 
        for i in range(bar_count):
            h = random.randint(15, 45) # Random heights without the swell shape
            x0 = start_x + (i * bar_gap); x1 = x0 + bar_width
            y0 = base_y - h; y1 = base_y + h
            fill_color = (255, 255, 255, 255) if i < (bar_count // 2) else (150, 150, 150, 200)
            if x1 > x0: draw.rounded_rectangle((x0, y0, x1, y1), radius=3, fill=fill_color)

        # --- PROGRESS LINE & ICONS (Shifted Upwards) ---
        line_y = base_y + 55 # Pehle +80 tha, ab thoda upar kiya
        draw.line([(start_x, line_y), (start_x + total_width, line_y)], fill=(80, 80, 80), width=1)
        draw.line([(start_x, line_y), (start_x + (total_width // 2), line_y)], fill=(255, 255, 255), width=2)
        draw.ellipse(((start_x + total_width // 2) - 8, line_y - 8, (start_x + total_width // 2) + 8, line_y + 8), fill="white")
        draw.text((start_x, line_y + 20), "00:00", fill="white", font=f_small)
        draw.text((start_x + total_width - 80, line_y + 20), duration, fill="white", font=f_small)

        ctrl_y = line_y + 50 # Pehle +60 tha, play icons ko bhi aur upar kiya
        mid_x = 960
        
        # Play / Pause Icon
        draw.ellipse((mid_x - 30, ctrl_y - 30, mid_x + 30, ctrl_y + 30), outline="white", width=3)
        draw.polygon([(mid_x - 8, ctrl_y - 12), (mid_x + 14, ctrl_y), (mid_x - 8, ctrl_y + 12)], fill="white")
        
        # Previous / Next Icons
        draw.ellipse((mid_x - 80, ctrl_y - 20, mid_x - 45, ctrl_y + 20), outline="white", width=2)
        draw.ellipse((mid_x + 45, ctrl_y - 20, mid_x + 80, ctrl_y + 20), outline="white", width=2)

        # Branding
        draw_text_with_glow(draw, (80, 975), "BETA BOT HUB", br, (132, 224, 240), (0, 255, 255, 100))
        draw_text_with_glow(draw, (1480, 975), "THE SHIV", br, (255, 60, 160), (255, 0, 170, 100))

        background.convert("RGB").save(final_path, "PNG")
        return final_path
    except Exception as e:
        print(f"Thumbnail Error: {e}")
        return None
    finally:
        if os.path.exists(f"cache/temp_{videoid}.jpg"): os.remove(f"cache/temp_{videoid}.jpg")
        if 'u_photo' in locals() and u_photo and os.path.exists(u_photo): os.remove(u_photo)
