import asyncio
import os
import re
import time
import yt_dlp
import aiohttp
import logging
import config  
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist

# ----------------- CONFIGURATION -----------------
# Changed to "music_cache" to isolate audio files from .png profile pictures!
DOWNLOAD_DIR = "music_cache" 
LOGGER = logging.getLogger(__name__)

# Shruti API (NEW PRIMARY - FASTEST)
API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsC0WH1GowF2HkGoKv4F3y")

# OneGrab API (Secondary)
ONEGRAB_API_URL = os.environ.get("ONEGRAB_API_URL", "https://api.onegrab.fun")
ONEGRAB_API_KEY = os.environ.get("ONEGRAB_API_KEY", "fbee25_x8FqJTStnOF5Ry5vGzMXTbR8zmuJ0H29")

# Apixhub API (Tertiary Fallback)
APIXHUB_API_URL = os.getenv("APIXHUB_API_URL", "https://bot.apixhub.fun")
APIXHUB_API_KEY = os.getenv("APIXHUB_API_KEY", "OijUY78533DPoPnOkwIK7qImQk")


def time_to_seconds(time_str):
    stringt = str(time_str)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))

def get_safe_filename(title: str, default_id: str) -> str:
    if not title:
        return default_id
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()

def extract_video_id(link: str) -> str:
    if "youtu.be/" in link:
        return link.split("youtu.be/")[1].split("?")[0]
    elif "v=" in link:
        return link.split("v=")[1].split("&")[0]
    return link

def clean_title_for_search(title: str) -> str:
    """Removes emojis, hashtags, brackets, and junk words for clean fallback searches."""
    if not title: return ""
    clean = re.sub(r'[^\w\s,]', '', title)
    clean = re.sub(r'\(.*?\)|\[.*?\]', '', clean)
    clean = re.sub(r'official|video|audio|lyric|hd|hq|song', '', clean, flags=re.IGNORECASE)
    return " ".join(clean.split()).strip()

