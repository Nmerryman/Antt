import examples.chat_client_base as ccb

if __name__ == '__main__':
    lport = 33355
    dport = 33377
    ccb.start_client(lport, ("127.0.0.1", dport), "client")
