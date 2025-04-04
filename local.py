import os
import sys
import asyncio
import time
from tqdm import tqdm
import logging
import shutil  # Add at the top

from config import BOT_TOKENSX
from utils.clients import initialize_clients2
from utils.directoryHandler import getRandomID
from utils.uploader import start_file_uploader2
# Enable detailed pyrogram logging
import pyrogram
root_folder = input("Enter the path of the local folder to upload: ").strip()
# Or convert to raw string
root_folder = os.path.normpath(root_folder)
root_name = input("Enter the name of the root folder in the Hi-Drive: ").strip()
uploader = input("Enter Uploader? ").strip()


# Configure logging: Log messages will be output to the console and saved in manager.log
# At the beginning of your script, after imports
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("manager.log", mode="a")
    ],
)
logger = logging.getLogger(__name__)

# At the start of the main function:
logger.debug(f"Root folder path: {os.path.abspath(root_folder)}")
logger.debug(f"Root folder exists: {os.path.exists(root_folder)}")

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
# Get immediate subdirectories (not recursive) from the given folder.
def get_all_folders(root_folder):
    folders = [
        os.path.join(root_folder, d)
        for d in os.listdir(root_folder)
        if os.path.isdir(os.path.join(root_folder, d))
    ]
    logger.info(f"Found folders in {root_folder}: {folders}")
    return folders


# Get only the files in the given directory (no subdirectories).
def get_all_files(root_folder):
    files = []
    for f in os.listdir(root_folder):
        file_path = os.path.normpath(os.path.join(root_folder, f))
        if os.path.isfile(file_path):
            files.append(file_path)
            logger.debug(f"Found valid file: {file_path}")
        else:
            logger.debug(f"Skipping non-file: {file_path}")
    logger.info(f"Found {len(files)} files in {root_folder}")
    return files


# Get cloud path for a folder with the given name under a given cloud parent path.
def getCpath(name, cparent):
    from utils.directoryHandler import DRIVE_DATA

    try:
        folder_data = DRIVE_DATA.get_directory(cparent)
        print("folder 1 ", folder_data)
        folder_data = convert_class_to_dict(folder_data, isObject=True, showtrash=False)
        print("folder 2 ", folder_data)
        print("folder items: ", folder_data["contents"].items())
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

# Use an asyncio.Queue for upload tasks. Each task is a tuple:
# (file, id, cpath, fname, file_size, b)
upload_queue = asyncio.Queue()

async def worker():
    """Worker to process upload tasks from the queue."""
    while True:
        try:
            file, id, cpath, fname, file_size, b = await upload_queue.get()
            file = os.path.abspath(file)
            
            # Enhanced file verification
            if not os.path.exists(file):
                logger.error(f"File not found: {file}")
                continue
                
            if not os.access(file, os.R_OK):
                logger.error(f"No read permissions: {file}")
                continue
                
            try:
                # Test file opening
                with open(file, 'rb') as f:
                    pass
            except Exception as e:
                logger.error(f"File access test failed: {file} - {str(e)}")
                continue
                
            logger.info(f"Starting upload for {file} (Size: {file_size})")
            
            try:
                # Create a temporary copy if original fails
                temp_file = None
                try:
                    await start_file_uploader2(file, id, cpath, fname, file_size, uploader)
                except Exception as e:
                    logger.warning(f"First upload attempt failed, trying with temp copy: {str(e)}")
                    import tempfile
                    temp_dir = tempfile.mkdtemp()
                    temp_file = os.path.join(temp_dir, os.path.basename(file))
                    shutil.copy2(file, temp_file)
                    await start_file_uploader2(temp_file, id, cpath, fname, file_size, uploader)
            except Exception as e:
                logger.error(f"Upload failed: {str(e)}")
                with open("failed.txt", "a") as f:
                    f.write(f"{file}\n")
            finally:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                    os.rmdir(temp_dir)
                    
        except asyncio.CancelledError:
            break
            
        from utils.uploader import PROGRESS_CACHE
        PROGRESS_CACHE[id] = ("completed", file_size, file_size)
        upload_queue.task_done()
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

            # Offload the blocking update to a thread.
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

    # Schedule upload tasks for all files in a folder.
    def upload_files(lpath, cpath):
        global TOTAL_UPLOAD
        files = get_all_files(lpath)
        for file in files:
            fname = os.path.basename(file)
        # Verify the file exists before proceeding
            if not os.path.exists(file):
                logger.error(f"File not found: {file}")
                with open("failed.txt", "a") as f:
                    f.write(f"{file} (File not found)\n")
                continue
            
        # Check if the file already exists in the cloud.
            new_cpath = getCpath(fname, cpath)
            if new_cpath:
                logger.info(
                    f"Skipping upload for '{fname}' as it already exists in cloud at {new_cpath}"
                )
                continue
            
            try:
                file_size = os.path.getsize(file)
                logger.info(f"Found file: {file} (Size: {file_size} bytes)")
            except Exception as e:
                with open("failed.txt", "a") as f:
                    f.write(f"{file}\n")
                logger.error(f"Failed to get size for '{fname}': {e}")
                continue
            
            id = getRandomID()
            RUNNING_IDS.append(id)
            logger.info(
                f"Added file upload task for '{fname}' with id {id} in cloud path {cpath}"
            )
            TOTAL_UPLOAD += file_size
        
        # Enqueue the upload task
            try:
                upload_queue.put_nowait((file, id, cpath, fname, file_size, False))
                logger.info(f"Successfully queued file: {file}")
            except asyncio.QueueFull:
                logger.error(f"Queue full! Could not add '{fname}' to upload queue.")


    # Create the root folder in the cloud if it does not exist.
    root_cpath = getCpath(root_name, "/")
    if root_cpath:
        logger.info(
            f"Root folder '{root_name}' already exists in cloud at {root_cpath}"
        )
    else:
        logger.info(f"Creating root folder '{root_name}' in cloud")
        root_cpath = DRIVE_DATA.new_folder("/", root_name, uploader)
        logger.info(f"Created root folder '{root_name}' in cloud at {root_cpath}")

    # Upload files in the root local folder.
    upload_files(root_folder, root_cpath)

    # Recursively create folders and schedule file uploads.
    def create_folders(lpath, cpath):
        folders = get_all_folders(lpath)
        print("folders", folders)
        
        for new_lpath in folders:
            print("cpath ", cpath)
            folder_name = os.path.basename(new_lpath)
            print("folder name ", folder_name)
            new_cpath = getCpath(folder_name, cpath)
            if not new_cpath:
                logger.info(
                    f"Creating cloud folder for local folder '{folder_name}' under {cpath}"
                )
                
                new_cpath = DRIVE_DATA.new_folder(cpath, folder_name, uploader)
                logger.info(f"Created cloud folder '{folder_name}' at {new_cpath}")
            # Schedule uploads for files in the current folder.
            upload_files(new_lpath, new_cpath)
            # Recursively process subfolders.
            create_folders(new_lpath, new_cpath)
            logger.info(f"Processed local folder: {new_lpath}")

    create_folders(root_folder, root_cpath)
    logger.info("All upload tasks have been scheduled. Waiting for completion...")

    # Start worker tasks.
    workers = [asyncio.create_task(worker()) for _ in range(max_concurrent_tasks)]
    progress_task = asyncio.create_task(limited_uploader_progress())

    # Wait until the upload queue is fully processed.
    await upload_queue.join()

    # Cancel worker tasks.
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
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start())
