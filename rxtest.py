import struct
import socket
# Decodes the supplied IP header (which should be 20 bytes long)
class IPHeader(object):
    # Custom Exception to be raised if the supplied IP header data can't be unpacked
    class DecodeException(Exception):
        pass

    def __init__(self, ip_header):
        # unpack header
        try:
            iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
            # First byte pf header contains version (bits 4-7) and i[ header length (bits 0-3)
            version_ihl = iph[0]
            self.version = version_ihl >> 4
            self.ipHeaderLength = version_ihl & 0xF
            self.ttl = iph[5]
            self.protocol = iph[6]
            self.s_addr = socket.inet_ntoa(iph[8])
            self.d_addr = socket.inet_ntoa(iph[9])
            # print('Version : ' + str(
            #     self.version) + ' IP Header Length : ' + str(
            #     self.ipHeaderLength) + ' TTL : ' + str(
            #     self.ttl) + ' Protocol : ' + str(
            #     self.protocol) + ' Source Address : ' + str(
            #     self.s_addr) + ' Destination Address : ' + str(self.d_addr))
        except Exception as e:
            raise IPHeader.DecodeException(str(e))

# Decodes the supplied UDP header (which should be 8 bytes long)
class UDPHeader(object):
    # Custom Exception to be raised if the supplied header data can't be unpacked
    class DecodeException(Exception):
        pass
    def __init__(self, udp_header):
        # unpack header
        try:
            self.udpHeader = struct.unpack("!HHHH", udp_header)
            self.sourcePort = self.udpHeader[0]
            self.destPort = self.udpHeader[1]
            self.dataLength = self.udpHeader[2]
            self.checksum = self.udpHeader[3]

        except Exception as e:
            raise UDPHeader.DecodeException(str(e))

def rawReceive():
    import select

    UDP_RX_PORT = 5000
    UDP_RX_IP = "127.0.0.1"
    # create UDP socket
    udpSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP

    # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
    # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
    # rawSocket.setblocking(0)

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

            print (str(ipHeader.d_addr) + ":" + str(udpHeader.destPort) + ", ttl: " + str(ipHeader.ttl) + " " + \
                   str([rawData[28:]]))
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


rawReceive()