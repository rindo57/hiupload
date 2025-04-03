import os
import sys
import asyncio
import time
from tqdm import tqdm
import logging
from pathlib import Path

from config import BOT_TOKENSX
from utils.clients import initialize_clients2
from utils.directoryHandler import getRandomID
from utils.uploader import start_file_uploader2

# Configure logging: Log messages will be output to the console and saved in manager.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("manager.log", mode="a")],
)
logger = logging.getLogger(__name__)

def convert_class_to_dict(data, isObject, showtrash=False):
    if isObject == True:
        data = data.__dict__.copy()
    new_data = {"contents": {}}

    for key in data["contents"]:
        if data["contents"][key].trash == showtrash:
            if data["contents"][key].type == "folder":
                folder = data["contents"][key]
                new_data["contents"][key] = {
                    "name": folder.name,
                    "type": folder.type,
                    "id": folder.id,
                    "path": folder.path,
                    "upload_date": folder.upload_date,
                }
            else:
                file = data["contents"][key]
                new_data["contents"][key] = {
                    "name": file.name,
                    "type": file.type,
                    "size": file.size,
                    "id": file.id,
                    "path": file.path,
                    "upload_date": file.upload_date,
                }
    return new_data

def get_all_folders(root_folder):
    """Get immediate subdirectories (not recursive) from the given folder."""
    try:
        folders = [
            str(item)
            for item in Path(root_folder).iterdir()
            if item.is_dir()
        ]
        logger.info(f"Found folders in {root_folder}: {folders}")
        return folders
    except Exception as e:
        logger.error(f"Error getting folders from {root_folder}: {e}")
        return []

def get_all_files(root_folder):
    """Get only the files in the given directory (no subdirectories)."""
    try:
        files = [
            str(item)
            for item in Path(root_folder).iterdir()
            if item.is_file()
        ]
        logger.info(f"Found files in {root_folder}: {files}")
        return files
    except Exception as e:
        logger.error(f"Error getting files from {root_folder}: {e}")
        return []

def getCpath(name, cparent):
    from utils.directoryHandler import DRIVE_DATA

    try:
        folder_data = DRIVE_DATA.get_directory(cparent)
        logger.debug(f"folder 1 {folder_data}")
        folder_data = convert_class_to_dict(folder_data, isObject=True, showtrash=False)
        logger.debug(f"folder 2 {folder_data}")
        logger.debug(f"folder items: {folder_data['contents'].items()}")
        for id, data in folder_data["contents"].items():
            if data["name"] == name:
                logger.info(
                    f"Found existing cloud folder '{name}' with id {id} under {cparent}"
                )
                return ("/" + data["path"] + id + "/").replace("//", "/")
    except Exception as e:
        logger.error(f"Exception in getCpath: {e}")
    return False

RUNNING_IDS = []
TOTAL_UPLOAD = 0
upload_queue = asyncio.Queue()

async def worker():
    """Worker to process upload tasks from the queue."""
    while True:
        try:
            file, id, cpath, fname, file_size, b = await upload_queue.get()
        except asyncio.CancelledError:
            break

        logger.info(f"Starting upload for '{fname}' with id {id}")
        try:
            uploader_name = "XenZen"  # Changed variable name to avoid conflict
            await start_file_uploader2(file, id, cpath, fname, file_size, uploader_name)
            await asyncio.sleep(11)
        except Exception as e:
            with open("failed.txt", "a", encoding='utf-8') as f:
                f.write(f"{file}\n")
            logger.error(f"Failed to upload '{fname}' with id {id}: {e}")
        from utils.uploader import PROGRESS_CACHE
        PROGRESS_CACHE[id] = ("completed", file_size, file_size)
        logger.info(f"Completed upload for '{fname}' with id {id}")
        upload_queue.task_done()
        logger.debug(f"Upload queue task done: {upload_queue}")

