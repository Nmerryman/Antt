import antt.servers as s


echo = s.LocateServer(12345)
echo.start()
print(echo.info_port)
input()
echo.alive = False
input()

