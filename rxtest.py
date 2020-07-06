import platform
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

# Attempts to determine what flavour of operating system is running
# Should return 'Windows' for Windows, or
def getOperatingSystem():
    current_os = platform.system()
    return current_os

# Custom Exceptions
class CreateRawSocketError(Exception):
    pass
class RawSocketNotPossibleForOSXError(Exception):
    pass

def rawReceive(argv):
    # Creates a UDP socket and binding
    def createUDPSocket(UDP_RX_IP, UDP_RX_PORT, timeout=1):
        # Custom Exception
        class CreateUDPSocketError(Exception):
            pass
        try:
            # create UDP socket
            udpSocket = socket.socket(socket.AF_INET,  # Internet
                                      socket.SOCK_DGRAM)  # UDP
            udpSocket.settimeout(1)
            udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))
            return udpSocket
        except Exception as e:
            raise CreateUDPSocketError(str(e))

    # Creates a raw socket and initialises it to suit the running OS
    def createRawSocket(UDP_RX_IP, UDP_RX_PORT):

        try:
            # Create Raw socket
            # The socket initialisation for Windows and Linux is different
            # OSX won't permit Raw sockets to receive UDP or TCP data at all
            # The aim of this function is to create a raw socket in parallel with the udp socket
            # For Linux and Windows

            # Determine what OS is running
            current_os = platform.system()
            if current_os == 'Windows':
                # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
                rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
                rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
                rawSocket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                # Enable promiscuous mode
                rawSocket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
                return rawSocket
            elif current_os == 'Linux':
                rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)  # Works on Linux
                rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
                return rawSocket

            elif current_os == 'Darwin':
                # The raw socket we want isn't possible for OSX, raise an Exception
                raise RawSocketNotPossibleForOSXError("Not supported on OSX (Darwin)")

        except RawSocketNotPossibleForOSXError as e:
            # Pass the Exception outwards
            raise RawSocketNotPossibleForOSXError(str(e))

        except Exception as e:
            # Socket creation failed. Raise an Exception
            # print ("createRawSocket() " + str(e))
            raise CreateRawSocketError(str(e))


    UDP_RX_IP = argv[0]  # "127.0.0.1"
    UDP_RX_PORT = int(argv[1])  # 5000

    # Attempt to create sockets
    try:
        udpSocket = createUDPSocket(UDP_RX_IP, UDP_RX_PORT)
        rawSocket = createRawSocket(UDP_RX_IP, UDP_RX_PORT)
        print("udpSocket :" + str(udpSocket))
        print("rawSocket :" + str(rawSocket))


    except Exception as e:
        print ("socket creation failed " + str(type(e)) + ", " + str(e))
        exit()

def rawReceiveLinux(argv):
    import select

    UDP_RX_IP = argv[0]  # "127.0.0.1"
    UDP_RX_PORT = int(argv[1])  # 5000
    # create UDP socket
    udpSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP
    udpSocket.settimeout(1)
    # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
    # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)    # Works on Linux
    # rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
    # rawSocket.settimeout(1)
    # rawSocket.setblocking(0)

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
                    print(str(rxSock.type) + ", " + str(ipHeader.d_addr) + ":" + str(udpHeader.destPort) + ", ttl: " + str(ipHeader.ttl) + " " + \
                           str([data[28:]]))

        except Exception as e:
            print (str(e))
            pass

def rawReceiveWindows(argv):
    import select
    import os

    UDP_RX_IP = argv[0] # "127.0.0.1"
    UDP_RX_PORT = int(argv[1])  # 5000§§

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
                    if udpHeader.destPort == UDP_RX_PORT:
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
    rawReceive(sys.argv[1:])
    #
    # os = getOperatingSystem()
    # print("os: " + os)
    # if  os == "Windows":
    #     rawReceiveWindows(sys.argv[1:])
    # else:
    #     rawReceiveLinux(sys.argv[1:])