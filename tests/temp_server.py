import time

import antt.nat_traversal as nt
from time import sleep
import antt.data_structures as ds

"""
Nat traversal module test
tries to use the start_connection function to return a working socket connection. Acts as the server and wait before kill.
"""


def main():
    o = 5
    src = nt.ConnInfo()
    src.punch_type = "cone"
    src.can_punch = True
    src.private_port = 2223 + o

    dest = nt.ConnInfo()
    dest.punch_type = "cone"
    dest.can_punch = True
    dest.public_ip = "127.0.0.1"
    dest.public_port = 3333 + o
    dest.symmetric_range = (2000, 3000)
    dest.order = dest.order[1:]

    s = nt.start_connection(src, dest, test_for_existing=False)
    ds.DEBUG = True
    # s = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
    # s.start()
    s.block_until_verify(3)
    print("Verified server")
    s.in_queue.put(b"Hello")

    s.block_until_shutdown()
    # print()
    # sleep(1)


if __name__ == '__main__':
    main()
