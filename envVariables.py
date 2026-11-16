from dotenv import load_dotenv
import os

load_dotenv('E:\\ashkan-project\EcoSentia\.env', verbose=True)

API_BASE = os.getenv("ECOSENTIA_API_URL")
APP_TITLE = os.getenv("APP_TITLE")
APP_VERSION = os.getenv("APP_VERSION")
HTTP_TIMEOUT = int(os.getenv("ECOSENTIA_HTTP_TIMEOUT"))
HEALTH_TIMEOUT = int(os.getenv("ECOSENTIA_HEALTH_TIMEOUT"))
DARK_THEME_PATH = os.getenv("DARK_THEME_PATH")
LIGHT_THEME_PATH = os.getenv("LIGHT_THEME_PATH")
BASE_THEME_PATH = os.getenv("BASE_THEME_PATH")
HTML_DARK_HEADER_PATH = os.getenv("HTML_DARK_HEADER_PATH")
HTML_LIGHT_HEADER_PATH = os.getenv("HTML_LIGHT_HEADER_PATH")
