import json
import os
import tempfile
from pathlib import Path


# Resolve the configuration path relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"

# Define the maximum set of tables that can be authorized.
SUPPORTED_TABLES = {
    "person",
    "specimen",
    "variant_occurrence",
    "target_gene",
    "variant_annotation"
}


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
        "allowed_tables"
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

    if not set(tables).issubset(SUPPORTED_TABLES):
        raise ValueError("Configuration contains unsupported tables.")

    return config


def load_config() -> dict:
    """Load and validate the saved configuration."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

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
