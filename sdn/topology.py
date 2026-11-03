#!/usr/bin/env python3
"""Two-host Mininet topology for the log collector integration stage."""

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo


class LogAggregationTopology(Topo):
    def build(self):
        h1 = self.addHost(
            "h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01"
        )
        h2 = self.addHost(
            "h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02"
        )
        switch = self.addSwitch(
            "s1",
            protocols="OpenFlow13",
            failMode="secure",
        )
        # Fix switch-side ports to match sdn.policy endpoint bindings.
        self.addLink(h1, switch, port2=1)
        self.addLink(h2, switch, port2=2)


def run():
    net = Mininet(
        topo=LogAggregationTopology(),
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=False,
    )
    net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )

    try:
        net.start()
        CLI(net)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
