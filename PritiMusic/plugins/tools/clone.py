import re
import logging
import asyncio
import importlib
import random
from sys import argv
from datetime import datetime, timedelta

from pyrogram import idle
from pyrogram import Client, filters
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
    UserAlreadyParticipant
)
import requests
import pyrogram.errors

import config # ✅ Added config import for CLONE_LOGGER_2

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
    "🌚 Support: @betabot_support"
)

try:
    from config import BOT_LINK
except ImportError:
    BOT_LINK = "https://t.me/clone_MUSICrobot"

C_BOT_COMMANDS = [
    {"command": "/clone", "description": "ᴄʟᴏɴᴇs ʏᴏᴜʀ ᴏᴡɴ ᴍᴜsɪᴄ ʙᴏᴛ"},
    {"command": "/start", "description": "sᴛᴀʀᴛs ᴛʜᴇ ᴍᴜsɪᴄ ʙᴏᴛ"},
    {"command": "/help", "description": "ɢᴇᴛ ʜᴇʟᴩ ᴍᴇɴᴜ ᴡɪᴛʜ ᴇxᴩʟᴀɴᴀᴛɪᴏɴ ᴏғ ᴄᴏᴍᴍᴀɴᴅs."},
    {"command": "/play", "description": "sᴛᴀʀᴛs sᴛʀᴇᴀᴍɪɴɢ ᴛʜᴇ ʀᴇǫᴜᴇsᴛᴇᴅ ᴛʀᴀᴄᴋ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ."},
    {"command": "/pause", "description": "ᴩᴀᴜsᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ."},
    {"command": "/resume", "description": "ʀᴇsᴜᴍᴇ ᴛʜᴇ ᴩᴀᴜsᴇᴅ sᴛʀᴇᴀᴍ."},
    {"command": "/skip", "description": "ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ ᴀɴᴅ sᴛᴀʀᴛ sᴛʀᴇᴀᴍɪɴɢ ᴛʜᴇ ɴᴇxᴛ ᴛʀᴀᴄᴋ ɪɴ ǫᴜᴇᴜᴇ."},
    {"command": "/end", "description": "ᴄʟᴇᴀʀs ᴛʜᴇ ǫᴜᴇᴜᴇ ᴀɴᴅ ᴇɴᴅ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴩʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ."},
    {"command": "/ping", "description": "ᴛʜᴇ ᴩɪɴɢ ᴀɴᴅ sʏsᴛᴇᴍ sᴛᴀᴛs ᴏғ ᴛʜᴇ ʙᴏᴛ."},
    {"command": "/id", "description": "ɢᴇᴛ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ɢʀᴏᴜᴘ ɪᴅ. ɪғ ᴜsᴇᴅ ʙʏ ʀᴇᴘʟʏɪɴɢ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ, ɢᴇᴛs ᴛʜᴀᴛ ᴜsᴇʀ's ɪᴅ."}
]

# ✅ Helper for Random Image
def get_random_start_img():
    if START_IMG_URL:
        if isinstance(START_IMG_URL, list):
            return random.choice(START_IMG_URL)
        return START_IMG_URL
    return "https://files.catbox.moe/f09yfp.jpg" # Fallback

# --- 🔥 HELPER FUNCTION FOR BACKGROUND RESTART ---
async def delayed_start(bot_token, session_string, wait_time, bot_number):
    """
    Ye function background me wait karega aur time pura hone par bot start karega.
    """
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
        await ai.start()
        
        bot_info = await ai.get_me()
        if bot_info.id not in CLONES:
            CLONES.add(bot_info.id)
        
        ACTIVE_CLONES[bot_info.id] = ai
        
        # Assistant Start Logic
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
        
        # Log to channel safely
        if LOG_CHAT:
            try:
                await app.send_message(LOG_CHAT, f"**✅ Clone {bot_number} Started (After FloodWait)**\n@{bot_info.username}")
            except:
                pass

    except Exception as e:
        logging.error(f"❌ Failed to start Clone {bot_number} in background: {e}")

# ---------------------------------------------------

