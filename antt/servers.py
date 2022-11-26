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

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.alive = True

        self.info_port = ds.get_first_port_from(10010)
        self.loc_port_a = ds.get_first_port_from(10020)
        self.loc_port_b = ds.get_first_port_from(10030)
        self.send_port_c = ds.get_first_port_from(10040)
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
            try:
                while True:
                    data, ip = self.info_socket.recvfrom(self.buffer_size)
                    self.info_socket.sendto(info_msg, ip)
            except socket.timeout:
                pass

            try:
                while True:
                    data, ip = self.loc_a_socket.recvfrom(self.buffer_size)
                    self.info_socket.sendto(f"a {ip[0]} {ip[1]}".encode(), ip)
            except socket.timeout:
                pass

            try:
                while True:
                    data, ip = self.loc_b_socket.recvfrom(self.buffer_size)
                    self.loc_b_socket.sendto(f"b {ip[0]} {ip[1]}".encode(), ip)
                    self.send_c_socket.sendto(f"c {ip[0]} {ip[1]}".encode(), ip)
            except socket.timeout:
                pass
