import antt.nat_traversal as nt
from time import sleep

"""
Nat traversal module test
tries to use the start_connection function to return a working socket connection. Acts as the server and wait before kill.
"""

def main():
    src = nt.ConnInfo()
    src.punch_type = "cone"
    src.can_punch = True
    src.private_port = 2222

    dest = nt.ConnInfo()
    dest.punch_type = "symmetric"
    dest.can_punch = True
    dest.public_ip = "127.0.0.1"
    dest.public_port = 3333
    dest.symmetric_range = (2000, 3000)

    s = nt.start_connection(src, dest)
    sleep(1)

    s.in_queue.put(b"Hello")
    s.in_queue.put("kill")


if __name__ == '__main__':
    main()
