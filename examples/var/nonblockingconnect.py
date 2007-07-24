from socket import socket
from time import sleep
from select import select

s = socket()
s.setblocking(0)
print s.connect_ex(('www.cq2.nl', 8990))
print select([s], [s], [s])
print s.send('GET / HTTP/1.1\r\nHost: www.cq2.nl\r\n\r\n')
print select([s], [s], [s])
print s.recv(999)