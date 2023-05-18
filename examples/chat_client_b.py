import examples.chat_client_base as ccb

if __name__ == '__main__':
    lport = 33377
    dport = 33355
    ccb.start_client(lport, ("127.0.0.1", dport), "server")