async def _async_run(func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

# ----------------- DOWNLOADERS -----------------

# 1. Shruti Downloader (PRIMARY - FASTEST)
async def api_download(video_id: str, download_type: str, title: str = None) -> str:
    if not API_URL or not API_KEY:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, video_id)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": yt_url, "type": "audio" if download_type == "audio" else "video", "api_key": API_KEY}
            ) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type and "text/html" not in content_type:
                        with open(file_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                                
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 FAST-HOP SUCCESS: Downloaded '{title}' from Shruti API!")
            return file_path
        else:
            if os.path.exists(file_path): os.remove(file_path)
            return None
            
    except Exception as e:
        LOGGER.error(f"Shruti API Failed: {e}. Skipping...")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        return None


# 2. OneGrab Downloader (SECONDARY)
async def onegrab_download(video_id: str, download_type: str, title: str = None) -> str:
    if not ONEGRAB_API_URL or not ONEGRAB_API_KEY:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, f"og_{video_id}")
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            params = {
                "url": yt_url, 
                "type": "audio" if download_type == "audio" else "video", 
                "api_key": ONEGRAB_API_KEY
            }
            async with session.get(
                f"{ONEGRAB_API_URL}/download", 
                params=params
            ) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type and "text/html" not in content_type:
                        with open(file_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                                
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 FAST-HOP SUCCESS: Downloaded '{title}' from OneGrab API!")
            return file_path
        else:
            if os.path.exists(file_path): os.remove(file_path)
            return None
            
    except Exception as e:
        LOGGER.error(f"OneGrab API Failed: {e}. Skipping...")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        return None


# 3. Apixhub Downloader (TERTIARY)
async def apixhub_download(video_id: str, download_type: str, title: str = None) -> str:
    if not APIXHUB_API_URL or not APIXHUB_API_KEY:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, f"apix_{video_id}")
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            endpoint = "streamvideo" if download_type == "video" else "streamaudio"
            url = f"{APIXHUB_API_URL}/{endpoint}/{video_id}?key={APIXHUB_API_KEY}"
            
            async with session.get(url) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type and "text/html" not in content_type:
                        with open(file_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                                
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 FAST-HOP SUCCESS: Downloaded '{title}' from Apixhub API!")
            return file_path
        else:
            if os.path.exists(file_path): os.remove(file_path)
            return None
            
    except Exception as e:
        LOGGER.error(f"Apixhub API Failed: {e}. Skipping...")
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        return None


async def ytdl_fallback_download(link: str, download_type: str, title: str = None) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    video_id = extract_video_id(link)
    filename = get_safe_filename(title, video_id)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    # 🚀 FIX: Extremely flexible format strings to stop "format not available" error
    video_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
    audio_format = 'bestaudio/best'
    
    ydl_opts = {
        'format': video_format if download_type == "video" else audio_format, 
        'outtmpl': file_path,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt', 
        'extractor_args': {'youtube': ['player_client=tv,android,web']}, 
        'geo_bypass': True,
        'nocheckcertificate': True,
        'noplaylist': True,
        'ignoreerrors': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    
    if download_type == "audio":
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        await _async_run(yt_dlp.YoutubeDL(ydl_opts).download, [link])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SOURCE-HOPPING SUCCESS: Downloaded '{title}' from yt-dlp!")
            return file_path
        return None
    except Exception as e:
        LOGGER.error(f"yt-dlp fallback error: {str(e)}")
        return None


async def soundcloud_fallback_download(title: str) -> str:
    if not title: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    clean_title = clean_title_for_search(title)
    if not clean_title: return None
    
    filename = get_safe_filename(clean_title, f"sc_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': file_path,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'ignoreerrors': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }
    
    try:
        search_query = f"scsearch1:{clean_title}"
        await _async_run(yt_dlp.YoutubeDL(ydl_opts).download, [search_query])
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SOURCE-HOPPING SUCCESS: Downloaded '{clean_title}' from SoundCloud!")
            return file_path
    except Exception as e:
        LOGGER.error(f"SoundCloud fallback error: {str(e)}")
    return None


async def download_song(link: str, title: str = None) -> str:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3:
        return None
        
    if not title:
        try:
            search = VideosSearch(video_id, limit=1)
            res = await search.next()
            if res and res.get("result"):
                title = res["result"][0]["title"]
        except Exception:
            pass

    # 1. Primary API
    api_result = await api_download(video_id, "audio", title)
    if api_result: return api_result
    
    LOGGER.warning(f"🔴 Shruti API failed for '{title}'. Hopping to OneGrab API...")

    # 2. Secondary API
    onegrab_result = await onegrab_download(video_id, "audio", title)
    if onegrab_result: return onegrab_result
    
    LOGGER.warning(f"🔴 OneGrab API failed for '{title}'. Hopping to Apixhub API...")

    # 3. Tertiary API
    apixhub_result = await apixhub_download(video_id, "audio", title)
    if apixhub_result: return apixhub_result

    LOGGER.warning(f"🔴 Apixhub API failed for '{title}'. Hopping to yt-dlp...")

    # 4. yt-dlp Fallback
    yt_result = await ytdl_fallback_download(link, "audio", title)
    if yt_result: return yt_result
    
    if title:
        LOGGER.warning(f"🔴 YouTube blocked '{title}'. Hopping to SoundCloud...")
        # 5. SoundCloud Fallback (Spotify and JioSaavn removed)
        sc_result = await soundcloud_fallback_download(title)
        if sc_result: return sc_result

    return None


async def download_video(link: str, title: str = None) -> str:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3:
        return None

    if not title:
        try:
            search = VideosSearch(video_id, limit=1)
            res = await search.next()
            if res and res.get("result"):
                title = res["result"][0]["title"]
        except:
            pass

    api_result = await api_download(video_id, "video", title)
    if api_result: return api_result
    
    LOGGER.warning(f"🔴 Shruti API failed for '{title}'. Hopping to OneGrab API...")

    onegrab_result = await onegrab_download(video_id, "video", title)
    if onegrab_result: return onegrab_result

    LOGGER.warning(f"🔴 OneGrab API failed for '{title}'. Hopping to Apixhub API...")

    apixhub_result = await apixhub_download(video_id, "video", title)
    if apixhub_result: return apixhub_result

    LOGGER.warning(f"🔴 Apixhub API failed for '{title}'. Hopping to yt-dlp...")

    return await ytdl_fallback_download(link, "video", title)


# ----------------- YOUTUBE API CLASS -----------------

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
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
                for result in response["result"]:
                    title = result["title"]
                    duration_min = result["duration"]
                    thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                    vidid = result["id"]
                    duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
                    return title, duration_min, duration_sec, thumbnail, vidid
        except Exception:
            pass

        try:
            ydl_opts = {
                "quiet": True, 
                "extract_flat": True, 
                "noplaylist": True,
                "cookiefile": "cookies.txt",
                "extractor_args": {"youtube": ["player_client=tv,android,web"]}, 
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            } 
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            search_query = link if "youtube.com" in link or "youtu.be" in link else f"ytsearch1:{link}"
            
            r = await _async_run(ydl.extract_info, search_query, download=False)
            if r and "entries" in r and len(r["entries"]) > 0:
                entry = r["entries"][0]
                title = entry.get("title")
                vidid = entry.get("id")
                dur_sec = int(entry.get("duration", 0))
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                duration_min = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                thumbnail = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
                return title, duration_min, dur_sec, thumbnail, vidid
        except Exception as e:
            LOGGER.error(f"yt-dlp search fallback failed in details: {e}")

        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return result["title"]
        except Exception:
            return "Unknown Title"

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return result["duration"]
        except Exception:
            return "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return result["thumbnails"][0]["url"].split("?")[0]
        except Exception:
            return "https://telegra.ph/file/2e3d368e77c449c287430.jpg"

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        try:
            plist = await _async_run(Playlist.get, link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data: continue
            vid = data.get("id")
            if not vid: continue
            ids.append(vid)
        return ids

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
        except Exception:
            pass

        try:
            ydl_opts = {
                "quiet": True, 
                "extract_flat": True, 
                "noplaylist": True,
                "cookiefile": "cookies.txt",
                "extractor_args": {"youtube": ["player_client=tv,android,web"]},
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            search_query = link if "youtube.com" in link or "youtu.be" in link else f"ytsearch1:{link}"
            r = await _async_run(ydl.extract_info, search_query, download=False)
            
            if r and "entries" in r and len(r["entries"]) > 0:
                entry = r["entries"][0]
                vidid = entry.get("id")
                dur_sec = int(entry.get("duration", 0))
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                
                return {
                    "title": entry.get("title"),
                    "link": f"https://www.youtube.com/watch?v={vidid}",
                    "vidid": vidid,
                    "duration_min": f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}",
                    "thumb": f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg",
                }, vidid
        except Exception as e:
            LOGGER.error(f"yt-dlp search fallback failed in track: {e}")

        return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        ytdl_opts = {
            "quiet": True,
            "cookiefile": "cookies.txt", 
            "extractor_args": {"youtube": ["player_client=tv,android,web"]},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "external_downloader": "aria2c",
            "external_downloader_args": [
                "-x", "16",            
                "-s", "16",            
                "-k", "1M",            
                "--allow-piece-length-change=true"
            ]
        }
        
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        formats_available = []
        
        try:
            r = await _async_run(ydl.extract_info, link, download=False)
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
        except Exception:
            pass
            
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        try:
            a = VideosSearch(link, limit=10)
            result = (await a.next()).get("result")
            return result[query_type]["title"], result[query_type]["duration"], result[query_type]["thumbnails"][0]["url"].split("?")[0], result[query_type]["id"]
        except Exception:
            return "Unknown Title", "0:00", "https://telegra.ph/file/2e3d368e77c449c287430.jpg", "None"

    async def download(
        self, link: str, mystic, video: Union[bool, str] = None, videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None, songvideo: Union[bool, str] = None, format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid: link = self.base + link
        try:
            file_title = title if isinstance(title, str) else None

            if video: downloaded_file = await download_video(link, title=file_title)
            else: downloaded_file = await download_song(link, title=file_title)
                
            if downloaded_file: return downloaded_file, True
            return None, False
        except Exception as e:
            LOGGER.error(f"Error in YouTubeAPI.download: {e}")
            return None, False

    # 🚀 FASTEST SEARCH API (Time Limit And Heavy Traffic Search Fallback Removed)
    async def autoplay(self, last_vidid: str, title: str, max_duration: int = None):
        try:
            import random
            search_query = f"{title}"
            valid_choices = []
            
            try:
                search = VideosSearch(search_query, limit=10)
                result = await search.next()
                if result and result.get("result"):
                    for res in result["result"]:
                        vidid = str(res.get("id") or "")
                        
                        # Skip if it's the exact song currently playing
                        if not vidid or vidid == "None" or vidid == last_vidid: 
                            continue
                            
                        dur_str = str(res.get("duration", "0:00"))
                        dur_sec = 0
                        
                        if dur_str and ":" in dur_str:
                            parts = dur_str.split(":")
                            try:
                                if len(parts) == 2: dur_sec = int(parts[0]) * 60 + int(parts[1])
                                elif len(parts) == 3: dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                            except ValueError: 
                                pass
                                
                        valid_choices.append({
                            "vidid": vidid,
                            "title": str(res.get("title", "Unknown Title")).title(),
                            "duration_min": dur_str,
                            "duration_sec": dur_sec
                        })
            except Exception: 
                pass 

            if valid_choices: 
                # Picks from top 5 instant results for smooth autoplay
                return random.choice(valid_choices[:5])
            return None
            
        except Exception as e:
            LOGGER.error(f"YouTube Autoplay Function Error: {e}")
            return None

YouTube = YouTubeAPI()
