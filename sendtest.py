import socket
import sys
import time
def sendUDP(argv):
    print("sending to " + str(argv[0]) + ":" + str(argv[1]))
    txSocket = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
    counter = 0
    while True:

        message = str(counter).encode('ascii') + b' some more random text'
        print(message)
        txSocket.sendto(message, (argv[0],int(argv[1])))
        counter += 1
        time.sleep(1)

if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    sendUDP(sys.argv[1:])
