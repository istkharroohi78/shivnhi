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
DOWNLOAD_DIR = "downloads"
LOGGER = logging.getLogger(__name__)

# --- API 1: Shruti ---
API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsC0WH1GowF2HkGoKv4F3y")

# --- API 2: Xbit ---
YTPROXY_URL = os.getenv("YTPROXY_URL", "https://tgapi.xbitcode.com")
YT_API_KEY = os.getenv("YT_API_KEY" , "xbit_kp3GFnAvdnFVDV3L6xACy-jbVBE5q5Cd")

# --- API 3: Worker ---
WORKER_FALLBACK_API_URL = os.getenv("WORKER_FALLBACK_API_URL", "https://youtubenewapi.skybotsdeveloper.workers.dev")
WORKER_FALLBACK_API_KEY = os.getenv("WORKER_FALLBACK_API_KEY", "itsmesid")

# --- API 4: Inflex (Fixed variable names to avoid overriding API 1) ---
INFLEX_API_URL = os.getenv("INFLEX_API_URL", "https://bot.apixhub.fun")
INFLEX_API_KEY = os.getenv("INFLEX_API_KEY", "OijUY78533DPoPnOkwIK7qImQk")

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

async def _async_run(func, *args, **kwargs):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


# ----------------- DOWNLOADERS -----------------