async def limited_uploader_progress():
    global RUNNING_IDS, TOTAL_UPLOAD
    logger.info(f"Total upload size: {TOTAL_UPLOAD} bytes")
    logger.info("Starting upload progress tracking")
    no_progress_counter = 0
    loop = asyncio.get_running_loop()
    
    with tqdm(
        total=TOTAL_UPLOAD,
        unit="B",
        unit_scale=True,
        desc="Uploading",
        dynamic_ncols=True,
    ) as pbar:
        prev_done = 0
        while True:
            from utils.uploader import PROGRESS_CACHE

            done = 0
            complete = 0
            for id in RUNNING_IDS:
                x = PROGRESS_CACHE.get(id, ("running", 0, 0))
                done += x[1]
                if x[0] == "completed":
                    complete += 1
            delta = done - prev_done

            await loop.run_in_executor(None, pbar.update, delta)
            prev_done = done

            if complete == len(RUNNING_IDS):
                break

            if delta == 0:
                no_progress_counter += 1
            else:
                no_progress_counter = 0

            if no_progress_counter >= 30:
                logger.error(
                    "Upload progress seems to be stuck. Aborting progress tracking."
                )
                break

            await asyncio.sleep(5)
    logger.info("Upload progress tracking ended")

async def start():
    # Get user inputs
    root_folder = input("Enter the path of the local folder to upload: ").strip()
    root_name = input("Enter the name of the root folder in the Hi-Drive: ").strip()
    uploader = input("Uploader Name?: ").strip()
    
    # Convert to Path object for consistent path handling
    root_folder = str(Path(root_folder).resolve())
    
    logger.info("Initializing clients...")
    await initialize_clients2()

    DRIVE_DATA = None
    while not DRIVE_DATA:
        from utils.directoryHandler import DRIVE_DATA
        await asyncio.sleep(3)
        logger.info("Waiting for DRIVE_DATA to be initialized...")

    max_concurrent_tasks = 1
    logger.info(f"Maximum concurrent upload tasks set to: {max_concurrent_tasks}")

    global RUNNING_IDS, TOTAL_UPLOAD

    def upload_files(lpath, cpath):
        global TOTAL_UPLOAD
        files = get_all_files(lpath)
        for file in files:
            fname = Path(file).name
            new_cpath = getCpath(fname, cpath)
            if new_cpath:
                logger.info(
                    f"Skipping upload for '{fname}' as it already exists in cloud at {new_cpath}"
                )
                continue
            try:
                file_size = os.path.getsize(file)
            except Exception as e:
                with open("failed.txt", "a", encoding='utf-8') as f:
                    f.write(f"{file}\n")
                logger.error(f"Failed to get size for '{fname}': {e}")
                continue
            id = getRandomID()
            RUNNING_IDS.append(id)
            logger.info(
                f"Added file upload task for '{fname}' with id {id} in cloud path {cpath}"
            )
            TOTAL_UPLOAD += file_size
            try:
                upload_queue.put_nowait((file, id, cpath, fname, file_size, False))
            except asyncio.QueueFull:
                logger.error(f"Queue full! Could not add '{fname}' to upload queue.")

    root_cpath = getCpath(root_name, "/")
    if root_cpath:
        logger.info(
            f"Root folder '{root_name}' already exists in cloud at {root_cpath}"
        )
    else:
        logger.info(f"Creating root folder '{root_name}' in cloud")
        root_cpath = DRIVE_DATA.new_folder("/", root_name, uploader)
        logger.info(f"Created root folder '{root_name}' in cloud at {root_cpath}")

    upload_files(root_folder, root_cpath)

    def create_folders(lpath, cpath):
        folders = get_all_folders(lpath)
        logger.debug(f"Found subfolders: {folders}")
        for new_lpath in folders:
            folder_name = Path(new_lpath).name
            new_cpath = getCpath(folder_name, cpath)
            if not new_cpath:
                logger.info(
                    f"Creating cloud folder for local folder '{folder_name}' under {cpath}"
                )
                new_cpath = DRIVE_DATA.new_folder(cpath, folder_name, uploader)
                logger.info(f"Created cloud folder '{folder_name}' at {new_cpath}")
            upload_files(new_lpath, new_cpath)
            create_folders(new_lpath, new_cpath)
            logger.info(f"Processed local folder: {new_lpath}")

    create_folders(root_folder, root_cpath)
    logger.info("All upload tasks have been scheduled. Waiting for completion...")

    workers = [asyncio.create_task(worker()) for _ in range(max_concurrent_tasks)]
    progress_task = asyncio.create_task(limited_uploader_progress())

    await upload_queue.join()

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    await progress_task

    logger.info("All uploads completed successfully.")
    logger.info("Backup completed successfully.")
    logger.info("Exiting...")
    await asyncio.sleep(1)
    sys.exit()

if __name__ == "__main__":
    if sys.platform == "win32":
        # Windows-specific event loop policy
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        sys.exit()
