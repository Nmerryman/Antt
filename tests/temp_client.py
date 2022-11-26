import antt.nat_traversal as nt

"""
Nat traversal module test
tries to use the start_connection function to return a working socket connection. Acts as the client and wait before kill.
"""

def main():
    src = nt.ConnInfo()
    src.punch_type = "symmetric"
    src.can_punch = True
    src.private_port = 3333

    dest = nt.ConnInfo()
    dest.punch_type = "cone"
    dest.can_punch = True
    dest.public_ip = "127.0.0.1"
    dest.public_port = 2222

    s = nt.start_connection(src, dest)
    print(s.block_until_message())
    s.in_queue.put("kill")


if __name__ == '__main__':
    main()
