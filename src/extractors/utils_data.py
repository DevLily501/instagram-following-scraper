thonimport json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")

def load_settings(path: Path) -> Dict[str, Any]:
    """
    Load settings from a JSON file. Returns an empty dict on failure.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            settings = json.load(f)
        if not isinstance(settings, dict):
            raise ValueError("settings.json must contain a JSON object")
        return settings
    except FileNotFoundError:
        logger.error("Settings file not found: %s", path)
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode settings JSON: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error loading settings: %s", exc)
    return {}

def load_inputs(path: Path) -> List[str]:
    """
    Load input usernames from a JSON file.

    The file may contain:
    - A list of plain usernames, e.g. ["zuck", "instagram"]
    - A list of objects with a 'username' field.
    """
    usernames: List[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Input file not found: %s", path)
        return usernames
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode input JSON from %s: %s", path, exc)
        return usernames

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                usernames.append(item)
            elif isinstance(item, dict) and "username" in item:
                usernames.append(str(item["username"]))
    else:
        logger.error("Input JSON must be a list of usernames or objects.")
    return usernames

def sanitize_usernames(usernames: Iterable[str]) -> List[str]:
    """
    Strip whitespace, lower-case, and validate usernames.

    Invalid usernames are skipped with a warning.
    """
    sanitized: List[str] = []
    for raw in usernames:
        username = str(raw).strip().strip("@").lower()
        if not username:
            continue
        if not USERNAME_RE.match(username):
            logger.warning("Skipping invalid username: %s", username)
            continue
        if username in sanitized:
            continue
        sanitized.append(username)
    return sanitized