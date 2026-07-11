import os
import time
import asyncio
import gc  # 🚀 Added this for RAM (Memory) cleanup
import shutil # 🚀 Added for checking server free space
import config
from config import autoclean
from PritiMusic import LOGGER, app
from pyrogram import filters
from pyrogram.types import Message

# Settings
WEEK_IN_SECONDS = 7 * 24 * 60 * 60
ONE_DAY_IN_SECONDS = 24 * 60 * 60 # 1 din (24 hours) ke liye limit
FIVE_MINS_IN_SECONDS = 5 * 60 # 🚀 5 Minutes limit for images
MAX_CACHE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB limit
MAX_FILE_SIZE = 500 * 1024 * 1024 # 500 MB limit

async def auto_clean(popped):
    try:
        current_time = time.time()
        
        # 🚀 1. Auto-Delete Profile Pics & Welcome Images older than 5 minutes
        image_directory = "./downloads"
        if os.path.exists(image_directory):
            for img_file in os.listdir(image_directory):
                # Sirf image files (.png, .jpg, .jpeg) ko target karega
                if img_file.lower().endswith((".png", ".jpg", ".jpeg")):
                    img_path = os.path.join(image_directory, img_file)
                    if os.path.isfile(img_path):
                        img_age = current_time - os.path.getctime(img_path)
                        if img_age > FIVE_MINS_IN_SECONDS:
                            try:
                                os.remove(img_path)
                                LOGGER(__name__).info(f"🗑️ Auto-deleted old image: {img_file}")
                            except Exception:
                                pass

        if not popped:
            return
            
        rem = popped.get("file")
        if not rem:
            return

        # 2. Remove from the active playing list
        try:
            autoclean.remove(rem)
        except ValueError:
            pass
            
        if not os.path.exists(rem):
            return

        # 3. Identify the folder where songs are being saved
        directory = os.path.dirname(rem)
        if not directory or not os.path.exists(directory):
            return

        deleted_files = []
        deleted_large_files = []
        all_files = []
        current_cache_size = 0
        
        # 4. Check and DELETE > 500MB file immediately after it finishes playing
        rem_size = os.path.getsize(rem)
        if rem_size > MAX_FILE_SIZE:
            try:
                os.remove(rem)
                deleted_large_files.append(os.path.basename(rem))
                LOGGER(__name__).info(f"🗑️ Deleted >500MB file immediately: {rem}")
            except Exception as e:
                LOGGER(__name__).warning(f"⚠️ Failed to delete large file {rem}: {e}")

        # 5. Gather all files and calculate total cache size
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                # Skip live streams or active index files
                if "live_" not in filepath and "index_" not in filepath:
                    f_size = os.path.getsize(filepath)
                    f_age = current_time - os.path.getctime(filepath)
                    
                    all_files.append({
                        "path": filepath, 
                        "name": filename, 
                        "size": f_size, 
                        "age": f_age
                    })
                    current_cache_size += f_size
                    
        # Sort files by age (Sabse purane files list mein upar aayenge)
        all_files.sort(key=lambda x: x["age"], reverse=True)
        
        # 6. Delete files if older than 7 days OR if storage limit is exceeded
        for f in all_files:
            filepath = f["path"]
            
            # Agar file already 500MB check me delete ho gayi hai, toh skip karo
            if not os.path.exists(filepath):
                continue
                
            # Delete condition: File age > 7 days YAA Cache limit paar ho gaya ho
            if (f["age"] > WEEK_IN_SECONDS or current_cache_size > MAX_CACHE_SIZE) and filepath not in autoclean:
                try:
                    os.remove(filepath)
                    deleted_files.append(f["name"])
                    current_cache_size -= f["size"] # Minus size from total after deletion
                    LOGGER(__name__).info(f"🗑️ Cleaned cached file: {filepath}")
                except Exception as e:
                    LOGGER(__name__).warning(f"⚠️ Failed to clean file {filepath}: {e}")
                    
        # 7. Send notification to the logger group
        logger_id = getattr(config, "LOG_GROUP_ID", getattr(config, "LOGGER_ID", None))
        if logger_id:
            log_text = ""
            
            if deleted_large_files:
                formatted_large = "\n".join([f"> `{name}`" for name in deleted_large_files])
                log_text += f"🚨 **Big File Auto-Cleaned (>500MB)**\n{formatted_large}\n\n"
                
            if deleted_files:
                formatted_songs = "\n".join([f"> `{name}`" for name in deleted_files])
                if len(formatted_songs) > 3000:
                    formatted_songs = formatted_songs[:3000] + "\n> `...aur baaki files.`"
                    
                log_text += (
                    "🗑️ **Storage Cache Cleaned**\n\n"
                    "**Neeche diye gaye purane songs space free karne ke liye delete kiye gaye hain:**\n"
                    f"{formatted_songs}"
                )
                
            if log_text:
                try:
                    await app.send_message(int(logger_id), log_text)
                except Exception as e:
                    LOGGER(__name__).warning(f"Failed to send Cache Log to GC: {e}")

        # 8. FORCE RAM CLEANUP
        collected = gc.collect()
        if collected > 0:
            LOGGER(__name__).info(f"🧹 RAM Garbage Collector freed {collected} unused memory objects.")

    except Exception as e:
        LOGGER(__name__).error(f"Auto-Clean Error: {e}")


