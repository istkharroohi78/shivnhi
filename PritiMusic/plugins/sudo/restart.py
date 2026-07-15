import asyncio
import os
import shutil
import socket
from datetime import datetime

import urllib3
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from PritiMusic import app

# YAHAN APNE CLONE LIST KO IMPORT KAREIN
try:
    from PritiMusic.core.bot import clones
except ImportError:
    clones = [] 

from PritiMusic.misc import HAPP, SUDOERS, XCB
from PritiMusic.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from PritiMusic.utils.decorators.language import language
from PritiMusic.utils.pastebin import LuckyBin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


async def is_heroku():
    return "heroku" in socket.getfqdn()


@app.on_message(filters.command(["getlog", "logs", "getlogs"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & SUDOERS)
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except:
        await message.reply_text(_["server_1"])


# ---------------- REDEPLOY / UPDATE COMMAND ---------------- #
@app.on_message(filters.command(["update", "gitpull"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & SUDOERS)
@language
async def update_(client, message, _):
    if await is_heroku():
        if HAPP is None:
            return await message.reply_text(_["server_2"])
    
    response = await message.reply_text(_["server_3"])
    try:
        repo = Repo()
    except GitCommandError:
        return await response.edit(_["server_4"])
    except InvalidGitRepositoryError:
        return await response.edit(_["server_5"])
        
    to_exc = f"git fetch origin {config.UPSTREAM_BRANCH} &> /dev/null"
    os.system(to_exc)
    await asyncio.sleep(7)
    verification = ""
    REPO_ = repo.remotes.origin.url.split(".git")[0]
    
    for checks in repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"):
        verification = str(checks.count())
        
    if verification == "":
        return await response.edit(_["server_6"])
        
    updates = ""
    ordinal = lambda format: "%d%s" % (
        format,
        "tsnrhtdd"[(format // 10 % 10 != 1) * (format % 10 < 4) * format % 10 :: 4],
    )
    for info in repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"):
        updates += f"<b>➣ #{info.count()}: <a href={REPO_}/commit/{info}>{info.summary}</a> ʙʏ -> {info.author}</b>\n\t\t\t\t<b>➥ ᴄᴏᴍᴍɪᴛᴇᴅ ᴏɴ :</b> {ordinal(int(datetime.fromtimestamp(info.committed_date).strftime('%d')))} {datetime.fromtimestamp(info.committed_date).strftime('%b')}, {datetime.fromtimestamp(info.committed_date).strftime('%Y')}\n\n"
        
    _update_response_ = "<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n➣ ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n<b><u>ᴜᴩᴅᴀᴛᴇs:</u></b>\n\n"
    _final_updates_ = _update_response_ + updates
    
    if len(_final_updates_) > 4096:
        url = await LuckyBin(updates)
        nrs = await response.edit(
            f"<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n➣ ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n<u><b>ᴜᴩᴅᴀᴛᴇs :</b></u>\n\n<a href={url}>ᴄʜᴇᴄᴋ ᴜᴩᴅᴀᴛᴇs</a>"
        )
    else:
        nrs = await response.edit(_final_updates_, disable_web_page_preview=True)
        
    os.system("git stash &> /dev/null && git pull")

    try:
        served_chats = await get_active_chats()
        for x in served_chats:
            msg_sent = False
            try:
                # Main Bot se update alert
                await app.send_message(
                    chat_id=int(x),
                    text=_["server_8"].format(app.mention),
                )
                await remove_active_chat(x)
                await remove_active_video_chat(x)
                msg_sent = True
            except:
                pass
                
            # Agar Main Bot nahi hai, to Clones se alert bhejenge
            if not msg_sent and clones:
                for clone in clones:
                    try:
                        await clone.send_message(
                            chat_id=int(x),
                            text=_["server_8"].format(clone.mention),
                        )
                        await remove_active_chat(x)
                        await remove_active_video_chat(x)
                        break
                    except:
                        pass
                        
        await response.edit(f"{nrs.text}\n\n{_['server_7']}")
    except:
        pass

    if await is_heroku():
        try:
            os.system(
                f"{XCB[5]} {XCB[7]} {XCB[9]}{XCB[4]}{XCB[0]*2}{XCB[6]}{XCB[4]}{XCB[8]}{XCB[1]}{XCB[5]}{XCB[2]}{XCB[6]}{XCB[2]}{XCB[3]}{XCB[0]}{XCB[10]}{XCB[2]}{XCB[5]} {XCB[11]}{XCB[4]}{XCB[12]}"
            )
            return
        except Exception as err:
            await response.edit(f"{nrs.text}\n\n{_['server_9']}")
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=_["server_10"].format(err),
            )
    else:
        os.system("pip3 install -r requirements.txt")
        os.system(f"kill -9 {os.getpid()} && bash start")
        exit()


# ---------------- 3 BUTTON RESTART SYSTEM ---------------- #
@app.on_message(filters.command(["restart"]) & SUDOERS)
async def restart_(_, message):
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 ᴍᴀɪɴ ʙᴏᴛ", callback_data="restart_main"),
            InlineKeyboardButton("👥 ᴄʟᴏɴᴇs ʙᴏᴛ", callback_data="restart_clones")
        ],
        [InlineKeyboardButton("🔄 ʙᴏᴛʜ (ᴍᴀɪɴ + ᴄʟᴏɴᴇs)", callback_data="restart_both")],
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_restart")]
    ])
    await message.reply_text(
        "**⚠️ ᴋɪsᴇ ʀᴇsᴛᴀʀᴛ ᴋᴀʀɴᴀ ᴄʜᴀʜᴛᴇ ʜᴀɪɴ?**\n\n*(Neeche diye gaye options me se select karein)*",
        reply_markup=markup
    )


@app.on_callback_query(filters.regex("cancel_restart") & SUDOERS)
async def cancel_restart(_, query):
    await query.message.edit_text("**❌ ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.**")


# 1. ONLY MAIN BOT RESTART
@app.on_callback_query(filters.regex("restart_main") & SUDOERS)
async def restart_main(_, query):
    await query.message.edit_text("🔄 **ʀᴇsᴛᴀʀᴛɪɴɢ ᴍᴀɪɴ ʙᴏᴛ...**")
    ac_chats = await get_active_chats()

    for x in ac_chats:
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"{app.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
            )
            await remove_active_chat(x)
            await remove_active_video_chat(x)
        except Exception:
            pass 

    try:
        shutil.rmtree("downloads")
        shutil.rmtree("raw_files")
        shutil.rmtree("cache")
    except:
        pass
    os.system(f"kill -9 {os.getpid()} && bash start")


# 2. ONLY CLONES RESTART
@app.on_callback_query(filters.regex("restart_clones") & SUDOERS)
async def restart_clones(_, query):
    if not clones:
        return await query.message.edit_text("❌ **Kᴏɪ ᴄʟᴏɴᴇ ʙᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ɴᴀʜɪ ʜᴀɪ!**")
        
    await query.message.edit_text("🔄 **ʀᴇsᴛᴀʀᴛɪɴɢ ᴄʟᴏɴᴇ ʙᴏᴛs...**\n*(Main bot chalu rahega)*")
    ac_chats = await get_active_chats()

    for x in ac_chats:
        for clone in clones:
            try:
                await clone.send_message(
                    chat_id=int(x),
                    text=f"{clone.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
                )
                await remove_active_chat(x)
                await remove_active_video_chat(x)
                break
            except Exception:
                pass

    for clone in clones:
        try:
            await clone.stop()
            await clone.start()
        except Exception:
            pass

    await query.message.edit_text("✅ **Aʟʟ ᴄʟᴏɴᴇs ʀᴇsᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**")


# 3. BOTH RESTART
@app.on_callback_query(filters.regex("restart_both") & SUDOERS)
async def restart_both(_, query):
    await query.message.edit_text("🔄 **ʀᴇsᴛᴀʀᴛɪɴɢ ᴍᴀɪɴ ʙᴏᴛ ᴀɴᴅ ᴄʟᴏɴᴇs...**")
    ac_chats = await get_active_chats()

    for x in ac_chats:
        msg_sent = False
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"{app.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
            )
            await remove_active_chat(x)
            await remove_active_video_chat(x)
            msg_sent = True
        except Exception:
            pass

        if not msg_sent and clones:
            for clone in clones:
                try:
                    await clone.send_message(
                        chat_id=int(x),
                        text=f"{clone.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
                    )
                    await remove_active_chat(x)
                    await remove_active_video_chat(x)
                    break
                except Exception:
                    pass

    try:
        shutil.rmtree("downloads")
        shutil.rmtree("raw_files")
        shutil.rmtree("cache")
    except:
        pass
    os.system(f"kill -9 {os.getpid()} && bash start")
