from pathlib import Path
import config
import random, string, asyncio
from utils.logger import Logger
from datetime import datetime, timezone
from pymongo import MongoClient
from config import mongo_uri
logger = Logger(__name__)

# MongoDB connection

client = MongoClient(mongo_uri)
db = client.tg_drive  # Database name
drive_data_collection = db.drive_data  # Collection name

drive_data_collectionx = db.drive_ids
def getRandomID(length=15):
    while True:
        id = "".join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=length))
        print("Generated ID:", id)

        # Retrieve or initialize the document
        document = drive_data_collectionx.find_one({})
        if not document:
            drive_data_collectionx.insert_one({"used_ids": []})
            document = {"used_ids": []}

        # Check if the ID already exists in 'used_ids'
        used_ids = document.get("used_ids", [])
        if id not in used_ids:
            used_ids.append(id)
            drive_data_collectionx.update_one(
                {}, 
                {"$set": {"used_ids": used_ids}}, 
                upsert=True
            )
            print("Updated ID:", id)
            return id

'''
        if not drive_data_collection.find_one({"used_ids": id}):
            # Use upsert to ensure document creation if not found
            result = drive_data_collection.update_one(
                {}, 
                {"$push": {"used_ids": id}}, 
                upsert=True
            )
            if result.modified_count > 0 or result.upserted_id is not None:
                print("after ", id)
                return id
'''
def get_current_utc_time():
    return datetime.now(timezone.utc).strftime("Date - %Y-%m-%d | Time - %H:%M:%S")

  
class Folder:
    def __init__(self, name: str, id: str, path: str, uploader: str) -> None:
        self.name = name
        self.contents = {}  # Initialize contents as a dictionary
        if name == "/":
            self.id = "root"
            self.path = "/"  # Ensure root folder has a valid path
        else:
            self.id = id
            # Remove trailing slash if present
            self.path = ("/" + path.strip("/") + "/").replace("//", "/")
        self.type = "folder"
        self.trash = False
        self.upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.uploader = uploader
        self.auth_hashes = []
    
    def to_dict(self):
        return {
            "name": self.name,
            "contents": {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.contents.items()},
            "id": self.id,
            "type": self.type,
            "trash": self.trash,
            "path": self.path,
            "upload_date": self.upload_date,
            "uploader": self.uploader,
            "auth_hashes": self.auth_hashes,
        }
    @classmethod
    def from_dict(cls, data):
        # Ensure path is not missing or empty
        path = data.get("path", "/")
        folder = cls(data["name"], data["id"], path, data["uploader"])
        folder.contents = {
            k: Folder.from_dict(v) if v["type"] == "folder" else File.from_dict(v)
            for k, v in data["contents"].items()
        }
       # folder.id = data["id"]
        folder.trash = data["trash"]
        folder.upload_date = data["upload_date"]
        #folder.uploader = data["uploader"]
        folder.auth_hashes = data.get("auth_hashes", [])
        return folder



class File:
    def __init__(
        self,
        name: str,
        file_id: int,
        id: str,
        size: int,
        path: str,
        rentry_link: str,
        paste_url: str,
        uploader: str,
        audio: str,
        subtitle: str,
        resolution: str,
        codec: str,
        bit_depth: str,
        duration: str,
    ) -> None:
        self.name = name
        self.file_id = file_id
        self.id = id
        self.size = size
        self.type = "file"
        self.trash = False
        # Handle empty path
        self.path = path[:-1] if path[-1] == "/" else path
        self.upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.rentry_link = rentry_link
        self.paste_url = paste_url
        self.uploader = uploader
        self.audio = audio
        self.subtitle = subtitle
        self.resolution = resolution
        self.codec = codec
        self.bit_depth = bit_depth
        self.duration = duration

    def to_dict(self):
        return {
            "name": self.name,
            "file_id": self.file_id,
            "id": self.id,
            "size": self.size,
            "type": self.type,
            "trash": self.trash,
            "path": self.path,
            "upload_date": self.upload_date,
            "rentry_link": self.rentry_link,
            "paste_url": self.paste_url,
            "uploader": self.uploader,
            "audio": self.audio,
            "subtitle": self.subtitle,
            "resolution": self.resolution,
            "codec": self.codec,
            "bit_depth": self.bit_depth,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data):
    # Ensure path is not missing or empty
        path = data.get("path", "")
        return cls(
            name=data["name"],
            file_id=data["file_id"],
            id=data["id"],
            size=data["size"],
            path=path,
            rentry_link=data["rentry_link"],
            paste_url=data["paste_url"],
            uploader=data["uploader"],
            audio=data["audio"],
            subtitle=data["subtitle"],
            resolution=data["resolution"],
            codec=data["codec"],
            bit_depth=data["bit_depth"],
            duration=data["duration"],
        )

