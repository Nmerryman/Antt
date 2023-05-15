import random
import socket
import multiprocessing as mp
import time
from time import sleep
from typing import Union
import antt.data_structures as ds
import json
from antt.cust_logging import *


class ConnInfo:

    def __init__(self):
        # What methods can we use for reachability
        self.can_udp: bool = True
        self.can_upnp: bool = False
        self.prioritize_upnp_tcp: bool = True
        self.needs_relay: bool = False

        self.order = ["local", "upnp connect", "punch cone", "upnp open", "punch symmetric", "relay"]
        self.timings = {"local": 3, "upnp connect": 5, "punch cone": 10, "upnp open": 15, "punch symmetric": 15, "relay": 10}  # Time given for each strategy before trying next one

        # Punch + upnp relevant info
        # Matters more for local connection
        self.private_ip: str = ""  # probably don't need, but papers recommended it
        self.private_port: int = 0   # probably don't need, but papers recommended it

        # Matters more for punching
        self.public_ip: str = ""
        self.public_port: int = 0

        self.upnp_port_start = 5554
        self.upnp_backup_count = 3
        self.upnp_backup_offsets = 101

        # Relay is intended to be tcp
        self.relay_session_token = ""

        self.punch_type: str = ""
        # We allow ("cone", "symmetric")
        self.symmetric_range: tuple[int, int] = (0, 0)

        self.conn_start_time: int = 0  # set a time to start sending commands to try to connect in case timing matters
        self.id = random.randint(1, 99999999)

    def dumps(self):
        return json.dumps(self.__dict__).encode()

    def loads(self, data: bytes):
        self.__dict__ = json.loads(data.decode())

    def set_private_ip(self):
        hostname = socket.gethostname()
        self.private_ip = socket.gethostbyname(hostname)


def start_connection(src: ConnInfo, dest: ConnInfo, test_for_existing: bool = True) -> ds.SocketConnection:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((src.private_ip, src.private_port))

    # test if we already have a working connection
    if test_for_existing:
        s.settimeout(1)
        s.sendto(b"\x01", (dest.public_ip, dest.public_port))
        try:
            # We may want to use a blocking_until func instead
            data = s.recv(10)
            if data == b"\x02":
                s.settimeout(0)
                s.close()
                conn = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
                conn.start()
                return conn
        except socket.timeout:
            s.settimeout(0)
        except ConnectionResetError:
            s.settimeout(0)

    # print("making new")

    retry_count = 6
    timeout = .5
    for a in dest.order:
        if a == "punch symmetric":
            # Copied from cone and prob wrong
            s.settimeout(timeout)
            count = 0
            sleep(1.5)
            while count < retry_count:
                if count % 3 == 0:
                    symm_shotgun(s, dest)
                try:
                    s.sendto(b"\x01", (dest.public_ip, dest.public_port))
                    data = s.recv(10)
                    if data == b"\x02":
                        s.close()
                        conn = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
                        conn.start()
                        print("got ack")
                        return conn
                    elif data == b"\x01":
                        s.sendto(b"\x02", (dest.public_ip, dest.public_port))
                        s.close()
                        conn = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
                        conn.start()
                        print("got syn")
                        return conn
                except TimeoutError:
                    print("inc")
                    count += 1
                except ConnectionResetError:
                    sleep(timeout)
                    count += 1

            if count == retry_count:
                raise ds.ConnectionIssue(f"No response after {retry_count} tries ({retry_count * timeout}s)")
        elif a == "punch cone":
            log_txt(f"{src.private_port}: Trying punch cone", "start_conn")
            s.settimeout(timeout)
            count = 0
            sleep(0.5)
            while count < retry_count:
                try:
                    s.sendto(b"\x01", (dest.public_ip, dest.public_port))
                    log_txt(f"{src.private_port}: sent syn")
                    data = s.recv(10)
                    if data == b"\x02":
                        s.close()
                        conn = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
                        conn.start()
                        log_txt(f"{src.private_port}: got ack", "start_conn")
                        return conn
                    elif data == b"\x01":
                        s.sendto(b"\x02", (dest.public_ip, dest.public_port))
                        s.close()
                        conn = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
                        conn.start()
                        log_txt(f"{src.private_port}: got syn", "start_conn")
                        return conn
                except socket.timeout:
                    log_txt(f"{src.private_port}: Hit socket.timeout", "start_conn")
                    sleep(timeout)
                    count += 1
                except ConnectionResetError:
                    log_txt(f"{src.private_port}: Hit ConnectionResetError", "start_conn")
                    sleep(timeout)
                    count += 1

            if count == retry_count:
                raise ds.ConnectionIssue(f"No response after {retry_count} tries ({retry_count * timeout}s)")

        elif a == "local":
            # We don't have a firewall in the way
            s.close()
            conn = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))  # TODO consider using dest private instead
            conn.start()
            return conn


