#!/usr/bin/env python

# from scapy.all import *
# from scapy.layers.inet import IP, UDP

import socket
def traceroute():
    pass
    # hostname = "google.com"
    # for i in range(1, 28):
    #     # print("sending with TTL " + str(i))
    #     pkt = IP(dst=hostname, ttl=i) / UDP(dport=33434)
    #     # Send the packet and get a reply
    #     reply = sr1(pkt, verbose=0, timeout=1)
    #     if reply is None:
    #         print(str(i) + " *")
    #         # break
    #     elif reply.type == 3:
    #         # We've reached our destination
    #         resolvedName = ""
    #         try:
    #             resolvedName = str(socket.gethostbyaddr(str(reply.src)))
    #         except:
    #             resolvedName =""
    #         print (str(i) + " "+ "Done! "+ str(reply.src)+ ",  " + resolvedName)
    #         break
    #     else:
    #         # We're in the middle somewhere
    #         resolvedName = ""
    #         try:
    #             resolvedName = str(socket.gethostbyaddr(str(reply.src)))
    #         except:
    #             resolvedName =""
    #
    #         print (str(i) + " "+ str(reply.src) + ",  " + resolvedName)

