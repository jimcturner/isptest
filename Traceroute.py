#!/usr/bin/env python

from scapy.all import *
from scapy.layers.inet import IP, UDP
def traceroute():
    pass
    hostname = "google.com"
    for i in range(1, 28):
        # print("sending with TTL " + str(i))
        pkt = IP(dst=hostname, ttl=i) / UDP(dport=33434)
        # Send the packet and get a reply
        reply = sr1(pkt, verbose=0, timeout=5, iface="en16")
        if reply is None:
            print(str(i) + " *")
            # break
        elif reply.type == 3:
            # We've reached our destination
            print ("Done! "+ str(reply.src))

            break
        else:
            # We're in the middle somewhere
            print (str(i) + " "+ str(reply.src))

