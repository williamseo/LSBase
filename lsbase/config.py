import os
from dotenv import load_dotenv

# --- LS Securities API ---
APP_KEY = os.getenv("LS_APP_KEY")
APP_SECRET = os.getenv("LS_APP_SECRET")

# --- LS Securities Account ---
ACCOUNT_NO = os.getenv("ACCOUNT_NO")
ACCOUNT_PASSWORD = os.getenv("ACCOUNT_PASSWORD")

# --- Email for Reporting ---
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# --- Database Settings ---
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# --- Logger Settings ---
# .env 파일에서 로그 레벨을 읽어오되, 설정이 없으면 'INFO'를 기본값으로 사용합니다.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def validate_config():
    """필수 설정값이 로드되었는지 확인합니다."""
    if not all([APP_KEY, APP_SECRET, ACCOUNT_NO]):
        raise ValueError("필수 환경 변수(APP_KEY, APP_SECRET, ACCOUNT_NO)가 .env 파일에 설정되지 않았습니다.")

#validate_config()
