import antt.servers as s


echo = s.LocateServer()
echo.start()
print(echo.info_port)
input()
echo.alive = False
input()

