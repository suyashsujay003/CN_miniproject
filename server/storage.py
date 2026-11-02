import json
import os
import threading
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

STORAGE_LOCK = threading.Lock()


def store_log(log):

    severity = log["severity"]

    filename = os.path.join(
        LOG_DIR,
        f"{severity.lower()}.jsonl"
    )

    with STORAGE_LOCK:

        with open(filename, "a", encoding="utf-8") as file:

            record = {
                **log,
                "received_at": datetime.now(
                    timezone.utc
                ).isoformat()
            }

            file.write(
                json.dumps(record) + "\n"
            )