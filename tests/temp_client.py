import antt.nat_traversal as nt
from time import sleep
import antt.data_structures as ds

"""
Nat traversal module test
tries to use the start_connection function to return a working socket connection. Acts as the client and wait before kill.
"""

def main():
    src = nt.ConnInfo()
    src.punch_type = "cone"
    src.can_punch = True
    src.private_port = 3335

    dest = nt.ConnInfo()
    dest.punch_type = "cone"
    dest.can_punch = True
    dest.public_ip = "127.0.0.1"
    dest.public_port = 2225

    # s = nt.start_connection(src, dest)
    ds.DEBUG = True
    s = ds.SocketConnection(src.private_port, (dest.public_ip, dest.public_port))
    s.start()
    s.block_until_verify(3)

    print(s.out_queue.get(timeout=3))

    s.in_queue.put("kill")


if __name__ == '__main__':
    main()
