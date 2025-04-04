from dotenv import load_dotenv
import os

# Load environment variables from the .env file, if present
load_dotenv()
# MongoDB Database URI
mongo_uri = "mongodb+srv://diablo:OH4WLGrCZOlG6FH6@cluster0.qokt3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Telegram API credentials obtained from https://my.telegram.org/auth
API_ID=10247139
API_HASH="96b46175824223a33737657ab943fd6a"
BOT_TOKENSX = os.getenv("BOT_TOKENS", "6769415354:AAHh7IfKn11PWuNxUo0qmoIuW7NclxaaFHQ, 8081002376:AAGvj-wBC_4EWKUu_XT_F-rDL6nwV1LAERs").strip(", ").split(",")
BOT_TOKENSX = [token.strip() for token in BOT_TOKENSX if token.strip() != ""]

#Set True if you need to delete file after uploads
FILE_DEL = True
# List of Premium Telegram Account Pyrogram String Sessions used for file upload/download operations
STRING_SESSIONS = os.getenv("STRING_SESSIONS", "").strip(", ").split(",")
STRING_SESSIONS = [
    session.strip() for session in STRING_SESSIONS if session.strip() != ""
]

# Chat ID of the Telegram storage channel where files will be stored
STORAGE_CHANNEL = -1001322241772


# Determine the maximum file size (in bytes) allowed for uploading to Telegram
# 1.98 GB if no premium sessions are provided, otherwise 3.98 GB
if len(STRING_SESSIONS) == 0:
    MAX_FILE_SIZE = 1.98 * 1024 * 1024 * 1024  # 2 GB in bytes
else:
    MAX_FILE_SIZE = 3.98 * 1024 * 1024 * 1024  # 4 GB in bytes

# Database backup interval in seconds. Backups will be sent to the storage channel at this interval
DATABASE_BACKUP_TIME = int(
    os.getenv("DATABASE_BACKUP_TIME", 60)
)  # Default to 60 seconds

# Time delay in seconds before retrying after a Telegram API floodwait error
SLEEP_THRESHOLD = int(os.getenv("SLEEP_THRESHOLD", 60))  # Default to 60 seconds

# Domain to auto-ping and keep the website active
WEBSITE_URL = os.getenv("WEBSITE_URL", None)

# List of Telegram User IDs who have admin access to the bot mode
TELEGRAM_ADMIN_IDS = os.getenv("TELEGRAM_ADMIN_IDS", "6542409825, 1498366357, 5419097944, 162010513, 590009569, 1863307059").strip(", ").split(",")
TELEGRAM_ADMIN_IDS = [int(id) for id in TELEGRAM_ADMIN_IDS if id.strip() != ""]
