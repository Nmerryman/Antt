import antt.data_structures as ds
from queue import Queue
from time import sleep
from pprint import pprint

"""
Tests if socket connection works
Acts as a client and waits for a single message before sending kill to socket object
"""
qin, qout = Queue(), Queue()
conn = ds.SocketConnection(33333, ("127.0.0.1", 22222), qin, qout)
conn.set_buffer_size(20).start()

sleep(2)

if not qout.empty():
    val = qout.get()
    qout.task_done()
    print(val)

qin.put("kill")

pprint(conn.__dict__)
