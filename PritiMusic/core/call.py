import asyncio
import os
import random
import logging
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

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
# 🛑 GLOBAL ERROR BYPASS
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

autoend = {}
counter = {}

FORCE_JOIN_LINKS = [
    "https://t.me/betabot_hub",
    "https://t.me/betabot_support",
]

# ==========================================
# 🎧 DOLBY-LIKE SWEET SOUND EQ PARAMETERS
# ==========================================
# Yeh filter clarity badhayega, stereo wide karega aur bass/treble sweet karega
DOLBY_EQ = "-af \"crystalizer=i=1.5,extrastereo=m=1.3,bass=g=4:f=110:w=0.3,treble=g=2:f=8000:w=0.5\""

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

    async def _safe_change_stream(self, client, chat_id, file_path, video=False, extra_args=""):
        # Combine existing extra_args (like seek offsets) with our Dolby EQ
        final_args = f"{extra_args} {DOLBY_EQ}".strip() if extra_args else DOLBY_EQ
        
        if not video:
            stream = MediaStream(file_path, audio_parameters=AudioQuality.HIGH, ffmpeg_parameters=final_args)
            await client.play(chat_id, stream)
            return

        try: 
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.HD_720p, 
                ffmpeg_parameters=final_args
            )
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).warning(f"720p Change Stream failed, auto-switching to 480p: {e}")
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.SD_480p, 
                ffmpeg_parameters=final_args
            )
            await client.play(chat_id, stream)

    async def _safe_join_call(self, assistant_to_join, chat_id, file_path, video=False):
        if not video:
            stream = MediaStream(file_path, audio_parameters=AudioQuality.HIGH, ffmpeg_parameters=DOLBY_EQ)
            return await assistant_to_join.play(chat_id, stream)

        try: 
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.HD_720p,
                ffmpeg_parameters=DOLBY_EQ
            )
            await assistant_to_join.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).warning(f"720p Join Call failed, auto-switching to 480p: {e}")
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.SD_480p,
                ffmpeg_parameters=DOLBY_EQ
            )
            await assistant_to_join.play(chat_id, stream)

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
        except Exception as e: 
            raise AssistantErr(f"VC Error: {e} - (Please check if Voice Chat is turned on in the group)")
        
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

    # ==========================================
    # 🟢 FULLY RESTORED & SYNCED CHANGE_STREAM 🟢
    # ==========================================
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
            
            # --- AUTOPLAY LOGIC ---
            if not check:
                from PritiMusic.utils.database.autoplay import is_autoplay_group
                auto_on = await is_autoplay_group(chat_id)
                if auto_on and popped:
                    LOGGER(__name__).info(f"Autoplay searching next song for {chat_id}")
                    raw_title = popped.get("title", "Popular Music")
                    last_vidid = str(popped.get("vidid", ""))

                    try:
                        recommendation = await YouTube.autoplay(last_vidid=last_vidid, title=str(raw_title), max_duration=900)
                        if recommendation:
                            db[chat_id].append({
                                "title": str(recommendation.get("title", "Unknown Title")),
                                "dur": recommendation.get("duration_min", "0:00"),
                                "streamtype": popped.get("streamtype", "audio") if popped else "audio",
                                "by": "Autoplay 🟢",
                                "user_id": 0,
                                "chat_id": chat_id,
                                "file": f"vid_{recommendation.get('vidid', '')}",
                                "vidid": str(recommendation.get("vidid", "")),
                                "seconds": recommendation.get("duration_sec", 0),
                                "old_dur": recommendation.get("duration_min", "0:00"),
                                "old_second": 0,
                                "played": 0,
                                "client": popped.get("client", app)
                            })
                    except Exception as e:
                        LOGGER(__name__).warning(f"Autoplay fallback failed: {e}")

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

        # --- STREAM & UI UPDATE LOGIC ---
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
        if config.STRING1: pings.append(self.one.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1: await self.one.start()

    async def decorators(self):
        @self.one.on_update()
        async def stream_handler(client, update):
            try:
                c_id = getattr(update, "chat_id", None)
                if not c_id: return
                
                t_name = type(update).__name__
                if "ChatUpdate" in t_name:
                    status = str(getattr(update, "status", "")).upper()
                    if "KICKED" in status or "LEFT" in status or "CLOSED" in status:
                        await self.stop_stream(c_id)
                elif "StreamEnd" in t_name:
                    await self.change_stream(client, c_id)
            except Exception as e:
                LOGGER(__name__).error(f"Stream handler error: {e}")

Lucky = Call()
