import asyncio
import os
import re
import time
import yt_dlp
import aiohttp
import logging
import random
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist

# ----------------- CONFIGURATION -----------------
DOWNLOAD_DIR = "music_cache"
LOGGER = logging.getLogger(__name__)

# 1. Shruti API (Primary)
SHRUTI_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
SHRUTI_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsC0WH1GowF2HkGoKv4F3y")

# 2. OneGrab API (Secondary)
ONEGRAB_URL = os.environ.get("ONEGRAB_API_URL", "https://api.onegrab.fun")
ONEGRAB_KEYS = [
    os.environ.get("ONEGRAB_API_KEY_1", "0b168a_I21sJa-aeWzx30ubnZOrbSmjY5eST1ID"),
    os.environ.get("ONEGRAB_API_KEY_2", "c93415_Qc6z38kFH52j38qSF4MShLaojVL1JOB5"),
    os.environ.get("ONEGRAB_API_KEY_3", "be7ccd_J_G_4M4LlNUSRbm9YuyhGKXoERPC3_1H")
]

# 3. Apixhub API (Tertiary)
APIXHUB_URL = os.getenv("APIXHUB_API_URL", "https://bot.apixhub.fun")
APIXHUB_KEY = os.getenv("APIXHUB_API_KEY", "OijUY78533DPoPnOkwIK7qImQk")

# 4. Worker Fallback API (NEWLY ADDED)
WORKER_FALLBACK_URL = os.getenv("WORKER_FALLBACK_API_URL", "https://youtubenewapi.skybotsdeveloper.workers.dev")
WORKER_FALLBACK_KEY = os.getenv("WORKER_FALLBACK_API_KEY", "itsmesid")


# ----------------- HELPERS -----------------
def time_to_seconds(time_str):
    if not time_str: return 0
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(str(time_str).split(":"))))

def get_safe_filename(title: str, default_id: str) -> str:
    if not title or str(title).strip().lower() == "none": return default_id
    return re.sub(r'[\\/*?:"<>|]', "", str(title)).strip()

def extract_video_id(link: str) -> str:
    if "youtu.be/" in link: return link.split("youtu.be/")[1].split("?")[0]
    elif "v=" in link: return link.split("v=")[1].split("&")[0]
    return link

