import asyncio
import os
import re
import json
import random
import logging
import aiohttp
import yt_dlp
import glob
from typing import Union
from urllib.parse import urlparse, unquote
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch

from PritiMusic.utils.database import is_on_off
from PritiMusic.utils.formatters import time_to_seconds
from PritiMusic import app
import config
from config import LOGGER_ID

STREAM_MODE = False  # True = download local stream | False = direct stream from API
DOWNLOAD_DIR = "downloads"
LOGGER = logging.getLogger(__name__)

# ======================================================================
# 🌐 API CONFIGURATIONS (SOURCE-HOPPING)
# ======================================================================

# 1. BabiesIQ API (Primary)
BABIESIQ_API_URL = os.getenv("BABIESIQ_API_URL", "https://api.babiesiq.tech")
BABIESIQ_API_KEY = os.getenv("BABIESIQ_API_KEY", "ADMINBABYX_BE1B36999F84D14C6DAF231FA4768710577EC9A1")

# 2. Apixhub API (Secondary)
APIXHUB_API_URL = os.getenv("APIXHUB_API_URL", "https://bot.apixhub.fun")
APIXHUB_API_KEY = os.getenv("APIXHUB_API_KEY", "OijUY78533DPoPnOkwIK7qImQk")

# 3. Worker API (Tertiary)
WORKER_FALLBACK_API_URL = os.getenv("WORKER_FALLBACK_API_URL", "https://youtubenewapi.skybotsdeveloper.workers.dev")
WORKER_FALLBACK_API_KEY = os.getenv("WORKER_FALLBACK_API_KEY", "itsmesid")

# 4. Shruti API (Quaternary)
API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsC0WH1GowF2HkGoKv4F3y")

# ======================================================================
# 🛠️ NATIVE UTILITIES (COOKIE & SECURITY)
# ======================================================================

def safe_yt_shell(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        allowed = (
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        )
        if not any(domain in p.netloc for domain in allowed):
            return False
        if any(x in url for x in [";", "|", "$", "`", "\n", "\r"]):
            return False
        return True
    except Exception:
        return False

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir):
        return None
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        return None
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

async def check_file_size(link):
    if not safe_yt_shell(link):
        return None

    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        if not cookie_file:
            print("No cookies found. Cannot check file size.")
            return None
            
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

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

async def _async_run(func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# ======================================================================
# 🚀 HOPPING DOWNLOADERS
# ======================================================================

async def babiesiq_download(video_id: str, download_type: str, title: str = None) -> str:
    if not BABIESIQ_API_URL or not BABIESIQ_API_KEY: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, f"biq_{video_id}")
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path

    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "url": video_id, 
                "type": "audio" if download_type == "audio" else "video", 
                "api_key": BABIESIQ_API_KEY,
                "stream": "false"
            }
            async with session.get(f"{BABIESIQ_API_URL}/download", params=params, timeout=600) as resp:
                if resp.status != 200: return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SUCCESS: Downloaded '{title}' from BabiesIQ!")
            return file_path
        return None
    except Exception: return None

async def apixhub_download(video_id: str, download_type: str, title: str = None) -> str:
    if not APIXHUB_API_URL or not APIXHUB_API_KEY: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, f"apix_{video_id}")
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path

    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "url": video_id, 
                "type": "audio" if download_type == "audio" else "video", 
                "api_key": APIXHUB_API_KEY,
                "stream": "false" 
            }
            async with session.get(f"{APIXHUB_API_URL}/download", params=params, timeout=600) as resp:
                if resp.status != 200: return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SUCCESS: Downloaded '{title}' from Apixhub!")
            return file_path
        return None
    except Exception: return None

async def worker_api_download(video_id: str, download_type: str, title: str = None) -> str:
    if not WORKER_FALLBACK_API_URL or not WORKER_FALLBACK_API_KEY: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, f"wk_{video_id}")
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path

    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "url": video_id, 
                "type": "audio" if download_type == "audio" else "video", 
                "api_key": WORKER_FALLBACK_API_KEY,
                "stream": "false"
            }
            async with session.get(f"{WORKER_FALLBACK_API_URL}/download", params=params, timeout=600) as resp:
                if resp.status != 200: return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SUCCESS: Downloaded '{title}' from Worker API!")
            return file_path
        return None
    except Exception: return None