def symm_shotgun(s: socket.socket, dest: ConnInfo):
    for i in range(dest.symmetric_range[0], dest.symmetric_range[1]):
        s.sendto(b"\x00", (dest.public_ip, i))


class ClientInfo:
    """
    This is for internal information + decision making
    It currently hold info/state for all alive connections + stuff
    Probably wont be used at the end
    """
    def __init__(self):
        self.reachable: bool = False
        self.type = ""
        self.public_ip = ""
        self.device_ip = ""
        self.punched_ports = []
        self.symm_test_range = (0, 0)
        self.upnp_avail: bool = False
        self.upnp_ports = []
        self.buffer_size = 200
        self.symm_test_count = 50
        self.start_port = 4554

    def dumps(self):
        return json.dumps(self.__dict__).encode()

    def loads(self, data: bytes):
        self.__dict__ = json.loads(data.decode())

    def detect_nat_type(self, discover_server: tuple[str, int]):
        """
        This assumes my rendezvous implementation/responses
        """
        # Create socket
        start_port = ds.get_first_port_from(4441)
        name = str(random.randint(1, 999999))
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", start_port))
        s.settimeout(5)

        try:
            s.sendto(ds.Packet("discover").generate(), discover_server)

            data = ds.Packet().parse(s.recv(self.buffer_size))
            sa = data.type
            sb = data.value
            sc = data.data
        except ConnectionResetError as e:
            log_txt("Discover didn't respond in time", "client detect nat")
            raise e

        for a in range(self.symm_test_count):
            symm_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_port = ds.get_first_port_from(self.start_port + a)
            symm_socket.bind(("", temp_port))
            symm_socket.sendto(ds.Packet(name).generate(), (discover_server[0], sa))

        final_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        final_socket.bind(("", ds.get_first_port_from(self.start_port + self.symm_test_count + 200)))
        final_socket.sendto(ds.Packet(name).generate(), (discover_server[0], sa))
        final_socket.sendto(ds.Packet(name).generate(), (discover_server[0], sb))

        try:
            s.sendto(ds.Packet("status", name).generate(), discover_server)
            start_time = time.time()
            status = ds.Packet().parse(s.recv(self.buffer_size))
            print(time.time() - start_time, status)
        except Exception as e:
            log_txt("Failed to return status request", "client detect nat")
            raise e
        if status.data[1] == status.extra[1]:
            # Different destinations (ports) show the same source
            self.type = "cone"
            s.sendto(ds.Packet("third").generate(), discover_server)
            try:
                response = s.recv(self.buffer_size)
                self.reachable = True
            except Exception as e:
                log_txt("No response from third", "client detect nat")
                raise e
        else:
            self.type = "symmetric"

        self.symm_test_range = (status.type, status.value)
        self.public_ip = status.data[0]
        self.device_ip = socket.gethostbyname(socket.gethostname())

    def gen_conn_info(self):
        base = ConnInfo()


