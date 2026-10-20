import json
import os
import tempfile
from pathlib import Path
import pandas as pd
from datetime import datetime

from src.configManager import load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_history_path(config=None):
    if config is None:
        config = load_config()

    return PROJECT_ROOT / config["history_path"]


def save_history(history: list, config=None) -> None:
    """Save the query history to a JSON file."""

    if config is None:
        config = load_config()

    history_path = get_history_path(config)

    # Keep only the most recent queries.
    history = history[-config["max_history"]:]

    serializable_history = []

    for item in history:
        df = item["results"]

        serializable_history.append({
            "question": item["question"],
            "sql": item["sql"],
            "columns": list(df.columns),
            "results": json.loads(
                df.to_json(orient="records", date_format="iso")
            )
        })

    history_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=history_path.parent,
            prefix=".history_",
            suffix=".tmp",
            delete=False
        ) as file:
            temporary_path = Path(file.name)
            json.dump(serializable_history, file, indent=2, ensure_ascii=False)
            file.write("\n")

        os.replace(temporary_path, history_path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_history(config=None) -> list:
    """Load previously saved questions and results."""

    if config is None:
        config = load_config()

    history_path = get_history_path(config)

    if not history_path.exists():
        return []

    with history_path.open("r", encoding="utf-8") as file:
        saved_history = json.load(file)

    history = []

    for item in saved_history[-config["max_history"]:]:
        df = pd.DataFrame(
            item["results"],
            columns=item["columns"]
        )

        history.append({
            "question": item["question"],
            "sql": item["sql"],
            "results": df
        })

    return history


def export_history(history: list, filename: str, directory: str) -> Path:
    """Export a snapshot of the current query history to a JSON file."""

    if not history:
        raise ValueError("There is no query history to save.")

    filename = filename.strip()
    directory = directory.strip()

    # Validate the file name.
    if not filename or Path(filename).name != filename:
        raise ValueError("Enter a valid file name without directory separators.")

    if filename in {".", ".."}:
        raise ValueError("Invalid file name.")

    if not filename.lower().endswith(".json"):
        filename += ".json"

    # Resolve the destination directory.
    config = load_config()
    project_root = PROJECT_ROOT.resolve()
    allowed_root = (project_root / "data").resolve()

    destination_directory = Path(directory).expanduser()

    if not destination_directory.is_absolute():
        destination_directory = project_root / destination_directory

    destination_directory = destination_directory.resolve()

    # Restrict exports to the application's data directory.
    if not destination_directory.is_relative_to(allowed_root):
        raise ValueError(
            "History exports must be saved inside the project's data directory."
        )

    destination = destination_directory / filename

    if destination.exists():
        raise FileExistsError(
            "A file with this name already exists. Choose another name."
        )

    serializable_history = []

    for item in history:
        df = item["results"]

        serializable_history.append({
            "question": item["question"],
            "sql": item["sql"],
            "columns": list(df.columns),
            "results": json.loads(
                df.to_json(orient="records", date_format="iso")
            )
        })

    destination_directory.mkdir(parents=True, exist_ok=True)

    # Create a new file exclusively: never overwrite an existing export.
    with destination.open("x", encoding="utf-8") as file:
        json.dump(serializable_history, file, indent=2, ensure_ascii=False)
        file.write("\n")

    return destination


def import_history(file_content: bytes) -> list:
    """Import a query history from JSON bytes."""

    saved_history = json.loads(file_content.decode("utf-8"))

    if not isinstance(saved_history, list):
        raise ValueError("Invalid history format: expected a list.")

    history = []

    for item in saved_history:
        if not isinstance(item, dict):
            raise ValueError("Invalid history entry.")

        required = {"question", "sql", "columns", "results"}

        if not required.issubset(item):
            raise ValueError("History entry contains missing fields.")

        if (
            not isinstance(item["question"], str)
            or not isinstance(item["sql"], str)
            or not isinstance(item["columns"], list)
            or not all(isinstance(c, str) for c in item["columns"])
            or not isinstance(item["results"], list)
        ):
            raise ValueError("Invalid history entry data.")

        df = pd.DataFrame(
            item["results"],
            columns=item["columns"]
        )

        history.append({
            "question": item["question"],
            "sql": item["sql"],
            "results": df
        })

    return history