import socket
import antt.servers as serv
from time import sleep


def test_echo_server():
    # Simply test if the echo server starts, works, and closes
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(.01)
    s = serv.EchoServer()
    s.start()
    assert s.is_alive() and s.alive

    try:
        data = client.recv(100)
        assert False
    except socket.timeout:
        # We expected nothing
        pass

    client.sendto(b"test", ("127.0.0.1", s.src_port))
    try:
        data = client.recv(100)
        assert data == b"test"
    except socket.timeout:
        # We should get a response
        assert False

    s.alive = False
    sleep(.1)
    assert not s.is_alive()