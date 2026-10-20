from pathlib import Path
import os


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("APARTMENT_AGENT_DATA_DIR", PROJECT_DIR / "data"))
CONFIG_DIR = Path(os.getenv("APARTMENT_AGENT_CONFIG_DIR", PROJECT_DIR / "config"))
DB_PATH = Path(os.getenv("APARTMENT_AGENT_DB", DATA_DIR / "apartments.db"))
INCOMING_DIR = Path(os.getenv("APARTMENT_AGENT_INCOMING_DIR", DATA_DIR / "incoming"))