@app.on_message(filters.command("clone"))
@language
async def clone_txt(client, message, _):
    # --- 🔥 CLONE LIMIT LOGIC START ---
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
                    ),
                    has_spoiler=True
                )
            except Exception as e:
                await message.reply_text("**⚠️ Clone Limit Reached.**" + FOOTER)
            return
    # --- 🔥 CLONE LIMIT LOGIC END ---

    userbot = await get_assistant(message.chat.id)
    userid = message.from_user.id
    has_already_cbot = await has_user_cloned_any_bot(userid)

    if has_already_cbot:
        if message.from_user.id != OWNER_ID:
            return await message.reply_text(_["C_B_H_0"])
    
    if len(message.command) > 1:
        bot_token = message.text.split("/clone", 1)[1].strip()
        mi = await message.reply_text(_["C_B_H_2"])
        
        # --- 🔥 STEP 1: Check DB First (Fixes Loop & Load) ---
        try:
            check_id = bot_token.split(":")[0]
            if check_id.isdigit():
                is_cloned = await clonebotdb.find_one({"bot_id": int(check_id)})
                if is_cloned:
                    await mi.edit_text(
                        "**❌ ᴀʟʀᴇᴀᴅʏ ᴄʟᴏɴᴇᴅ**\n\n"
                        "**ᴛʜɪs ʙᴏᴛ ɪs ᴀʟʀᴇᴀᴅʏ ᴄʟᴏɴᴇᴅ ɪɴ ᴏᴜʀ sᴇʀᴠᴇʀ.**"
                    )
                    return
        except Exception:
            pass
        # ----------------------------------------------------

        try:
            ai = Client(
                bot_token,
                API_ID,
                API_HASH,
                bot_token=bot_token,
                plugins=dict(root="PritiMusic.cplugin"),
                in_memory=True, 
            )
            await ai.start()
            bot = await ai.get_me()
            bot_users = await ai.get_users(bot.username)
            bot_id = bot_users.id
            c_b_owner_fname = message.from_user.first_name
            c_bot_owner = message.from_user.id
            
            ACTIVE_CLONES[bot_id] = ai

        except (AccessTokenExpired, AccessTokenInvalid):
            await mi.edit_text(_["C_B_H_3"])
            return
        except Exception as e:
            if "database is locked" in str(e).lower():
                await message.reply_text(_["C_B_H_4"])
            else:
                await mi.edit_text(f"An error occurred: {str(e)}")
            return

        await mi.edit_text(_["C_B_H_5"])
        try:
            # 🔥 TOKEN ADDED TO LOG 2 HERE 🔥
            # Yahan ye check karega ki CLONE_LOGGER_2 exist karta hai ya nahi
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
                try:
                    requests.post(url, json=params)
                except:
                    pass

            set_bot_commands()

            await mi.edit_text(_["C_B_H_6"].format(bot.username) + FOOTER)
        except BaseException as e:
            logging.exception("Error while cloning bot.")
            await mi.edit_text(
                f"⚠️ <b>ᴇʀʀᴏʀ:</b>\n\n<code>{e}</code>\n\n**ᴋɪɴᴅʟʏ ғᴏᴡᴀʀᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ @{OWNER_USERNAME} ᴛᴏ ɢᴇᴛ ᴀssɪsᴛᴀɴᴄᴇ**"
            )
    else:
        await message.reply_text(_["C_B_H_1"])


