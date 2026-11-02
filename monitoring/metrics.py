import threading
import time


class Metrics:

    def __init__(self):

        self.lock = threading.Lock()
        self.start_time = time.monotonic()

        self.total_packets = 0
        self.total_bytes = 0

        self.latency_sum = 0.0
        self.latency_count = 0
        self.min_latency = None
        self.max_latency = None

        self.severity_stats = {
            "CRITICAL": 0,
            "ERROR": 0,
            "WARNING": 0,
            "INFO": 0
        }

        # (host_id, session_id, severity) -> received sequence numbers
        self.received_sequences = {}

        # (host_id, session_id, severity) -> expected packet count
        self.expected_packets = {}

    def record_packet(self, log, packet_size, latency_ms):

        key = (
            log["host_id"],
            log["session_id"],
            log["severity"]
        )

        with self.lock:

            self.total_packets += 1
            self.total_bytes += packet_size

            self.severity_stats[log["severity"]] += 1

            if key not in self.received_sequences:
                self.received_sequences[key] = set()

            self.received_sequences[key].add(
                log["sequence_number"]
            )

            if latency_ms is not None:

                self.latency_sum += latency_ms
                self.latency_count += 1

                if self.min_latency is None:
                    self.min_latency = latency_ms
                    self.max_latency = latency_ms
                else:
                    self.min_latency = min(
                        self.min_latency,
                        latency_ms
                    )

                    self.max_latency = max(
                        self.max_latency,
                        latency_ms
                    )

    def register_summary(self, summary):

        key = (
            summary["host_id"],
            summary["session_id"],
            summary["severity"]
        )

        expected = summary["sent_count"]

        with self.lock:

            self.expected_packets[key] = expected

    def get_statistics(self):

        with self.lock:

            elapsed = max(
                time.monotonic() - self.start_time,
                0.001
            )

            expected_total = sum(
                self.expected_packets.values()
            )

            received_for_loss = 0

            for key, expected in self.expected_packets.items():

                sequences = self.received_sequences.get(
                    key, set()
                )

                # Count only valid sequence numbers for this session.
                valid_received = sum(
                    1 for sequence in sequences
                    if 1 <= sequence <= expected
                )

                received_for_loss += min(
                    valid_received,
                    expected
                )

            lost_packets = max(
                expected_total - received_for_loss,
                0
            )

            if expected_total > 0:
                packet_loss = (
                    lost_packets / expected_total
                ) * 100
            else:
                packet_loss = None

            average_latency = (
                self.latency_sum / self.latency_count
                if self.latency_count > 0
                else None
            )

            return {
                "elapsed_seconds": elapsed,
                "total_packets": self.total_packets,
                "total_bytes": self.total_bytes,
                "packets_per_second": (
                    self.total_packets / elapsed
                ),
                "bytes_per_second": (
                    self.total_bytes / elapsed
                ),
                "expected_packets": expected_total,
                "lost_packets": lost_packets,
                "packet_loss_percent": packet_loss,
                "severity_stats": dict(self.severity_stats),
                "average_latency": average_latency,
                "minimum_latency": self.min_latency,
                "maximum_latency": self.max_latency
            }