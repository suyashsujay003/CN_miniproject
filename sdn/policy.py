"""Layer 2/3 endpoint bindings for the fixed two-host Mininet lab."""

# The topology explicitly assigns these MAC addresses and s1 ingress ports.
ENDPOINT_BINDINGS = {
    "10.0.0.1": {"mac": "00:00:00:00:00:01", "port": 1},
    "10.0.0.2": {"mac": "00:00:00:00:00:02", "port": 2},
}
AUTHORIZED_IPV4_SOURCES = frozenset(ENDPOINT_BINDINGS)


def is_authorized_ipv4_source(source_ip, source_mac, ingress_port):
    """Check an IPv4 source against its configured MAC and switch port."""
    binding = ENDPOINT_BINDINGS.get(source_ip)
    return bool(
        binding
        and source_mac.lower() == binding["mac"]
        and ingress_port == binding["port"]
    )


def is_authorized_arp(sender_ip, sender_mac, ethernet_source, ingress_port):
    """Require ARP sender identity and Ethernet identity to match a binding."""
    binding = ENDPOINT_BINDINGS.get(sender_ip)
    return bool(
        binding
        and sender_mac.lower() == binding["mac"]
        and ethernet_source.lower() == binding["mac"]
        and ingress_port == binding["port"]
    )
