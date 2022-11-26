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
                data, ip = self.socket.recvfrom(self.buffer_size)
                self.socket.sendto(data, ip)
            except socket.timeout:
                pass


