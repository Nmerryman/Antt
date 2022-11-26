import pytest

import antt.data_structures as ds
from time import sleep

assert_timeout = 1
assert_delay = .01
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
    while conn.is_alive() and count < int(assert_timeout / assert_delay):
        sleep(assert_delay)
        count += 1

    assert not conn.is_alive()
    assert not conn.alive


