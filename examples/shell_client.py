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
        command_packet = ds.Packet(*command.split()).generate()
        if command == "db":
            code.interact(local=locals())
        elif command == "dp":
            pprint(client.__dict__)
            continue
        client.in_queue.put(command_packet)


        try:
            response_raw = client.block_until_message(3)
            response = ds.Packet().parse(response_raw)
        except:
            option = input("EXCEPTION: c-continue, i-interactive")
            if option == "c":
                pass
            elif option == "i":
                code.interact(local=locals())

        # if command.split()[0] == "dl":
        #     code.interact(local=locals())
        #     input(">>>><<<<>>>>")  # incase this matters

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
