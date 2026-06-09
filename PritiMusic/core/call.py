import asyncio
import os
import random
import logging
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    TelegramServerError,
)
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import (
    HighQualityAudio, 
    HighQualityVideo, 
    MediumQualityVideo, 
    LowQualityVideo
)
from pytgcalls.types.stream import StreamAudioEnded
from pyrogram.enums import ParseMode

import config
from PritiMusic import LOGGER, YouTube, app
from PritiMusic.misc import db
from PritiMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from PritiMusic.utils.exceptions import AssistantErr
from PritiMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from PritiMusic.utils.inline.play import stream_markup, telegram_markup
from PritiMusic.utils.stream.autoclear import auto_clean
from strings import get_string
from PritiMusic.utils.thumbnails import get_thumb

# ==========================================
# 🛑 GLOBAL ERROR BYPASS FOR CLONES
# ==========================================
def handle_asyncio_exceptions(loop, context):
    msg = context.get("exception", context.get("message"))
    msg_str = str(msg)
    if "GROUPCALL_FORBIDDEN" in msg_str or "SetVideoCallStatus" in msg_str or "GROUPCALL_INVALID" in msg_str:
        pass 
    else:
        logging.getLogger("asyncio").error(f"Unhandled Asyncio Error: {msg}")

try:
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_asyncio_exceptions)
except Exception:
    pass
# ==========================================

autoend = {}
counter = {}

FORCE_JOIN_LINKS = [
    "https://t.me/betabot_hub",
    "https://t.me/betabot_support",
]

def get_random_img(img_list):
    if img_list:
        if isinstance(img_list, list):
            return random.choice(img_list)
        return img_list
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg" 

