import unittest

from sdn.policy import (
    AUTHORIZED_IPV4_SOURCES,
    ENDPOINT_BINDINGS,
    is_authorized_arp,
    is_authorized_ipv4_source,
)


class SourceAuthorizationPolicyTests(unittest.TestCase):
    def test_expected_endpoint_bindings(self):
        self.assertEqual(
            AUTHORIZED_IPV4_SOURCES,
            frozenset({"10.0.0.1", "10.0.0.2"}),
        )
        self.assertEqual(ENDPOINT_BINDINGS["10.0.0.1"], {
            "mac": "00:00:00:00:00:01", "port": 1,
        })
        self.assertEqual(ENDPOINT_BINDINGS["10.0.0.2"], {
            "mac": "00:00:00:00:00:02", "port": 2,
        })

    def test_authorized_ipv4_requires_ip_mac_and_ingress_port(self):
        self.assertTrue(is_authorized_ipv4_source(
            "10.0.0.1", "00:00:00:00:00:01", 1
        ))
        self.assertTrue(is_authorized_ipv4_source(
            "10.0.0.2", "00:00:00:00:00:02", 2
        ))
        self.assertFalse(is_authorized_ipv4_source(
            "10.0.0.3", "00:00:00:00:00:03", 3
        ))
        self.assertFalse(is_authorized_ipv4_source(
            "10.0.0.1", "00:00:00:00:00:01", 2
        ))
        self.assertFalse(is_authorized_ipv4_source(
            "10.0.0.1", "00:00:00:00:00:99", 1
        ))

    def test_arp_requires_bound_sender_and_matching_ethernet_identity(self):
        self.assertTrue(is_authorized_arp(
            "10.0.0.1", "00:00:00:00:00:01", "00:00:00:00:00:01", 1
        ))
        self.assertFalse(is_authorized_arp(
            "10.0.0.99", "00:00:00:00:00:99", "00:00:00:00:00:99", 1
        ))
        self.assertFalse(is_authorized_arp(
            "10.0.0.1", "00:00:00:00:00:01", "00:00:00:00:00:01", 2
        ))
        self.assertFalse(is_authorized_arp(
            "10.0.0.1", "00:00:00:00:00:99", "00:00:00:00:00:99", 1
        ))
        self.assertFalse(is_authorized_arp(
            "10.0.0.1", "00:00:00:00:00:01", "00:00:00:00:00:99", 1
        ))


if __name__ == "__main__":
    unittest.main()
