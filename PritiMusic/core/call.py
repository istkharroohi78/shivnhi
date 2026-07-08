import asyncio
import os
import random
import logging
import time
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram import Client
from pyrogram.enums import ChatType, ButtonStyle
from pyrogram.errors import ChatAdminRequired
from pyrogram.handlers import RawUpdateHandler
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.functions.messages import GetFullChat
from pyrogram.raw.types import PeerUser, UpdateGroupCallParticipants
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import config
from strings import get_string
# from PritiMusic.utils.logger import autoplay_log # If you don't have this, comment it out
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

from PritiMusic.utils.inline.play import stream_markup
from PritiMusic.utils.stream.autoclear import auto_clean
# from PritiMusic.utils.stream.cards import schedule_stream_card # Use app.send_photo instead if missing
from PritiMusic.utils.thumbnails import get_thumb

autoend = {}
counter = {}
vc_join_monitors = {}
vc_join_snapshots = {}
vc_join_targets = {}
vc_join_call_map = {}
vc_join_event_cache = {}
vc_join_notice_cache = {}

# 🟢 LATEST ntgcalls SAFE MEDIA STREAM
def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    if not path:
        raise TypeError("Argument 'path' cannot be None or empty.")
    
    base_ffmpeg = "-threads 1"
    final_ffmpeg = f"{base_ffmpeg} {ffmpeg_params}".strip() if ffmpeg_params else base_ffmpeg

    kwargs = {
        "media_path": path,
        "audio_parameters": AudioQuality.MEDIUM if video else AudioQuality.HIGH,
        "ffmpeg_parameters": final_ffmpeg,
    }
    
    if video:
        kwargs["video_parameters"] = VideoQuality.SD_360p
    
    return MediaStream(**kwargs)

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        if isinstance(popped, list):
            for track in popped:
                try:
                    await auto_clean(track)
                except Exception:
                    pass
        else:
            try:
                await auto_clean(popped)
            except Exception:
                pass
                
    db[chat_id] = []
    for call_id, info in list(vc_join_call_map.items()):
        if info.get("chat_id") == chat_id:
            vc_join_call_map.pop(call_id, None)
    task = vc_join_monitors.pop(chat_id, None)
    if task and not task.done():
        task.cancel()
    vc_join_snapshots.pop(chat_id, None)
    vc_join_targets.pop(chat_id, None)
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

