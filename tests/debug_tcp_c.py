import antt.data_structures as ds
from time import sleep

port = 22200
dest_port = port + 100
client = ds.SocketConnectionTCP(port, ("127.0.0.1", dest_port))

client.start()
client.block_until_verify(2)

print(client.verified_connection)
client.in_queue.put(b"test")
# client.in_queue.put("kill")
# sleep(3)
client.block_until_shutdown()
print(client.in_queue.empty())
