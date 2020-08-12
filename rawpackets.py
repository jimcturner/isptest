#!/usr/bin/env python
############## Start of attempt 1
import array
import socket
import struct

# Checksum calculation fn pinched from here:
# https://medium.com/@NickKaramoff/tcp-packets-from-scratch-in-python-3a63f0cd59fe
# https://gist.github.com/NickKaramoff/b06520e3cb458ac7264cab1c51fa33d6
# I'm not entirely sure how this works, but it does the folllowing:-
# The RFC tells us the following:
# The checksum field is the 16 bit one’s complement of the one’s complement sum
# of all 16 bit words in the header and text.
# This method makes use of Python’s built-in array module, that creates an array with fixed element types.
# This lets us calculate the sum of 16-bit words more easily than using a loop.
# Then the function simply applies some bit arithmetics magic to the sum and returns it.
def chksum(packet: bytes) -> int:
    if len(packet) % 2 != 0:
        packet += b'\0'

    res = sum(array.array("H", packet))
    res = (res >> 16) + (res & 0xffff)
    res += res >> 16

    return (~res) & 0xffff
# Creates an IP header
def IP(srcAddr, destAddr):
    version = 4
    ihl = 5
    DF = 0
    Tlen = 0 # OSX *WILL* validate this field so it has to be calculated (OSX won't do it). Additionally,
            # unlike all the other header fields which should be written in 'network (= big-endian)) byte order
            # (basically, by prepending the struct/pack() format string with '!') this should be packed in
            # 'native byte order' (that is, that of the OS, which for OSX seems to be little-endian)
    ID = 54321
    Flag = 0
    Fragment = 0
    TTL = 59
    Proto = socket.IPPROTO_UDP
    ip_checksum = 0     # It seems like the OSX calculates this automatically (if set to zero, according to Wireshark, anyway)
                        # However, we *will* need to calculate it ourselves anyway, because we'll use it to verify that
                        # the IP header contained in the payload of the ICMP error message contains the same checksum value
    SIP = socket.inet_aton(srcAddr)
    DIP = socket.inet_aton(destAddr)
    ver_ihl = (version << 4) + ihl
    f_f = (Flag << 13) + Fragment
    ip_hdr =  struct.pack("!BBHHHBBH4s4s", ver_ihl,DF,Tlen,ID,f_f,TTL,Proto,ip_checksum,SIP,DIP)
    return ip_hdr

# Creates a complete UDP Datagram complete with header (anc calculated checksum)
def UDP(srcAddr, destAddr, srcPort, dstPort, payload):
    UDP_HEADER_LENGTH = 8
    length = UDP_HEADER_LENGTH + len(payload)
    # Initially set the UDP checksum value to zero (will be overwritten by the calculated checksum value)
    checksum = 0    #
    # UDP checksum is calculated by summing the source addr, dest addr, protocol ID (17, for UDP) and UDP packet length
    # known as the 'pseudo header'. Create the pseudo header first
    # and then adding that to the sum of the UDP header, before inverting all the bits (1's complimenting)
    udp_hdr = struct.pack("!HHHH", srcPort, dstPort, length, checksum) + payload
    pseudo_hdr = struct.pack(
        '!4s4sHH',
        socket.inet_aton(srcAddr),  # Source Address
        socket.inet_aton(destAddr),  # Destination Address
        socket.IPPROTO_UDP,  # PTCL
        length  # UDP Length
    )
    # Calculate the checksum
    udp_checksum = chksum(pseudo_hdr + udp_hdr)
    # Now insert the newly calculated checksum back into the udp header *in native byte order* (so no '!' in struct.pack)
    udp_hdr = udp_hdr[:6] + struct.pack('H', udp_checksum) + udp_hdr[8:]
    return udp_hdr

s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)

# the error occurs only when the IP_HDRINCL is enabled
s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
srcAddr = "192.168.0.2"
srcPort = 20
destAddr = "8.8.8.8"
dstPort = 2000
payload = b'Hello'

pkt = IP(srcAddr, destAddr) + UDP(srcAddr, destAddr, srcPort, dstPort, payload)
# overwrite total length field of IP header in 'host or 'native' byte order' otherwise sendto() will complain
# under OSX with an unhelpful 'invalid argument' error
# It seems (on OSX at least) that this field is the only value that's validated by the OS
# All other fields seem to be able to be spoofed.
# See http://cseweb.ucsd.edu/~braghava/notes/freebsd-sockets.txt and
# https://stackoverflow.com/questions/32575558/creating-raw-packets-with-go-1-5-on-macosx
totalLength = len(pkt)
pkt = pkt[:2] + struct.pack("H", totalLength) + pkt[4:]
s.sendto(pkt, (destAddr,0))
######## End of attempt 1