class Call:
    def __init__(self):
        # 🟢 SAFE CONFIG CHECK (Fix for AttributeError: 'config' has no attribute 'STRING3')
        str1 = getattr(config, "STRING1", None)
        self.userbot1 = Client(
            "LuckyAss1", api_id=getattr(config, "API_ID", None), api_hash=getattr(config, "API_HASH", None), session_string=str(str1)
        ) if str1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        str2 = getattr(config, "STRING2", None)
        self.two = None
        if str2:
            self.userbot2 = Client(
                "LuckyAss2", api_id=getattr(config, "API_ID", None), api_hash=getattr(config, "API_HASH", None), session_string=str(str2)
            )
            self.two = PyTgCalls(self.userbot2)

        str3 = getattr(config, "STRING3", None)
        self.three = None
        if str3:
            self.userbot3 = Client(
                "LuckyAss3", api_id=getattr(config, "API_ID", None), api_hash=getattr(config, "API_HASH", None), session_string=str(str3)
            )
            self.three = PyTgCalls(self.userbot3)

        str4 = getattr(config, "STRING4", None)
        self.four = None
        if str4:
            self.userbot4 = Client(
                "LuckyAss4", api_id=getattr(config, "API_ID", None), api_hash=getattr(config, "API_HASH", None), session_string=str(str4)
            )
            self.four = PyTgCalls(self.userbot4)

        str5 = getattr(config, "STRING5", None)
        self.five = None
        if str5:
            self.userbot5 = Client(
                "LuckyAss5", api_id=getattr(config, "API_ID", None), api_hash=getattr(config, "API_HASH", None), session_string=str(str5)
            )
            self.five = PyTgCalls(self.userbot5)

        self.active_calls: set[int] = set()
        self._stream_locks: dict[int, asyncio.Lock] = {}

    def _get_stream_lock(self, chat_id: int) -> asyncio.Lock:
        lock = self._stream_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._stream_locks[chat_id] = lock
        return lock

    async def _resolve_vc_call_id(self, chat_id: int) -> int | None:
        try:
            chat = await app.get_chat(chat_id)
        except Exception:
            return None

        try:
            if chat.type in {ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.FORUM}:
                full = await app.invoke(
                    GetFullChannel(channel=await app.resolve_peer(chat_id))
                )
            else:
                full = await app.invoke(GetFullChat(chat_id=abs(int(chat_id))))
        except Exception:
            return None

        call = getattr(getattr(full, "full_chat", None), "call", None)
        if not call:
            return None
        return int(call.id)

    @staticmethod
    def _extract_user_id_from_peer(peer) -> int | None:
        if isinstance(peer, PeerUser):
            return int(peer.user_id)
        return None

    @staticmethod
    def _remember_join_event(call_id: int, user_id: int, date: int, source: int) -> bool:
        now = time.monotonic()
        for key, stamp in list(vc_join_event_cache.items()):
            if now - stamp > 30:
                vc_join_event_cache.pop(key, None)

        event_key = (call_id, user_id, date, source, "join")
        if event_key in vc_join_event_cache:
            return False

        vc_join_event_cache[event_key] = now 
        return True
        
    @staticmethod
    def _remember_join_notice(notify_chat_id: int, user_id: int, date: int, source: int) -> bool:
        now = time.monotonic()
        for key, stamp in list(vc_join_notice_cache.items()):
            if now - stamp > 60:
                vc_join_notice_cache.pop(key, None)

        notice_key = (notify_chat_id, user_id, date, source)
        if notice_key in vc_join_notice_cache:
            return False

        vc_join_notice_cache[notice_key] = now
        return True

    async def _fetch_vc_participant_ids(self, chat_id: int) -> set[int]:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        user_ids = set()
        for participant in participants:
            user_id = getattr(participant, "user_id", None)
            if not user_id:
                continue
            user_ids.add(int(user_id))
        return user_ids

    async def _send_vc_join_notice(self, notify_chat_id: int, user_id: int, date: int = 0, source: int = 0) -> None:
        if not self._remember_join_notice(notify_chat_id, user_id, date, source):
            return

        try:
            user = await app.get_users(user_id)
            name = " ".join(part for part in [user.first_name, user.last_name] if part).strip() or user.username or "Unknown User"
            username = f" (@{user.username})" if user.username else ""
        except Exception:
            name = "Unknown User"
            username = ""

        await app.send_message(notify_chat_id, f"Joined VC\nName: {name}{username}\nUser ID: <code>{user_id}</code>")

    async def _handle_group_call_participants_update(self, update: UpdateGroupCallParticipants) -> None:
        call_id = int(update.call.id)
        mapping = vc_join_call_map.get(call_id)
        if not mapping:
            return

        notify_chat_id = mapping["notify_chat_id"]

        member_snapshot = vc_join_snapshots.setdefault(mapping["chat_id"], set())

        for participant in update.participants:
            user_id = self._extract_user_id_from_peer(getattr(participant, "peer", None))
            if not user_id: continue

            if getattr(participant, "left", False):
                member_snapshot.discard(user_id)
                continue

            if not getattr(participant, "just_joined", False): continue

            if user_id in member_snapshot: continue

            if not self._remember_join_event(call_id, user_id, int(getattr(participant, "date", 0) or 0), int(getattr(participant, "source", 0) or 0)):
                continue

            member_snapshot.add(user_id)
            await self._send_vc_join_notice(notify_chat_id, user_id, int(getattr(participant, "date", 0) or 0), int(getattr(participant, "source", 0) or 0))

    async def _vc_join_monitor_loop(self, chat_id: int, notify_chat_id: int) -> None:
        try:
            while True:
                try:
                    current_ids = await self._fetch_vc_participant_ids(chat_id)
                except Exception:
                    await asyncio.sleep(1)
                    continue

                previous_ids = vc_join_snapshots.get(chat_id)
                if previous_ids is None:
                    vc_join_snapshots[chat_id] = current_ids
                    await asyncio.sleep(1)
                    continue

                joined_ids = current_ids - previous_ids
                for user_id in joined_ids:
                    try:
                        await self._send_vc_join_notice(notify_chat_id, user_id)
                    except Exception:
                        continue

                vc_join_snapshots[chat_id] = current_ids
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        finally:
            task = vc_join_monitors.get(chat_id)
            if task and task is asyncio.current_task():
                vc_join_monitors.pop(chat_id, None)

    async def maybe_start_vc_join_notifier(self, chat_id: int, notify_chat_id: int) -> bool:
        call_id = await self._resolve_vc_call_id(chat_id)
        vc_join_targets[chat_id] = notify_chat_id
        if call_id:
            vc_join_call_map[call_id] = {"chat_id": chat_id, "notify_chat_id": notify_chat_id}

        if chat_id not in vc_join_snapshots:
            try:
                vc_join_snapshots[chat_id] = await self._fetch_vc_participant_ids(chat_id)
            except Exception:
                vc_join_snapshots[chat_id] = set()

        existing = vc_join_monitors.get(chat_id)
        if not existing or existing.done():
            vc_join_monitors[chat_id] = asyncio.create_task(self._vc_join_monitor_loop(chat_id, notify_chat_id))
        return True

    async def stop_vc_join_notifier(self, chat_id: int) -> None:
        task = vc_join_monitors.pop(chat_id, None)
        if task and not task.done(): task.cancel()
        vc_join_snapshots.pop(chat_id, None)
        vc_join_targets.pop(chat_id, None)
        for call_id, info in list(vc_join_call_map.items()):
            if info.get("chat_id") == chat_id:
                vc_join_call_map.pop(call_id, None)

    async def _play_stream(self, assistant: PyTgCalls, chat_id: int, stream: MediaStream) -> None:
        async with self._get_stream_lock(chat_id):
            for attempt in range(2):
                try:
                    await assistant.play(chat_id, stream)
                    return
                except OSError as err:
                    if err.errno != 24 or attempt == 1: raise
                    LOGGER(__name__).warning("Retrying stream play for chat %s after hitting open-file limit.", chat_id)
                    await asyncio.sleep(1)

    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await self.stop_vc_join_notifier(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls: return
        try: await assistant.leave_call(chat_id)
        except Exception: pass
        finally: self.active_calls.discard(chat_id)

    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await self.stop_vc_join_notifier(chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except (IndexError, KeyError): pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls: return
        try: await assistant.leave_call(chat_id)
        except Exception: pass
        finally: self.active_calls.discard(chat_id)

    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        if not link:
            LOGGER(__name__).warning(f"skip_stream received None/empty link for chat: {chat_id}")
            return
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        await self._play_stream(assistant, chat_id, stream)

    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not getattr(p, "is_muted", False)]

    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        if not file_path: return
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await self._play_stream(assistant, chat_id, stream)

    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            args = [
                "ffmpeg", "-i", file_path, "-filter:v", f"setpts={vs}*PTS",
                "-filter:a", f"atempo={speed}", out,
            ]
            proc = await asyncio.create_subprocess_exec(
                *args, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        try: loop = asyncio.get_running_loop()
        except: loop = asyncio.get_event_loop()
        dur = int(await loop.run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await self._play_stream(assistant, chat_id, stream)

        db[chat_id][0].update({
            "played": con_seconds, "dur": duration_min, "seconds": dur,
            "speed_path": out, "speed": speed,
            "old_dur": db[chat_id][0].get("dur"), "old_second": db[chat_id][0].get("seconds"),
        })

    async def stream_call(self, link: str) -> None:
        if not link: return
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await self._play_stream(assistant, config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try: await assistant.leave_call(config.LOGGER_ID)
            except: pass

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        if not link: raise AssistantErr("Stream link path cannot be empty.")
        assistant = await group_assistant(self, chat_id)
        
        try:
            lang = await get_lang(chat_id)
            _ = get_string(lang)
        except:
            _ = get_string("en")

        stream = dynamic_media_stream(path=link, video=bool(video))

        try:
            await self._play_stream(assistant, chat_id, stream)
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {e}")
            
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)
        await self.maybe_start_vc_join_notifier(chat_id, original_chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try: await client.leave_call(chat_id)
                    except: pass
                    finally: self.active_calls.discard(chat_id)
                return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            queued = check[0]["file"]
            try:
                language = await get_lang(chat_id)
                _ = get_string(language)
            except:
                _ = get_string("en")
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            requester_id = check[0].get("user_id")
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0

            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            video = True if str(streamtype) == "video" else False

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0 or not link: return await app.send_message(original_chat_id, text=_["call_6"])
                stream = dynamic_media_stream(path=link, video=video)
                try: await self._play_stream(client, chat_id, stream)
                except Exception: return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                try:
                    img = await get_thumb(videoid, requester_id, app) or get_random_img(config.PLAYLIST_IMG_URL)
                    run = await app.send_photo(
                        original_chat_id, photo=img,
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except: pass

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                file_path = None
                try:
                    file_path, direct = await YouTube.download(videoid, mystic, video=video, videoid=vidid)
                except Exception as download_err:
                    LOGGER(__name__).error(f"YouTube extraction failed: {download_err}")

                if not file_path:
                    try: await mystic.edit_text("❌ Download failed. Skipping track...")
                    except: pass
                    return await self.play(client, chat_id)

                stream = dynamic_media_stream(path=file_path, video=video)
                try: await self._play_stream(client, chat_id, stream)
                except: return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                try: await mystic.delete()
                except: pass
                
                try:
                    img = await get_thumb(videoid, requester_id, app) or get_random_img(config.PLAYLIST_IMG_URL)
                    run = await app.send_photo(
                        original_chat_id, photo=img,
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
                except: pass

            elif "index_" in queued:
                stream = dynamic_media_stream(path=videoid, video=video)
                try: await self._play_stream(client, chat_id, stream)
                except: return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                try:
                    run = await app.send_photo(
                        chat_id=original_chat_id, photo=config.STREAM_IMG_URL,
                        caption=_["stream_2"].format(user), reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                except: pass

            else:
                stream = dynamic_media_stream(path=queued, video=video)
                try: await self._play_stream(client, chat_id, stream)
                except: return await app.send_message(original_chat_id, text=_["call_6"])

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                            caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"
                    except: pass
                elif videoid in ["soundcloud", "spotify", "apple", "jiosaavn"]:
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id, photo=config.SOUNCLOUD_IMG_URL,
                            caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"
                    except: pass
                else:
                    button = stream_markup(_, chat_id)
                    try:
                        img = await get_thumb(videoid, requester_id, app) or get_random_img(config.PLAYLIST_IMG_URL)
                        run = await app.send_photo(
                            original_chat_id, photo=img,
                            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                            reply_markup=InlineKeyboardMarkup(button)
                        )
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "stream"
                    except: pass

    async def ping(self) -> str:
        pings = []
        if getattr(config, "STRING1", None): pings.append(self.one.ping)
        if getattr(config, "STRING2", None): pings.append(self.two.ping)
        if getattr(config, "STRING3", None): pings.append(self.three.ping)
        if getattr(config, "STRING4", None): pings.append(self.four.ping)
        if getattr(config, "STRING5", None): pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        if getattr(config, "STRING1", None): await self.one.start()
        if getattr(config, "STRING2", None): await self.two.start()
        if getattr(config, "STRING3", None): await self.three.start()
        if getattr(config, "STRING4", None): await self.four.start()
        if getattr(config, "STRING5", None): await self.five.start()

    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))
        raw_clients = list(filter(None, [app, getattr(self, "userbot1", None), getattr(self, "userbot2", None), getattr(self, "userbot3", None), getattr(self, "userbot4", None), getattr(self, "userbot5", None)]))

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
            | ChatUpdate.Status.DISCARDED_CALL
            | ChatUpdate.Status.BUSY_CALL
        )

        async def unified_update_handler(client, update: Update) -> None:
            try:
                if isinstance(update, ChatUpdate):
                    status = update.status
                    if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                        await self.stop_stream(update.chat_id)
                        return
                elif isinstance(update, StreamEnded):
                    if update.stream_type == StreamEnded.Type.AUDIO:
                        assistant = await group_assistant(self, update.chat_id)
                        await self.play(assistant, update.chat_id)
            except Exception as e:
                LOGGER(__name__).error(f"Stream Update Error: {e}")

        async def raw_group_call_handler(client, update, users, chats) -> None:
            try:
                if isinstance(update, UpdateGroupCallParticipants):
                    await self._handle_group_call_participants_update(update)
            except Exception as e:
                LOGGER(__name__).error(f"VC Notify Error: {e}")

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)
        for raw_client in raw_clients:
            raw_client.add_handler(RawUpdateHandler(raw_group_call_handler), group=99)

Lucky = Call()
