#!/usr/bin/env python
############## Start of attempt 1
import array
import socket
import struct


# Creates a returns a customised UDP packet
def createCustomUdpPacket(srcAddr, destAddr, id_field, TTL, srcPort, dstPort, payload):
    # Creates an IP header - specifying the source/dest address, ID field, TTL and protocol carried within
    def createIPHeader(srcAddr, destAddr, ID, TTL, protocol):
        version = 4
        ihl = 5
        DF = 0
        Tlen = 0  # OSX *WILL* validate this field so it has to be calculated (OSX won't do it). Additionally,
        # unlike all the other header fields which should be written in 'network (= big-endian)) byte order
        # (basically, by prepending the struct/pack() format string with '!') this should be packed in
        # 'native byte order' (that is, that of the OS, which for OSX seems to be little-endian)
        # Will will preset this to a known value and verify it against the copy of the IP header
        # returned in the ICMP message payload
        Flag = 0
        Fragment = 0
        ip_checksum = 0  # It seems like the OSX calculates this automatically (if set to zero, according to Wireshark, anyway)

        SIP = socket.inet_aton(srcAddr)
        DIP = socket.inet_aton(destAddr)
        ver_ihl = (version << 4) + ihl
        f_f = (Flag << 13) + Fragment
        ip_hdr = struct.pack("!BBHHHBBH4s4s", ver_ihl, DF, Tlen, ID, f_f, TTL, protocol, ip_checksum, SIP, DIP)
        return ip_hdr

    # Creates a complete UDP Datagram complete with UDP header (and calculated checksum)
    def createUdpDatagram(srcAddr, destAddr, srcPort, dstPort, payload):
        # Checksum calculation fn pinched from here:
        # https://medium.com/@NickKaramoff/tcp-packets-from-scratch-in-python-3a63f0cd59fe
        # https://gist.github.com/NickKaramoff/b06520e3cb458ac7264cab1c51fa33d6
        # I'm not entirely sure how this works, but it does the folllowing:-
        # The RFC tells us the following:
        # The checksum field is the 16 bit one’s complement of the one’s complement sum
        # of all 16 bit words in the header and text.
        # This method makes use of Python’s built-in array module, that creates an array with fixed element types.
        # This lets us calculate the sum of 16-bit words more easily than using a loop.
        # Then the function simply applies some bit arithmetic magic to the sum and returns it.
        def chksum(packet: bytes) -> int:
            # Check for an even length. If odd, pad with an additional binary 0 (this will make no difference to the sum)
            if len(packet) % 2 != 0:
                packet += b'\0'

            # Convert each pair of bytes into an array element and sum the contents of that array
            res = sum(array.array("H", packet))
            # Expand the sum (res) to 32 bits (bytes) by masking with 0xFFFF
            # Also, add the top 16 bits to the bottom 16 bits
            res = (res >> 16) + (res & 0xffff)
            # Add the top 16 bits to the bottom 16 bits once more
            res += res >> 16
            return (~res) & 0xffff

        UDP_HEADER_LENGTH = 8
        length = UDP_HEADER_LENGTH + len(payload)
        # Initially set the UDP checksum value to zero (will be overwritten by the calculated checksum value)
        checksum = 0  #
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
        # print("udp_checksum: " + str(hex(udp_checksum)))
        # Now insert the newly calculated checksum back into the udp header *in native byte order* (so no '!' in struct.pack)
        udp_hdr = udp_hdr[:6] + struct.pack('H', udp_checksum) + udp_hdr[8:]
        return udp_hdr

    # Create a custom UDP Datagram (IP length field will be filled in later, IP checksum to be calculated by the OS)
    pkt = createIPHeader(srcAddr, destAddr, id_field, TTL, socket.IPPROTO_UDP) + \
          createUdpDatagram(srcAddr, destAddr, srcPort, dstPort, payload)
    # overwrite total length field of IP header in 'host or 'native' byte order' otherwise sendto() will complain
    # under OSX with an unhelpful 'invalid argument' error
    # It seems (on OSX at least) that this field is the only value that's validated by the OS
    # All other fields seem to be able to be spoofed.
    # See http://cseweb.ucsd.edu/~braghava/notes/freebsd-sockets.txt and
    # https://stackoverflow.com/questions/32575558/creating-raw-packets-with-go-1-5-on-macosx
    # Calculate total length of packet
    totalLength = len(pkt)
    # Re-insert packet length into IP header (in native byte order, so no ! in struct.pack)
    pkt = pkt[:2] + struct.pack("H", totalLength) + pkt[4:]
    return pkt

# Create a layer 3 socket  - we will interface at IP level (socket.IPPROTO_RAW)
s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)

# Set socket.IP_HDRINCL = 1. This means we must supply the IP header ourselves (although the OS will calculate the checksum)
s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
srcAddr = "192.168.0.2"
srcPort = 1000
destAddr = "8.8.8.8"
dstPort = 5000
payload = b'Hello'
id_field =15151
TTL = 25

# # Create a custom UDP Datagram (IP length field will be filled in later, IP checksum to be calculated by the OS)
# pkt = createIPHeader(srcAddr, destAddr, id_field, TTL, socket.IPPROTO_UDP) + \
#       createUdpDatagram(srcAddr, destAddr, srcPort, dstPort, payload)
# # overwrite total length field of IP header in 'host or 'native' byte order' otherwise sendto() will complain
# # under OSX with an unhelpful 'invalid argument' error
# # It seems (on OSX at least) that this field is the only value that's validated by the OS
# # All other fields seem to be able to be spoofed.
# # See http://cseweb.ucsd.edu/~braghava/notes/freebsd-sockets.txt and
# # https://stackoverflow.com/questions/32575558/creating-raw-packets-with-go-1-5-on-macosx
# # Calculate total length of packet
# totalLength = len(pkt)
# # Re-insert packet length into IP header (in native byte order, so no ! in struct.pack)
# pkt = pkt[:2] + struct.pack("H", totalLength) + pkt[4:]

udpPacket = createCustomUdpPacket(srcAddr, destAddr, id_field, TTL, srcPort, dstPort, payload)
s.sendto(udpPacket, (destAddr,0))



