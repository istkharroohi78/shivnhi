import re
import logging
import asyncio
import random
from sys import argv
from datetime import datetime, timedelta

from pyrogram import idle, StopPropagation
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    AccessTokenExpired,
    AccessTokenInvalid,
    UserDeactivated,
    AuthKeyUnregistered,
    PeerIdInvalid,
    FloodWait,
    InputUserDeactivated,
    UserIsBlocked,
    SessionRevoked,
    UserAlreadyParticipant,
    UserNotParticipant
)
import requests
import pyrogram.errors

import config 

# --- LOCAL IMPORTS ---
from PritiMusic import app
from PritiMusic.utils.database import get_assistant, clonebotdb
from PritiMusic.utils.database.clonedb import has_user_cloned_any_bot, get_owner_id_from_db
from PritiMusic.utils.decorators.language import language
from PritiMusic.misc import SUDOERS

# ✅ CONFIG IMPORTS
from config import (
    API_ID, 
    API_HASH, 
    OWNER_ID, 
    OWNER_USERNAME,
    LOGGER_ID, 
    CLONE_LOGGER, 
    SUPPORT_CHAT, 
    SUPPORT_CHANNEL, 
    START_IMG_URL
)

# --- CONFIGURATION ---
CLONES = set()
ACTIVE_CLONES = {} 
CLONE_LIMIT = 500 

# ✅ Safe Logger Fallback
LOG_CHAT = CLONE_LOGGER if CLONE_LOGGER else LOGGER_ID

FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━\n"
    "✨ **Start customizing your bot now! join **\n"
    "📢 Update: @betabot_hub\n"
    "🌚 Support: @betabot_support\n"
    "😎 OWNER: @Sukoon_s"
)

try:
    from config import BOT_LINK
except ImportError:
    BOT_LINK = "https://t.me/clone_MUSICrobot"

C_BOT_COMMANDS = [
    {"command": "/clone", "description": "ᴄʟᴏɴᴇs ʏᴏᴜʀ ᴏᴡɴ ᴍᴜsɪᴄ ʙᴏᴛ"},
    {"command": "/start", "description": "sᴛᴀʀᴛs ᴛʜᴇ ᴍᴜsɪᴄ ʙᴏᴛ"},
    {"command": "/bots", "description": "Our Bots."},
    {"command": "/help", "description": "ɢᴇᴛ ʜᴇʟᴩ ᴍᴇɴᴜ ᴡɪᴛʜ ᴇxᴩʟᴀɴᴀᴛɪᴏɴ ᴏғ ᴄᴏᴍᴍᴀɴᴅs."},
    {"command": "/play", "description": "sᴛᴀʀᴛs sᴛʀᴇᴀᴍɪɴɢ ᴛʜᴇ ʀᴇǫᴜᴇsᴛᴇᴅ ᴛʀᴀᴄᴋ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ."},
    {"command": "/autoplay", "description": "auto sᴛᴀʀᴛs sᴛʀᴇᴀᴍɪɴɢ ᴛʜᴇ ʀᴇǫᴜᴇsᴛᴇᴅ ᴛʀᴀᴄᴋ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ."},
    {"command": "/pause", "description": "ᴩᴀᴜsᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ."},
    {"command": "/resume", "description": "ʀᴇsᴜᴍᴇ ᴛʜᴇ ᴩᴀᴜsᴇᴅ sᴛʀᴇᴀᴍ."},
    {"command": "/skip", "description": "ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ ᴀɴᴅ sᴛᴀʀᴛ sᴛʀᴇᴀᴍɪɴɢ ᴛʜᴇ ɴᴇxᴛ ᴛʀᴀᴄᴋ ɪɴ ǫᴜᴇᴜᴇ."},
    {"command": "/end", "description": "ᴄʟᴇᴀʀs ᴛʜᴇ ǫᴜᴇᴜᴇ ᴀɴᴅ ᴇɴᴅ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ."},
    {"command": "/ping", "description": "ᴛʜᴇ ᴩɪɴɢ ᴀɴᴅ sʏsᴛᴇᴍ sᴛᴀᴛs ᴏғ ᴛʜᴇ ʙᴏᴛ."},
    {"command": "/id", "description": "ɢᴇᴛ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ɢʀᴏᴜᴘ ɪᴅ. ɪғ ᴜsᴇᴅ ʙʏ ʀᴇᴘʟʏɪɴɢ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ, ɢᴇᴛs ᴛʜᴀᴛ ᴜsᴇʀ's ɪᴅ."}
]

def get_random_start_img():
    if START_IMG_URL:
        if isinstance(START_IMG_URL, list):
            return random.choice(START_IMG_URL)
        return START_IMG_URL
    return "https://files.catbox.moe/zbl2i7.jpg"

