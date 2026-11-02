
import json


VALID_SEVERITIES = {
    "CRITICAL",
    "ERROR",
    "WARNING",
    "INFO"
}


def process_log(data):

    try:
        log = json.loads(data.decode("utf-8"))

        required_fields = [
            "host_id",
            "session_id",
            "sequence_number",
            "timestamp",
            "sent_at_unix_ns",
            "severity",
            "message"
        ]

        # Check whether all required fields exist
        for field in required_fields:
            if field not in log:
                raise ValueError(f"Missing field: {field}")

        # Validate severity
        if log["severity"] not in VALID_SEVERITIES:
            raise ValueError("Invalid severity")

        # Validate host ID
        if not isinstance(log["host_id"], str) or not log["host_id"]:
            raise ValueError("Invalid host ID")

        # Validate session ID
        if not isinstance(log["session_id"], str) or not log["session_id"]:
            raise ValueError("Invalid session ID")

        # Validate sequence number
        if (
            not isinstance(log["sequence_number"], int)
            or isinstance(log["sequence_number"], bool)
            or log["sequence_number"] < 1
        ):
            raise ValueError("Invalid sequence number")

        # Validate send timestamp
        if not isinstance(log["sent_at_unix_ns"], int):
            raise ValueError("Invalid send timestamp")

        # Validate message
        if not isinstance(log["message"], str):
            raise ValueError("Invalid message")

        # Return validated log
        return log

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError
    ) as error:

        print(f"Invalid log packet: {error}")
        return None
