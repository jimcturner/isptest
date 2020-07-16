import random
import socket
import string
import sys
import time


def generatePayload(payloadLength):
    # Generate random byte string of length 'length' to create a payload of length self.payloadLength

    # Create byte string containing all uppercase and lowercase letters
    letters = string.ascii_letters
    # iterate over stringLength picking random letters from 'letters'
    randomDataString = ''.join(random.choice(letters) for i in range(payloadLength))

    # Return as a bytestring
    return randomDataString.encode('ascii')

def sendUDP(argv):
    print("sending to " + str(argv[0]) + ":" + str(argv[1]))
    txSocket = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
    randomText = generatePayload(20)
    counter = 0
    noOfRepeats = 3
    while True:
        if counter % noOfRepeats == 0:
            randomText = generatePayload(20)
        message = str(counter).encode('ascii') + randomText + b'_sendUDP: '
        print(message)
        txSocket.sendto(message, (argv[0],int(argv[1])))
        counter += 1
        if counter == 1000:
            counter = 0
        time.sleep(0.01)

if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    sendUDP(sys.argv[1:])
