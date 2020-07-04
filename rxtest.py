import struct
import socket
# Decodes the supplied IP header (which should be 20 bytes long)
import sys


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

def rawReceiveLinux():
    import select

    UDP_RX_PORT = 5000
    UDP_RX_IP = "127.0.0.1"
    # create UDP socket
    udpSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP
    udpSocket.settimeout(1)
    # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
    # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)    # Works on Linux
    # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
    # rawSocket.settimeout(1)
    rawSocket.setblocking(0)

    udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    print ("udpSocket :" +str(udpSocket))
    print("rawSocket :" + str(rawSocket))
    while True:
        try:
            r, w, x = select.select([udpSocket, rawSocket], [], [])
            for rxSock in r:
                data, addr = rxSock.recvfrom(131072)
                if rxSock == udpSocket:
                    print(str(rxSock.type) + ", " + str(data))
                else:
                    # extract IP Header
                    ipHeader = IPHeader(data[:20])
                    udpHeader = UDPHeader(data[20:28])
                    print (str(ipHeader.d_addr) + ":" + str(udpHeader.destPort) + ", ttl: " + str(ipHeader.ttl) + " " + \
                           str([data[28:]]))
        except Exception as e:
            print (str(e))
            pass

def rawReceiveWindows(argv):
    import select
    import os


    UDP_RX_IP = argv[0] # "127.0.0.1"
    UDP_RX_PORT = argv[1]  # 5000

    # create UDP socket
    udpSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP
    udpSocket.settimeout(1)
    # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
    rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
    # rawSocket.settimeout(1)
    # rawSocket.setblocking(0)

    udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    rawSocket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    # Enable promiscuous mode
    rawSocket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)

    print("udpSocket :" + str(udpSocket))
    print("rawSocket :" + str(rawSocket))
    while True:
        try:
            r, w, x = select.select([udpSocket, rawSocket], [], [])
            for rxSock in r:
                data, addr = rxSock.recvfrom(131072)
                if rxSock == udpSocket:
                    print(str(rxSock.type) + ", " + str(data))
                else:
                    # extract IP Header
                    ipHeader = IPHeader(data[:20])
                    udpHeader = UDPHeader(data[20:28])
                    print (str(rxSock.type) + ", " + str(ipHeader.d_addr) + ":" + str(udpHeader.destPort) + ", ttl: " + str(ipHeader.ttl) + " " + \
                           str([data[28:]]))
        except Exception as e:
            print (str(e))
            pass





# Main prog starts here
# #####################


# rawReceiveLinux()

if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    rawReceiveWindows(sys.argv[1:])