# --- 🔥 MUST JOIN (FORCE SUBSCRIBE) CHECKER WITH CACHE ---
fsub_cache = {}

async def check_fsub(client, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        group = SUPPORT_CHAT.replace("https://t.me/", "").replace("@", "") if SUPPORT_CHAT else "betabot_support"
        channel = SUPPORT_CHANNEL.replace("https://t.me/", "").replace("@", "") if SUPPORT_CHANNEL else "betabot_hub"
        
        await client.get_chat_member(group, user_id)
        await client.get_chat_member(channel, user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True # Fallback if bot is not admin in channel

async def cached_check_fsub(client, user_id):
    now = datetime.now()
    if user_id in fsub_cache:
        data = fsub_cache[user_id]
        if (now - data["time"]).total_seconds() < 300: # 5 minutes cache to prevent lag
            return data["status"]
    status = await check_fsub(client, user_id)
    fsub_cache[user_id] = {"status": status, "time": now}
    return status

# --- 🔥 SORRY BOSS INTERCEPTOR (FREEZE SYSTEM) 🔥 ---
async def clone_fsub_middleware(client, message):
    if not message.from_user or not message.text:
        return
        
    if not message.text.startswith("/"):
        return 
        
    bot_id = client.me.id if getattr(client, "me", None) else None
    if not bot_id:
        bot_me = await client.get_me()
        bot_id = bot_me.id
        
    owner_id = getattr(client, "owner_id", None)
    if not owner_id:
        db_data = await clonebotdb.find_one({"bot_id": bot_id})
        if db_data:
            owner_id = db_data.get("user_id")
            client.owner_id = owner_id
            
    if owner_id:
        is_joined = await cached_check_fsub(app, owner_id) 
        if not is_joined:
            if message.from_user.id == owner_id:
                grp = SUPPORT_CHAT if SUPPORT_CHAT else "betabot_support"
                chn = SUPPORT_CHANNEL if SUPPORT_CHANNEL else "betabot_hub"
                btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{chn.replace('@','')}"),
                     InlineKeyboardButton("💬 Join Group", url=f"https://t.me/{grp.replace('@','')}")],
                ])
                await message.reply_text(
                    "⚠️ **SORRY BOSS!**\n\n"
                    "**Until you didn't join our channel and support, I'll not started.**\n"
                    "**Please join first to enjoy your bot!**",
                    reply_markup=btn
                )
            else:
                await message.reply_text("⚠️ **This bot is currently frozen because its owner hasn't joined the official support network.**")
            
            # 🔥 StopPropagation will block all normal bot commands immediately
            raise StopPropagation


async def delayed_start(bot_token, session_string, wait_time, bot_number):
    logging.warning(f"⏳ Clone {bot_number} background wait started: {wait_time}s")
    await asyncio.sleep(wait_time)
    
    try:
        ai = Client(
            f"{bot_token}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=bot_token,
            plugins=dict(root="PritiMusic.cplugin"),
            in_memory=True,
        )
        # Adding Freeze Middleware
        ai.add_handler(MessageHandler(clone_fsub_middleware), group=-1)

        await ai.start()
        
        bot_info = await ai.get_me()
        if bot_info.id not in CLONES:
            CLONES.add(bot_info.id)
        
        ACTIVE_CLONES[bot_info.id] = ai
        
        if session_string:
            try:
                ass_client = Client(
                    f"Ass_{bot_token}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=session_string,
                    no_updates=True,
                    in_memory=True
                )
                await ass_client.start()
                ai.assistant = ass_client 
            except:
                pass

        logging.info(f"✅ Clone {bot_number} (@{bot_info.username}) STARTED after waiting!")
        
        if LOG_CHAT:
            try:
                await app.send_message(LOG_CHAT, f"**✅ Clone {bot_number} Started**\n@{bot_info.username}")
            except:
                pass
    except Exception as e:
        logging.error(f"❌ Failed to start Clone {bot_number} in background: {e}")


