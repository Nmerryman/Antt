import antt.data_structures as ds
from threading import Thread
import socket


class EchoServer(Thread):

    def __init__(self, src_port: int = None):
        super().__init__()
        if src_port:
            self.src_port = src_port
        else:
            self.src_port = ds.get_first_port_from(10000)
        self.daemon = True
        # I should probably propagate this "bind in init to ensure valid first" methodology
        self.buffer_size = 1000
        self.alive = True
        self.timeout_len = .1
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.src_port))

    def run(self) -> None:
        self.socket.settimeout(self.timeout_len)
        while self.alive:
            try:
                data, ip = self.socket.recvfrom(self.buffer_size)  # No overflow checks could crash
                self.socket.sendto(data, ip)
            except socket.timeout:
                pass


class LocateServer(Thread):

    def __init__(self, info_port: int = None, other_ports: tuple[int, int, int] = None):
        super().__init__()
        self.daemon = True
        self.alive = True

        # This should probably get reorganized by creating each socket before finding next port but this hack is ok for now
        if info_port:
            self.info_port = info_port
        else:
            self.info_port = ds.get_first_port_from(10010)
        if other_ports:
            self.loc_port_a = other_ports[0]
            self.loc_port_b = other_ports[1]
            self.send_port_c = other_ports[2]
        else:
            self.loc_port_a = ds.get_first_port_from(self.info_port + 10)
            self.loc_port_b = ds.get_first_port_from(self.info_port + 20)
            self.send_port_c = ds.get_first_port_from(self.info_port + 30)
        self.buffer_size = 256
        self.timeout_len = .1

        self.info_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.info_socket.bind(("", self.info_port))
        self.info_socket.settimeout(self.timeout_len)
        self.loc_a_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.loc_a_socket.bind(("", self.loc_port_a))
        self.loc_a_socket.settimeout(self.timeout_len)
        self.loc_b_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.loc_b_socket.bind(("", self.loc_port_b))
        self.loc_b_socket.settimeout(self.timeout_len)
        self.send_c_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_c_socket.bind(("", self.send_port_c))
        self.send_c_socket.settimeout(self.timeout_len)

    def run(self):
        info_packet = ds.Packet(self.loc_port_a, self.loc_port_b)
        info_msg = info_packet.generate()
        while self.alive:
            # Tell client important server ports
            try:
                while True:
                    data, ip = self.info_socket.recvfrom(self.buffer_size)
                    self.info_socket.sendto(info_msg, ip)
            except socket.timeout:
                pass

            # Use as an echo for base location comparison + nat symmetric properties discovery
            try:
                while True:
                    data, ip = self.loc_a_socket.recvfrom(self.buffer_size)
                    self.info_socket.sendto(f"a {ip[0]} {ip[1]}".encode(), ip)
            except socket.timeout:
                pass

            # Extra echo to contrast different target location (port)
            # send_c_socket is to check nat cone status
            try:
                while True:
                    data, ip = self.loc_b_socket.recvfrom(self.buffer_size)
                    self.loc_b_socket.sendto(f"b {ip[0]} {ip[1]}".encode(), ip)
                    self.send_c_socket.sendto(f"c {ip[0]} {ip[1]}".encode(), ip)
            except socket.timeout:
                pass


class RendezvousServer(Thread):

    def __init__(self, src_port: int = None):
        super().__init__()
        self.daemon = True

        if src_port:
            self.src_port = src_port
        else:
            self.src_port = ds.get_first_port_from(10100)

        self.collection = {}
        self.timeout_len = .1
        self.buffer_size = 256

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.src_port))
        self.socket.settimeout(self.timeout_len)
        self.alive = True

    def run(self) -> None:
        while self.alive:
            try:
                while True:
                    data, ip = self.socket.recvfrom(self.buffer_size)
                    packet = ds.Packet().parse(data)  # we assume {auth, channel_id, info_packet}
                    if packet.type == "status":  # We're assuming that auth value can never be this
                        if packet.value in self.collection:
                            self.socket.sendto(ds.Packet(packet.value, "waiting").generate(), ip)
                        else:
                            self.socket.sendto(ds.Packet(packet.value, "missing").generate(), ip)
                    else:
                        # We're going to assume that auth is taken care of
                        if packet.value not in self.collection:  # New channel
                            self.collection[packet.value] = (ip, packet.data)
                        else:  # Previous channel found
                            if ip != self.collection[packet.value][0]:  # if from a different source ip
                                # We fire the exchange
                                # Send to orig
                                self.socket.sendto(ds.Packet(packet.value, packet.data).generate(), self.collection[packet.value][0])
                                # Send to latest
                                self.socket.sendto(ds.Packet(packet.value, self.collection[packet.value][1]).generate(), ip)
                                # Remove entry from collection
                                del self.collection[packet.value]
            except socket.timeout:
                # Do other stuff like maintenance
                pass
