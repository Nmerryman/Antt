

DEBUG = True
# Options all(default), verification, mainloop, start_conn, DS socket loop, tcp socket setup
TOPICS = {"all"}


def log(*text):
    if DEBUG:
        print("D:", *text)


def log_txt(text, topic="all", out_file=r"D:\dump\Git\Antt\log.txt", ending="\n"):
    if DEBUG and topic in TOPICS:
        with open(out_file, "a") as f:
            f.write(text + ending)
