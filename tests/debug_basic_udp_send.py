import antt.data_structures as ds
from queue import Queue

"""
Tests if socket connection works
Acts as a server by assuming client is already connected, and just sends a message to target. Then kills self
"""
qin, qout = Queue(), Queue()
ds.SocketConnection(22222, ("127.0.0.1", 33333), qin, qout).set_buffer_size(20).start()

data = b"aoeu1234"*10

qin.put(data)

qin.put("kill")

