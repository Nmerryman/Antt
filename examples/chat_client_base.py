import antt.data_structures as ds
from functools import partial


def print_text(client: ds.SocketConnectionTCP, data: bytes):
    val = data.decode()
    if val == "kill":
        print("Other side terminated")
        client.in_queue.put(val)
    else:
        print(val)
        print(">", end="", flush=True)


def start_client(local_port: int, dest: tuple[str, int], acts_as: str):
    client = ds.SocketConnectionTCP(local_port, dest, acts_as=acts_as)
    client.on_message = partial(print_text, client)

    client.start()
    client.block_until_verify()

    while client.verified_connection:
        text = input(">")
        if text:
            client.in_queue.put(text.encode())
        if text == "kill":
            client.in_queue.put(text)
            client.block_until_shutdown()
            break


