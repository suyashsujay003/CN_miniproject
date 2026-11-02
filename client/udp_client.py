import socket
import time
import argparse
import json
import uuid

from config import SERVER_IP, SEVERITY_PORTS, DEFAULT_HOST_ID
from log_generator import generate_log, serialize_log


SUMMARY_PORT = 5005


def send_logs(host_id, severity, count, interval, server_ip):

    port = SEVERITY_PORTS[severity]

    client = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    session_id = uuid.uuid4().hex

    print(f"\nStarting UDP client: {host_id}")
    print(f"Session ID: {session_id}")
    print(f"Severity: {severity}")
    print(f"Destination: {server_ip}:{port}\n")

    sent = 0

    try:

        for sequence in range(1, count + 1):

            log = generate_log(
                host_id,
                sequence,
                severity
            )

            log["session_id"] = session_id

            packet = serialize_log(log)

            client.sendto(
                packet,
                (server_ip, port)
            )

            sent += 1

            print(
                f"Sent #{sequence}: {log['message']}"
            )

            if interval > 0:
                time.sleep(interval)

        # Send transmission summary to collector.

        summary = {
            "type": "SUMMARY",
            "host_id": host_id,
            "session_id": session_id,
            "severity": severity,
            "sent_count": sent
        }

        client.sendto(
            json.dumps(summary).encode("utf-8"),
            (server_ip, SUMMARY_PORT)
        )

    finally:

        client.close()

    print(f"\nTransmission complete. Sent: {sent}")
    print("Transmission summary sent to collector.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Distributed Log UDP Client"
    )

    parser.add_argument("--host", default=DEFAULT_HOST_ID)

    parser.add_argument(
        "--severity",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO"],
        default="INFO"
    )

    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--server", default=SERVER_IP)

    args = parser.parse_args()

    if args.count <= 0 or args.interval < 0:
        parser.error(
            "Count must be positive and interval non-negative"
        )

    send_logs(
        args.host,
        args.severity,
        args.count,
        args.interval,
        args.server
    )