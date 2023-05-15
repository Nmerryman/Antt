# Client A
import socket
import antt.data_structures as ds
import antt.nat_traversal as nt

local = "127.0.0.1"
aws = "3.21.27.156"
target = aws
test_name = "aoeu"

def single():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", ds.get_first_port_from(20001)))
    s.settimeout(.1)

    packet = ds.Packet("discover",  test_name)
    # packet = ds.Packet("aoeu")
    # packet = ds.Packet("discover")
    s.sendto(packet.generate(), (target, 4454))
    temp = s.recvfrom(200)
    print(temp)
    print(ds.Packet().parse(temp[0]))


def multi():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", ds.get_first_port_from(20003)))
    s.settimeout(.1)

    packet = ds.Packet("status", "aoeu")
    # packet = ds.Packet("aoeu")
    # packet = ds.Packet("discover")
    s.sendto(ds.Packet(test_name).generate(), (target, 4464))
    s.sendto(ds.Packet(test_name).generate(), (target, 4474))
    s.sendto(ds.Packet("status", test_name).generate(), (target, 4454))
    print(s.recv(200))


def detect():
    info = nt.ClientInfo()
    info.detect_nat_type((target, 4454))
    print(info.__dict__)


detect()
