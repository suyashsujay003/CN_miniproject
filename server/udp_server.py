import socket
import threading
import time
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)
from log_processor import process_log
from storage import store_log
from monitoring.metrics import Metrics


HOST = "0.0.0.0"
BUFFER_SIZE = 4096
SUMMARY_PORT = 5005

PORT_SEVERITY = {
    5001: "CRITICAL",
    5002: "ERROR",
    5003: "WARNING",
    5004: "INFO"
}

metrics = Metrics()


def receive_logs(port, expected_severity):

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind((HOST, port))

    print(
        f"[LISTENING] {expected_severity} on UDP port {port}"
    )

    while True:

        try:

            data, address = server.recvfrom(BUFFER_SIZE)

            received_at_ns = time.time_ns()

            log = process_log(data)

            if log is None:
                continue

            if log["severity"] != expected_severity:

                print(
                    f"[REJECTED] Severity-port mismatch from {address}"
                )

                continue

            latency_ms = (
                received_at_ns - log["sent_at_unix_ns"]
            ) / 1_000_000

            if latency_ms < 0:
                latency_ms = None

            store_log(log)

            metrics.record_packet(
                log,
                len(data),
                latency_ms
            )

            print(
                f"[RECEIVED] {expected_severity} | "
                f"Host: {log['host_id']} | "
                f"Seq: {log['sequence_number']} | "
                f"Latency: {latency_ms if latency_ms is not None else 'N/A'} ms"
            )

        except OSError as error:

            print(f"[SOCKET ERROR] {error}")


def receive_summaries():

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind((HOST, SUMMARY_PORT))

    print(
        f"[LISTENING] Transmission summaries on UDP port {SUMMARY_PORT}"
    )

    while True:

        try:

            data, address = server.recvfrom(BUFFER_SIZE)

            summary = json.loads(
                data.decode("utf-8")
            )

            if summary.get("type") != "SUMMARY":
                continue

            if summary.get("severity") not in PORT_SEVERITY.values():
                continue

            if (
                not isinstance(summary.get("host_id"), str)
                or not summary["host_id"]
                or not isinstance(summary.get("session_id"), str)
                or not summary["session_id"]
                or type(summary.get("sent_count")) is not int
                or summary["sent_count"] < 0
            ):
                print(f"[INVALID SUMMARY] From {address}")
                continue

            metrics.register_summary(summary)

            print(
                f"[SUMMARY RECEIVED] {summary['host_id']} | "
                f"{summary['severity']} | "
                f"Sent: {summary['sent_count']}"
            )

        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:

            print(f"[INVALID SUMMARY] {error}")

        except OSError as error:

            print(f"[SUMMARY SOCKET ERROR] {error}")


def display_statistics():

    while True:

        time.sleep(5)

        result = metrics.get_statistics()

        print("\n========== PERFORMANCE METRICS ==========")

        print(
            f"Total packets received: {result['total_packets']}"
        )

        print(
            f"Total bytes received: {result['total_bytes']}"
        )

        print(
            f"Packet throughput: {result['packets_per_second']:.2f} packets/sec"
        )

        print(
            f"Data throughput: {result['bytes_per_second']:.2f} bytes/sec"
        )

        print(
            f"Expected packets: {result['expected_packets']}"
        )

        print(
            f"Lost packets: {result['lost_packets']}"
        )

        if result["packet_loss_percent"] is not None:

            print(
                f"Packet loss: {result['packet_loss_percent']:.2f}%"
            )

        else:

            print("Packet loss: Waiting for transmission summary")

        print("\nSeverity-wise received packets:")

        for severity, count in result["severity_stats"].items():

            print(f"{severity}: {count}")

        if result["average_latency"] is not None:

            print(
                f"\nAverage latency: {result['average_latency']:.3f} ms"
            )

            print(
                f"Minimum latency: {result['minimum_latency']:.3f} ms"
            )

            print(
                f"Maximum latency: {result['maximum_latency']:.3f} ms"
            )

        else:

            print("\nLatency: No valid measurements yet")

        print("==========================================\n")


if __name__ == "__main__":

    print("Starting Distributed Log Collector...\n")

    for port, severity in PORT_SEVERITY.items():

        thread = threading.Thread(
            target=receive_logs,
            args=(port, severity),
            daemon=True
        )

        thread.start()

    summary_thread = threading.Thread(
        target=receive_summaries,
        daemon=True
    )

    summary_thread.start()

    stats_thread = threading.Thread(
        target=display_statistics,
        daemon=True
    )

    stats_thread.start()

    try:

        while True:
            time.sleep(1)

    except KeyboardInterrupt:

        print("\nShutting down log collector.")