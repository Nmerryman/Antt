import pytest

import antt.data_structures as ds
from time import sleep

assert_timeout = 3
assert_delay = .01
assert_limit = int(assert_timeout / assert_delay)
# pytest.mark.filterwarnings("error")


@pytest.mark.filterwarnings("error")
def test_basic_socket_life():
    """
    Test if we can start and stop these connections through internal means
    """
    conn = ds.SocketConnection(ds.get_first_port_from(10000), ("", 2222))
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
def test_basic_socket_send():
    """
    Send a basic message from one comm to the other
    """
    port_sender = ds.get_first_port_from(2222)
    port_receiver = ds.get_first_port_from(3333)
    sender = ds.SocketConnection(port_sender, ("127.0.0.1", port_receiver))
    receiver = ds.SocketConnection(port_receiver, ("127.0.0.1", port_sender))

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
    sender.in_queue.put("kill")
    receiver.in_queue.put("kill")

    assert message == b"Hello"


