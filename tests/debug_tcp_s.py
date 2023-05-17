import antt.data_structures as ds
from time import sleep

dest_port = 22200
port = dest_port + 100
server = ds.SocketConnectionTCP(port, ("127.0.0.1", dest_port), acts_as="server")

server.start()
server.block_until_verify(2)

print(server.verified_connection)
print(server.block_until_message())