@app.on_message(
    filters.command(
        [
            "delbot",
            "rmbot",
            "delcloned",
            "delclone",
            "deleteclone",
            "removeclone",
            "cancelclone",
        ]
    )
)
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

            # 🔥 TOKEN ADDED TO LOG HERE 🔥
            bot_info = (
                f"**#Remove_Clone_Bot**\n\n"
                f"**ʙᴏᴛ ɴᴀᴍᴇ:** {cloned_bot['name']}\n"
                f"**ʙᴏᴛ ɪᴅ:** `{cloned_bot['bot_id']}`\n"
                f"**ᴜsᴇʀɴᴀᴍᴇ:** @{cloned_bot['username']}\n"
                f"**ᴛᴏᴋᴇɴ:** `{cloned_bot['token']}`\n"
                f"**ᴏᴡɴᴇʀ:** {owner_mention}"
            )
            # ---------------------------------------------

            C_OWNER = await get_owner_id_from_db(cloned_bot['bot_id'])
            OWNERS = [OWNER_ID, C_OWNER]

            if message.from_user.id not in OWNERS:
                return await status.edit_text(_["NOT_C_OWNER"].format(SUPPORT_CHAT))

            target_bot_id = cloned_bot["bot_id"]
            target_token = cloned_bot["token"]

            # --- 🔥 METHOD 1: Stop if in Memory ---
            if target_bot_id in ACTIVE_CLONES:
                try:
                    await ACTIVE_CLONES[target_bot_id].stop()
                    del ACTIVE_CLONES[target_bot_id]
                    logging.info(f"Bot {target_bot_id} stopped from memory.")
                except Exception as e:
                    logging.error(f"Failed to stop bot {target_bot_id}: {e}")
            
            # --- 🔥 METHOD 2: Force Kill via Session Revoke ---
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
                    logging.info(f"Bot {target_bot_id} session killed remotely.")
                except Exception as e:
                    logging.error(f"Could not kill session for {target_bot_id}: {e}")

            await clonebotdb.delete_one({"_id": cloned_bot["_id"]})
            if cloned_bot["bot_id"] in CLONES:
                CLONES.remove(cloned_bot["bot_id"])

            await status.edit_text(_["C_B_H_10"])
            
            # Use same fallback logic for deletion log
            clone_log_2 = getattr(config, "CLONE_LOGGER_2", LOG_CHAT)
            if clone_log_2:
                try:
                    await app.send_message(clone_log_2, bot_info)
                except:
                    pass
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

            # --- 🔥 Optimization: Check Token Validity First ---
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            try:
                response = requests.get(url)
                if response.status_code == 401:
                    logging.error(f"Removing Dead Clone (Invalid Token): {bot_token}")
                    await clonebotdb.delete_one({"token": bot_token})
                    continue
            except Exception:
                pass 
            # ---------------------------------------------------

            try:
                ai = Client(
                    f"{bot_token}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    bot_token=bot_token,
                    plugins=dict(root="PritiMusic.cplugin"),
                    in_memory=True,
                )
                
                # --- 🔥 BACKGROUND RETRY LOGIC (Smart Start) 🔥 ---
                try:
                    await ai.start()
                except FloodWait as e:
                    wait_time = e.value + 6 # Buffer time
                    logging.warning(f"⚠️ FloodWait {wait_time}s on Clone {botNumber}. Moving to background task...")
                    
                    asyncio.create_task(delayed_start(bot_token, session_string, wait_time, botNumber))
                    
                    botNumber += 1
                    continue
                except Exception as e:
                    logging.error(f"Could not start clone {botNumber}: {e}")
                    continue
                # -------------------------------------

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
                        except FloodWait:
                            pass
                        except Exception:
                            pass
                            
                        if ass_client.is_connected:
                            ai.assistant = ass_client 
                        logging.info(f"Assistant Auto-Started for Clone: {bot_info.first_name}")
                    except Exception as e:
                        logging.error(f"Failed to auto-start assistant for {bot_token}: {e}")

                print(f"Clone {botNumber} Started: @{bot_info.username}")
                
                # --- 🔥 FAST SLEEP LOGIC 🔥 ---
                if botNumber % 10 == 0:
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(0.5)
                
                botNumber += 1

            except Exception as e:
                logging.exception(f"Error starting clone {bot_token}: {e}")

        if LOG_CHAT:
            try:
                await app.send_message(
                    LOG_CHAT, f"**Process Completed!**\nActive bots started.\nFloodWait bots will auto-start in background."
                )
            except:
                pass
    except Exception as e:
        logging.exception("Error while restarting bots.")


@app.on_message(filters.command("delallclone") & filters.user(OWNER_ID))
@language
async def delete_all_cloned_bots(client, message, _):
    try:
        await message.reply_text(_["C_B_H_14"])
        
        # --- 🔥 STOP ALL PROCESSES ---
        count = 0
        for bot_id, bot_client in list(ACTIVE_CLONES.items()):
            try:
                await bot_client.stop()
                count += 1
            except:
                pass
        ACTIVE_CLONES.clear()
        # -----------------------------

        await clonebotdb.delete_many({})
        CLONES.clear()
        await message.reply_text(f"{_['C_B_H_15']} (Stopped {count} active instances)")
    except Exception as e:
        await message.reply_text("An error occurred while deleting all cloned bots.")
        logging.exception(e)


@app.on_message(filters.command(["mybot", "mybots"], prefixes=["/", "."]))
@language
async def my_cloned_bots(client, message, _):
    try:
        user_id = message.from_user.id
        
        cloned_bots = []
        async for bot in clonebotdb.find({"user_id": user_id}):
            cloned_bots.append(bot)
        
        if not cloned_bots:
            await message.reply_text(_["C_B_H_16"] + FOOTER)
            return
        
        total_clones = len(cloned_bots)
        text = f"**ʏᴏᴜʀ ᴄʟᴏɴᴇᴅ ʙᴏᴛs : {total_clones}**\n\n"
        
        for bot in cloned_bots:
            text += f"**ʙᴏᴛ ɴᴀᴍᴇ:** {bot['name']}\n"
            text += f"**ʙᴏᴛ ᴜsᴇʀɴᴀᴍᴇ:** @{bot['username']}\n\n"
        
        await message.reply_text(text + FOOTER)
    except Exception as e:
        logging.exception(e)
        await message.reply_text("An error occurred while fetching your cloned bots.")


