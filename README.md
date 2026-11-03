# Distributed Log Aggregation with SDN-Based QoS

## 1. Project Overview

This project implements a distributed log aggregation system using UDP socket programming and Software-Defined Networking (SDN).

A log-generating client sends severity-classified log messages to a central collector. The collector validates incoming messages, processes them and stores them in separate JSONL files based on severity.

An SDN controller built using Ryu manages an Open vSwitch (OVS) switch through OpenFlow 1.3. It performs endpoint authorization, MAC learning and severity-based traffic queue selection.

The project also implements Quality of Service (QoS) using Linux HTB queues in Open vSwitch. Different log severities are mapped to different queues to provide differentiated bandwidth guarantees under competing network traffic.

### Project Objectives

- Implement UDP-based communication between distributed hosts.
- Generate and transmit severity-classified log messages.
- Collect, validate and store logs centrally.
- Integrate Mininet with a Ryu SDN controller.
- Implement endpoint authorization using IP, MAC address and switch ingress port.
- Classify log traffic into separate QoS queues.
- Compare network performance with QoS disabled and enabled.

---

## 2. System Architecture

The system consists of three main components:

1. **Log Generator (h1):** Generates and transmits log messages using UDP sockets.
2. **Log Collector (h2):** Receives, validates, processes and stores log messages.
3. **SDN Controller (c0):** Controls the Open vSwitch switch, enforces endpoint authorization and selects QoS queues.

### Network Topology

| Component | Configuration |
|---|---|
| Host 1 (h1) | 10.0.0.1/24 |
| Host 2 (h2) | 10.0.0.2/24 |
| Switch | Open vSwitch (s1) |
| Controller | Ryu (c0) |
| Controller address | 127.0.0.1:6653 |
| OpenFlow version | 1.3 |
| h1 switch port | 1 |
| h2 switch port | 2 |

The switch uses secure fail mode and communicates with the remote Ryu controller.

### Communication Flow

1. The client generates a log message.
2. The message is serialized into JSON.
3. The client transmits it through a UDP socket.
4. The Open vSwitch switch receives the packet.
5. The Ryu controller authorizes the source and installs forwarding rules.
6. The controller maps the UDP destination port to a QoS queue.
7. The switch forwards the packet to h2.
8. The collector validates and processes the message.
9. The message is stored in the appropriate JSONL file.

---

## 3. Project Structure

```text
distributed_log_aggregation/
│
├── client/
│   ├── config.py
│   ├── log_generator.py
│   └── udp_client.py
│
├── server/
│   ├── udp_server.py
│   ├── storage.py
│   └── log_processor.py
│
├── monitoring/
│   └── metrics.py
│
├── sdn/
│   ├── __init__.py
│   ├── controller.py
│   ├── policy.py
│   └── topology.py
│
├── logs/
│   ├── critical.jsonl
│   ├── error.jsonl
│   ├── warning.jsonl
│   └── info.jsonl
│
├── results/
│   ├── log-collector-baseline.log
│   ├── log-collector-qos.log
│   ├── iperf-baseline.log
│   ├── iperf-qos.log
│   └── queue-stats-qos.txt
│
├── tests/
│   └── test_sdn_policy.py
│
└── README.md
```

---

## 4. Log Generation and UDP Communication

The client generates structured log messages containing information such as:

- Host identifier
- Sequence number
- Timestamp
- Severity level
- Log message
- Send timestamp

The messages are serialized into JSON and transmitted using UDP sockets.

### Severity Classification

The system supports four severity levels:

| Severity | UDP Destination Port |
|---|---:|
| CRITICAL | 5001 |
| ERROR | 5002 |
| WARNING | 5003 |
| INFO | 5004 |
| Session Summary | 5005 |

Each client session also transmits a summary datagram to port 5005.

### Example Client Commands

```bash
python3 client/udp_client.py --server 10.0.0.2 --severity CRITICAL --count 100 --interval 0
```

```bash
python3 client/udp_client.py --server 10.0.0.2 --severity INFO --count 100 --interval 0
```

The client supports configurable destination addresses, severity levels, message counts and transmission intervals.

---

## 5. Log Collection and Storage

The UDP collector runs on h2 and listens on ports 5001–5005.

The collector:

- Receives incoming UDP datagrams.
- Validates and processes received messages.
- Calculates application-level latency statistics.
- Tracks received and expected packet counts where session information is available.
- Stores log messages in JSON Lines format.

### Storage Files

| File | Contents |
|---|---|
| `logs/critical.jsonl` | CRITICAL logs |
| `logs/error.jsonl` | ERROR logs |
| `logs/warning.jsonl` | WARNING logs |
| `logs/info.jsonl` | INFO logs |

JSONL storage allows each log entry to be independently serialized and processed.

---

## 6. SDN Controller Implementation

The SDN controller is implemented using Ryu and OpenFlow 1.3.

### 6.1 MAC Learning

The controller maintains a MAC-to-port mapping for the connected switch.