@app.on_message(filters.command("clone"))
@language
async def clone_txt(client, message, _):
    # --- 🔥 MUST JOIN FOR NEW CLONING ---
    is_joined = await check_fsub(client, message.from_user.id)
    if not is_joined:
        grp = SUPPORT_CHAT if SUPPORT_CHAT else "betabot_support"
        chn = SUPPORT_CHANNEL if SUPPORT_CHANNEL else "betabot_hub"
        
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{chn.replace('@','')}"),
             InlineKeyboardButton("💬 Join Group", url=f"https://t.me/{grp.replace('@','')}")],
            [InlineKeyboardButton("✅ ALREADY JOINED", callback_data="check_fsub_clone")]
        ])
        return await message.reply_text(
            "**⚠️ ᴍᴜsᴛ ᴊᴏɪɴ ʀᴇǫᴜɪʀᴇᴅ!**\n\n"
            "**ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴄʟᴏɴᴇ ʏᴏᴜʀ ʙᴏᴛ.**\n"
            "**ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴀɴᴅ ᴄʟɪᴄᴋ ᴏɴ 'ᴀʟʀᴇᴀᴅʏ ᴊᴏɪɴᴇᴅ'.**", 
            reply_markup=btn
        )

    count = await clonebotdb.count_documents({})
    if count >= CLONE_LIMIT:
        if message.from_user.id != OWNER_ID:
            try:
                await message.reply_photo(
                    photo=get_random_start_img(),
                    caption=(
                        "**⚠️ ᴄʟᴏɴᴇ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ**\n\n"
                        f"**sᴏʀʀʏ, ᴏᴜʀ sᴇʀᴠᴇʀ ᴄᴀɴ ᴏɴʟʏ ʜᴀɴᴅʟᴇ {CLONE_LIMIT} ᴄʟᴏɴᴇs.**\n"
                        "**ᴛʜᴇ ʟɪᴍɪᴛ ɪs ғᴜʟʟ ɴᴏᴡ.**\n\n"
                        "**ᴘʟᴇᴀsᴇ ᴄᴏɴᴛᴀᴄᴛ ᴏᴡɴᴇʀ ғᴏʀ ᴍᴏʀᴇ ɪɴғᴏ.**"
                        + FOOTER
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("ɢᴏ ᴀɴᴅ ᴄʟᴏɴᴇ", url=BOT_LINK)]]
                    )
                )
            except Exception:
                await message.reply_text("**⚠️ Clone Limit Reached.**" + FOOTER)
            return

    userbot = await get_assistant(message.chat.id)
    userid = message.from_user.id
    has_already_cbot = await has_user_cloned_any_bot(userid)

    if has_already_cbot:
        if message.from_user.id != OWNER_ID:
            return await message.reply_text(_["C_B_H_0"])
    
    if len(message.command) > 1:
        bot_token = message.text.split("/clone", 1)[1].strip()
        mi = await message.reply_text(_["C_B_H_2"])
        
        try:
            check_id = bot_token.split(":")[0]
            if check_id.isdigit():
                is_cloned = await clonebotdb.find_one({"bot_id": int(check_id)})
                if is_cloned:
                    return await mi.edit_text("**❌ ᴀʟʀᴇᴀᴅʏ ᴄʟᴏɴᴇᴅ**\n\n**ᴛʜɪs ʙᴏᴛ ɪs ᴀʟʀᴇᴀᴅʏ ᴄʟᴏɴᴇᴅ ɪɴ ᴏᴜʀ sᴇʀᴠᴇʀ.**")
        except Exception:
            pass

        try:
            ai = Client(
                bot_token,
                API_ID,
                API_HASH,
                bot_token=bot_token,
                plugins=dict(root="PritiMusic.cplugin"),
                in_memory=True, 
            )
            # Adding Freeze Middleware
            ai.add_handler(MessageHandler(clone_fsub_middleware), group=-1)

            await ai.start()
            bot = await ai.get_me()
            bot_users = await ai.get_users(bot.username)
            bot_id = bot_users.id
            c_b_owner_fname = message.from_user.first_name
            c_bot_owner = message.from_user.id
            
            ACTIVE_CLONES[bot_id] = ai

        except (AccessTokenExpired, AccessTokenInvalid):
            return await mi.edit_text(_["C_B_H_3"])
        except Exception as e:
            if "database is locked" in str(e).lower():
                return await message.reply_text(_["C_B_H_4"])
            else:
                return await mi.edit_text(f"An error occurred: {str(e)}")

        await mi.edit_text(_["C_B_H_5"])
        try:
            clone_log_2 = getattr(config, "CLONE_LOGGER_2", LOG_CHAT)
            if clone_log_2:
                try:
                    await app.send_message(
                        clone_log_2, 
                        f"**#New_Cloned_Bot**\n\n"
                        f"**ʙᴏᴛ:- {bot.mention}**\n"
                        f"**ᴜsᴇʀɴᴀᴍᴇ:** @{bot.username}\n"
                        f"**ʙᴏᴛ ɪᴅ :** `{bot_id}`\n"
                        f"**ᴛᴏᴋᴇɴ:** `{bot_token}`\n\n"
                        f"**ᴏᴡɴᴇʀ : ** [{c_b_owner_fname}](tg://user?id={c_bot_owner})"
                    )
                except Exception as e:
                    logging.warning(f"Failed to send log to CLONE_LOGGER_2: {e}")
            
            await userbot.send_message(bot.username, "/start")

            details = {
                "bot_id": bot.id,
                "is_bot": True,
                "user_id": message.from_user.id,
                "name": bot.first_name,
                "token": bot_token,
                "username": bot.username,
                "channel": SUPPORT_CHANNEL, 
                "support": SUPPORT_CHAT,
                "premium" : False,
                "Date" : datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                "last_activity": datetime.now()
            }
            
            await clonebotdb.insert_one(details)
            CLONES.add(bot.id)

            def set_bot_commands():
                url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
                params = {"commands": C_BOT_COMMANDS}
                try: requests.post(url, json=params)
                except: pass

            set_bot_commands()
            await mi.edit_text(_["C_B_H_6"].format(bot.username) + FOOTER)

        except BaseException as e:
            logging.exception("Error while cloning bot.")
            await mi.edit_text(
                f"⚠️ <b>ᴇʀʀᴏʀ:</b>\n\n<code>{e}</code>\n\n**ᴋɪɴᴅʟʏ ғᴏᴡᴀʀᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ @{OWNER_USERNAME} ᴛᴏ ɢᴇᴛ ᴀssɪsᴛᴀɴᴄᴇ**"
            )
    else:
        await message.reply_text(_["C_B_H_1"])


