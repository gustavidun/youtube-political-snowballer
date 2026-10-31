from pathlib import Path
import os
from dotenv import load_dotenv
import json

HEADLESS = False

ROOT = Path(__file__).parents[1]

load_dotenv(ROOT / ".env")
_raw_api_key = os.environ.get("API_KEY") or os.environ.get("YT_API_KEYS")
API_KEY = json.loads(_raw_api_key) if _raw_api_key else []
MAX_API_ERRORS : int = 5

VIDEO_IDS_PATH = ROOT / "data" / "video_ids.parquet"

SESSION_DIR = ROOT / "data" / "session"
LOG_DIR = ROOT / "data" / "logs"
PUPPETS_DIR = ROOT / "data" / "puppets"

UBLOCK_PATH = ROOT / "src" / "puppet" / "extensions"

SLANT_DIR = ROOT / "data" / "slant"
SLANT_ESTIMATIONS_CSV = SLANT_DIR / "slant_estimations.csv"
SLANTS_TRAIN = SLANT_DIR / "slants_train.pkl"

MODELS_DIR = ROOT / "data" / "models"

if not PUPPETS_DIR.exists():
    os.mkdir(PUPPETS_DIR)

if not MODELS_DIR.exists():
    os.mkdir(MODELS_DIR)

if not SESSION_DIR.exists():
    os.mkdir(SESSION_DIR)

if not LOG_DIR.exists():
    os.mkdir(LOG_DIR)

if not UBLOCK_PATH.exists():
    os.mkdir(UBLOCK_PATH)