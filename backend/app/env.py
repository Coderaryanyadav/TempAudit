"""
Environment Configuration Loader for FinAuditPro.
Provides offline, zero-dependency .env parsing and loading into os.environ.
"""
import os
from typing import Optional


def load_dotenv(env_path: Optional[str] = None) -> bool:
    """
    Parses a .env file and sets values into os.environ without overwriting existing environment variables.
    Searches current working directory, script directory, and parents up to 4 levels if env_path is not specified.
    """
    if env_path is None:
        start_dirs = [
            os.getcwd(),
            os.path.dirname(os.path.abspath(__file__)),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ]
        for d in start_dirs:
            candidate = os.path.join(d, ".env")
            if os.path.isfile(candidate):
                env_path = candidate
                break

    if not env_path or not os.path.isfile(env_path):
        return False

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        return True
    except Exception:
        return False
