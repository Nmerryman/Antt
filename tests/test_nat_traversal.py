import antt.nat_traversal as nt

serv = nt.DetectionServer(4454)
print(serv.root_port)
serv.launch()

