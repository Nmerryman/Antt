import pytest

import antt.data_structures as ds
from time import sleep

assert_timeout = 2
assert_delay = .01
assert_limit = int(assert_timeout / assert_delay)


def test_packet_conversions():
    base_string = "0123456789"
    packet = ds.Packet(base_string, 1, None, [1, 2, 3])
    packet_bytes = packet.generate()

    new_packet = ds.Packet()
    new_packet.parse(packet_bytes)

    assert new_packet.type == base_string
    assert new_packet.value == 1
    assert new_packet.data == ""
    assert new_packet.extra == [1, 2, 3]


@pytest.mark.filterwarnings("error")
def test_basic_socket_life():
    """
    Test if we can start and stop these connections through internal means
    """
    conn = ds.SocketConnectionUDP(ds.get_first_port_from(10000), ("", 2222))
    conn.verified_connection = True
    conn.start()
    conn.in_queue.put("kill")

    count = 0
    while conn.is_alive() and count < assert_limit:
        sleep(assert_delay)
        count += 1

    assert not conn.is_alive()
    assert not conn.alive


@pytest.mark.filterwarnings
def test_basic_udp_socket_send():
    """
    Send a basic message from one comm to the other
    """
    port_sender = ds.get_first_port_from(2222)
    port_receiver = ds.get_first_port_from(3333)
    sender = ds.SocketConnectionUDP(port_sender, ("127.0.0.1", port_receiver))
    receiver = ds.SocketConnectionUDP(port_receiver, ("127.0.0.1", port_sender))

    sender.start()
    receiver.start()

    # Wait for both to be alive
    count = 0
    while not receiver.alive and count < assert_limit:
        sleep(assert_delay)
        count += 1
    assert count != assert_limit

    # Wait for message to be sent
    sender.in_queue.put(b"Hello")
    count = 0
    while not sender.in_queue.empty() and count < assert_limit:
        sleep(assert_delay)
        count += 1
    assert count != assert_limit

    message = receiver.block_until_message()
    assert sender.verified_connection
    assert receiver.verified_connection
    sender.in_queue.put("kill")
    receiver.in_queue.put("kill")

    assert message == b"Hello"


def test_basic_tcp_socket_send():
    test_port = 22222
    sender_port = ds.get_first_port_from(test_port)
    receiver_port = ds.get_first_port_from(test_port + 10000)
    sender = ds.SocketConnectionTCP(sender_port, ("127.0.0.1", receiver_port))
    receiver = ds.SocketConnectionTCP(receiver_port, ("127.0.0.1", sender_port), acts_as="server")

    sender.start()
    receiver.start()

    # sender.block_until_verify()
    # Make sure we connect
    count = 0
    while not (sender.verified_connection and receiver.verified_connection and sender.alive and receiver.alive) and count < assert_limit:
        sleep(assert_delay)
        count += 1
    assert count < assert_limit
    assert sender.verified_connection
    assert receiver.verified_connection
    assert sender.alive
    assert receiver.alive

    sender.in_queue.put(b"test text")
    while not sender.in_queue.empty() and count < assert_limit:
        sleep(assert_delay)
        count += 1
    assert count < assert_limit

    message = receiver.block_until_message()
    sender.in_queue.put("kill")
    receiver.in_queue.put("kill")

    # Make sure we shut down
    count = 0
    while (sender.alive or receiver.alive) and count < assert_limit:
        sleep(assert_delay)
        count += 1
    assert count < assert_limit

    assert message == b"test text"


def test_basic_tcp_socket_send2():
    test_port = 22202
    sender_port = ds.get_first_port_from(test_port)
    receiver_port = ds.get_first_port_from(test_port + 10000)
    sender = ds.SocketConnectionTCP(sender_port, ("127.0.0.1", receiver_port))
    receiver = ds.SocketConnectionTCP(receiver_port, ("127.0.0.1", sender_port), acts_as="server")

    sender.start()
    receiver.start()

    # Make sure we connect
    sender.block_until_verify()
    assert sender.verified_connection
    assert receiver.verified_connection

    sender.in_queue.put(b"test text")

    message = receiver.block_until_message()

    # Make sure we shut down
    receiver.in_queue.put(b"waiting for shutdown")
    receiver.block_until_shutdown()
    sender.block_until_shutdown()

    assert not sender.alive and not receiver.alive

    assert message == b"test text"

# test_basic_tcp_socket_send2()