async def api_download(video_id: str, download_type: str, title: str = None) -> str:
    if not API_URL or not API_KEY: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, video_id)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path

    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "url": video_id, 
                "type": "audio" if download_type == "audio" else "video", 
                "api_key": API_KEY,
                "stream": "false" 
            }
            async with session.get(f"{API_URL}/download", params=params, timeout=600) as resp:
                if resp.status != 200: return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SUCCESS: Downloaded '{title}' from Shruti API!")
            return file_path
        return None
    except Exception: return None

async def ytdl_fallback_download(link: str, download_type: str, title: str = None) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    video_id = extract_video_id(link)
    filename = get_safe_filename(title, video_id)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path

    video_format = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    cookie_file = cookie_txt_file()
    
    ydl_opts = {
        'format': video_format if download_type == "video" else 'bestaudio/best', 
        'outtmpl': file_path,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': ['player_client=ios,tv_embedded']}, 
        'geo_bypass': True,
        'nocheckcertificate': True,
        'noplaylist': True,
    }
    if cookie_file: ydl_opts['cookiefile'] = cookie_file
    
    if download_type == "audio":
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

    try:
        await _async_run(yt_dlp.YoutubeDL(ydl_opts).download, [link])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            LOGGER.info(f"🟢 SUCCESS: Downloaded '{title}' from yt-dlp!")
            return file_path
        return None
    except Exception: return None