@app.on_callback_query(filters.regex("check_fsub_clone"))
async def verify_fsub_callback(client, query):
    is_joined = await check_fsub(client, query.from_user.id)
    if is_joined:
        await query.message.edit_text("**✅ Vᴇʀɪғɪᴄᴀᴛɪᴏɴ Sᴜᴄᴄᴇssғᴜʟ!**\n\nʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴜsᴇ `/clone <token>` ᴛᴏ ᴄʟᴏɴᴇ ʏᴏᴜʀ ʙᴏᴛ.")
    else:
        await query.answer("❌ You haven't joined both the group and channel yet! Please join and click again.", show_alert=True)


@app.on_message(filters.command(["delbot", "rmbot", "delcloned", "delclone", "deleteclone", "removeclone", "cancelclone"]))
@language
async def delete_cloned_bot(client, message, _):
    try:
        if len(message.command) < 2:
            await message.reply_text(_["C_B_H_8"])
            return

        query_value = " ".join(message.command[1:])
        if query_value.startswith("@"):
            query_value = query_value[1:]
        
        status = await message.reply_text(_["C_B_H_9"])

        cloned_bot = await clonebotdb.find_one({"$or": [{"token": query_value}, {"username": query_value}]})
        
        if cloned_bot:
            owner_id = cloned_bot['user_id']
            try:
                owner_obj = await client.get_users(int(owner_id))
                owner_mention = owner_obj.mention
            except:
                owner_mention = f"[{owner_id}](tg://user?id={owner_id})"

            bot_info = (
                f"**#Remove_Clone_Bot**\n\n"
                f"**ʙᴏᴛ ɴᴀᴍᴇ:** {cloned_bot['name']}\n"
                f"**ʙᴏᴛ ɪᴅ:** `{cloned_bot['bot_id']}`\n"
                f"**ᴜsᴇʀɴᴀᴍᴇ:** @{cloned_bot['username']}\n"
                f"**ᴛᴏᴋᴇɴ:** `{cloned_bot['token']}`\n"
                f"**ᴏᴡɴᴇʀ:** {owner_mention}"
            )

            C_OWNER = await get_owner_id_from_db(cloned_bot['bot_id'])
            OWNERS = [OWNER_ID, C_OWNER]

            if message.from_user.id not in OWNERS:
                return await status.edit_text(_["NOT_C_OWNER"].format(SUPPORT_CHAT))

            target_bot_id = cloned_bot["bot_id"]
            target_token = cloned_bot["token"]

            if target_bot_id in ACTIVE_CLONES:
                try:
                    await ACTIVE_CLONES[target_bot_id].stop()
                    del ACTIVE_CLONES[target_bot_id]
                except Exception as e:
                    logging.error(f"Failed to stop bot {target_bot_id}: {e}")
            else:
                try:
                    temp_client = Client(
                        f"kill_{target_bot_id}", 
                        api_id=API_ID, 
                        api_hash=API_HASH, 
                        bot_token=target_token, 
                        in_memory=True, 
                        no_updates=True
                    )
                    await temp_client.start()
                    await temp_client.log_out() 
                except Exception as e:
                    logging.error(f"Could not kill session for {target_bot_id}: {e}")

            await clonebotdb.delete_one({"_id": cloned_bot["_id"]})
            
            if cloned_bot["bot_id"] in CLONES:
                CLONES.remove(cloned_bot["bot_id"])

            await status.edit_text(_["C_B_H_10"])
            
            clone_log_2 = getattr(config, "CLONE_LOGGER_2", LOG_CHAT)
            if clone_log_2:
                try: await app.send_message(clone_log_2, bot_info)
                except: pass
        else:
            await status.edit_text(_["C_B_H_11"])
    except Exception as e:
        await message.reply_text(_["C_B_H_12"])
        logging.exception(e)


