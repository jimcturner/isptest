#!/usr/bin/env python
############## Start of attempt 1
import socket
import struct
# Creates an IP header
def IP():
    version = 4
    ihl = 5
    DF = 0
    Tlen = 0
    ID = 54321
    Flag = 0
    Fragment = 0
    TTL = 59
    Proto = socket.IPPROTO_UDP
    ip_checksum = 0
    SIP = socket.inet_aton("192.168.0.2")
    DIP = socket.inet_aton("8.8.8.8")
    ver_ihl = (version << 4) + ihl
    f_f = (Flag << 13) + Fragment
    ip_hdr =  struct.pack("!BBHHHBBH4s4s", ver_ihl,DF,Tlen,ID,f_f,TTL,Proto,ip_checksum,SIP,DIP)
    return ip_hdr

def UDP(payload):
    sourcePort = 20  # **** OS WON'T FILL THIS IN - need to
    destPort = 2000
    length = 13      # **** OS WON'T FILL THIS IN - need to calculate it
    checksum = 0    # Hoping the OS will fill this in
    udp_hdr = struct.pack("!HHHH", sourcePort, destPort, length, checksum)
    return udp_hdr

s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)

# the error occurs only when the IP_HDRINCL is enabled
s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
dip = "8.8.8.8"
pkt = IP() + UDP() + b'Hello'
# overwrite total length field of IP header in 'host byte order' otherwise sendto() will complain
# See http://cseweb.ucsd.edu/~braghava/notes/freebsd-sockets.txt and
# https://stackoverflow.com/questions/32575558/creating-raw-packets-with-go-1-5-on-macosx
totalLength = len(pkt)
pkt = pkt[:2] + struct.pack("H", totalLength) + pkt[4:]
s.sendto(pkt, (dip,0))
######## End of attempt 1


