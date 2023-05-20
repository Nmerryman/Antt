import antt.data_structures as ds
import os
import time

if __name__ == '__main__':
    try:
        os.remove("log.txt")
    except FileNotFoundError:
        pass
    lport = 33773
    dport = 33553
    server = ds.SocketConnectionUDP(lport, ("127.0.0.1", dport))

    server.start()
    # Because this is udp based, we can keep reconnecting and don't need initial verification as were listening but it should be fine
    server.block_until_verify()

    while server.alive and server.verified_connection:
        if not server.out_queue.empty():
            message_raw = server.block_until_message()  # We could manually take it out of the queue an task_done() it
            message = ds.Packet().parse(message_raw)

            if message.type == "ls":
                dir_obs = os.listdir()
                dirs = []
                files = []
                for a in dir_obs:
                    if os.path.isfile(a):
                        files.append(a)
                    else:
                        dirs.append(a)
                server.in_queue.put(ds.Packet("ls", dirs, files).generate())
            elif message.type == "cd":
                prev = os.path.basename(os.getcwd())
                os.chdir(message.value)
                server.in_queue.put(ds.Packet("cd", f"{prev}->{message.value}").generate())
            elif message.type == "dl":
                try:
                    with open(message.value, 'rb') as f:
                        data = f.read()
                        server.in_queue.put(ds.Packet("file", data).generate())
                        print("file sent")
                except FileNotFoundError:
                    server.in_queue.put(ds.Packet("text", f"File '{message.value}' was not found").generate())

        else:
            # So we don't just spin away at max speed
            time.sleep(.1)
            if os.path.exists("df"):
                import code
                from pprint import pprint
                code.interact(local=locals())