def clean_title_for_search(title: str) -> str:
    if not title or str(title).strip().lower() == "none": return ""
    clean = re.sub(r'[^\w\s,]', '', str(title))
    clean = re.sub(r'\(.*?\)|\[.*?\]', '', clean)
    clean = re.sub(r'episode\s*\d+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'official|video|audio|lyric|hd|hq|song|ary digital|hum tv|eng sub', '', clean, flags=re.IGNORECASE)
    return " ".join(clean.split()).strip()

async def _async_run(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# ----------------- SMART UNIFIED DOWNLOADER -----------------
async def smart_downloader(link: str, d_type: str, title: str = None) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3: return None
    
    safe_title = title if title and str(title).strip().lower() != "none" else video_id
    filename = get_safe_filename(safe_title, video_id)
    ext = "mp4" if d_type == "video" else "mp3"
    filepath = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    # Agar file pehle se available hai aur sahi size ki hai to return kar do
    if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
        return filepath

    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # 🔥 NO TIMEOUT (Late bhi ho tabhi download chalega)
    timeout = aiohttp.ClientTimeout(total=None) 
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Sabhi APIs ki list Priority ke hisaab se
    api_list = [
        {"name": "Shruti", "url": f"{SHRUTI_URL}/download", "params": {"url": yt_url, "type": "audio" if d_type=="audio" else "video", "api_key": SHRUTI_KEY}},
        {"name": "OneGrab", "url": f"{ONEGRAB_URL}/download", "params": {"url": yt_url, "type": "audio" if d_type=="audio" else "video", "api_key": random.choice(ONEGRAB_KEYS)}},
        {"name": "Apixhub", "url": f"{APIXHUB_URL}/{'streamvideo' if d_type=='video' else 'streamaudio'}/{video_id}", "params": {"key": APIXHUB_KEY}},
        {"name": "WorkerAPI", "url": WORKER_FALLBACK_URL, "params": {"url": yt_url, "type": d_type, "key": WORKER_FALLBACK_KEY, "api_key": WORKER_FALLBACK_KEY}}
    ]

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        for api in api_list:
            try:
                LOGGER.info(f"Trying to download via {api['name']} API...")
                async with session.get(api["url"], params=api["params"]) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "").lower()
                        
                        # 🔥 FIX 1: API JSON Link Extractor (For Shruti & OneGrab)
                        if "application/json" in content_type:
                            data = await resp.json()
                            download_url = data.get("url") or data.get("download_url") or data.get("link")
                            
                            if download_url:
                                LOGGER.info(f"👉 {api['name']} returned a link. Fetching file...")
                                async with session.get(download_url) as file_resp:
                                    with open(filepath, "wb") as f:
                                        async for chunk in file_resp.content.iter_chunked(131072):
                                            f.write(chunk)
                            else:
                                LOGGER.warning(f"🔴 {api['name']} API JSON Error/Limit: {data}")
                        
                        # 🔥 FIX 2: Direct stream handler (For Apixhub & Worker)
                        elif "text/html" not in content_type:
                            with open(filepath, "wb") as f:
                                async for chunk in resp.content.iter_chunked(131072):
                                    f.write(chunk)
                        
                        # Check if file downloaded successfully (>50KB)
                        if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
                            LOGGER.info(f"🟢 SUCCESS: Downloaded '{safe_title}' via {api['name']} API!")
                            return filepath
                        else:
                            LOGGER.warning(f"🔴 {api['name']} API File Rejected: Size too small (Error file).")
                    else:
                        LOGGER.warning(f"🔴 {api['name']} API HTTP Error: {resp.status}")
                        
            except Exception as e:
                LOGGER.warning(f"🔴 {api['name']} API Connection Failed: {str(e)}")
            
            # Agar file adhi download hokar fat gayi ya 50KB se choti thi, to use delete karo
            if os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass

    # --- 5. YT-DLP FALLBACK (Flexible Format Fix) ---
    LOGGER.info(f"All APIs failed. Falling back to yt-dlp for {safe_title}...")
    
    if d_type == "video":
        format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    else:
        format_string = "bestaudio[ext=m4a]/bestaudio/best/ba"

    ydl_opts = {
        'format': format_string,
        'outtmpl': filepath,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'noplaylist': True,
        'ignoreerrors': True,
        'extractor_args': {'youtube': ['player_client=android,web']},
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
    if d_type == "audio":
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

    try:
        await _async_run(yt_dlp.YoutubeDL(ydl_opts).download, [yt_url])
        if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
            LOGGER.info("🟢 SUCCESS: Downloaded via yt-dlp!")
            return filepath
    except Exception as e:
        LOGGER.error(f"🔴 yt-dlp Fallback Failed: {str(e)}")
        if os.path.exists(filepath):
            try: os.remove(filepath)
            except: pass

    # --- 6. SOUNDCLOUD FALLBACK (Final Audio Option) ---
    if d_type == "audio":
        clean_title = clean_title_for_search(title)
        if clean_title:
            LOGGER.info(f"Trying SoundCloud fallback for {clean_title}...")
            ydl_opts_sc = {
                'format': 'ba/b',
                'outtmpl': filepath,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'ignoreerrors': True,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            }
            try:
                await _async_run(yt_dlp.YoutubeDL(ydl_opts_sc).download, [f"scsearch1:{clean_title}"])
                if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
                    LOGGER.info("🟢 SUCCESS: Downloaded via SoundCloud Fallback!")
                    return filepath
            except Exception as e:
                LOGGER.error(f"🔴 SoundCloud Fallback Failed: {str(e)}")

    return None


# ----------------- YOUTUBE API CLASS -----------------
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message: messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            response = await results.next()
            if response and response.get("result"):
                result = response["result"][0]
                duration_sec = int(time_to_seconds(result["duration"])) if result.get("duration") else 0
                return result["title"], result["duration"], duration_sec, result["thumbnails"][0]["url"].split("?")[0], result["id"]
        except Exception: pass
        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]: return result["title"]
        except Exception: return "Unknown Title"

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]: return result["duration"]
        except Exception: return "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]: return result["thumbnails"][0]["url"].split("?")[0]
        except Exception: return "https://telegra.ph/file/2e3d368e77c449c287430.jpg"

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        downloaded_file = await smart_downloader(link, "video")
        if downloaded_file: return 1, downloaded_file
        return 0, "Video download failed"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        try:
            plist = await _async_run(Playlist.get, link)
            videos = plist.get("videos") or []
            return [data.get("id") for data in videos[:limit] if data and data.get("id")]
        except Exception: return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            response = await results.next()
            if response and response.get("result"):
                result = response["result"][0]
                return {
                    "title": result["title"],
                    "link": result["link"],
                    "vidid": result["id"],
                    "duration_min": result["duration"],
                    "thumb": result["thumbnails"][0]["url"].split("?")[0],
                }, result["id"]
        except Exception: pass
        return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        ytdl_opts = {
            "quiet": True,
            "cookiefile": "cookies.txt", 
            "extractor_args": {"youtube": ["player_client=tv,android,web"]},
            "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        }
        formats_available = []
        try:
            r = await _async_run(yt_dlp.YoutubeDL(ytdl_opts).extract_info, link, download=False)
            if r and "formats" in r:
                for format in r["formats"]:
                    try:
                        if "dash" not in str(format.get("format", "")).lower():
                            formats_available.append({
                                "format": format.get("format"),
                                "filesize": format.get("filesize"),
                                "format_id": format.get("format_id"),
                                "ext": format.get("ext"),
                                "format_note": format.get("format_note"),
                                "yturl": link,
                            })
                    except Exception: continue
        except Exception: pass
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result")
            return result[query_type]["title"], result[query_type]["duration"], result[query_type]["thumbnails"][0]["url"].split("?")[0], result[query_type]["id"]
        except Exception: return "Unknown Title", "0:00", "https://telegra.ph/file/2e3d368e77c449c287430.jpg", "None"

    # 🔥 MAIN DOWNLOAD ENTRY POINT
    async def download(
        self, link: str, mystic, video: Union[bool, str] = None, videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None, songvideo: Union[bool, str] = None, format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid: link = self.base + link
        file_title = title if isinstance(title, str) else None

        # Directly call our Smart Downloader
        d_type = "video" if video else "audio"
        downloaded_file = await smart_downloader(link, d_type, file_title)
        
        if downloaded_file: return downloaded_file, True
        return None, False

    async def autoplay(self, last_vidid: str, title: str, max_duration: int = None):
        try:
            search_query = clean_title_for_search(title)
            if not search_query: search_query = "top hits"
            
            search = VideosSearch(search_query, limit=10)
            result = await search.next()
            valid_choices = []
            
            if result and result.get("result"):
                for res in result["result"]:
                    vidid = str(res.get("id") or "")
                    if not vidid or vidid == "None" or vidid == last_vidid: continue
                        
                    dur_str = str(res.get("duration", "0:00"))
                    dur_sec = 0
                    if dur_str and ":" in dur_str:
                        parts = dur_str.split(":")
                        try:
                            if len(parts) == 2: dur_sec = int(parts[0]) * 60 + int(parts[1])
                            elif len(parts) == 3: dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        except ValueError: pass
                            
                    valid_choices.append({
                        "vidid": vidid,
                        "title": str(res.get("title", "Unknown Title")).title(),
                        "duration_min": dur_str,
                        "duration_sec": dur_sec
                    })

            if valid_choices: return random.choice(valid_choices[:3])
            return None
        except Exception as e:
            LOGGER.error(f"YouTube Autoplay Function Error: {e}")
            return None

YouTube = YouTubeAPI()