class DetectionServer:

    def __init__(self, root_port: int):
        self.root_port = ds.get_first_port_from(root_port)
        self.echo_port_a = ds.get_first_port_from(self.root_port + 10)
        self.echo_port_b = ds.get_first_port_from(self.root_port + 20)
        self.echo_port_c = ds.get_first_port_from(self.root_port + 30)
        # noinspection PyTypeChecker
        self.pro_a: mp.Process = None  # Collector
        # noinspection PyTypeChecker
        self.pro_b: mp.Process = None  # Alt dest
        # noinspection PyTypeChecker
        self.pro_c: mp.Process = None  # New sender
        self.port_collection = dict()  # {sent name: (min, max, last a (ip, port), last b (ip, port))}
        self.buffer_size = 100

    def launch(self):
        # I don't think we should need to worry about too much traffic
        sr = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sr.bind(("", self.root_port))
        sr.settimeout(0)
        sa = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sa.bind(("", self.echo_port_a))
        sa.settimeout(0)
        sb = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sb.bind(("", self.echo_port_b))
        sb.settimeout(0)
        sc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sc.bind(("", self.echo_port_c))
        sc.settimeout(0)

        recv_delay = .01
        while True:
            try:
                while True:
                    raw_data, ip = sa.recvfrom(self.buffer_size)
                    data = ds.Packet().parse(raw_data).type
                    if data in self.port_collection.keys():
                        tmin, tmax, tlasta, tlastb = self.port_collection[data]
                    else:
                        tmin, tmax, tlasta, tlastb = 99999999, -1, ("", 1), ("", 1)
                    if ip[1] < tmin:
                        tmin = ip[1]
                    if ip[1] > tmax:
                        tmax = ip[1]
                    tlasta = ip
                    self.port_collection[data] = (tmin, tmax, tlasta, tlastb)
                    sleep(recv_delay)
            except BlockingIOError:
                log_txt("DS: BIOE (sa)", "DS socket loop")
                pass
            except Exception as e:
                raise e

            try:
                while True:
                    raw_data, ip = sb.recvfrom(self.buffer_size)
                    data = ds.Packet().parse(raw_data).type
                    if data in self.port_collection.keys():
                        tmin, tmax, tlasta, tlastb = self.port_collection[data]
                    else:
                        tmin, tmax, tlasta, tlastb = 99999999, -1, ("", 1), ("", 1)
                    if ip[1] < tmin:
                        tmin = ip[1]
                    if ip[1] > tmax:
                        tmax = ip[1]
                    tlastb = ip
                    self.port_collection[data] = (tmin, tmax, tlasta, tlastb)
                    sleep(recv_delay)
            except BlockingIOError:
                log_txt("DS: BIOE (sb)", "DS socket loop")
                pass
            except Exception as e:
                raise e

            try:
                while True:
                    data, ip = sr.recvfrom(self.buffer_size)  # We assume we are sent packets here
                    packet = ds.Packet().parse(data)
                    if packet.type == "status":
                        if packet.value in self.port_collection.keys():
                            vals = self.port_collection[packet.value]
                            sr.sendto(ds.Packet(*vals).generate(), ip)
                        else:
                            sr.sendto(ds.Packet("not found", packet.value).generate(), ip)
                    elif packet.type == "third":
                        sc.sendto(str(ip).encode(), ip)
                    elif packet.type == "discover":
                        sr.sendto(ds.Packet(self.echo_port_a, self.echo_port_b, self.echo_port_c).generate(), ip)
                    elif packet.type == "echo":
                        sr.sendto(ds.Packet(data).generate(), ip)

            except BlockingIOError:
                log_txt("DS: BIOE (sr)", "DS socket loop")
                pass
            except ConnectionResetError:
                log_txt("DS: CRE (sr)", "DS socket loop")
                pass
            except Exception as e:
                raise e

            # This may still be too high. It causes CRE errors sometimes
            sleep(.01)

    def kill(self):
        if self.pro_a:
            self.pro_a.terminate()
        if self.pro_b:
            self.pro_b.terminate()


def echo_server(s_port: int, root_port: int, ident: str, buffer_size: int):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", s_port))
    while True:
        data, ip = s.recvfrom(buffer_size)
        if data == b"new source":  # only called when new dest incoming is requested
            mp.Process(target=simple_send, args=(ip, f"{ip[0]} {ip[1]} ".encode() + data, extra_port, .5)).start()
        else:
            s.sendto(f"{ip[0]} {ip[1]} ".encode() + data, ip)


def simple_send(target: tuple[str, int], msg: Union[bytes, str], port: int = None, delay: int = 0):
    """
    Make sure message is sendable, bind if needed and then send to the target. Optional delay included
    """
    sleep(delay)
    if isinstance(msg, str):
        msg = msg.encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if port:
        s.bind(("", port))
    s.sendto(msg, target)
