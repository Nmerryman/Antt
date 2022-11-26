import socket
import antt.data_structures as ds

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("", 20000))

s.sendto(b"Hello World!", ("127.0.0.1", 10012))
info_packet = ds.Packet()
info_packet.parse(s.recv(1000))
a_port = info_packet.type
b_port = info_packet.value

for a in range(2):
    s.sendto(b"", ("127.0.0.1", a_port))
    print(s.recv(100))

s.sendto(b"", ("127.0.0.1", b_port))
print(s.recv(100))
print(s.recv(100))




