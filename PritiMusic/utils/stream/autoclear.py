import os
import time
import asyncio
import config
from config import autoclean
from PritiMusic import LOGGER, app

# Settings
WEEK_IN_SECONDS = 7 * 24 * 60 * 60
MAX_CACHE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB limit (Aap isko apne VPS storage ke hisaab se change kar sakte hain)

async def auto_clean(popped):
    try:
        if not popped:
            return
            
        rem = popped.get("file")
        if not rem:
            return

        # 1. Remove from the active playing list
        try:
            autoclean.remove(rem)
        except ValueError:
            pass

        # 2. Identify the folder where songs are being saved
        directory = os.path.dirname(rem)
        if not directory or not os.path.exists(directory):
            return

        current_time = time.time()
        deleted_files = []
        all_files = []
        current_cache_size = 0
        
        # 3. Gather all files and calculate total cache size
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
        
        # 4. Delete files if older than 7 days OR if storage limit is exceeded
        for f in all_files:
            filepath = f["path"]
            
            # Delete condition: File age > 7 days YAA Cache limit par ho gaya ho
            if (f["age"] > WEEK_IN_SECONDS or current_cache_size > MAX_CACHE_SIZE) and filepath not in autoclean:
                try:
                    os.remove(filepath)
                    deleted_files.append(f["name"])
                    current_cache_size -= f["size"] # Minus size from total after deletion
                    LOGGER(__name__).info(f"🗑️ Cleaned cached file: {filepath}")
                except Exception as e:
                    LOGGER(__name__).warning(f"⚠️ Failed to clean file {filepath}: {e}")
                    
        # 5. Send notification to the logger group in blockquotes format
        if deleted_files:
            logger_id = getattr(config, "LOG_GROUP_ID", getattr(config, "LOGGER_ID", None))
            if logger_id:
                # Quarts/Blockquotes format (> song_name)
                formatted_songs = "\n".join([f"> `{name}`" for name in deleted_files])
                
                # Agar list bohot lambi ho gayi, toh Telegram message limit (4096 chars) se bachne ke liye truncate karna padega
                if len(formatted_songs) > 3500:
                    formatted_songs = formatted_songs[:3500] + "\n> `...aur baaki files.`"
                    
                log_text = (
                    "🗑️ **Storage Cache Cleaned**\n\n"
                    "**Neeche diye gaye purane songs space free karne ke liye delete kiye gaye hain:**\n"
                    f"{formatted_songs}"
                )
                
                try:
                    await app.send_message(int(logger_id), log_text)
                except Exception as e:
                    LOGGER(__name__).warning(f"Failed to send Cache Log to GC: {e}")

    except Exception as e:
        LOGGER(__name__).error(f"Auto-Clean Error: {e}")
