import antt.servers as s


echo = s.EchoServer()
echo.start()
print(echo.src_port)
input()
echo.alive = False
input()

