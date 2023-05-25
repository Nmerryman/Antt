import antt.data_structures as ds
import code
from pprint import pprint

if __name__ == '__main__':
    lport = 33553
    dport = 33773
    client = ds.SocketConnectionUDP(lport, ("127.0.0.1", dport))

    client.start()
    client.block_until_verify()

    print("""Imagine a shell
cd [dir name] - as expected
ls - as expected
dl [src name] - Download file""")

    while client.alive and client.verified_connection:
        command = input("> ")

        parts = command.split()
        if '"' in command:  # If there are quotes we assume that the spaces are all part of the same value
            command_packet = ds.Packet(parts[0], " ".join(parts[1:])[1:-1]).generate()
        else:
            command_packet = ds.Packet(*parts).generate()
        client.in_queue.put(command_packet)

        response_raw = client.block_until_message(5)
        response = ds.Packet().parse(response_raw)

        if response.type == "ls":
            print("Dirs:", response.value)
            print("Files:", response.data)
        elif response.type == "cd":
            print(response.value)
        elif response.type == "text":
            print(response.value)
        elif response.type == "file":
            local_name = input("Save as name> ")
            with open(local_name, "wb") as f:
                f.write(response.value)
            print("file received")
