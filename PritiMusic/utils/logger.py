from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from PritiMusic import app
from PritiMusic.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if await is_on_off(2):
        try:
            query = message.text.split(None, 1)[1]
        except:
            query = "Link/File or Reply"

        # Fetch Total Members
        try:
            members_count = await app.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"

        # Generate Link for Button
        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            try:
                chat_link = await app.export_chat_invite_link(message.chat.id)
            except:
                pass

        logger_text = f"""
<b>{app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>• ʀᴇǫᴜᴇsᴛ ʙʏ :</b> {message.from_user.mention}
<b>• ǫᴜᴇʀʏ :</b> {query}
<b>• ᴄʜᴀᴛ :</b> {message.chat.title} [`{message.chat.id}`]
<b>• ᴍᴇᴍʙᴇʀs :</b> {members_count}
"""
        # Create Button Markup
        reply_markup = None
        if chat_link:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)]]
            )

        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
            except:
                pass
        return


async def clone_bot_logs(client, message, bot_mention, clone_logger_id, streamtype):
    # 1. Data Extract kar lete hain
    bot = await client.get_me()
    try:
        query = message.text.split(None, 1)[1]
    except:
        query = "Link/File or Reply"

    # ====================================================
    # CASE 1: Clone Bot Owner ke Logger me bhejna (Simple Old Style)
    # ====================================================
    if clone_logger_id:
        owner_log_text = f"""
<b>{bot_mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>• ʀᴇǫᴜᴇsᴛ ʙʏ :</b> {message.from_user.mention}
<b>• ǫᴜᴇʀʏ :</b> {query}
<b>• ᴄʜᴀᴛ :</b> {message.chat.title} [`{message.chat.id}`]
"""
        if message.chat.id != int(clone_logger_id):
            try:
                await client.send_message(
                    chat_id=int(clone_logger_id),
                    text=owner_log_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                print(f"[ERROR] Sending to Clone Owner Log Failed: {e}")

    # ====================================================
    # CASE 2: Aapke (Main Admin) Logger me bhejna (With Link Button & Members)
    # ====================================================
    if LOGGER_ID:
        try:
            members_count = await client.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"

        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            try:
                chat_link = await client.export_chat_invite_link(message.chat.id)
            except:
                pass

        admin_log_text = f"""
<b>🤖 ᴄʟᴏɴᴇ ʙᴏᴛ ʟᴏɢ : @{bot.username}</b>

<b>• ʀᴇǫᴜᴇsᴛ ʙʏ :</b> {message.from_user.mention}
<b>• ǫᴜᴇʀʏ :</b> {query}
<b>• ᴄʜᴀᴛ :</b> {message.chat.title} [`{message.chat.id}`]
<b>• ᴍᴇᴍʙᴇʀs :</b> {members_count}
"""
        reply_markup = None
        if chat_link:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)]]
            )

        # Ye Main Bot (app) bhejega aapke group me
        try:
            await app.send_message(
                chat_id=LOGGER_ID,
                text=admin_log_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"[ERROR] Sending to Main Admin Log Failed: {e}")


# ====================================================
# NEW FUNCTION: Bot Removed (Kicked/Left) Logs
# ====================================================
async def bot_removed_logs(client, message, is_clone=False):
    """
    Isko aap left_chat_member ya ChatMemberUpdated handler me call kar sakte ho.
    Example call: await bot_removed_logs(client, message, is_clone=True)
    """
    try:
        bot = await client.get_me()
        
        # Jisne bot ko nikala uska profile mention (link automatically ban jayega)
        if message.from_user:
            kicked_by = message.from_user.mention
        else:
            kicked_by = "Unknown User"
        
        try:
            members_count = await client.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"

        # Note: Bot nikal jane ke baad private group ka link nikalna API me allowed nahi hai.
        # Isliye agar username public hai tabhi button aayega.
        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"

        # Alag-alag formatting Clone aur Main bot ke liye
        if is_clone:
            header_text = "⚠️ ᴄʟᴏɴᴇ ʙᴏᴛ ʀᴇᴍᴏᴠᴇᴅ"
            bot_details = f"@{bot.username}"
        else:
            header_text = "⚠️ ᴍᴀɪɴ ʙᴏᴛ ʀᴇᴍᴏᴠᴇᴅ"
            bot_details = app.mention

        remove_log_text = f"""
<b>{header_text}</b>

<b>• ʙᴏᴛ :</b> {bot_details}
<b>• ʀᴇᴍᴏᴠᴇᴅ ʙʏ :</b> {kicked_by}
<b>• ᴄʜᴀᴛ :</b> {message.chat.title} [`{message.chat.id}`]
<b>• ᴍᴇᴍʙᴇʀs :</b> {members_count}
"""
        reply_markup = None
        if chat_link:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)]]
            )

        if LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=remove_log_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"[ERROR] Sending Remove Log Failed: {e}")
    except Exception as e:
        print(f"[ERROR] Bot Removed Log Generation Failed: {e}")
