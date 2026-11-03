"""Ryu OpenFlow 1.3 controller for the distributed log lab.

IPv4 forwarding is restricted to the explicitly authorized Mininet endpoints.
ARP is forwarded so the hosts can resolve each other's MAC addresses.
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from ryu.lib.packet import arp, ethernet, ether_types, ipv4, packet, udp
from ryu.ofproto import ofproto_v1_3

from sdn.policy import is_authorized_arp, is_authorized_ipv4_source


DROP_PRIORITY = 100
FORWARD_PRIORITY = 10
BLOCK_DURATION_SECONDS = 30
LEARNED_FLOW_IDLE_TIMEOUT_SECONDS = 60
UDP_DESTINATION_QUEUES = {
    5001: 1,  # CRITICAL
    5002: 2,  # ERROR
    5003: 3,  # WARNING
    5004: 4,  # INFO
    5005: 5,  # Session summary
}
COLLECTOR_EGRESS_PORT = 2


class LogAggregationController(app_manager.RyuApp):
    """Learning switch with an explicit IPv4 source allowlist."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(LogAggregationController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.logger.info("Log aggregation controller started (OpenFlow 1.3)")

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def datapath_state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.mac_to_port.pop(datapath.id, None)
            self.logger.info("Switch disconnected: %s; cleared learned MACs", datapath.id)

    def add_flow(self, datapath, priority, match, actions=None,
                 idle_timeout=0, hard_timeout=0):
        parser = datapath.ofproto_parser
        instructions = []
        if actions is not None:
            instructions = [
                parser.OFPInstructionActions(
                    datapath.ofproto.OFPIT_APPLY_ACTIONS,
                    actions,
                )
            ]

        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
        ))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Remove stale rules left by a previous controller connection before
        # installing this controller's table-miss rule.
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            table_id=ofproto.OFPTT_ALL,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=parser.OFPMatch(),
        ))

        self.mac_to_port[datapath.id] = {}
        self.datapaths[datapath.id] = datapath
        self.add_flow(
            datapath,
            priority=0,
            match=parser.OFPMatch(),
            actions=[parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER,
            )],
        )
        self.logger.info("Switch connected: %s", datapath.id)

    def _packet_out(self, datapath, msg, actions):
        ofproto = datapath.ofproto
        datapath.send_msg(datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=msg.match["in_port"],
            actions=actions,
            data=msg.data,
        ))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        arp_pkt = pkt.get_protocol(arp.arp)
        udp_pkt = pkt.get_protocol(udp.udp)

        if ip_pkt is not None:
            if not is_authorized_ipv4_source(
                ip_pkt.src, eth.src, msg.match["in_port"]
            ):
                self.add_flow(
                    datapath,
                    priority=DROP_PRIORITY,
                    match=parser.OFPMatch(
                        eth_type=ether_types.ETH_TYPE_IP,
                        ipv4_src=ip_pkt.src,
                        eth_src=eth.src,
                        in_port=msg.match["in_port"],
                    ),
                    hard_timeout=BLOCK_DURATION_SECONDS,
                )
                self.logger.warning("Unauthorized IPv4 source blocked: %s", ip_pkt.src)
                return
            eth_type = ether_types.ETH_TYPE_IP
            ip_protocol = ip_pkt.proto
        elif arp_pkt is not None:
            if not is_authorized_arp(
                arp_pkt.src_ip,
                arp_pkt.src_mac,
                eth.src,
                msg.match["in_port"],
            ):
                self.logger.warning(
                    "Inconsistent ARP identity rejected: %s / %s on port %s",
                    arp_pkt.src_ip,
                    arp_pkt.src_mac,
                    msg.match["in_port"],
                )
                return
            eth_type = ether_types.ETH_TYPE_ARP
        # Non-ARP, non-IPv4 traffic is intentionally not forwarded.
        else:
            return

        dpid = datapath.id
        in_port = msg.match["in_port"]
        learned = self.mac_to_port.setdefault(dpid, {})
        learned[eth.src] = in_port
        out_port = learned.get(eth.dst, ofproto.OFPP_FLOOD)

        if out_port != ofproto.OFPP_FLOOD and out_port != in_port:
            match_fields = {
                "in_port": in_port,
                "eth_src": eth.src,
                "eth_dst": eth.dst,
                "eth_type": eth_type,
            }
            if ip_pkt is not None:
                # Keep source authorization in every learned IPv4 rule so the
                # forwarding entry cannot authorize a different source IP.
                match_fields["ipv4_src"] = ip_pkt.src
                match_fields["ip_proto"] = ip_protocol
                if udp_pkt is not None:
                    match_fields["udp_dst"] = udp_pkt.dst_port

            queue_id = None
            if (out_port == COLLECTOR_EGRESS_PORT
                    and udp_pkt is not None):
                queue_id = UDP_DESTINATION_QUEUES.get(udp_pkt.dst_port)

            flow_actions = []
            if queue_id is not None:
                flow_actions.append(parser.OFPActionSetQueue(queue_id))
            flow_actions.append(parser.OFPActionOutput(out_port))

            self.add_flow(
                datapath,
                priority=FORWARD_PRIORITY,
                match=parser.OFPMatch(**match_fields),
                actions=flow_actions,
                idle_timeout=LEARNED_FLOW_IDLE_TIMEOUT_SECONDS,
            )

        actions = []
        if out_port == COLLECTOR_EGRESS_PORT and udp_pkt is not None:
            queue_id = UDP_DESTINATION_QUEUES.get(udp_pkt.dst_port)
            if queue_id is not None:
                actions.append(parser.OFPActionSetQueue(queue_id))
        actions.append(parser.OFPActionOutput(out_port))
        self._packet_out(datapath, msg, actions)
