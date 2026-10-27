import json
import os
import tempfile
from pathlib import Path

from functools import lru_cache
from .schemaMetadata import get_database_schema

# Resolve the configuration path relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"

# Define the maximum set of tables that can be authorized.
@lru_cache(maxsize=1)
def get_supported_tables() -> set[str]:
    """Retrieve available tables from the PostgreSQL cdm schema."""
    return set(get_database_schema().keys())

def validate_config(config: dict) -> dict:
    """Validate application configuration values."""

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object.")

    required_keys = {
        "programmer_mode",
        "max_rows",
        "automatic_retry",
        "max_retries",
        "retry_delay_seconds",
        "allowed_tables",
        "max_history",
        "history_path"
    }

    if set(config) != required_keys:
        raise ValueError("Configuration contains missing or unknown settings.")

    if not isinstance(config["programmer_mode"], bool):
        raise ValueError("Programmer Mode must be a boolean.")

    if type(config["max_rows"]) is not int:
        raise ValueError("Maximum rows must be an integer.")

    if not 1 <= config["max_rows"] <= 10000:
        raise ValueError("Maximum rows must be between 1 and 10000.")

    if not isinstance(config["automatic_retry"], bool):
        raise ValueError("Automatic Retry must be a boolean.")

    if type(config["max_retries"]) is not int:
        raise ValueError("Maximum retries must be an integer.")

    if not 0 <= config["max_retries"] <= 10:
        raise ValueError("Maximum retries must be between 0 and 10.")

    if type(config["retry_delay_seconds"]) is not int:
        raise ValueError("Retry delay must be an integer.")

    if not 1 <= config["retry_delay_seconds"] <= 60:
        raise ValueError("Retry delay must be between 1 and 60 seconds.")

    tables = config["allowed_tables"]

    if not isinstance(tables, list):
        raise ValueError("Allowed tables must be a list.")

    if not tables:
        raise ValueError("At least one table must be authorized.")

    if not all(isinstance(table, str) for table in tables):
        raise ValueError("Table names must be strings.")

    if len(tables) != len(set(tables)):
        raise ValueError("Allowed tables must not contain duplicates.")

    if not set(tables).issubset(get_supported_tables()):
        raise ValueError("Configuration contains unsupported tables.")

    # Validate maximum saved queries.
    if type(config["max_history"]) is not int:
        raise ValueError("Maximum saved queries must be an integer.")

    if not 10 <= config["max_history"] <= 500:
        raise ValueError("Maximum saved queries must be between 10 and 500.")

    # Validate history save path.
    if not isinstance(config["history_path"], str):
        raise ValueError("History path must be a string.")

    if not config["history_path"].strip():
        raise ValueError("History path cannot be empty.")

    history_path = Path(config["history_path"])

    if history_path.is_absolute() or ".." in history_path.parts:
        raise ValueError("History path must be relative to the project directory.")

    if history_path.suffix.lower() != ".json":
        raise ValueError("History path must point to a JSON file.")

    # Restrict history files to the project's data directory.
    resolved_path = (PROJECT_ROOT / history_path).resolve()
    allowed_directory = (PROJECT_ROOT / "data").resolve()

    if not resolved_path.is_relative_to(allowed_directory):
        raise ValueError("History must be saved inside the data directory.")

    return config


def load_config() -> dict:
    """Load configuration, adding defaults for new history settings."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    config.setdefault("max_history", 100)
    config.setdefault("history_path", "data/currentHistory.json")

    return validate_config(config)


def save_config(config: dict) -> None:
    """Validate and atomically save application settings."""

    validate_config(config)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_PATH.parent,
            prefix=".settings_",
            suffix=".tmp",
            delete=False
        ) as file:
            temporary_path = Path(file.name)
            json.dump(config, file, indent=2)
            file.write("\n")

        os.replace(temporary_path, CONFIG_PATH)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
