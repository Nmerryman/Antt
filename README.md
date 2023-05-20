# Antt
A custom nat traversal tool
The goal is to provide an easy way for p2p communications by wrapping the python socket class in a custom class that handles connections and all the busy work. Currently only the primative connection classes are working, Nat traversal is still WIP.
The TCP version is recomended, but some nat traversal requires udp to act predictably. Both versions act in similar ways and have similar apis. There is also a provided `Packet` class to help encapsulate data.

# Testing the Examples
## Environment
A `requirements.txt` file is provided, but the only library needed is psutil
## Running chat clients
Simply run `chat_client_a.py` and `chat_client_b.py` at the same time (the timing is a bit tight).
## Running Shell Client
Simply start `shell_server.py` and `shell_client.py` at the same time.
All usable commands will be printed in the terminal on what it can do.

## Notes
Because the connections are meant to be used in a p2p context, the connection timeout is relatively low. This can always be adressed later by tweaking some numbers.

The usage of `SocketConnectionUDP` and `SocketConnectionTCP` is interchangable in both examples. The only difference is that `TCP` needs `acts_as` to be defined as either `client` or `server` so it can negotiate it's initial setup.
