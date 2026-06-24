import random
from pyrogram.types import InlineKeyboardButton
from pyrogram.enums import ButtonStyle
import config
from PritiMusic import app

# 🔥 PREMIUM EMOJIS LIST 🔥
PREMIUM_EMOJIS = [
    "5422831825178206894", 
    "5368324170673489600",
    "5206607081334906820",
    "5206380668048496464"
]

# 🎨 Dynamic Color Generator (Random Styles)
def get_style_map():
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
    random.shuffle(styles)
    # Row me buttons ke hisaab se random color assign hoga
    return {1: styles[0], 2: styles[1], 3: styles[2]}

# 🔘 Smart Button Creator (Fixed user_id link)
def create_btn(text, cb=None, url=None, user_id=None, style=ButtonStyle.PRIMARY, no_emoji=False):
    kwargs = {"text": text, "style": style}
    if cb: 
        kwargs["callback_data"] = cb
    # User profile kholne ke liye direct link
    if user_id: 
        kwargs["url"] = f"tg://user?id={user_id}"
    elif url: 
        kwargs["url"] = url
        
    if not no_emoji: 
        kwargs["icon_custom_emoji_id"] = random.choice(PREMIUM_EMOJIS)
        
    return InlineKeyboardButton(**kwargs)


def start_panel(_):
    s_map = get_style_map()
    buttons = [
        [
            create_btn(
                text=_["SO_B_1"], 
                url=f"https://t.me/{app.username}?startgroup=true",
                style=s_map[2]
            ),
            create_btn(
                text=_["S_B_2"], 
                url=config.SUPPORT_CHAT, 
                style=s_map[2]
            ),
        ],
    ]
    return buttons


def private_panel(_):
    s_map = get_style_map()
    buttons = [
        [
            create_btn(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?startgroup=true",
                style=s_map[1]
            )
        ],
        [
            create_btn(
                text=_["S_B_5"], 
                user_id=config.OWNER_ID, 
                style=s_map[2]
            ),
            create_btn(
                text="ᴄʟᴏɴᴇ", 
                cb="clone_page", 
                style=s_map[2]
            )
        ],
        [
            create_btn(
                text="sᴜᴘᴘᴏʀᴛ", 
                cb="support_page", 
                style=s_map[2]
            ),
            create_btn(
                text="sᴏᴜʀᴄᴇ", 
                cb="gib_source", 
                style=s_map[2]
            )
        ],
        [
            create_btn(
                text=_["S_B_4"], 
                cb="settingsback_helper", 
                style=s_map[1]
            )
        ],
    ]
    return buttons


def support_panel(_):
    s_map = get_style_map()
    buttons = [
        [
            create_btn(
                text=_["S_B_2"], 
                url=config.SUPPORT_CHAT, 
                style=s_map[2]
            ),
            create_btn(
                text=_["S_B_6"], 
                url=config.SUPPORT_CHANNEL, 
                style=s_map[2]
            ),
        ],
        [
            create_btn(
                text=_["BACK_BUTTON"], 
                cb="settingsback_helper", 
                style=s_map[1]
            )
        ]
    ]
    return buttons


def about_panel(_):
    s_map = get_style_map()
    buttons = [
        [
            create_btn(
                text=_["S_B_5"], 
                user_id=config.OWNER_ID, 
                style=s_map[2]
            ),
            create_btn(
                text=_["S_B_11"], 
                url=config.GITHUB, 
                style=s_map[2]
            ),
        ],
        [
            create_btn(
                text=_["S_B_6"], 
                url=config.SUPPORT_CHANNEL, 
                style=s_map[2]
            ),
            create_btn(
                text=_["S_B_2"], 
                url=config.SUPPORT_CHAT, 
                style=s_map[2]
            )
        ],
        [
            create_btn(
                text=_["BACK_BUTTON"], 
                cb="settingsback_helper", 
                style=s_map[1]
            )
        ]
    ]
    return buttons
    