async def spotify_fallback_download(title: str) -> str:
    if not title: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|video|audio|lyric', '', title, flags=re.IGNORECASE).strip()
    filename = get_safe_filename(clean_title, f"sp_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    try:
        async with aiohttp.ClientSession(timeout=15) as session:
            async with session.get(f"https://api.spotifydown.com/search?q={clean_title}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("tracks"):
                        best_track_url = data["tracks"][0].get("downloadUrl") 
                        if best_track_url:
                            async with session.get(best_track_url) as song_resp:
                                if song_resp.status == 200:
                                    with open(file_path, "wb") as f:
                                        async for chunk in song_resp.content.iter_chunked(131072): f.write(chunk)
                                    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path
    except Exception: pass
    return None

async def jiosaavn_fallback_download(title: str) -> str:
    if not title: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|video|audio|lyric', '', title, flags=re.IGNORECASE).strip()
    filename = get_safe_filename(clean_title, f"js_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    try:
        async with aiohttp.ClientSession(timeout=15) as session:
            async with session.get(f"{getattr(config, 'JIOSAAVN_API', 'https://saavn.dev/api/search/songs?query=')}{clean_title}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data", {}).get("results"):
                        download_urls = data["data"]["results"][0].get("downloadUrl", [])
                        if download_urls:
                            async with session.get(download_urls[-1]["url"]) as song_resp:
                                if song_resp.status == 200:
                                    with open(file_path, "wb") as f:
                                        async for chunk in song_resp.content.iter_chunked(131072): f.write(chunk)
                                    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path
    except Exception: pass
    return None

async def soundcloud_fallback_download(title: str) -> str:
    if not title: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|video|audio|lyric', '', title, flags=re.IGNORECASE).strip()
    filename = get_safe_filename(clean_title, f"sc_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best', 'outtmpl': file_path, 'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    }
    try:
        await _async_run(yt_dlp.YoutubeDL(ydl_opts).download, [f"scsearch1:{clean_title}"])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000: return file_path
    except Exception: pass
    return None

# ======================================================================
# 🚀 MASTER DOWNLOAD ROUTERS
# ======================================================================

async def download_song(link: str, title: str = None) -> str:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3: return None
    if not title:
        try:
            search = VideosSearch(video_id, limit=1)
            res = await search.next()
            if res and res.get("result"): title = res["result"][0]["title"]
        except Exception: pass

    res = await babiesiq_download(video_id, "audio", title)
    if res: return res
    
    LOGGER.warning(f"🔴 BabiesIQ failed. Hopping to Apixhub API...")
    res = await apixhub_download(video_id, "audio", title)
    if res: return res

    LOGGER.warning(f"🔴 Apixhub failed. Hopping to Worker API...")
    res = await worker_api_download(video_id, "audio", title)
    if res: return res

    LOGGER.warning(f"🔴 Worker failed. Hopping to Shruti API...")
    res = await api_download(video_id, "audio", title)
    if res: return res
    
    LOGGER.warning(f"🔴 Shruti failed. Hopping to yt-dlp...")
    res = await ytdl_fallback_download(link, "audio", title)
    if res: return res
    
    if title:
        LOGGER.warning(f"🔴 YouTube blocked. Hopping to Spotify...")
        res = await spotify_fallback_download(title)
        if res: return res

        LOGGER.warning(f"🔴 Spotify failed. Hopping to JioSaavn...")
        res = await jiosaavn_fallback_download(title)
        if res: return res

        LOGGER.warning(f"🔴 JioSaavn failed. Hopping to SoundCloud...")
        res = await soundcloud_fallback_download(title)
        if res: return res

    return None

async def download_video(link: str, title: str = None) -> str:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3: return None
    if not title:
        try:
            search = VideosSearch(video_id, limit=1)
            res = await search.next()
            if res and res.get("result"): title = res["result"][0]["title"]
        except: pass

    res = await babiesiq_download(video_id, "video", title)
    if res: return res

    LOGGER.warning(f"🔴 BabiesIQ failed. Hopping to Apixhub API...")
    res = await apixhub_download(video_id, "video", title)
    if res: return res

    LOGGER.warning(f"🔴 Apixhub failed. Hopping to Worker API...")
    res = await worker_api_download(video_id, "video", title)
    if res: return res

    LOGGER.warning(f"🔴 Worker failed. Hopping to Shruti API...")
    res = await api_download(video_id, "video", title)
    if res: return res
    
    LOGGER.warning(f"🔴 Shruti failed. Hopping to yt-dlp...")
    return await ytdl_fallback_download(link, "video", title)

# ======================================================================
# 🎵 YOUTUBE API CLASS
# ======================================================================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        if not safe_yt_shell(link):
            return 0, "Invalid or unsafe URL."
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
        except Exception as e:
            print(f"Video API failed: {e}")
        
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return 0, "No cookies found. Cannot download video."
            
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        if not safe_yt_shell(link):
            return []
            
        cookie_file = cookie_txt_file()
        args = ["yt-dlp", "-i", "--get-id", "--flat-playlist"]
        if cookie_file:
            args.extend(["--cookies", cookie_file])
        args.extend(["--playlist-end", str(limit), "--skip-download", link])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        playlist_data = stdout.decode("utf-8")
        
        try:
            result = playlist_data.split("\n")
            result = [key for key in result if key.strip() != ""]
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)

        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]

        clean_title = title.strip()
        if len(clean_title) > 14:
            clean_title = clean_title[:14].rstrip() + "...."

        track_details = {
            "title": clean_title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }

        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        if not safe_yt_shell(link):
            return [], link

        cookie_file = cookie_txt_file()
        if not cookie_file:
            return [], link
            
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_file}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
            
        if not safe_yt_shell(link):
            return None, None

        loop = asyncio.get_running_loop()
        
        if songvideo or songaudio:
            fpath = await download_song(link, title)
            if not fpath:
                vid_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link.split("/")[-1]
                fpath = f"downloads/{vid_id}.mp3"
            return fpath
            
        elif video:
            try:
                downloaded_file = await download_video(link, title)
                if downloaded_file:
                    return downloaded_file, True
            except Exception as e:
                print(f"Video API failed: {e}")
            
            cookie_file = cookie_txt_file()
            if not cookie_file:
                return None, None
                
            if await is_on_off(1):
                direct = True
                downloaded_file = await download_song(link, title)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookie_file,
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = False
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        return None, None
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        return None, None
                    direct = True
                    
                    def video_dl():
                        ydl_optssx = {
                            "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                            "outtmpl": "downloads/%(id)s.%(ext)s",
                            "geo_bypass": True,
                            "nocheckcertificate": True,
                            "quiet": True,
                            "cookiefile" : cookie_file,
                            "no_warnings": True,
                        }
                        x = yt_dlp.YoutubeDL(ydl_optssx)
                        info = x.extract_info(link, False)
                        xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                        if os.path.exists(xyz): return xyz
                        x.download([link])
                        return xyz
                        
                    downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            downloaded_file = await download_song(link, title)
            
        return downloaded_file, direct
