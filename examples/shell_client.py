import time
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

        # show progress if transfer takes more than 5s
        start_wait = time.time()
        last_len = 0
        while client.out_queue.empty():
            time.sleep(.5)
            if time.time() - start_wait > 5 and client.last_updated:
                temp_data = client.get_message_status(client.last_updated)
                if len(temp_data[0]) != last_len:
                    print(len(temp_data[0]) - 1, temp_data[1])
                    last_len = len(temp_data[0])
        client.last_updated = None

        # Extract message from out_queue
        response_raw = client.block_until_message()
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
