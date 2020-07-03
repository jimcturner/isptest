import socket
import time
txSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP
counter = 0
while True:

    message = str(counter).encode('ascii')
    print(message)
    txSocket.sendto(message, ("192.168.3.27",5000))
    counter += 1
    time.sleep(1)