@app.on_message(filters.command("cloned") & SUDOERS)
@language
async def list_cloned_bots(client, message, _):
    try:
        cloned_bots = []
        async for bot in clonebotdb.find():
            cloned_bots.append(bot)

        if not cloned_bots:
            await message.reply_text(_["C_B_H_13"])
            return

        total_clones = len(cloned_bots)
        text = f"**ᴛᴏᴛᴀʟ ᴄʟᴏɴᴇᴅ ʙᴏᴛs: `{total_clones}`**\n\n"

        chunk_size = 10
        chunks = [cloned_bots[i:i + chunk_size] for i in range(0, len(cloned_bots), chunk_size)]

        for chunk in chunks:
            chunk_text = text
            for bot in chunk:
                user_id = bot.get("user_id")
                bot_id = bot.get("bot_id", "Unknown")
                name = bot.get("name", "Unknown")
                username = bot.get("username", "Unknown")
                session = bot.get("session_string") 

                if session:
                    assistant_status = "✅ Connected"
                else:
                    assistant_status = "❌ None"
                
                created_on = bot.get("Date", "Unknown")
                if created_on is False:
                    created_on = "Unknown"

                if not user_id:
                    owner_name = "Data Missing"
                    owner_profile_link = "#"
                else:
                    try:
                        owner = await client.get_users(user_id)
                        owner_name = owner.first_name
                        owner_profile_link = f"tg://user?id={user_id}"
                    except pyrogram.errors.PeerIdInvalid:
                        owner_name = "Deleted User"
                        owner_profile_link = "#"
                    except Exception as e:
                        logging.error(f"Error fetching user {user_id}: {e}")
                        owner_name = "Unknown User"
                        owner_profile_link = "#"

                chunk_text += f"**ʙᴏᴛ ɪᴅ :** `{bot_id}`\n"
                chunk_text += f"**ʙᴏᴛ ɴᴀᴍᴇ :** {name}\n"
                chunk_text += f"**ʙᴏᴛ ᴜsᴇʀɴᴀᴍᴇ :** @{username}\n"
                chunk_text += f"**ᴏᴡɴᴇʀ :** [{owner_name}]({owner_profile_link})\n"
                chunk_text += f"**ᴀssɪsᴛᴀɴᴛ :** {assistant_status}\n"
                chunk_text += f"**ᴄʀᴇᴀᴛᴇᴅ ᴏɴ :** {created_on}\n\n"

            await message.reply_text(chunk_text)

    except Exception as e:
        logging.exception(e)
        await message.reply_text("An error occurred while listing cloned bots.")


@app.on_message(filters.command("totalbots") & SUDOERS)
@language
async def list_cloned_bots_total(client, message, _):
    try:
        cloned_bots = []
        async for bot in clonebotdb.find():
            cloned_bots.append(bot)

        if not cloned_bots:
            await message.reply_text("No bots have been cloned yet.")
            return

        total_clones = len(cloned_bots)
        text = f"**ᴛᴏᴛᴀʟ ᴄʟᴏɴᴇᴅ ʙᴏᴛs : `{total_clones}`**\n\n"          

        await message.reply_text(text)
    except Exception as e:
        logging.exception(e)
        await message.reply_text("An error occurred while listing cloned bots.")


