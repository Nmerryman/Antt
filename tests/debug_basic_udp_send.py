import socket
import antt.data_structures as ds

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("", ds.get_first_port_from(20000)))

s.sendto(b"Hello World!", ("127.0.0.1", 12345))
info_packet = ds.Packet()
in_data = s.recv(1000)
info_packet.parse(in_data)
print(in_data)
a_port = info_packet.type
b_port = info_packet.value

for a in range(2):
    s.sendto(b"", ("127.0.0.1", a_port))
    print(s.recv(100))

s.sendto(b"", ("127.0.0.1", b_port))
print(s.recv(100))
print(s.recv(100))




