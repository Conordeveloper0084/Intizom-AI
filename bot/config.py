from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "productivity_bot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Ball tizimi
SCORE_DONE = 5        # Bajarganda
SCORE_FAILED = -3     # Bajarmaganida
STREAK_BONUS = 2      # Har streak kuni uchun bonus

# Kunlik summary vaqti
SUMMARY_HOUR = 21
SUMMARY_MINUTE = 0