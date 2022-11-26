import socket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("", 20000))

s.sendto(b"Hello World!", ("127.0.0.1", 10000))
print(s.recv(1000))



