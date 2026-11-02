import json
import time
from datetime import datetime, timezone


MESSAGES = {
    "CRITICAL": [
        "Database connection failure",
        "Server unavailable",
        "Critical memory exhaustion",
        "Payment processing failure"
    ],

    "ERROR": [
        "Authentication failed",
        "API request failed",
        "File access error",
        "Service timeout"
    ],

    "WARNING": [
        "High CPU utilization",
        "Disk space running low",
        "Unusual login activity",
        "Slow database response"
    ],

    "INFO": [
        "User logged in",
        "Application started",
        "Request processed successfully",
        "Scheduled task completed"
    ]
}


def generate_log(host_id, sequence_number, severity):

    if severity not in MESSAGES:
        raise ValueError("Invalid severity level")

    timestamp = datetime.now(timezone.utc).isoformat()

    log = {
        "host_id": host_id,
        "sequence_number": sequence_number,
        "timestamp": timestamp,
        "sent_at_unix_ns": time.time_ns(),
        "severity": severity,
        "message": __import__("random").choice(MESSAGES[severity])
    }

    return log


def serialize_log(log):
    return json.dumps(log).encode("utf-8")