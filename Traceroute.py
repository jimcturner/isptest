#!/usr/bin/env python

from scapy.all import *
from scapy.layers.inet import IP, UDP
def traceroute():
    hostname = "google.com"
    for i in range(1, 28):
        pkt = IP(dst=hostname, ttl=i) / UDP(dport=33434)
        # Send the packet and get a reply
        reply = sr1(pkt, verbose=0)
        if reply is None:
            # No reply =(
            break
        elif reply.type == 3:
            # We've reached our destination
            print ("Done! "+ str(reply.src))

            break
        else:
            # We're in the middle somewhere
            print (str(i) + " hops away: " + str(reply.src))

