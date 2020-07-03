

def rawReceive():
    import select
    import socket
    from Utils import IPHeader, UDPHeader
    UDP_RX_PORT = 5000
    UDP_RX_IP = "127.0.0.1"
    # create UDP socket
    udpSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP

    # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
    # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
    rawSocket.setblocking(0)

    udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    print ("udpSocket :" +str(udpSocket))
    print("rawSocket :" + str(rawSocket))
    while True:
        data, addr = udpSocket.recvfrom(131072)
        print(str(udpSocket.type) + ", " + str(data))
        try:
            rawData, rawAddr = rawSocket.recvfrom(131072)
            # print("raw " + str(rawData))
            # # extract IP Header
            ipHeader = IPHeader(rawData[:20])
            udpHeader = UDPHeader(rawData[20:28])

            print (str(ipHeader.d_addr) + ":" + str(udpHeader.destPort) + ", ttl: " + str(ipHeader.ttl))
        except Exception as e:
            print (str(e))

        # r, w, x = select.select([rawSocket], [], [])
        # for i in r:
        #     receiveSocket = i
        #     data, addr = receiveSocket.recvfrom(131072)
        #     print(str(receiveSocket.type) + ", " + str(data))
        # rawData, rawAddr = rawSocket.recvfrom(131072)
        # print("raw " + str(rawData))

            # # extract IP Header
            # ipHeader = Utils.IPHeader(data[:20])
            # udpHeader = Utils.UDPHeader(data[20:28])
            # icmpMessage = Utils.ICMPHeader(data[20:28])
            # message = data[28:]
            # # print(str(i) + ", " + str(i.recvfrom(131072)))
            # print(str(ipHeader.d_addr) + ":" + ", " + str(ipHeader.protocol) + ", type:" + str(icmpMessage.type) +\
            #       ", code:" + str(icmpMessage.code))


# Main prog starts here
# #####################
# x =0
# while True:
#     time.sleep(0.00006670440)
#     x+=1
#     if x % 1000000:
#         print ("x=0")

rawReceive()