async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="LuckyAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(
            self.userbot1,
            cache_duration=100,
        )
        self.custom_assistants = {} 
        self.active_clients = {} 

    # 🎵 HELPER: HIGH QUALITY AUDIO + 1080->720->480 VIDEO FALLBACK FOR CHANGE_STREAM
    async def _safe_change_stream(self, client, chat_id, file_path, video=False, extra_args=""):
        if not video:
            stream = AudioPiped(file_path, audio_parameters=HighQualityAudio(), additional_ffmpeg_parameters=extra_args)
            await client.change_stream(chat_id, stream)
            return

        try: # Try 1080p
            stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=HighQualityVideo(), additional_ffmpeg_parameters=extra_args)
            await client.change_stream(chat_id, stream)
        except Exception:
            try: # Fallback to 720p
                stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo(), additional_ffmpeg_parameters=extra_args)
                await client.change_stream(chat_id, stream)
            except Exception: # Final Fallback to 480p
                stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=LowQualityVideo(), additional_ffmpeg_parameters=extra_args)
                await client.change_stream(chat_id, stream)

    # 🎵 HELPER: HIGH QUALITY AUDIO + 1080->720->480 VIDEO FALLBACK FOR JOIN_CALL
    async def _safe_join_call(self, assistant_to_join, chat_id, file_path, video=False):
        if not video:
            stream = AudioPiped(file_path, audio_parameters=HighQualityAudio())
            return await assistant_to_join.join_group_call(chat_id, stream, stream_type=StreamType().pulse_stream)

        try: # Try 1080p
            stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=HighQualityVideo())
            await assistant_to_join.join_group_call(chat_id, stream, stream_type=StreamType().pulse_stream)
        except Exception:
            try: # Fallback to 720p
                stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())
                await assistant_to_join.join_group_call(chat_id, stream, stream_type=StreamType().pulse_stream)
            except Exception: # Final Fallback to 480p
                stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=LowQualityVideo())
                await assistant_to_join.join_group_call(chat_id, stream, stream_type=StreamType().pulse_stream)

    async def get_active_clients(self, chat_id):
        clients = []
        if chat_id in self.active_clients:
            val = self.active_clients[chat_id]
            if isinstance(val, list):
                clients.extend(val)
            else:
                clients.append(val)
        if not clients:
            try:
                main_ass = await group_assistant(self, chat_id)
                clients.append(main_ass)
            except:
                clients.append(self.one)
        return list(set(clients))

    async def pause_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await assistant.pause_stream(chat_id)
            except: pass

    async def resume_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await assistant.resume_stream(chat_id)
            except: pass

    async def stop_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        try: await _clear_(chat_id)
        except: pass
        for assistant in assistants:
            try: await assistant.leave_group_call(chat_id)
            except: pass
        if chat_id in self.active_clients: del self.active_clients[chat_id]

    async def stop_stream_force(self, chat_id: int):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await assistant.leave_group_call(chat_id)
            except: pass
        if chat_id in self.active_clients: del self.active_clients[chat_id]
        try: await _clear_(chat_id)
        except: pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistants = await self.get_active_clients(chat_id)
        assistant = assistants[0] if assistants else self.one
        if str(speed) != str("1.0"):
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == str("0.5"): vs = 2.0
                if str(speed) == str("0.75"): vs = 1.35
                if str(speed) == str("1.5"): vs = 0.68
                if str(speed) == str("2.0"): vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS -filter:a atempo={speed} {out}"),
                    stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
            
        try: loop = asyncio.get_running_loop()
        except RuntimeError: loop = asyncio.get_event_loop()
            
        dur = await loop.run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        
        is_video = playing[0]["streamtype"] == "video"
        extra_args = f"-ss {played} -to {duration}"
        
        if str(db[chat_id][0]["file"]) == str(file_path):
            for assistant in assistants:
                try:
                    await self._safe_change_stream(assistant, chat_id, out, is_video, extra_args)
                except: pass
        else: raise AssistantErr("Umm")
        
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await self._safe_change_stream(assistant, chat_id, link, video)
            except: pass

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistants = await self.get_active_clients(chat_id)
        is_video = mode == "video"
        extra_args = f"-ss {to_seek} -to {duration}"
        for assistant in assistants:
            try: await self._safe_change_stream(assistant, chat_id, file_path, is_video, extra_args)
            except: pass

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await self._safe_join_call(assistant, config.LOGGER_ID, link, video=True)
        await asyncio.sleep(0.2)
        await assistant.leave_group_call(config.LOGGER_ID)

    async def join_call(self, chat_id: int, original_chat_id: int, link, video: Union[bool, str] = None, image: Union[bool, str] = None, userbot=None):
        assistant_to_join = None
        if userbot:
            if FORCE_JOIN_LINKS:
                for link_join in FORCE_JOIN_LINKS:
                    try:
                        await userbot.join_chat(link_join)
                        await asyncio.sleep(0.5) 
                    except: pass
            user_id = userbot.me.id
            if user_id in self.custom_assistants:
                assistant_to_join = self.custom_assistants[user_id]
            else:
                assistant_to_join = PyTgCalls(userbot, cache_duration=100)
                await assistant_to_join.start()
                @assistant_to_join.on_stream_end()
                async def stream_end_handler(client, update: Update):
                    if not isinstance(update, StreamAudioEnded): return
                    await self.change_stream(client, update.chat_id)
                @assistant_to_join.on_kicked()
                @assistant_to_join.on_closed_voice_chat()
                @assistant_to_join.on_left()
                async def stream_services_handler(_, chat_id: int):
                    await self.stop_stream(chat_id)
                self.custom_assistants[user_id] = assistant_to_join
        else:
            assistant_to_join = await group_assistant(self, chat_id)
            
        if chat_id not in self.active_clients:
            self.active_clients[chat_id] = []
        if assistant_to_join not in self.active_clients[chat_id]:
            self.active_clients[chat_id].append(assistant_to_join)
            
        language = await get_lang(chat_id)
        _ = get_string(language)
        
        try:
            await self._safe_join_call(assistant_to_join, chat_id, link, video)
        except NoActiveGroupCall: raise AssistantErr(_["call_8"])
        except AlreadyJoinedError: raise AssistantErr(_["call_9"])
        except TelegramServerError: raise AssistantErr(_["call_10"])
        
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)
        
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant_to_join.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                if check: popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            
            if popped: await auto_clean(popped)
            
            # Autoplay Core Implementation
            if not check:
                from PritiMusic.utils.database.autoplay import is_autoplay_group
                auto_on = await is_autoplay_group(chat_id)
                if auto_on and popped:
                    success = False
                    raw_title = popped.get("title") or "Unknown Title"
                    title_lower = str(raw_title).lower()
                    last_vidid = str(popped.get("vidid") or "")

                    try:
                        lang_pools = {
                            "Hindi": ["hindi single track official video", "bollywood latest lyrical song"],
                            "Punjabi": ["latest punjabi single official video", "punjabi trending track lyrical"],
                            "Bhojpuri": ["bhojpuri latest single video song", "bhojpuri trending song official"],
                            "Haryanvi": ["haryanvi single track official", "latest haryanvi video song"],
                            "Tamil": ["tamil latest single official video", "kollywood trending song lyrical"],
                            "Telugu": ["telugu tollywood latest single song", "telugu lyrical video official"],
                            "English": ["english pop single official music video", "trending english lyrical song"]
                        }
                        keywords_map = {
                            "Punjabi": ["punjabi", "jass", "sidhu", "karan", "diljit", "amrit", "ap dhillon"],
                            "Bhojpuri": ["bhojpuri", "khesari", "pawan", "shilpi", "antra"],
                            "Haryanvi": ["haryanvi", "sapna", "renuka", "gulzaar"],
                            "Tamil": ["tamil", "anirudh", "rahman", "kollywood"],
                            "Telugu": ["telugu", "allu", "ramarao", "tollywood", "dsp"],
                            "English": ["english", "pop song", "taylor swift", "justin bieber"]
                        }
                        detected_lang = "Hindi"
                        for lang, kws in keywords_map.items():
                            if any(kw in title_lower for kw in kws):
                                detected_lang = lang
                                break

                        search_query = random.choice(lang_pools[detected_lang])
                        valid_choices = []

                        try:
                            from youtubesearchpython.__future__ import VideosSearch
                            search = VideosSearch(search_query, limit=15)
                            result = await search.next()
                            if result and result.get("result"):
                                for res in result["result"]:
                                    vidid = str(res.get("id") or "")
                                    if not vidid or vidid == "None" or vidid == last_vidid: continue
                                    next_dur = str(res.get("duration") or "0:00")
                                    dur_sec = 0
                                    if next_dur and ":" in next_dur:
                                        parts = next_dur.split(":")
                                        try:
                                            if len(parts) == 2: dur_sec = int(parts[0]) * 60 + int(parts[1])
                                            elif len(parts) == 3: dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                                        except ValueError: pass
                                    if 30 <= dur_sec <= 900:
                                        valid_choices.append((vidid, str(res.get("title") or "Unknown Title").title(), next_dur, dur_sec))
                        except: pass 

                        if not valid_choices:
                            import yt_dlp
                            loop_e = asyncio.get_event_loop()
                            ytdl_opts = {"quiet": True, "extract_flat": True}
                            ydl = yt_dlp.YoutubeDL(ytdl_opts)
                            r = await loop_e.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch10:{search_query}", download=False))
                            if r and "entries" in r:
                                for entry in r["entries"]:
                                    vidid = entry.get("id")
                                    if not vidid or vidid == last_vidid: continue
                                    raw_dur = entry.get("duration", 0)
                                    try: dur_sec = int(float(raw_dur)) if raw_dur else 0
                                    except (ValueError, TypeError): dur_sec = 0
                                    if not dur_sec or dur_sec < 30 or dur_sec > 900: continue
                                    m, s = divmod(dur_sec, 60)
                                    h, m = divmod(m, 60)
                                    dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                                    valid_choices.append((vidid, str(entry.get("title", "Unknown Title")).title(), dur_str, dur_sec))

                        if valid_choices:
                            chosen_tuple = random.choice(valid_choices)
                            db[chat_id].append({
                                "vidid": chosen_tuple[0],
                                "title": chosen_tuple[1],
                                "by": "Autoplay 🟢",
                                "chat_id": chat_id,
                                "file": f"vid_{chosen_tuple[0]}",
                                "streamtype": "audio", 
                                "user_id": 0,          
                                "seconds": chosen_tuple[3], 
                                "dur": chosen_tuple[2],
                                "old_dur": chosen_tuple[2],
                                "old_second": 0,
                                "client": popped.get("client") if popped else app
                            })
                            success = True
                            try:
                                from PritiMusic.utils.logger import autoplay_log
                                await autoplay_log(app, chat_id, chosen_tuple[1])
                            except: pass
                    except Exception as e:
                        LOGGER(__name__).warning(f"Smart Autoplay Error: {e}")

                    if not success:
                        try:
                            recommendation = await YouTube.autoplay(last_vidid=last_vidid, title=str(raw_title), max_duration=900)
                            if recommendation:
                                db[chat_id].append({
                                    "title": str(recommendation.get("title", "Unknown Title")),
                                    "dur": recommendation.get("duration_min", "0:00"),
                                    "streamtype": popped.get("streamtype", "audio") if popped else "audio",
                                    "by": "Autoplay",
                                    "user_id": 0,
                                    "chat_id": chat_id,
                                    "file": f"vid_{recommendation.get('vidid', '')}",
                                    "vidid": str(recommendation.get("vidid", "")),
                                    "seconds": recommendation.get("duration_sec", 0),
                                    "old_dur": recommendation.get("duration_min", "0:00"),
                                    "old_second": 0,
                                    "played": 0,
                                    "client": popped.get("client") if popped else app
                                })
                        except Exception as e:
                            LOGGER(__name__).warning(f"Native Autoplay fallback failed: {e}")

            if not db.get(chat_id): 
                await _clear_(chat_id)
                if chat_id in self.active_clients: del self.active_clients[chat_id]
                try: await client.leave_group_call(chat_id)
                except: pass
                return

        except Exception as e:
            LOGGER(__name__).error(f"Error in change_stream core: {e}")
            await _clear_(chat_id)
            if chat_id in self.active_clients: del self.active_clients[chat_id]
            try: await client.leave_group_call(chat_id)
            except: pass
            return

        # Play Next Track
        if db.get(chat_id):
            queued = db[chat_id][0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            raw_title = db[chat_id][0].get("title")
            title = str(raw_title).title() if raw_title else "Unknown Title"
            raw_user = db[chat_id][0].get("by")
            user = str(raw_user) if raw_user else "Unknown User"
            user_id = db[chat_id][0].get("user_id", 0) 
            original_chat_id = db[chat_id][0]["chat_id"]
            streamtype = db[chat_id][0]["streamtype"]
            videoid = db[chat_id][0]["vidid"]
            chat_client = db[chat_id][0].get("client") or app

            db[chat_id][0]["played"] = 0
            exis = db[chat_id][0].get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = db[chat_id][0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = True if str(streamtype) == "video" else False
            
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                try: await self._safe_change_stream(client, chat_id, link, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                button = telegram_markup(_, chat_id)
                run = await chat_client.send_photo(
                    chat_id=original_chat_id, photo=get_random_img(config.STREAM_IMG_URL),
                    caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], db[chat_id][0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button)
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
                
            elif "vid_" in queued:
                mystic = await chat_client.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                except:
                    try: file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                    except:
                        try: await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
                        except: pass
                        return await self.change_stream(client, chat_id)
                
                if not file_path or str(file_path) == "None":
                    try: await mystic.edit_text("❌ **Error:** Download failed. Skipping track...")
                    except: pass
                    return await self.change_stream(client, chat_id)

                try: await self._safe_change_stream(client, chat_id, file_path, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                img = await get_thumb(videoid, user_id, chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
                button = stream_markup(_, chat_id)
                try: await mystic.delete()
                except: pass
                
                run = await chat_client.send_photo(
                    chat_id=original_chat_id, photo=img,
                    caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], db[chat_id][0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button)
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
                
            elif "index_" in queued:
                try: await self._safe_change_stream(client, chat_id, videoid, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                button = telegram_markup(_, chat_id)
                run = await chat_client.send_photo(
                    chat_id=original_chat_id, photo=get_random_img(config.STREAM_IMG_URL),
                    caption=_["stream_2"].format(user), reply_markup=InlineKeyboardMarkup(button)
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
                
            else:
                try: await self._safe_change_stream(client, chat_id, queued, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                if videoid == "telegram":
                    button = telegram_markup(_, chat_id)
                    tg_img = get_random_img(config.TELEGRAM_AUDIO_URL) if not video else get_random_img(config.TELEGRAM_VIDEO_URL)
                    run = await chat_client.send_photo(
                        chat_id=original_chat_id, photo=tg_img,
                        caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], db[chat_id][0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                    
                elif videoid == "soundcloud":
                    button = telegram_markup(_, chat_id)
                    run = await chat_client.send_photo(
                        chat_id=original_chat_id, photo=get_random_img(config.SOUNCLOUD_IMG_URL),
                        caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], db[chat_id][0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                    
                else:
                    img = await get_thumb(videoid, user_id, chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
                    button = stream_markup(_, chat_id)
                    run = await chat_client.send_photo(
                        chat_id=original_chat_id, photo=img,
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], db[chat_id][0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        pings = []
        if config.STRING1: pings.append(await self.one.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1: await self.one.start()

    async def decorators(self):
        @self.one.on_kicked()
        @self.one.on_closed_voice_chat()
        @self.one.on_left()
        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

        @self.one.on_stream_end()
        async def stream_end_handler1(client, update: Update):
            if not isinstance(update, StreamAudioEnded): return
            await self.change_stream(client, update.chat_id)

Lucky = Call()
