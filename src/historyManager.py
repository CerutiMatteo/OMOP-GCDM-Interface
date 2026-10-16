import json
import os
import tempfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = PROJECT_ROOT / "data" / "queryHistory.json"


def save_history(history: list) -> None:
    """Save the query history to a JSON file."""

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

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=HISTORY_PATH.parent,
            prefix=".history_",
            suffix=".tmp",
            delete=False
        ) as file:
            temporary_path = Path(file.name)
            json.dump(serializable_history, file, indent=2, ensure_ascii=False)
            file.write("\n")

        os.replace(temporary_path, HISTORY_PATH)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_history() -> list:
    """Load previously saved questions and results."""

    if not HISTORY_PATH.exists():
        return []

    with HISTORY_PATH.open("r", encoding="utf-8") as file:
        saved_history = json.load(file)

    history = []

    for item in saved_history:
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