async def single_api_download(api_name: str, req_url: str, params: dict, final_path: str) -> str:
    """Downloads from a single API. Returns final_path on success, None on error."""
    temp_path = f"{final_path}_{api_name.replace(' ', '')}.tmp"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(req_url, params=params) as resp:
                if resp.status == 200:
                    
                    # 🟢 FIX: Content-Type वाली चेकिंग हटा दी गई है ताकि अगर API गलती से Text/JSON header भेजे तो भी वो डाउनलोड ट्राई करे।
                    
                    with open(temp_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(131072):
                            f.write(chunk)
                    
                    # 🟢 Strict File Size Check: असली गाना/वीडियो 100KB से ऊपर ही होगा।
                    if os.path.exists(temp_path):
                        file_size = os.path.getsize(temp_path)
                        if file_size > 102400:  # 100 KB minimum size
                            if not os.path.exists(final_path): 
                                os.rename(temp_path, final_path)
                                LOGGER.info(f"✅ Success: {api_name} downloaded the file successfully!")
                                return final_path
                        else:
                            LOGGER.warning(f"❌ {api_name} gave an error or invalid file (Size: {file_size} bytes). Shifting to next...")
                            
    except Exception as e:
        LOGGER.error(f"❌ {api_name} failed with error: {e}. Shifting to next...")
    finally:
        # Garbage clear
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
    return None

async def sequential_api_download(video_id: str, download_type: str, title: str) -> str:
    """एक-एक करके API ट्राई करेगा, एरर आने पर ही अगले API पर शिफ्ट होगा।"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = get_safe_filename(title, video_id)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 102400:
        return file_path

    type_param = "audio" if download_type == "audio" else "video"

    # API List (Order के हिसाब से)
    apis_to_try = []
    if API_URL and API_KEY:
        apis_to_try.append(("ShrutiAPI", f"{API_URL}/download", {"url": video_id, "type": type_param, "api_key": API_KEY}))
    if YTPROXY_URL and YT_API_KEY:
        apis_to_try.append(("XbitAPI", f"{YTPROXY_URL}/download", {"url": video_id, "type": type_param, "api_key": YT_API_KEY}))
    if WORKER_FALLBACK_API_URL and WORKER_FALLBACK_API_KEY:
        apis_to_try.append(("WorkerAPI", f"{WORKER_FALLBACK_API_URL}/download", {"url": video_id, "type": type_param, "api_key": WORKER_FALLBACK_API_KEY}))
    if INFLEX_API_URL and INFLEX_API_KEY:
        apis_to_try.append(("InflexAPI", f"{INFLEX_API_URL}/download", {"url": video_id, "type": type_param, "api_key": INFLEX_API_KEY}))

    for api_name, req_url, params in apis_to_try:
        LOGGER.info(f"🔄 Trying API: {api_name}...")
        result = await single_api_download(api_name, req_url, params, file_path)
        if result:
            return result  # अगर फाइल मिल गई तो लूप ब्रेक और रिटर्न
            
    return None  # अगर सारे API फेल हो गए


async def ytdl_fallback_download(link: str, download_type: str, title: str = None) -> str:
    """यह सबसे लास्ट में चलेगा और Cookies का इस्तेमाल करेगा।"""
    LOGGER.info("🔄 All APIs failed. Falling back to yt-dlp (Cookies)...")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    video_id = extract_video_id(link)
    filename = get_safe_filename(title, video_id)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 102400: return file_path

    video_format = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    
    ydl_opts = {
        'format': video_format if download_type == "video" else 'bestaudio/best', 
        'outtmpl': file_path,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies.txt',  
        'extractor_args': {'youtube': ['player_client=ios,tv_embedded']}, 
        'geo_bypass': True,
        'nocheckcertificate': True,
        'noplaylist': True,
    }
    
    if download_type == "audio":
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

    try:
        await _async_run(yt_dlp.YoutubeDL(ydl_opts).download, [link])
        if os.path.exists(file_path) and os.path.getsize(file_path) > 102400:
            LOGGER.info("✅ Success: Downloaded using yt-dlp fallback!")
            return file_path
    except Exception as e:
        LOGGER.error(f"❌ yt-dlp fallback error: {str(e)}")
    return None

async def spotify_fallback_download(title: str) -> str:
    if not title: return None
    LOGGER.info("🔄 yt-dlp failed. Falling back to Spotify...")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|video|audio|lyric', '', title, flags=re.IGNORECASE).strip()
    filename = get_safe_filename(clean_title, f"sp_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(f"https://api.spotifydown.com/search?q={clean_title}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("tracks"):
                        best_track_url = data["tracks"][0].get("downloadUrl") 
                        if best_track_url:
                            async with session.get(best_track_url) as song_resp:
                                if song_resp.status == 200:
                                    with open(file_path, "wb") as f:
                                        async for chunk in song_resp.content.iter_chunked(131072):
                                            f.write(chunk)
                                    if os.path.exists(file_path) and os.path.getsize(file_path) > 102400:
                                        LOGGER.info("✅ Success: Downloaded using Spotify fallback!")
                                        return file_path
    except Exception as e: 
        LOGGER.error(f"❌ Spotify fallback failed: {e}")
    return None

async def jiosaavn_fallback_download(title: str) -> str:
    if not title: return None
    LOGGER.info("🔄 Spotify failed. Falling back to JioSaavn...")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|video|audio|lyric', '', title, flags=re.IGNORECASE).strip()
    filename = get_safe_filename(clean_title, f"js_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(f"{getattr(config, 'JIOSAAVN_API', 'https://saavn.dev/api/search/songs?query=')}{clean_title}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data", {}).get("results"):
                        song_data = data["data"]["results"][0]
                        download_urls = song_data.get("downloadUrl", [])
                        if download_urls:
                            best_url = download_urls[-1]["url"]
                            async with session.get(best_url) as song_resp:
                                if song_resp.status == 200:
                                    with open(file_path, "wb") as f:
                                        async for chunk in song_resp.content.iter_chunked(131072):
                                            f.write(chunk)
                                    if os.path.exists(file_path) and os.path.getsize(file_path) > 102400:
                                        LOGGER.info("✅ Success: Downloaded using JioSaavn fallback!")
                                        return file_path
    except Exception as e:
        LOGGER.error(f"❌ JioSaavn fallback failed: {e}")
    return None

async def soundcloud_fallback_download(title: str) -> str:
    if not title: return None
    LOGGER.info("🔄 JioSaavn failed. Falling back to SoundCloud...")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|video|audio|lyric', '', title, flags=re.IGNORECASE).strip()
    filename = get_safe_filename(clean_title, f"sc_{int(time.time())}")
    file_path = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best', 'outtmpl': file_path, 'quiet': True, 'no_warnings': True, 'noplaylist': True,
        'socket_timeout': 30,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    }
    try:
        await asyncio.wait_for(_async_run(yt_dlp.YoutubeDL(ydl_opts).download, [f"scsearch1:{clean_title}"]), timeout=120)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 102400: 
            LOGGER.info("✅ Success: Downloaded using SoundCloud fallback!")
            return file_path
    except Exception as e:
        LOGGER.error(f"❌ SoundCloud fallback failed: {e}")
    return None

async def download_song(link: str, title: str = None) -> str:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3: return None
        
    if not title:
        try:
            search = VideosSearch(video_id, limit=1)
            res = await asyncio.wait_for(search.next(), timeout=7)
            if res and res.get("result"): title = res["result"][0]["title"]
        except Exception: pass

    # 1. API Sequential Trying
    api_result = await sequential_api_download(video_id, "audio", title)
    if api_result: return api_result

    # 2. yt-dlp Fallback
    yt_result = await ytdl_fallback_download(link, "audio", title)
    if yt_result: return yt_result
    
    # 3. Spotify/Jiosaavn/SoundCloud Fallback
    if title:
        sp_result = await spotify_fallback_download(title)
        if sp_result: return sp_result

        js_result = await jiosaavn_fallback_download(title)
        if js_result: return js_result

        sc_result = await soundcloud_fallback_download(title)
        if sc_result: return sc_result

    return None

async def download_video(link: str, title: str = None) -> str:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3: return None

    if not title:
        try:
            search = VideosSearch(video_id, limit=1)
            res = await asyncio.wait_for(search.next(), timeout=7)
            if res and res.get("result"): title = res["result"][0]["title"]
        except Exception: pass

    api_result = await sequential_api_download(video_id, "video", title)
    if api_result: return api_result

    yt_result = await ytdl_fallback_download(link, "video", title)
    if yt_result: return yt_result

    return None

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
        if message_1.reply_to_message: messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK: return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        try:
            results = VideosSearch(link, limit=1)
            response = await asyncio.wait_for(results.next(), timeout=7)
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
                "quiet": True, "extract_flat": True, "noplaylist": True, "cookiefile": "cookies.txt",
                "extractor_args": {"youtube": ["player_client=ios,tv_embedded"]},
                "socket_timeout": 15 
            } 
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            search_query = link if "youtube.com" in link or "youtu.be" in link else f"ytsearch1:{link}"
            
            r = await asyncio.wait_for(_async_run(ydl.extract_info, search_query, download=False), timeout=20)
            if r and "entries" in r and len(r["entries"]) > 0:
                entry = r["entries"][0]
                vidid = entry.get("id")
                dur_sec = int(entry.get("duration", 0))
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                duration_min = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                return entry.get("title"), duration_min, dur_sec, f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg", vidid
        except Exception:
            pass

        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            res = await asyncio.wait_for(results.next(), timeout=5)
            for result in res["result"]: return result["title"]
        except Exception:
            return "Unknown Title"

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            res = await asyncio.wait_for(results.next(), timeout=5)
            for result in res["result"]: return result["duration"]
        except Exception:
            return "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            results = VideosSearch(link, limit=1)
            res = await asyncio.wait_for(results.next(), timeout=5)
            for result in res["result"]: return result["thumbnails"][0]["url"].split("?")[0]
        except Exception:
            return "https://telegra.ph/file/2e3d368e77c449c287430.jpg"

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file: return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if "&" in link: link = link.split("&")[0]
        try:
            plist = await asyncio.wait_for(_async_run(Playlist.get, link), timeout=15)
        except Exception:
            return []
        
        videos = plist.get("videos") or []
        return [data.get("id") for data in videos[:limit] if data and data.get("id")]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        try:
            results = VideosSearch(link, limit=1)
            response = await asyncio.wait_for(results.next(), timeout=7)
            if response and response.get("result"):
                result = response["result"][0]
                return {
                    "title": result["title"], "link": result["link"], "vidid": result["id"],
                    "duration_min": result["duration"], "thumb": result["thumbnails"][0]["url"].split("?")[0],
                }, result["id"]
        except Exception: pass

        try:
            ydl_opts = {
                "quiet": True, "extract_flat": True, "noplaylist": True, "cookiefile": "cookies.txt",
                "extractor_args": {"youtube": ["player_client=ios,tv_embedded"]},
                "socket_timeout": 15
            }
            ydl = yt_dlp.YoutubeDL(ydl_opts)
            search_query = link if "youtube.com" in link or "youtu.be" in link else f"ytsearch1:{link}"
            r = await asyncio.wait_for(_async_run(ydl.extract_info, search_query, download=False), timeout=20)
            
            if r and "entries" in r and len(r["entries"]) > 0:
                entry = r["entries"][0]
                vidid = entry.get("id")
                dur_sec = int(entry.get("duration", 0))
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                return {
                    "title": entry.get("title"), "link": f"https://www.youtube.com/watch?v={vidid}", "vidid": vidid,
                    "duration_min": f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}", "thumb": f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg",
                }, vidid
        except Exception: pass

        return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        ytdl_opts = {
            "quiet": True, "cookiefile": "cookies.txt", "extractor_args": {"youtube": ["player_client=ios,tv_embedded"]},
            "external_downloader": "aria2c", "socket_timeout": 15,
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M", "--allow-piece-length-change=true"]
        }
        
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        formats_available = []
        
        try:
            r = await asyncio.wait_for(_async_run(ydl.extract_info, link, download=False), timeout=20)
            if r and "formats" in r:
                for format in r["formats"]:
                    try:
                        if "dash" not in str(format.get("format", "")).lower():
                            formats_available.append({
                                "format": format.get("format"), "filesize": format.get("filesize"), "format_id": format.get("format_id"),
                                "ext": format.get("ext"), "format_note": format.get("format_note"), "yturl": link,
                            })
                    except Exception: continue
        except Exception: pass
            
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
            
        try:
            a = VideosSearch(link, limit=10)
            result = (await asyncio.wait_for(a.next(), timeout=7)).get("result")
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
        except Exception:
            return None, False

    async def autoplay(self, last_vidid: str, title: str, max_duration: int = None):
        try:
            import random
            search_query = f"{title} official audio"
            valid_choices = []
            
            try:
                search = VideosSearch(search_query, limit=15)
                result = await asyncio.wait_for(search.next(), timeout=7)
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
                                
                        if dur_sec < 30: continue
                        if max_duration and dur_sec > max_duration: continue
                            
                        valid_choices.append({
                            "vidid": vidid, "title": str(res.get("title", "Unknown Title")).title(),
                            "duration_min": dur_str, "duration_sec": dur_sec
                        })
            except Exception: pass 

            if not valid_choices:
                ytdl_opts = {
                    "quiet": True, "extract_flat": True, "noplaylist": True, "cookiefile": "cookies.txt",
                    "extractor_args": {"youtube": ["player_client=ios,tv_embedded"]},
                    "socket_timeout": 15 
                } 
                ydl = yt_dlp.YoutubeDL(ytdl_opts)
                
                r = await asyncio.wait_for(_async_run(ydl.extract_info, f"ytsearch10:{search_query}", download=False), timeout=20)
                if r and "entries" in r:
                    for entry in r["entries"]:
                        vidid = entry.get("id")
                        if not vidid or vidid == last_vidid: continue
                        
                        raw_dur = entry.get("duration", 0)
                        try: dur_sec = int(float(raw_dur)) if raw_dur else 0
                        except (ValueError, TypeError): dur_sec = 0
                            
                        if not dur_sec or dur_sec < 30: continue
                        if max_duration and dur_sec > max_duration: continue
                            
                        m, s = divmod(dur_sec, 60)
                        h, m = divmod(m, 60)
                        dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                        
                        valid_choices.append({
                            "vidid": vidid, "title": str(entry.get("title", "Unknown Title")).title(),
                            "duration_min": dur_str, "duration_sec": dur_sec
                        })

            if valid_choices: return random.choice(valid_choices)
            return None
            
        except Exception:
            return None

YouTube = YouTubeAPI()