# ===================================================
# --- NEW CINFO COMMAND (CLONE INFO FIX) ---
# ===================================================
@app.on_message(filters.command(["cinfo"]) & SUDOERS)
@language
async def clone_bot_info(client, message, _):
    if len(message.command) < 2:
        return await message.reply_text(
            "**⚠️ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ ᴄʟᴏɴᴇ ʙᴏᴛ's ᴜsᴇʀɴᴀᴍᴇ, ɪᴅ ᴏʀ ᴛᴏᴋᴇɴ.**\n"
            "**ᴇxᴀᴍᴘʟᴇ:** `/cinfo @MyCloneBot`"
        )

    # Safely extract query and remove leading '@'
    query_value = message.command[1]
    if query_value.startswith("@"):
        query_value = query_value[1:]
        
    msg = await message.reply_text("🔄 **ғᴇᴛᴄʜɪɴɢ ᴄʟᴏɴᴇ ʙᴏᴛ ᴅᴇᴛᴀɪʟs...**")

    try:
        # ✅ FIX: Search dynamically by Username (case-insensitive), Token, or Bot ID
        search_query = {
            "$or": [
                {"username": re.compile(f"^{query_value}$", re.IGNORECASE)},
                {"token": query_value}
            ]
        }
        if query_value.isdigit():
            search_query["$or"].append({"bot_id": int(query_value)})

        cloned_bot = await clonebotdb.find_one(search_query)

        if not cloned_bot:
            return await msg.edit_text(f"**❌ ɴᴏ ᴄʟᴏɴᴇ ʙᴏᴛ ғᴏᴜɴᴅ ᴡɪᴛʜ:** `{query_value}`")

        # Extracting Data
        bot_name = cloned_bot.get("name", "Unknown")
        bot_token = cloned_bot.get("token", "Unknown")
        bot_id = cloned_bot.get("bot_id", "Unknown")
        bot_username = cloned_bot.get("username", query_value)
        created_on = cloned_bot.get("Date", "Unknown")
        
        # Format last activity if it's a datetime object
        last_activity = cloned_bot.get("last_activity", "Unknown")
        if isinstance(last_activity, datetime):
            last_activity = last_activity.strftime("%d-%m-%Y %H:%M:%S")
        
        # Check if assistant is added
        session = cloned_bot.get("session_string")
        assistant_status = "✅ Added" if session else "❌ Not Added"

        # Fetch Owner Details
        owner_id = cloned_bot.get("user_id")
        if owner_id:
            try:
                owner_obj = await client.get_users(int(owner_id))
                owner_name = owner_obj.first_name
                owner_mention = owner_obj.mention
            except pyrogram.errors.PeerIdInvalid:
                owner_name = "Deleted/Unknown User"
                owner_mention = f"[{owner_id}](tg://user?id={owner_id})"
            except Exception:
                owner_name = "Unknown"
                owner_mention = f"[{owner_id}](tg://user?id={owner_id})"
        else:
            owner_name = "Data Missing"
            owner_mention = "N/A"

        # Final Message Formatting
        text = (
            f"**🤖 ᴄʟᴏɴᴇ ʙᴏᴛ ɪɴғᴏʀᴍᴀᴛɪᴏɴ**\n\n"
            f"**👤 ʙᴏᴛ ɴᴀᴍᴇ:** {bot_name}\n"
            f"**🆔 ʙᴏᴛ ɪᴅ:** `{bot_id}`\n"
            f"**🔗 ᴜsᴇʀɴᴀᴍᴇ:** @{bot_username}\n"
            f"**🔑 ᴛᴏᴋᴇɴ:** `{bot_token}`\n"
            f"**📅 ᴄʀᴇᴀᴛᴇᴅ ᴏɴ:** {created_on}\n"
            f"**⏱️ ʟᴀsᴛ ᴀᴄᴛɪᴠɪᴛʏ:** {last_activity}\n"
            f"**🎧 ᴀssɪsᴛᴀɴᴛ:** {assistant_status}\n\n"
            f"**👑 ᴏᴡɴᴇʀ ɴᴀᴍᴇ:** {owner_name}\n"
            f"**🔗 ᴏᴡɴᴇʀ ʟɪɴᴋ:** {owner_mention}"
        )

        await msg.edit_text(text)

    except Exception as e:
        await msg.edit_text(f"**❌ ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ᴅᴇᴛᴀɪʟs:** `{str(e)}`")
        logging.exception(f"Error in /cinfo command: {e}")

# ===================================================

# --- ACTIVE & INACTIVE BOTS MANAGEMENT ---

# ✅ 1. LIST ACTIVE BOTS
@app.on_message(filters.command("active") & SUDOERS)
async def list_active_bots(client, message):
    try:
        days = int(message.command[1]) if len(message.command) > 1 else 30
        limit_date = datetime.now() - timedelta(days=days)

        text = f"**🟢 Active Bots (Used in last {days} days):**\n\n"
        count = 0
        
        async for bot in clonebotdb.find({"last_activity": {"$gte": limit_date}}):
            last_active = bot.get("last_activity")
            if last_active:
                last_active = last_active.strftime("%d-%m-%Y")
            else:
                last_active = "Just Created"
            
            text += f"**Bot:** @{bot['username']}\n**Last Active:** {last_active}\n\n"
            count += 1
            
        if count == 0:
            await message.reply_text(f"**❌ No active bots found in last {days} days.**")
        else:
            if len(text) > 4000:
                with open("active_bots.txt", "w", encoding="utf-8") as f:
                    f.write(text.replace("*", ""))
                await message.reply_document("active_bots.txt", caption=f"Total Active: {count}")
                import os
                os.remove("active_bots.txt")
            else:
                await message.reply_text(text)

    except Exception as e:
        await message.reply_text(f"Error: {e}")