class NewDriveData:
    def __init__(self, contents: dict, used_ids: list) -> None:
        self.contents = contents
        self.used_ids = used_ids
        self.isUpdated = False

    def to_dict(self):
        return {
            "contents": {k: v.to_dict() for k, v in self.contents.items()},
            "used_ids": self.used_ids,
            "isUpdated": self.isUpdated,
        }

    @classmethod
    def from_dict(cls, data):
        # Ensure contents is not missing or empty
        contents = {k: Folder.from_dict(v) for k, v in data["contents"].items()}
        return cls(contents, data["used_ids"])
        
    def save(self) -> None:
        drive_data_collection.replace_one({}, self.to_dict(), upsert=True)
        self.isUpdated = True

    def new_folder(self, path: str, name: str, uploader: str) -> None:
        logger.info(f"Creating new folder {name} in {path} by {uploader}")

    # Ensure path is not empty
        if not path:
            path = "/"

    # Create the folder
        id =  getRandomID()
        folder = Folder(name, id, path, uploader)
        print("New some path ", path)
        if path == "/":
            directory_folder: Folder = self.contents[path]
            directory_folder.contents[folder.id] = folder
        else:
            paths = path.strip("/").split("/")
            directory_folder: Folder = self.contents["/"]
            for path in paths:
                directory_folder = directory_folder.contents[path]
                print("directory folder ", directory_folder)
            directory_folder.contents[folder.id] = folder

        self.save()
        return folder.path + folder.id

    def new_file(self, path: str, name: str, file_id: int, size: int, rentry_link: str, paste_url: str, uploader: str, audio: str, subtitle: str, resolution: str, codec: str, bit_depth: str, duration: str) -> None:
        logger.info(f"Creating new file {name} in {path} by {uploader}")
        id = getRandomID()
        file = File(name, file_id, id, size, path, rentry_link, paste_url, uploader, audio, subtitle, resolution, codec, bit_depth, duration)
        if path == "/":
            directory_folder: Folder = self.contents[path]
            directory_folder.contents[file.id] = file
        else:
            paths = path.strip("/").split("/")
            directory_folder: Folder = self.contents["/"]
            for path in paths:
                directory_folder = directory_folder.contents[path]
            directory_folder.contents[file.id] = file

        self.save()

    def get_directory(self, path: str, is_admin: bool = True, auth: str = None) -> Folder:
        folder_data: Folder = self.contents["/"]
        auth_success = False
        auth_home_path = None

        if path != "/":
            path = path.strip("/")

            if "/" in path:
                path = path.split("/")
            else:
                path = [path]

            for folder in path:
                folder_data = folder_data.contents[folder]

                if auth in folder_data.auth_hashes:
                    auth_success = True
                    auth_home_path = (
                        "/" + folder_data.path.strip("/") + "/" + folder_data.id
                    )

        if not is_admin and not auth_success:
            return None

        if auth_success:
            return folder_data, auth_home_path

        return folder_data

    def get_directory2(self, path: str, is_admin: bool = True, auth: str = None) -> Folder:
        folder_data: Folder = self.contents["/"]
        auth_success = False
        auth_home_path = None

        if path != "/":
            path = path.strip("/")

            if "/" in path:
                path = path.split("/")
            else:
                path = [path]

            for folder in path:
                folder_data = folder_data.contents[folder]

                #if auth in folder_data.auth_hashes:
                auth_success = True
                auth_home_path = (
                    "/" + folder_data.path.strip("/") + "/" + folder_data.id
                )

        return folder_data
        
    def get_folder_auth(self, path: str) -> None:
        auth = getRandomID()
        folder_data: Folder = self.contents["/"]

        if path != "/":
            path = path.strip("/")

            if "/" in path:
                path = path.split("/")
            else:
                path = [path]

            for folder in path:
                folder_data = folder_data.contents[folder]

        folder_data.auth_hashes.append(auth)
        self.save()
        return auth

    def get_file(self, path) -> File:
        if len(path.strip("/").split("/")) > 0:
            folder_path = "/" + "/".join(path.strip("/").split("/")[:-1])
            file_id = path.strip("/").split("/")[-1]
        else:
            folder_path = "/"
            file_id = path.strip("/")

        folder_data = self.get_directory(folder_path)
        return folder_data.contents[file_id]

    def rename_file_folder(self, path: str, new_name: str) -> None:
        logger.info(f"Renaming {path} to {new_name}")

        if len(path.strip("/").split("/")) > 0:
            folder_path = "/" + "/".join(path.strip("/").split("/")[:-1])
            file_id = path.strip("/").split("/")[-1]
        else:
            folder_path = "/"
            file_id = path.strip("/")
        folder_data = self.get_directory(folder_path)
        folder_data.contents[file_id].name = new_name
        self.save()

    def trash_file_folder(self, path: str, trash: bool) -> None:
        logger.info(f"Trashing {path}")

        if len(path.strip("/").split("/")) > 0:
            folder_path = "/" + "/".join(path.strip("/").split("/")[:-1])
            file_id = path.strip("/").split("/")[-1]
        else:
            folder_path = "/"
            file_id = path.strip("/")
        folder_data = self.get_directory(folder_path)
        folder_data.contents[file_id].trash = trash
        self.save()

    def get_trashed_files_folders(self):
        root_dir = self.get_directory("/")
        trash_data = {}

        def traverse_directory(folder):
            for item in folder.contents.values():
                if item.type == "folder":
                    if item.trash:
                        trash_data[item.id] = item
                    else:
                        # Recursively traverse the subfolder
                        traverse_directory(item)
                elif item.type == "file":
                    if item.trash:
                        trash_data[item.id] = item

        traverse_directory(root_dir)
        return trash_data

    def delete_file_folder(self, path: str) -> None:
        logger.info(f"Deleting {path}")

        if len(path.strip("/").split("/")) > 0:
            folder_path = "/" + "/".join(path.strip("/").split("/")[:-1])
            file_id = path.strip("/").split("/")[-1]
        else:
            folder_path = "/"
            file_id = path.strip("/")

        folder_data = self.get_directory(folder_path)
        del folder_data.contents[file_id]
        self.save()

    def search_file_folder(self, query: str, path: str):
        if path=="":
            root_dir = self.get_directory("/")
        elif path=="/":
            root_dir = self.get_directory("/")
        else:   
            root_dir = self.get_directory(path)
            print(root_dir)
        search_results = {}

        def traverse_directory(folder):
            for item in folder.contents.values():
                if query.lower() in item.name.lower():
                    search_results[item.id] = item
                if item.type == "folder":
                    traverse_directory(item)
        traverse_directory(root_dir)
        return search_results

    def search_file_folderx(self, query: str):
        root_dir = self.get_directory("/")
        search_results = {}

        def traverse_directory(folder):
            for item in folder.contents.values():
                if query.lower() in item.name.lower():
                    search_results[item.id] = item
                if item.type == "folder":
                    traverse_directory(item)

        traverse_directory(root_dir)
        return search_results

    def search_file_folder2(self, query: str, path: str, is_admin: bool, auth: str):
        if path=="":
            root_dir, auth_home_path = self.get_directory("/", is_admin, auth)
        elif path=="/":
            root_dir, auth_home_path = self.get_directory("/", is_admin, auth)
        else:   
            root_dir = self.get_directory(path)
            print(root_dir)
        search_results = {}

        def traverse_directory(folder):
            for item in folder.contents.values():
                if query.lower() in item.name.lower():
                    search_results[item.id] = item
                if item.type == "folder":
                    traverse_directory(item)

        traverse_directory(root_dir)
        return search_results

class NewBotMode:
    def __init__(self, drive_data: NewDriveData) -> None:
        self.drive_data = drive_data

        # Set the current folder to root directory by default
        self.current_folder = "/"
        self.current_folder_name = "/ (root directory)"

    def set_folder(self, folder_path: str, name: str) -> None:
        self.current_folder = folder_path
        self.current_folder_name = name
        self.drive_data.save()

DRIVE_DATA: NewDriveData = None
BOT_MODE: NewBotMode = None

async def loadDriveData2():
    global DRIVE_DATA

    try:
        # Load data from MongoDB
        data = drive_data_collection.find_one({})
        if data:
            DRIVE_DATA = NewDriveData.from_dict(data)
            print("DRIVE DATA: ", DRIVE_DATA)
            logger.info("Drive data loaded from MongoDB")
        else:
            logger.info("Creating new drive.data file")
            DRIVE_DATA = NewDriveData({"/": Folder("/", "ad78asfas90ad5", "/", "root")}, [])
            DRIVE_DATA.save()

    except Exception as e:
        logger.error(f"Error loading drive data: {e}")