# 🚀 9. COMMAND: /cdust (Manual cleanup for files older than 1 day)
@app.on_message(filters.command("cdust") & filters.user(config.OWNER_ID))
async def clean_dust_command(client, message: Message):
    m = await message.reply_text("⏳ `Scanning dust... checking files older than 1 day...`")
    
    # Changed to check both music and download folders
    directories = ["./downloads", "./music_cache"]
    current_time = time.time()
    deleted_count = 0
    freed_space = 0
    deleted_files_list = []

    try:
        for directory in directories:
            if not os.path.exists(directory):
                continue
                
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    if "live_" not in filepath and "index_" not in filepath:
                        f_age = current_time - os.path.getctime(filepath)
                        
                        # Agar file 1 din se purani hai
                        if f_age > ONE_DAY_IN_SECONDS and filepath not in autoclean:
                            f_size = os.path.getsize(filepath)
                            try:
                                os.remove(filepath)
                                deleted_count += 1
                                freed_space += f_size
                                deleted_files_list.append(filename)
                            except:
                                pass

        gc.collect()

        if deleted_count > 0:
            freed_mb = round(freed_space / (1024 * 1024), 2)
            
            await m.edit_text(
                f"🧹 **Dust Cleaned Successfully!**\n\n"
                f"🗑 **Deleted Files:** `{deleted_count}`\n"
                f"💾 **Freed Space:** `{freed_mb} MB`\n"
                f"📝 **Note:** `Details sent to Logger Group.`"
            )
            
            logger_id = getattr(config, "LOG_GROUP_ID", getattr(config, "LOGGER_ID", None))
            if logger_id and deleted_files_list:
                formatted_dust = "\n".join([f"> `{name}`" for name in deleted_files_list])
                
                if len(formatted_dust) > 3000:
                    formatted_dust = formatted_dust[:3000] + "\n> `...aur baaki files.`"
                    
                log_text = (
                    f"🧹 **Manual Dust Cleaned (/cdust)**\n\n"
                    f"**Total {freed_mb} MB space free kiya gaya.**\n"
                    f"**Neeche diye gaye 1 din se purane files delete kiye gaye hain:**\n"
                    f"{formatted_dust}"
                )
                try:
                    await app.send_message(int(logger_id), log_text)
                except:
                    pass
        else:
            await m.edit_text("✨ `No dusty files found. Storage is already clean! (Kept files from the last 24 hours)`")
            
    except Exception as e:
        await m.edit_text(f"⚠️ **Error occurred:** `{e}`")


# 🚀 10. COMMAND: /downloads (Check total storage usage and file list)
@app.on_message(filters.command("downloads") & filters.user(config.OWNER_ID))
async def check_downloads_command(client, message: Message):
    m = await message.reply_text("⏳ `Checking server storage and downloaded files...`")
    
    # Checks both folders to show true storage footprint
    directories = ["./downloads", "./music_cache"]
    total_files = 0
    total_size_bytes = 0
    file_list = []
    
    try:
        for directory in directories:
            if not os.path.exists(directory):
                continue
                
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    if "live_" not in filepath and "index_" not in filepath:
                        total_files += 1
                        f_size = os.path.getsize(filepath)
                        total_size_bytes += f_size
                        
                        f_size_mb = round(f_size / (1024 * 1024), 2)
                        
                        # Add a tiny icon depending on file type
                        icon = "🖼️" if filename.endswith((".png", ".jpg")) else "🎧"
                        file_list.append(f"{icon} `{filename}` ({f_size_mb} MB)")
                    
        # Check Server Free Space on the root directory
        disk_info = shutil.disk_usage(".")
        server_free_gb = round(disk_info.free / (1024 * 1024 * 1024), 2)
        server_total_gb = round(disk_info.total / (1024 * 1024 * 1024), 2)
        
        if total_size_bytes >= (1024 * 1024 * 1024):
            size_formatted = f"{round(total_size_bytes / (1024 * 1024 * 1024), 2)} GB"
        else:
            size_formatted = f"{round(total_size_bytes / (1024 * 1024), 2)} MB"
            
        header_text = (
            f"📁 **Server Storage Status**\n\n"
            f"💽 **Server Total Space:** `{server_total_gb} GB`\n"
            f"🟢 **Server Free Space:** `{server_free_gb} GB`\n\n"
            f"🎵 **Total Cached Files:** `{total_files}`\n"
            f"💾 **Space Occupied by Bot:** `{size_formatted}`\n\n"
            f"📑 **Downloaded File List:**\n"
        )
        
        if file_list:
            songs_text = "\n".join(file_list)
        else:
            songs_text = "`No downloaded files found.`"
            
        footer_text = "\n\n💡 _Tip: Storage clean karne ke liye /cdust ka use karein._"
        
        full_text = header_text + songs_text + footer_text
        
        if len(full_text) > 4000:
            allowed_length = 4000 - len(header_text) - len(footer_text) - 50
            truncated_songs = songs_text[:allowed_length]
            truncated_songs = truncated_songs.rsplit('\n', 1)[0] 
            full_text = header_text + truncated_songs + "\n\n... `aur baaki files (Message too long)`" + footer_text
            
        await m.edit_text(full_text)
        
    except Exception as e:
        await m.edit_text(f"⚠️ **Error occurred:** `{e}`")