# ✅ 2. BOT STATISTICS (SUMMARY)
@app.on_message(filters.command("botstats") & SUDOERS)
async def bot_statistics(client, message):
    try:
        msg = await message.reply_text("🔄 **Calculating Stats...**")
        
        limit_date = datetime.now() - timedelta(days=30)
        
        total = await clonebotdb.count_documents({})
        active = await clonebotdb.count_documents({"last_activity": {"$gte": limit_date}})
        inactive = await clonebotdb.count_documents({
            "$or": [
                {"last_activity": {"$lt": limit_date}},
                {"last_activity": {"$exists": False}}
            ]
        })
        
        text = (
            f"**📊 CLONE BOT STATISTICS**\n\n"
            f"**🤖 Total Bots:** `{total}`\n"
            f"**🟢 Active (Last 30 Days):** `{active}`\n"
            f"**🔴 Inactive (Dead):** `{inactive}`\n"
        )
        await msg.edit_text(text)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

# ✅ 3. LIST INACTIVE BOTS
@app.on_message(filters.command("inactive") & SUDOERS)
async def list_inactive_bots(client, message):
    try:
        days = int(message.command[1]) if len(message.command) > 1 else 30
        limit_date = datetime.now() - timedelta(days=days)

        text = f"**⚠️ Inactive Bots (Not used in {days} days):**\n\n"
        count = 0
        
        async for bot in clonebotdb.find({
            "$or": [
                {"last_activity": {"$lt": limit_date}},
                {"last_activity": {"$exists": False}}
            ]
        }):
            last_active = bot.get("last_activity", "Never/Unknown")
            if last_active != "Never/Unknown":
                last_active = last_active.strftime("%d-%m-%Y")
            
            text += f"**Bot:** @{bot['username']}\n**Last Active:** {last_active}\n\n"
            count += 1
            
        if count == 0:
            await message.reply_text(f"**✅ No inactive bots found older than {days} days.**")
        else:
            if len(text) > 4000:
                with open("inactive_bots.txt", "w", encoding="utf-8") as f:
                    f.write(text.replace("*", ""))
                await message.reply_document("inactive_bots.txt", caption=f"Total Inactive: {count}")
                import os
                os.remove("inactive_bots.txt")
            else:
                await message.reply_text(text)

    except Exception as e:
        await message.reply_text(f"Error: {e}")

# ✅ 4. DELETE INACTIVE BOTS
@app.on_message(filters.command("delinactive") & SUDOERS)
async def delete_inactive_bots(client, message):
    try:
        days = int(message.command[1]) if len(message.command) > 1 else 30
        limit_date = datetime.now() - timedelta(days=days)
        
        to_delete = await clonebotdb.count_documents({
            "$or": [
                {"last_activity": {"$lt": limit_date}},
                {"last_activity": {"$exists": False}}
            ]
        })
        
        if to_delete == 0:
            return await message.reply_text("No inactive bots to delete.")
            
        await message.reply_text(f"Deleting {to_delete} bots inactive for {days} days...")
        
        # --- 🔥 STOP INACTIVE PROCESSES ---
        bots_to_delete = clonebotdb.find({
            "$or": [
                {"last_activity": {"$lt": limit_date}},
                {"last_activity": {"$exists": False}}
            ]
        })
        async for bot in bots_to_delete:
            bot_id = bot.get("bot_id")
            if bot_id in ACTIVE_CLONES:
                try:
                    await ACTIVE_CLONES[bot_id].stop()
                    del ACTIVE_CLONES[bot_id]
                except:
                    pass
        # ----------------------------------

        await clonebotdb.delete_many({
            "$or": [
                {"last_activity": {"$lt": limit_date}},
                {"last_activity": {"$exists": False}}
            ]
        })
        
        await message.reply_text(f"**✅ Successfully deleted {to_delete} inactive bots!**\n\nNote: Please restart the bot to clear memory cache.")
        
    except Exception as e:
        await message.reply_text(f"Error: {e}")
