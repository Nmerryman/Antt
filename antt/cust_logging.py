

DEBUG = True
# Options all(default), verification, mainloop, start_conn, DS socket loop
TOPICS = {"all", "start_conn",}


def log(*text):
    if DEBUG:
        print("D:", *text)


def log_txt(text, topic="all", out_file="log.txt", ending="\n"):
    if DEBUG and topic in TOPICS:
        with open(out_file, "a") as f:
            f.write(text + ending)