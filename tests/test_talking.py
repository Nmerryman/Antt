import antt.data_structures as ds
import antt.nat_traversal as nt
from queue import Queue
import sys
from threading import Thread

"""
A very primitive version of a p2p chat connection. Socket death happens somewhere and only sometimes allows 1 message through 1 way.
Doesn't work rn
"""


def print_incoming(t: Queue):
    while True:
        if not t.empty():
            print('\r->' + t.get().decode() + '\n>', end='')
            t.task_done()


def main():
    src_port = int(sys.argv[1])
    target_port = int(sys.argv[2])

    send, recv = Queue(), Queue()
    s = ds.SocketConnection(src_port, ("127.0.0.1", target_port), send, recv).set_buffer_size(20)
    s.start()
    t = Thread(target=print_incoming, args=(recv,))
    t.start()

    while True:
        text = input(">")
        if text != 'kill':
            text = text.encode()
        send.put(text)


if __name__ == '__main__':
    main()
