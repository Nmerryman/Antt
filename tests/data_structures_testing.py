# Server
import antt.servers as s

server = s.RendezvousServer(12345)
server.start()
print(server.src_port)
input()
server.alive = False
input()