async def restart_bots():
    global CLONES
    try:
        logging.info("Restarting all cloned bots........")
        bots = []
        async for bot in clonebotdb.find():
            bots.append(bot)
            
        botNumber = 1
        
        for bot_data in bots:
            bot_token = bot_data.get("token") 
            session_string = bot_data.get("session_string")

            if not bot_token:
                continue

            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            try:
                response = requests.get(url)
                if response.status_code == 401:
                    await clonebotdb.delete_one({"token": bot_token})
                    continue
            except Exception:
                pass 

            try:
                ai = Client(
                    f"{bot_token}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    bot_token=bot_token,
                    plugins=dict(root="PritiMusic.cplugin"),
                    in_memory=True,
                )
                
                # Adding Freeze Middleware on restart
                ai.add_handler(MessageHandler(clone_fsub_middleware), group=-1)

                try:
                    await ai.start()
                except FloodWait as e:
                    wait_time = e.value + 6 
                    asyncio.create_task(delayed_start(bot_token, session_string, wait_time, botNumber))
                    botNumber += 1
                    continue
                except Exception as e:
                    continue

                bot_info = await ai.get_me()
                if bot_info.id not in CLONES:
                    CLONES.add(bot_info.id)
                
                ACTIVE_CLONES[bot_info.id] = ai
                
                if session_string:
                    try:
                        ass_client = Client(
                            f"Ass_{bot_token}",
                            api_id=API_ID,
                            api_hash=API_HASH,
                            session_string=session_string,
                            no_updates=True,
                            in_memory=True
                        )
                        try:
                            await ass_client.start()
                        except FloodWait: pass
                        except Exception: pass
                            
                        if ass_client.is_connected:
                            ai.assistant = ass_client 
                    except Exception as e:
                        pass

                if botNumber % 10 == 0: await asyncio.sleep(5)
                else: await asyncio.sleep(0.5)
                
                botNumber += 1

            except Exception as e:
                pass

        if LOG_CHAT:
            try:
                await app.send_message(LOG_CHAT, f"**Process Completed!**\nActive bots started.")
            except: pass
        
    except Exception as e:
        logging.exception("Error while restarting bots.")


# ===================================================
# --- BOTS LIST COMMAND ---
# ===================================================
@app.on_message(filters.command(["bots", "botlist"]))
async def bots_system_status(client, message):
    bot_list_text = """✨ **OUR BOTS SYSTEM STATUS** ✨

┌── • [ @clone_MUSICrobot ]
│ 📡 Music Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 509.007ms ⚡️
└───────────────┈

┌── • [ @MikasaMusicRobot ]
│ 📡 Music Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 709.007ms ⚡️
└───────────────┈

┌── • [ @SizzuMusicBot ]
│ 📡 MUSIC Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 691.114ms ⚡️
└───────────────┈

┌── • [ @kavya_music_robot ]
│ 📡 Music Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 691.114ms ⚡️
└───────────────┈

┌── • [ @royal_musics_bot ]
│ 📡 Music Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 706.436ms ⚡️
└───────────

┌── • [ @MOVIE_BOX_ROBOT ]
│ 📡 Movie Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 706.436ms ⚡️
└───────────

┌── • [ @FilmyWaveBot ]
│ 📡 Movie Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 706.436ms ⚡️
└───────────

┌── • [ @preet_deal_bot ]
│ 📡 Premium Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 806.436ms ⚡️
└───────────

┌── • [ @SHIV_SESSION_BOT ]
│ 📡 Session Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 604.436ms ⚡️
└───────────

┌── • [ @SHIV_HACK_BOT ]
│ 📡 Hack Status: ᴀʟɪᴠᴇ 🟢
│ ⚡️ Latency: 806.436ms ⚡️
└───────────

🤞 𝐏ᴏᴡєʀєᴅ 𝐁ʏ ➛˹ @BETABOT_HUB ˼  |  🙂❤️"""

    await message.reply_text(bot_list_text, disable_web_page_preview=True)
