# Client A
import socket
import antt.data_structures as ds


def single():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", ds.get_first_port_from(20000)))
    s.settimeout(.1)

    packet = ds.Packet("status", "aaoeu")
    # packet = ds.Packet("aoeu")
    # packet = ds.Packet("discover")
    s.sendto(packet.generate(), ("127.0.0.1", 4454))
    print(s.recvfrom(200))


def multi():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", ds.get_first_port_from(20001)))
    s.settimeout(.1)

    packet = ds.Packet("status", "aoeu")
    # packet = ds.Packet("aoeu")
    # packet = ds.Packet("discover")
    s.sendto(ds.Packet("aoeu").generate(), ("127.0.0.1", 4464))
    s.sendto(ds.Packet("aoeu").generate(), ("127.0.0.1", 4474))
    s.sendto(ds.Packet("status", "aoeu").generate(), ("127.0.0.1", 4454))
    print(s.recv(200))

single()

