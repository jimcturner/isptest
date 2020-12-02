#!/usr/bin/env python
# Defines RtpStream objects for use by isptest
# James Turner 20/2/20
import select
import socket
import os
import binascii
import sys
import struct
import time
import datetime
import threading
import random
import string
import textwrap
import platform
from functools import reduce
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import http.client
from queue import SimpleQueue, Queue, Empty, Full
from timeit import default_timer as timer  # Used to calculate elapsed time
import math
import json
from abc import ABCMeta, abstractmethod  # Used for event abstract class
from copy import deepcopy
import pickle
from collections import deque   # Used for circular buffers
from urllib.parse import parse_qs, urlparse, parse_qsl, urlencode

import requests
from pathvalidate import ValidationError, validate_filename, sanitize_filepath

# Additonal libraries required (of my own making)
from validator_collection import is_integer, is_float

import Utils
from Registry import Registry

try:
    # Try to import the bz2 compresion library. This seems to be missing on some Linuxes
    import bz2
except Exception as e:
    Registry.rtpReceiveStreamCompressResultsBeforeSending = False
    print("WARNING: Can't import bz2 compression library " + str(e))

# # Required for Windows traceroute implemenation - imports moved into traceroute routine itself
# from scapy.layers.inet import IP, UDP
# from scapy.sendrecv import sr1
# from scapy.packet import Raw

class Foo(object):

    def __init__(self):
        print ("Hello from Foo!")

# Define an abstract class for events (should make creating new  types of event more straightforward)
# This class defines a template for event classes (because Python doesn;t support interfaces like Java)
# Note all Python abstract classes inherit from 'ABC'
class Event():
    # define class variables
    timestampOfLastEvent = None
    totalEventCount = 0

    # # NOTE: The following line may/may not be necessary for Python 2.7. Python 3 should use the class declaration
    # # class Event(ABC) but this causes an error in Python 2.7
    # __metaclass__ = ABCMeta
    # @abstractmethod
    def __init__(self, stats):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()

        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1
        # By default, take the name of the class as the 'type'. This could be overwritten
        self.type = self.__class__.__name__
        # Add additional instance variables as required

    # Utility method that returns  a string containing the Event parameters common to all stream events
    # These are:- SyncSourceID, FriendlyName, EventNo, Type etc
    # The contents (or detail) of the return string is dependant upon the bool flags
    # The method is called from an Event subclass as an argument (eg Glitch, StreamStarted, etc)
    # Because all of the subclasses will make use of this method, it makes sense to incorporate it here
    def createCommonSummaryText(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        summary = ""
        try:
            if includeStreamSyncSourceID:
                summary += "[" + str(self.stats["stream_syncSource"]) + "]"
            if includeFriendlyName:
                summary += "[" + str(self.stats["stream_friendly_name"]).rstrip() + "]"
            if includeEventNo:
                summary += "[" + str(self.eventNo) + "] "
            if includeType:
                summary += str(self.type)
        except Exception as e:
            summary += "Event.createCommonSummaryText: " + str(e)
        return summary

    # This method is expected to be overridden by all Event subclasses
    @abstractmethod
    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        # # Returns a dictionary containing a timestamp and a concise description of the event as a string
        # # It invokes the method from the parent class (Event) Event.createCommonSummaryText() to allow
        # # some control over the construction of the string (i.e how much detail it contains) via the optional args
        # # By default, all the optional args are set to True, so the Summary will actually be quite detailed!
        # optionalFields = ""
        # summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
        #                                         includeEventNo=includeEventNo,
        #                                         includeType=includeType,
        #                                         includeFriendlyName=includeFriendlyName)
        # summary += optionalFields
        #
        #
        # data = {'timeCreated': self.timeCreated, 'summary': summary}
        # return data
        pass

    # This is the master method to generate a csv string containing the info common to all events
    def createCommonCSVString(self):
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",syncSource," + str(self.stats["stream_syncSource"]) +\
                ",friendlyName," + str(self.stats["stream_friendly_name"]) + \
              ",timeElapsed," + str(self.stats["stream_time_elapsed_total"]) + \
              ",eventNo," + str(self.eventNo) + ","

        return csv

    # This method is expected to be overridden by all Event subclasses
    @abstractmethod
    def getCSV(self):
        pass

    # Returns a dictionary containing the elements common to all events - to be used in the json export
    def __createCommonJsonDataDictObject(self):
        eventCommonDetailsDict = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats}
        return eventCommonDetailsDict

    # Creates a json object representation of the event.
    # The additionalKeysDict argument allows additional dict keys to be appended to the default keys set up by
    # the call to createCommonJsonDataDictObject
    def createJsonRepresentationOfEvent(self, additionalKeysDict=None):
        # Create initial dictonary of Event data
        jsonData = self.__createCommonJsonDataDictObject()
        if additionalKeysDict is not None:
            # If additional keys are supplied, append them to jsonData
            try:
                jsonData.update(additionalKeysDict)
            except Exception as e:
                # If the data can't be appended, append an error code to the dict
                jsonData.update({"ERROR_createJsonRepresentationOfEvent":str(e)})
        # Create the actual json object
        return json.dumps(jsonData, sort_keys=True, indent=4, default=str)



    # This method is expected to be overridden by all Event subclasses
    @abstractmethod
    def getJSON(self):
        pass

# Now define the 'events' that can happen to a stream
class StreamStarted(Event):

    def __init__(self, stats, firstPacketReceived):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()

        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1
        # By default, take the name of the class as the 'type'. This could be overwritten
        self.type = self.__class__.__name__
        # Additional instance variables
        self.firstPacketReceived = firstPacketReceived

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        # Returns a dictionary containing a timestamp and a concise description of the event as a string
        # It invokes the method from the parent class (Event) Event.createCommonSummaryText() to allow
        # some control over the construction of the string (i.e how mich detail it contains) via the optional args
        # By default, all the optional args are set to True, so the Summary will actually be quite detailed!
        optionalFields = ", first rtp sequence no:"+str(self.firstPacketReceived.rtpSequenceNo)
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo = includeEventNo,
                                                includeType = includeType,
                                                includeFriendlyName = includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "firstRtpSequenceNo,"+str(self.firstPacketReceived.rtpSequenceNo)
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string

        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'rtpSequenceNo': self.firstPacketReceived.rtpSequenceNo}
        # Create the json object
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation


# Define an event that represents a loss of rtpStream
class StreamLost(Event):

    def __init__(self, stats):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1
        # By default, take the name of the class as the 'type'. This could be overwritten
        self.type = self.__class__.__name__


    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        try:
            optionalFields = ", Last packet seen at " +\
                             str(self.stats["packet_last_seen_received_timestamp"].strftime("%d/%m/%Y %H:%M:%S"))
        except:
            optionalFields = ", Invalid packet_last_seen_received_timestamp"

        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        try:
            optionalFields = "Last packet seen at," + \
                             str(self.stats["packet_last_seen_received_timestamp"].strftime("%d/%m/%Y %H:%M:%S"))
        except:
            optionalFields = "Invalid packet_last_seen_received_timestamp"
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv


    def getJSON(self):
        # # Returns a json object representation of the event as a string
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self)
        return jsonRepresentation

# Define an event object that represents a excessive jitter event
class ExcessiveJitter(Event):

    def __init__(self, stats, lastPacketReceived, jitter, threshold):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1
        # By default, take the name of the class as the 'type'. This could be overwritten
        self.type = self.__class__.__name__
        # Add additional instance variables as required
        self.lastPacketReceived = lastPacketReceived
        self.jitter = jitter
        self.threshold = threshold
    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        optionalFields = " "+str(int(self.jitter)) + "/" + str(int(self.threshold)) + "uS"
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)
        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "jitter_uS,"+str(int(self.jitter))+\
            ",threshold_uS,"+str(int(self.threshold))
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Add additional keys as required
        additionalData = {'jitter': self.jitter, 'threshold': self.threshold}
        # Create the json object
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation
# Define an event object that represents a processor overload. This might happen if the calculateThread can't process
# incoming packets fast enough
# class ProcessorOverload(Event):
#     def __init__(self, stats, lastPacketReceived):
#         # Create timestamp of event
#         self.timeCreated = datetime.datetime.now()
#         # Take local copy of stats dictionary
#         self.stats = dict(stats)
#         # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
#         self.eventNo = self.stats["stream_all_events_counter"] + 1
#         # By default, take the name of the class as the 'type'. This could be overwritten
#         self.type = self.__class__.__name__
#         # Add additional instance variables as required
#         self.lastPacketReceived = lastPacketReceived
#
#     def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
#         optionalFields =  " "+str(int(self.stats["stream_processor_utilisation_percent"])) + "% cpu usage. "
#         summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
#                                                 includeEventNo=includeEventNo,
#                                                 includeType=includeType,
#                                                 includeFriendlyName=includeFriendlyName)
#
#         summary += optionalFields
#         data = {'timeCreated': self.timeCreated, 'summary': summary}
#         return data
#
#     def getCSV(self):
#         # returns a CSV formatted string suitable for import into Excel
#         optionalFields = "stream_processor_utilisation_percent,"+ str(self.stats["stream_processor_utilisation_percent"])+\
#             ",lastRtpSequenceNo," + str(self.lastPacketReceived.rtpSequenceNo)
#         csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
#               ",eventNo," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
#               ",friendlyName," +self.stats["stream_friendly_name"]+ "," +optionalFields
#         return csv
#
#     def getJSON(self):
#         # Returns a json object representation of the event as a string
#         # Add additional keys as required
#         data = {'type': self.type, 'timeCreated': self.timeCreated,
#                 'eventNo': self.eventNo,
#                 'syncSource': self.stats["stream_syncSource"], 'stats': self.stats,
#                 'lastRtpSequenceNo': self.lastPacketReceived.rtpSequenceNo}
#         return json.dumps(data, sort_keys=True, indent=4, default=str)

# Define an event that represent a glitch
# This will be in the form of the packets (RtpData objects) either side of the 'hole' in received data
class Glitch(Event):
    # def __init__(self, stats, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap, packetsLost):
    def __init__(self, stats, rtpPackets, packetsLost):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1
        # By default, take the name of the class as the 'type'. This could be overwritten
        self.type = self.__class__.__name__
        # Add additional instance variables as required
        # self.startOfGap = lastReceivedPacketBeforeGap
        self.startOfGap = rtpPackets[-2]
        # self.endOfGap = firstPackedReceivedAfterGap
        self.endOfGap = rtpPackets[-1]

        self.packetsLost = packetsLost

        # Calculate length of this glitch
        ### NOTE: Initially I calculated this by taking the diff between the two packets where there was a seq no
        # discrepency (as it seems logical to assume that the glitch duration would correlate with the no of packets lost).
        # However, I've observed a situation whereby a stream is lost and when it re-emerges at the Receiver, the
        # two packets at the boundary of the glitch arrive bunched together. This means that the packet loss calculation
        # is correct (because it relies upon sequence numbers) but the glitch duration is incorrect.
        # Therefore I am attempting to get around this by taking the timestamp diff between rtpPackets[-1] (the most recent)
        # and rtpPackets[-3] which is assumed to be the last 'on time' packet.
        # At worst, this will have the effect of adding one 'packet period's worth of time to the calculated glitch period

        # self.glitchLength = firstPackedReceivedAfterGap.timestamp - lastReceivedPacketBeforeGap.timestamp
        self.glitchLength = rtpPackets[-1].timestamp - rtpPackets[-3].timestamp

        # Calculate useful values showing expected and actual rtpSequence no
        self.expectedSequenceNo = self.startOfGap.rtpSequenceNo + 1
        self.actualReceivedSequenceNo = self.endOfGap.rtpSequenceNo

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        optionalFields = " " + Utils.dtstrft(self.glitchLength) + ", " + str(self.packetsLost) + " lost. "+\
                "Exptd." +str(self.expectedSequenceNo)+", Got."+ str(self.actualReceivedSequenceNo)
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "Duration,"+str(self.glitchLength)+", packet(s) lost,"+str(self.packetsLost)+\
            ",Expected seq no,"+str(self.expectedSequenceNo)+",Actual received seq no,"+ str(self.actualReceivedSequenceNo)
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string

        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'packetsLost': self.packetsLost, 'duration': self.glitchLength,
                'lastReceivedPacketBeforeGap.rtpSequenceNo': self.startOfGap.rtpSequenceNo,
                'firstPackedReceivedAfterGap.rtpSequenceNo': self.endOfGap.rtpSequenceNo,
                'expectedSequenceNo': self.expectedSequenceNo,
                'actualReceivedSequenceNo': self.actualReceivedSequenceNo}
        # Create the json object
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation


# Define an generic event to represent an unexpected sequence no
# This can be inherited, and the daughter events will automatically take on the name of the inherited class
class UnexpectedSeqNo(Event):
    def __init__(self, stats, prevReceivedPacket, lastReceivedPacket):
        super().__init__(stats)
        # Define instance variable
        self.lastReceivedPacket = lastReceivedPacket
        self.prevReceivedPacket = prevReceivedPacket


    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True,
                   includeFriendlyName=True):
        try:
            optionalFields = ", Expected seq no " + str(self.prevReceivedPacket.rtpSequenceNo + 1) + ", got " +\
                str(self.lastReceivedPacket.rtpSequenceNo)
        except:
            optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "Expected seq no," + str(self.prevReceivedPacket.rtpSequenceNo + 1) +\
                         ",Actual received seq no," + str(self.lastReceivedPacket.rtpSequenceNo)
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'expectedSequenceNo': self.prevReceivedPacket.rtpSequenceNo + 1,
                          'actualReceivedSequenceNo': self.lastReceivedPacket.rtpSequenceNo}
        # Create the json object
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation

# Define an event to represent an out of order packet O(where the received rtp sequence no appears to go backwards)
class OutOfOrderPacket(UnexpectedSeqNo):
    def __init__(self, stats, prevReceivedPacket, lastReceivedPacket):
        # Invoke Constructor method of super class (UnexpectedSeqNo)
        super().__init__(stats, prevReceivedPacket, lastReceivedPacket)


class DuplicateSequenceNo(UnexpectedSeqNo):
    def __init__(self, stats, prevReceivedPacket, lastReceivedPacket):
        # Invoke Constructor method of super class (UnexpectedSeqNo)
        super().__init__(stats, prevReceivedPacket, lastReceivedPacket)

# Define an event to represent a change in the IP routing yielded by the Traceroute thread
class IPRoutingTracerouteChange(Event):

    def __init__(self, stats, latestHopsList):
        # Call Constructor of parent class. This will set parameters such as timeCreated etc
        super().__init__(stats)
        # Declare specific instance variables
        self.latestHopsList = latestHopsList

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True,
                   includeFriendlyName=True):
        try:
            optionalFields = ", No of hops: " + str(len(self.latestHopsList))
        except:
            optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        optionalFields = "Hops,"
        try:
            # Firstly, write the no of hops
            optionalFields += str(len(self.latestHopsList)) + ", "
            # Iterate over the hops list, formatting each list of Octets as a string
            for hop in self.latestHopsList:
                optionalFields += (str(hop[0]) + "." + str(hop[1]) + "." + str(hop[2]) + "." + str(hop[3]) + ",")
        except:
            optionalFields += "No hops to display,"
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # # Returns a json object representation of the event as a string
        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'hoplist': self.latestHopsList}
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation

# Define an event to register a change in the TTL field of the received UDP packets - signals a route change
class IPRoutingTTLChange(Event):
    def __init__(self, stats, prevRxTTL, currentRxTTL):
        # Call Constructor of parent class. This will set parameters such as timeCreated etc
        super().__init__(stats)
        # Declare specific instance variables
        self.prevRxTTL = prevRxTTL
        self.currentRxTTL = currentRxTTL

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True,
                   includeFriendlyName=True):
        try:
            optionalFields = ", Rx TTL change: " + str(self.prevRxTTL) + " >> " + str(self.currentRxTTL)
        except:
            optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        optionalFields = ""
        try:
            optionalFields = "prev rxTTL," + str(self.prevRxTTL) + ",current rxTTL," + str(self.currentRxTTL)
        except:
            pass
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # # Returns a json object representation of the event as a string
        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'prev rxTTL': self.prevRxTTL, 'current rxTTL': self.currentRxTTL}
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation

# Define an Event to represent a change in source address (address or port)
class SrcAddrChange(Event):

    def __init__(self, stats, prevSrcAddr, prevSrcPort, currentSrcAddr, currentSrcPort):
        # Call Constructor of parent class. This will set parameters such as timeCreated etc
        super().__init__(stats)
        # Declare specific instance variables
        self.prevSrcAddr = prevSrcAddr
        self.prevSrcPort = prevSrcPort
        self.currentSrcAddr = currentSrcAddr
        self.currentSrcPort = currentSrcPort

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True,
                   includeFriendlyName=True):
        try:
            optionalFields = ", " + str(self.prevSrcAddr) + ":" + str(self.prevSrcPort) + \
                             ">" + str(self.currentSrcAddr) + ":" + str(self.currentSrcPort)
        except:
            optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        optionalFields = ""
        try:
            optionalFields = "prev source," + str(self.prevSrcAddr) + ":" + str(self.prevSrcPort) + \
                             ",current source," + str(self.currentSrcAddr) + ":" + str(self.currentSrcPort)
        except:
            pass
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # # Returns a json object representation of the event as a string
        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'prev source address': self.prevSrcAddr, 'prev source port': self.prevSrcPort,
                          'current source address': self.currentSrcAddr, 'current source port': self.currentSrcPort}
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation

# Define an Event to represent a change in dest address (address or port)
class DestAddrChange(Event):

    def __init__(self, stats, prevDestAddr, prevDestPort, currentDestAddr, currentDestPort):
        # Call Constructor of parent class. This will set parameters such as timeCreated etc
        super().__init__(stats)
        # Declare specific instance variables
        self.prevDestAddr = prevDestAddr
        self.prevDestPort = prevDestPort
        self.currentDestAddr = currentDestAddr
        self.currentDestPort = currentDestPort

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True,
                   includeFriendlyName=True):
        try:
            optionalFields = ", " + str(self.prevDestAddr) + ":" + str(self.prevDestPort) + \
                             ">" + str(self.currentDestAddr) + ":" + str(self.currentDestPort)
        except:
            optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        optionalFields = ""
        try:
            optionalFields = "prev dest," + str(self.prevDestAddr) + ":" + str(self.prevDestPort) + \
                             ",current dest," + str(self.currentDestAddr) + ":" + str(self.currentDestPort)
        except:
            pass
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # # Returns a json object representation of the event as a string
        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'prev dest address': self.prevDestAddr, 'prev dest port': self.prevDestPort,
                          'current dest address': self.currentDestAddr, 'current dest port': self.currentDestPort}
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation

# Define an Event that represents the resuming of an existing known stream, following a Streamlost Event
# Calculates the duration between the previous StreamLost and 'now' to
class StreamResumed(Event):
    def __init__(self, stats, streamLostTimestamp):
        # Call Constructor of parent class. This will set parameters such as timeCreated etc
        super().__init__(stats)
        # Declare Event-specific instance variables
        self.streamLostTimestamp = streamLostTimestamp
        self.durationOfOutage = datetime.timedelta()
        # Calculate the length of the outage
        # Take into account the length of time for the StreamLost alarm to be triggered
        try:
            self.durationOfOutage = self.timeCreated - self.streamLostTimestamp + \
                                    datetime.timedelta(seconds=Registry.lossOfStreamAlarmThreshold_s)
        except Exception as e:
            Utils.Message.addMessage("ERR: StreamResumed calculate outage " + str(e))
            self.durationOfOutage = None


    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True,
                   includeFriendlyName=True):
        try:
            # optionalFields = ", Start:" + str(self.streamLostTimestamp.strftime("%H:%M:%S")) + ", End:" + \
            #                  str(self.timeCreated.strftime("%H:%M:%S")) + \
            #                  ", Dur:" + str(Utils.dtstrft(self.durationOfOutage))
            optionalFields = ", Dur:" + str(Utils.dtstrft(self.durationOfOutage))

        except:
            optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        optionalFields = ""
        try:
            optionalFields = "stream lost at," + str(self.streamLostTimestamp.strftime("%d/%m %H:%M:%S")) + \
                             ",stream restarted," + str(self.timeCreated.strftime("%d/%m %H:%M:%S")) + \
                             ", outage duration," + str(Utils.dtstrft(self.durationOfOutage))
        except:
            pass
        csv = Event.createCommonCSVString(self) + optionalFields
        return csv

    def getJSON(self):
        # # Returns a json object representation of the event as a string
        # Create dictionary with any additional keys specific to this type of event
        additionalData = {'stream lost at': self.streamLostTimestamp, 'stream restarted': self.timeCreated,
                          'outage duration': self.durationOfOutage}
        jsonRepresentation = Event.createJsonRepresentationOfEvent(self, additionalKeysDict=additionalData)
        return jsonRepresentation


# Stores a running total of events that happened within the last x seconds with y granularity
class MovingTotalEventCounter(object):
    # Stores a running total of events that happened within the last x seconds with y granularity
    # x (the total duration of interest, eg a day, hour, week) and y (the duration of each sampling period eg.
    # for a duration of 12 hours, you might want 12 1hr samples so that you can determine the spread of events
    # over that time
    # Once created, to register a new event, call addEvent()
    # The object does not have a built in timer. Therefore it must be 'clocked' every second, by calling recalculate()
    def __init__(self, name, totalPeriod_s, samplingPeriod_S):
        self.name = name
        self.samplingPeriod_S = samplingPeriod_S
        # Calculate length of array required for totalPeriod_s for a given samplingPeriod_S
        # eg a 60 second moving total, with 10 second granularity would require an array length = 6
        self.noOfSamplePeriods = totalPeriod_s // samplingPeriod_S
        # Safety check the result
        if self.noOfSamplePeriods < 1:
            self.noOfSamplePeriods = 1
        # Create a list to hold historic totals and prefill with zeroes
        self.historicEventsList = [0] * self.noOfSamplePeriods

        # Declare var to hold the current running total of events
        self.__eventCountRunningTotal = 0

        # Declare var to hold latest result
        self.__eventCountMovingTotal = 0

        # Declare a var to hold the elapsed time (in seconds)
        self.__timeElapsed_S = 0

    def addEvent(self, noOfEvents):
        # Adds noOfEvents to the current running total of events (in latest sampling period)
        self.__eventCountRunningTotal += noOfEvents
        # Update the latest sampling period with the new total
        self.historicEventsList[-1] = self.__eventCountRunningTotal

    def recalculate(self):
        # recalculates self.eventCountMovingTotal based on current time elapsed and self.eventCountRunningTotal
        # If the current sampling period is coming to an end, appends a new sampling period to the array and
        # deletes the oldest data

        # Increment the elapsed timer
        self.__timeElapsed_S += 1

        # Check to see if we have reached the end pof the current sampling period and therefore have to
        # create a new sampling period (and delete the oldest)
        if self.__timeElapsed_S > (self.samplingPeriod_S - 1):
            # Clear timer
            self.__timeElapsed_S = 0
            # Update most recent element of the array with current running total (within this sample period)
            self.historicEventsList[-1] = self.__eventCountRunningTotal
            # Append a new element onto thr end of the array (with value 0)
            self.historicEventsList.append(0)
            # Clear running total for this sampling period
            self.__eventCountRunningTotal = 0
            # Check for length of array. If longer than noOfSamplePeriods, discard first element of array
            if len(self.historicEventsList) > self.noOfSamplePeriods:
                # discard first (oldest) element of array
                self.historicEventsList.remove(self.historicEventsList[0])

        # Clear old total
        self.__eventCountMovingTotal = 0
        # Sum contents of array to get total no of events over the entire period
        for x in self.historicEventsList:
            self.__eventCountMovingTotal += x

    def getResults(self):
        # Return a tuple containing it's [name, the current moving total, a list of events]
        return self.name, self.__eventCountMovingTotal, list(self.historicEventsList)

# Define an object to hold data about an individual received rtp packet
class RtpData(object):
    # Constructor method
    def __init__(self, rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData, rxTTL,
                 srcAddr, srcPort, destAddr, destPort):
        self.rtpSequenceNo = rtpSequenceNo
        self.payloadSize = payloadSize
        self.timestamp = timestamp
        self.syncSource = syncSource
        self.isptestHeaderData = isptestHeaderData
        self.rxTTL = rxTTL  # The TTL field from the IP header carrying this Rtp packet
        self.srcAddr = srcAddr
        self.srcPort = srcPort
        self.destAddr = destAddr
        self.destPort = destPort
        # timeDelta will store the timestamp diff between this and the previous packet
        self.timeDelta = 0
        # jitter will store the diff between the timeDelta of this and the prev packet
        self.jitter = 0

# Define a Super Class for all RTP objects (Generators, ReceiveStreams, ReceiveResults..)
# This will contain methods that are useful to all
class RtpCommon(object):
    def __init__(self) -> None:
        super().__init__()
        # Default timeout for all http requests
        self.httpRequestTimeout=0.1
        # the TCP listener port of the HTTP Server running on the controller process (used for whois lookups etc via tha API)
        self.controllerTCPPort = None
        # Var to store the instance of the HTTP Server created in httpServerThreadCommon.
        # Required in order to be able to access the  HTTPServer.shutdown() method
        self.httpd = None

        self.syncSourceIdentifier = None

    # Takes a list of octets [[a,b,c,d],[a,b,c,d]....] and XORs all contents to a single byte to create a checksum value
    # Returns None on failure, otherwise returns an int
    def createTracerouteChecksum(self, hopsList):
        try:
            if len(hopsList) > 0:
                # Create lambda function to xor two values
                xor = lambda x, y: x ^ y
                # Use reduce() to iterate over a the list of octets in sequence using our lambda function
                xorSingleHop = lambda hopOctets: reduce(xor, hopOctets)
                # Create variable to hold the output
                output = 0
                # Iterate over the all the hops, xor'ing each hop in turn
                for hop in hopsList:
                    # XOR current hop with all previous hops
                    output = output ^ xorSingleHop(hop)
                return output
            else:
                return 0
        except Exception as e:
            return None

    # Blocking method to be run as an HTTP Server
    # Because it actually invokes the HTTP Server, it needs access to the HTTPRequestHandler which will contain the
    # do_GET(), do_POST etc methods
    # StreasmID is not actually required for the http server, but is useful for logging purposes
    def httpServerThreadCommon(self, tcpListenPort, streamID, httpRequestHandler, addr="127.0.0.1"):
        # Utils.Message.addMessage("DBUG: start " + str(self.__stats["stream_syncSource"]) + ":httpServerThread")
        try:
            # This call will block
            self.httpd = Utils.CustomHTTPServer((addr, tcpListenPort), httpRequestHandler)

            # Pass this RtpReceiveStream instance to the server (so that the dynamically created instances of
            # httpRequestHandler will have access to the parent object)
            self.httpd.setParentObjectInstance(self)
            # Start the http server - *This will block until self.httpd.shutdown() is called (but only by another thread)*
            self.httpd.serve_forever()

        except Exception as e:
            raise Exception(f"ERR: RtpCommon.httpServerThread stream:{streamID}, port:{tcpListenPort}, error:{e}")

# Define a Super Class for RTP Receive streams. This will contain methods that are common to both
# RtpReceiveStream and RtpStreamResults
class RtpReceiveCommon(RtpCommon):
    def __init__(self):
        # Call super constructor
        super().__init__()

        # Create a 'leaderboard' for the worst 10 glitches
        self.worstGlitchesList = []
        self.worstGlitchesMutex = threading.Lock()

        # A list to contain the traceroute hops as received as part of the isptestheader data
        self.tracerouteHopsList = []  # A list of tuples containing [IP octet1, IP octet2, IP octet3, Ip octet4]
        self.tracerouteHopsListMutex = threading.Lock()
        self.tracerouteHopsListLastUpdated = None  # Timestamps the last successful traceroute update

        # Deque list to hold previous traceroute results (used for the traceroute viewer)
        self.historicTracerouteEvents = deque(maxlen=Registry.rtpCommonHistoricTracerouteEventsToKeep)

    # Thread-safe method to return a list of the worst glitches
    # If returnSummaries is True, will return a list of summary strings. Otherwise will return a list of events
    def getWorstGlitches(self, returnSummaries = False):
        self.worstGlitchesMutex.acquire()
        worstGlitchesList = deepcopy(self.worstGlitchesList)
        self.worstGlitchesMutex.release()
        if returnSummaries is False:
            # Default behaviour, return a list of events
            return worstGlitchesList
        else:
            # Return a list of text strings containing summaries of the glitch event
            glitchSummariesList = []
            for glitch in worstGlitchesList:

                g = glitch.getSummary(includeStreamSyncSourceID=False,
                                                            includeEventNo=True,
                                                            includeType=False,
                                                            includeFriendlyName=False)
                summary = str(g['timeCreated'].strftime("%d/%m %H:%M:%S")) + ", " + str(g['summary'])
                glitchSummariesList.append(summary)
            return glitchSummariesList

    # Populates self.worstGlitchesList
    # It will also maintain a top ten list of the worst glitches so far
    def addToWorstGlitchesList(self, glitch):
        # Specify the length of the 'glitch wall of shame' leaderboard
        listLength = 10
        # First, get a local copy of the glitches list
        worstGlitchesList = []
        worstGlitchesList = self.getWorstGlitches()
        # Append the latest glitch to the local copy of the list
        worstGlitchesList.append(glitch)
        # Now sort the list, based on glitch.packetsLost parameter in descending order
        worstGlitchesList.sort(key=lambda x: x.packetsLost, reverse=True)
        # Trim off any excess list entries beyond that specified by listLength
        if len(worstGlitchesList) > listLength:
            # Remove the last element of the list
            worstGlitchesList.pop()
        # Copy the sorted list back into the instance variable
        self.worstGlitchesMutex.acquire()
        self.worstGlitchesList = deepcopy(worstGlitchesList)
        self.worstGlitchesMutex.release()


    # Thread-safe method to return a list of the traceroute hops
    # Returns a tuple of the lastUpdatedTimestamp and the hops list
    def getTraceRouteHopsList(self):
        self.tracerouteHopsListMutex.acquire()
        tracerouteHopsList = deepcopy(self.tracerouteHopsList)
        self.tracerouteHopsListMutex.release()
        return self.tracerouteHopsListLastUpdated, tracerouteHopsList

    # Thread-safe method to set the self.tracerouteHopsList[]
    # This completely replaces the existing list with a new supplied list
    def setTraceRouteHopsList(self, newList):
        self.tracerouteHopsListMutex.acquire()
        # Copy the new list into the instance variable list
        self.tracerouteHopsList = deepcopy(newList)
        self.tracerouteHopsListMutex.release()
        # Update the timestamp
        self.tracerouteHopsListLastUpdated = datetime.datetime.now()

    # This method attempts to update an individual tracerouteHopsList list entry
    # It should be much faster than setTraceRouteHopsList (which has to copy the entire list)
    # It begins by comparing the lengths of the current stored list with the latest known length
    # If there is a discrepency, it will reinitialise the list to the new length
    # The arg 'hop' is zero indexed (so hop 0 is the first address in the hop list)
    def updateTraceRouteHopsList(self, hopNo, noOfHops, hopAddr):
        if noOfHops > 0:
            self.tracerouteHopsListMutex.acquire()
            try:
                if len(self.tracerouteHopsList) == noOfHops:
                    pass
                else:
                    # If there is a discrepancy between the length the list and the latest known length
                    # Throw away the current list and initialise a new empty list
                    self.tracerouteHopsList = [None] * noOfHops
                self.tracerouteHopsList[hopNo] = hopAddr
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveCommon.updateTraceRouteHopsList() " + str(e))
            self.tracerouteHopsListMutex.release()

    @abstractmethod
    def getRtpStreamStats(self, keyIs=None, keyContains=None, keyStartsWith=None, listKeys=False):
        pass

    @abstractmethod
    def getRTPStreamEventList(self, *args, filterList=None, reverseOrder=False, requestedEventNo=None,
                              recent=None, start=None, end=None):
        pass

    @abstractmethod
    def getRTPStreamID(self):
        pass

    # This method will generate a formatted report containing the performance of the Rtp Stream
    def generateReport(self, eventFilterList=None):
        # It will include:-
        # Source Ip, Dest IP, Port, Sync Source ID, Friendly Name
        # Duration of test, % Loss, Glitch period, bitrate, packet size
        # % Loss
        # Get a dump of the current stats
        stats = self.getRtpStreamStats()
        # Get a dump of the current events (taking into account whether display filtering has been applied)
        # Retrieve the desired event types from the RTP Stream object
        # The '\r\n' escape sequence is required for Windows
        eventsList = self.getRTPStreamEventList(filterList=eventFilterList)
        worstGlitchesList = self.getWorstGlitches(returnSummaries=True)


        # Simple local function to determine the current operation mode based on the type of 'this' object instance
        # and return a string
        def getOperationMode():
            if type(self) == RtpStreamResults:
                return "TRANSMIT"
            elif type(self) == RtpReceiveStream:
                return "RECEIVE"
            else:
                return "UNKNOWN"

        # Get a copy of the traceroute hops list.
        tracerouteHopsList = []
        tracerouteLastUpdate = None
        try:
            tracerouteLastUpdate, tracerouteHopsList = self.getTraceRouteHopsList()
        except Exception as e:
            Utils.Message.addMessage("ERR: RtpReceiveCommon.generateReport, get traceroute hops list. stream " +\
                                     str(stats["stream_syncSource"]) + ", " + str(e))

        separator = ("-" * 63) + "\r\n"
        title = "Report for stream " + str(stats["stream_syncSource"]) + ", (" + str(
            stats["stream_friendly_name"]).rstrip() + ")" + "\r\n"
        subtitle = "Generated by isptest v" + str(Registry.version) +\
                   " running in " + str(getOperationMode()) + " mode at " +\
            datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\r\n"
        streamIPDetails = \
            str(stats["stream_transmitter_local_srcPort"]) + ":" + str(stats["stream_transmitter_localAddress"]) +\
            "(" + str(stats["stream_srcAddress"]) + ")" + " ---> " + "(" + str(stats["stream_srcPort"]) + ":" +\
            str(stats["stream_transmitter_destAddress"]) + ")" + str(stats["stream_rxAddress"]) + ":" +\
            str(stats["stream_rxPort"]) + "\r\n" + \
            "Packet size: " + str(stats["packet_payload_size_mean_1S_bytes"]) + " bytes" + \
            ", Received bitrate: " + str(Utils.bToMb(8 * stats["packet_data_received_1S_bytes"])) + "bps" + "\r\n"
        transmitterDetails = ""
        # Now test to see if this stream was generated by isptest. if so, add some details about the transmitter
        if stats["stream_transmitterVersion"] > 0:
            transmitterDetails = \
                "Transmitter version: v" + str(stats["stream_transmitterVersion"]) + \
                ", Transmit bitrate: " + str(Utils.bToMb(stats["stream_transmitter_txRate_bps"])) + "bps" + \
                ", Return loss " + str("%0.2f" % stats["stream_transmitter_return_loss_percent"]) + "%" + "\r\n"


        labelWidth = 33
        streamPerformance = \
            "Duration of test: ".rjust(labelWidth) + str(Utils.dtstrft(stats["stream_time_elapsed_total"], showDays=True)) + "\r\n" + \
        "Total bytes received: ".rjust(labelWidth) + str(Utils.bToMb(stats["packet_data_received_total_bytes"])) + "B" +\
            "\r\n" + \
        "Packet loss: ".rjust(labelWidth) + str("%0.2f" % stats["glitch_packets_lost_total_percent"]) + "%" + "\r\n" + \
        "Total packets lost: ".rjust(labelWidth) + str(int(stats["glitch_packets_lost_total_count"])) + "\r\n" + \
            "Mean packet loss per glitch: ".rjust(labelWidth) + str(math.ceil(stats["glitch_packets_lost_per_glitch_mean"])) + "\r\n" + \
            "Total no of glitches: ".rjust(labelWidth) + str(int(stats["glitch_counter_total_glitches"])) + "\r\n" + \
            str("Ignored glitches (<=" + str(stats["glitch_Event_Trigger_Threshold_packets"]) + " packets lost): ").rjust(labelWidth) + \
            str(int(stats["glitch_glitches_ignored_counter"])) + "\r\n" + \
            "Maximum glitch dur: ".rjust(labelWidth) + str(Utils.dtstrft(stats["glitch_max_glitch_duration"])) + "\r\n" + \
            "Mean glitch dur: ".rjust(labelWidth) + str(Utils.dtstrft(stats["glitch_mean_glitch_duration"])) + "\r\n" + \
            "Mean interval between glitches: ".rjust(labelWidth) + str(
                Utils.dtstrft(stats["glitch_mean_time_between_glitches"], showDays=True)) + "\r\n"
        worstGlitchesListAsString = "Worst Glitches:\r\n"


        if len(stats["glitch_worst_glitches_list"]) > 0:
            for glitch in stats["glitch_worst_glitches_list"]:
                worstGlitchesListAsString += str(glitch) + "\r\n"

        else:
            worstGlitchesListAsString += "No glitches to report\r\n"

        # if available, create route change stats
        routeChangeStats = "Route Change stats:\r\n"
        try:
        # Get traceroute change stats
            if len(tracerouteHopsList) > 0 and None not in tracerouteHopsList:
                routeChangeStats += "No. of traceroute changes: ".rjust(labelWidth) + \
                                              str(stats["route_change_events_total"]) + "\r\n"
                routeChangeStats += "Mean interval between route changes: ".rjust(labelWidth) +\
                                              str(Utils.dtstrft(stats["route_mean_time_between_route_change_events"], showDays=True)) + "\r\n"
                if type(stats["route_time_of_last_route_change_event"]) == datetime.datetime:
                    # At creation, this parameter is a datetime.timedelta object, which means that it won't have a
                    # strftime() method. Therefore, we need to check that it's been turned into a timestamp (which is a
                    # datetime.datetime object) which will have a strftime() method
                    routeChangeStats += "Time of last route change: ".rjust(labelWidth) + \
                                    str(stats["route_time_of_last_route_change_event"].strftime("%d/%m %H:%M:%S")) + "\r\n"


            # Get RxTTL stats (if available)
            if stats["packet_ttl_decrement_count"] is not None:
                routeChangeStats += "No of hops according to received TTL: ".rjust(labelWidth) + \
                                              str(stats["packet_ttl_decrement_count"]) + "\r\n"
            if stats["packet_instantaneous_ttl"] is not None:
                routeChangeStats += "No of received TTL changes: ".rjust(labelWidth) + \
                                    str(stats["route_TTl_change_events_total"]) + "\r\n"
                routeChangeStats += "Mean interval between TTL changes: ".rjust(labelWidth) + \
                                    str(Utils.dtstrft(stats["route_mean_time_between_TTl_change_events"], showDays=True)) + "\r\n"
                if type(stats["route_time_of_last_TTL_change_event"]) == datetime.datetime:
                    # At creation, this parameter is a datetime.timedelta object, which means that it won't have a
                    # strftime() method. Therefore, we need to check that it's been turned into a timestamp (which is a
                    # datetime.datetime object) which will have a strftime() method
                    routeChangeStats += "Time of last TTL change: ".rjust(labelWidth) + \
                                    str(stats["route_time_of_last_TTL_change_event"].strftime("%d/%m %H:%M:%S")) + "\r\n"
            else:
                routeChangeStats += "No received TTL information available" + "\r\n"

        except Exception as e:
            Utils.Message.addMessage("RtpreceiveCommon.generateReport() route stats " + str(e))


        # Create a traceroute list of hops.
        tracerouteHopsListAsString = "Traceroute:\r\n"
        if len(tracerouteHopsList) > 0 and None not in tracerouteHopsList:
            for hopNo in range(len(tracerouteHopsList)):
                try:
                    hopAddr = str(tracerouteHopsList[hopNo][0]) + "." + \
                        str(tracerouteHopsList[hopNo][1]) + "." + \
                        str(tracerouteHopsList[hopNo][2]) + "." + \
                              str(tracerouteHopsList[hopNo][3])
                    tracerouteHopsListAsString += str(hopNo + 1) + "\t" + hopAddr.ljust(16)
                    # Now query the hop name to see if it's in the whois cache
                    hopName = Utils.WhoisResolver.queryWhoisCache(hopAddr)
                    if hopName is not None:
                        tracerouteHopsListAsString += hopName[0]['asn_description']
                    tracerouteHopsListAsString += "\r\n"

                except Exception as e:
                    Utils.Message.addMessage("DBUG: RtpReceiveCommon.generateReport() Create traceroute string: " + str(e))
                    tracerouteHopsListAsString += "--Invalid traceroute data--\r\n"
            if tracerouteLastUpdate is not None:
                try:
                    tracerouteHopsListAsString += "Last updated: " + tracerouteLastUpdate.strftime("%d/%m %H:%M:%S") + "\r\n"
                except Exception as e:
                    Utils.Message.addMessage("ERR: RtpReceiveCommon.generateReport() add traceroute last updated " + str(e))


        else:
            tracerouteHopsListAsString += "No traceroute info available" + "\r\n"

        # Create list of events (as a string)
        eventsListAsAString = "Events:\r\n"
        # Display the events list in reverse order (most recent first)
        for event in range(len(eventsList) - 1, -1, -1):
            # Retrieve each Event summary, ommiting the syncSourceID and the friendlyName (for display purposes)
            eventDetails = eventsList[event].getSummary(includeStreamSyncSourceID=False, includeFriendlyName=False)
            # Creata a formatted string for the event
            eventsListAsAString += (str(eventDetails['timeCreated'].strftime("%d/%m %H:%M:%S")) + \
                                    ", " + str(eventDetails['summary']) + "\r\n")

        outputString = title + subtitle + separator + streamIPDetails + transmitterDetails + \
                       separator + streamPerformance + separator +\
                        routeChangeStats + separator +\
                        tracerouteHopsListAsString + separator +\
                       worstGlitchesListAsString + separator + eventsListAsAString

        # Return a string containing the output
        return outputString

    # This utility method will generate a filename based on the stream parameters.
    # The optional includePath will create a filename with a complete path
    # By default, the filename prefix will be pulled from Registry.streamReportFilename but can be overridden
    # by setting overrideFileNamePrefix
    def createFilenameForReportExport(self, includePath=True, overrideFileNamePrefix=None):
        # Get info about the stream (to be used in the title)
        syncSourceID, srcAddr, srcPort, friendlyName = self.getRTPStreamID()
        fileName = ""
        # Filename prefix not specified, so pull from the Registry
        if overrideFileNamePrefix is None:
            fileName += Registry.streamReportFilename
        else:
            # Use supplied filename prefix
            fileName += str(overrideFileNamePrefix).strip()

        fileName += str(syncSourceID) + "_" + \
                   str(friendlyName).rstrip() + "_" + \
                   str(srcAddr) + "_" + \
                   str(datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S"))
        # Return a sanitised filename including the full path (as specified in Registry.resultsPath
        # Note the use of sanitize_filepath will automatically orientate the 'slash' for Windows or Mac/Linux
        if includePath:
            # This will return a filname incuding the path retrieved from Registry.resultsSubfolder
            return sanitize_filepath(Registry.resultsSubfolder + fileName + ".txt")
        else:
            # This will just return a filename
            return sanitize_filepath(fileName + ".txt")

    # This utility class method will generate a filename based on the stream parameters.
    # The optional includePath will create a filename with a complete path
    # By default, the filename prefix will be pulled from Registry.streamReportFilename but can be overridden
    # by setting overrideFileNamePrefix
    @classmethod
    def createFilenameForReportExportClassMethod(cls, syncSourceID, includePath=True, overrideFileNamePrefix=None):
        # Get info about the stream (to be used in the title)
        syncSourceID, srcAddr, srcPort, friendlyName = self.getRTPStreamID()
        fileName = ""
        # Filename prefix not specified, so pull from the Registry
        if overrideFileNamePrefix is None:
            fileName += Registry.streamReportFilename
        else:
            # Use supplied filename prefix
            fileName += str(overrideFileNamePrefix).strip()

        fileName += str(syncSourceID) + "_" + \
                    str(friendlyName).rstrip() + "_" + \
                    str(srcAddr) + "_" + \
                    str(datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S"))
        # Return a sanitised filename including the full path (as specified in Registry.resultsPath
        # Note the use of sanitize_filepath will automatically orientate the 'slash' for Windows or Mac/Linux
        if includePath:
            # This will return a filname incuding the path retrieved from Registry.resultsSubfolder
            return sanitize_filepath(Registry.resultsSubfolder + fileName + ".txt")
        else:
            # This will just return a filename
            return sanitize_filepath(fileName + ".txt")


    # Simple local function to determine the current operation mode based on the type of 'this' object instance
    # and return a string
    def getOperationMode(self):
        if type(self) == RtpStreamResults:
            return "TRANSMIT"
        elif type(self) == RtpReceiveStream:
            return "RECEIVE"
        else:
            return "UNKNOWN"

    # This method will generate a formatted report containing the last n IPRoutingTracerouteChange Events
    # Setting historyLength will modify the no of historic events to include
    def generateTracerouteHistoryReport(self, historyLength=10):
        # Takes a list of tuples [[ip address, whoisLookup],...] and renders them as a table
        # Returns a string containing /t and newline chars
        def renderTracerouteDataAsTable(tracerouteData):
            # String to hold the output
            renderedTable = f""
            for hopNo in range(len(tracerouteData)):
                # Create each table row as [hopNo, ip address, whois name]
                addr = str(tracerouteData[hopNo][0]).ljust(16) # Pad each IP address to 16 characters
                whoisName = tracerouteData[hopNo][1]
                # Create the table row
                renderedTable += f"{hopNo + 1}\t{addr}\t{whoisName}\r\n"
            return renderedTable

        try:
            # Get a filtered eventlist of the selected Rx or RxResults stream containing only the
            # IPRoutingTracerouteChange Events
            tracerouteEventsList = self.getRTPStreamEventList(historyLength,
                                                              filterList=[IPRoutingTracerouteChange], reverseOrder=True)

            # Get a copy of the stats dict for this stream
            stats = self.getRtpStreamStats()

            if len(tracerouteEventsList) > 0:
                separator = ("-" * 63) + "\r\n"  # Dotted line separator for the report
                # Format a string containing the IP src/dest address details
                streamIPDetails = \
                    str(stats["stream_transmitter_local_srcPort"]) + ":" + \
                    str(stats["stream_transmitter_localAddress"]) + \
                    "(" + str(stats["stream_srcAddress"]) + ")" + " ---> " + "(" + \
                    str(stats["stream_srcPort"]) + ":" + \
                    str(stats["stream_transmitter_destAddress"]) + ")" + str(stats["stream_rxAddress"]) + ":" + \
                    str(stats["stream_rxPort"]) + "\r\n"


                streamReport = f"Traceroute history (last {historyLength} events) for stream " + str(stats["stream_syncSource"]) + \
                               "(" + str(stats["stream_friendly_name"]).strip() + ")" + "\r\n"
                subtitle = "Generated by isptest v" + str(Registry.version) + \
                           " running in " + str(self.getOperationMode()) + " mode at " + \
                           datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\r\n"

                streamReport += subtitle + separator + streamIPDetails + separator
                # Create an API helper
                api = Utils.APIHelper(self.controllerTCPPort, addr="127.0.0.1")

                ####### Get a copy of the current traceroute hops list and render a table with whois lookup
                try:
                    tracerouteLastUpdate, tracerouteHopsList = self.getTraceRouteHopsList()
                    currentTraceRoute = f"Current: Last updated {tracerouteLastUpdate.strftime('%d/%m/%Y %H:%M:%S')}\r\n"

                    # Use the API helper to query the WhoisResolver
                    apiResponse = api.whoisLookup(tracerouteHopsList)
                    # Now create the table contents to be displayed using the data returned from the API
                    currentTraceRoute = renderTracerouteDataAsTable(apiResponse)
                    # Append the *current* traceroute hops table string to streamReport
                    streamReport += f"Current: Last updated {tracerouteLastUpdate.strftime('%d/%m/%Y %H:%M:%S')}\r\n" +\
                                     currentTraceRoute + separator
                except Exception as e:
                    Utils.Message.addMessage(f"ERR: RtpReceiveCommon.generateTracerouteHistoryReport, get current traceroute hops list. stream "
                                             f" {stats['stream_syncSource']}, {e}, tracerouteLastUpdate:{tracerouteLastUpdate}, tracerouteHopsList:{tracerouteHopsList}")


                ####### Create tables containing historic traceroute data with whois lookup
                try:
                    for event in tracerouteEventsList:
                        # Use the API helper to query the WhoisResolver
                        apiResponse = api.whoisLookup(event.latestHopsList)
                        # Now create the table contents to be displayed using the data returned from the API
                        trData = renderTracerouteDataAsTable(apiResponse)
                        # Create display string
                        streamReport += "Time of change: " + event.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + "\r\n" + \
                                        trData + separator
                except Exception as e:
                    Utils.Message.addMessage(
                        "ERR: RtpReceiveCommon.generateTracerouteHistoryReport, get historic traceroute hops list. stream " + \
                        str(stats["stream_syncSource"]) + ", " + str(e))

                return streamReport

        except Exception as e:
            Utils.Message.addMessage("ERR:RtpReceiveCommon.generateTracerouteHistoryReport() Render traceroute history " + \
                                     str(e))
            return None

    # This function tests the supplied key against some specified key values, and formats the corresponding value
    # to make it more readable
    # if appendUnit is set, a suitable suffix (eg '%' will be appended)
    # This is a class method, so accessible anywhere
    @classmethod
    def humanise(cls, key, value, appendUnit=False):
        try:
            # This function tests the supplied key against some specified key values, and formats the corresponding value
            # to make it more readable
            # Test to see if the value is datetime object encoded in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.mmmmmm)
            # If co, convert it back to a python Datetime object
            try:
                value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
            except:
                # If this fails, test to see if the object is a datetime.timedelta object encoded as a string
                try:
                    value = Utils.convertStringToTimeDelta(value)
                except:
                    # Otherwise ignore the value
                    pass

            if value == None:
                value = " - "
            if key == "packet_data_received_1S_bytes":
                # We want this value in bps
                # Convert bytes to bits
                value *= 8
                value = Utils.bToMb(value)
                return value

            if key == "stream_syncSource" or key == 'Sync Source ID':
                value = str(value).rjust(10)

            # Render dates concisely
            if type(value) == datetime.datetime:
                value = value.strftime("%d/%m %H:%M:%S")
                return value


            if type(value) == datetime.timedelta:
                # Pass to (my) dtstrft() function to create a much shorter string
                return Utils.dtstrft(value)

            if key == "packet_data_received_total_bytes" or key == "Bytes transmitted":
                value = Utils.bToMb(value) + "B"
                return value

            if key == 'Tx Rate (actual)' or key == 'stream_transmitter_txRate_bps':
                value = Utils.bToMb(value)
                return value

            if key.find('percent') > 0:
                # Round % values to 2 dec place if less than 10.0
                if value < 10:
                    value = "%0.2f" % value
                # Othewise round to 1 decimal place (so that the value fixes into a screen space 4 chars wide)
                else:
                    value = "%0.1f" % value
                # Finally, if appendUnit is set, cast as a string and append a '%'
                if appendUnit:
                    value = str(value) + "%"
                return value

            if key.find('_uS') > 0:
                # If > 1000uS, express as a mS
                if int(value) > 1000 or int(value) < -1000:
                    value = str(math.ceil(value / 1000.0)) + "mS"
                else:
                    # Append _uS to the value
                    value = str(math.ceil(value)) + "uS"
                return value

            # TX Streams 'time remain' field
            if key == 'Time to live':
                # If this is am endless stream (created with a negative time to live)
                if value < 0:
                    value = "forever"
                elif value < 2:
                    value = "Expired"
                else:
                    value = datetime.timedelta(seconds=value)
                return value

            # Transmitter pane on Receiver
            # The time remain messages are sent very slowly so if the time remaining is < 5 seconds, just write 'Expired'
            if key == 'stream_transmitter_TimeToLive_sec':
                # If this is am endless stream (created with a negative time to live)
                if value < 0:
                    value = "forever"
                elif value < 5:
                    value = "Expired"
                else:
                    value = datetime.timedelta(seconds=value)
                return value

            if key == "stream_srcAddress" or key == "stream_rxAddress" or key == 'Dest IP':
                # Should pad ip addresses to the max no of characters aaa.bbb.ccc.ddd
                value = value.ljust(15)
                return value

            if key == "glitch_packets_lost_per_glitch_mean":
                value = math.ceil(value)
                return value
            # Else if no criteria matched, return the original value, unmodified
            else:
                return value
        except Exception as e:
            Utils.Message.addMessage("ERR:RtpReceiveCommon.humanise() value: " + str(value) + ", " + str(e))
            return value

    # Method to return a filtered version of the eventsList
    def filterEventsList(self, unfilteredEventList, filterList=None, reverseOrder=False, requestedEventNo=None,
                                recent=None, start=None, end=None):

        # Special case: If eventNo is specified, look for and return a list
        # containing a *single* event with that event no (if it still exists)
        if requestedEventNo is not None:
            # Iterate over unfilteredEventList looking for an event whose eventNo matches requestedEventNo
            filteredEventList = list(filter(lambda event: event.eventNo == requestedEventNo, unfilteredEventList))
            return filteredEventList

        # Now apply a 'type' filter (if specified)
        if filterList is not None:
            # Test to see if filterList is actually a list, or a single variable
            if type(filterList) == list:
                # A list has been passed, so carry on as normal
                pass
            else:
                # A single value has been supplied. Convert the single value to a one element list to preserve the
                # existing filter() code
                filterList = [filterList]

            # Iterate over unfilteredEventList creating a sublist containing objects (Events) that match the entries
            # specified in filterList[]
            # Note:
            # filter() is a built in method that can iterate over an iterable object (unfilteredEventList)
            # We supply it with a lambda function which takes the current event and checks to see if that type of event is
            # present in filterList[]. If it is, that Event gets added to the filteredEventsList

            # Use __class__.__name__ to get the 'concrete name' (i.e the Type of Class an object is an instance of
            # Therefore we can filter by Object type or by Object type name

            filteredEventList = \
                list(filter(lambda event: ((type(event) in filterList) or (event.__class__.__name__ in filterList)),
                            unfilteredEventList))

        else:
            # If no filter spcified, all take all the events
            filteredEventList = unfilteredEventList

        # 'recent' trumps start and end
        if recent is not None:
            # Return the last n events (or else, if kwarg 'recent' is specified'
            # IF event list not as long as n, return what does exist
            try:
                filteredEventList = filteredEventList[(recent * -1):]
            except:
                pass

        # Start specified but end is not
        elif start is not None and end is None:
            try:
                # Slice the list
                # Guard against a -ve start value
                # Inclusive, so start = 1 (or start = 0) and end = 4 will return events 1,2,3 and 4
                if start < 1:
                    start = 1
                filteredEventList = filteredEventList[start - 1:]
            except Exception as e:
                Utils.Message.addMessage(f"ERR: RtpStream.getRTPStreamEventList(start={start})"\
                                            f" index out of range: {e}")

        # end specified but not start
        elif start is None and end is not None:
            try:
                # Slice the list
                # Guard against a -ve end value
                # Inclusive, so start = 1 (or start = 0) and end = 4 will return events 1,2,3 and 4
                if end < 1:
                    end = 1
                filteredEventList = filteredEventList[:end]
            except Exception as e:
                Utils.Message.addMessage(f"ERR: RtpStream.getRTPStreamEventList(end={end})"\
                                        f" index out of range: {e}")

        elif start is not None and end is not None:
            # If kwarg 'start' and 'end' are  specified'
            try:
                # Slice the list
                # Guard against a -ve start value
                # Inclusive, so start = 1 (or start = 0) and end = 4 will return events 1,2,3 and 4
                if start < 1:
                    start = 1
                filteredEventList = filteredEventList[start - 1:end]
            except Exception as e:
                Utils.Message.addMessage("ERR: RtpStream.getRTPStreamEventList(" + str(start) + ":" +
                                         str(end) + ") requested start and end indexes out of range: " + str(e))
                filteredEventList = []

        # Finally, if reverseOrder=True, reverse the order of the returned list
        if reverseOrder:
            filteredEventList.reverse()

        return filteredEventList




# Define a class to represent a stream of received rtp packets (and associated stats)
# if restoredStreamFlag is set (in the constructor), the following optional arguments (historicStatsDict{} and
# historicEventsList[] will be used to recreate the stream by reconstructing all the old packet counters etc to
# the point where they left off
class RtpReceiveStream(RtpReceiveCommon):
    # Constructor method.
    # The RtpReceiveStream object should be created with a unique id no
    # (for instance the rtp sync-source value would be perfect)
    def __init__(self, syncSource, srcAddress, srcPort, rxAddress, rxPort, glitchEventTriggerThreshold,
                 rxQueuesDict, txQueuesDict,
                 restoredStreamFlag=False, historicStatsDict=None, historicEventsList=None, controllerTCPPort=None):
        # Call super constructor
        super().__init__()

        self.rxQueuesDict = rxQueuesDict    # This dict will contain a key (the syncSourceID) whose value points to the
                                            # packet receive queue for this stream
        self.rtpStreamQueueCurrentSize = 0  # Tracks the current size of the receive queue
        self.rtpStreamQueueMaxSize = 0     # Tracks the historic maximum size of the receive queue
        # self.packetsAddedToRxQueueCount = 0 # Tracks the packets going into the receive queue

        self.txQueuesDict = txQueuesDict # Shared dict of Queues for sending results back to the transmitter (keyed by
                                        # udp receive port)
                                        # So to access the tx queue for this object we would use
                                        # self.txQueuesDict[self.__stats["stream_rxPort"]]
        self.controllerTCPPort = controllerTCPPort # the TCP listener port of the HTTP Server running on the controller process
        # Create an API helper to allow access to the HTTP API of the Controller
        self.ctrlAPI = Utils.APIHelper(self.controllerTCPPort)
        # # Create private empty dictionary to hold stats for this RtpReceiveStream object. Accessible via a getter method
        self.__stats = {}
        # Assign to instance variable
        self.__stats["stream_syncSource"] = syncSource
        self.syncSourceIdentifier = syncSource # Added, to retain consistency with class RtpGenerator
        self.__stats["stream_srcAddress"] = srcAddress
        self.__srcAddress = srcAddress
        self.__stats["stream_srcPort"] = srcPort
        self.__srcPort = srcPort
        self.__stats["stream_rxAddress"] = rxAddress
        self.__stats["stream_rxPort"] = rxPort
        self.__stats["stream_transmitter_localAddress"] = "" # Will be populated by incoming isptest header data
        self.__stats["stream_transmitter_local_srcPort"] = 0  # Will be populated by incoming isptest header data
        self.__stats["stream_transmitter_destAddress"] = "" # Will be populated by incoming isptest header data
        self.__stats["stream_transmitterVersion"] = 0
        self.__stats["stream_transmitter_PID"] = 0
        self.__stats["stream_transmitter_txRate_bps"] = 0 # Will be populated by incoming isptest header data
        self.__stats["stream_transmitter_TimeToLive_sec"] = 0  # Will be populated by incoming isptest header data
        self.__stats["stream_transmitter_return_loss_percent"] = 0  # Will be populated by incoming isptest header data
        Utils.Message.addMessage("INFO: RtpReceiveStream:: Creating RtpReceiveStream with syncSource: " + str(self.__stats["stream_syncSource"]))

        # A list to contain the *live* traceroute hops as received as part of the isptestheader data
        # Note: This list is liable to be in a state of flux as it's being continuaously updated
        self.liveTracerouteHopsList = []  # A list of tuples containing [IP octet1, IP octet2, IP octet3, Ip octet4]
        self.liveTracerouteHopsListMutex = threading.Lock()
        self.liveTracerouteHopsListLastUpdated = None  # Timestamps the last traceroute update

        # Var to store the traceroute checksum value extracted from the isptestheader data
        self.tracerouteReceivedChecksum = 0
        # Create a mutex lock to be used by the a thread
        # To set the lock use: __accessRtpDataMutex.acquire(), To release use: __accessRtpDataMutex.release()
        # self.__accessRtpStreamStatsMutex = threading.Lock()
        # self.__accessRtpStreamEventListMutex = threading.Lock()

        # Add a name field (which can be set with a friendly name (via a setter method) to identify the stream)
        # This value is pulled from the RtpGenerator object
        self.maxNameLength = RtpGenerator.getMaxFriendlyNameLength()

        # On init, set friendly name to be the same as the sync source ID (padded out with spaces)
        self.__stats["stream_friendly_name"] = \
            str(str(self.__stats["stream_syncSource"])[0:self.maxNameLength]).ljust(self.maxNameLength, " ")

        # Query (and store) the length of the headers sent by RtpGenerator so we know how to decode them
        self.ISPTEST_HEADER_SIZE = RtpGenerator.getIsptestHeaderSize()

        # Stream status flags
        self.__stats["lossOfStreamFlag"] = False
        self.__stats["streamIsDeadFlag"] = False
        self.__stats["lossOfStreamEventTimestamp"] = datetime.timedelta()
        self.__stats["lastUpdatedTimestamp"] = datetime.timedelta() # Timestamp of when the stats[] dict was last updated

        # Create private empty list to hold Events for this RtpReceiveStream object. Accessible via a getter method
        self.__eventList = deque(maxlen=Registry.rtpReceiveStreamHistoricEventsLimit)

        # Running totals updated by __queueReceiverThread()
        # Notes: These running counters are updated very frequently (with every packet received) so they are kept
        # separate from the (identical) counters in the stats[] dict
        self.packetCounterReceivedTotal = 0 # Note: This is made public to aid debugging. It's queried by the help table
        self.__packetCounterTotalLost = 0
        self.__packetDataReceivedTotalBytes = 0
        self.__receivePeriodRunningTotal = 0
        self.__jitterRunningtotal = 0
        self.__packet_last_seen_received_timestamp = datetime.timedelta()
        self.__packetCounterTransmittedTotal = 0# Will be populated by incoming isptest header data
        self.__streamTransmitterTxRateBps = 0  # Will be populated by incoming isptest header data
        self.__txStreamTimeToLive = 0 # Will be populated by incoming isptest header data
        self.__rxTTL = None # The most recent TTL value from the IP Header (that conveyed the Rtp packet)
        self.__latestReceivedRtpPacket = None   # A copy of the most recently received Rtp packet (populated by __queueReceiverThread)

        # Counter to be used by __calculateJitter()
        # self.sumOfJitter_1s = 0

        # No of events to keep before purging self.__eventList = []
        # self.historicEventsLimit = Registry.rtpReceiveStreamHistoricEventsLimit
        self.__stats["glitch_Event_Trigger_Threshold_packets"]= glitchEventTriggerThreshold
        self.__stats["packet_first_packet_received_timestamp"] = datetime.timedelta()
        self.__stats["packet_last_seen_received_timestamp"] = datetime.timedelta()
        self.__stats["packet_counter_1S"] = 0
        self.__stats["packet_data_received_1S_bytes"] = 0
        self.__stats["packet_data_received_total_bytes"] = 0
        self.__stats["packet_payload_size_mean_1S_bytes"] = 0
        self.__stats["packet_counter_received_total"] = 0
        self.__stats["packet_counter_transmitted_total"] = 0 # Will be populated by incoming isptest header data
        self.__stats["stream_time_elapsed_total"] = datetime.timedelta()
        self.__stats["packet_instantaneous_receive_period_uS"] = 0
        self.__stats["packet_mean_receive_period_uS"] = 0
        self.__stats["packet_instantaneous_ttl"] = None
        self.__stats["packet_ttl_decrement_count"] = None # Contains the difference in IP ttl value between at the start
                                                            # (if known) and at the point of arrival
        self.aggregateSumOfTimeDeltas = 0  # Used to calculate self.__stats["packet_mean_receive_period_uS"]

        # Aggregate Glitch counters
        self.__glitch_glitches_ignored_counter = 0
        self.__stats["glitch_glitches_ignored_counter"] = 0
        self.__stats["glitch_packets_lost_total_percent"] = 0
        self.__stats["glitch_packets_lost_total_count"] = 0
        self.__stats["glitch_packets_lost_per_glitch_mean"] = 0
        self.__stats["glitch_packets_lost_per_glitch_min"] = 0
        self.__stats["glitch_packets_lost_per_glitch_max"] = 0
        self.__glitch_counter_total_glitches = 0
        self.__stats["glitch_counter_total_glitches"] = 0
        self.__stats["glitch_worst_glitches_list"] = [] # A maintained list of the summaries of the top n worst glitches

        # Keeps a count of all events recorded against this RtpReceiveStream
        self.__stats["stream_all_events_counter"] = 0

        ######## Moving glitch counters
        # Array to hold a list of glitch conter defintions of the form [name, duration_s, no of sampling periods
        movingGlitchCounterDefinitions = [
            ["historic_glitch_counter_last_10Sec", 10, 1],      # 10 second duration, 1 second sampling period
            ["historic_glitch_counter_last_1Min", 60, 10],      # 1 min duration, 10 second sample period
            ["historic_glitch_counter_last_10Min", 600, 60],    # 10 min duration, 1 minute sample period
            ["historic_glitch_counter_last_1Hr", 3600, 600],    # 1hr duration, 10 minute sample period
            ["historic_glitch_counter_last_24Hr", 86400, 3600]  # 24hr duration, 1hr sample period
        ]

        # Array to store (any number of) moving glitch counters defined in movingGlitchCounterDefinitions[]
        self.movingGlitchCounters = []
        # Now create the glitch counters themselves and also the stats[] keys to hold the results
        # Each counter yields two results, an overall counter and also containing the
        # distribution of events across each sample
        # Iterate over movingGlitchCounterDefinitions [] to create the counter and associated stats keys
        for mc in movingGlitchCounterDefinitions:
            name = mc[0]
            duration = mc[1]
            noOfSamples = mc[2]
            # Create the counter
            self.movingGlitchCounters.append(MovingTotalEventCounter(name,duration,noOfSamples))
            # Create the stats keys to store the results
            self.__stats[name] = 0  # moving total
            self.__stats[name + "_events"] = [] # This key holds a list containing the distribution of events across each sample


        # define timedelta object to store an aggregate of of Glitch length
        self.__stats["glitch_length_total_time"] = datetime.timedelta()
        self.__stats["glitch_most_recent_timestamp"] = datetime.timedelta()
        self.__stats["glitch_most_recent_eventNo"] = None   # Captures the event no of the most recent glitch
                                                            # so it can be directly recalled from the eventsList
        self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.timedelta()
        self.__stats["glitch_mean_time_between_glitches"] = datetime.timedelta()
        self.__stats["glitch_mean_glitch_duration"] = datetime.timedelta()
        self.__stats["glitch_max_glitch_duration"] = datetime.timedelta()
        self.__stats["glitch_min_glitch_duration"] = datetime.timedelta()
        # self.sumOfTimeElapsedSinceLastGlitch = datetime.timedelta()
        self.__stats["sumOfTimeElapsedSinceLastGlitch"] = datetime.timedelta() # The sum total of the gaps *between* the glitches
                                                                                # Think of it as the lengths of the fences between
                                                                                # the fenceposts, (if a glitch is the fencepost)
        # self.sumOfGlitchDurations = datetime.timedelta()

        # Jitter counters
        self.__stats["jitter_min_uS"] = 0
        self.__stats["jitter_max_uS"] = 0
        self.__stats["jitter_range_uS"] = 0
        # self.__stats["jitter_instantaneous"] = 0
        self.__stats["jitter_mean_1S_uS"] = 0
        self.__stats["jitter_mean_10S_uS"] = 0
        self.__stats["jitter_long_term_uS"] = 0
        self.jitter_min_uS = 0
        self.jitter_max_uS = 0
        self.jitter_range_uS = 0

        # % ratio of 1S Jitter_uS to packet_mean_receive_period_uS that will trigger an excessJitterEvent
        # self.__stats["jitter_excessive_alarm_threshold_percent"] = \
        #     Registry.rtpReceiveStreamJitterExcessiveAlarmThresholdPercent
        # self.excessJitterThresholdFactor = (self.__stats["jitter_excessive_alarm_threshold_percent"] / 100.0)

        # No of seconds to inhibit an excessive jitter alarm
        self.__stats["jitter_alarm_event_timeout_S"] = 2
        self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = datetime.timedelta()
        self.__stats["jitter_time_of_last_excess_jitter_event"] = datetime.timedelta()
        self.__stats["jitter_excess_jitter_events_total"] = 0
        self.__stats["jitter_mean_time_between_excess_jitter_events"] = datetime.timedelta()
        # self.sumOfTimeElapsedSinceLastExcessJitterEvents = datetime.timedelta()
        self.__stats["sumOfTimeElapsedSinceLastExcessJitterEvents"] = datetime.timedelta()

        # IPRoutingChange traceroute stats
        self.__stats["route_time_elapsed_since_last_route_change_event"] = datetime.timedelta()
        self.__stats["route_time_of_last_route_change_event"] = datetime.timedelta()
        self.__stats["route_change_events_total"] = 0
        self.__stats["route_mean_time_between_route_change_events"] = datetime.timedelta()
        # self.sumOfTimeElapsedSinceLastRouteChange = datetime.timedelta()
        self.__stats["sumOfTimeElapsedSinceLastRouteChange"] = datetime.timedelta()

        # Ip routing Rx TTL stats
        self.__stats["route_time_elapsed_since_last_TTL_change_event"] = datetime.timedelta()
        self.__stats["route_time_of_last_TTL_change_event"] = datetime.timedelta()
        self.__stats["route_TTl_change_events_total"] = 0
        self.__stats["route_mean_time_between_TTl_change_events"] = datetime.timedelta()
        # self.sumOfTimeElapsedSinceLastRxTTLChange = datetime.timedelta()
        self.__stats["sumOfTimeElapsedSinceLastRxTTLChange"] = datetime.timedelta()

        # Amount of time to elapse before a lossOfStream alarm event is triggered
        self.lossOfStreamAlarmThreshold_s = Registry.lossOfStreamAlarmThreshold_s

        # Amount of time to elapse before a stream is believed completely dead (and automatically
        # destroyed)
        self.streamIsDeadThreshold_s = Registry.streamIsDeadThreshold_s
        # Create a flag to signal when the stream is believed dead (is therefore scheduled to delete itself)
        # self.believedDeadFlag = False

        # Before starting the receive threads, check to see if this is a 'reconstructed stream' with historic values
        # If so, copy the historic values into the _stats{}, eventsList[] and other counters before the threads are launched
        streamsSuccessfullyRecreated = False
        try:
            if restoredStreamFlag:
                # Populate self._stats{}
                if historicStatsDict is not None:
                    # Confirm that the inported stats{} contains identical keys to that of self.__stats{}
                    # diff = set(historicStatsDict.keys()) - set(self.__stats.keys())
                    diff = [] # a list to hold any missing keys *for debug purposes)
                    # Iterate over the self.__stats{} keys
                    for key in self.__stats.keys():
                        # Check that thew key is present in the imported dict
                        if not key in historicStatsDict:
                            # If it is missing, append the missing key to the diff list
                            diff.append(key)

                    if len(diff) == 0:
                        # If diff[] is empty, there are no missing keys in the historicStatsDict
                        # Utils.Message.addMessage("DBUG:RtpReceiveStream historicStatsDict stats keys match " +\
                        #                          str(len(historicStatsDict)) + ":" + str(len(self.__stats)) +\
                        #                          ", diff " + str(diff))
                        # Update stats{} dict
                        self.updateStats(historicStatsDict)
                        # Preset counters used by self.queueReceiverThread
                        self.packetCounterReceivedTotal = self.__stats["packet_counter_received_total"]
                        self.__packetDataReceivedTotalBytes = self.__stats["packet_data_received_total_bytes"]
                        self.__packetCounterTransmittedTotal = self.__stats["packet_counter_transmitted_total"]

                        if historicEventsList is not None:
                            self.updateEventsList(historicEventsList, replaceExistingList=True)
                        streamsSuccessfullyRecreated = True
                        Utils.Message.addMessage("Historic stream " + str(self.__stats["stream_syncSource"]) + " recreated")
                    else:
                        Utils.Message.addMessage("ERR:RtpReceiveStream historicStatsDict key differences " + str(diff) +\
                                                 " Aborting import of stats[] dict ")
                        streamsSuccessfullyRecreated = False

        except Exception as e:
            Utils.Message.addMessage("ERR:Stream " + str(self.__stats["stream_syncSource"]) +\
                                     "_stats{}, __eventList restoration error " + str(e))

        if restoredStreamFlag is False or\
                (restoredStreamFlag and streamsSuccessfullyRecreated):
            # Create a _consumeReceiveQueueThread
            self.queueReceiverThreadActiveFlag = True # Used as a signal to shut down the thread
            self.queueReceiverThread = threading.Thread(target=self.__queueReceiverThread, args=())
            self.queueReceiverThread.daemon = False
            self.queueReceiverThread.setName(str(self.__stats["stream_syncSource"]) + ":queueReceiverThread")
            self.queueReceiverThread.start()

            # Create a __samplingThread
            self.samplingThreadActiveFlag = True # Used as a signal to shut down the thread
            self.samplingThread = threading.Thread(target=self.__samplingThread, args=())
            self.samplingThread.daemon = False
            self.samplingThread.setName(str(self.__stats["stream_syncSource"]) + ":samplingThread")
            self.samplingThread.start()

            # Request an unused TCP port for the HTTP server to listen on
            self.tcpListenPort = Utils.TCPListenPortCreator.getNext()
            # Create an HTTP server thread
            try:
                Utils.Message.addMessage(f'DBUG: Creating httpServerThread for RtpReceiveStream:{self.__stats["stream_syncSource"]}')
                self.httpServerThread = threading.Thread(target=self.httpServerThreadCommon,
                                                         args=(self.tcpListenPort,
                                                               self.__stats["stream_syncSource"],
                                                               RtpReceiveStream.HTTPRequestHandler))
                self.httpServerThread.daemon = False
                self.httpServerThread.setName(f"{self.syncSourceIdentifier}:httpServerThread({self.tcpListenPort})")
                self.httpServerThread.start()

                # Verify that the http server is actually running, by attempting to connect it
                r = requests.get(f"http://127.0.0.1:{self.tcpListenPort}", timeout=1)
                r.raise_for_status()  # Will raise an Exception if there was a problem
                Utils.Message.addMessage(f"INFO:RTPReceiveStream({self.syncSourceIdentifier}) http server started on port {self.tcpListenPort}")


            except Exception as e:
                Utils.Message.addMessage(f'ERR:RtpReceiveStream.__init__() Couldn\'t create httpServerThread {self.syncSourceIdentifier}, {e}')

            # Now register the stream with the stream directory service
            # Note: If this fails, __samplingThread performs a 1 sec check to see if registration was successful,
            # and if not, attempts to re-add the stream
            try:
                # Create a dict to define the stream
                streamDefinition = {
                    "streamID": self.__stats["stream_syncSource"],
                    "httpPort": self.tcpListenPort,
                    "streamType": "RtpReceiveStream"
                }
                # Register the stream
                self.ctrlAPI.addToStreamsDirectory(streamDefinition)
            except Exception as e:
                Utils.Message.addMessage(
                    f'ERR:RtpReceiveStream.__init__() Initial stream Registration failed {self.syncSourceIdentifier}, {e}')

            # Finally, add this RtpReceiveStream object to rtpRxStreamsDictMutex
            # self.rtpRxStreamsDictMutex.acquire()
            # self.rtpRxStreamsDict[self.__stats["stream_syncSource"]] = self
            # self.rtpRxStreamsDictMutex.release()

            Utils.Message.postMessage(f"DBUG:RtpReceiveStream.__init__(): {self.__stats['stream_syncSource']}", tcpPort=self.controllerTCPPort)

    # Thread-safe method to update individual elements of the *live* (i.e unstable) traceroute hops list
    # It should be much faster than setTraceRouteHopsList (which has to copy the entire list)
    # It begins by comparing the lengths of the current stored list with the latest known length
    # If there is a discrepency, it will reinitialise the list to the new length
    # The arg 'hop' is zero indexed (so hop 0 is the first address in the hop list)
    def updateLiveTraceRouteHopsList(self, hopNo, noOfHops, hopAddr):
        if noOfHops > 0:
            self.liveTracerouteHopsListMutex.acquire()
            try:
                if len(self.liveTracerouteHopsList) == noOfHops:
                    pass
                else:
                    # If there is a discrepancy between the length the list and the latest known length
                    # Throw away the current list and initialise a new empty list
                    self.liveTracerouteHopsList = [None] * noOfHops
                self.liveTracerouteHopsList[hopNo] = hopAddr
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveStream.liveTracerouteHopsList() " + str(e))
            self.liveTracerouteHopsListMutex.release()

    # Thread-safe method to completely replace the *live* self.liveTracerouteHopsList[] with a new list
    def setLiveTraceRouteHopsList(self, newList):
        self.liveTracerouteHopsListMutex.acquire()
        # Copy the new list into the instance variable list
        self.liveTracerouteHopsList = deepcopy(newList)
        self.liveTracerouteHopsListMutex.release()
        # Update the timestamp
        self.liveTracerouteHopsListLastUpdated = datetime.datetime.now()

    # Thread-safe method to return a list of the *live* traceroute hops
    # Returns a tuple of the lastUpdatedTimestamp and the hops list
    def getLiveTraceRouteHopsList(self):
        self.liveTracerouteHopsListMutex.acquire()
        hl = deepcopy(self.liveTracerouteHopsList)
        self.liveTracerouteHopsListMutex.release()
        return self.liveTracerouteHopsListLastUpdated, hl


    class HTTPRequestHandler(Utils.HTTPRequestHandlerRTP):
        # Acts a repository for the GET endpoints provided by the HTTP API
        def apiGETEndpoints(self):
            # Access parent Rtp Stream object methods via server attribute
            parent = self.server.parentObject
            # A dictionary to map incoming GET URLs to an existing RtpGenerator method
            # The "args" key contains a lost with the preset values that will be passed to targetMethod() when
            # "optKeys" is a list of keys that  targetMethod will accept as a kwarg
            # that particular URL is requested
            # "contentType" is an additional key that specifies the type of data returned by targetMethod (if known)
            # The default behaviour of do_GET() will be to try and encode all targetMethod() return values as json
            # Some methods (eg getEventsListAsJson()) already return json, so there is no need to re-encode it
            # Additionally, the /report generation methods return plaintext so the "contentType" key is a means of
            # signalling to do_GET() how to handle the returned values
            getMappings = {
                "/": {"targetMethod": self.renderIndexPage, "args": [], "optKeys":[], "contentType": 'text/html'},
                "/debug": {"targetMethod": self.renderDebugPage, "args": [], "optKeys": []},
                "/stats": {"targetMethod": parent.getRtpStreamStats, "args": [],
                           "optKeys": ["keyIs", "keyContains", "keyStartsWith", "listKeys"]},
                "/report/traceroute": {"targetMethod": parent.generateTracerouteHistoryReport, "args": [],
                                       "optKeys": ["historyLength"], "contentType": 'text/plain'},
                "/report/summary": {"targetMethod": parent.generateReport, "args": [],
                                       "optKeys": ["eventFilterList"], "contentType": 'text/plain'},
                "/events/json": {"targetMethod": self.getEventsListAsJson, "args": [],
                                 "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent", "start", "end"],
                                 "contentType": 'application/json'},
                "/events/summary": {"targetMethod": self.getEventsSummaries, "args": [],
                                 "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent", "start", "end"]+\
                                    ["includeStreamSyncSourceID", "includeEventNo", "includeType","includeFriendlyName"]
                                 },
                "/events/csv": {"targetMethod": self.getEventsListAsCSV,
                                              "args": [],
                                              "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent",
                                                          "start", "end",]
                                },
                "/events/raw": {"targetMethod": self.getEventsListAsRaw,
                                "args": [],
                                "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent",
                                            "start", "end", ],
                                "contentType": 'application/python-pickle'
                                },
                "/traceroute": {"targetMethod": parent.getTraceRouteHopsList, "args": [], "optKeys": []},

                "/txrate/inc": {"targetMethod": self.remotelyControlTxStream, "args": ["/txrate/inc"], "optKeys": []},
                "/txrate/dec": {"targetMethod": self.remotelyControlTxStream, "args": ["/txrate/dec"], "optKeys": []},
                "/length/inc": {"targetMethod": self.remotelyControlTxStream, "args": ["/length/inc"], "optKeys": []},
                "/length/dec": {"targetMethod": self.remotelyControlTxStream, "args": ["/length/dec"], "optKeys": []},
                "/ttl/inc": {"targetMethod": self.remotelyControlTxStream, "args": ["/ttl/inc"], "optKeys": []},
                "/ttl/dec": {"targetMethod": self.remotelyControlTxStream, "args": ["/ttl/dec"], "optKeys": []},
                "/burst": {"targetMethod": self.remotelyControlTxStream, "args": ["/burst"], "optKeys": []},
            }
            return getMappings

        # Acts a repository for the POST endpoints provided by the HTTP API
        def apiPOSTEndpoints(self):
            # Access parent Rtp Stream object methods via server attribute
            parent = self.server.parentObject
            # A dictionary to map incoming POST URLs to an existing RtpGenerator method
            # The keys/values within the POST data will be mapped to the keys listed in "args"[] and "kwargs"[]
            # "reqKeys"[] lists the mandatory parameters expected by targetMethod()
            # "optKeys"[] lists the optional key/value parameters that targetMethod() will accept
            # {"url path":
            #   {
            #       "targetMethod":target method/function,
            #       "reqKeys":[required arg1, required arg2..],    <---*only* the values are passed to the mapped function
            #       "optKeys":[optional arg1, arg2..]    <------the key/value pairs are passed to the function
            #   }
            postMappings = {
                # "/url": {"targetMethod": None, "reqKeys": [], "optKeys": []},
                "/label": {"targetMethod": parent.setFriendlyName, "reqKeys": ["name"], "optKeys": []}
            }
            return postMappings

        # Acts a repository for the DELETE endpoints provided by the HTTP API
        def apiDELETEEndpoints(self):
            # Access parent Rtp Stream object methods via server attribute
            parent = self.server.parentObject
            deleteMappings = {"/delete": {"targetMethod": parent.killStream, "reqKeys": [], "optKeys": []}}
            return deleteMappings

        def getEventsListAsJson(self, **kwargs):
            try:
                # Get a handle on the RtpReceiveStream object
                rtpReceiveStream = self.server.parentObject
                # Get the events list - pass in the kwargs
                eventsList = rtpReceiveStream.getRTPStreamEventList(**kwargs)
                # Retrieve the event summaries as json
                eventsListJSON = [event.getJSON() for event in eventsList]

                # Create response by concatenating all the json events together
                concatenatedJSONList = "[" + ",".join(eventsListJSON) + "]"
                # Convert back to ASCII
                response = concatenatedJSONList.encode('utf-8')

                return response
            except Exception as e:
                return [str(e)]

        def getEventsSummaries(self, **kwargs):
            try:
                # Get a handle on the RtpStreamsResults object
                # This will fail if the object doesn;t exist yet
                rtpReceiveStream = self.server.parentObject

                # Prefilter the kwargs to allow only the keys accepted by getRTPStreamEventList()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                                ["filterList", "reverseOrder", "requestedEventNo", "recent", "start", "end"])
                # Get the events list - pass in the kwargs
                eventsList = rtpReceiveStream.getRTPStreamEventList(**filteredKwargs)

                # Prefilter the kwargs to allow only the keys accepted by Event.getSummary()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                    ["includeStreamSyncSourceID", "includeEventNo", "includeType", "includeFriendlyName"])
                # Create a list of Events summaries
                eventsListSummaries = [event.getSummary(**filteredKwargs) for event in eventsList]
                # Return the list
                return eventsListSummaries
            except Exception as e:
                return [str(e)]

        # Returns a list of Events as a list of csv strings
        def getEventsListAsCSV(self, **kwargs):
            try:
                # Get a handle on the RtpStreamsResults object
                # This will fail if the object doesn't exist yet
                rtpStreamResults = self.server.parentObject

                # Prefilter the kwargs to allow only the keys accepted by getRTPStreamEventList()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                                                                 ["filterList", "reverseOrder",
                                                                  "requestedEventNo",
                                                                  "recent", "start", "end"])
                # Get the events list - pass in the kwargs
                eventsList = rtpStreamResults.getRTPStreamEventList(**filteredKwargs)

                # Create a list of Events CSV exports
                eventsListAsCSV = [event.getCSV() for event in eventsList]
                # Return the list
                return eventsListAsCSV
            except Exception as e:
                return [str(e)]

        # Returns a list of events as pickles
        def getEventsListAsRaw(self, **kwargs):
            try:
                # Get a handle on the RtpStreamsResults object
                # This will fail if the object doesn't exist yet
                rtpStreamResults = self.server.parentObject

                # Prefilter the kwargs to allow only the keys accepted by getRTPStreamEventList()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                                                                 ["filterList", "reverseOrder",
                                                                  "requestedEventNo",
                                                                  "recent", "start", "end"])
                # Get the events list - pass in the kwargs
                eventsList = rtpStreamResults.getRTPStreamEventList(**filteredKwargs)

                # now pickle the list so that it can be sent via http
                pickledEventsList = pickle.dumps(eventsList)
                # Return the list
                return pickledEventsList

            except Exception as e:
                return [str(e)]



        # render HTML index page
        # Shown a list of available api endpoints
        def renderIndexPage(self):
            # Access parent Rtp Stream object via server attribute
            parent = self.server.parentObject
            try:
                syncSourceID = parent.syncSourceIdentifier
                response = f"<h1>Index page for {parent.__class__.__name__}:{syncSourceID}</h1>" \
                           f"{self.listEndpoints()}"
                return response
            except Exception as e:
                raise Exception(f"renderIndexPage() {parent.__class__.__name__}, {e}")

        # Display debug information
        def renderDebugPage(self):
            # Access parent RtpReceiveStream object via server attribute
            rtpRxStream = self.server.parentObject
            try:
                syncSourceID = rtpRxStream.syncSourceIdentifier
                stats = rtpRxStream.getRtpStreamStats()
                debugInfoDict = {
                    "syncSourceID": syncSourceID,
                    "type": rtpRxStream.__class__.__name__,
                    "packet_counter_transmitted_total": stats["packet_counter_transmitted_total"],
                    "stream_transmitter_txRate_bps": stats["stream_transmitter_txRate_bps"],
                    "Rx current queue size": rtpRxStream.rtpStreamQueueCurrentSize,
                    "Rx max queue size": rtpRxStream.rtpStreamQueueMaxSize,
                    "Rx Queue packets extracted": rtpRxStream.packetCounterReceivedTotal,
                    "Active Threads": Utils.listCurrentThreads(asList=True)
                }
                return debugInfoDict
            except Exception as e:
                raise Exception(f"renderDebugPage() {rtpRxStream.__class__.__name__}, {e}")





        # Sends a remote control message to an associated RtpGenerator
        def remotelyControlTxStream(self, controlMessage):
            # Access parent Rtp Stream object via server attribute
            rtpStream = self.server.parentObject
            syncSourceID = None
            try:
                syncSourceID = rtpStream.syncSourceIdentifier
                rtpStream.sendControlMessageToTransmitter({"syncSourceID": syncSourceID,
                                                                  "source": "Receiver",
                                                                  "type": controlMessage})
                Utils.Message.addMessage(f"DBUG:remotelyControlTxStream:{syncSourceID},  controlMessage: {controlMessage},")
            except Exception as e:
                Utils.Message.addMessage(f"ERR:RtpReceiveStream.HTTPRequestHandler.remotelyControlTxStream ({syncSourceID}),"\
                                         f" controlMessage{controlMessage}")
    # # Getter method for self.resultsTxQueue
    # def getResultsTxQueue(self):
    #     return self.resultsTxQueue
    #
    # # Setter method for self.resultsTxQueue (tests the incoming type, but doesn't validate it)
    # def setResultsTxQueue(self, newResultsTxQueue):
    #     if type(newResultsTxQueue) == SimpleQueue:
    #         self.resultsTxQueue = newResultsTxQueue
    #         Utils.Message.addMessage("DBUG:RtpReceiveStream.setResultsTxQueue() (stream " + \
    #                                  str(self.__stats["stream_syncSource"]) + " updated")
    #         return True
    #     else:
    #         return False

    # Method to destroy this object
    # Caller is an optional field to allow the method to check where the call is coming from
    # This is important because it calls join() on threads to make sure that they've shut down
    # A thread can't call join() on itself (it will block forever) so we need to check
    # Since __samplingThread calls kill() when the autoremove stream is triggered, this is a real danger
    def killStream(self, caller=None):
        # Kill the  __queueReceiverThread associated with this receive stream
        self.queueReceiverThreadActiveFlag = False

        self.queueReceiverThread.join()
        Utils.Message.addMessage("DBUG: self.queueReceiverThread.join() complete for " + str(self.__stats["stream_syncSource"]))

        # Kill the __samplingThread associated with this stream
        self.samplingThreadActiveFlag = False
        # Test to see if the kill() method is being called by the object itself
        try:
            if caller is self:
                # If the object is killing 'itself' from the same thread we're trying to join()
                # from it will block indefintely. This is bad!
                Utils.Message.addMessage("DBUG: ***** thread trying to join() itself ***** "  + str(self.__stats["stream_syncSource"]))
            else:
                # Otherwise, kill() is being called by another thread/object so we can safely wait on join()
                # to verify that the thread has ended
                self.samplingThread.join()
                Utils.Message.addMessage("DBUG: self.samplingThread.join() complete"  + str(self.__stats["stream_syncSource"]))
        except Exception as e:
            Utils.Message.addMessage("ERR:self.samplingThread.join() filed " + str(self.__stats["stream_syncSource"]) +\
                                     ", "+ str(e))

        # Kill the http server
        try:
            self.httpd.shutdown()
            Utils.Message.addMessage("DBUG:Closing http server for stream " + str(self.__stats["stream_syncSource"]))
        except Exception as e:
            Utils.Message.addMessage("ERR:Closing http server for stream " + str(self.__stats["stream_syncSource"]) + str(e))

        # Now attempt to remove the stream from the streams directory
        try:
            self.ctrlAPI.removeFromStreamsDirectory("RtpReceiveStream", self.__stats["stream_syncSource"])
        except Exception as e:
            Utils.Message.addMessage("ERR: RtpReceiveStream.killStream() removeFromStreamsDirectory() for stream " + \
                                     str(self.__stats["stream_syncSource"]) + ", " + str(e))

        # Now remove the Receive queue for this stream (from rxQueuesDict)
        try:
            del self.rxQueuesDict[self.syncSourceIdentifier]
        except Exception as e:
            Utils.Message.addMessage(f"ERR:RtpReceiveStream() del rxQueuesDict[{self.syncSourceIdentifier}], {e}")
        # # Finally remove this RtpReceiveStream (itself) from rtpRxStreamsDict
        # self.rtpRxStreamsDictMutex.acquire()
        # try:
        #     Utils.Message.addMessage("Removing RtpReceiveStream object " + str(self.__stats["stream_syncSource"]))
        #     del self.rtpRxStreamsDict[self.__stats["stream_syncSource"]]
        # except Exception as e:
        #     Utils.Message.addMessage("ERR: RtpReceiveStream.killStream() (remove from rtpRxStreamsDict{})" + str(self.__stats["stream_syncSource"]))
        # self.rtpRxStreamsDictMutex.release()


    # This method will parse the isptest header data (and update the instance variables accordingly)
    def __parseIsptestHeaderData(self, isptestHeaderData):
        try:
            # Determine what type of message this is
            # Note element 0 is the 'UniqueIDforISPTESTstreams'.
            # element 1 is the message type
            # The data itself is in the subsequent 6 bytes
            if isptestHeaderData[1] == 0:
                # This is a traceroute message
                # Extract the hop no. and the address octets isptestHeaderData[2] - isptestHeaderData[7]
                hopNo = isptestHeaderData[2]
                noOfHops = isptestHeaderData[3]

                # Elements 4-7 contain the octets of the traceroute hop IP address
                # hopAddr = [isptestHeaderData[4], isptestHeaderData[5],
                #            isptestHeaderData[6], isptestHeaderData[7]]
                # update the 'live' self.__tracerouteHopsList[] with the latest received address/hopNo
                self.updateLiveTraceRouteHopsList(hopNo, noOfHops, isptestHeaderData[4:8])
                # Element 8 contains the traceroute hops checksum generated by the transmitter
                # This allows the receiver to confirm that it has received a complete set of traceroute hops,
                # rather than just different parts of a traceroute
                self.tracerouteReceivedChecksum = isptestHeaderData[8]
                # Now pass the hop address to WhoisResolver.queryWhoisCache
                # to populate the whois cache for later use
                hopAddrAsString = str(isptestHeaderData[4]) + "." + str(isptestHeaderData[5]) + "." +\
                                  str(isptestHeaderData[6]) + "." + str(isptestHeaderData[7])
                Utils.WhoisResolver.queryWhoisCache(hopAddrAsString)

            elif isptestHeaderData[1] == 1:
                # This is a message containing the transmitter local address and also the UDP src port of the tx'd packets
                # Regenerate the 16bit UDP source port value from bytes 2 (the MSB) and 3 (the LSB)
                self.__stats["stream_transmitter_local_srcPort"] = (isptestHeaderData[2] << 8) | isptestHeaderData[3]
                # Create a an IP address string from the seperate octets
                self.__stats["stream_transmitter_localAddress"] = str(isptestHeaderData[4]) + "." + \
                                                                  str(isptestHeaderData[5]) + "." + \
                                                                  str(isptestHeaderData[6]) + "." + \
                                                                  str(isptestHeaderData[7])

            elif isptestHeaderData[1] == 2:
                # This is a message containing the transmitter destination address for the stream
                # Create a an IP address string from the seperate octets
                self.__stats["stream_transmitter_destAddress"] = str(isptestHeaderData[4]) + "." + \
                                                                  str(isptestHeaderData[5]) + "." + \
                                                                  str(isptestHeaderData[6]) + "." + \
                                                                  str(isptestHeaderData[7])

            elif isptestHeaderData[1] == 3:
                # This is a message containing version no information about the transmitter
                txVersionNo = str(isptestHeaderData[2]) + "." + str(isptestHeaderData[3])
                self.__stats["stream_transmitterVersion"] = float(txVersionNo)
                self.__stats["stream_transmitter_PID"] = struct.unpack_from("!L", bytes(isptestHeaderData[4:8]))[0]

            elif isptestHeaderData[1] == 4:
                # This is a message containing the intended tx rate of the stream (as an unsigned long, 4 bytes)
                try:
                    # Convert the 4 bytes back to an int
                    self.__streamTransmitterTxRateBps = struct.unpack_from("!L", bytes(isptestHeaderData[4:8]))[0]
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__parseIsptestHeaderData, msg type 4 " + str(e))

            elif isptestHeaderData[1] == 5:
                # This is a message containing a count of the tx'd packets (as an unsigned long, 4 bytes)
                try:
                    # Convert the 4 bytes back to an int
                    self.__packetCounterTransmittedTotal = struct.unpack_from("!L", bytes(isptestHeaderData[4:8]))[0]
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__parseIsptestHeaderData, msg type 5 " + str(e))

            elif isptestHeaderData[1] == 6:
                # This is a message containing the stream time to live (as an signed long, 4 bytes)
                try:
                    # Convert the 4 bytes back to a signed int
                    self.__txStreamTimeToLive = struct.unpack_from("!i", bytes(isptestHeaderData[4:8]))[0]
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__parseIsptestHeaderData, msg type 6 " + str(e))

            elif isptestHeaderData[1] == 7:
                # This is a message containing the return loss (as a float  , 4 bytes)
                try:
                    # Convert the 4 bytes back to a float
                    self.__stats["stream_transmitter_return_loss_percent"] = \
                        struct.unpack_from("!f", bytes(isptestHeaderData[4:8]))[0]
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__parseIsptestHeaderData, msg type 6 " + str(e))

        except Exception as e:
            Utils.Message.addMessage("DBUG:__RtpReceiveStream.__pasrseIsptestHeader " + str(e))

    # This method examines the payload of the RTP packet to see if it's been sent by an instance of an isptest TRANSMITTER
    # It will then split off the numerical data part and the 'friendly name' string for the stream
    # The numerical data part will be passed to __parseIsptestHeaderData to decode the actual messages within
    def __extractIsptestHeaderData(self, rtpPayload):
        # Extract ispheader data from first packet in this batch
        # Calculate the split between the numerical data and the friendly name
        numericalHeaderDataLength = self.ISPTEST_HEADER_SIZE - self.maxNameLength
        try:
            # substring the part of the data holding the numerical values
            isptestHeaderDataStruct = rtpPayload[:numericalHeaderDataLength]
            # substring the part of the data holding the friendly name of the stream
            isptestHeaderDataFriendlyName = str(rtpPayload[numericalHeaderDataLength:].decode('utf-8'))
            # unpack the values from the struct
            isptestHeaderData = struct.unpack("!HBBBBBBBB", isptestHeaderDataStruct)
            # Utils.Message.addMessage("INFO: Decoded header: " + str(isptestHeaderData) + ", " + str(isptestHeaderDataFriendlyName))
            # Check to see if we've managed to unpack the data
            if len(isptestHeaderData) > 0:
                # Check to see that if this a stream sent by an instance of isptest
                if isptestHeaderData[0] == RtpGenerator.getUniqueIDforISPTESTstreams():
                    # If so, make use the friendly name field to name this receive stream
                    self.__stats["stream_friendly_name"] = isptestHeaderDataFriendlyName
                    # Now decode the messages contained within the isptest header
                    self.__parseIsptestHeaderData(isptestHeaderData)
                else:
                    pass
        except Exception as e:
            pass
            # Utils.Message.addMessage("DBUG: Decoded header: " + str(e) + str(self.rtpStream[0].isptestHeaderData))

    # This thread updates the 1sec averages, moving counters and also housekeeps
    def __samplingThread(self):

        # Puts the current stream stats and events (the results) in a queue to be transmitted back to the transmitter
        # (if the transmitter is an instance of isptest)
        # Rather than sending the entire events list, we only send the last five events.
        # The correspoinding results receiver is able to ignore any events it has already received
        def addResultsToTxQueue(stats, eventsToBeSent, resultsTxQueue, destAddr, destPort):
            try:
                # Create a dictionary containing the stats and eventList data and pickle it (so it can be sent)
                msg = {"stats": stats, "eventList": eventsToBeSent}
                # pickledMessage = pickle.dumps(msg, protocol=2)
                pickledMessage = pickle.dumps(msg)
                # If compression is enabled, compress the message string before sending
                if Registry.rtpReceiveStreamCompressResultsBeforeSending:
                    pickledMessage = bz2.compress(pickledMessage)
                # add the pickled message to the txMessageQueue
                resultsTxQueue.put([pickledMessage, destAddr, destPort])

            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread.addResultsToTxQueue() " + str(e))

        # This function attempts to calculate the mean period between events (such as glitch, or jitter)
        # to provide a value of how often, on average, the event has occurred
        # To give a glimpse into the future, it will also take into account the time elapsed since the
        # last event happened. Once this elapsed time is greater than the calculated mean of the time
        # between the events, it will also take this time period into account - in effect increasing the
        # average time between events
        def calculateMeanPeriodBetweenEvents(sumOfTimePeriodsBetweenEvents,
                                             timeElapsedSinceMostRecentEvent,
                                             totalNoOfEvents):
            try:
                # Calculate mean period between the events that have already happened
                actualPeriodBetweenEvents = sumOfTimePeriodsBetweenEvents / totalNoOfEvents
                # Now look to see if time elapsed since the last event is longer than the mean between events
                if timeElapsedSinceMostRecentEvent > actualPeriodBetweenEvents:
                    # This 'pretends' that a event has 'just happened' which will have the effect of increasing
                    # the apparent time between events. Therefore as time moves on, with no more events
                    # recorded, the 'mean period between events' will improve (i.e get larger)
                    meanPeriodBetweenEvents = (sumOfTimePeriodsBetweenEvents + timeElapsedSinceMostRecentEvent) / \
                                              (totalNoOfEvents + 1)
                    return meanPeriodBetweenEvents
                else:
                    # The time elapsed since the last event is less than the calculated actual mean.
                    # Therefore we ignore the effect of it, as it will only worsen the mean period
                    return actualPeriodBetweenEvents
            except Exception as e:
                Utils.Message.addMessage("RtpReceiveStream.__samplingThread.calculateMeanPeriodBetweenEvents() " + \
                                         str(e))
                return None

        Utils.Message.addMessage("DBUG: __samplingThread started for stream " + str(self.__stats["stream_syncSource"]))
        # Initialise variables to be used within the loop
        loopCounter = 0
        # Initialise variables to hold final calculated values
        meanRxPeriod_1Sec = 0
        meanJitter_1Sec = 0
        meanJitter_10Sec = 0
        rxBps = 0
        meanPacketLengthBytes = 0

        elapsedTime = datetime.timedelta()
        # Counter used to determine whether a stream has been lost or should be purged (because it has been lost forever)
        secondsWithNoBytesRxdTimer = 0
        # # This flag will go high once a stream is believed lost
        # self.__stats["lossOfStreamFlag"] = False
        # Records the timestamp of the most recent StreamLost Event
        # lossOfStreamEventTimestamp = datetime.timedelta()

        # This flag will go high when a stream is declared dead
        # streamIsDeadFlag = False

        # Stores the previous long-term jitter value.
        jitterLongterm_uS = 0

        # Stores the prev packets received count value. Required for calculating averages over particular periods
        prevPacketsReceivedCount = 0
        latestPacketsReceivedCount = 0

        # Create circular buffer for rx bytes/sec counter (using 200mS windows, so buffersize of 5
        rxBpsBuffer = deque(maxlen=5)
        prevRxdBytesCount = 0

        # Create a circular buffer for the average receive period
        rxPeriodBuffer = deque(maxlen=5)
        prevRxPeriodCount = 0

        # Create circular buffer for the no of packets per second
        packetsPerSecondBuffer = deque(maxlen=5)
        prevPacketsPeriodCount = 0

        latestRxdBytesCount = 0
        latestReceivePeriodCount = 0

        # Create circular buffer for jitter calculations
        # For 1 sec jitter calculation
        jitterPerSecBuffer = deque(maxlen=5)
        latestJitterPeriodCount = 0
        prevJitterPeriodCount = 0
        # For 10 sec jitter calculation
        jitter10SecBuffer = deque(maxlen=10)

        # Stores the previous traceroute hops list. Used to detect route changes
        prevHopsList = []
        # Stores the most recent hops list
        hopsList = []
        # This flag will be set high by any changes detected in the rxTTL value.
        # rxTTL will change immediately, but it takes time for any traceroute hopslist changes to be transmitted
        # Therefore we need a mechanism to to tell the route change detection to expect a hopList change, and also
        # until that new list is picked up, ignore the prevRxTTl and rxTTL values.
        # Once the new hopList has been received the detection routine will acknowledge the change and clear the
        # hopsListChangeExpected flag. At this point it will resume monitoring prev rxTTl and rxTTL
        hopsListChangeExpected = False
        # Stores the previous rx TTL value - Used to detect route changes
        prevRxTTL = None
        # Stores previous source address and UDP port. Used to detect changes
        prevSrcAddr = None
        prevSrcPort = None
        # Stores previous destination address and UDP port. Used to detect changes
        prevDestAddr = None
        prevDestPort = None

        # Infinite loop
        while self.samplingThreadActiveFlag:
            time.sleep(0.2)
            try:
                ## Take snapshots of latest running counter values
                # Snapshot latest count of packets received (for averages)
                latestPacketsReceivedCount = self.packetCounterReceivedTotal
                self.__stats["packet_counter_received_total"] = latestPacketsReceivedCount
                # Snapshot latest received bytes value (for rx bps calculation)
                latestRxdBytesCount = self.__packetDataReceivedTotalBytes
                self.__stats["packet_data_received_total_bytes"] = latestRxdBytesCount
                # Snapshot latest receive period count
                latestReceivePeriodCount = self.__receivePeriodRunningTotal
                # Snapshot latest jitter count
                latestJitterPeriodCount = self.__jitterRunningtotal

                # If __latestReceivedRtpPacket is set, update the snapshots
                if type(self.__latestReceivedRtpPacket) == RtpData:
                    # Snapshot last packet seen timestamp (if it exists)
                    self.__stats["packet_last_seen_received_timestamp"] = self.__latestReceivedRtpPacket.timestamp
                    # Snapshot latest packet IP TTL value
                    self.__stats["packet_instantaneous_ttl"] = self.__latestReceivedRtpPacket.rxTTL
                    # self.__stats["packet_instantaneous_ttl"] = 10
                    # Snapshot latest src address
                    self.__stats["stream_srcAddress"] = self.__latestReceivedRtpPacket.srcAddr
                    # Snapshot latest src port
                    self.__stats["stream_srcPort"] = self.__latestReceivedRtpPacket.srcPort
                    # Snapshot latest dest address
                    self.__stats["stream_rxAddress"] = self.__latestReceivedRtpPacket.destAddr
                    # Snapshot latest dest port
                    self.__stats["stream_rxPort"] = self.__latestReceivedRtpPacket.destPort

                # Snapshot packetCounterTransmittedTotal (packets Tx'd according to the transmitter
                self.__stats["packet_counter_transmitted_total"] = self.__packetCounterTransmittedTotal
                # Snapshot streamTransmitterTxRateBps (intended tx rate, according to the transmitter)
                self.__stats["stream_transmitter_txRate_bps"] = self.__streamTransmitterTxRateBps
                # Snapshot latest transmitter stream time to live
                self.__stats["stream_transmitter_TimeToLive_sec"] = self.__txStreamTimeToLive
            except Exception as e:
                Utils.Message.addMessage("ERR: RtpReceiveStream.__samplingThread snapshot stats " + str(e))


            try:
                ########### Calculate how many packets received in the latest 200mS period - required for 'mean' calculations
                # Special case for a 'restored stream' with no new incoming packets
                # Otherwise, the entire previous received packets would be used (erroneously) to calculate the packets/sec
                if prevPacketsReceivedCount == 0:
                    prevPacketsReceivedCount = latestPacketsReceivedCount
                # calculate packets received since the last count
                packetsReceivedThisPeriod = latestPacketsReceivedCount - prevPacketsReceivedCount
                # Store latest count for next time around the loop
                prevPacketsReceivedCount = latestPacketsReceivedCount

                ########### Calculate packets received per sec
                # Add the latest count of packets received (this period) to the buffer
                packetsPerSecondBuffer.append(packetsReceivedThisPeriod)
                # Sum the buffer to get packets received for the last second
                self.__stats["packet_counter_1S"] = sum(packetsPerSecondBuffer)

                ############ Calculate received bits per second
                # Special case for a 'restored stream' with no new incoming bytes
                # Otherwise, the entire previous recveived bytes would be used (erroneously) to calculate the Bps
                if prevRxdBytesCount == 0:
                    prevRxdBytesCount = latestRxdBytesCount
                # calculate bytes received since the last count
                RxdBytesCountThisPeriod = latestRxdBytesCount - prevRxdBytesCount
                # Snapshot the latest value for next time around the loop
                prevRxdBytesCount = latestRxdBytesCount
                # Append the bytes received this period to the rxBpsBuffer circular buffer
                rxBpsBuffer.append(RxdBytesCountThisPeriod)
                # Now sum the contents of rxBpsBuffer to get the latest rx rate in *bytes* per second
                # rxBps = rxBytesPerSec * 8
                self.__stats["packet_data_received_1S_bytes"] = sum(rxBpsBuffer)


                ########### Calculate elapsed time
                # Note. This is inhibited if streamIsDeadFlag is set
                if self.__stats["streamIsDeadFlag"] is False:
                    self.__stats["stream_time_elapsed_total"] = datetime.datetime.now() - \
                                                            self.__stats["packet_first_packet_received_timestamp"]

                if packetsReceivedThisPeriod > 0:
                    ########### Calculate mean packet length (1 sec)
                    meanPacketLengthBytes = int(RxdBytesCountThisPeriod / packetsReceivedThisPeriod)
                    self.__stats["packet_payload_size_mean_1S_bytes"] = meanPacketLengthBytes

                    ########## Calculate mean receive period (1 sec)
                    # Calculate difference since last count
                    rxPeriodDiff = latestReceivePeriodCount - prevRxPeriodCount
                    # Snapshot the latest value for next time around the loop
                    prevRxPeriodCount = latestReceivePeriodCount
                    # Calculate mean for this 200mS period
                    meanRxPeriod = rxPeriodDiff / packetsReceivedThisPeriod
                    # Add the calculated mean value to the rxPeriodBuffer
                    rxPeriodBuffer.append(meanRxPeriod)
                    # Calculate a 1 second mean by taking a mean of all the 200mS periods
                    sumOf200msMeanRxPeriods = 0
                    for x in rxPeriodBuffer:
                        sumOf200msMeanRxPeriods += x
                    meanRxPeriod_1Sec = int(sumOf200msMeanRxPeriods / 5)
                    self.__stats["packet_mean_receive_period_uS"] = meanRxPeriod_1Sec

                    ########### Calculate mean jitter (1 sec)
                    # Calculate difference since last count
                    jitterPeriodDiff = latestJitterPeriodCount -  prevJitterPeriodCount
                    # Snapshot the latest value for next time around the loop
                    prevJitterPeriodCount = latestJitterPeriodCount
                    # Calculate the mean jitter for this 200mS period
                    meanJitterPeriod = jitterPeriodDiff / packetsReceivedThisPeriod
                    # Add the calculated mean value to the jitterPerSecBuffer buffer
                    jitterPerSecBuffer.append(meanJitterPeriod)
                    # Calculate a 1 second mean by taking a mean of all the 200mS periods
                    sumOf200msMeanJitter = 0
                    for x in jitterPerSecBuffer:
                        sumOf200msMeanJitter += x
                    meanJitter_1Sec = int(sumOf200msMeanJitter / 5)
                    self.__stats["jitter_mean_1S_uS"] = meanJitter_1Sec

                    ########## Calculate long-term jitter -- self.__stats["jitter_long_term_uS"]
                    jitterLongterm_uS = int(self.__jitterRunningtotal / self.packetCounterReceivedTotal)
                    self.__stats["jitter_long_term_uS"] = jitterLongterm_uS

                    ########## calculate jitter range (in receive queue, not here)
                    self.__stats["jitter_min_uS"] = self.jitter_min_uS
                    self.__stats["jitter_max_uS"] = self.jitter_max_uS
                    self.__stats["jitter_range_uS"] = self.jitter_range_uS

            except Exception as e:
                Utils.Message.addMessage("ERR: RtpReceiveStream.__samplingThread 0.2 sec loop" + str(e))

            if loopCounter % 5 == 0:
                ######## 1 second counter
                # Update the 'last updated' timestamp
                self.__stats["lastUpdatedTimestamp"] = datetime.datetime.now()

                try:
                    ########### Calculate 10sec jitter mean -- self.__stats["jitter_mean_10S_uS"] = 0
                    # Add the latest 1sec jitter mean to the meanJitter_1Sec circular buffer
                    jitter10SecBuffer.append(meanJitter_1Sec)
                    # Calculate mean value of jitter10SecBuffer contents
                    sumOfjitter10SecBuffer = sum(jitter10SecBuffer)
                    self.__stats["jitter_mean_10S_uS"] = int(sumOfjitter10SecBuffer / 10)
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread calc 10 sec jitter " + str(e))


                try:
                    ########### Update Mean Jitter averages
                    if (self.__stats["jitter_excess_jitter_events_total"] > 0) and (self.__stats["streamIsDeadFlag"] is False):

                        ########### Now update the self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] timer
                        self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = \
                            datetime.datetime.now() - self.__stats["jitter_time_of_last_excess_jitter_event"]


                        ########### Calculate mean TimeBetween Excess Jitter Events (jitter Period)
                        self.__stats["jitter_mean_time_between_excess_jitter_events"] = \
                            calculateMeanPeriodBetweenEvents(self.__stats["sumOfTimeElapsedSinceLastExcessJitterEvents"],
                                                             self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"],
                                                             self.__stats["jitter_excess_jitter_events_total"])
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread Jitter means " + str(e))

                try:
                    ########## Calculate Glitch stats
                    # (But only if there has actually been a glitch in the past to measure against) AND stream is alive
                    if (self.__stats["glitch_counter_total_glitches"] > 0) and (self.__stats["streamIsDeadFlag"] is False):
                        ########## Calculate time elapsed since last glitch
                        # Calculate new value
                        self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.datetime.now() - self.__stats[
                            "glitch_most_recent_timestamp"]

                        ########## Calculate Glitch mean averages -
                        ########## Calculate mean time between glitches (glitch period)
                        self.__stats["glitch_mean_time_between_glitches"] = \
                            calculateMeanPeriodBetweenEvents(self.__stats["sumOfTimeElapsedSinceLastGlitch"],
                                                             self.__stats["glitch_time_elapsed_since_last_glitch"],
                                                             self.__stats["glitch_counter_total_glitches"])
                        ########## Calculate mean glitch duration
                        self.__stats["glitch_mean_glitch_duration"] = \
                            self.__stats["glitch_length_total_time"] / self.__stats[
                                "glitch_counter_total_glitches"]
                        ########## Calculate mean packet loss per glitch
                        self.__stats["glitch_packets_lost_per_glitch_mean"] = \
                            math.ceil(self.__stats["glitch_packets_lost_total_count"] / self.__stats[
                                "glitch_counter_total_glitches"])
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread Glitch stats " + str(e))

                try:
                    ######### Calculate % packet loss
                    if self.__stats["packet_counter_received_total"] > 0:
                        totalExpectedPackets = self.__stats["packet_counter_received_total"] + \
                                               self.__stats["glitch_packets_lost_total_count"]
                        # Guard against divide by zero errors
                        if totalExpectedPackets > 0:
                            self.__stats["glitch_packets_lost_total_percent"] = \
                                self.__stats["glitch_packets_lost_total_count"] * 100 / totalExpectedPackets
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread % packet loss " + str(e))

                try:
                    ######### Now update moving glitch counters by iterating over the self.movingGlitchCounters array
                    # firstly recalculate, then generate stats keys automatically for any moving totals counters
                    # within self.movingGlitchCounters
                    for x in self.movingGlitchCounters:
                        # Force the moving counters to increment their timers and recalculate totals
                        x.recalculate()
                        name, movingTotal, events = x.getResults()
                        # Update the stats keys using the name field of the moving glitch counter
                        self.__stats[name] = movingTotal # This key holds the running total
                        self.__stats[name + "_events"] = events # This key holds a list containing the distribution of events across each sample
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread update moving glitch counters " + str(e))

                try:
                    ######## Get latest version of the worst glitches list (as text), and update to the __stats[] dict
                    self.__stats["glitch_worst_glitches_list"] = self.getWorstGlitches(returnSummaries=True)
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread get worst glitches list " + str(e))

                try:
                    ######## Confirm that some packets have been received this second (used for the loss of signal alarm)
                    # If not, increment the timer
                    if self.__stats["packet_counter_1S"] > 0:
                        # Packets have been received so clear the timer
                        secondsWithNoBytesRxdTimer = 0
                        # If lossOfStreamFlag was previously True but is about to be cleared, create a StreamResumed Event to
                        # signify that the stream has restarted
                        if self.__stats["lossOfStreamFlag"] == True:
                            # Create a 'stream resumed' event
                            try:
                                streamResumedEvent = StreamResumed(self.__stats, self.__stats["lossOfStreamEventTimestamp"])
                                # Append the event to the events list
                                self.__eventList.append(streamResumedEvent)
                                # Increment the Event counter
                                self.__stats["stream_all_events_counter"] += 1
                                # Display a message
                                Utils.Message.addMessage(
                                    streamResumedEvent.getSummary(includeStreamSyncSourceID=False)['summary'])
                            except Exception as e:
                                Utils.Message.addMessage(
                                    "ERR:RtpReceiveStream.__samplingThread add streamResumed Event  " + str(e))

                        # Clear the flag so another StreamLost Event can be generated
                        self.__stats["lossOfStreamFlag"] = False
                        # Clear streamIsDeadFlag
                        self.__stats["streamIsDeadFlag"] = False
                    else:
                        # No packets received this period so increment the timer
                        secondsWithNoBytesRxdTimer += 1
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread check packets per sec " + str(e))

                try:
                    ######## Check to see if we've lost the stream (but only do this once, via the lossOfStreamFlag)
                    if secondsWithNoBytesRxdTimer >= Registry.lossOfStreamAlarmThreshold_s and not self.__stats["lossOfStreamFlag"]:
                        # Set flag (this Event can only fire again if the flag is subsequently cleared)
                        self.__stats["lossOfStreamFlag"] = True
                        # Add event to the list (but only do this once)
                        streamLostEvent = StreamLost(self.__stats)
                        self.__eventList.append(streamLostEvent)
                        # Increment the all_events counter
                        self.__stats["stream_all_events_counter"] += 1
                        Utils.Message.addMessage(streamLostEvent.getSummary(includeStreamSyncSourceID=False)['summary'])
                        # Snapshot the time of the latest StreamLost Event (this is consumed by the StreamResumed Event)
                        self.__stats["lossOfStreamEventTimestamp"] = datetime.datetime.now()
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread detect loss of stream " + str(e))

                ######## Detect changes in the source address/port
                try:
                    # Set initial values
                    if prevSrcAddr is None:
                        prevSrcAddr = self.__stats["stream_srcAddress"]
                    if prevSrcPort is None:
                        prevSrcPort = self.__stats["stream_srcPort"]

                    # Test for changes of either source IP address or port
                    if (prevSrcAddr != self.__stats["stream_srcAddress"]) or (prevSrcPort != self.__stats["stream_srcPort"]):
                        # Src has changed, create a SrcAddressChange Event
                        srcAddressChange = SrcAddrChange(self.__stats, prevSrcAddr, prevSrcPort,
                                                            self.__stats["stream_srcAddress"],
                                                            self.__stats["stream_srcPort"])
                        # Add the event to the event list
                        self.__eventList.append(srcAddressChange)
                        # # Increment the all_events counter
                        self.__stats["stream_all_events_counter"] += 1
                        # # Post a message
                        Utils.Message.addMessage(
                            srcAddressChange.getSummary(includeStreamSyncSourceID=False)['summary'])

                    # Now snapshot latest values
                    prevSrcAddr = self.__stats["stream_srcAddress"]
                    prevSrcPort = self.__stats["stream_srcPort"]

                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread detect source address/port changes " + str(e))

                ######## Detect changes in the dest address/port
                try:
                    # Set initial values
                    if prevDestAddr is None:
                        prevDestAddr = self.__stats["stream_rxAddress"]
                    if prevDestPort is None:
                        prevDestPort = self.__stats["stream_rxPort"]

                    # Test for changes of either source IP address or port
                    if (prevDestAddr != self.__stats["stream_rxAddress"]) or (prevDestPort != self.__stats["stream_rxPort"]):
                        # Dest has changed, create a DestAddressChange Event
                        destAddressChange = DestAddrChange(self.__stats, prevDestAddr, prevDestPort,
                                                         self.__stats["stream_rxAddress"],
                                                         self.__stats["stream_rxPort"])
                        # Add the event to the event list
                        self.__eventList.append(destAddressChange)
                        # # Increment the all_events counter
                        self.__stats["stream_all_events_counter"] += 1
                        # # Post a message
                        Utils.Message.addMessage(
                            destAddressChange.getSummary(includeStreamSyncSourceID=False)['summary'])
                    # Now snapshot latest values
                    prevDestAddr = self.__stats["stream_rxAddress"]
                    prevDestPort = self.__stats["stream_rxPort"]
                except Exception as e:
                    Utils.Message.addMessage(
                        "ERR:RtpReceiveStream.__samplingThread detect dest address/port changes " + str(e))

                ######## Detect changes in the value of rxTTL
                try:
                    if self.__stats["packet_instantaneous_ttl"] != prevRxTTL:
                        # Change in the value of rxTTL detected
                        # # Get copy of the current 'live' hopslist
                        # lastUpdate, hopsList =  self.getTraceRouteHopsList()
                        # oldLen = len(hopsList)
                        # Utils.Message.addMessage("rxTTL change " + str(prevRxTTL) + ">>" + \
                        #                          str(self.__stats["packet_instantaneous_ttl"]))
                        # RxTTL change detected, create a new IPRoutingTTLChange Event
                        ipRoutingTTLChange = IPRoutingTTLChange(self.__stats, prevRxTTL, self.__stats["packet_instantaneous_ttl"])
                        # Add the event to the event list
                        self.__eventList.append(ipRoutingTTLChange)
                        # # Increment the all_events counter
                        self.__stats["stream_all_events_counter"] += 1
                        # Update the rx TTL stats
                        self.__stats["route_TTl_change_events_total"] += 1
                        self.__stats["route_time_of_last_TTL_change_event"] = ipRoutingTTLChange.timeCreated

                        # Take snapshot of new time delta and add to the sum of existing values (to calculate mean)
                        self.__stats["sumOfTimeElapsedSinceLastRxTTLChange"] \
                            += self.__stats["route_time_elapsed_since_last_TTL_change_event"]
                        # Since the rxTTl has changed, we can expect a subsequent change in the received hopslist
                        hopsListChangeExpected = True
                        # Flush the contents of the current hopsList because it's now been invalidated
                        # Utils.Message.addMessage("DBUG: hopsListChangeExpected.")
                        # self.setTraceRouteHopsList([])
                        # Post a message
                        Utils.Message.addMessage(ipRoutingTTLChange.getSummary(includeStreamSyncSourceID=False)['summary'])
                        # # Snapshot current rxTTL value
                        # prevRxTTL = self.__stats["packet_instantaneous_ttl"]

                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread detect rxTTL changes " + str(e))


                ########## Calculate rxTTL change stats
                try:
                    # (But only if there has actually been a second TTL change in the past to measure against)
                    # AND stream is alive
                    # Note: The initial route is considered as 'change 1' therefore is ignored and threshold is >=1
                    ####### Now update the self.__stats["route_time_elapsed_since_last_TTL_change_event"] timer
                    if (self.__stats["route_TTl_change_events_total"] > 0) and (self.__stats["streamIsDeadFlag"] is False):
                        self.__stats["route_time_elapsed_since_last_TTL_change_event"] = \
                            datetime.datetime.now() - self.__stats["route_time_of_last_TTL_change_event"]

                    ########### Calculate mean time between Rx TTL changes.
                    # Note: Ignore the first route change, because it's not really a 'change', just the initial value
                    if (self.__stats["route_TTl_change_events_total"] > 1) and (self.__stats["streamIsDeadFlag"] is False):
                        self.__stats["route_mean_time_between_TTl_change_events"] = \
                            calculateMeanPeriodBetweenEvents(self.__stats["sumOfTimeElapsedSinceLastRxTTLChange"],
                                                             self.__stats["route_time_elapsed_since_last_TTL_change_event"],
                                                             (self.__stats["route_TTl_change_events_total"] - 1))

                    # Utils.Message.addMessage("ttl  events " + str(self.__stats["route_TTl_change_events_total"]) + \
                    #         ", elapsed " + str(self.__stats["route_time_elapsed_since_last_TTL_change_event"].total_seconds()) +\
                    #                          ", period " + str(Utils.dtstrft(self.__stats["route_mean_time_between_TTl_change_events"])))

                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Calculate Rx TTL Change stats " + str(e) + ", " +\
                                             str(self.__stats["sumOfTimeElapsedSinceLastRxTTLChange"]))


                ######## Calculate no of IP hops according to rxTTL value Display current rxTTL
                # Only do this if the received packets were sent from an instance of isptest (because otherwise we
                # won't know what the starting ttl would have been)
                try:
                    if (self.__stats["packet_instantaneous_ttl"] is not None) and \
                            (self.__stats["stream_transmitterVersion"] > 0):
                        self.__stats["packet_ttl_decrement_count"] = \
                            Registry.rtpGeneratorUDPTxTTL - self.__stats["packet_instantaneous_ttl"]
                        # Compare
                        # Utils.Message.addMessage("rxTTL " + str(self.__stats["packet_instantaneous_ttl"]) + "(" +\
                        #                          str(self.__stats["packet_ttl_decrement_count"]) +")")
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Calculate ttl decrements " + str(e))

                ######## Detect route changes using traceroute hops list (and rxTTL if available)
                # Also update the 'stable' self.tracerouteHopsList if the checksum has been validated
                try:
                    # Get the current 'live' hops list
                    lastUpdate, hopsList = self.getLiveTraceRouteHopsList()
                    # Calculate checksum of current hops list. Does it match that of self.tracerouteReceivedChecksum?
                    # if it doesn't, that suggests we have an incomplete or jumbled up hopsList
                    # This could happen if the traceroute hops have jjst changed but the transmitter bitrate is slow
                    # leading to a long time for the entire traceroute hops list to be transmitted
                    localTracerouteChecksum = self.createTracerouteChecksum(hopsList)
                    if localTracerouteChecksum == self.tracerouteReceivedChecksum:
                        # If the checksum's match, we can be reasonably confident our hopsList data is valid
                        # Utils.Message.addMessage("Checksums match local " +str(localTracerouteChecksum) + ", rx" +\
                        #               str(self.tracerouteReceivedChecksum))

                        # Update the 'stable' TracerouteHopsList (this will be used for reports/display purposes)
                        self.setTraceRouteHopsList(hopsList)

                        # Attempt to detect a route change
                        if hopsListChangeExpected is False:
                            # Under normal circumstances, take the rxTTL into account to determine route changes
                            # This *should* mean that even if the hopList lengths differ, if the RxTTL values *haven't*
                            # changed, we can ignore the change in prevHopsList/hopsList
                            routeHasChanged = Utils.detectRouteChanges(prevHopsList, hopsList,
                                                                prevRxTTL=prevRxTTL,
                                                                 rxTTL=self.__stats["packet_instantaneous_ttl"])
                            # Debug code:
                            # if str(self.__stats["stream_friendly_name"]).find("Berlin") >= 0:
                            #     if routeHasChanged is False:
                            #         Utils.Message.addMessage(
                            #             "Route debug. " + str(self.__stats["stream_friendly_name"]) + " routeHasChanged: False, prevHopsList:" + str(prevHopsList) + \
                            #             ", hopsList:" + str(hopsList) + ", prevRxTTL: " + str(prevRxTTL) + \
                            #             ", rxTTL:" + str(self.__stats["packet_instantaneous_ttl"]))
                            #
                            #
                            #     else:
                            #         Utils.Message.addMessage(
                            #             "Route debug. " + str(self.__stats["stream_friendly_name"]) + " routeHasChanged: True, prevHopsList:" + str(
                            #                 prevHopsList) + \
                            #             ", hopsList:" + str(hopsList) + ", prevRxTTL: " + str(prevRxTTL) + \
                            #             ", rxTTL:" + str(self.__stats["packet_instantaneous_ttl"]))

                        else:
                            # Otherwise, if the rxTTL has not recently changed, we can only go on the prevHopsList and hopsList
                            # to determine route changes because the hopsList changes will lag behind those of rxTTL
                            routeHasChanged = Utils.detectRouteChanges(prevHopsList, hopsList)

                        if routeHasChanged:
                            # Route change detected, create a new IPRoutingChange event
                            # Acknowledge the route change and clear the flag
                            hopsListChangeExpected = False
                            iPRoutingTracerouteChange = IPRoutingTracerouteChange(self.__stats, hopsList)
                            # Add the event to the event list
                            self.__eventList.append(iPRoutingTracerouteChange)
                            # # Increment the all_events counter
                            self.__stats["stream_all_events_counter"] += 1
                            # Update the routeChange stats
                            self.__stats["route_change_events_total"] += 1
                            self.__stats["route_time_of_last_route_change_event"] = iPRoutingTracerouteChange.timeCreated

                            # Take snapshot of new time delta and add to the sum of existing values (to calculate mean)
                            self.__stats["sumOfTimeElapsedSinceLastRouteChange"] +=\
                                    self.__stats["route_time_elapsed_since_last_route_change_event"]

                            # Post a message
                            Utils.Message.addMessage(iPRoutingTracerouteChange.getSummary(includeStreamSyncSourceID=False)['summary'])
                            # Utils.Message.addMessage("old tr " + str(prevHopsList))
                            # Utils.Message.addMessage("new tr " + str(hopsList))

                        # Snapshot latest hopsList (regardless of whether a route change was detected)
                        prevHopsList = hopsList
                    else:
                        # Utils.Message.addMessage("Traceroute checksums don't match " + str(localTracerouteChecksum) + ":" +\
                        #               str(self.tracerouteReceivedChecksum))
                        pass

                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread detect route changes " + str(e))

                # Snapshot current rxTTL value
                prevRxTTL = self.__stats["packet_instantaneous_ttl"]

                ########## Calculate traceroute route change stats
                try:
                    # (But only if there has actually been a second route change in the past to measure against)
                    # AND stream is alive
                    # Note: The initial route is considered as 'change 1' therefore is ignored and threshold is >=1
                    ####### Now update the self.__stats["route_time_elapsed_since_last_route_change_event"] timer
                    if (self.__stats["route_change_events_total"] > 0) and (self.__stats["streamIsDeadFlag"] is False):

                        self.__stats["route_time_elapsed_since_last_route_change_event"] = \
                            datetime.datetime.now() - self.__stats["route_time_of_last_route_change_event"]

                    ########### Calculate mean time between route changes.
                    # Note: Ignore the first route change, because it's not really a 'change', just the initial value
                    if (self.__stats["route_change_events_total"] > 1) and (self.__stats["streamIsDeadFlag"] is False):
                        self.__stats["route_mean_time_between_route_change_events"] = \
                            calculateMeanPeriodBetweenEvents(self.__stats["sumOfTimeElapsedSinceLastRouteChange"],
                                                             self.__stats["route_time_elapsed_since_last_route_change_event"],
                                                             (self.__stats["route_change_events_total"] - 1))
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Calculate traceroute Change stats " + str(e) + ", " +\
                                             str(self.__stats["sumOfTimeElapsedSinceLastRouteChange"]))

                ############ Now send results back to transmitter
                try:
                    # Confirm that the stream is being sent from an instance of isptest AND only send if we're
                    # currently receiving bytes AND only if we have a valid message queue to send through
                    if (self.__stats["stream_transmitterVersion"] > 0) and \
                            self.__stats["packet_data_received_1S_bytes"] > 0 and \
                                self.__stats["stream_rxPort"] in self.txQueuesDict:

                            # Get the last 5 events for this stream
                            NO_OF_PREV_EVENTS_TO_SEND = 5
                            eventsList = self.getRTPStreamEventList(NO_OF_PREV_EVENTS_TO_SEND)
                            addResultsToTxQueue(self.__stats, eventsList, self.txQueuesDict[self.__stats["stream_rxPort"]],
                                                self.__stats["stream_srcAddress"],
                                                self.__stats["stream_srcPort"])
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Transmit results for stream " +\
                                             str(self.__stats["stream_syncSource"]) + ", " + str(e))


                # Finally verify that this stream has been successfully registered with the directory
                # This should happen at the point of stream creation (in __init__()) but may fail
                # if the server is busy
                try:
                    streamsList = self.ctrlAPI.getStreamsList(streamID=self.syncSourceIdentifier)
                    # Test to see if response contains an entry for this stream
                    if streamsList[0]["streamID"] == self.syncSourceIdentifier and \
                            streamsList[0]["streamType"] == "RtpReceiveStream":
                        # Utils.Message.addMessage(f"RtpReceiveStream {self.syncSourceIdentifier} exists in streamsList")
                        pass
                except:
                    # stream doesn't exist, so need to register it
                    # Create a dict to define the stream
                    streamDefinition = {
                        "streamID": self.syncSourceIdentifier,
                        "httpPort": self.tcpListenPort,
                        "streamType": "RtpReceiveStream"
                    }
                    try:
                        # Register the stream
                        self.ctrlAPI.addToStreamsDirectory(streamDefinition)
                        Utils.Message.addMessage(f"DBUG:RtpReceiveStream.__samplingThread({self.syncSourceIdentifier}) "\
                                                 f"successful stream registration")
                    except Exception as e:
                        Utils.Message.addMessage(f"ERR:RtpReceiveStream.__samplingThread({self.syncSourceIdentifier})"\
                                                 f" registration fail {e}")

                # Utils.Message.addMessage("Tx pid " + str(self.__stats["stream_transmitter_PID"]) )

                # #Get last glitch by eventNo
                # try:
                #     lastGlitchEventList = self.getRTPStreamEventList(requestedEventNo=self.__stats["glitch_most_recent_eventNo"])
                #     if len(lastGlitchEventList) > 0:
                #             lastGlitchEventSummary = lastGlitchEventList[0].getSummary()["summary"]
                #             Utils.Message.addMessage("Last glitch  event no: " + str(self.__stats["glitch_most_recent_eventNo"]) +\
                #                                      ", " + lastGlitchEventSummary)
                # except Exception as e:
                #     Utils.Message.addMessage("ERR: Last glitch: " + str(e))

                # Utils.Message.addMessage(f"DBUG:sampling Thread__eventList {self.__eventList}")

                ######## 1 second counter end of code ########

            try:
                ######## Check to see if the stream is dead (has been permanently lost). If so, set streamIsDeadFlag
                # but only do this once, so need to check that the flag has not already been set
                if secondsWithNoBytesRxdTimer >= Registry.streamIsDeadThreshold_s and self.__stats["lossOfStreamFlag"] and\
                        self.__stats["streamIsDeadFlag"] is False:
                    self.__stats["streamIsDeadFlag"] = True
                    Utils.Message.addMessage("Stream " + str(self.__stats["stream_syncSource"]) + \
                                             "(" + str(self.__stats["stream_friendly_name"]).rstrip() + \
                                             ") believed dead")
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread detect dead stream " + str(e))

            try:
                ######## If the stream has been declared 'dead' and the autoRemoveDeadRxStreamsThreshold_s
                # threshold has been exceeded AND auto-remove is enabled, kill it
                # if streamIsDeadFlag and Registry.autoRemoveDeadRxStreamsEnable:
                if self.__stats["streamIsDeadFlag"] and \
                        ((datetime.datetime.now() - self.__stats["lossOfStreamEventTimestamp"]).total_seconds() > \
                                Registry.autoRemoveDeadRxStreamsThreshold_s) and Registry.autoRemoveDeadRxStreamsEnable:

                    # Generate and save a report
                    # Generate the actual report
                    report = self.generateReport()
                    # Retrieve the auto-generated filename
                    _filename = self.createFilenameForReportExport()

                    # Write a report to disk
                    Utils.writeReportToDisk(report, fileName=_filename)
                    # Kill itself
                    self.killStream(caller=self)
            except Exception as e:
                Utils.Message.addMessage(f"ERR:RtpReceiveStream.__samplingThread auto remove stream:"
                                         f"lossOfStreamEventTimestamp: {self.__stats['lossOfStreamEventTimestamp']}, err: {e}")

            # Increment 1 sec loop counter
            loopCounter += 1
        Utils.Message.addMessage("DBUG: __samplingThread ended for stream " + str(self.__stats["stream_syncSource"]))


    # This is the main receiver thread for the incoming Rtp stream. It employs a 'non-busy wait' for RtpData objects
    # to become available. It will detect events, and it will alse update the relevant instance variables with the
    # latest data.
    # NOTE: Ideally This thread shouldn't update the __ stats[] dictionary directly (for the purposes of speed and risk
    # of being blocked by other processes that might want to access __stats[]) any more than it needs to.
    # The fastest changing vars have their own instance variables and these are copied into the stats

    def __queueReceiverThread(self):
        Utils.Message.addMessage("DBUG: Starting __queueReceiverThread for stream " + \
                                 str(self.__stats["stream_syncSource"]))

        def updateGlitchStats(qrtInstance, latestGlitch):
            # update running total glitch stats
            # qrtInstance.__stats["glitch_packets_lost_total_count"] += latestGlitch.packetsLost
            qrtInstance.__stats["glitch_length_total_time"] += latestGlitch.glitchLength
            qrtInstance.__stats["glitch_counter_total_glitches"] += 1

            # Add event to moving counters
            for x in qrtInstance.movingGlitchCounters:
                x.addEvent(1)

            if qrtInstance.__stats["glitch_counter_total_glitches"] == 1:
                # Special case: If this is the first glitch, add the time elapsed *before* the first glitch to the
                # sumOfTimeElapsedSinceLastGlitch running total
                qrtInstance.__stats["sumOfTimeElapsedSinceLastGlitch"] += qrtInstance.__stats["stream_time_elapsed_total"]


            # Take snapshot of new time delta and add to the sum of existing values (to calculate mean)
            qrtInstance.__stats["sumOfTimeElapsedSinceLastGlitch"] += qrtInstance.__stats["glitch_time_elapsed_since_last_glitch"]

            # Update glitch min/max packet loss stats
            if qrtInstance.__stats["glitch_packets_lost_per_glitch_min"] < 1:
                qrtInstance.__stats["glitch_packets_lost_per_glitch_min"] = latestGlitch.packetsLost

            # Update min/max counters
            if latestGlitch.packetsLost < qrtInstance.__stats["glitch_packets_lost_per_glitch_min"]:
                qrtInstance.__stats["glitch_packets_lost_per_glitch_min"] = latestGlitch.packetsLost

            if latestGlitch.packetsLost > qrtInstance.__stats["glitch_packets_lost_per_glitch_max"]:
                qrtInstance.__stats["glitch_packets_lost_per_glitch_max"] = latestGlitch.packetsLost

            # update glitch min/max duration stats
            # Test for 'zero' duration (the initial value)
            if qrtInstance.__stats["glitch_min_glitch_duration"] == datetime.timedelta():
                qrtInstance.__stats["glitch_min_glitch_duration"] = latestGlitch.glitchLength

            if latestGlitch.glitchLength < qrtInstance.__stats["glitch_min_glitch_duration"]:
                qrtInstance.__stats["glitch_min_glitch_duration"] = latestGlitch.glitchLength

            if latestGlitch.glitchLength > qrtInstance.__stats["glitch_max_glitch_duration"]:
                qrtInstance.__stats["glitch_max_glitch_duration"] = latestGlitch.glitchLength

            # Add the glitch to the worstGlitches leaderboard Where it will be analysed to see if it's in the top 'n')
            qrtInstance.addToWorstGlitchesList(latestGlitch)
            # # Get a text version of the worst glitches, and copy to the __stats[] dict
            # qrtInstance.__stats["glitch_worst_glitches_list"] = qrtInstance.getWorstGlitches(returnSummaries=True)

        # Attempts to add new Jitter Event
        def addJitterEvent(qrtInstance, latestPacket, jitter, excessiveJitterThreshold):
            # If time since last jitter event exceeds the rate-limit threshold, add a new jitter event
            # Take diff between time.now() and the time of the last event
            # Allow the stream to settle into a steady state by waiting for 5 seconds and also verify that
            # a non-zero excessiveJitterThreshold has been supplied
            # and. Jitter Event generation is enabled Registry.rtpReceiveStreamEnableExcessiveJitterEventGeneration
            if (qrtInstance.__stats["jitter_time_elapsed_since_last_excess_jitter_event"].total_seconds() >\
                    qrtInstance.__stats["jitter_alarm_event_timeout_S"] or\
                    qrtInstance.__stats["jitter_excess_jitter_events_total"] == 0) and excessiveJitterThreshold > 0 and\
                    qrtInstance.__stats["stream_time_elapsed_total"].total_seconds() > 5 and\
                    Registry.rtpReceiveStreamEnableExcessiveJitterEventGeneration:

                # Utils.Message.addMessage("Excessive jitter Event Creation. Timeout " + \
                #              str(qrtInstance.__stats["jitter_time_elapsed_since_last_excess_jitter_event"].total_seconds()) + \
                #              ", threshold " + str(qrtInstance.__stats["jitter_alarm_event_timeout_S"]) + \
                #              ", no of events: " + str(qrtInstance.__stats["jitter_excess_jitter_events_total"]))

                # Create an Excessive Jitter event
                excessiveJitterEvent = ExcessiveJitter(qrtInstance.__stats, latestPacket, jitter, excessiveJitterThreshold)
                # Add the event to the event list
                qrtInstance.__eventList.append(excessiveJitterEvent)
                # Increment the all_events counter
                qrtInstance.__stats["stream_all_events_counter"] += 1
                # Update jitter_time_elapsed_since_last_excess_jitter_event
                qrtInstance.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = \
                    datetime.datetime.now() - excessiveJitterEvent.timeCreated

                # Post a message
                Utils.Message.addMessage(excessiveJitterEvent.getSummary(includeStreamSyncSourceID=False)['summary'])

                # Update the event counter for Excess Jitter
                qrtInstance.__stats["jitter_excess_jitter_events_total"] += 1

                # Special case: if this is the first Excesive Jitter event, add the time elapsed *before* the first
                # jitter event to the sumOfTimeElapsedSinceLastExcessJitterEvents running total
                if qrtInstance.__stats["jitter_excess_jitter_events_total"] == 1:
                    qrtInstance.__stats["sumOfTimeElapsedSinceLastExcessJitterEvents"] += \
                        qrtInstance.__stats["stream_time_elapsed_total"]


                # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean period between events)
                qrtInstance.__stats["sumOfTimeElapsedSinceLastExcessJitterEvents"] += \
                    qrtInstance.__stats["jitter_time_elapsed_since_last_excess_jitter_event"]

                # Take timestamp for this (the most recent) Excess Jitter event
                qrtInstance.__stats["jitter_time_of_last_excess_jitter_event"] = excessiveJitterEvent.timeCreated
            else:
                # Utils.Message.addMessage("Excessive jitter Event inhibited. Timeout " +\
                #     str(qrtInstance.__stats["jitter_time_elapsed_since_last_excess_jitter_event"].total_seconds()) +\
                #                          ", threshold " + str(qrtInstance.__stats["jitter_alarm_event_timeout_S"]) +\
                #                          ", no of events: " + str(qrtInstance.__stats["jitter_excess_jitter_events_total"]))
                pass

        # Circular buffer to contine the latest, and previous two packets. This will allow detection of glitches,
        # the receive period and also the jitter (which requires three samples)
        rtpPackets = deque(maxlen=3)

        # Create timedelta objects for jitter variables
        prevReceivePeriod = 0

        # Flag to permit detection of jitter
        # jitter detection is disabled the first time around
        jitterDetectionEnabledFlag = False

        # # Store the current and previous rtp sequence nos. - replaces the deque
        # latestRtpSeqNo = 0
        # prevRtpSeqNo = 0 # 'n-1' seq no
        # oldestSeqNo = 0 # the 'n-2' seq

        while self.queueReceiverThreadActiveFlag:

            # Check to see whether this stream is known about in rxQueuesDict (it won't necessarily be, if it was
            # a historic stream that has been recreated)
            if self.syncSourceIdentifier in self.rxQueuesDict:
                # Now wait for items to appear in the queue (with a timeout)
                try:

                    # Get a handle on the receive queue
                    rxQueue = self.rxQueuesDict[self.syncSourceIdentifier]
                    # Wait for a packet to arrive in the receive queue
                    rtpPacketData = rxQueue.get(timeout=0.2)
                    # Copy the latest received rtp packet into the instance variable (so it can be referenced elsewhere)
                    self.__latestReceivedRtpPacket = rtpPacketData

                    # # Take a copy of the latest sequence no.
                    # latestSeqNo = rtpPacketData.rtpSequenceNo

                    # Monitor the size of the queue
                    # If the queue size starts creeping up, this suggests the CPU can't can't keep up with the rate
                    # of incoming packets
                    self.rtpStreamQueueCurrentSize = rxQueue.qsize()
                    if self.rtpStreamQueueCurrentSize > self.rtpStreamQueueMaxSize:
                        # Keep track of the maximum queue size
                        self.rtpStreamQueueMaxSize = self.rtpStreamQueueCurrentSize

                    # Set initial values
                    if self.packetCounterReceivedTotal == 0:
                        # If this is the first packet, set the 'packet first seen' timestamp
                        self.__stats["packet_first_packet_received_timestamp"] = datetime.datetime.now()
                        # Create a 'stream started' event
                        streamStartedEvent = StreamStarted(self.__stats, rtpPacketData)
                        # Append the event to the events list
                        self.__eventList.append(streamStartedEvent)
                        # Increment the Event counter
                        self.__stats["stream_all_events_counter"] += 1
                        # Display a message
                        Utils.Message.addMessage(streamStartedEvent.getSummary(includeStreamSyncSourceID=False)['summary'])

                    # Update 'last seen packet' timestamp.
                    # Note: This is a fast changing variable so is held as an instance variable.
                    # The __samplingThread will copy this var into the __stats dict
                    self.__packet_last_seen_received_timestamp = datetime.datetime.now()

                    # Increment packet received counter
                    self.packetCounterReceivedTotal += 1
                    # Update total bytes received
                    self.__packetDataReceivedTotalBytes += rtpPacketData.payloadSize

                    ########### Extract isptest header from most recent packet
                    self.__extractIsptestHeaderData(rtpPacketData.isptestHeaderData)

                    ############ Snapshot the 'latest IP TTL' value
                    # Note: This TTL value might be 'None' (i.e not set)
                    self.__rxTTL = rtpPacketData.rxTTL
                    ############ Snapshot the 'latest src addr' value
                    self.__srcAddress = rtpPacketData.srcAddr
                    ############ Snapshot the 'latest src port' value
                    self.__srcPort = rtpPacketData.srcPort

                    # Add the packet to the circular packet buffer (for glitch, receive period and jitter analysis)
                    rtpPackets.append(rtpPacketData)
                    # We need to have received at least two packets before we can detect a glitch seq error
                    # and three packets before we can calculate the glitch period
                    # also three packets required before we can calculate the jitter
                    if len(rtpPackets) > 2:
                        ### Detect sequence no. anomoly (i.e a glitch)
                        # Test the latest seq no against the previous
                        # Detect against false glitches when the seq no wraps around
                        # if rtpPackets[-2].rtpSequenceNo == 65535:
                        #     rtpPackets[-2].rtpSequenceNo = -1
                        sequenceNoGap = rtpPackets[-1].rtpSequenceNo - rtpPackets[-2].rtpSequenceNo

                        # if sequenceNoGap < 1:
                        #     Utils.Message.addMessage("PKT: 0 or -ve sequenceNoGap " + str(sequenceNoGap))
                        #
                        # Detect sequence no wrapping around to zero
                        if sequenceNoGap < -32768:
                            # If diff < -32768, add 65536 // Turns diff into a +ve no.
                            modifiedSequenceNoGap = sequenceNoGap + 65536
                            # Utils.Message.addMessage("PKT:Seq no wrapping to zero. old diff " +\
                            #                          str(sequenceNoGap) + " new diff " + str(modifiedSequenceNoGap))
                            # Copy new seq no
                            sequenceNoGap = modifiedSequenceNoGap

                        # Detect out-of-order packet receipt (i.e received seq numbers going backwards!)
                        # This should manifest itself as a -ve sequenceNoGap between -32768 and 0
                        elif (sequenceNoGap < 0) and (sequenceNoGap > -32768):
                            # Utils.Message.addMessage("PKT:Out of order packet: current seq " + str(rtpPackets[-1].rtpSequenceNo) +\
                            #               ", prev " + str(rtpPackets[-2].rtpSequenceNo) + ", diff " +\
                            #                          str(sequenceNoGap))
                            # Create an OutOfOrderPacket Event
                            outOfOrderPacket = OutOfOrderPacket(self.__stats, rtpPackets[-2], rtpPackets[-1])
                            # Append the event to the eventList
                            self.__eventList.append(outOfOrderPacket)
                            # Increment the all_events counter
                            self.__stats["stream_all_events_counter"] += 1
                            # Post a message
                            Utils.Message.addMessage(outOfOrderPacket.getSummary(includeStreamSyncSourceID=False)['summary'])

                        # Detect duplicate sequence no. This shouldn't be possible because the sequence no.s should increment
                        elif sequenceNoGap == 0:
                            # Utils.Message.addMessage("Duplicate seq no received " + str(str(rtpPackets[-1].rtpSequenceNo)))
                            # Create a DuplicateSequenceNo event
                            duplicateSequenceNo = DuplicateSequenceNo(self.__stats, rtpPackets[-2], rtpPackets[-1])
                            # Append the event to the eventList
                            self.__eventList.append(duplicateSequenceNo)
                            # Increment the all_events counter
                            self.__stats["stream_all_events_counter"] += 1
                            # Post a message
                            Utils.Message.addMessage(duplicateSequenceNo.getSummary(includeStreamSyncSourceID=False)['summary'])

                        # A seq no gap of > 1 suggests a glitch
                        if sequenceNoGap > 1:
                            # Discontinuous sequence numbers detected
                            # Create a Glitch Event
                            # Calculate packets lost
                            packetslost = sequenceNoGap - 1
                            # glitch = Glitch(self.__stats, rtpPackets[-2], rtpPackets[-1], packetslost)
                            glitch = Glitch(self.__stats, rtpPackets, packetslost)
                            # Update the packets lost count
                            self.__stats["glitch_packets_lost_total_count"] += glitch.packetsLost
                            # Test to see how many packets have been lost
                            if glitch.packetsLost > self.__stats["glitch_Event_Trigger_Threshold_packets"]:
                                # Significant glitch detected, add it to the eventList[]
                                self.__eventList.append(glitch)
                                # update glitch stats
                                updateGlitchStats(self, glitch)
                                # Take timestamp of most recent glitch
                                self.__stats["glitch_most_recent_timestamp"] = glitch.timeCreated
                                # Snapshot the event no of the most recent glitch
                                self.__stats["glitch_most_recent_eventNo"] = glitch.eventNo
                                # Increment the all_events counter
                                self.__stats["stream_all_events_counter"] += 1
                                # Post a message
                                Utils.Message.addMessage(glitch.getSummary(includeStreamSyncSourceID=False)['summary'])

                            else:
                                # Glitch is below the threshold. Acknowledge it with a message but don't add an Event
                                # increment the 'ignored' counter so that we know that it happened
                                # Note, this message is not logged to disk, to save the log file being filled
                                self.__stats["glitch_glitches_ignored_counter"] += 1
                                # Post a message
                                Utils.Message.addMessage("Stream " + str(self.__stats["stream_syncSource"]) + ", " +\
                                                         str(sequenceNoGap) + " packets lost. (<=" +\
                                                         str(self.__stats["glitch_Event_Trigger_Threshold_packets"]) +\
                                                         ", minor loss " + str(rtpPackets[-2].rtpSequenceNo) + ":" +\
                                                         str(rtpPackets[-1].rtpSequenceNo) + ")", logToDisk=False )

                            # Temporarily disable the jitter detection immediately after a glitch
                            jitterDetectionEnabledFlag = False
                            # Inhibit immediate jitter-event triggering by setting __stats["jitter_time_of_last_excess_jitter_event"]
                            # to the current time
                            self.__stats["jitter_time_of_last_excess_jitter_event"] = datetime.datetime.now()

                        # Calculate receive period of latest packet (taking into account seconds and microseconds)
                        receivePeriodTimeDelta = (rtpPackets[-1].timestamp - rtpPackets[-2].timestamp)
                        # Consider the seconds and microseconds components/Convert secs to microsecs
                        receivePeriod = (receivePeriodTimeDelta.seconds * 1000000) + receivePeriodTimeDelta.microseconds

                        # Add latest receive period value to running total, for averaging
                        self.__receivePeriodRunningTotal += receivePeriod

                        # Perform jitter calculation if detection is enabled (it will be disabled immediately after a glitch)
                        # and also when we have enough data points (3 packets)
                        if jitterDetectionEnabledFlag:
                            # Calculate jitter of latest packet by calculating the difference in receive periods
                            # Note: Jitter might be -ve if the received packet is 'early'
                            jitter = receivePeriod - prevReceivePeriod
                            # Add absolute (+ve) latest jitter value to running total, for averaging
                            self.__jitterRunningtotal += abs(jitter)
                            # Snapshot latest receive period
                            prevReceivePeriod = receivePeriod

                            # Update min/max jitter stats
                            if self.jitter_min_uS == 0:
                                # Set initial value
                                self.jitter_min_uS = jitter
                            elif jitter < self.jitter_min_uS:
                                # Update if latest value is less
                                self.jitter_min_uS = jitter
                            if self.jitter_max_uS == 0:
                                # Set initial value
                                self.jitter_max_uS = jitter
                            elif jitter > self.jitter_max_uS:
                                # Update max jitter
                                self.jitter_max_uS = jitter
                            # Update jitter range stats
                            self.jitter_range_uS = self.jitter_max_uS - self.jitter_min_uS

                            # Now detect an excessive jitter event
                            if jitterDetectionEnabledFlag:
                                excessiveJitterThreshold = Registry.rtpReceiveStreamJitterExcessiveAlarmThreshold *\
                                                           self.__stats["packet_mean_receive_period_uS"]
                                if jitter > excessiveJitterThreshold:
                                    # Utils.Message.addMessage("Excessive jitter " + str(jitter) + ", threshold " + str(excessiveJitterThreshold) +\
                                    #                          ", packet_mean_receive_period_uS " + str(self.__stats["packet_mean_receive_period_uS"]))
                                    # calculated jitter exceeds threshold, so add event and update the stats
                                    addJitterEvent(self, rtpPacketData, jitter, excessiveJitterThreshold)

                        else:
                            # re-enable jitter detection
                            jitterDetectionEnabledFlag = True

                        # x = rtpPackets[-1].rtpSequenceNo
                        # if x % 20 == 0:
                        #     # Utils.Message.addMessage("__queueReceiverThread " + str(x) + " Packets Rx'd: " +\
                        #     #                          str(packet_counter_received_total) +\
                        #     #                          ", bytes rx'd " + str(packet_data_received_total_bytes))
                        #     # seqNos = str(rtpPackets[0].rtpSequenceNo) + ", " + \
                        #     #          str(rtpPackets[1].rtpSequenceNo) + ", " + \
                        #     #          str(rtpPackets[2].rtpSequenceNo) + ", "
                        #     # Utils.Message.addMessage(seqNos)
                        #     # Utils.Message.addMessage("jitter " + str(self.jitter_min_uS) +">" + str(self.jitter_range_uS) +\
                        #     #                          ">" + str(self.jitter_max_uS))
                        #     pass


                except Empty:
                # Will be raised if there is a queue timeout (i.e no data in the queue)
                    pass
                except Exception as e:
                    Utils.Message.addMessage("ERR:__queueReceiverThread.get() " + str(e))
            else:
                # Otherwise, wait a while before checking again
                time.sleep(0.5)

        Utils.Message.addMessage("DBUG: Ending __queueReceiverThread for stream " + \
                                 str(self.__stats["stream_syncSource"]))


    # Define setter methods
    # Thread-safe method to set the friendly name field
    # NOTE: This method checks to see if the received stream has been generated by an instance of isptest
    # If so, it will send a 'change name' message to the transmitter end. If not (eg, if the incoming stream has been
    # generated by an NTT, it will modify the stats["stream_friendly_name"] value locally
    def setFriendlyName(self, friendlyName):
        # Truncate supplied name to x characters (truncated to preserve the screen layout) or else pad to 12 chars
        if len(friendlyName) < self.maxNameLength:
            # Too short, so Pad out name to x chars
            friendlyName += (self.maxNameLength - len(friendlyName)) * " "
        else:
            # Too big, so truncate
            friendlyName = friendlyName[:self.maxNameLength]

        # Confirm whether the stream is being sent from an instance of isptest AND only send if we're
        # currently receiving bytes AND only if we have a valid tx message queue to send through
        if (self.__stats["stream_transmitterVersion"] > 0) and \
                self.__stats["packet_data_received_1S_bytes"] > 0 and \
                    self.__stats["stream_rxPort"] in self.txQueuesDict:

            try:
                # Send a 'name change' message back to the TRANSMITTER
                self.sendControlMessageToTransmitter({"syncSourceID": self.syncSourceIdentifier,
                                                        "source": "Receiver",
                                                        "type": "/label",
                                                        "name": friendlyName})
            except Exception as e:
                Utils.Message.addMessage(f"ERR:RtpReceiveStream({self.syncSourceIdentifier}).setFriendlyName() "\
                                         f"{friendlyName}, err:{e}")
        else:
            # Otherwise, this is a stream from an unknown source OR a historic stream and no more data is being received
            # so just change the name locally
            self.__stats["stream_friendly_name"] = friendlyName
        return friendlyName

    # Define getter methods
    def getRTPStreamID(self):
        # Thread-safe method to access stream syncSource, src address, src port and name fields
        stats = self.__stats.copy()
        return stats["stream_syncSource"], stats["stream_srcAddress"], \
               stats["stream_srcPort"], self.__stats["stream_friendly_name"]

    # Will overwrite the existing stats dict with the newly supplied one
    # Note: This method is not remotely thread safe RtpReceiveStream.__stats[] is NOT mutex protected
    def updateStats(self, statsDict):
        # take copy of the incoming dict (to decouple it)
        copiedStatsDict = deepcopy(statsDict)
        # Overwrite the existing dict
        self.__stats = copiedStatsDict

    # Thread-safe method for accessing all RtpStream stats
    def getRtpStreamStats(self, keyIs=None, keyContains=None, keyStartsWith=None, listKeys=False):
        stats = self.__stats.copy()
        # Get a filtered version of the stats dict
        filteredStats = Utils.filterDictByKey(stats, keyIs=keyIs, keyContains=keyContains, keyStartsWith=keyStartsWith,
                                              listKeys=listKeys)
        return filteredStats

    ## DEPRECATED: Use optional args in getRtpStreamStats() instead
    def getRtpStreamStatsByFilter(self, keyFilter):
        # Thread-safe method to return specific stats who's dictionary key starts with 'filter'
        # Returns a list of tuples
        stats = self.__stats.copy()
        # Filter keys of stats by startswith('filter') into a new dictionary
        filteredStats = {k: v for k, v in stats.items() if k.startswith(keyFilter)}
        return filteredStats

    ## DEPRECATED: Use optional args in getRtpStreamStats() instead
    def getRtpStreamStatsByKey(self, key):
        # Thread safe method to retrieve a single stats item by key
        # If the key doesn't exist, it will return None type
        stats = self.__stats.copy()
        if key in stats:
            return stats[key]
        else:
            return None

    # Appends eventsList to the existing contents of self.__eventList
    # if replaceExistingList is True, the existing self.__eventList will be replaced
    # NOTE: This is not thread safe as self.__eventList is NOT mutex-protected
    def updateEventsList(self, eventsList, replaceExistingList=False):
        # take copy of the incoming list (to decouple it)
        copiedEventsList = deepcopy(eventsList)
        if replaceExistingList is False:
            self.__eventList.extend(copiedEventsList)
        else:
            self.__eventList = copiedEventsList

    # Thread-safe method for accessing realtime RtpStream eventList
    # No args: Returns the entire list
    # 1 arg: Returns the last n events
    # 2 args: returns the range specified (inclusive)
    # ALTERNATIVELY: Use kwargs, recent=None, start=None, end=None instead

    # filterList is an optional arg containing a list of Event object types to test against within EventsList
    # UPDATE 4/11/20 filterList can now be a single item (either a string corresponding to the __class__.__name__
    # attribute of an object or a Python Object) instead of a list.
    # eg these are all valid: filterList="Glitch", filterList=Glitch (where Glitch is a Python class) or
    # filterlist=[Glitch], or filterList = ["Glitch"]

    # eg filterList = [Glitch] will return only a list of glitches, [Glitch, StreamStarted] would give you a list
    # containing all Glitch and StreamStarted events

    # Alternatively, filterList can also be a list of strings which are the class names of the objects to be
    # filtered (as opposed to the Class name itself (as in, the Object.__name attribute)
    # The filter (if present) is applied first, then the range specifier
    # Finally, if reverseOrder==True, the list will be returned in reverse order
    def getRTPStreamEventList(self, *args, filterList=None, reverseOrder=False, requestedEventNo=None,
                                recent=None, start=None, end=None):
        # Create copy of events list
        unfilteredEventList = list(self.__eventList)

        # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
        # (or else, if kwarg 'start' and 'end' are  specified'
        if len(args) == 2:
            start = args[0]
            end = args[1]
        # If one arg supplied, return the last n events (or else, if kwarg 'recent' is specified'
        # IF event list not as long as n, return what does exist
        elif len(args) == 1: # If non kwarg supplied, use that instead
            recent = args[0]

        # Filter the events list using the specified criteria
        filteredEventList = self.filterEventsList(unfilteredEventList, filterList=filterList, reverseOrder=reverseOrder,
                                                  requestedEventNo=requestedEventNo, recent=recent, start=start, end=end)
        return filteredEventList


    # Define setter methods
    #### DEPRECATED  1/12/20 RtpPacketReceiver now places new RtpData objects directly into the queue referenced in
    # rxQueuesDict{}
    # def addData(self, rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData, rxTTl, srcAddress, srcPort):
    #     # Create a new rtp data object to hold the rtp packet data and add it to the receive queue
    #     # newData = RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData)
    #     try:
    #         self.rtpStreamQueue.put(RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData, \
    #                                         rxTTl, srcAddress, srcPort))
    #         # Increment the counter. Packets out should equal packets in
    #         self.packetsAddedToRxQueueCount += 1
    #     except Exception as e:
    #         Utils.Message.addMessage("RtpReceiveStream.addData() " + str(e))

    # Sends a control message to the isptest Transmitter associated with this ReceiverStream object
    # by pickling the supplied message and wrapping it up in another dict along with
    # a destination ip and port (so that the  udpTransmit routine knows where to send it)
    # Returns a sucess/fail message transmit status in the form of a dict
    # Messages sent by this method will be parsed by RtpGenerator.parseControlMessage()
    def sendControlMessageToTransmitter(self, msg):
        # Test to see if the rtp source of this stream is actually an instance of isptest

        if self.__stats["stream_transmitterVersion"] > 0:
            # and a valid tx queue exists
            if self.__stats["stream_rxPort"] in self.txQueuesDict:
                Utils.Message.addMessage("DBUG:sendControlMessageToTransmitter() msg to send: " + str(msg))
                try:
                    # wrap the message in a dict with the "control" key. This will be detected in ResultsReceiver.__resultsReceiverThread()
                    wrappedMessage = {"control": msg}
                    # pickle the wrapped message
                    # pickledMessage = pickle.dumps(wrappedMessage, protocol=2)
                    pickledMessage = pickle.dumps(wrappedMessage)
                    # add the pickled message to the txMessageQueue
                    txQueue = self.txQueuesDict[self.__stats["stream_rxPort"]]
                    txQueue.put([pickledMessage, self.__stats["stream_srcAddress"], self.__stats["stream_srcPort"]])
                    return {"status": True, "error": None}

                except Exception as e:
                    return {"status": False, "error": str(e)}
            else:
                return {"status": False, "error": "Rtp stream " + str(self.__stats["stream_syncSource"]) + \
                                                  " can't be remotely controlled. No Tx Queue available"}
        else:
            return {"status": False, "error": "Rtp stream " + str(self.__stats["stream_syncSource"]) +\
                                                        " can't be remotely controlled. Not generated by isptest"}


# Define a class to encompass the results sent back from the receiving to the transmitting side (via the
# ResultsTransmitter and ResultsReceiver objects)
# It does't perform any calculations itself (unlike RtpReceiveStream) but it does have similar getter methods for results,
# which should allow displayThread to treat this like an RtpStream object without any additional code alteration
class RtpStreamResults_OLD(RtpReceiveCommon):
    def __init__(self, syncSourceID, rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex, controllerTCPPort=None):

        super().__init__()
        self.controllerTCPPort = controllerTCPPort  # the TCP listener port of the HTTP Server running on the controller process
        self.rtpTxStreamResultsDict = rtpTxStreamResultsDict
        self.rtpTxStreamResultsDictMutex = rtpTxStreamResultsDictMutex
        self.syncSourceID = syncSourceID
        # Create private empty dictionary to hold stats for this RtpStream object. Accessible via a getter method
        self.__stats = {}

        # Create private empty list to hold Events for this RtpStream object. Accessible via a getter method
        # self.__eventList = []
        # __eventList is a collections.deque object so will auto-housekeep
        self.__eventList = deque(maxlen=Registry.rtpStreamResultsHistoricEventsLimit)

        # Create mutex locks for data access
        self.__accessRtpStreamStatsMutex = threading.Lock()         # for the stats dictionary
        self.__accessRtpStreamEventListMutex = threading.Lock()     # for the eventsList

        # Used to record when this object last received updated stats
        self.lastUpdatedTimestamp = datetime.timedelta()

        #Add this new RtpStreamResults object to the rtpTxStreamResultsDict
        self.rtpTxStreamResultsDictMutex.acquire()
        self.rtpTxStreamResultsDict[self.syncSourceID] = self
        self.rtpTxStreamResultsDictMutex.release()


    def updateStats(self, statsDict):
        # Will copy statsDict into self.__stats
        self.__accessRtpStreamStatsMutex.acquire()
        # Empty the current contents of the dictionary
        self.__stats.clear()
        # Copy supplied Dict contents into self.__stats{}
        self.__stats = deepcopy(statsDict)
        # Release the mutex
        self.__accessRtpStreamStatsMutex.release()
        # update the lastUpdated timestamp
        self.lastUpdatedTimestamp = datetime.datetime.now()

    def updateEventsList(self, eventsList, replaceExistingList=False):
        # Will take a list of new events and, by default, append them to the existing eventsList list
        # If replaceExistingList is set, it will completely replace the old list with the new list
        # NOTE: It won't check for duplicate entries or validate the list items,
        # it will blindly just append to what's already there

        # Take control of the mutex
        self.__accessRtpStreamEventListMutex.acquire()
        if replaceExistingList is False:
            # Default behaviour. Append the new events list to the existing list
            self.__eventList.extend(eventsList)
        else:
            # Completely replace the existing list with the newly supplied list
            self.__eventList=eventsList
        # Release the mutex
        self.__accessRtpStreamEventListMutex.release()
        # update the lastUpdated timestamp
        self.lastUpdatedTimestamp = datetime.datetime.now()
        # Now create a message for each event added (showing the summary for each event)
        for event in eventsList:
            try:
                Utils.Message.addMessage(event.getSummary()["summary"])
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpStreamresults.updateEventsList(), len " + str(len(eventsList)) +\
                                         ", " + str(e))


    # This method will remove this stream object from the rtpTxStreamResultsDict dictionary
    def killStream(self):
        self.rtpTxStreamResultsDictMutex.acquire()
        Utils.Message.addMessage("Deleting RtpStreamResults object for stream: " + str(self.syncSourceID))
        del self.rtpTxStreamResultsDict[self.syncSourceID]
        self.rtpTxStreamResultsDictMutex.release()

    # Define getter methods
    def getRTPStreamID(self):
        # Thread-safe method to access stream syncSource, src address, src port and name fields
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats["stream_syncSource"], stats["stream_srcAddress"], \
               stats["stream_srcPort"], self.__stats["stream_friendly_name"]

    # Thread-safe method for accessing all RtpStream stats
    def getRtpStreamStats(self, keyIs=None, keyContains=None, keyStartsWith=None, listKeys=False):
    # def getRtpStreamStats(self, **kwargs):
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        # Get a filtered version of the stats dict
        filteredStats = Utils.filterDictByKey(stats, keyIs=keyIs, keyContains=keyContains, keyStartsWith=keyStartsWith, listKeys=listKeys)
        return filteredStats


    def getRtpStreamStatsByFilter(self, keyFilter):
        # Thread-safe method to return specific stats who's dictionary key starts with 'filter'
        # Returns a list of tuples
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        # Filter keys of stats by startswith('filter') into a new dictionary
        filteredStats = {k: v for k, v in stats.items() if k.startswith(keyFilter)}
        return filteredStats

    def getRtpStreamStatsByKey(self, key):
        # Thread safe method to retrive a single stats item by key
        # If the key doesn't exist, it will return None type
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        if key in stats:
            return stats[key]
        else:
            return None

    # Thread-safe method for accessing realtime RtpStream eventList
    # No args: Returns the entire list
    # 1 arg: Returns the last n events
    # 2 args: returns the range specified (inclusive)
    # filterList is an optional arg containing a list of Event object types to test against within EventsList
    # eg filterList = [Glitch] will return only a list of glitches, [Glitch, StreamStarted] would give you a list
    # containing all Glitch and StreamStarted events
    # The filter (if present) is applied first, then the range specifier
    # Finally, if reverseOrder==True, the list will be returned in reverse order
    def getRTPStreamEventList(self, *args, filterList=None, reverseOrder=False, requestedEventNo=None,
                              recent=None, start=None, end=None):
        self.__accessRtpStreamEventListMutex.acquire()
        # Create copy of events list
        unfilteredEventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()

        # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
        # (or else, if kwarg 'start' and 'end' are  specified'
        if len(args) == 2:
            start = args[0]
            end = args[1]
        # If one arg supplied, return the last n events (or else, if kwarg 'recent' is specified'
        # IF event list not as long as n, return what does exist
        elif len(args) == 1:  # If non kwarg supplied, use that instead
            recent = args[0]

        # Filter the events list using the specified criteria
        filteredEventList = self.filterEventsList(unfilteredEventList, filterList=filterList, reverseOrder=reverseOrder,
                                                  requestedEventNo=requestedEventNo, recent=recent, start=start,
                                                  end=end)
        return filteredEventList

# Define a class to encompass the results sent back from the receiving to the transmitting side (via the
# ResultsTransmitter and ResultsReceiver objects)
# It does't perform any calculations itself (unlike RtpReceiveStream) but it does have similar getter methods for results,
# which should allow displayThread to treat this like an RtpStream object without any additional code alteration
class RtpStreamResults(RtpReceiveCommon):
    def __init__(self, syncSourceID, controllerTCPPort=None):

        super().__init__()
        self.controllerTCPPort = controllerTCPPort  # the TCP listener port of the HTTP Server running on the controller process
        self.syncSourceID = syncSourceID
        # Create private empty dictionary to hold stats for this RtpStream object. Accessible via a getter method
        self.__stats = {}

        # Create private empty list to hold Events for this RtpStream object. Accessible via a getter method
        # self.__eventList = []
        # __eventList is a collections.deque object so will auto-housekeep
        self.__eventList = deque(maxlen=Registry.rtpStreamResultsHistoricEventsLimit)

        # Create mutex locks for data access
        self.__accessRtpStreamStatsMutex = threading.Lock()         # for the stats dictionary
        self.__accessRtpStreamEventListMutex = threading.Lock()     # for the eventsList

        # Used to record when this object last received updated stats
        self.lastUpdatedTimestamp = datetime.timedelta()


    def updateStats(self, statsDict):
        # Will copy statsDict into self.__stats
        self.__accessRtpStreamStatsMutex.acquire()
        # Empty the current contents of the dictionary
        self.__stats.clear()
        # Copy supplied Dict contents into self.__stats{}
        self.__stats = deepcopy(statsDict)
        # Release the mutex
        self.__accessRtpStreamStatsMutex.release()
        # update the lastUpdated timestamp
        self.lastUpdatedTimestamp = datetime.datetime.now()

    def updateEventsList(self, eventsList, replaceExistingList=False):
        # Will take a list of new events and, by default, append them to the existing eventsList list
        # If replaceExistingList is set, it will completely replace the old list with the new list
        # NOTE: It won't check for duplicate entries or validate the list items,
        # it will blindly just append to what's already there

        # Take control of the mutex
        self.__accessRtpStreamEventListMutex.acquire()
        if replaceExistingList is False:
            # Default behaviour. Append the new events list to the existing list
            self.__eventList.extend(eventsList)
        else:
            # Completely replace the existing list with the newly supplied list
            self.__eventList=eventsList
        # Release the mutex
        self.__accessRtpStreamEventListMutex.release()
        # update the lastUpdated timestamp
        self.lastUpdatedTimestamp = datetime.datetime.now()
        # Now create a message for each event added (showing the summary for each event)
        for event in eventsList:
            try:
                Utils.Message.addMessage(event.getSummary()["summary"])
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpStreamresults.updateEventsList(), len " + str(len(eventsList)) +\
                                         ", " + str(e))


    # This method will remove this stream object from the rtpTxStreamResultsDict dictionary
    def killStream(self):
        pass

    # Define getter methods
    def getRTPStreamID(self):
        # Thread-safe method to access stream syncSource, src address, src port and name fields
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats["stream_syncSource"], stats["stream_srcAddress"], \
               stats["stream_srcPort"], self.__stats["stream_friendly_name"]

    # Thread-safe method for accessing all RtpStream stats
    def getRtpStreamStats(self, keyIs=None, keyContains=None, keyStartsWith=None, listKeys=False):
    # def getRtpStreamStats(self, **kwargs):
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        # Get a filtered version of the stats dict
        filteredStats = Utils.filterDictByKey(stats, keyIs=keyIs, keyContains=keyContains, keyStartsWith=keyStartsWith, listKeys=listKeys)
        return filteredStats


    def getRtpStreamStatsByFilter(self, keyFilter):
        # Thread-safe method to return specific stats who's dictionary key starts with 'filter'
        # Returns a list of tuples
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        # Filter keys of stats by startswith('filter') into a new dictionary
        filteredStats = {k: v for k, v in stats.items() if k.startswith(keyFilter)}
        return filteredStats

    def getRtpStreamStatsByKey(self, key):
        # Thread safe method to retrive a single stats item by key
        # If the key doesn't exist, it will return None type
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        if key in stats:
            return stats[key]
        else:
            return None

    # Thread-safe method for accessing realtime RtpStream eventList
    # No args: Returns the entire list
    # 1 arg: Returns the last n events
    # 2 args: returns the range specified (inclusive)
    # filterList is an optional arg containing a list of Event object types to test against within EventsList
    # eg filterList = [Glitch] will return only a list of glitches, [Glitch, StreamStarted] would give you a list
    # containing all Glitch and StreamStarted events
    # The filter (if present) is applied first, then the range specifier
    # Finally, if reverseOrder==True, the list will be returned in reverse order
    def getRTPStreamEventList(self, *args, filterList=None, reverseOrder=False, requestedEventNo=None,
                              recent=None, start=None, end=None):
        self.__accessRtpStreamEventListMutex.acquire()
        # Create copy of events list
        unfilteredEventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()

        # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
        # (or else, if kwarg 'start' and 'end' are  specified'
        if len(args) == 2:
            start = args[0]
            end = args[1]
        # If one arg supplied, return the last n events (or else, if kwarg 'recent' is specified'
        # IF event list not as long as n, return what does exist
        elif len(args) == 1:  # If non kwarg supplied, use that instead
            recent = args[0]

        # Filter the events list using the specified criteria
        filteredEventList = self.filterEventsList(unfilteredEventList, filterList=filterList, reverseOrder=reverseOrder,
                                                  requestedEventNo=requestedEventNo, recent=recent, start=start,
                                                  end=end)
        return filteredEventList

# Define an RTP Generator that can run autonomously as a thread
class RtpGenerator(RtpCommon):
    # How this works:
    # When started:-
    #   The RtpGenerator constructor  creates an instance of ResultsReceiver
    #   (which sets up a UDP receiver thread to collect the results sent by RtpReceiveStream at the far end)
    #   If the ResultsReceiver object does receive some data, it will spawn a RtpStreamResults object
    #   which will hold the stats and events for the performance of the RtpGenerator stream that started it all

    # On close:-
    #   The RtpGenerator.killStream() method will:-
    #       1)force the time to live to zero (which will cause the object to delete itself
    #       2)call the corresponding ResultsReceiver.kill() method which will:-
    #           1)Cause the the ResultsReceiver receive thread to cease (killing the object)
    #           2) Check to see if a corresponding RtpStreamResults object exists for this stream ID, and if so
    #              call it's RtpStreamResults.killStream() method. This will cause the object to remove itself
    #              from the rtpTxStreamResultsDict{} which will then mean the object ceases to exist also.


    # The size of the messages sent in the RtpGenerator payload
    # This can be queried by the class method getIsptestHeaderSize() (and is consumed by RtpReceiveStream and main())
    ISPTEST_HEADER_SIZE = 20

    # The maximum allowed stream friendly name length
    # This can be queried by the class method getMaxFriendlyNameLength() (and is consumed by RtpReceiveStream and main())
    MAX_FRIENDLY_NAME_LENGTH = 10

    # Specify a unique identifiying value (eg David's birthday) that will allow the reciever to
    # identify that this stream is being set by an isptest transmitter (this is a 16 bit unsigned
    # val, so 65535 is the max)
    UNIQUE_ID_FOR_ISPTEST_STREAMS = 10518

    # Constants. Used in the calculation of transmitted data rate
    UDP_HEADER_LENGTH_BYTES = 8
    RTP_HEADER_LENGTH_BYTES = 12

    # Constants. Used in the construction of the rtp header
    # rtpParams = 0b01000000
    rtpParams = Registry.rtpGeneratorRtpParams
    # rtpPayloadType = 0b00000000
    rtpPayloadType = Registry.rtpGeneratorRtpPayloadType


    @classmethod
    def getMaxFriendlyNameLength(cls):
        return cls.MAX_FRIENDLY_NAME_LENGTH

    @classmethod
    def getIsptestHeaderSize(cls):
        return cls.ISPTEST_HEADER_SIZE

    @classmethod
    def getUniqueIDforISPTESTstreams(cls):
        return cls.UNIQUE_ID_FOR_ISPTEST_STREAMS

    # Define a custom BaseHTTPRequestHandler class to handle HTTP GET, POST requests
    # NOTE: The actual do_GET(), do_POST and do_DELETE() methods are defined in and inherited from
    # my Utils.HTTPRequestHandlerRTP class
    class HTTPRequestHandler(Utils.HTTPRequestHandlerRTP):
        # Method to retrieve list of Events and return them as a list that is **already json encoded**
        def getEventsListAsJson(self, **kwargs):
            try:
                # Get a handle on the RtpStreamsResults object
                # This will fail if the object doesn;t exist yet
                rtpStreamResults = self.server.parentObject.relatedRtpStreamResults
                # Get the events list - pass in the kwargs
                eventsList = rtpStreamResults.getRTPStreamEventList(**kwargs)
                # Retrieve the event summaries as json
                eventsListJSON = [event.getJSON() for event in eventsList]

                # Create response by concatenating all the json events together
                concatenatedJSONList = "[" + ",".join(eventsListJSON) + "]"
                # Convert back to ASCII
                response = concatenatedJSONList.encode('utf-8')

                return response
            except Exception as e:
                return [str(e)]

        # Returns a list of Event summaries
        def getEventsSummaries(self, **kwargs):
            try:
                # Get a handle on the RtpStreamsResults object
                # This will fail if the object doesn;t exist yet
                rtpStreamResults = self.server.parentObject.relatedRtpStreamResults

                # Prefilter the kwargs to allow only the keys accepted by getRTPStreamEventList()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                                ["filterList", "reverseOrder", "requestedEventNo", "recent", "start", "end"])
                # Get the events list - pass in the kwargs
                eventsList = rtpStreamResults.getRTPStreamEventList(**filteredKwargs)

                # Prefilter the kwargs to allow only the keys accepted by Event.getSummary()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                    ["includeStreamSyncSourceID", "includeEventNo", "includeType", "includeFriendlyName"])
                # Create a list of Events summaries
                eventsListSummaries = [event.getSummary(**filteredKwargs) for event in eventsList]
                # Return the list
                return eventsListSummaries
            except Exception as e:
                return [str(e)]

        # Returns a list of Events as a list of csv strings
        def getEventsListAsCSV(self, **kwargs):
            try:
                # Get a handle on the RtpStreamsResults object
                # This will fail if the object doesn't exist yet
                rtpStreamResults = self.server.parentObject.relatedRtpStreamResults

                # Prefilter the kwargs to allow only the keys accepted by getRTPStreamEventList()
                filteredKwargs = Utils.extractWantedKeysFromDict(kwargs,
                                                                 ["filterList", "reverseOrder", "requestedEventNo",
                                                                  "recent", "start", "end"])
                # Get the events list - pass in the kwargs
                eventsList = rtpStreamResults.getRTPStreamEventList(**filteredKwargs)

                # Create a list of Events CSV exports
                eventsListAsCSV = [event.getCSV() for event in eventsList]
                # Return the list
                return eventsListAsCSV
            except Exception as e:
                return [str(e)]

        # Acts a repository for the GET endpoints provided by the RtpGenerator HTTP API
        def apiGETEndpoints(self):
            # Access parent Rtp Stream object via server attribute
            rtpGen = self.server.parentObject
            # A dictionary to map incoming GET URLs to an existing RtpGenerator method
            # The "args" key contains a lost with the preset values that will be passed to targetMethod() when
            # "optKeys" is a list of keys that  targetMethod will accept as a kwarg
            # that particular URL is requested
            # "contentType" is an additional key that specifies the type of data returned by targetMethod (if known)
            # The default behaviour of do_GET() will be to try and encode all targetMethod() return values as json
            # Some methods (eg getEventsListAsJson()) already return json, so there is no need to re-encode it
            # Additionally, the /report generation methods return plaintext so the "contentType" key is a means of
            # signalling to do_GET() how to handle the returned values
            getMappings = {
                #"/url": {"targetMethod": None, "args": [], "optKeys": [], "contentType": 'application/json'},
                "/": {"targetMethod": self.renderIndexPage, "args": [], "optKeys": [], "contentType": 'text/html'},
                "/debug": {"targetMethod": self.renderDebugPage, "args": [], "optKeys": []},
                "/txrate/inc": {"targetMethod": rtpGen.setTxRate, "args": [0, 1], "optKeys": []},
                "/txrate/dec": {"targetMethod": rtpGen.setTxRate, "args": [0, -1], "optKeys": []},
                "/length/inc": {"targetMethod": rtpGen.setPayloadLength, "args": [0, 1], "optKeys": []},
                "/length/dec": {"targetMethod": rtpGen.setPayloadLength, "args": [0, -1], "optKeys": []},
                "/ttl/inc": {"targetMethod": rtpGen.setTimeToLive, "args": [0, 1], "optKeys": []},
                "/ttl/dec": {"targetMethod": rtpGen.setTimeToLive, "args": [0, -1], "optKeys": []},
                "/burst": {"targetMethod": rtpGen.enableBurstMode, "args": [], "optKeys": []},
                "/enable": {"targetMethod": rtpGen.enableStream, "args": [], "optKeys": []},
                "/disable": {"targetMethod": rtpGen.disableStream, "args": [], "optKeys": []},
                "/jitter/on": {"targetMethod": rtpGen.enableJitter, "args": [], "optKeys": []},
                "/jitter/off": {"targetMethod": rtpGen.disableJitter, "args": [], "optKeys": []},
                "/txstats": {"targetMethod": rtpGen.getRtpStreamStats, "args": [], "optKeys": []},
                "/traceroute": {"targetMethod": rtpGen.getTraceRouteHopsList, "args": [], "optKeys": []}
            }
            # Add additonal endpoints that relate to the RtpStreamResults associated with this RtpGenerator
            # Note, this object (and therefore its methods) will only exist if the Receiver has responded to
            # the transmitter.
            # Therefore we can't assume that the methods will be available
            try:
                # Attempt to add a /stats endpoint
                getMappings["/stats"] = {"targetMethod": rtpGen.relatedRtpStreamResults.getRtpStreamStats,
                                         "args": [],
                                         "optKeys": ["keyIs", "keyContains", "keyStartsWith", "listKeys"]
                                         }
                getMappings["/events/json"] = {"targetMethod": self.getEventsListAsJson,
                                         "args": [],
                                         "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent", "start", "end",
                                                     ],
                                         "contentType": 'application/json' # <<--denotes that this fn returns json
                                         }
                getMappings["/events/csv"] = {"targetMethod": self.getEventsListAsCSV,
                                               "args": [],
                                               "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent",
                                                           "start", "end",
                                                           ],
                                               }

                getMappings["/events/summary"] = {
                    "targetMethod": self.getEventsSummaries,
                    "args": [],
                    "optKeys": ["filterList", "reverseOrder", "requestedEventNo", "recent", "start", "end"]+ \
                                ["includeStreamSyncSourceID", "includeEventNo", "includeType","includeFriendlyName"]
                    }
                getMappings["/report/summary"] = {"targetMethod": rtpGen.relatedRtpStreamResults.generateReport,
                                         "args": [],
                                         "optKeys": ["eventFilterList"],
                                         "contentType": 'text/plain' # <<--denotes that this fn returns plain text
                                         }
                getMappings["/report/traceroute"] = {"targetMethod": rtpGen.relatedRtpStreamResults.generateTracerouteHistoryReport,
                                                  "args": [],
                                                  "optKeys": ["historyLength"],
                                                  "contentType": 'text/plain'
                                                  # <<--denotes that this fn returns plain text
                                                  }
            except Exception as e:
                # Utils.Message.addMessage(f"ERR:RtpGenerator.HTTPRequestHandler.apiGETEndpoints() {e}")
                pass

            return getMappings

        # Acts a repository for the POST endpoints provided by the RtpGenerator HTTP API
        def apiPOSTEndpoints(self):
            # Access parent Rtp Stream object via server attribute
            rtpGen = self.server.parentObject
            # A dictionary to map incoming POST URLs to an existing RtpGenerator method
            # The keys/values within the POST data will be mapped to the keys listed in "args"[] and "kwargs"[]
            # "reqKeys"[] lists the mandatory parameters expected by targetMethod()
            # "optKeys"[] lists the optional key/value parameters that targetMethod() will accept
            #{"url path":
            #   {
            #       "targetMethod":target method/function,
            #       "reqKeys":[required arg1, required arg2..],    <---*only* the values are passed to the mapped function
            #       "optKeys":[optional arg1, arg2..]    <------the key/value pairs are passed to the function
            #   }
            postMappings = {
                "/label": {"targetMethod": rtpGen.setFriendlyName, "reqKeys": ["name"], "optKeys": []},
                "/txrate": {"targetMethod": rtpGen.setTxRate, "reqKeys": ["bps"], "optKeys": []},
                "/length": {"targetMethod": rtpGen.setPayloadLength, "reqKeys": ["bytes"], "optKeys": []},
                "/ttl": {"targetMethod": rtpGen.setTimeToLive, "reqKeys": ["seconds"], "optKeys": []},
                "/burst": {"targetMethod": rtpGen.enableBurstMode, "reqKeys": [], "optKeys": ["burstLength_s", "burstRatio"]},
                "/simulateloss": {"targetMethod": rtpGen.simulatePacketLoss, "reqKeys": [], "optKeys": ["packetsToSkip"]}
            }
            return postMappings

        # Acts a repository for the POST endpoints provided by the RtpGenerator HTTP API
        def apiDELETEEndpoints(self):
            # Access parent Rtp Stream object via server attribute
            rtpGen = self.server.parentObject
            deleteMappings = {"/delete": {"targetMethod": rtpGen.killStream, "reqKeys": [], "optKeys": []}}
            return deleteMappings

        # render HTML index page
        # Shown a list of available api endpoints
        def renderIndexPage(self):
            # Access parent Rtp Stream object via server attribute
            parent = self.server.parentObject
            try:
                syncSourceID = parent.syncSourceIdentifier
                response = f"<h1>Index page for {parent.__class__.__name__}:{syncSourceID}</h1>" \
                           f"{self.listEndpoints()}"
                return response
            except Exception as e:
                raise Exception(f"renderIndexPage() {parent.__class__.__name__}, {e}")

        # Display debug information
        def renderDebugPage(self):
            # Access parent RtpGenerator object via server attribute
            rtpGen = self.server.parentObject
            try:
                syncSourceID = rtpGen.syncSourceIdentifier
                debugInfoDict = {
                    "syncSourceID": syncSourceID,
                    "type": rtpGen.__class__.__name__,
                    "Sleep Time mean": rtpGen.meanSleepTime,
                    "Tx period": rtpGen.txPeriod,
                    "Total transmitted packets": rtpGen.txCounter_packets,
                    "Transmit error count": rtpGen.txErrorCounter,
                    "Traceroute function in use": str(rtpGen.tracerouteFunctionInUse),
                    "Active Threads": Utils.listCurrentThreads(asList=True)
                }
                # Add further info relating to the rtpStreamResultsReceiver
                if rtpGen.rtpStreamResultsReceiver is not None:
                    debugInfoDict["Rx unpickled error count"] = rtpGen.rtpStreamResultsReceiver.receiveDecodeErrorCounter
                    debugInfoDict["Rx fragment error count"] = rtpGen.rtpStreamResultsReceiver.receiveResultsFragmentErrorCounter
                    debugInfoDict["Return loss %"] = rtpGen.rtpStreamResultsReceiver.returnPacketLoss_pc
                    debugInfoDict["Rx packet count"] = rtpGen.rtpStreamResultsReceiver.receiveResultsActualReceivedPacketsCounter
                    debugInfoDict["Rx expected count"] = rtpGen.rtpStreamResultsReceiver.receiveResultsExpectedPacketsCounter

                return debugInfoDict

            except Exception as e:
                raise Exception(f"renderDebugPage() {rtpGen.__class__.__name__}, {e}")

    def __init__(self, UDP_TX_IP, UDP_TX_PORT, txRate, payloadLength, syncSourceID, timeToLive, \
                 uiInstance=None,
                 controllerTCPPort=None, **kwargs):
        # The last arguments (**kwargs) are optional. it allows you to specify a source port or friendly name on creation
        # kwargs are "friendlyName" and "UDP_SRC_PORT"

        # Call super constructor
        super().__init__()

        # Assign instance variables
        self.controllerTCPPort = controllerTCPPort  # the TCP listener port of the HTTP Server running on the controller process
        # Create an API helper to allow access to the HTTP API of the Controller
        self.ctrlAPI = Utils.APIHelper(self.controllerTCPPort)
        self.UDP_TX_IP = UDP_TX_IP  # The destination address
        self.UDP_TX_PORT = int(UDP_TX_PORT)
        self.UDP_TX_SRC_PORT = 0
        self.txRate = int(txRate)
        self.txPeriod = 0  # Calculated from self.txRate and set by RtpGenerator.calculateTxPeriod()
        self.resetSleepPeriodFlag = False # Used to force __rtpGeneratorThread.txScheduler.CalculateSleepPeriod() to reset
                                        # it's initial time calculation. This seems to be required if the ssh connection
                                        # to the transmitter fails, or the transmitter laptop/PC goes to 'sleep'
                                        # in which  case, when the transmitter wakes up again, the calculateSleepPeriod()
                                        # function attempts to 'catch up' leading to excessive tx rates way beyond
                                        # that specified
        self.payloadLength = int(payloadLength)
        self.txCounter_bytes = 0
        self.txCounter_packets = 0 # Counts the number of successful transmissions. Note. the 'bytes tx'd message'
                                    # embedded within the isptest header will always be at least less by one because
                                    # this value is incremented after a successul transmission by socket.sendto()
        self.txActualTxRate_bps = 0 # Used to 'sample' the actual tx rate
        self.syncSourceIdentifier = int(syncSourceID)
        self.regeneratePayloadFlag = True   # A flag to specify the the 'dummy data' should be recalculated during the
                                            # next call to RtpGenerator.prepareNextRtpPacket()

        # Create bytearray to hold the actual data to be transmitted over the wire
        # As a minimum, this will be decared with a default length large enough to hold the rtp and isptest headers
        # In due course, an additional payload of random data will be appended to it
        self.udpTxData = bytearray(RtpGenerator.RTP_HEADER_LENGTH_BYTES + RtpGenerator.getIsptestHeaderSize())
        self.rtpSequenceNo = 0 # The incrementing index within the rtp header
        self.elapsedTime = datetime.timedelta()
        self.friendlyName = ""
        self._tracerouteHopsList = []  # A list of tuples containing [IP octet1, IP octet2, IP octet3, Ipopctet4]
                                        # Should only be accessed by the setter/getter methods
        self.tracerouteHopsListMutex = threading.Lock() # Protects tracerouteHopsListMutex
        self.tracerouteHopsListLastUpdated = None # Timestamps the last successful traceroute update
        self.tracerouteCarouselIndexNo = 0  # Keeps track of which traceroute hop value is currently being transmitted
                                            # in the isptest header (in RtpGenerator.generateIsptestHeader()

        self.tracerouteChecksum = 0# Calculated by XORing an entire hops list, once it's been successfully validated

        self.isptestHeaderMessageIndex = 0 # Keeps track of which type of message we are sending in the header
        self.noOfMessageTypes = 8 # The current message types are:
                                    # 0 Traceroute
                                    # 1 private LAN Address of the local interface used for transmitting
                                    # 2 The 'public' destination address
                                    # 3 The current version of isptest
                                    # 4 The specified TX rate
                                    # 5 The transmitted packet count
                                    # 6 The stream time to live (in seconds)
                                    # 7 The return loss (as measured by the ResultsReceiver)

        self.uiInstance = uiInstance   # This allows access to the methods of the UI class
        # self.minSleepTime = None
        # self.maxSleepTime = None
        self.meanSleepTime = 0
        # self.minCalculationTime = None
        # self.maxCalculationTime = None
        # self.meanCalculationTime = None
        self.txErrorCounter = 0 # Counts the no. of transmit errors reported by the transmit thread

        # Query the routing table to determine the address of the Ethernet interface that will be used to transmit
        self.SRC_IP_ADDR = Utils.get_ip(self.UDP_TX_IP)
        Utils.Message.addMessage("Transmitting from " + str(self.SRC_IP_ADDR))

        # Attempt to set the friendly name from the optional supplied kwargs
        try:
            # If name supplied
            if kwargs["friendlyName"] != "":
                # If the name is not empty
                self.setFriendlyName(kwargs["friendlyName"])
            else:
                # If the name is empty set friendly name to be the same as the sync source ID
                self.setFriendlyName(self.syncSourceIdentifier)
        except Exception as e:
            # Utils.Message.addMessage("RTP Gen: " + str(e))
            # If not, set friendly name to be the same as the sync source ID
            self.setFriendlyName(self.syncSourceIdentifier)

        # Attempt to determine whether a UDP source port was specified in kwargs and whether it was valid
        try:
            if int(kwargs["UDP_SRC_PORT"]) > 1024:
                self.UDP_TX_SRC_PORT = int(kwargs["UDP_SRC_PORT"])
            else:
                self.UDP_TX_SRC_PORT = 0
                Utils.Message.addMessage("INFO: RtpGenerator.__init__() Invalid source port specified " + str(kwargs["UDP_SRC_PORT"]))
        # Can't extract src port from kwargs
        except Exception as e:
            self.UDP_TX_SRC_PORT = 0


        self.timeToLive = int(timeToLive)
        self.enablePacketGeneration = True
        self.packetsToSkip = 0 # Set by simulatePacketLoss()
        self.jitterGenerationFlag = False
        self.udpTxSocket = 0 # This is pointer to the socket created by __rtpGeneratorThread

        self.burstTimer = 0 # Used to count seconds when Generator is in Burst mode
        # Slowstart variables - This creates a logarithmic increase in the  tx rate at the start of the stream.
        # Its purpose is to allow the network hardware/CPUs to ramp up resources gradually when using high bitrates
        # No of packets to have been transmitted between each increase in the controlled tx rate
        self.slowStartPacketInterval = 10 # Eg Every 10 packets sent, the rate will be allowed to increase
        self.slowStartTxRateDivisor = 1.5 # The amount by which the prev tx period is divided by, to get the next
                                            # A smaller number will mean a longer ramp-up time
                                            # A bigger number will mean a much quicker ramp up to the target tx rate
        self.slowStartActiveFlag = True    # Flag to indicate whether slowStart is active
        self.slowStartInitialTxPeriod = 0.1    # The starting tx period, i.e 100 mS, or 10 packets per second

        self.pid = os.getpid()  # Stores the processID (which is transmitted as part of the isptestheader data
                                # Allows the Receiver to determine whether the transmitter instance has changed

        # Create a FIFO queue to hold control messages/instructions. These will be picked up in the __samplingThread
        # This messages can be used to modify the RtpGenrator parameters as an alternative to calling the
        # various setxx() methods directly
        # The ResultsReceiver.__resultsReceiverThread() is able to receive control messages from the corresponding
        # RECEIVER instance, and will put the received control messages onto the controlMessageQueue
        # self.addControlMessage() will put a message onto the queue
        # self.parseControlMessage() will decode a message

        # Each message is a dictionary of at least length = 3
        #{syncSourceID: int, source: String, type: String}
        # The first element of the list is a number which identifies the sync source ID
        # The second element is a string that identifies the source of message (bot sure how this will be used yet)
        # The third  element is a string that identifies the type of message
        # current message types are:
        #   {"txbps_inc"} Increase the tx bitrate
        #   {"txbps_dec"} Decrease the tx bitrate
        self.__controlMessageQueue = SimpleQueue()


        ######## Actual code starts here
        # Start the traffic generator thread
        self.rtpGeneratorThread = threading.Thread(target=self.__rtpGeneratorThread, args=())
        self.rtpGeneratorThread.daemon = False
        self.rtpGeneratorThread.setName(str(self.syncSourceIdentifier) + ":RtpGenerator")
        self.rtpGeneratorThread.start()

        self.tracerouteFunctionInUse = None     # Will be a label set by __traceRouteThread. Indicates which OS-dependant
                                                # traceroute function is to be used

        # Test the Registry var. If traceroute is enabled, create and start the thread
        if Registry.rtpGeneratorEnableTraceroute:
            self.tracerouteThread = threading.Thread(target=self.__tracerouteThread, args=())
            self.tracerouteThread.setName(str(self.syncSourceIdentifier) + ":tracerouteThread")
            self.tracerouteThread.daemon = False
            self.tracerouteThread.start()


        # create a stream results receiver object for this tx stream
        self.rtpStreamResultsReceiver = ResultsReceiver(self)

        # create a placeholder for the related RtpStreamResults object
        # This will be updated by rtpStreamResultsReceiver once it has successfullly created the RtpStreamResults object
        # (but only if the reply packets from the Receiver have been received)
        self.relatedRtpStreamResults = None

        # start the 1 second sampling thread
        self.samplingThread = threading.Thread(target=self.__samplingThread, args=())
        self.samplingThread.daemon = False
        self.samplingThread.setName(str(self.syncSourceIdentifier) + ":samplingThread")
        self.samplingThread.start()

        # Create an HTTP server thread. If successful, register the stream
        try:
            # Request an unused TCP port for the HTTP server to listen on
            self.tcpListenPort = Utils.TCPListenPortCreator.getNext()
            Utils.Message.addMessage(f"DBUG: Creating httpServerThread for RtpGenerator:{self.syncSourceIdentifier}, TCP port:{self.tcpListenPort}")
            self.httpServerThread = threading.Thread(target=self.httpServerThreadCommon,
                                                     args=(self.tcpListenPort,
                                                           self.syncSourceIdentifier,
                                                           RtpGenerator.HTTPRequestHandler))
            self.httpServerThread.daemon = False
            self.httpServerThread.setName(f"{self.syncSourceIdentifier}:httpServerThread({self.tcpListenPort})")
            self.httpServerThread.start()

            # Verify that the http server is actually running, by attempting to connect it
            r = requests.get(f"http://127.0.0.1:{self.tcpListenPort}", timeout=1)
            r.raise_for_status()  # Will raise an Exception if there was a problem
            Utils.Message.addMessage(
                f"INFO:RTPGenerator({self.syncSourceIdentifier}) http server started on port {self.tcpListenPort}")

        except Exception as e:
            Utils.Message.addMessage(f'ERR:RTPGenerator.__init__() Couldn\'t create httpServerThread {self.syncSourceIdentifier}, {e}')

        # Now register the stream with the stream directory service
        # Note: If this fails, __samplingThread performs a 1 sec check to see if registration was successful,
        # and if not, attempts to re-add the stream
        try:
            # Create a dict to define the stream
            streamDefinition = {
                "streamID": self.syncSourceIdentifier,
                "httpPort": self.tcpListenPort,
                "streamType": "RtpGenerator"
            }
            # Register the stream
            self.ctrlAPI.addToStreamsDirectory(streamDefinition)
        except Exception as e:
            Utils.Message.addMessage(
                f'ERR:RTPGenerator.__init__() Initial stream Registration failed {self.syncSourceIdentifier}, {e}')

    def getRtpStreamStats(self):
        # Returns a dictionary of useful stats
        return {'Dest IP': self.UDP_TX_IP,
                'Dest Port': self.UDP_TX_PORT,
                'Tx Rate': self.txRate,
                'Tx Rate (actual)': self.txActualTxRate_bps,
                'Packet size': self.payloadLength,
                'Bytes transmitted': self.txCounter_bytes,
                'Sync Source ID': self.syncSourceIdentifier,
                'stream_syncSource': self.syncSourceIdentifier, # Duplicate entry to harmonise with RtpReceiveStream and RtpStreamResults
                'Elapsed Time': self.elapsedTime,
                'Friendly Name': self.friendlyName,
                'stream_friendly_name': self.friendlyName, # Duplicate entry to harmonise with RtpReceiveStream and RtpStreamResults
                'Tx Source Port': self.UDP_TX_SRC_PORT,
                'Time to live': self.timeToLive,
                'Sleep Time mean': self.meanSleepTime,
                #'Calculation time mean': self.meanCalculationTime,
                'Tx period': self.txPeriod,
                'simulateJitterStatus': self.getJitterStatus(),
                'streamEnabledStatus': self.getEnableStreamStatus()
                }

    def getRtpStreamStatsByKey(self, key):
        # Method to retrieve a single stats item by key
        # If the key doesn't exist, it will return None type
        stats = self.getRtpStreamStats()
        if key in stats:
            return stats[key]
        else:
            return None

    def setFriendlyName(self, friendlyName):
        # Ultimately this name will be transmitted as part of the stream (so that the receiver
        # can auto-set the friendly name of the stream at the rx end)
        # Currently it just sets an instance variable

        # convert friendlyName into a string
        friendlyName=str(friendlyName)
        # Truncate supplied name to x characters (truncated to preserve the screen layout) or else pad to 12 chars
        if len(friendlyName) < RtpGenerator.MAX_FRIENDLY_NAME_LENGTH:
            # Too short, so Pad out name to x chars
            friendlyName += (RtpGenerator.MAX_FRIENDLY_NAME_LENGTH - len(friendlyName)) * " "
        else:
            # Too big, so truncate
            friendlyName = friendlyName[:RtpGenerator.MAX_FRIENDLY_NAME_LENGTH]
        # assign to instance variable
        self.friendlyName = friendlyName


    def generatePayload(self, payloadLength):
        # Generate random byte string of length 'length' to create a payload of length self.payloadLength

        # Create byte string containing all uppercase and lowercase letters
        letters = string.ascii_letters
        # iterate over stringLength picking random letters from 'letters'
        randomDataString = ''.join(random.choice(letters) for i in range(payloadLength))

        # Return as a bytestring
        return randomDataString.encode('ascii')

    # Generates the isptest (this program) specific header to convey extra info (like the friendly name) to the receiver
    def generateIsptestHeader(self):
        # Generate the 'isptest' header
        # Header currently consists of 20 bytes of data NOTE. This is defined in RtpGenerator.getIsptestHeaderSize():
        # [uniqueValue(David's birthday)(short, 2 bytes)
        # plus....
        # [byte1] Message type (0: Traceroute)
        # [byte2] Hop no
        # [byte3] Total no of hops
        # [byte4][byte5][byte6][byte7] Hop id address octets
        # [byte8] traceroute Checksum value (consisisting of all the hop Octets XORd together)
        # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (1: SRC IP address (the local LAN address of the transmitting machine)
        #         # [byte2] src port (MSB)
        #         # [byte3] src port (LSB)
        #         # [byte4][byte5][byte6][byte7] local ip address octets
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (2: DST IP address) (the destination PUBLIC address that the transmitter is sending to)
        #         # [byte2] 0/not used
        #         # [byte3] 0/not used
        #         # [byte4][byte5][byte6][byte7] dest ip address octets
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (3: Transmitter isptest version no. and PID of transmitter process
        #         # [byte2] major version no
        #         # [byte3] minor version no
        #         # [byte4][byte5][byte6][byte7] Carries the pid of the transmitter process
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (4: Transmitter tx bitrate.
        #         # [byte2]
        #         # [byte3]
        #         # [byte4][byte5][byte6][byte7] tx bitrate as an unsigned long (4 bytes)
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (5: Transmitter tx total packets sent.
        #         # [byte2]
        #         # [byte3]
        #         # [byte4][byte5][byte6][byte7] total packets sent as an unsigned long (4 bytes)
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (6: Tx stream time to live (in seconds).
        #         # [byte2]
        #         # [byte3]
        #         # [byte4][byte5][byte6][byte7] time to live as a signed int (4 bytes) (ttl can be -ve)
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (7: The return loss (from Receiver to Transmitter).
        #         # [byte2]
        #         # [byte3]
        #         # [byte4][byte5][byte6][byte7] return loss, float 4 bytes
        #         # [byte8] not used
        #         # [friendlyName] 10 bytes


        header = b""  # Specify byte string
        # Initialise messageData to zero
        messageData = [0,0,0,0,0,0,0]
        try:
            # Note: a short is 16 bits - max value 65535
            uniqueValue = RtpGenerator.UNIQUE_ID_FOR_ISPTEST_STREAMS & 0xFFFF
            # Test what type of message we are scheduled to send
            if self.isptestHeaderMessageIndex == 0:
                # This is traceroute message - Get copy of tracerouteHopsList[]
                # We don't want to hold up the transmission of packets, so instruct getTraceRouteHopsList to not block
                tracerouteLastUpdate, tracerouteHopsList = self.getTraceRouteHopsList(allowBlocking=False)
                # Check to see that we have received a valid hopslist
                if tracerouteHopsList is not None:
                    # Transmit each element of the self.tracerouteHopsList sequentially (as a carousel)
                    hopsListLength = len(tracerouteHopsList)
                    if hopsListLength > 0:
                        # Get the hop to be transmitted
                        # Initialise with default value
                        hopToBeTransmitted = [0,0,0,0]
                        try:
                            # Test to ensure that self.tracerouteCarouselIndexNo array index is within range
                            if self.tracerouteCarouselIndexNo > (hopsListLength - 1):
                                # If so, reset it to zero to avoid an out-of-range index error
                                self.tracerouteCarouselIndexNo = 0
                            # Now grab the hop pointed to by self.tracerouteCarouselIndexNo
                            hopToBeTransmitted = tracerouteHopsList[self.tracerouteCarouselIndexNo]
                        except Exception as e:
                            Utils.Message.addMessage(
                                "ERR: RtpGenerator.generateIsptestHeader():traceroute_gethopToBeTransmitted index no:" +\
                                str(self.tracerouteCarouselIndexNo) + ", len(tracerouteHopsList): " + \
                                str(len(tracerouteHopsList)) + ", " + str(e))
                        # Now construct the actual message
                        try:
                            messageData = [0 & 0xFF,  # Message type 0: traceroute
                                           self.tracerouteCarouselIndexNo & 0xFF,  # Traceroute Hop no
                                           hopsListLength & 0xFF,  # # Traceroute total no of hops
                                          hopToBeTransmitted[0] & 0xFF,  # IP address octet 1
                                          hopToBeTransmitted[1] & 0xFF,  # IP address octet 2
                                          hopToBeTransmitted[2] & 0xFF,  # IP address octet 3
                                          hopToBeTransmitted[3] & 0xFF,  # IP address octet 4
                                            self.tracerouteChecksum & 0xFF]  # hopList checksum
                            # Now increment the carousel index so that the next hop value will be transmitted the next time this
                            # method is called
                            self.tracerouteCarouselIndexNo += 1

                        except Exception as e:
                            Utils.Message.addMessage("ERR: RtpGenerator.generateIsptestHeader():traceroute_create message " + str(e))
                    else:
                        # Retrieved tracerouteHopsList was empty
                        # Create a dummy traceroute message
                        messageData = [0 & 0xFF,  # Message type 0: traceroute
                                       0 & 0xFF,  # Traceroute Hop no
                                       0 & 0xFF,  # Traceroute total no of hops
                                       0 & 0xFF,  # IP address octet 1
                                       0 & 0xFF,  # IP address octet 2
                                       0 & 0xFF,  # IP address octet 3
                                       0 & 0xFF,  # IP address octet 4
                                       0 & 0xFF]  # hopList checksum
                else:
                    # Unable to retrieve tracerouteHopsList
                    # Create a dummy traceroute message
                    messageData = [0 & 0xFF,  # Message type 0: traceroute
                                   0 & 0xFF,  # Traceroute Hop no
                                   0 & 0xFF,  # Traceroute total no of hops
                                   0 & 0xFF,  # IP address octet 1
                                   0 & 0xFF,  # IP address octet 2
                                   0 & 0xFF,  # IP address octet 3
                                   0 & 0xFF,  # IP address octet 4
                                   0 & 0xFF]  # hopList checksum

            elif self.isptestHeaderMessageIndex == 1:
                # This is a 'local adapter IP address and src port' message
                localAddr = str(self.SRC_IP_ADDR).split(".") # Seperate out the address octets into a list
                srcPortMSB = self.UDP_TX_SRC_PORT >> 8  # Isolate the top byte of the source port
                srcPortLSB = self.UDP_TX_SRC_PORT & 0xFF # Isolate the bottom byte of the source port
                try:
                    # Create the message data
                    messageData = [1 & 0xFF,  # Message type 1: src (local) ip address
                                   srcPortMSB & 0xFF,  # Top byte (MSB) of the source port
                                   srcPortLSB & 0xFF,  # Bottom byte (LSB) of the source port
                                   int(localAddr[0]) & 0xFF,  # IP address octet 1
                                   int(localAddr[1]) & 0xFF,  # IP address octet 2
                                   int(localAddr[2]) & 0xFF,  # IP address octet 3
                                   int(localAddr[3]) & 0xFF,  # IP address octet 4
                                    0 & 0xFF]  # not used
                except Exception as e:
                    messageData = [1 & 0xFF,  # Message type 0: traceroute
                                   0 & 0xFF,  # Top byte (MSB) of the source port
                                   0 & 0xFF,  # Bottom byte (LSB) of the source port
                                   0 & 0xFF,  # IP address octet 1
                                   0 & 0xFF,  # IP address octet 2
                                   0 & 0xFF,  # IP address octet 3
                                   0 & 0xFF,  # IP address octet 4
                                    0 & 0xFF]  # not used
                    Utils.Message.addMessage("DBUG:RtpGenerator.generateIsptestHeader(): tx local adapter addr " + str(e))

            elif self.isptestHeaderMessageIndex == 2:
                # This is a 'destination IP address' message
                destAddr = str(self.UDP_TX_IP).split(".") # Seperate out the address octets into a list
                try:
                    # Create the message data
                    messageData = [2 & 0xFF,  # Message type 1: src (local) ip address
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   int(destAddr[0]) & 0xFF,  # IP address octet 1
                                   int(destAddr[1]) & 0xFF,  # IP address octet 2
                                   int(destAddr[2]) & 0xFF,  # IP address octet 3
                                   int(destAddr[3]) & 0xFF,  # IP address octet 4
                                   0 & 0xFF]  # not used
                except Exception as e:
                    messageData = [2 & 0xFF,  # Message type 2: destination addr
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # IP address octet 1
                                   0 & 0xFF,  # IP address octet 2
                                   0 & 0xFF,  # IP address octet 3
                                   0 & 0xFF,  # IP address octet 4
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage("DBUG:RtpGenerator.generateIsptestHeader(): tx dest addr " + str(e))

            elif self.isptestHeaderMessageIndex == 3:
                # This is 'isptest version'  and also PID message
                try:
                    # Split the version no into a major and minor part
                    version = str(Registry.version).split('.')
                    # encode pid (process ID) as a series of four bytes (unsigned long, 4 bytes)
                    pidAsBytes = struct.pack("!L", self.pid & 0xFFFFFFFF)
                    messageData = [3 & 0xFF,  # Message type 3: Destination addr
                                   int(version[0]) & 0xFF,  # Major version no
                                   int(version[1]) & 0xFF,  # Minor version no
                                   pidAsBytes[0] & 0xFF,  # PID MSB
                                   pidAsBytes[1] & 0xFF,  #
                                   pidAsBytes[2] & 0xFF,  #
                                   pidAsBytes[3] & 0xFF,  # PID LSB
                                   0 & 0xFF]  # not used
                except Exception as e:
                    messageData = [3 & 0xFF,  # Message type 3: Destination addr
                                   0 & 0xFF,  # Major version no
                                   0 & 0xFF,  # Minor version no
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage("DBUG:RtpGenerator.generateIsptestHeader(): tx version info " + str(e))

            elif self.isptestHeaderMessageIndex == 4:
                # Transmitter tx bitrate message
                # encode rate as a series of four bytes (unsigned long, 4 bytes)
                try:
                    # Split txRate into a series of bytes
                    txRateAsBytes = struct.pack("!L", self.txRate & 0xFFFFFFFF)
                    messageData = [4 & 0xFF,  # Message type 4: Transmit rate (the specified rate)
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   txRateAsBytes[0] & 0xFF,  # MSB
                                   txRateAsBytes[1] & 0xFF,  #
                                   txRateAsBytes[2] & 0xFF,  #
                                   txRateAsBytes[3] & 0xFF,  # LSB
                                   0 & 0xFF]  # not used

                except Exception as e:
                    messageData = [4 & 0xFF,  # Message type 4: Transmit rate (the specified rate)
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage("DBUG:RtpGenerator.generateIsptestHeader(): Message type 4: Transmit rate " + str(e))

            elif self.isptestHeaderMessageIndex == 5:
                # Transmitter tx total packets sent
                try:
                    # Split txRate into a series of bytes
                    txdPackets = struct.pack("!L", self.txCounter_packets & 0xFFFFFFFF)
                    messageData = [5 & 0xFF,  # Message type 5: Transmitter total packets sent
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   txdPackets[0] & 0xFF,  # MSB
                                   txdPackets[1] & 0xFF,  #
                                   txdPackets[2] & 0xFF,  #
                                   txdPackets[3] & 0xFF,  # LSB
                                   0 & 0xFF]  # not used

                except Exception as e:
                    messageData = [5 & 0xFF,  # Message type 5: Transmit rate (the specified rate)
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage(
                        "DBUG:RtpGenerator.generateIsptestHeader(): Message type 5: Transmit total packets " + str(e))

            elif self.isptestHeaderMessageIndex == 6:
                # Transmitter tx stream time to live (in seconds)
                try:
                    # Split ttl into a series of bytes
                    timeToLive = struct.pack("!i", self.timeToLive)
                    messageData = [6 & 0xFF,  # Message type 6: # Transmitter tx stream time to live (in seconds)
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   timeToLive[0] & 0xFF,  # MSB
                                   timeToLive[1] & 0xFF,  #
                                   timeToLive[2] & 0xFF,  #
                                   timeToLive[3] & 0xFF,  # LSB
                                   0 & 0xFF]  # not used

                except Exception as e:
                    messageData = [6 & 0xFF,  # Message type 6: # Transmitter tx stream time to live (in seconds)
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage(
                        "DBUG:RtpGenerator.generateIsptestHeader(): Message type 6: Transmit tx stream time to live " + str(e))

            elif self.isptestHeaderMessageIndex == 7:
                # Return loss from Receiver to Transmitter, float 4 bytes, %
                try:
                    # Get return packet loss value from related ResultsReceiver object
                    returnPacketLoss_pc = struct.pack("!f", self.rtpStreamResultsReceiver.returnPacketLoss_pc)
                    messageData = [7 & 0xFF,  # Message type 7: # Return loss from Receiver to Transmitter, float 4 bytes
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   returnPacketLoss_pc[0] & 0xFF,  # MSB
                                   returnPacketLoss_pc[1] & 0xFF,  #
                                   returnPacketLoss_pc[2] & 0xFF,  #
                                   returnPacketLoss_pc[3] & 0xFF,  # LSB
                                   0 & 0xFF]  # not used

                except Exception as e:
                    messageData = [7 & 0xFF,  # Message type 7: # Return loss from Receiver to Transmitter, float 4 bytes
                                   0 & 0xFF,  #
                                   0 & 0xFF,  #
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage(
                        "DBUG:RtpGenerator.generateIsptestHeader(): Message type 7: Return loss " + str(e))

            # Now That the message data list has been created, increment the message type index
            self.isptestHeaderMessageIndex += 1
            # Send only the specific 'tx packets sent' (message type #5)
            # self.isptestHeaderMessageIndex =5

            # Bounds check isptestHeaderMessageIndex
            if self.isptestHeaderMessageIndex >=self.noOfMessageTypes:
                self.isptestHeaderMessageIndex = 0


            # Now assemble the header
            header = struct.pack("!HBBBBBBBB", uniqueValue, messageData[0], messageData[1], messageData[2], \
                                 messageData[3], messageData[4], messageData[5], messageData[6], messageData[7])

            # Append friendly name to header digits
            header += str(self.friendlyName).encode('ascii')
            # Calculate total header length
            headerLength = len(header)
            # Check to see that we haven't tried to create a header thats longer than that specified
            # by the class var ISPTEST_HEADER_SIZE
            if headerLength != RtpGenerator.ISPTEST_HEADER_SIZE:
                Utils.Message.addMessage(
                    "INFO: RtpGenerator.generatePayload() Mismatch between headerLength and RtpGenerator.ISPTEST_HEADER_SIZE. Setting header to be blank ")
                # The length of the header we've created doesn't match that specifed by RtpGenerator.ISPTEST_HEADER_SIZE therefore
                # main() and RtpReceiveStream objects will be expecting the wrong length header and won't be able to
                # decode it
                header = b""

        except Exception as e:
            Utils.Message.addMessage("ERR: RtpGenerator.generateIsptestHeader(). Header err: " + str(e))

        # Return the isptestheader data (as a bytestring)
        return header

    def setSyncSourceIdentifier(self, value):
        # Sets the self self.syncSourceIdentifier value
        # This is only allowed to be 32 bits long (specified by the RTP header)
        # so mask input value for safety
        if value < 0:
            value = 0
        maskedValue = value & 0xFFFFFFFF
        self.syncSourceIdentifier=maskedValue

    def calculateTxPeriod(self, newTxRate_bps):
        UDP_HEADER_LENGTH_BYTES = 8
        RTP_HEADER_LENGTH_BYTES = 12
        # Calculates the required tx period for a given supplied txRate and payload length
        # Takes into account the UDP and RTP headers, to hopefully derive a true 'interface' rate
        txPeriod = (self.payloadLength + UDP_HEADER_LENGTH_BYTES + RTP_HEADER_LENGTH_BYTES) * 8.0 / newTxRate_bps
        return txPeriod

    # Modify the tx rate of the RtpGenerator stream.
    # Additionally, if autoIncrement or autoDecrement are set, the first argument (newTxRate_bps) will be ignored
    # and instead, the method will increase/decrease the tx rate by a fixed amount relative to the current rate
    # if autoIncrement = 1, the rate will increase, if autoIncrement = -1, the rate will decrease
    def setTxRate(self, newTxRate_bps, autoIncrement=None):

        # Check to see whether newTxRate_bps is an integer. If not, raise an Exception
        if is_integer(newTxRate_bps):
            pass
        else:
            raise Exception(f"RtpGenerator({self.syncSourceIdentifier}).setTxrate() Invalid newTxRate_bps: {newTxRate_bps}")

        # Snaps the incoming value to 1024 so that autoIncrements/decrements will settle on a neat value (i.e in
        # steps of 1024bps). See https://stackoverflow.com/questions/2272149/round-to-5-or-other-number-in-python
        # Snap value is overridden by setting base= value
        def snapTo(x, base=1024):
            return base * round(x / base)
        txRateChange_bps = 0
        # calculate step change value (up or down) based on current txRate
        # If 100kbps or less, change in 10kbps steps
        if self.txRate <= 102400:
            txRateChange_bps = 10240
        # Special case. If tx rate is currently 256kbps or less AND is being decremented, use 10kbps steps
        elif (self.txRate <= 262144) and (autoIncrement == -1):
            txRateChange_bps = 10240
        # Else if tx rate between 100kbps and 1Mbps, change in 256kbps steps
        elif self.txRate <= 1048576:
            txRateChange_bps = 262144
        # Otherwise change in 512kbps steps
        else:
            txRateChange_bps = 524288

        # Check to see if autoIncrement or autoDecrement have been set. If so, override newTxRate_bps value
        if autoIncrement == 1:
            # Auto increment is set
            newTxRate_bps = snapTo(self.txRate + txRateChange_bps, base=txRateChange_bps)
        elif autoIncrement == -1:
            # Auto decrement is set
            newTxRate_bps = snapTo(self.txRate - txRateChange_bps, base=txRateChange_bps)


        # Confirm that the new TX rate isn't below the minimum permitted
        if newTxRate_bps < Registry.minimumPermittedTXRate_bps:
            newTxRate_bps = Registry.minimumPermittedTXRate_bps

        Utils.Message.addMessage("Setting new tx rate " + str(Utils.bToMb(newTxRate_bps)) + \
                                 "bps, for stream " + str(self.syncSourceIdentifier))

        # Update instance variable
        self.txRate = newTxRate_bps
        # Calculate then set the new txPeriod for a given newTxRate_bps
        self.txPeriod = self.calculateTxPeriod(newTxRate_bps)

    # Modifies the payload length of this RTP TX stream
    # If autoIncrement is set to -1 or 1, payload will be incremented or decremented by 10 bytes
    # and the payloadLength_bytes argument will be ignored
    def setPayloadLength(self, payloadLength_bytes, autoIncrement=None):
        # Function used to ensure a nice snap-to value when auto incrementing/decrementing
        def snapTo(x, base=10):
            return base * round(x / base)

        # Check to see whether payloadLength_bytes is an integer. If not, raise an Exception
        if is_integer(payloadLength_bytes):
            pass
        else:
            raise Exception(
                f"RtpGenerator({self.syncSourceIdentifier}).setTxrate() Invalid payloadLength_bytes: {payloadLength_bytes}")

        if autoIncrement == 1:
            # override supplied value and just increment existing value
            payloadLength_bytes = self.payloadLength + 10
        elif autoIncrement == -1:
            # override supplied value and just increment existing value
            payloadLength_bytes = self.payloadLength - 10

        # Snap the value to the nearest '10'
        payloadLength_bytes = snapTo(payloadLength_bytes)

        # Bounds check new supplied/calculated value
        if payloadLength_bytes > 1488:
            payloadLength_bytes = 1488
        if payloadLength_bytes < 20:
            payloadLength_bytes =20

        # Set instance variable
        self.payloadLength = payloadLength_bytes
        # Trigger regeneration of entire udp data frame (rtp header + isptest header + dummy payload)
        # self.generatePayload()
        self.regeneratePayloadFlag = True
        # Recalculates the tx period based on the new packet length
        self.txPeriod = self.calculateTxPeriod(self.txRate)

    # Modifies the existing time to live value
    # Setting this to a -ve value will mean the tx stream object last for ever
    # If autoIncrement = 1, the method will auto add a certain amount of time to the lifetime
    # If autoIncrement = -1, the method will auto decrement a certain amount of time from the lifepan
    def setTimeToLive(self, newTimeToLive, autoIncrement=None):
        # Check to see whether newTimeToLive is an integer. If not, raise an Exception
        if is_integer(newTimeToLive):
            pass
        else:
            raise Exception(
                f"RtpGenerator({self.syncSourceIdentifier}).setTxrate() Invalid newTimeToLive: {newTimeToLive}")

        if autoIncrement is None:
            self.timeToLive = newTimeToLive
        else:
            # Calculate the amount to decrement by
            # If current time to live less than 1hr, change time in 10 min increments
            # Otherwise change ttl by 1hr
            if self.timeToLive < 3600: # 1hr
                delta = 600 # 10 minutes
            elif (self.timeToLive < 4300) and (autoIncrement == -1): # 1hr 10mins and decrementing
                delta = 600
            else:
                delta = 3600 # 1 hr

            # calculate new ttl
            newTTL = 0
            if autoIncrement == -1:
                newTTL = self.timeToLive - delta
            elif autoIncrement == 1:
                newTTL = self.timeToLive + delta
            # Bounds check new TTL value. -1 is the lowest allowed value (-1 means 'forever')
            if newTTL < -1:
                newTTL = -1
            # Set the instance variable
            self.timeToLive = newTTL
            Utils.Message.addMessage("Setting new time to live " + str(datetime.timedelta(seconds=self.timeToLive)) + \
                                     " for stream " + str(self.syncSourceIdentifier))


    def killStream(self):
        # Kills the stream by setting the time to live to zero. This will cause the main thread to exit
        self.setTimeToLive(0)
        # Wait for __rtpGeneratorThread to end
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __rtpGeneratorThread to end")
        self.rtpGeneratorThread.join()
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __rtpGeneratorThread has ended")
        try:
            # Check to see if __tracerouteThread exists (it may have been intentionally disabled)
            if self.tracerouteThread.is_alive():
                # Wait for __tracerouteThread to end
                Utils.Message.addMessage("DBUG: RtpGenerator.killStream()  Waiting for __tracerouteThread has ended")
                self.tracerouteThread.join()
                Utils.Message.addMessage("DBUG: RtpGenerator.killStream()  __tracerouteThread has ended")
        except Exception as e:
            Utils.Message.addMessage("ERR:RtpGenerator.killStream() self.tracerouteThread.join() " + str(e))
        # Wait for __samplingThread to end
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __samplingThread to end")
        self.samplingThread.join()
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __samplingThread has ended")

        # Now kill corresponding RtpResultsReceiver object (should be a blocking call)
        try:
            self.rtpStreamResultsReceiver.kill()
            # Clear any reference to the relatedRtpStreamResults (to ensure that it will be garbage collected)
            self.relatedRtpStreamResults = None
        except Exception as e:
            Utils.Message.addMessage("ERR:RtpGenerator.killStream() kill rtpStreamResultsReceiver " + str(e))

        # Finally, remove this RtpGenerator object from rtpTxStreamsDict
        # self.rtpTxStreamsDictMutex.acquire()
        # Utils.Message.addMessage("INFO: Deleting RtpGenerator entry in rtpTxStreamsDict for stream: " + str(self.syncSourceIdentifier))
        # del self.rtpTxStreamsDict[self.syncSourceIdentifier]
        # self.rtpTxStreamsDictMutex.release()

        # Now kill UDP socket
        try:
            self.udpTxSocket.close()
        except Exception as e:
            Utils.Message.addMessage(
                "ERR: RtpGenerator.killStream()::udpTxSocket.close() for stream: " + str(self.syncSourceIdentifier))

        # Kill the http server
        try:
            self.httpd.shutdown()
            Utils.Message.addMessage(
                "DBUG:Closing http server for RtpGenerator  " + str(self.syncSourceIdentifier))
        except Exception as e:
            Utils.Message.addMessage(
                "ERR:Closing http server for RtpGenerator " + str(self.syncSourceIdentifier) + str(e))

        # Now attempt to remove the stream from the streams directory
        try:
            self.ctrlAPI.removeFromStreamsDirectory("RtpGenerator", self.syncSourceIdentifier)
        except Exception as e:
            Utils.Message.addMessage("ERR: RtpGenerator.killStream() removeFromStreamsDirectory() for stream " + \
                                         str(self.syncSourceIdentifier) + ", " + str(e))

    def disableStream(self):
        # Disables transmission of packets to simulate packet loss by clearing flag
        # Sequence numbers incrementing will continue even during inhibiting of stream
        self.enablePacketGeneration = False

    def enableStream(self):
        # Enables transmission of packets to simulate packet loss by setting flag
        self.enablePacketGeneration = True

    def getEnableStreamStatus(self):
        # Returns the current status of self.enablePacketGeneration
        return self.enablePacketGeneration

    # Turns on 'burst mode, whereby the tx rate will be temporarlily increased for a set period of seconds
    # This is to test network performance under 'burst' conditions
    # By default, the tx rate will double for 5 seconds
    # The tx rate is manipulated by modifying the previously calculated txPeriod value
    # At the transition from burstTimer=1 to burstTimer=0, the original tx period will be recalculated
    def enableBurstMode(self, burstLength_s = 5, burstRatio = 2):
        # Validate burstLength_s  - should be a +ve integer
        if not is_integer(burstLength_s, minimum=0):
            raise Exception(f"RtpGenerator{self.syncSourceIdentifier}.enableBurstMode() invalid burstLength_s {burstLength_s}")
        # Validate burstRatio  - cannot be 0 otherwise we'll get a div by zero error
        if not is_float(burstRatio, minimum=0.1): #
            raise Exception(
                f"RtpGenerator{self.syncSourceIdentifier}.enableBurstMode() invalid burstRatio {burstRatio}")


        # Confirm we're not already in burst mode, don't want to apply it twice
        if self.burstTimer == 0:
            # Start the burst timer. This value will be decremented every second by the __samplingThread
            self.burstTimer = burstLength_s
            # Modify the prev calculated txPeriod to manipulate the txRate
            # e.g if burstRatio is '2', the tx rate will be doubled
            self.txPeriod = self.txPeriod / burstRatio
            Utils.Message.addMessage("Enabling " + str(burstLength_s) + "s burst mode for stream " + str(self.syncSourceIdentifier))
        else:
            Utils.Message.addMessage("Burst mode already active for stream " + str(self.syncSourceIdentifier) +\
                    ". " + str(self.burstTimer) + "s remaining")

    # Used to simulate packet loss by skipping x packets (whilst incrementing the seq no internally)
    # Setting packetsToSkip to -1 will auto generate a minor loss (stats["glitch_Event_Trigger_Threshold_packets"] -1 )
    # Setting packetsToSkip to -2 will auto generate a minor loss (stats["glitch_Event_Trigger_Threshold_packets"] + 1)
    def simulatePacketLoss(self, packetsToSkip=0):
        # validate packetsToSkip, should be an integer > 0
        if not is_integer(packetsToSkip, minimum=-2):
            raise Exception(f"RtpGenerator{self.syncSourceIdentifier}.simulatePacketLoss() invalid packetsToSkip {packetsToSkip}."
                            f"Use 'packetsToSkip=-2' for auto major loss, and 'packetsToSkip=-1' for auto minor loss")
        if packetsToSkip < 0:
            # Auto generate minor/major loss loss
            # In the first instance, query the associated RtpStreamResults.stats["glitch_Event_Trigger_Threshold_packets"] threshold
            if self.relatedRtpStreamResults is not None:
                try:
                    # Attempt to retrieve the "glitch_Event_Trigger_Threshold_packets" threshold
                    statsDict = self.relatedRtpStreamResults.getRtpStreamStats(keyIs="glitch_Event_Trigger_Threshold_packets")
                    glitchThreshold = statsDict["glitch_Event_Trigger_Threshold_packets"]
                    if packetsToSkip == -2:
                        # Auto generate major loss
                        packetsToSkip = glitchThreshold + 1
                    else:
                        # Auto generate minor loss
                        packetsToSkip = glitchThreshold - 1
                except Exception as e:
                    raise Exception(f"ERR:RtpGenerator({self.syncSourceIdentifier}).simulatePacketLoss() {e}")
            else:
                # Associated RtpStreamResults does not exist, so 'guess' how many packets to skip
                if packetsToSkip == -2:
                    # Auto generate major loss
                    packetsToSkip = 20
                else:
                    # Auto generate minor loss
                    packetsToSkip = 3
        Utils.Message.addMessage(f"DBUG:RtpGenerator({self.syncSourceIdentifier}).simulatePacketLoss() packetsToSkip: {packetsToSkip}")
        self.packetsToSkip = packetsToSkip

    def enableJitter(self):
        # Turns on simulated jitter on tx stream
        self.jitterGenerationFlag = True

    def disableJitter(self):
        # Disables simulated jitter on tx stream
        self.jitterGenerationFlag = False

    def getJitterStatus(self):
        # Returns the status of self.jitterGenerationFlag
        return self.jitterGenerationFlag

    def getUDPSocket(self):
        # returns a reference to the socket created by __rtpGeneratorThread
        return self.udpTxSocket

    # Puts a control message into self.__controlMessageQueue
    def addControlMessage(self, controlMessage):
        self.__controlMessageQueue.put(controlMessage)

    # Takes a control message (as stored in self.__controlMessageQueue) and parses it
    # Each control message is a dict of keys containing at least {syncSourceID, source and type fields}
    def parseControlMessage(self, controlMessage):
        # Messages are a dict of the form
        # {syncSourceID: int, source: String, type: String}
        Utils.Message.addMessage("INFO:parseControlMessage() " + str(self.syncSourceIdentifier) + ":" + str(controlMessage))
        # parse the incoming message
        try:
            # Get message type
            messageSyncSourceID = controlMessage["syncSourceID"]
            messageType = controlMessage["type"]
            # Confirm that this is a message destined for this RtpGenerator Object
            if messageSyncSourceID == self.syncSourceIdentifier:
                if messageType == "/txrate/inc":
                    self.setTxRate(0, autoIncrement=1)
                elif messageType == "/txrate/dec":
                    self.setTxRate(0, autoIncrement=-1)
                elif messageType == "/ttl/inc":
                    self.setTimeToLive(0, autoIncrement=1)
                elif messageType == "/ttl/dec":
                    self.setTimeToLive(0, autoIncrement=-1)
                elif messageType == "/length/inc":
                    self.setPayloadLength(0, autoIncrement=1)
                elif messageType == "/length/dec":
                    self.setPayloadLength(0, autoIncrement=-1)
                elif messageType == "/burst":
                    self.enableBurstMode()
                # Set friendly name - confirm that the 'name' key is present in the controlMessage dict
                elif messageType == "/label" and "name" in controlMessage:
                    self.setFriendlyName(controlMessage["name"])
                else:
                    Utils.Message.addMessage(f"RtpGenerator({self.syncSourceIdentifier}).parseControlMessage() unrecognised message {controlMessage}")

            else:
                Utils.Message.addMessage("Misrouted RTPGenerator control message. Dest:" + \
                                         str(messageSyncSourceID) + ", Recipient:" + str(self.syncSourceIdentifier))

        except Exception as e:
            Utils.Message.addMessage("ERR:RtpGenerator.parseControlMessage() (stream " + \
                                     str(self.syncSourceIdentifier) + "), " + str(e))


    # This thread samples the actual transmitter tx rate and also housekeeps
    def __samplingThread(self):
        Utils.Message.addMessage(
            "DBUG:RtpGenerator.__samplingThread starting for stream " + str(self.syncSourceIdentifier))
        # Initialise variables to be used within the loop
        loopCounter = 0
        # The tx bps counter is a 1 second moving average with 0.2 sec accuracy
        # bpsCounterList = []
        bpsCounterList = deque(maxlen=5)
        # Snapshot current value
        prevTxCounter_Bytes = self.txCounter_bytes

        # Infinite loop = this should fire every 0.2 seconds
        while self.timeToLive != 0:
            sleepTime = 0.2
            # sleep
            time.sleep(sleepTime)
            ########### Timed loop starts

            # Check to see if there are any control messages in the queue
            while self.__controlMessageQueue.qsize() > 0:
                # Attempt to retrieve the message(s) from the queue
                try:
                    # Take the message from the queue
                    msg = self.__controlMessageQueue.get(timeout=0.2)
                    # parse the message
                    self.parseControlMessage(msg)
                # If not possible to get message/timeout reached
                except Empty as e:
                    Utils.Message.addMessage("ERR:RtpGenerator.__samplingThread. __controlMessageQueue.get() (stream " + \
                                             str(self.syncSourceIdentifier) + "), " + str(e))

            # Take snapshot of current tx byte counter
            currentTxCounter_Bytes = self.txCounter_bytes
            # Append the latest bytes transmitted (during the last 0.2 seconds) to the list
            # bpsCounterList is a Collections.deque() circuklar buffer object so will auto-housekeep
            bpsCounterList.append(currentTxCounter_Bytes - prevTxCounter_Bytes)

            # Store current value of currentTxCounter_Bytes for next time around the loop
            prevTxCounter_Bytes = currentTxCounter_Bytes

            # Reset the counters
            bytesPerSec = 0
            # Wait until we have all our data points
            if len(bpsCounterList) >= 5:
                # Sum the entire list to calculate the bytes per sec tx rate
                bytesPerSec = sum(bpsCounterList)

                # Calculate the transmitted bits per second
                self.txActualTxRate_bps = bytesPerSec * 8
                # Check to see if actual TX rate is exceeding the specified rate (but ignore if burst mode is enabled)
                if (self.txActualTxRate_bps > self.txRate) and (self.burstTimer == 0) and\
                        (Registry.enableExcessTxSpeedWarnings is True):
                    # If actual tx rate is > 25% higher than the rate specified by txRate, force the txScheduler to
                    # restart its timing calculations
                    # For the sake of speed, shift txRate by '2 bits' to divide by 4 rather than using division
                    if self.txActualTxRate_bps > (self.txRate + (self.txRate >> 2)):
                        # Set the flag to cause the txScheduler timer to reset
                        self.resetSleepPeriodFlag = True
                        # Put up a warning
                        Utils.Message.addMessage("Warning: Stream " + str(self.syncSourceIdentifier) + \
                                                 " tx rate exceeding " + \
                                                 str(Utils.bToMb(self.txRate)) + "(" + \
                                                 str(Utils.bToMb(self.txActualTxRate_bps)) + ")bps. Resyncing tx timer")


                    # If actual Tx rate is > 12.5% higher than the rate specified by txRate put up a warning
                    # For the sake of speed, shift txRate by '3 bits' to divide by 8 rather than using division
                    elif self.txActualTxRate_bps > (self.txRate + (self.txRate >> 3)):
                        Utils.Message.addMessage("Warning: Stream " + str (self.syncSourceIdentifier) +\
                                             " tx rate exceeding " +\
                                             str(Utils.bToMb(self.txRate)) + "(" +\
                                             str(Utils.bToMb(self.txActualTxRate_bps)) + ")bps")

            ######## 1 second counter
            if loopCounter % 5 == 0:
                # 1 Second has elapsed

                # Check to see if the tx source IP address has changed (transmitting via different interface/Wifi network?)
                currentSrcIPAddr = Utils.get_ip(self.UDP_TX_IP)
                # if it has changed, update the instance variable. The traceroute thread depends upon this
                if self.SRC_IP_ADDR != currentSrcIPAddr:
                    self.SRC_IP_ADDR = currentSrcIPAddr

                # If timeToLive seconds decrements to '2' seconds left, this means that it's about to expire
                # (it will expire when it reaches 1 second).
                # At this point, automatically generate/save a stream report
                if self.timeToLive == 2:
                    # Now check to see if there is a corresponding RtpStreamResults object for this Tx stream
                    if self.relatedRtpStreamResults is not None:
                        # Generate and save a report
                        try:
                            # Generate the actual report
                            report = self.relatedRtpStreamResults.generateReport()

                            # Retrieve the auto-generated filename
                            _filename = self.relatedRtpStreamResults.createFilenameForReportExport()
                            Utils.Message.addMessage(
                                "Stream " + str(self.syncSourceIdentifier) + " object is expiring. Autosaving report (__samplingThread)")
                            # Write a report to disk
                            Utils.writeReportToDisk(report, fileName=_filename)
                            Utils.Message.addMessage("Autosaved " + str(_filename + " to disk"))
                        except Exception as e:
                            Utils.Message.addMessage(
                                "ERR: RtpGenerator.killStream() rtpTxStreamResults.generateReport(): " + str(e))


                # Decrement timeToLive seconds counter but only if current value is +ve and >= 1
                # A -ve value is used to denote 'live for ever'
                # A value of 1 is used to denote 'expired' . At this point, the _rtpGeneratorThread.txScheduler() will
                # cease transmitting rtp packets, and will, instead transmit a 1 second 'keepalive' udp packet in order
                # to keep the 'connection tracking' on the NAT/Firewall of the outgoing router alive.
                # This should mean that the Receiver never loses control of the Transmitter, even after the stream
                # has expired
                if self.timeToLive > 1:
                    self.timeToLive -= 1

                # Decrement the burst timer, but only if current value is +ve
                if self.burstTimer >0:
                    self.burstTimer -= 1
                    # If we've only got 1 second left, recalculate txPeriod to revert the stream to the original tx rate
                    if self.burstTimer < 2:
                        self.txPeriod = self.calculateTxPeriod(self.txRate)
                        Utils.Message.addMessage("Burst mode ending for stream " + str(self.syncSourceIdentifier) + \
                                      ". Reverting to " + str(Utils.bToMb(self.txRate)) + "bps")

                # Increment elapsed time counter - add a second
                self.elapsedTime += datetime.timedelta(seconds=1)

                # Finally verify that this stream has been successfully registered with the directory
                # This should happen at the point of stream creation (in __init__()) but may fail
                # if the server is busy
                try:
                    streamsList = self.ctrlAPI.getStreamsList(streamID=self.syncSourceIdentifier)
                    # Test to see if response contains an entry for this stream
                    if streamsList[0]["streamID"] == self.syncSourceIdentifier and \
                            streamsList[0]["streamType"] == "RtpGenerator":
                        # Utils.Message.addMessage(f"RtpReceiveStream {self.syncSourceIdentifier} exists in streamsList")
                        pass
                except:
                    # stream doesn't exist, so need to register it
                    # Create a dict to define the stream
                    streamDefinition = {
                        "streamID": self.syncSourceIdentifier,
                        "httpPort": self.tcpListenPort,
                        "streamType": "RtpGenerator"
                    }
                    try:
                        # Register the stream
                        self.ctrlAPI.addToStreamsDirectory(streamDefinition)
                        Utils.Message.addMessage(f"DBUG:RtpGenerator.__samplingThread({self.syncSourceIdentifier}) " \
                                                 f"successful stream registration")
                    except Exception as e:
                        Utils.Message.addMessage(f"ERR:RtpGenerator.__samplingThread({self.syncSourceIdentifier})" \
                                                 f" registration fail {e}")

            ######## 1 second counter end of code ########

            # Increment 1 sec loop counter
            loopCounter += 1
            ########### 0.2 sec timed loop ends

        Utils.Message.addMessage(
            "DBUG:RtpGenerator.__samplingThread ending for stream " + str(self.syncSourceIdentifier))


    # This utility method will take a source bytearray and copy it into an existing bytearray, overwriting
    # the existing contents. If the srcData exceeds the length of buffer at the given stating position, the buffer
    # will be extended. If the position value is outside the range of the buffer, the new value will be appended to
    # the end of the buffer
    def copyIntoByteArray(self, destBytesArray, srcBytesArray, position):
        destBytesArray[position:position + len(srcBytesArray)] = srcBytesArray

    # This method will create the next Rtp packet to be generated, all apart from the timestamp which is created at the
    # last possible moment before socket.sendto()
    # If self.regeneratePayloadFlag is set, it will recreate the rtp header, isptest header and 'dummy payload' data
    # from scratch (essentially the entire udp payload)
    # If not, it will just increment the rtp sequence no within the rtp header and also update the isptest header data
    def prepareNextRtpPacket(self):
        if self.regeneratePayloadFlag is True:
            # Clear the flag
            self.regeneratePayloadFlag = False
            Utils.Message.addMessage("DBUG:prepareNextRtpPacket() self.regeneratePayloadFlag is True. Regenerating packet")
            # Create 12 byte RTP header structure (including sequence no). timestamp will be set to zero (as set later)
            # B: unsigned char, H: unsigned short (2 bytes), L: unsigned long (4 bytes)
            rtpTimestamp = 0 & 0xFFFFFFFF
            rtpHeader = struct.pack("!BBHLL", RtpGenerator.rtpParams, RtpGenerator.rtpPayloadType,
                                    self.rtpSequenceNo, rtpTimestamp, self.syncSourceIdentifier)

            # Create an empty placeholder for the isptestheader data
            isptestHeaderData = bytearray(RtpGenerator.getIsptestHeaderSize())

            # Create dummy payload (based on the current value of self.payloadLength)
            dummyPayload = self.generatePayload(self.payloadLength -\
                                                RtpGenerator.ISPTEST_HEADER_SIZE - RtpGenerator.RTP_HEADER_LENGTH_BYTES)

            # Construct the entire udp data frame
            self.udpTxData = bytearray(rtpHeader + isptestHeaderData + dummyPayload)
        else:
            # The only part of the rtp header that needs to be modified is the sequence no
            # Overwrite old rtp sequence no with new (the rtp sequence no is a 16 bit int starting at the 17th byte
            # of the header (i.e the third and fourth byte)
            struct.pack_into("!H", self.udpTxData, 2, self.rtpSequenceNo)

        # Create isptest header data
        isptestHeaderData = self.generateIsptestHeader()
        # Copy the isptest header data into the udp message frame.
        # The rtp header occupies bytes 0-11, the first bit of actual data starts at byte 12
        try:
            self.copyIntoByteArray(self.udpTxData, isptestHeaderData, 12)
            pass
        except Exception as e:
            Utils.Message.addMessage("prepareNextPacket() copy isptestHeader into self.udpTxData " + str(type(self.udpTxData)) + ", " + str(e))

        # increment sequence no. for next time this method is called
        self.rtpSequenceNo += 1
        # Seq no is only a 16 bit value, so reset at max value (65535)
        if self.rtpSequenceNo > 65535:
            self.rtpSequenceNo = 0
            Utils.Message.addMessage(
                "INFO: rtpGenerator. " + str(self.syncSourceIdentifier) + " Seq no wrapping to zero")

    # Exception raised by RtpGenerator.createUDPSocket()
    class RtpGeneratorCreateUDPSocketException(Exception):
        pass

    # Create a UDP socket for transmission and reception of the rtp packets (and received results)
    # Raises an RtpGeneratorCreateUDPSocketException on failure
    def __createUDPSocket(self):
        # Attempt to create UDP socket
        try:
            self.udpTxSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP
            # Set a timeout of 1 second (required because we will use recvfrom() in the corresponding
            # ResultsReceiver object (which will use this same socket, but to receive)
            self.udpTxSocket.settimeout(1)
            # Set custom udp ttl value
            self.udpTxSocket.setsockopt(socket.SOL_IP, socket.IP_TTL, Registry.rtpGeneratorUDPTxTTL)
            # Utils.Message.addMessage(str(self.udpTxSocket.get))
            # If a UDP source port has been specified, use it
            if self.UDP_TX_SRC_PORT > 1024:
                # Bind to the socket, allows you to specify the source port
                try:
                    self.udpTxSocket.bind(('0.0.0.0', int(self.UDP_TX_SRC_PORT)))
                except Exception as e:
                    Utils.Message.addMessage(
                        "ERR: RtpGenerator.__rtpGeneratorThread. self.udpTxSocket.bind (User supplied source port). " + str(
                            e))
            else:
                # Let the OS determine the source port
                self.udpTxSocket.bind(('0.0.0.0', 0))
                self.UDP_TX_SRC_PORT = self.udpTxSocket.getsockname()[1]
        except Exception as e:
            raise RtpGenerator.RtpGeneratorCreateUDPSocketException(str(e))
            # Utils.Message.addMessage(
            #     "ERR:\x1B[31__rtpGeneratorThread() socket.socket(): Cannot create socket. Please quit now\x1B[0m" + self.UDP_TX_IP + ":" + \
            #     str(self.UDP_TX_PORT) + ", " + str(e))

    def __rtpGeneratorThread(self):

        # This utility method will update the stats relating to the sleep period used to regulate the transmission rate
        def updateSleepTimeStats(rtpGeneratorInstance, sleepTime):
            # if rtpGeneratorInstance.minSleepTime is None:
            #     rtpGeneratorInstance.minSleepTime = sleepTime
            # elif sleepTime < rtpGeneratorInstance.minSleepTime:
            #     # record new minimum
            #     rtpGeneratorInstance.minSleepTime = sleepTime
            #
            # if rtpGeneratorInstance.maxSleepTime is None:
            #     rtpGeneratorInstance.maxSleepTime = sleepTime
            # elif sleepTime > rtpGeneratorInstance.maxSleepTime:
            #     # record new maximum
            #     rtpGeneratorInstance.maxSleepTime = sleepTime
            #
            # if rtpGeneratorInstance.meanSleepTime is None:
            #     rtpGeneratorInstance.meanSleepTime = sleepTime
            # else:
            # Calculate mean
            rtpGeneratorInstance.meanSleepTime = (rtpGeneratorInstance.meanSleepTime + sleepTime) / 2.0

        # This utility method will update the stats relating to the time taken for the RtpGenerator thread to prepare
        # and transmit each rtp packet
        # def updateCalculationTimeStats(rtpGeneratorInstance, calculationTime):
        #     if rtpGeneratorInstance.minCalculationTime is None:
        #         rtpGeneratorInstance.minCalculationTime = calculationTime
        #     elif calculationTime < rtpGeneratorInstance.minCalculationTime:
        #         rtpGeneratorInstance.minCalculationTime = calculationTime
        #
        #     if rtpGeneratorInstance.maxCalculationTime is None:
        #         rtpGeneratorInstance.maxCalculationTime = calculationTime
        #     elif calculationTime > rtpGeneratorInstance.maxCalculationTime:
        #         rtpGeneratorInstance.maxCalculationTime = calculationTime
        #
        #     if rtpGeneratorInstance.meanCalculationTime is None:
        #         rtpGeneratorInstance.meanCalculationTime = calculationTime
        #     else:
        #         rtpGeneratorInstance.meanCalculationTime = \
        #             (rtpGeneratorInstance.meanCalculationTime + calculationTime) / 2.0

        # This function will actually create and send the rtp packets
        def sendPacket(rtpGeneratorInstance):
            # If all tx flags are set then transmit the (previously created) rtp packet
            if rtpGeneratorInstance.enablePacketGeneration == True and rtpGeneratorInstance.packetsToSkip < 1:
                try:
                    # Create a new timestamp. This has to be done at the last moment before the packet is sent
                    # Create a 32 bit timestamp (needs truncating to 32 bits before passing to struct.pack)
                    # 0xFFFFFFFF is 32 '1's, so the '&' operation will throw away MSBs larger than this
                    rtpTimestampAsInt = int(datetime.datetime.now().strftime("%H%M%S%f")) & 0xFFFFFFFF

                    # Directly modify the timestamp field of the rtp header within the self.udpTxData bytearray
                    # The RTP timestamp field is bytes 4-7 of the RTP header
                    struct.pack_into("!L", rtpGeneratorInstance.udpTxData, 4, rtpTimestampAsInt)

                    # If Registry.rtpHeaderOffsetString has been set, prepend the rtp packet with the contents
                    # to create an offset between udp header and the rtp header
                    udpPayload = b""
                    if Registry.rtpHeaderOffsetString is not None:
                        udpPayload = Registry.rtpHeaderOffsetString + rtpGeneratorInstance.udpTxData
                    else:
                        udpPayload = rtpGeneratorInstance.udpTxData

                    # Send the data
                    sentBytes = rtpGeneratorInstance.udpTxSocket.sendto(udpPayload,
                                                            (rtpGeneratorInstance.UDP_TX_IP,
                                                             rtpGeneratorInstance.UDP_TX_PORT))

                    # Confirm that we appear to have sent the correct no. of bytes
                    if sentBytes == len(udpPayload):
                        # Update tx bytes counter (taking packet headers into account)
                        rtpGeneratorInstance.txCounter_bytes += sentBytes
                        # Update tx packets counter
                        rtpGeneratorInstance.txCounter_packets += 1
                    else:
                        # Increment the error counter
                        rtpGeneratorInstance.txErrorCounter += 1
                        Utils.Message.addMessage("ERR:RtpGenerator.__rtpGeneratorThread incorrect bytes sent. Tx'd: " +\
                                            str(sentBytes) + ", Expected: " + str(len(rtpGeneratorInstance.udpTxData)))


                except Exception as e:
                    Utils.Message.addMessage("\x1B[31 RtpGenerator.__newImprovedRtpGeneratorThread() sendto().   \x1B[0m " + str(e))
                    time.sleep(1)  # Throttle rate of error messages from this thread
            else:
                # Decrement self.packetsToSkip. Once this var reaches zero, packet generation will resume
                rtpGeneratorInstance.packetsToSkip -= 1


        # This Generator-based function will repeatedly call the functionToBeScheduled every 'period' seconds
        # A python 'Generator' is a function with 'memory'. Every time 'next' is called, it will return (or 'yield')
        # a value based on the previous returned value
        # If the execution of the code in sendPacket() exceeds the transmission period, calculateSleepTime() will
        # Return zero, so that the code in sendPacket() will be called immediately
        def txScheduler(rtpGeneratorInstance):
            # Calculate the sleep period based on the last time this function was called (this is a 'Generator' function
            # so it has 'memory'
            def calculateSleepPeriod():
                t = time.time()
                count = 0
                prevTxPeriod = rtpGeneratorInstance.txPeriod
                while True:
                    count += 1
                    txPeriod = rtpGeneratorInstance.txPeriod
                    # If the txPeriod has changed (which it will, if the tx rate is changed), reset the counter
                    if prevTxPeriod != txPeriod or rtpGeneratorInstance.resetSleepPeriodFlag:
                        # Clear the flag
                        rtpGeneratorInstance.resetSleepPeriodFlag = False
                        Utils.Message.addMessage("DBUG: RtpGenerator.calculateSleepPeriod() timing reset")
                        # Reset the initial time reference
                        t = time.time()
                        # Reset the counter
                        count = 1
                        # Capture the latest txPeriod value
                        prevTxPeriod = txPeriod

                    yield max(t + count * txPeriod - time.time(), 0)

            # This function calculates a deliberately inconsistent sleep period, to simulate network jitter
            def calculateJitterySleepPeriod():
                # Calculate the maximum intentional timing deviation to be add/subtracted from txPeriod if jitter is enabled
                maxDeviation = self.txPeriod * Registry.simulatedJitterPercent / 100
                jitter = random.uniform(-1 * maxDeviation, maxDeviation)
                sleepTime = 0
                try:
                    sleepTime = rtpGeneratorInstance.txPeriod + jitter #  - rtpGeneratorInstance.meanCalculationTime
                except Exception as e:
                    Utils.Message.addMessage("ERR: jitter sleepTime " + str(sleepTime) + ", " + str(e))
                if sleepTime < 0:
                    return 0
                else:
                    return sleepTime

            # This function deliberately increases the tx period at the start of transmission, to start the initial
            # tx rate much slower than the specified rate
            # it is a generator function, so it will remember it's previous value
            def calculateSlowStartSleepPeriod():
                # Every x packets, reduce the txPeriod until it matches the calculated tx rate
                count = 0
                # Capture the initial tx period from the instance var
                txPeriod = rtpGeneratorInstance.slowStartInitialTxPeriod
                while True:
                    # Increment count with each call to calculateSlowStartSleepPeriod
                    count += 1
                    if count > 1:
                        # With each successive call, halve the txPeriod
                        txPeriod = txPeriod / rtpGeneratorInstance.slowStartTxRateDivisor
                    # Return the latest value of txPeriod
                    yield txPeriod


            # This is the infinite loop that actually transmits the rtp packet at an interval determined
            # by the tx period. The sleep period is determined by the calculateSleepPeriod() 'generator' function
            # Infinite loop until timeToLive == 0
            # Create a Generator function (which is a bit like an object, in that it will continue to exist after returning)
            g = calculateSleepPeriod()
            # Create a Generator function to calculate the SlowStart tx period timings
            slowStartTxPeriodGenerator = calculateSlowStartSleepPeriod()
            # Declare sleeptime with a dfrault value
            sleepTime = rtpGeneratorInstance.slowStartInitialTxPeriod
            while rtpGeneratorInstance.timeToLive != 0:
                if rtpGeneratorInstance.slowStartActiveFlag is True:
                    # Every x packets, request a regeneration of the slowstart tx Period
                    # by using modulo division on the number oif packets sent
                    if rtpGeneratorInstance.txCounter_packets % rtpGeneratorInstance.slowStartPacketInterval == 0:
                        sleepTime = next(slowStartTxPeriodGenerator)
                        # Now check to see if the sleepTime has decreased to/beyond the target tx Period
                        if sleepTime <= rtpGeneratorInstance.txPeriod:
                            Utils.Message.addMessage("DBUG:target tx Period reached for stream " +\
                                                     str(rtpGeneratorInstance.syncSourceIdentifier) + \
                                                     ". Clearing slowStartActiveFlag")
                            # Clear the slowStartActiveFlag. The Regular calculateSleepPeriod will take over now
                            rtpGeneratorInstance.slowStartActiveFlag = False

                elif rtpGeneratorInstance.jitterGenerationFlag is False:

                    # Get (dynamic) sleep interval. This should ensure that the next packet is sent at precisely the correct
                    # time with any processing delays compensated for
                    sleepTime = next(g)
                else:
                    # Otherwise, deliberately get a jittery sleep value
                    sleepTime = calculateJitterySleepPeriod()
                    # Now recreate the calculateSleepPeriod() function in order to reset its counter
                    # Otherwise, when we exit 'jitter generation' mode, we end up with a burst of packets
                    # as the generator function tries to catch up
                    # g = calculateSleepPeriod()

                    # Now reset the calculateSleepPeriod() function by setting resetSleepPeriodFlag
                    # Otherwise, when we exit 'jitter generation' mode, we end up with a burst of packets
                    # as the generator function tries to catch up
                    rtpGeneratorInstance.resetSleepPeriodFlag = True

                # Sleep between UDP emmissions
                # Special case: If the stream timeToLive has decremented to '1 second' the stream is considered to
                # have expired. At this point, the RtpGenerator will enter a dormant state whereby it will send a
                # non-RTP udp 'connection keepalive udp packet' once a second
                if rtpGeneratorInstance.timeToLive == 1:
                    time.sleep(1)
                    # Send keepalive packet here
                    keepAliveString = b'keepAlive' + str(datetime.datetime.now().strftime("%S")).encode('ascii') +\
                                      str(rtpGeneratorInstance.syncSourceIdentifier).encode('ascii')
                    sentBytes = rtpGeneratorInstance.udpTxSocket.sendto(keepAliveString,
                                                                        (rtpGeneratorInstance.UDP_TX_IP,
                                                                         rtpGeneratorInstance.UDP_TX_PORT))

                else:
                    # Sleep for a dynamically calculated period to satisfy the bps tx rate
                    time.sleep(sleepTime)

                    # start timer
                    # processingStartTime = timer()
                    # send previously prepared packet
                    sendPacket(rtpGeneratorInstance)
                    # Prepare the next packet
                    rtpGeneratorInstance.prepareNextRtpPacket()

                    # # Deliberately cause a glitch
                    # if rtpGeneratorInstance.rtpSequenceNo == 65530:
                    #     Utils.Message.addMessage("seq no = 65530, insert 100 packet glitch")
                    #     rtpGeneratorInstance.packetsToSkip = 100

                    # # Deliberately cause a duplicate seq no every 500 packets
                    # if rtpGeneratorInstance.txCounter_packets % 500 == 0:
                    #     Utils.Message.addMessage("Cause duplicate sequence no error")
                    #     rtpGeneratorInstance.rtpSequenceNo -= 1

                    # # Deliberately cause an out of seq packet every 500 packets
                    # if rtpGeneratorInstance.txCounter_packets % 500 == 0:
                    #     Utils.Message.addMessage("Cause out of sequence error")
                    #     rtpGeneratorInstance.rtpSequenceNo -= 2

                    # # Deliberately modify the traceroute hops list every 500 packets
                    # if rtpGeneratorInstance.txCounter_packets % 500 == 0:
                    #     newOctet = rtpGeneratorInstance.txCounter_packets % 255
                    #     # Utils.Message.addMessage("new tr octet " + str(newOctet))
                    #     try:
                    #         if sum(rtpGeneratorInstance.tracerouteHopsList[0]) == 0:
                    #             Utils.Message.addMessage("new tr octet 0.0.0." + str(newOctet))
                    #             rtpGeneratorInstance.tracerouteHopsList=[[0,0,0,newOctet]]
                    #         else:
                    #             Utils.Message.addMessage("new tr octet 0.0.0.0")
                    #             rtpGeneratorInstance.tracerouteHopsList[0] = [0, 0, 0, 0]
                    #     except Exception as e:
                    #         Utils.Message.addMessage("TR test " + str(e))
                    #         rtpGeneratorInstance.tracerouteHopsList.append([0, 0, 0, 0])

                    # # Deliberately modify the traceroute hops list every 50 packets
                    # paths = [[
                    #     [192, 168, 224, 252],
                    #     [82, 194, 125, 65],
                    #     [212, 74, 66, 251],
                    #     [62, 214, 37, 134],
                    #     [80, 81, 192, 59],
                    #     [0, 0, 0, 0],
                    #     [0, 0, 0, 0],
                    #     [0, 0, 0, 0],
                    #     [132, 185, 249, 7],
                    #     [212, 58, 231, 65]]
                    #     ,
                    #     [
                    #         [192, 168, 224, 252],
                    #         [82, 194, 125, 65],
                    #         [212, 74, 66, 251],
                    #         [62, 214, 37, 134],
                    #         [80, 81, 192, 59],
                    #         [0, 0, 0, 0],
                    #         [0, 0, 0, 0],
                    #         [0, 0, 0, 0],
                    #         [132, 185, 249, 7]]
                    #     ,
                    #         [
                    #         [192, 168, 224, 253],
                    #         [62, 96, 44, 73],
                    #         [212, 74, 66, 251],
                    #         [212, 74, 66, 251],
                    #         [80, 81, 192, 59],
                    #         [0, 0, 0, 0],
                    #         [0, 0, 0, 0],
                    #         [0, 0, 0, 0],
                    #         [132, 185, 249, 9],
                    #         [212, 58, 231, 65]
                    #     ]]
                    # packetThreshold = 400
                    # if rtpGeneratorInstance.txCounter_packets % packetThreshold < (packetThreshold / 2):
                    #     # Modify the path
                    #     rtpGeneratorInstance.tracerouteHopsList = paths[0]
                    # else:
                    #     rtpGeneratorInstance.tracerouteHopsList = paths[1]
                    # # calculate the checksum
                    # rtpGeneratorInstance.tracerouteChecksum = \
                    #     rtpGeneratorInstance.createTracerouteChecksum(rtpGeneratorInstance.tracerouteHopsList)


                    # Update sleepTime stats
                    updateSleepTimeStats(rtpGeneratorInstance, sleepTime)

                # Stop calculation timer - calculate how long the packet preparation and transmission has taken
                # calculationPeriod = timer() - processingStartTime
                # Update calculation time stats
                # updateCalculationTimeStats(rtpGeneratorInstance, calculationPeriod)

        Utils.Message.addMessage("DBUG:New RtpGen thread. Thread starting")
        # Prepare the first rtp packet to be sent
        self.prepareNextRtpPacket()
        # Calculate tx period required to provide supplied txRate for a given stringLength
        # Note: txPeriod = self.payloadLength * 8.0 / self.txRate
        self.txPeriod = self.calculateTxPeriod(self.txRate)

        try:
            # Create a UDP socket for UDP transmission and reception
            self.__createUDPSocket()

            # Wait a couple of seconds to allow the sockets to be created
            time.sleep(2)

            # start the scheduler that will actually regulate the rate of transmission of packets
            # This is a blocking function call
            txScheduler(self)

            # If timeToLive has decremented to zero, the scheduler will end and execution will reach this point
            if self.relatedRtpStreamResults is not None:
                # Generate and save a report
                try:
                    # Generate the actual report
                    report = self.relatedRtpStreamResults.generateReport()

                    # Retrieve the auto-generated filename
                    _filename = self.relatedRtpStreamResults.createFilenameForReportExport()
                    Utils.Message.addMessage("Stream " + str(self.syncSourceIdentifier) + " object is ending. Autosaving report (__rtpGeneratorThread)")
                    # Write a report to disk
                    Utils.writeReportToDisk(report, fileName=_filename)
                    Utils.Message.addMessage("Written " + str(_filename + " to disk"))
                except Exception as e:
                    Utils.Message.addMessage(
                        "ERR: RtpGenerator.killStream() rtpTxStreamResults.generateReport(): " + str(e))

            Utils.Message.addMessage("DBUG: __newImprovedRtpGeneratorThread ending for stream " + str(self.syncSourceIdentifier))

        except Exception as e:
            Utils.Message.addMessage("ERR:__newImprovedRtpGeneratorThread " + str(e))

    # Thread-safe method to return a tuple of the last update timestamp and the list of the traceroute hops
    # Optional allowBlocking argument. If True, the method will block until the data is available
    # If allowBlocking is False, the method will check to see if the data is available in this instance and, if not
    # it will return None, []
    def getTraceRouteHopsList(self, allowBlocking=True):
        # Check status of lock before attempting to lock it
        isAccessible = self.tracerouteHopsListMutex.acquire(blocking=allowBlocking)
        if isAccessible:
            # Data is available
            tracerouteHopsList = deepcopy(self._tracerouteHopsList)
            self.tracerouteHopsListMutex.release()
            return self.tracerouteHopsListLastUpdated, tracerouteHopsList
        else:
            # Data is currently locked by another process
            Utils.Message.addMessage("DBUG:RtpGenerator.getTraceRouteHopsList() blocked")
            return None, []

    # Thread-safe method to set the traceroute hops list
    def setTraceRouteHopsList(self, newHopsList):
        # Decouple the method from any changes to the input source list by taking a deepcopy
        tempList = deepcopy(newHopsList)
        self.tracerouteHopsListMutex.acquire()
        self._tracerouteHopsList = tempList
        self.tracerouteHopsListMutex.release()
        # Update the timestamp
        self.tracerouteHopsListLastUpdated = datetime.datetime.now()



    def __tracerouteThread(self):
    # def __tracerouteLinuxOSXThread(self, ipAddrofSendingInterface, destHost, destPort, fallbackPort=33434,
    #                                noOfRetries=6, timeOut=0.5, \
    #                                maxNoOfHops=16):
        # Declare some custom Exceptions
        class UDPTxSocketSetupError(Exception):
            pass
        class ICMPRxSocketSetupError(Exception):
            pass
        class UDPTxError(Exception):
            pass
        class ICMPRxError(Exception):
            pass
        # class TracerouteLinuxOSXThreadError(Exception):
        #     pass

        # Creates and returns two separate sockets, one for tx (udp) and one for rx (icmp)
        # Returns a UDPTxSocketSetupError or ICMPRxSocketSetupError Exception
        def createSockets(ipAddrofInterface):
            ipAddrofInterface = "0.0.0.0"
            # Set up udp transmit socket
            try:
                # Create a layer 3 socket  - we will interface at IP level (socket.IPPROTO_RAW) but will send UDP through it
                udpTx = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
                # Set socket.IP_HDRINCL = 1. This means we must supply the IP header ourselves (although the OS will calculate the checksum)
                udpTx.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                udpTx.setblocking(False)


            except Exception as createSocketsError:
                raise UDPTxSocketSetupError(str(createSocketsError))
                # print("udpTxSocket socket setup error " + str(e))
                # exit()

            # Set up icmp receiving socket to receive ICMP
            try:
                # Create raw socket
                icmpRx = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                # icmpRx.settimeout(timeOut)
                icmpRx.setblocking(False)
                # Bind to the ip address of the interface specified by ipAddrofInterface
                icmpRx.bind((ipAddrofInterface, 0))
            except Exception as createSocketsError:
                raise ICMPRxSocketSetupError(str(createSocketsError))
                # print("reply socket setup error " + str(e))
                # exit()
            # Return the rx and tx sockets
            return udpTx, icmpRx

        # Decodes the supplied icmp header (which should be 8 bytes long)
        class ICMPHeader(object):
            # Custom Exception to be raised if the supplied icmpHeader data can't be unpacked
            class DecodeException(Exception):
                pass
            def __init__(self, icmp_header):
                # Attempt to unpack the header
                try:
                    self.type, self.code, self.checksum, self.p_id, self.sequence = struct.unpack('bbHHh', icmp_header)
                except Exception as e:
                    raise ICMPHeader.DecodeException(str(e))

        # Decodes the supplied IP header (which should be 20 bytes long)
        class IPHeader(object):
            # Custom Exception to be raised if the supplied IP header data can't be unpacked
            class DecodeException(Exception):
                pass
            def __init__(self, ip_header):
                # unpack header
                try:
                    iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
                    # First byte of header contains version (bits 4-7) and ip header length (bits 0-3)
                    version_ihl = iph[0]
                    self.version = version_ihl >> 4
                    self.ipHeaderLength = version_ihl & 0xF
                    self.id_field = iph[3]      # We'll use this field to verify that this was the packet we expected
                    self.flags_frag_offset = iph[4] # Composite field. Not used yet, so left alone
                    self.ttl = iph[5]
                    self.protocol = iph[6]
                    self.checksum = iph[7]
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

        # # This function decodes the icmp Header and icmp payload (which should contain a copy of the header
        # # that caused the icmp reply to be generated).
        # # It expects an ICMPHeader and IPHeader object as arguments
        # # If the function can match the srcAddress, srcTtl, icmpType and icmpCode to that of the original sending
        # # message we can infer that this ICMP message is for us.
        # # Returns True if all the  optional parameters were matched, False if not, or None of there was an error
        # def icmpReplyMatcher(__icmpHeader, __ipHeaderOfSrc, srcAddress=None, destAddress=None, \
        #                      srcTtl=None, icmpType=None, icmpCode=None, id_field=None):
        #
        #     # Test the fields within __icmpHeader and __ipHeaderOfSrc to see if they're what we're looking for
        #     try:
        #         if ((srcAddress == __ipHeaderOfSrc.s_addr) or (srcAddress is None)) and \
        #                 ((destAddress == __ipHeaderOfSrc.d_addr) or (destAddress is None)) and \
        #                 ((srcTtl == __ipHeaderOfSrc.ttl) or (srcTtl is None)) and \
        #                   ((icmpType == __icmpHeader.type) or (icmpType is None)) and \
        #                 ((icmpCode == __icmpHeader.code) or (icmpCode is None)):# and \
        #                 #((id_field == __icmpHeader.id_field) or (id_field is None)):
        #             return True
        #         else:
        #             return False
        #     except:
        #         return None

        # Utility function to tidy up the main loop. Sends a UDP message, allowing IP Header TTL parameter to be set
        def sendUDP(txSock, txTTL, payload, destIPAddr, destUDPPort, srcAddr, srcPort, id_field):
            try:
                # Create a UDP packet with custom header
                # srcAddr, destAddr, id_field, TTL, srcPort, dstPort, payload
                udpPkt = Utils.createCustomUdpPacket(srcAddr, destIPAddr, id_field, txTTL, srcPort, destUDPPort, payload)
                # Send the packet
                bytesSent = txSock.sendto(udpPkt, (destIPAddr, 0))
                return bytesSent
            except Exception as e:
                raise UDPTxError("UDPTxError " + str(e))

        # Utility function to tidy up the main loop. Strips any trailing 0.0.0.0s from the list of traceroute hops
        # Returns a sliced version of the list
        def trimHopsList(srcList):
            destList = []
            if len(srcList) > 0:
                elementsToTrim = 0
                # Work backwards from the end of the list
                for x in range(len(srcList) - 1, 0, -1):
                    # Test to see if hop value is 0.0.0.0
                    if srcList[x] == [0, 0, 0, 0]:
                        elementsToTrim += 1
                    else:
                        # Otherwise a non-0.0.0.0 address present, so break out of the loop
                        break
                # Now actually trim the redundant trailing 0.0.0.0's from the tracerouteHopsList list
                if elementsToTrim > 0:
                    try:
                        # Slice the unwanted elements from the top of the list (keeping only the bottom of the list)
                        destList = srcList[:(len(srcList) - elementsToTrim)]
                    except Exception as e:
                        Utils.Message.addMessage("ERR:__tracerouteThread.trimHopsList() " + str(e))
                else:
                    destList = srcList
            return destList

        # Utility function to tidy up main loop. Compares a list of lists for equality. If identical, returns True, else False
        def testHopsListsForEquality(srcList):
            listsAreEqual = False    # Default return value
            if len(srcList) > 1:    # Need to have more than 1 result to compare
                for n in range(1, len(tracerouteResultsList)):
                    # compare lists n and n-1 for equality
                    if tracerouteResultsList[n - 1] == tracerouteResultsList[n]:
                        # If equal, move onto the next pair
                        listsAreEqual = True
                    else:
                        # If the lists aren't equal, set the flag and break out of the loop
                        listsAreEqual = False
                        break
                return listsAreEqual
            elif len(srcList) > 0:
                # If len(srcList) == 1 (I.e only a single item), return True
                return True
            else:
                return False

        # Linux/OSX compatible function to send a UDP packet with a specfied TTL value, and then immediately wait for
        # an ICMP reply. Makes use of a previously created raw and UDP socket
        # Takes: rawSocket, udpSocket, source address, destAddr, destPort, ttl, receive timeout
        # Note: _icmpSocket and _udpSocket *must* be overridden
        # Returns: a dictionary containing the decoded fields from the ICMP message or None if there is no/an invalid response
        def sendUdpRecvIcmpRawSockets(_srcAddr, _destAddr, _destPort, _ttl, _timeout, _icmpSocket=None, _udpSocket=None,\
                                      _srcPort=1515, _id_field=0):

            # Send the UDP message (with a custom ttl and id_field value)
            try:
                bytesSent = sendUDP(_udpSocket, _ttl, b'tracert',  _destAddr, _destPort, _srcAddr, _srcPort, _id_field)
                # Utils.Message.addMessage("****TR sendUDP(() _ttl " + str(_ttl) + ", bytesSent " + str(bytesSent))

            except Exception as e:
                raise UDPTxError("ERR: __tracerouteLinuxOSXThread.sendUdpRecvIcmpLinuxOSX.sendUDP " + str(e))

            # Receive ICMP packet(s)
            # This loop waits to receive icmp packets
            # It's possible we might receive icmp packets not destined for us. Therfore we can't just accept
            # the first icmp packet we receive. We have to examine its contents
            # Either a socket.timeout, an elapsedTime timeout or a icmpReplyMatcher=True will cause this while
            # loop to break

            # Create elapsed timer
            startTime = datetime.datetime.now()
            while True:
                # Infinite loop to receive *all* icmp packets
                # Break out of loop:
                #   If timeOut period has been exceeded
                #   OR If matcher matches an icmp reply with the correct id_field
                elapsedTime = datetime.datetime.now() - startTime
                if elapsedTime.total_seconds() > _timeout:
                    # Utils.Message.addMessage("elapsedTimer exceeded limit " + str(elapsedTime.total_seconds()) + "/" + str(timeOut * 1))
                    break
                # Receive ICMP data from socket
                # Keep waiting until we get a matched packet or the timeout occurs
                try:
                    # Utils.Message.addMessage(
                    #     "***TR  recvfrom ICMP wait TTL:" + str(_ttl) + ", " + datetime.datetime.now().strftime("%H:%M:%S"))
                    # data, addr = _icmpSocket.recvfrom(65535)
                    # Use select() to poll the socket, before attempting to read it. This should block for _timeout seconds
                    # Utils.Message.addMessage("****TR select([_icmpSocket, _udpSocket]) _ttl " + str(_ttl))
                    r, w, x = select.select([_icmpSocket, _udpSocket], [], [], _timeout)

                    if not r:
                        # select () timeout reached so returned list will be empty
                        # Utils.Message.addMessage("****TR select() timeout reached")
                        return None
                    else:
                        # select() reckons there's some data to be read
                        if _udpSocket in r:
                            data, addr = _udpSocket.recvfrom(65535)
                            # Utils.Message.addMessage("****TR _udpSocket has data (" + str(len(data)) + ") " + \
                            #                          str(addr) + ", " + str(data))
                            pass
                        elif _icmpSocket in r:
                            # Utils.Message.addMessage("****TR _icmpSocket has data")
                            # The socket contains data to be read
                            data, addr = _icmpSocket.recvfrom(65535)

                            # Create ICMPHeader object from the received data. This will unpack and decode the fields
                            # The IP Header is contained within the first 20 bytes
                            # The ICMP Message Header is contained within the next 8 bytes
                            # The data after that is copy of the entire IPv4 header (20 bytes)
                            # ipHeaderOfReply = IPHeader(data[0:20])
                            # Decode the ICMP header
                            if len(data) >= 48:
                                try:
                                    icmpHeader = ICMPHeader(data[20:28])
                                    # Decode the ICMP payload, which contains a copy of the IP header originally sent
                                    # From this we can verify that the TTL and source IP address were the same as that sent
                                    # Therefore we can infer that this particular ICMP message is our reply, otherwise we discard the
                                    # message and listen again (within the timeout period)
                                    ipHeaderOfOriginalSender = IPHeader(data[28:48])
                                    # # Display the  header fields of the received packet
                                    # Utils.Message.addMessage("DBUG:Stream " + str(self.syncSourceIdentifier) + \
                                    #                          " RtpGenerator.__tracerouteThread() ICMP packet fields " + \
                                    #                          "src:" + str(addr[0]) + \
                                    #                          ", type:" + str(icmpHeader.type) + \
                                    #                          ", code:" + str(icmpHeader.code) + \
                                    #                          ", IPsrc:" + str(ipHeaderOfOriginalSender.s_addr) + \
                                    #                          ", IPdst:" + str(ipHeaderOfOriginalSender.d_addr) + \
                                    #                          ", IPttl:" + str(ipHeaderOfOriginalSender.ttl) + \
                                    #                          ", IPchecksum:" + str(ipHeaderOfOriginalSender.checksum) +\
                                    #                          ", id:" + str(ipHeaderOfOriginalSender.id_field))


                                    # Test to see if this icmp packet is a reply to the UDP message we just sent
                                    # Do this by examining the IPsrc and id_field values of the 'returned' IP header
                                    # contained within the payload of the icmp packet
                                    # We know exactly what we sent, so we know what we're looking for
                                    if ipHeaderOfOriginalSender.id_field == _id_field and \
                                            ipHeaderOfOriginalSender.s_addr == _srcAddr:
                                        # The received icmp contents are as expected
                                        # Extract any extra data (beyond the IP in ICMP payload) if it exists
                                        IPinICMP_payload = None # Set default value
                                        if len(data) > 48:
                                            IPinICMP_payload = data[48:]

                                        # Return a dictionary containing the unpacked fields of the icmp message
                                        return {"ICMP_Type": icmpHeader.type,
                                                "ICMP_Code": icmpHeader.code,
                                                "IP_replyFromAddr": addr[0],
                                                "IPinICMP_ttlReceived": ipHeaderOfOriginalSender.ttl,
                                                "IPinICMP_id_field": ipHeaderOfOriginalSender.id_field,
                                                "IPinICMP_srcAddr": ipHeaderOfOriginalSender.s_addr,
                                                "IPinICMP_dstAddr": ipHeaderOfOriginalSender.d_addr,
                                                "IPinICMP_checksum": ipHeaderOfOriginalSender.checksum,
                                                "length": len(data),
                                                "IPinICMP_payload": IPinICMP_payload
                                                }
                                    else:
                                        # Display the  header fields of the unexpected packet
                                        # Utils.Message.addMessage("DBUG:Stream " + str(self.syncSourceIdentifier) + \
                                        #                          " RtpGenerator.__tracerouteThread() Unexpected ICMP packet fields " + \
                                        #                          "src:" + str(addr[0]) + \
                                        #                          ", type:" + str(icmpHeader.type) + \
                                        #                          ", code:" + str(icmpHeader.code) + \
                                        #                          ", IPsrc:" + str(ipHeaderOfOriginalSender.s_addr) + \
                                        #                          ", IPdst:" + str(ipHeaderOfOriginalSender.d_addr) + \
                                        #                          ", IPttl:" + str(ipHeaderOfOriginalSender.ttl) + \
                                        #                         ", tx'd ttl:" + str(_ttl) + \
                                        #                          ", IPchecksum:" + str(ipHeaderOfOriginalSender.checksum) + \
                                        #                          ", id:" + str(ipHeaderOfOriginalSender.id_field) +\
                                        #                          ", tx'd id:" + str(_id_field))
                                        pass


                                except Exception as e:
                                    Utils.Message.addMessage("DBUG:Stream " + str(self.syncSourceIdentifier) + \
                                                             " RtpGenerator.__tracerouteThread() ICMP decode error, from " + \
                                                             str(addr[0]) + ", " + str(e))
                                    return None

                            else:
                                Utils.Message.addMessage("DBUG:Stream " + str(self.syncSourceIdentifier) + \
                                                     " RtpGenerator.__tracerouteThread() Unexpected short length packet from " + \
                                                     str(addr[0]))
                                pass



                except Exception as e:
                    raise ICMPRxError("ERR: __tracerouteLinuxOSXThread.sendUdpRecvIcmpRawSocket.recvICMP " + str(e))

            # If no validated icmp packet was received within the time allowed, return with None
            return None

    # Linux/OSX compatible function to send a UDP packet with a specfied TTL value, and then immediately wait for
    # an ICMP reply. Makes use of a previously created raw (for icmp) and UDP socket
    # Takes: rawSocket, udpSocket, source address, destAddr, destPort, ttl, receive timeout, payload
    # Note: _icmpSocket and _udpSocket *must* be overridden
    # Returns: a dictionary containing the decoded fields from the ICMP message or None if there is no/an invalid response
    # It validates the received ICMP reply by comparing the length of a randomly geenrated _payload (in bytes) to the
    # length field specified in the returned IP header included within the ICMP message. If the lengths match, it is assumed that
    # the ICMP reply relates to the packet sent.
    # _srcPort is ignored as this should be specified as part of the _udpSocket socket binding when the socket is created

        def sendUdpRecvIcmpSimple(_srcAddr, _destAddr, _destPort, _ttl, _timeout, _icmpSocket=None, _udpSocket=None,\
                                 _srcPort=None):
            def generatePayload(payloadLength):
                # Generate random byte string of length 'length' to create a payload of length self.payloadLength

                # Create byte string containing all uppercase and lowercase letters
                letters = string.ascii_letters
                # iterate over stringLength picking random letters from 'letters'
                randomDataString = ''.join(random.choice(letters) for i in range(payloadLength))

                # Return as a bytestring
                return randomDataString.encode('ascii')

            # Create a random length payload between 50 and 250 bytes long
            payload = generatePayload(random.randint(50, 250))

            # Send the UDP message (with a custom ttl)
            try:
                # bytesSent = sendUDP(_udpSocket, _ttl, b'tracert', _destAddr, _destPort, _srcAddr, _srcPort, _id_field)
                # Set the ttl for the socket
                _udpSocket.setsockopt(socket.SOL_IP, socket.IP_TTL, _ttl)
                # Send the payload
                bytesSent = _udpSocket.sendto(payload, (_destAddr, _destPort))
                Utils.Message.addMessage("****TR sendUdpRecvIcmpSimple() _ttl " + str(_ttl) + ", bytesSent " + str(bytesSent))

            except Exception as e:
                raise UDPTxError("ERR: __tracerouteLinuxOSXThread.sendUdpRecvIcmpLinuxOSX.sendUDP " + str(e))




        # Windows compatible function to send a UDP packet with a specfied TTL value, and then immediately wait for
        # an ICMP reply. Makes use of the Scapy library to receive raw packets/decode ICMP
        # Takes: rawSocket, udpSocket, destAddr, destPort, ttl
        # Returns: a dictionary containing the decoded fields from the ICMP message or None if there is no valid response
        # Note: The _icmpSocket=None, _udpSocket arguments are ignored. They are there to retain consistency with the
        # sendUdpRecvIcmpRawSockets function
        # IMPORTANT: Unlike the Linux/OSX equivalent function, we cannot reuse the same UDP source port as the rtp
        # stream. Therefore we just let the OS decide
        def sendUdpRecvIcmpScapy(_srcAddr, _destAddr, _destPort, _ttl, _timeout, _icmpSocket=None, _udpSocket=None,\
                                 _srcPort=1515, _id_field=0):
            try:
                # Create a packet template 'craft a Scapy packet'
                payload = b'tracert'
                # NOTE: Source port is specified as 1
                pkt = IP(dst=_destAddr, ttl=_ttl, id=_id_field) / UDP(dport=_destPort) / Raw(
                    load=payload)
                # Send the packet and wait for a reply
                reply = sr1(pkt, verbose=0, timeout=_timeout)
                # Now parse the reply
                # Confirm tjat we have a response, and also that reply contains the ["IP in ICMP"] dict key
                if reply is not None and "IP in ICMP" in reply:
                    # Confirm the ICMP message tallies with the sent UDP packet, by comparing the id_field parameter
                    # # Extract ID field from "IP in ICMP" layer of reply
                    if reply["IP in ICMP"].id == _id_field:
                        # # Detect TTL Expired messages (icmp type 11, code 0)
                        # if reply.type == 11:
                        #     # This is a TTL expired in transit message, for us - snapshot the address
                        #     icmpSourceAddr = reply.src
                        #     icmpMessageType = reply.type
                        # # Detect Destination Host Port unreachable, destination reached
                        # elif reply.type == 3 or reply.src == _destAddr:
                        #     icmpSourceAddr = reply.src
                        #     icmpMessageType = reply.type

                        # Return a dictionary containing the unpacked fields of the icmp message
                        return {"ICMP_Type": reply.type,
                                "ICMP_Code": reply.code,
                                "IP_replyFromAddr": reply.src,
                                "IPinICMP_ttlReceived": reply["IP in ICMP"].ttl,
                                "IPinICMP_id_field": reply["IP in ICMP"].id,
                                "IPinICMP_srcAddr": reply["IP in ICMP"].src,
                                "IPinICMP_dstAddr": reply["IP in ICMP"].dst,
                                "IPinICMP_checksum": reply["IP in ICMP"].chksum,
                                "length": reply.len,
                                "IPinICMP_payload": reply["UDP in ICMP"].payload
                                }
                    else:
                        # Utils.Message.addMessage("__tracerouteThread.sendUdpRecvIcmpScapy() Unexpected ICMP packet fields " + \
                        #                          "src:" + str(reply.src) + \
                        #                          ", type:" + str(reply.type) + \
                        #                          ", code:" + str(reply.code) + \
                        #                          ", IPsrc:" + str(reply["IP in ICMP"].src) + \
                        #                          ", IPdst:" + str(reply["IP in ICMP"].dst) + \
                        #                          ", IPttl:" + str(reply["IP in ICMP"].ttl) + \
                        #                          ", tx'd ttl:" + str(_ttl) + \
                        #                          ", IPchecksum:" + str(reply["IP in ICMP"].chksum) + \
                        #                          ", id:" + str(reply["IP in ICMP"].id) + \
                        #                          ", tx'd id:" + str(_id_field))
                        pass


                else:
                    # Reply timed out, or reply couldn't be matched with sent packet
                    return None

            except Exception as e:
                Utils.Message.addMessage("ERR: RtpGenerator.__tracerouteThread.sendUdpRecvIcmpScapy() " + str(e))
                return None



        # Define a socket timeout value
        timeOut = 0.1
        # Define the number of times the traceroute will attempt to illicit a response from the router.
        # This is becuse some routers will fail to respond due to rate limiting of requests.
        # Note: Each subsquent attempt alternates between two possible ports
        # The first attempt will be to use the destination port for the stream
        # If that fails, a fallback port specified in the Registry will be used. Routers are more likely to respond
        # on this other port (33434)
        maxNoOfRetries = 4
        # Get the max no of hops before traceroute gives up
        maxNoOfHops = Registry.tracerouteMaxHops
        # Get the UDP 'fallback' port
        fallbackPort = Registry.tracerouteFallbackUDPDestPort
        # The no. of consecqutive 'no response from router' requests we'll tolerate before giving up
        maxNoOfNoResponse = 5

        # Flag to signal that the tx udp and icmp rx sockets were created successfully (in Linux/OSX mode)
        setupSuccessfulFlag = False
        udpTx = None        # placeholder for udp transmit socket
        icmpRx = None       # placeholder for  icmp receive socket
        sendUdpRecvIcmp = None # Operating system-dependant pointer to the traceroute send/recv function
        setupErrorMessage = None

        Utils.Message.addMessage("DBUG:__tracerouteThread starting for stream " + str(self.syncSourceIdentifier))

        # Determine which Operating System is in use, and therefore which udp tx/icmp rx function we will use
        os = Utils.getOperatingSystem()
        # os = "Windows"
        if os == "Windows":
            # Windows detected
            from scapy.layers.inet import IP, UDP
            from scapy.sendrecv import sr1
            from scapy.packet import Raw
            # Create pointer to the correct function for this OS
            sendUdpRecvIcmp = sendUdpRecvIcmpScapy
            self.tracerouteFunctionInUse = "sendUdpRecvIcmpScapy"
            # Do a simple test using Scapy.sr1() to check it will work (by sending a single raw packet to localhost)
            # If it raises an exception, traceroute won't work
            try:
                pkt = IP(dst="127.0.0.1", ttl=1) / UDP(dport=5000)
                # Send the packet and wait for a reply
                reply = sr1(pkt, verbose=0, timeout=0.1)
                Utils.Message.addMessage(
                    "DBUG:RtpGeneratorThread.__tracerouteThread() Scapy raw send/recv successful " + str(reply))
                setupSuccessfulFlag = True

            except Exception as e:
                # Scapy failed
                Utils.Message.addMessage("DBUG:RtpGeneratorThread.__tracerouteThread() Scapy raw send/recv test failed " +\
                                         str(e))
                setupSuccessfulFlag = False
                # Store the error message
                setupErrorMessage = str(e)
        else:
            # Linux or OSX detected
            # Create pointer to correct function for this OS
            sendUdpRecvIcmp = sendUdpRecvIcmpRawSockets
            self.tracerouteFunctionInUse = "sendUdpRecvIcmpRawSockets"
            # Now create udp tx and icmp rx sockets
            try:
                # Create tx (udp) and rx (icmp) sockets, specifying the ip address we will be transmitting from
                udpTx, icmpRx = createSockets(self.SRC_IP_ADDR)
                # Set the 'sockets okay' flag so that the main while loop will start
                setupSuccessfulFlag = True

            except Exception as e:
                # Failed to set up sockets
                Utils.Message.addMessage(
                    "DBUG:RtpGeneratorThread.__tracerouteThread() createSockets() failed " + \
                    str(e))
                setupSuccessfulFlag = False
                # Store the error message
                setupErrorMessage = str(e)

        if setupSuccessfulFlag:
            Utils.Message.addMessage("DBUG:__tracerouteThread Stream " + str(self.syncSourceIdentifier) + " using " +\
                          str(self.tracerouteFunctionInUse))
        else:
            # If setup failed
            Utils.Message.addMessage("ERR: __tracerouteThread setup error: " + str(setupErrorMessage))
            Utils.Message.addMessage("\033[31mHint: Run as sudo to enable traceroute functionality")
            # If a UI instance (user interface) reference was supplied, display an error message on the UI
            maxWidth = 60
            # errorText = textwrap.fill(setupErrorMessage, width=maxWidth) + \
            # Truncate setupErrorMessage if necessary, to fit screen
            if setupErrorMessage is not None and len(setupErrorMessage) >= maxWidth:
                setupErrorMessage = setupErrorMessage[:maxWidth]
            errorText = str(setupErrorMessage).center(maxWidth) + \
                                    "\n\n" + "isptest TRANSMITTER will continue to run, but without traceroute.".center(maxWidth) + \
                        "\n" + "To enable this function, exit the app and run as sudo ".center(maxWidth) + \
                        "\n" + "(or as Administrator, if running on Windows)".center(maxWidth) + \
                        "\n\n" + "<Press any key to continue>".center(maxWidth)
            if self.uiInstance is not None:
                try:
                    self.uiInstance.showErrorDialogue("Traceroute error", errorText)
                except Exception as e:
                    Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread: display error message on UI " + \
                                             str(e))

        # A list to contain two (or more) tracerouteHopsList lists. The lists can then be compared. Only when n
        # consecutive identical lists have been determined can we say that we have a 'stable' route
        # Create empty list to put the results of each traceroute attempt into

        tracerouteHopsListMustMatchThreshold = 2
        tracerouteResultsList = deque(maxlen=tracerouteHopsListMustMatchThreshold)
        # Additionally, it's possible a mismatch would occur if a hop flapped to/from zero. This is likely to be quite a
        # frequent occurance. And, given the length of time it takes a traceroute to complete, we don't necessarily want
        # to write-off the results we have
        tracerouteHopsListMismatchCounterThreshold = 5 # No of consecutive failures before clearing the hopsList
        tracerouteHopsListMismatchCounter = 0 # Counts the no of consecutive failures
        tracerouteLoopCounter = 0       # Acts as a delayed start device. Increments every second
        enableVerboseLogging = False
        try:
            # Perform the traceroute in an infinite loop as long as the transmit stream is alive
            # The traceroute is performed n times. Only when the same route has been confirmed will the
            # tracerouteHopsList be updated. This is to guard against situations where the route changes mid-traceroute
            while self.timeToLive != 0 and setupSuccessfulFlag:
                # This is the main traceroute loop and counts the hops
                # Set initial ttl (NOTE, start by decrementing 1, as the increment happens in the loop)
                ttl = Registry.tracerouteStartingTTL - 1

                # Counter for the number of consequtive 0 responses. If this exceeds maxNoOfNoResponse, traceroute will abort
                # Reset the 'no response' counter
                noResponseCounter = 0
                # This list will be populated with the results of the traceroute
                hopsList = []
                # Counts the no of retries for each hop
                retryCount = 1
                # Utils.Message.addMessage("Starting traceroute....ttl = 1")
                while ttl < maxNoOfHops and self.timeToLive != 0 and tracerouteLoopCounter > Registry.tracerouteStartDelay:
                    retryCount = 1
                    # We want to start at ttl = 1. Increment
                    ttl += 1
                    # Initialise hop addr. This will be overwritten if an ICMP reply is received for this hop
                    icmpSrcAddr = None

                    # This loop counts the attempts for each hop
                    while (retryCount < maxNoOfRetries) and self.timeToLive != 0:
                        # Utils.Message.addMessage("Attempts loop starting. Hop: " + str(ttl) + ", Attempt: " + str(retryCount))
                        # Send UDP packet
                        # Determine which UDP destination port to use
                        if fallbackPort is None:
                            # If fallback port is not set, only ever use self.UDP_TX_PORT as the traceroute probe port no
                            udpTxPort = self.UDP_TX_PORT
                        elif retryCount % 2 == 1:
                            # Otherwise, for odd numbered attempts, use self.UDP_TX_PORT
                            udpTxPort = self.UDP_TX_PORT
                        else:
                            # and for even numbered attempts use the fallback port specified in Registry.tracerouteFallbackUDPDestPort
                            udpTxPort = fallbackPort

                        # Perform the UDP Send/ICMP receive
                        # Set the IP id_field to match that of the current ttl. We should then be able to
                        # match the packet send to the received response
                        icmpMsg = None # Stores the icmp response (in the form of a dictonary) returned by sendUdpRecvIcmp()
                        # Initialise hop addr. This will be overwritten if an ICMP reply is received for this hop
                        icmpSrcAddr = None
                        try:
                            # Calculate a unique id field based on the syncSourceID (which should be unique) +
                            # src port + dest port + current TTL value to be tested
                            # This is necessary because for a multiple TX streams, if the id_fields weren't unique
                            # between the streams, the ICMP receiver code might get confused about which reply
                            # went with which stream
                            # This can only be a 16 bit value so needs to be masked to ensure that it doesn't wrap
                            # tracerouteID = (self.UDP_TX_SRC_PORT + self.UDP_TX_PORT + self.syncSourceIdentifier + ttl) & 0xFFFF
                            # Calculate a unique id field using a random number
                            # This can only be a 16 bit value so needs to be masked to ensure that it doesn't wrap
                            tracerouteID = random.randint(1000, 65535) & 0xFFFF


                            icmpMsg = sendUdpRecvIcmp(\
                                self.SRC_IP_ADDR, self.UDP_TX_IP, udpTxPort, ttl, timeOut,\
                                _udpSocket=udpTx, _icmpSocket=icmpRx, _srcPort=self.UDP_TX_SRC_PORT, _id_field=tracerouteID)

                        except UDPTxError as e:
                            Utils.Message.addMessage("ERR:Stream" + str(self.syncSourceIdentifier) + \
                                                     "__tracerouteThread UDPTxError. Recreating udp Tx socket" + str(
                                type(e)) + ", " + str(e))
                            # close existing socket
                            try:
                                udpTx.close()
                            except:
                                Utils.Message.addMessage("ERR:Stream" + str(self.syncSourceIdentifier) + \
                                                         "__tracerouteThread UDPTxError.  udpTx.close()" + str(
                                    type(e)) + ", " + str(e))
                            # Recreate the udp tx socket
                            try:
                                # close existing socket (this can only happen for sendUdpRecvIcmprawSockets, because
                                # Scapy handles its own sockets)
                                # Create tx (udp) and rx (icmp) sockets, specifying the ip address we will be transmitting from
                                udpTx, icmpRx = createSockets(self.SRC_IP_ADDR)
                                Utils.Message.addMessage("DBUG:Stream" + str(self.syncSourceIdentifier) + \
                                                         "__tracerouteThread UDPTxError.  udpTx socket recreated successfully " + str(
                                    type(e)) + ", " + str(e))
                            except:
                                Utils.Message.addMessage("ERR:Stream" + str(self.syncSourceIdentifier) + \
                                                         "__tracerouteThread UDPTxError.  udpTx socket recreation failed " + str(
                                    type(e)) + ", " + str(e))

                        # Test the icmp response:-
                        # If the traceroute hop router did not respond, we get None, otherwise we should get a dictionary
                        # containing the unpacked fields of the traceroute message
                        if icmpMsg is not None:
                            try:
                                # Extract reply-from addr
                                icmpSrcAddr = icmpMsg["IP_replyFromAddr"]
                                # Utils.Message.addMessage("ttl " + str(ttl) + ", " + str(icmpSrcAddr) + ", id: " +\
                                #                          str(icmpMsg["IPinICMP_id_field"]) + ", len: " +\
                                #                          str(icmpMsg["length"]))

                                # Detect erroneous messages to trap messages with an unexpected ttl at the point of
                                # arrival at the router.
                                #   Each hop should only ever receive a TTL of 1. If it doesn't that suggests that
                                # a previous router has allowed a packet through whose ttl has already decremented to
                                # zero. Therefore we can't trust this response
                                if icmpMsg["IPinICMP_ttlReceived"] != 1:
                                    if enableVerboseLogging:
                                        Utils.Message.addMessage("DBUG:Stream " + str(self.syncSourceIdentifier) + \
                                            " Erroneous ttl=" + str(icmpMsg["IPinICMP_ttlReceived"]) + \
                                                             " ICMP message for traceroute hop " + str(ttl) + \
                                                             " Setting hop value to 0.0.0.0")
                                    icmpSrcAddr = "0.0.0.0"

                                # Detect Destination Host Port unreachable, destination reached
                                elif icmpMsg["ICMP_Type"] == 3 or icmpMsg["IPinICMP_srcAddr"] == self.UDP_TX_IP:
                                    # Utils.Message.addMessage("icmpType == 3 or icmpSrcAddr == self.UDP_TX_IP")
                                    # Cause the outer-outer hops counter loop to break. The traceroute is complete
                                    ttl = maxNoOfHops
                                # Detect TTL Expired messages (icmp type 11, code 0) - we're mid-traceroute
                                elif icmpMsg["ICMP_Type"] == 11 and icmpMsg["ICMP_Code"] == 0:
                                    pass

                            except Exception as e:
                                icmpSrcAddr = "0.0.0.0"
                                Utils.Message.addMessage("ERR: __tracerouteThread " + str(self.syncSourceIdentifier) +
                                                         " Decode icmpMsg{} dict. Setting hop  " + str(ttl) + \
                                                         " to 0.0.0.0. "+ str(e))

                            # Store the address
                            # Query the WhoisResolver to find the owner of the domain
                            Utils.WhoisResolver.queryWhoisCache(icmpSrcAddr)
                            # If so, break the address up into a list of octets - this is how they're stored in self._tracerouteHopsList
                            icmpSrcAddrOctets = str(icmpSrcAddr).split('.')
                            hopsList.append([int(icmpSrcAddrOctets[0]), int(icmpSrcAddrOctets[1]),
                                                 int(icmpSrcAddrOctets[2]),
                                                 int(icmpSrcAddrOctets[3])])
                            # Reset the 'no response' counter
                            noResponseCounter = 0
                            # Cause the inner attempts loop to break - we have a response for this hop
                            # retryCount = maxNoOfRetries
                            break
                        # Else, the router did not respond
                        else:
                            # Increment the retry counter
                            retryCount += 1
                            # If this is the final attempt but still no response, append 0.0.0.0 to hopsList
                            if retryCount == maxNoOfRetries:
                                # Utils.Message.addMessage(
                                #     "retries exceeded for hop " + str(ttl) + ", retry " + str(retryCount))
                                hopsList.append([0, 0, 0, 0])
                                # Increment the 'no response' counter
                                noResponseCounter += 1

                    # Now check to see if we've received five 'no replies' in a row, if so, give up
                    # Or else, if we've reached the max no of hops, give up
                    if (noResponseCounter > maxNoOfNoResponse) or (ttl >= maxNoOfHops):
                        # Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread:" + str(noResponseCounter) + \
                        #                          " None's in a row or hop limit reached. Aborting")
                        # Cause the outer-outer hops counter loop to break
                        # ttl = maxNoOfHops
                        break
                    # Utils.Message.addMessage("[TTL:" + str(ttl) + ", Retry:" + str(retryCount) +"]" + str(hopsList[-1]))

                # Traceroute pass completed,

                # Now strip off any trailing 0.0.0.0 (no responses)
                if len(hopsList) > 0:
                    hopsList = trimHopsList(hopsList)
                    # Utils.Message.addMessage("hopsList: " + str(hopsList))
                    # Traceroute pass completed and hopslist trimmed. Now append to tracerouteResultsList for later validation
                    # Add the latest traceroute result to tracerouteResultsList

                    tracerouteResultsList.append(hopsList)
                    # Utils.Message.addMessage("DBUG: stream " + str(self.syncSourceIdentifier) + \
                    #                          " traceroute len:" + str(len(hopsList)) + \
                    #                          ", ttl:" + str(ttl) + ", retry:" + str(retryCount) + ")" + \
                    #                          str(hopsList))
                #
                # # Wait for tracerouteResultsList to be populated with the required no of traceroute passes
                # # When ready, compare the contents of the lists within tracerouteResultsList for equality
                if len(tracerouteResultsList) >= tracerouteHopsListMustMatchThreshold:
                    if testHopsListsForEquality(tracerouteResultsList):
                        # If the lists are all identical that means that n consecutive traceroutes gave the same result
                        # so the traceroute has been validated. Update the instance variable (via the setter method)
                        self.setTraceRouteHopsList(hopsList)
                        # Successful (replicated) traceroute has completed, so reset the mismatch counter
                        tracerouteHopsListMismatchCounter = 0
                        # Recalculate the checksum for the (transmitted( hopsList
                        self.tracerouteChecksum = self.createTracerouteChecksum(hopsList)

                        # # Now update the tracerouteHops list in the corresponding RtpStreamResults object (if it exists)
                        # # Note: This is not transmitted by the receiver (because it's not part of the stats dictionary)
                        # # So has to be updated manually here
                        try:
                            if self.relatedRtpStreamResults is not None:
                                ### Copy the traceroute hops list into the object instance var
                                self.relatedRtpStreamResults.setTraceRouteHopsList(hopsList)
                        except Exception as e:
                            # Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread() update RtpStreamResults tracerouteHopList " + str(e))
                            pass

                    else:
                        # Consequtive traceroutes were not identical. Perhaps the route changed, mid-traceroute?
                        # Increment the mismatch counter
                        tracerouteHopsListMismatchCounter += 1
                        # Now test to see if we have exceeded the max no of allowed consecutive mismatches
                        if tracerouteHopsListMismatchCounter > tracerouteHopsListMismatchCounterThreshold:
                            Utils.Message.addMessage(\
                                "DBUG:Traceroute. Stream (" + str(self.syncSourceIdentifier) +\
                                ") Exceeded consecutive mismatch Threshold (" +\
                                str(tracerouteHopsListMismatchCounterThreshold) + \
                                "), clearing hopsList. Most recent " + str(hopsList))

                            # Empty the current tracerouteHopsList (by filling with an empty list)
                            self.setTraceRouteHopsList([])
                            # Clear the traceroute checksum
                            self.tracerouteChecksum = 0
                            # reset the mismatch counter
                            tracerouteHopsListMismatchCounter = 0
                            # # Now update the tracerouteHops list in the corresponding RtpStreamResults object (if it exists)
                            # # Note: This is not transmitted by the receiver (because it's not part of the stats dictionary)
                            # # So has to be updated manually here
                            try:
                                # # get the instance of the corresponding RtpStreamResults object
                                # rtpStreamResults = self.rtpTxStreamResultsDict[self.syncSourceIdentifier]
                                # # Copy the entire RtpGenerator tracerouteHops list into the rtpStreamResults tracerouteHops list
                                # rtpStreamResults.setTraceRouteHopsList([])
                                if self.relatedRtpStreamResults is not None:
                                    ### Copy the traceroute hops list into the object instance var
                                    self.relatedRtpStreamResults.setTraceRouteHopsList([])
                            except Exception as e:
                                # Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread() update RtpStreamResults tracerouteHopList " + str(e))
                                pass

                # Increment traceroute loop counter
                tracerouteLoopCounter += 1
                # Sleep for 1 sec between completed traceroutes
                time.sleep(1)

        except Exception as e:
            Utils.Message.addMessage("ERR:Stream" + str(self.syncSourceIdentifier) + \
                                     "__tracerouteThread outer loop error. " + str(type(e)) + ", " + str(e))

        finally:
            try:
                if setupSuccessfulFlag:
                    # Thread is ending. Close sockets (but only if they were ever created)
                    if udpTx is not None:
                        udpTx.close()
                    if icmpRx is not None:
                        icmpRx.close()
            except Exception as e:
                Utils.Message.addMessage(
                    "ERR:Stream " + + str(self.syncSourceIdentifier) + \
                    " __tracerouteThread couldn't close sockets. " + str(type(e)) + ", " + str(e))

        Utils.Message.addMessage("DBUG:Stream " + str(self.syncSourceIdentifier) + \
                                 " __tracerouteThread ending ")


# An object that will act as a UDP receiver. It will receive server reports from ResultsTransmitter
class ResultsReceiver(object):
    # It is designed as a counterpart to class ResultsTransmitter
    # It sets up a listener on the source port used by it's related RtpGenerator tx stream.
    # Because you can't bind to the same addr/port twice, it therefore needs a reference to the
    # UDP socket created within the RtpGenerator itself. This is obtained using the
    # RtpGenerator.getUDPSocket() method
    def __init__(self,rtpGeneratorObject):
        self.relatedRtpGenerator = rtpGeneratorObject
        self.udpSocket = 0

        # This counts the receive errors reported by the unpickler routine in __resultsReceiverThread()
        # (normally caused by UDP transmission errors. Better than generating an error message and clogging
        # up the log file)
        self.receiveDecodeErrorCounter = 0
        # This counts the no results/events messages whos fragments were missing
        self.receiveResultsFragmentErrorCounter = 0
        # These counters allow an approximation of the return loss (from receiver back to transmitter) by
        # calculating the no of packets containing results that have been lost
        self.receiveResultsExpectedPacketsCounter = 0
        self.receiveResultsActualReceivedPacketsCounter = 0
        self.returnPacketLoss_pc = 0

        # Used a signal flag to shut the __resultsReceiverThread down
        self.receiverActiveFlag = True

        # Start the listener thread
        self.resultsReceiverThread = threading.Thread(target=self.__resultsReceiverThread, args=())
        self.resultsReceiverThread.daemon = False
        self.resultsReceiverThread.setName(str(self.relatedRtpGenerator.syncSourceIdentifier) + ":ResultsReceiver")
        self.resultsReceiverThread.start()


    def kill(self):
        # This method will kill the receiver thread by setting the self.receiverActiveFlag to false
        # It is a blocking method - it will nly return once the resultsReceiverThread has ended
        self.receiverActiveFlag = False
        Utils.Message.addMessage("INFO: ResultsReceiver.kill()")
        # Now wait for ResultsReceiverThread to end
        Utils.Message.addMessage("DBUG: ResultsReceiver.kill() Waiting for resultsReceiverThread to end")
        self.resultsReceiverThread.join()
        Utils.Message.addMessage("DBUG: ResultsReceiver.kill() resultsReceiverThread has ended")


        # Finally, attempt to remove the RtpStreamResults object created by __resultsReceiverThread from
        # the rtpTxStreamResultsDict

        # # Check to see if the RtpStreamResults object exists in rtpTxStreamResultsDict
        # if self.relatedRtpGenerator.syncSourceIdentifier in self.rtpTxStreamResultsDict:
        #     # If so, invoke its killStream method (to remove itself from rtpTxStreamResultsDict
        #     self.rtpTxStreamResultsDict[self.relatedRtpGenerator.syncSourceIdentifier].killStream()


    def __resultsReceiverThread(self):
        Utils.Message.addMessage("INFO: ResultsReceiver thread starting")

        rxMssage = b""  # Array (string IN BYTE FORMAT) to store the reconstructed message
        lastReceivedFragmentIndex = 0  # Tracks the most recently received fragment index (ie. which fragment within the set
        verboseLogging = True
        lastKnownUniqueID = 0 # Tracks the ID field unique to each set of fragments
        lastKnownExpectedNoOfFragments = 0 # Tracks the no of expected fragments that form the current message
        while self.receiverActiveFlag:
            # Wait for relatedRtpGenerator object to set up a socket binding
            self.udpSocket = self.relatedRtpGenerator.getUDPSocket()
            if self.udpSocket != 0:
                try:
                    # Wait for data (blocking function call)
                    data, addr = self.udpSocket.recvfrom(4096)  # buffer size is 4096 bytes
                    # increment the packets received counter
                    self.receiveResultsActualReceivedPacketsCounter += 1
                    # Recalculate the self.returnPacketLoss_pc
                    if self.receiveResultsExpectedPacketsCounter > 0:  # Avoid div by zero error
                        self.returnPacketLoss_pc = \
                            ((self.receiveResultsExpectedPacketsCounter - \
                              self.receiveResultsActualReceivedPacketsCounter) / \
                             self.receiveResultsExpectedPacketsCounter) * 100
                    # Utils.Message.addMessage("DBUG: ResultsReceiver.__receiverThread()" + ", " + str(data))
                    # attempt to unpickle the received data to yield a stats dictionary

                    # Create empty dictionary to hold incoming stats updates
                    stats = {}
                    # Create empty list to store incoming events list updates
                    latestEventsList =[]

                    # First round of unpickling - extract the fragment (a tuple)
                    # Each tuple will be of the form [a,b,c,d,e] where
                    # a = the index no of this portion,
                    # b = the total no of portions (packets)
                    # c = total length of reconstructed string
                    # d is the portion itself
                    # e is a random integer that serves as unique ID for this set of fragments
                    try:
                        fragment = pickle.loads(data)
                        # Utils.Message.addMessage("Fragment " + str(fragment[0] + 1) + "/" + str(fragment[1]))
                        # detect first fragment
                        if fragment[0] == 0:
                            # If we are receiving a zero index fragment but we've yet to receive all the fragments
                            # from a previous message, that suggests we've lost some fragments (packets)
                            # Check to see if we have any outstanding fragments expected. If so, add to the error count
                            if lastReceivedFragmentIndex < (lastKnownExpectedNoOfFragments - 1):
                                if verboseLogging:
                                    Utils.Message.addMessage(
                                        "INFO: __resultsReceiverThread.Incomplete set of fragments. Resetting to zero ",
                                            logToDisk=False)
                                self.receiveResultsFragmentErrorCounter += 1


                            # Clear away any existing contents of rxMessage
                            rxMssage = b""
                            # Append the message portion of this fragment to rxMessage
                            rxMssage =b"".join([rxMssage,fragment[3]])

                            # Record the index no of the last received fragment
                            lastReceivedFragmentIndex = fragment[0]

                        # Detect next expected fragment
                        elif fragment[0] == (lastReceivedFragmentIndex + 1):
                            # Append the message portion of this fragment to rxMessage
                            rxMssage =b"".join([rxMssage,fragment[3]])
                            # Record the index no of the last received fragment
                            lastReceivedFragmentIndex = fragment[0]


                        # Else, something went wrong = we have an out of sequence fragment
                        else:
                            self.receiveResultsFragmentErrorCounter += 1
                            # Detect too many fragments
                            if fragment[0] > (fragment[1] - 1):
                                # More fragments than expected
                                if verboseLogging:
                                    Utils.Message.addMessage(
                                        "INFO: __resultsReceiverThread. More fragments received than expected " +\
                                        str(fragment[0]) + "/" + str(fragment[1]), logToDisk=False)
                            elif fragment[0] != (lastReceivedFragmentIndex + 1):
                                # Out of sequence fragment received
                                if verboseLogging:
                                    Utils.Message.addMessage(
                                        "INFO: __resultsReceiverThread. Out of sequence fragment. Expected " + \
                                        str(lastReceivedFragmentIndex + 1) + ", got " + str(fragment[0]), logToDisk=False)
                            else:
                                # Catch anything else
                                Utils.Message.addMessage(
                                    "INFO: __resultsReceiverThread. Unexpected fragment " + \
                                    str(fragment[0]) + "/" + str(fragment[1]), logToDisk=False)

                        # Now check to see if this is the *final* fragment we were expecting (note fragment[0] is a zero indexed value
                        # i.e. have we received the entire message (all the fragments, and expected length)?
                        if fragment[0] == (fragment[1] - 1):
                            # # Recalculate the self.returnPacketLoss_pc
                            # if self.receiveResultsExpectedPacketsCounter > 0:  # Avoid div by zero error
                            #     self.returnPacketLoss_pc = \
                            #         ((self.receiveResultsExpectedPacketsCounter - \
                            #           self.receiveResultsActualReceivedPacketsCounter) / \
                            #          self.receiveResultsExpectedPacketsCounter) * 100

                            # Confirm that the received length of all the reconstructed fragments is as expected
                                if len(rxMssage) == fragment[2]:
                                    # Whole message has hopefully been reassembled
                                    # Now unpickle (for a second time) to reconstruct the originally pickled and tx'd Python object

                                    # We're expecting a dictionary containing a stats dictionary{} and an eventsList{} containing the
                                    # last 5 events
                                    try:
                                        # firstly check to see whether the pickle incomig data was compressed before sending
                                        if Registry.rtpReceiveStreamCompressResultsBeforeSending:
                                            # uncompress the data
                                            rxMssage = bz2.decompress(rxMssage)
                                        # Attempt to reconstruct the original message sent by ResultsTransmitter
                                        # unPickledMessage = pickle.loads(rxMssage, fix_imports=True)
                                        unPickledMessage = pickle.loads(rxMssage)
                                        # Utils.Message.addMessage("DBG:" + str(unPickledMessage))

                                        # Attempt to extract the stats dictionary and eventsList list

                                        if "stats" in unPickledMessage:
                                            stats = unPickledMessage["stats"]
                                        if "eventList" in unPickledMessage:
                                            latestEventsList = unPickledMessage["eventList"]
                                        if "control" in unPickledMessage:
                                            controlMessage = unPickledMessage["control"]
                                            Utils.Message.addMessage(
                                                "DBUG:__resultsReceiverThread() Control Message Rx'd: " + \
                                                str(controlMessage))
                                            # Pass the message to the RtpGenerator Control Message queue
                                            self.relatedRtpGenerator.addControlMessage(controlMessage)
                                    except Exception as e:
                                        # Utils.Message.addMessage("ERR: __resultsReceiverThread(pickle.loads(all fragments)): " + str(e))
                                        # Increment the receive error counter
                                        Utils.Message.addMessage(
                                            "ERR: __resultsReceiverThread (error unpickling stats/Events/control dicts): " + str(
                                                e))
                                        self.receiveDecodeErrorCounter += 1
                                else:
                                    if verboseLogging:
                                        Utils.Message.addMessage(
                                            "ERR: __resultsReceiverThread. Last fragment received but wrong length. Expt'd: " +\
                                            str(fragment[2]) + ", got " + str(len(rxMssage)) + " bytes")

                        # Check to see if this fragment is part of a new set by comparing lastKnownUniqueID
                        if fragment[4] == lastKnownUniqueID:
                            # This fragment is part of the current set of fragments
                            pass
                        else:
                            # This is a new set of fragments with a new uniqueID
                            # Snapshot the latest ID
                            lastKnownUniqueID = fragment[4]
                            # Snapshot the no of fragments we will be expecting as part of this message
                            lastKnownExpectedNoOfFragments = fragment[1]
                            # Update the 'expected' packets counter (we can only do this once, per set of fragments)
                            self.receiveResultsExpectedPacketsCounter += fragment[1]

                    except Exception as e:
                        Utils.Message.addMessage("ERR: __resultsReceiverThread(single fragment): Unpickling error " + str(e))

                    # Check if we have some new stats data
                    if len(stats) > 0:
                        # Now perform a validation of the stas dictionary by attempting to iterate over the dictionary
                        lastValidatedKey = None
                        statsValidated = False
                        try:
                            for key in stats:
                                lastValidatedKey = stats[key]
                                statsValidated = True
                        except Exception as e:
                            Utils.Message.addMessage(
                                "ERR:__resultsReceiverThread stats validation failed. Last validated key: " + \
                                str(lastValidatedKey))
                            # Validation failed so clear the flag
                            statsValidated = False

                        if statsValidated:
                            try:
                                # Firstly check to see if the RtpStreamResults object already exists for this stream
                                if self.relatedRtpGenerator.relatedRtpStreamResults is not None:
                                    # It does exist, so get a handle on it
                                    rtpStreamResults = self.relatedRtpGenerator.relatedRtpStreamResults
                                    # And update the stats
                                    rtpStreamResults.updateStats(stats)
                                else:
                                    # Otherwise that stream object doesn't exist yet, so create it
                                    Utils.Message.addMessage("INFO:_resultsReceiverThread(). Stream doesn't exist, adding: "
                                                       + str(stats["stream_syncSource"]))
                                    # Create new RtpStreamResults object
                                    rtpStreamResults = RtpStreamResults(stats["stream_syncSource"],
                                                                        controllerTCPPort=self.relatedRtpGenerator.controllerTCPPort)


                                    # Pass the rtpStreamResults back to the related RtpGenerator object
                                    self.relatedRtpGenerator.relatedRtpStreamResults = rtpStreamResults
                                    # Immediately update the stats
                                    rtpStreamResults.updateStats(stats)

                            except Exception as e:
                                Utils.Message.addMessage("ERR: __resultsReceiverThread. Invalid stats dict or can't add new stream to rtpTxStreamResultsDict. " + str(e))

                    # Check to see if the new eventList contains any data and also that there exists a stream object to add the data to
                    if len(latestEventsList) > 0 and len(stats) > 0:
                        try:
                            # validate each of the newly received events to check that they have not been corrupted by
                            # the pickling/unpickling process.
                            # Validate by calling the events getJson() method. If this succeeds, we can assume that
                            # the received Event object is intact (because it accesses all stored data within the Event)
                            # Iterate over all the events in latestEventsList. If there's a failure, an exception
                            # will be raised and this batch of received events discarded
                            eventsValidated = False
                            lastValidatedEventNo = 0
                            for event in latestEventsList:
                                try:
                                    # 'Test' that the event works, by calling its getJSON() method
                                    validatedEvent = event.getJSON()
                                    # Update lastValidatedEventNo - used for debugging
                                    lastValidatedEventNo = event.eventNo
                                    # Event validated, so set the flag
                                    eventsValidated = True
                                except Exception as e:
                                    Utils.Message.addMessage("ERR:__resultsReceiverThread Event validation failed. Last validated event: " +\
                                                             str(lastValidatedEventNo))
                                    # Validation failed so clear the flag
                                    eventsValidated = False
                                    # Break out of the loop
                                    break

                            # If all the received events in latestEventsList are valid, update the events list for the specified stream
                            if eventsValidated:
                                # Utils.Message.addMessage("DBUG: **latestEventsList: " + str(latestEventsList[-1].eventNo))
                                syncSourceID = stats["stream_syncSource"]
                                # Get handle on an (existing) RtpStreamResults object
                                rtpStreamResults = self.relatedRtpGenerator.relatedRtpStreamResults

                                # Update (All) Events list
                                try:
                                    # Get the last event no from the latest received batch
                                    lastEventNoInNewList = latestEventsList[-1].eventNo
                                    # Get latest known event no from the rtpStreamResults stream object
                                    existingEventsList = rtpStreamResults.getRTPStreamEventList(1) # Request last event in the list
                                    # Update Events list for this object
                                    if len(existingEventsList) > 0:
                                        # # Extract the event no from the last known event
                                        lastKnownEventNo = existingEventsList[-1].eventNo

                                        # Check to see if the latest event no appears to be less than the previous known
                                        # event no. This could be because the stats at the Receiver were reset mid test.
                                        # If this is the case, delete the existing stored event list and restart the list
                                        if lastEventNoInNewList < lastKnownEventNo:
                                            Utils.Message.addMessage("Stats/Event list for stream " + str(syncSourceID) +\
                                                                     " has been reset by receiver")
                                            # Remove the old events list and start again
                                            rtpStreamResults.updateEventsList(latestEventsList, replaceExistingList=True)

                                        # Check if the latest item in the new list is more recent than the last item of the known list
                                        elif lastEventNoInNewList > lastKnownEventNo:
                                            # Calculate how many new events have arrived
                                            eventsToAdd = lastEventNoInNewList - lastKnownEventNo

                                            # append the last n new events to the existing eventList
                                            # check to see if the no of new events since last update exceeds
                                            # length of latestEventsList[]
                                            if eventsToAdd > len(latestEventsList):
                                                eventsToAdd = len (latestEventsList)
                                            # Slice latestEventsList to get a sublist of just the new events
                                            newEvents = latestEventsList[(eventsToAdd * -1):]
                                            # and append to existing events list
                                            rtpStreamResults.updateEventsList(newEvents)
                                    else:
                                        # existingEventsList is empty so append the entirety of latestEventsList
                                        rtpStreamResults.updateEventsList(latestEventsList)
                                    # Utils.Message.addMessage("DBUG:**" + str(rtpStreamResults.getRTPStreamEventList(1)))
                                except Exception as e:
                                    Utils.Message.addMessage(
                                        "ERR:_resultsReceiverThread(). rtpStreamResults.getRTPStreamEventList(1) " + str(e))
                        except Exception as e:
                            Utils.Message.addMessage("ERR:_resultsReceiverThread(): rtpStreamResults. validate/updateEventsList() " + str(e))


                # socket is set with a timeout, so need to catch timeouts but can ignore them
                except socket.timeout:
                    # Utils.Message.addMessage("DBUG: ResultsReceiver socket.recvfrom() timeout")
                    pass

                # Catch all other exceptions
                except Exception as e:
                    Utils.Message.addMessage("ERR: __resultsReceiverThread sock.recvfrom() "+str(e))
            else:
                # Wait 1 second before checking to see if self.udpSocket is now valid
                time.sleep(1)
        Utils.Message.addMessage("INFO: ResultsReceiver:__resultsReceiverThread ended")

# This class provides a means of comparing the performance stats of multiple Rtp receive streams
class RtpStreamComparer_old(object):

    # Takes a pointer to the dictionary containing all the RTP Stream objects to be compared
    # These are expected to be RtpReceiveCommon objects (or their subclasses)
    def __init__(self, rtpStreamsDict) -> None:
        super().__init__()
        self.rtpStreamsDict = rtpStreamsDict

    # This method iterates over rtpStreamsDict and examines the stats[statsKeyToCompare] parameter.
    # It will then return an ordered list of dictionaries containing [{friendlyName, syncSourceID, statsKeyToCompare, value}]
    # It is expected that these results will be displayed somewhere
    # If reverseOrder==True, the returned list will be in descending order of value
    def compareByKey(self, statsKeyToCompare, reverseOrder = False):
        unsortedList = []  # Holds the list of streams that are being compared
        try:
            if len(self.rtpStreamsDict) > 0:
                # Take shallow copy of rtpStreamsDict (just case it changes size mid-iteration)
                rtpStreamsDict = dict(self.rtpStreamsDict)
                # Iterate over the Rtp stream object keys
                for rtpStream in rtpStreamsDict:
                    # Get stats object for the current stream
                    stats = self.rtpStreamsDict[rtpStream].getRtpStreamStats()
                    # Create a small dict containing the specified stats key and value
                    streamStatsToBeCompared = {
                                                "syncSourceID": stats["stream_syncSource"],
                                                "friendlyName": stats["stream_friendly_name"],
                                                "statsKeyToCompare": statsKeyToCompare,
                                                "value": stats[statsKeyToCompare],
                                                "relatedEvent": None # If appropriate, this will hold a reference to the event
                                                                # relevant to the current comparison measure
                                                }
                    # Now populate the streamStatsToBeCompared["eventNo"] if relevant to the current stats key being compared
                    if statsKeyToCompare == "glitch_most_recent_timestamp" or\
                            statsKeyToCompare == "glitch_packets_lost_per_glitch_max" or\
                            statsKeyToCompare == "glitch_max_glitch_duration":
                        # Request the specific event that relates to this measure
                        relatedEventList = \
                            self.rtpStreamsDict[rtpStream].getRTPStreamEventList(requestedEventNo=stats["glitch_most_recent_eventNo"])
                        # If the event has been located, add it to the streamStatsToBeCompared[] dict
                        if len(relatedEventList) > 0:
                            streamStatsToBeCompared["relatedEvent"] = relatedEventList[0]

                    # Test for special cases of values that cannot be sorted (zero or None values/exceptions)
                    if statsKeyToCompare == "glitch_most_recent_timestamp" and \
                            type(streamStatsToBeCompared["value"]) == datetime.timedelta:
                        # NOTE: stats[glitch_most_recent_timestamp] is initialised as a datetime.timedelta object
                        # If not glitches are recorded it'll stay that way.
                        # Once a glitch occurs it will be set as a datetime.datetime object and these two types
                        # cannot be sorted using sorted() (raises an Exception) therefore it's easiest just to
                        # exclude from the list of items to be sorted
                        pass
                    elif streamStatsToBeCompared["value"] == None or \
                            streamStatsToBeCompared["value"] == datetime.timedelta(seconds=0): # Ignores time values of '00:00:00'
                        # Catch-all for any values that might be None
                        pass
                    else:
                        # Otherwise append the dict to the unsorted list
                        unsortedList.append(streamStatsToBeCompared)

                # Now sort the list by the value of statsKeyToCompare
                # Based on code here: https://www.kite.com/python/answers/how-to-sort-a-list-of-lists-by-an-index-of-each-inner-list-in-python
                sorted_list = sorted(unsortedList, key=lambda x: x["value"], reverse=reverseOrder)
                return sorted_list

        except Exception as e:
            Utils.Message.addMessage("ERR:RtpStreamComparer.compareByKey (" + str(statsKeyToCompare) + ", " + str(e))
            # Return None
            return None

    # Provides a comparison of all streams
    # Returns a dict of stats
    def compareAll(self):
        # Define the mean stats to be calculated
        # Each calculation defined by a tuple [Rtp Stream stats key to be used, friendly name of the key, the defauly value]
        # The friendly name and value fields will then be used to construct a dictionary that will be returned to the caller
        statsKeysToCompare = [["glitch_packets_lost_total_percent", "Mean packet loss %", 0],
                              ["glitch_mean_time_between_glitches", "Mean glitch period (how often)", datetime.timedelta()],
                              ["glitch_mean_glitch_duration", "Mean glitch duration", datetime.timedelta()],
                              ["glitch_packets_lost_per_glitch_mean", "Mean glitch packet loss", 0]
                            ]

        allStreamsStatsDict = {} # The dictionary that will be returned
        # Take shallow copy of rtpStreamsDict (just case it changes size mid-iteration)
        rtpStreamsDict = dict(self.rtpStreamsDict)

        # Iterate over keys to assemble an an array containing all the individual stats dicts for all streams
        statsForAllStreams = []
        try:
            for stream in rtpStreamsDict:
                statsForAllStreams.append(rtpStreamsDict[stream].getRtpStreamStats())

            # Now calculate the mean values across all streams for each of the keys listed in statsKeysToCompare
            for stat in statsKeysToCompare:
                # Collect all values of the key stat in statsForAllStreams
                currentKeyValueToExtract = stat[0]
                # Explanation of this line (or see https://stackoverflow.com/a/11093436):-
                # This is 'list comprehension'
                #   'for x in statsForAllStreams' # iterates over the statsForAllStreams list yielding 'x'
                # 'x[currentKeyValueToExtract]' # since each 'x' is a RtpStream stats dictionary, we want
                # to extract only the value corresponding to the key specified by currentKeyValueToExtract
                # '[ ]' # Put the extracted value in a new list
                values = []
                values = [x[currentKeyValueToExtract] for x in statsForAllStreams]

                # Now we need to calculate the mean value of the values in values[]
                if len(values) > 0:
                    # Check the type of the values in the list. If they are timedelta objects, the mean will
                    # have to be calculated differently. See https://stackoverflow.com/a/3617540
                    start = 0 # The start value for sum(). This will be overwritten in the list contains datetime objects
                    if type(values[0]) == datetime.timedelta:
                        start = datetime.timedelta(0)
                    # Calculate the mean and assign back to the value in the current statsKeysToCompare[] list
                    stat[2] = sum(values, start) / len (values)

            # Dynamically create dict to be returned by compareAll()
            # Note: The function will return a 'humanised' value
            for item in statsKeysToCompare:
                key = item[1]
                # extract and humanise the value
                value = RtpReceiveCommon.humanise(item[0], item[2], appendUnit=True)
                allStreamsStatsDict[key] = value

        except Exception as e:
            Utils.Message.addMessage("RtpStreamComparer.compareAll() " + str(e))

        return allStreamsStatsDict

    # Generates a formatted report ranking the streams in order of the comparison
    # criteria (stats[] keys) specified in the statsKeysToCompare list
    # This is a list of string tuples [stats key, friendly name]
    # listOrder specifies sort ascending or descending
    def generateReport(self, statsKeysToCompare, listOrder=False):
        # Simple local function to determine the current operation mode based on the type of object instances
        # present in self.rtpStreamsDict. Returns a string
        def getOperationMode(_rtpStreamsDict):
            # Iterate over rtpStreamsDict to determine what objects are present
            if len(self.rtpStreamsDict) > 0:
                # Take shallow copy of rtpStreamsDict (just case it changes size mid-iteration)
                rtpStreamsDict = dict(_rtpStreamsDict)
                # Assume that all the objects in the list are of the same type (therefore loop only needs to run once)
                for key in rtpStreamsDict:
                    if type(rtpStreamsDict[key]) == RtpStreamResults:
                        return "TRANSMIT"
                    elif type(rtpStreamsDict[key]) == RtpReceiveStream:
                        return "RECEIVE"
                    else:
                        return "UNKNOWN"

        try:
            labelWidth = 33
            friendlyNameLength = RtpGenerator.getMaxFriendlyNameLength()
            separator = ("-" * 63) + "\r\n"
            streamReport = "Rtp stream performance comparison " + "\r\n"
            streamReport += "Generated by isptest v" + str(Registry.version) + \
                       " running in " + str(getOperationMode(self.rtpStreamsDict)) + " mode at " + \
                       datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\r\n"

            streamReport += separator

            # Retrieve overall stream stats
            overallStats = self.compareAll()
            streamReport += "Overall stream stats:-\r\n"
            for key, value in overallStats.items():
                streamReport += str(key).rjust(labelWidth) + ": " + str(value) + "\r\n"
            streamReport += separator

            # Generate stream comparisons for all the keys listed in statsKeysToCompare
            # Each stream comparison will get its own tabulated table
            if len(statsKeysToCompare) > 0:
                for key in statsKeysToCompare:
                    comparisonCriteria = key[0]
                    comparisonCriteriaFriendlyName = key[1]
                    # retrieve the comparison results for each criteria in turn
                    sortedStreamsList = self.compareByKey(comparisonCriteria, reverseOrder=listOrder)
                    if sortedStreamsList is not None and len(sortedStreamsList) > 0:
                        # Column titles
                        streamReport += comparisonCriteriaFriendlyName + "\r\n"
                        # Construct a tabulated table
                        # streamReport += "\t" + "Name".ljust(friendlyNameLength) + "\r\n"
                        for index in range(len(sortedStreamsList)):
                            streamName = sortedStreamsList[index]["friendlyName"]
                            # humanise the value
                            value = RtpReceiveCommon.humanise(sortedStreamsList[index]["statsKeyToCompare"], \
                                                                sortedStreamsList[index]["value"], appendUnit=True)
                            # If the relatedEvent key has been populated, we can attempt to retrieve that event from the eventsList
                            # to add some more detail to the comparison table
                            eventSummaryFormattedText = ""
                            if sortedStreamsList[index]["relatedEvent"] is not None:
                                try:
                                    # Get an eventSummary
                                    relatedEvent = sortedStreamsList[index]["relatedEvent"].getSummary(
                                        includeStreamSyncSourceID=False,
                                        includeEventNo=False,
                                        includeType=False,
                                        includeFriendlyName=False)

                                    eventCreated = relatedEvent["timeCreated"].strftime("%d/%m %H:%M:%S")
                                    eventSummary = relatedEvent["summary"]  # Summary in the form of a text string
                                    eventSummaryFormattedText = eventCreated + ", " + eventSummary
                                except Exception as e:
                                    Utils.Message.addMessage(
                                        "ERR: ERR:RtpStreamComparer.generateReport() - lookup event " + str(e))

                            # Create the table row
                            streamReport += str(index + 1) + "\t" + \
                                str(streamName).rjust(friendlyNameLength) + " " + str(value) + "\t" + eventSummaryFormattedText + "\r\n"
                        streamReport += separator

            return streamReport
        except Exception as e:
            Utils.Message.addMessage("ERR:RtpStreamComparer " + str(e))
            return None

# This class provides a means of comparing the performance stats of multiple Rtp streams
# It takes a list of stream definitions of the available streams
# For certain comparisons it will look up the relevant Event by querying the api of the stream where the event occurred
class RtpStreamComparer(object):
    # Takes a pointer to the list containing all the currently available stream definitions
    def __init__(self, availableStreamsList) -> None:
        super().__init__()
        # Take local shallow copy of incoming list (just in case it changes size mid-iteration)
        self.availableStreamsList = list(availableStreamsList)
        # A list of dicts to contain a list of the stats dicts of all available streams
        self.statsForAllStreams = []
        # Iterate over availableStreamsList to build a list of dicts containing the stats for each stream
        for stream in self.availableStreamsList:
            try:
                # Create an API helper for each stream
                api = Utils.APIHelper(stream["httpPort"])
                # Retrieve the stats dict for the current stream
                self.statsForAllStreams.append(api.getStats())
            except Exception as e:
                Utils.Message.addMessage(f"ERR:RtpStreamComparer.__init__(): get stream stats {e}")

    # This method iterates over rtpStreamsStatsList and examines the stats[statsKeyToCompare] parameter.
    # It will then return an ordered list of dictionaries containing [{friendlyName, syncSourceID, statsKeyToCompare, value}]
    # It is expected that these results will be displayed somewhere
    # If reverseOrder==True, the returned list will be in descending order of value
    def compareByKey(self, statsKeyToCompare, reverseOrder = False):
        unsortedList = []  # Holds the list of streams that are being compared
        try:
            # # Take shallow copy of rtpStreamsStatsList (just case it changes size mid-iteration)
            # rtpStreamsStatsList = list(self.rtpStreamsStatsList)
            # # Iterate over the Rtp stream object keys

            for stats in self.statsForAllStreams:
                # # Get stats object for the current stream
                # stats = self.rtpStreamsDict[rtpStream].getRtpStreamStats()
                # Create a small dict containing the specified stats key and value
                streamStatsToBeCompared = {
                                            "syncSourceID": stats["stream_syncSource"],
                                            "friendlyName": stats["stream_friendly_name"],
                                            "statsKeyToCompare": statsKeyToCompare,
                                            "value": stats[statsKeyToCompare],
                                            "relatedEvent": None # If appropriate, this will hold a reference to the event
                                                            # relevant to the current comparison measure
                                            }
                # Now populate the streamStatsToBeCompared["eventNo"] if relevant to the current stats key being compared
                if statsKeyToCompare == "glitch_most_recent_timestamp" or\
                        statsKeyToCompare == "glitch_packets_lost_per_glitch_max" or\
                        statsKeyToCompare == "glitch_max_glitch_duration":
                    # Request the specific event that relates to this measure using
                    # relatedEventList = \
                    #     self.rtpStreamsDict[rtpStream].getRTPStreamEventList(requestedEventNo=stats["glitch_most_recent_eventNo"])
                    # Do a reverse lookup to get the httpPort for the stream for which we want to retrieve the event details
                    # To do this, we filter self.availableStreamsList to isolate the stream definition with a matching
                    # sync source ID. This should yield a list containing a single element
                    # We then extract the api HTTP port for that stream
                    apiHTTPPort = list(filter(lambda stream: stream["streamID"] == int(stats["stream_syncSource"]),
                                              self.availableStreamsList))[0]["httpPort"]
                    # Get the specific related event via the streams' api
                    relatedEventList = \
                        Utils.APIHelper(apiHTTPPort).getRTPStreamEventListAsSummary(requestedEventNo=stats["glitch_most_recent_eventNo"],
                                                                                    includeStreamSyncSourceID=False,
                                                                                    includeEventNo=False,
                                                                                    includeType=False,
                                                                                    includeFriendlyName=False
                                                                                    )
                    # If the event has been located, add it to the streamStatsToBeCompared[] dict
                    if len(relatedEventList) > 0:
                        streamStatsToBeCompared["relatedEvent"] = relatedEventList[0]

                # Test for special cases of values that cannot be sorted (zero or None values/exceptions)
                if statsKeyToCompare == "glitch_most_recent_timestamp" and \
                        type(streamStatsToBeCompared["value"]) == datetime.timedelta:
                    # NOTE: stats[glitch_most_recent_timestamp] is initialised as a datetime.timedelta object
                    # If not glitches are recorded it'll stay that way.
                    # Once a glitch occurs it will be set as a datetime.datetime object and these two types
                    # cannot be sorted using sorted() (raises an Exception) therefore it's easiest just to
                    # exclude from the list of items to be sorted
                    pass
                elif streamStatsToBeCompared["value"] == None or \
                        streamStatsToBeCompared["value"] == datetime.timedelta(seconds=0): # Ignores time values of '00:00:00'
                    # Catch-all for any values that might be None
                    pass
                else:
                    # Otherwise append the dict to the unsorted list
                    unsortedList.append(streamStatsToBeCompared)

            # Now sort the list by the value of statsKeyToCompare
            # Based on code here: https://www.kite.com/python/answers/how-to-sort-a-list-of-lists-by-an-index-of-each-inner-list-in-python
            sorted_list = sorted(unsortedList, key=lambda x: x["value"], reverse=reverseOrder)
            return sorted_list

        except Exception as e:
            Utils.Message.addMessage("ERR:RtpStreamComparer.compareByKey (" + str(statsKeyToCompare) + ", " + str(e))
            # Return None
            return None

    # Provides a comparison of all streams by generating some mean averages
    # Returns a dict of stats
    def compareAll(self):
        # Define the mean stats to be calculated
        # Each calculation defined by a dict {Rtp Stream stats key to be used, friendly name of the key, the defauly value}
        # The friendly title and value fields will then be used to construct a dictionary that will be returned to the caller
        statsKeysToCompare = [{"keyToCompare": "glitch_packets_lost_total_percent", "friendlyTitle": "Mean packet loss %", "result": 0},
                              {"keyToCompare": "glitch_mean_time_between_glitches", "friendlyTitle": "Mean glitch period (how often)", "result": datetime.timedelta()},
                              {"keyToCompare": "glitch_mean_glitch_duration", "friendlyTitle": "Mean glitch duration", "result": datetime.timedelta()},
                              {"keyToCompare": "glitch_packets_lost_per_glitch_mean", "friendlyTitle": "Mean glitch packet loss", "result": 0}
                            ]

        resultsDict = {}    # The dictionary that will be returned
        # Iterate over keys to assemble an an array containing all the individual stats dicts for all streams
        # statsForAllStreams = []
        try:
            # Now calculate the mean values across all streams for each of the keys listed in statsKeysToCompare
            for stat in statsKeysToCompare:
                # Collect all values of the key stat in statsForAllStreams
                currentKeyValueToExtract = stat["keyToCompare"]
                # Explanation of this line (or see https://stackoverflow.com/a/11093436):-
                # This is 'list comprehension'
                #   'for x in statsForAllStreams' # iterates over the statsForAllStreams list yielding 'x'
                # 'x[currentKeyValueToExtract]' # since each 'x' is a RtpStream stats dictionary, we want
                # to extract only the value corresponding to the key specified by currentKeyValueToExtract
                # Additionally, we preemptively convert values from a string to a python datetime or timedelta object
                # using Utils.convertStringToTimeDelta(). If it is not a timedelta or datetime object
                # it will remain unchanged
                # '[ ]' # Put the extracted value in a new list
                values = [Utils.convertStringToTimeDelta(x[currentKeyValueToExtract]) for x in self.statsForAllStreams]

                # Now we need to calculate the mean value of the values in values[]
                if len(values) > 0:
                    # Check the type of the values in the list. If they are timedelta objects, the mean will
                    # have to be calculated differently. See https://stackoverflow.com/a/3617540
                    start = 0 # The start value for sum(). This will be overwritten in the list contains datetime objects
                    if type(values[0]) == datetime.timedelta:
                        start = datetime.timedelta(0)
                    # Calculate the mean and assign back to the value in the current statsKeysToCompare[] dict
                    try:
                        stat["result"] = sum(values, start) / len(values)
                    except Exception as e:
                        raise Exception(f"sum(values, start) values:{values}, start:{start}, {e}")

            # Dynamically create dict to be returned by compareAll()
            # Note: The function will return a 'humanised' value
            for item in statsKeysToCompare:
                friendlyTitle = item["friendlyTitle"]
                # extract and humanise the value
                try:
                    value = RtpReceiveCommon.humanise(item["keyToCompare"], item["result"], appendUnit=True)
                    resultsDict[friendlyTitle] = value
                except:
                    raise Exception("humanise()")

        except Exception as e:
            Utils.Message.addMessage("ERR:RtpStreamComparer.compareAll() " + str(e))

        return resultsDict

    # Generates a formatted report ranking the streams in order of the comparison
    # criteria (stats[] keys) specified in the statsKeysToCompare dict
    # This is a list of string dicts {stats key, friendly name}
    # listOrder specifies sort ascending or descending
    # By default each key comparison will yield a table with three columns [index, friendlyName, value]
    # If includeSyncSourceID is true, the SyncSourceID column will also be added
    def generateReport(self, statsKeysToCompare, listOrder=False, includeSyncSourceID=True):
        # Simple local function to determine the current operation mode based on the type of object instances
        # present in self.rtpStreamsDict. Returns a string
        def deduceOperationMode(streamsList):
            # Iterate over rtpStreamsDict to determine what objects are present
            if len(streamsList) > 0:
                # Take shallow copy of self.availableStreamsList (just case it changes size mid-iteration)
                rtpStreamsList = list(streamsList)
                # Assume that all the objects in the list are of the same type (therefore loop only needs to run once)
                for stream in rtpStreamsList:
                    if stream["streamType"] == "RtpReceiveStream":
                        return "RECEIVE"
                    elif stream["streamType"] == "RtpGenerator":
                        return "TRANSMIT"
                    else:
                        return "UNKNOWN"
        try:
            labelWidth = 33
            friendlyNameLength = RtpGenerator.getMaxFriendlyNameLength()
            separator = ("-" * 63) + "\r\n"
            streamReport = "Rtp stream performance comparison " + "\r\n"
            streamReport += "Generated by isptest v" + str(Registry.version) + \
                       " running in " + str(deduceOperationMode(self.availableStreamsList)) + " mode at " + \
                       datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\r\n"

            streamReport += separator

            # Retrieve overall stream stats
            overallStats = self.compareAll()
            streamReport += "Overall stream stats:-\r\n"
            for key, value in overallStats.items():
                streamReport += str(key).rjust(labelWidth) + ": " + str(value) + "\r\n"
            streamReport += separator

            # Generate stream comparisons for all the keys listed in statsKeysToCompare
            # Each stream comparison will get its own tabulated table
            if len(statsKeysToCompare) > 0:
                for key in statsKeysToCompare:
                    comparisonCriteria = key["keyToCompare"]
                    comparisonCriteriaFriendlyTitle = key["friendlyTitle"]
                    # retrieve the comparison results for each criteria in turn
                    sortedStreamsList = self.compareByKey(comparisonCriteria, reverseOrder=listOrder)
                    if sortedStreamsList is not None and len(sortedStreamsList) > 0:
                        # Column titles
                        streamReport += comparisonCriteriaFriendlyTitle + "\r\n"
                        # Construct a tabulated table
                        # streamReport += "\t" + "Name".ljust(friendlyNameLength) + "\r\n"
                        for index in range(len(sortedStreamsList)):
                            streamName = sortedStreamsList[index]["friendlyName"]
                            streamSyncSourceID = sortedStreamsList[index]["syncSourceID"]
                            # humanise the value
                            value = RtpReceiveCommon.humanise(sortedStreamsList[index]["statsKeyToCompare"], \
                                                                sortedStreamsList[index]["value"], appendUnit=True)
                            # If the relatedEvent key has been populated, we can attempt to retrieve that event from the eventsList
                            # to add some more detail to the comparison table
                            eventSummaryFormattedText = ""
                            if sortedStreamsList[index]["relatedEvent"] is not None:
                                try:
                                    # Get an eventSummary/time created for the Event relating to this stat
                                    # Get the time created and humanise
                                    eventCreated = RtpReceiveCommon.humanise("",
                                                            sortedStreamsList[index]["relatedEvent"]["timeCreated"])
                                    # Get the Event summary as a text string
                                    eventSummary = sortedStreamsList[index]["relatedEvent"]["summary"]
                                    eventSummaryFormattedText = eventCreated + ", " + eventSummary
                                except Exception as e:
                                    Utils.Message.addMessage(
                                        "ERR:RtpStreamComparer.generateReport() - lookup event " + str(e))

                            if includeSyncSourceID:
                                # Create the table row (including the syncSourceID)
                                # streamReport += str(index + 1) + "\t" + \
                                #                 str(streamName).rjust(friendlyNameLength) + " " + str(
                                #     value) + "\t" + eventSummaryFormattedText + "\r\n"
                                streamReport += f"{index+1}\t[{streamSyncSourceID}]{str(streamName).rjust(friendlyNameLength)} "\
                                                f"{value}\t{eventSummaryFormattedText}\r\n"
                            else:
                                # Otherwise create a table row without the syncSourceID
                                streamReport += str(index + 1) + "\t" + \
                                    str(streamName).rjust(friendlyNameLength) + " " + str(value) + "\t" + eventSummaryFormattedText + "\r\n"
                        streamReport += separator

            return streamReport
        except Exception as e:
            Utils.Message.addMessage("ERR:RtpStreamComparer " + str(e))
            return None
# # Define a custom HTTPServer. This will allow access to the associated RtpReceiveStream object that created it
# class RtpStreamHTTPServer(HTTPServer):
#     def __init__(self, *args, **kwargs):
#         # Because HTTPServer is an old-style class, super() can't be used.
#         HTTPServer.__init__(self, *args, **kwargs)
#         self.rtpStream = None
#
#     # Provide a setter method to allow the server to have access to the RtpStream object that created it
#     # The reason not to have this set by the Constructor method is that I didn't want to modify the existing
#     # constructor method of HTTPServer
#     def setRtpStream(self, parentRtpStreamInstance):
#         self.rtpStream = parentRtpStreamInstance