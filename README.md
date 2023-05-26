# Antt
## Another Nat Traversal Tool
The goal is to provide an easy way for p2p communications by wrapping the python socket class in a custom class that handles connections and all the busy work. At this moment, the socket wrapping classes work, but the nat traversal is still very much a WIP.

Currently, only the primitive socket connection classes exist. These classes are designed to allow easy communications between clients through putting the socket in a different thread and providing an easy api to send and recieve messages through. The socket thread takes care of any miscellaneous things that are needed for proper nat traversal connections.

There are two versions of the clients with identical apis, the only difference is whether it uses TCP or UDP in the socket thread. Ideally only TCP would be used, but many nats refuse to play nicely with TCP hole punching. Due to this, much of the functionality built into the TCP socket had to be rebuilt with UDP.
The TCP version is recommended due to it's guarenteed reliability, but UDP should provide nearly as reliable as well.

### Date structures
The easiest class to use is the `Packet` class. It simply provides a simple way to encapsulate data and turn it into a byte string or parse said string to recreate the original `Packet`. This makes it easy to generate the byte string to pass to the socket and rebuilt the original data on the other side.
Obviously the client and server are always run as diferent programs, they are just put together for simplicity.
```python
import antt.data_structures as ds

# Client sends
in_data = ds.Packet(1, "text", b"bytes")  # Any data type compatible with json + byte strings can be passed
client.in_queue.put(in_data.generate())  # Putting the full byte string into an example socket server

# Server recieves
out_data_raw = server.out_queue.get()  # Server pulls out raw byte string after it's sent
out_data = ds.Packet().parse(out_data_raw)

assert out_data == in_data  # These will produce the same values
```

Both `SocketConnectionUDP` and `SocketConnectionTCP` have nearly the same api. Only the init is different.
```python
import antt.data_structures as ds

# Client side
client_socket = ds.SocketConnectionUDP(src_port=3345, target=("127.0.0.1", 4456))  # Assuming we have access to the target
client_socket.start()  # Start the thread
client_socket.block_until_verify()  # This will wait until both sides do handshakes and are ready to send/recieve data
client_socket.in_queue.put(b"example text")  # This will automatically get consumed as the thread gets ready to send data

# Server side
server_socket = ds.SocketConnectionUDP(src_port=4456, target=("127.0.0.1", 3345))
server_socket.start()
server_socket.block_until_verify()
data = server_socket.block_until_message()  # This is a helper to avoid continuously checking server_socket.out_queue.empty() for a recieved message
assert data == b"example text"
```

The only difference between the init for the TCP version is that it looks as follows.
```python
import antt.data_structures as ds
# Client
client_socket = ds.SocketConnectionTCP(src_port=3345, target=("127.0.0.1", 4456), acts_as="client")
# Server
server_socket = ds.SocketConnectionTCP(src_port=4456, target=("127.0.0.1", 3345), acts_as="server")
```
It does not matter which socket thread uses which value, all that maters is that `acts_as` is different so that the sockets can properly connect to each other during their initial connection. 

# Testing the Examples
## Environment
A `requirements.txt` file is provided, but the only library needed is psutil.
I always add `$Env:PYTHONPATH = "absolute path to root dir"` to my venv activation script. That way all files can find each other in my project structure. That way I can run `python examples/chat_client_a.py` from my root directory
## Running chat clients
Simply run `chat_client_a.py` and `chat_client_b.py` at the same time (the timing is a bit tight).
## Running Shell Client
Simply start `shell_server.py` and `shell_client.py` at the same time.
All usable commands will be printed in the terminal on what it can do.

## Notes
Because the connections are meant to be used in a p2p context, the connection timeout is relatively low. This can always be addressed later by tweaking some numbers. We also assume that the connections will always be p2p and as such currently UDP does no verification of the origins of any packets. We have assumed that the hole punched nat hase taken care of ensuring that the origin of all packets is correct.

`SocketConnectionUDP` should be good enough to use interchangably with `SocketConnectionTCP`, but there are currently a few additional known limitations. 
- No packet source verification.
- Receiving a duplicated/delayed partial packet after marking message as complete will trigger the `missing frames` protocol to request missing pieces again.
- Every 40th frame gets dropped so messages won't finish sending until a latency timeout triggers the `missing frames` protocol for the message.
- Due to the nature of UDP, there are many more functions that can be used to help debug issues but don't need to be used in general.

## Benchmarks
These are just some very rough values:
### UDP
From load file to saved file, locally transferring a 760MB file took 5m50s or had a throughput of about 2MBps.
Same as before but when done over a local network, a 80MB file took 1m30s and had a throughput of about 0.89MBps.
There seemed to be slowdowns due to lost frames and delays when requesting the next set (maybe timeout_latency, some memory, or os socket thing).
Sending frames seems to slow to a crawl when file is about 600k frames large (around the 300MB original file size).
### TCP
From load file to saved file, locally transferring a 760MB file took 1m09s or had a throughput of about 11MBps.
Same as before but when done over a local network, a 80MB file took 5m55s and had a throughput of about 0.23MBps.
Compared to UDP, TCP speed seems much more stable. This is likely due to a bug causing UDP to become slow over time, but may be worth the tradeoff if the dl time becomes too long.

# TODO
- Comprehensive tests that check for more paths/cases
- Cleaning up the code base
  - Standardizing naming, style
  - Ordering chunks in more reasonable ways
  - Documentation/code hints/comments
- Fix general bugs or undesirable behavior
- optimize/streamline internals
- Use the data structures to work on nat traversal
