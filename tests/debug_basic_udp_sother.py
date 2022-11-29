# Client B
import socket
import antt.data_structures as ds

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("", ds.get_first_port_from(25000)))
s.settimeout(0.1)

packet = ds.Packet("status", "aoeu")
# packet = ds.Packet("auth", "aoeu", "info2")
s.sendto(packet.generate(), ("127.0.0.1", 12345))
print(s.recv(200))