When a packet arrives, the controller learns the source MAC address and its ingress port. It uses this information to determine the appropriate forwarding port.

Learned forwarding rules have a 60-second idle timeout.

### 6.2 Endpoint Authorization

The system uses predefined endpoint bindings.

| IP Address | Authorized MAC Address | Switch Port |
|---|---|---:|
| 10.0.0.1 | 00:00:00:00:00:01 | 1 |
| 10.0.0.2 | 00:00:00:00:00:02 | 2 |

For IPv4 traffic, the controller checks:

- Source IP address
- Ethernet source MAC address
- Switch ingress port

For ARP traffic, it additionally verifies that the ARP sender MAC and Ethernet source MAC match the configured endpoint binding.

Unauthorized IPv4 traffic results in a drop flow with a 30-second hard timeout.

Inconsistent ARP identities are rejected.

This provides endpoint authorization for the fixed two-host laboratory topology.

**Security limitation:** This is a controlled-lab endpoint binding mechanism, not cryptographic device authentication. An attacker capable of spoofing an authorized IP address, MAC address and switch attachment could potentially impersonate an authorized endpoint.

---

## 7. QoS Implementation

Quality of Service is implemented using Linux Hierarchical Token Bucket (HTB) queues attached to the collector-facing OVS interface, `s1-eth2`.

The controller identifies log severity using the UDP destination port and applies an OpenFlow `set_queue` action before forwarding the packet to the collector.

### 7.1 Queue Mapping

| Queue ID | Traffic Class | UDP Port | Minimum Rate |
|---:|---|---:|---:|
| 1 | CRITICAL | 5001 | 4 Mbps |
| 2 | ERROR | 5002 | 3 Mbps |
| 3 | WARNING | 5003 | 2 Mbps |
| 4 | INFO | 5004 | 0.9 Mbps |
| 5 | Session Summary | 5005 | 0.1 Mbps |
| 0 | Default traffic | Other traffic | Default queue |

The HTB parent rate is configured at 10 Mbps.

The configured minimum rates for queues 1–5 add up to 10 Mbps.

**Important:** HTB minimum-rate guarantees are not strict-priority scheduling. The queues provide differentiated bandwidth allocation rather than an absolute rule that CRITICAL traffic must always be transmitted first.

### 7.2 OpenFlow Queue Selection

The controller maintains the following mapping:

```python
UDP_DESTINATION_QUEUES = {
    5001: 1,  # CRITICAL
    5002: 2,  # ERROR
    5003: 3,  # WARNING
    5004: 4,  # INFO
    5005: 5,  # Session summary
}
```

For traffic directed to the collector-facing port, the controller applies:

```python
parser.OFPActionSetQueue(queue_id)
```

before the output action.

The switch therefore performs queue selection based on the traffic classification installed by the controller.

---

## 8. Experimental Methodology

The system was evaluated under two configurations.

### Configuration A: QoS Disabled

- OVS HTB QoS was detached from the collector-facing interface.
- A single-root TBF qdisc limited the interface to 10 Mbps.
- TCP background traffic was generated using iperf.
- Four batches of 100 log messages were transmitted, one batch per severity.

### Configuration B: QoS Enabled

- OVS HTB QoS was attached to the collector-facing interface.
- Five traffic classes were configured.
- TCP background traffic was generated using iperf.
- Four batches of 100 log messages were transmitted, one batch per severity.
- OVS queue statistics were collected to verify queue usage.

### Common Workload

| Parameter | Value |
|---|---|
| CRITICAL messages | 100 |
| ERROR messages | 100 |
| WARNING messages | 100 |
| INFO messages | 100 |
| Total messages | 400 |
| Background traffic | TCP using iperf |
| Configured link rate | 10 Mbps |
| UDP destination | 10.0.0.2 |

The collector was restarted before each main experiment to obtain clean application-level packet counts.

---

## 9. Performance Evaluation

The following measurements were obtained from the baseline and QoS-enabled experiments.

### 9.1 Performance Comparison

| Metric | QoS Disabled | QoS Enabled |
|---|---:|---:|
| Total packets expected | 400 | 400 |
| Total packets received | 400 | 400 |
| Packet loss | 0% | 0% |
| Average latency | 132.169 ms | 155.074 ms |
| Minimum latency | 5.688 ms | 11.913 ms |
| Maximum latency | 271.197 ms | 325.430 ms |
| TCP throughput | 9.56 Mbps | 9.55 Mbps |

### 9.2 Observations

1. Both configurations successfully delivered all 400 expected log messages.
2. No UDP packet loss was observed in either experiment.
3. TCP throughput remained approximately 9.5 Mbps in both configurations.
4. The measured average latency was higher in the QoS-enabled experiment.
5. Minimum and maximum latency were also higher in the QoS-enabled experiment.

The experiment therefore demonstrated successful queue classification and traffic delivery, but did not demonstrate an improvement in aggregate application-level latency or TCP throughput.

### 9.3 Queue Statistics

The QoS-enabled experiment produced the following cumulative queue counters:

| Queue | Packets Recorded | Errors |
|---:|---:|---:|
| 0 | 49,801 | 0 |
| 1 | 101 | 0 |
| 2 | 101 | 0 |
| 3 | 101 | 0 |
| 4 | 101 | 0 |
| 5 | 8 | 0 |

Queues 1–4 each recorded 101 packets, consistent with the 100-message experiment batches and one earlier classification test per severity.

Queue 5 recorded session-summary traffic.

These are cumulative counters, not isolated counter deltas for the main experiment.

### 9.4 Experimental Limitations

- Both configurations experienced zero packet loss, so packet-loss improvement could not be demonstrated.
- The experiment used aggregate latency measurements rather than separate latency distributions for each severity.
- The queue statistics are cumulative.
- The baseline TBF and QoS-enabled HTB configurations use different scheduling disciplines.
- A single experiment per configuration is insufficient to establish statistical significance.

Further repeated experiments, per-severity latency measurements and queue-counter deltas would be useful future improvements.

---

## 10. Running the Project

### Requirements

The tested environment consisted of:

- Windows 11 with Ubuntu 24.04 through WSL2
- Mininet 2.3.0
- Open vSwitch 3.3.9
- Ryu 4.34
- Python 3.9 for the Ryu environment
- Python 3 for the application and tests
- Linux HTB traffic control support

### Step 1: Start the Ryu Controller

Open the first Ubuntu terminal:

```bash
cd /mnt/c/Users/sujay/Desktop/distributed_log_aggregation

source ~/sdn-project/ryu39-env/bin/activate

export PYTHONPATH="$PWD:$PYTHONPATH"

ryu-manager --verbose sdn.controller
```

Keep the controller running.

### Step 2: Start Mininet

Open a second Ubuntu terminal:

```bash
cd /mnt/c/Users/sujay/Desktop/distributed_log_aggregation

sudo python3 sdn/topology.py
```

At the Mininet prompt:

```text
mininet> pingall
mininet> net
```

### Step 3: Start the Collector

At the Mininet prompt:

```text
mininet> h2 python3 -u /mnt/c/Users/sujay/Desktop/distributed_log_aggregation/server/udp_server.py > /tmp/log-collector.log 2>&1 &
```

Check the listening ports:

```text
mininet> h2 ss -lun
```

### Step 4: Send Test Logs

```text
mininet> h1 python3 /mnt/c/Users/sujay/Desktop/distributed_log_aggregation/client/udp_client.py --server 10.0.0.2 --severity CRITICAL --count 5 --interval 0.01
```

Repeat with ERROR, WARNING and INFO to test all severity classes.

### Step 5: Inspect the Collector

```text
mininet> h2 tail -n 30 /tmp/log-collector.log
```

The collector should show the received messages and session summaries.

### Step 6: Stop Mininet

```text
mininet> exit
```

Then clean up:

```bash
sudo mn -c
```

**Note:** The commands above start the basic application and SDN integration. The QoS experiment additionally requires the HTB queue configuration and background TCP workload described in the experimental methodology.

---

## 11. Automated Testing

The project uses Python's built-in `unittest` framework.

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

### Test Coverage

The current automated test suite contains three tests:

| Test | Purpose |
|---|---|
| `test_expected_endpoint_bindings` | Checks the configured endpoint IP, MAC and switch-port bindings. |
| `test_authorized_ipv4_requires_ip_mac_and_ingress_port` | Checks IPv4 authorization using all three endpoint attributes. |
| `test_arp_requires_bound_sender_and_matching_ethernet_identity` | Checks ARP sender and Ethernet identity validation. |

### Verified Test Result

```text
Ran 3 tests in 0.000s

OK
```

All three automated unit tests passed.

The automated tests cover the endpoint authorization policy. Live controller operation, OpenFlow negotiation, Mininet connectivity, UDP delivery and QoS queue behaviour were verified separately through the integration experiments.

---

## 12. Limitations and Future Improvements

Potential future improvements include:

- Implement per-severity latency and throughput monitoring.
- Collect queue-counter deltas for individual experiments.
- Repeat performance experiments under different traffic loads.
- Evaluate packet loss and latency under more demanding congestion conditions.
- Implement dynamic QoS policy adjustments based on traffic conditions.
- Expand the topology to support additional log-generating hosts.
- Improve endpoint authentication beyond static IP/MAC/port bindings.
- Add automated integration tests for the controller and collector.

---

## 13. Conclusion

The project demonstrates a distributed UDP log aggregation system integrated with an SDN-controlled network.

The implementation combines socket programming, centralized log collection, endpoint authorization, OpenFlow-based forwarding and HTB QoS queue classification.

The experiments verified successful delivery of 400 log messages under both baseline and QoS-enabled configurations, with zero observed packet loss. The QoS-enabled experiment also confirmed the use of severity-specific queues through OVS queue statistics.

Although the measured aggregate latency did not improve, the project successfully demonstrates the integration of application-level log severity classification with SDN-controlled traffic queue selection.
