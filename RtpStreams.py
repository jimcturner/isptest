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
import platform
from functools import reduce
from queue import SimpleQueue, Queue, Empty, Full
from timeit import default_timer as timer  # Used to calculate elapsed time
import math
import json
from abc import ABCMeta, abstractmethod  # Used for event abstract class
from copy import deepcopy
import pickle
from collections import deque   # Used for circular buffers
from pathvalidate import ValidationError, validate_filename, sanitize_filepath
# from scapy.all import *
from scapy.layers.inet import IP, UDP
from scapy.sendrecv import sr1
from Utils import WhoisResolver


# Additonal libraries required (of my own making)
import Utils
from Registry import Registry


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
    def __init__(self, stats, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap, packetsLost):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1
        # By default, take the name of the class as the 'type'. This could be overwritten
        self.type = self.__class__.__name__
        # Add additional instance variables as required
        self.startOfGap = lastReceivedPacketBeforeGap
        self.endOfGap = firstPackedReceivedAfterGap

        self.packetsLost = packetsLost
        # # Calculate packets lost by taking the diff of the sequence nos at the end and start of hole
        # # The '-1' is because it's fences and fenceposts
        # self.packetsLost = abs(
        #     firstPackedReceivedAfterGap.rtpSequenceNo - lastReceivedPacketBeforeGap.rtpSequenceNo) - 1
        # # Guard against the possibility of a -ve packetsLost value
        # if self.packetsLost < 0:
        #     self.packetsLost =0

        # Calculate length of this glitch
        self.glitchLength = firstPackedReceivedAfterGap.timestamp - lastReceivedPacketBeforeGap.timestamp
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

# Stores a running total of events that happened within the last x seconds with y granularity
class MovingTotalEventCounter(object):
    # Stores a running total of events that happened within the last x seconds with y granularity
    # x (the total duration of interest, eg a day, hour, week) and y (the duration of each sampling period eg.
    # for a duration of 12 hours, you might want 12 1hr samples so that you can determine the spread of events
    # over that time
    # Once created, to register a new event, call addEvent()
    # The object does not have a bit in timer. Therefore it must be 'clocked' every second, by calling recalculate()
    def __init__(self, name, totalPeriod_s, samplingPeriod_S):
        self.name = name
        self.samplingPeriod_S = samplingPeriod_S
        # Calculate length of array required for totalPeriod_s for a given samplingPeriod_S
        # eg a 60 second moving total, with 10 second granularity would require an array length = 6
        self.noOfSamplePeriods = totalPeriod_s // samplingPeriod_S
        # Safety check the result
        if self.noOfSamplePeriods < 1:
            self.noOfSamplePeriods = 1
        # Create array to hold historic totals
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
        # Return a tuple containing it's name, the current moving total and also a copy of the array
        return self.name, self.__eventCountMovingTotal, list(self.historicEventsList)

# Define an object to hold data about an individual received rtp packet
class RtpData(object):
    # Constructor method
    def __init__(self, rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData, rxTTL, srcAddr, srcPort):
        self.rtpSequenceNo = rtpSequenceNo
        self.payloadSize = payloadSize
        self.timestamp = timestamp
        self.syncSource = syncSource
        self.isptestHeaderData = isptestHeaderData
        self.rxTTL = rxTTL  # The TTL field from the IP header carrying this Rtp packet
        self.srcAddr = srcAddr
        self.srcPort = srcPort
        # timeDelta will store the timestamp diff between this and the previous packet
        self.timeDelta = 0
        # jitter will store the diff between the timeDelta of this and the prev packet
        self.jitter = 0

# Define a Super Class for all RTP objects (Generators, ReceiveStreams, ReceiveResults..)
# This will contain methods that are useful to all
class RtpCommon(object):
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


# Define a Super Class for RTP Receive streams. This will contain methods that are common to both
# RtpReceiveStream and RtpStreamResults
class RtpReceiveCommon(RtpCommon):
    def __init__(self):
        # Create a 'leaderboard' for the worst 10 glitches
        # In futire this will be a list of Glitch events
        # Currently this list only ever includes 1 item (the current worst glitch)
        self.worstGlitchesList = []
        self.worstGlitchesMutex = threading.Lock()

        self.tracerouteHopsList = []  # A list of tuples containing [IP octet1, IP octet2, IP octet3, Ip octet4]
        self.tracerouteHopsListMutex = threading.Lock()

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
    # If trimEndOfList=True, all the trailing '0.0.0.0' hops will omitted from the returned list
    def getTraceRouteHopsList(self):
        self.tracerouteHopsListMutex.acquire()
        tracerouteHopsList = deepcopy(self.tracerouteHopsList)
        self.tracerouteHopsListMutex.release()
        return tracerouteHopsList

    # Thread-safe method to set the self.tracerouteHopsList[]
    # This completely replaces the existing list with a new supplied list
    def setTraceRouteHopsList(self, newList):
        self.tracerouteHopsListMutex.acquire()
        # Copy the new list into the instance variable list
        self.tracerouteHopsList = deepcopy(newList)
        self.tracerouteHopsListMutex.release()

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
    def getRtpStreamStats(self):
        pass

    @abstractmethod
    def getRTPStreamEventList(self, filterList=None):
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
        tracerouteHopsList = self.getTraceRouteHopsList()

        # Simple local function to determine the current operation mode based on the type of 'this' object instance
        # and return a string
        def getOperationMode():
            if type(self) == RtpStreamResults:
                return "TRANSMIT"
            elif type(self) == RtpReceiveStream:
                return "RECEIVE"
            else:
                return "UNKNOWN"


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
                ", Transmit bitrate: " + str(Utils.bToMb(stats["stream_transmitter_txRate_bps"])) + "bps" + "\r\n"


        labelWidth = 33
        streamPerformance = \
            "Duration of test: ".rjust(labelWidth) + str(Utils.dtstrft(stats["stream_time_elapsed_total"])) + "\r\n" + \
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
                Utils.dtstrft(stats["glitch_mean_time_between_glitches"])) + "\r\n"
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
                                              str(Utils.dtstrft(stats["route_mean_time_between_route_change_events"])) + "\r\n"
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
                                    str(Utils.dtstrft(stats["route_mean_time_between_TTl_change_events"])) + "\r\n"
                routeChangeStats += "Time of last TTL change: ".rjust(labelWidth) + \
                                    str(stats["route_time_of_last_TTL_change_event"].strftime("%d/%m %H:%M:%S")) + "\r\n"
            else:
                routeChangeStats += "No received TTL information available" + "\r\n"

        except Exception as e:
            Utils.Message.addMessage("RtpreceiveCommon.generateReport() route stats " + str(e))


        # Create a traceroute list of hops.
        tracerouteHopsListAsString = "Traceroute:\r\n"
        # tracerouteHopsListAsString += "No. of route changes: ".rjust(labelWidth) + \
        #                               str(stats["route_change_events_total"]) + "\r\n"
        # tracerouteHopsListAsString += "Mean interval between route changes: ".rjust(labelWidth) +\
        #                               str(Utils.dtstrft(stats["route_mean_time_between_route_change_events"])) + "\r\n"
        if len(tracerouteHopsList) > 0 and None not in tracerouteHopsList:
            for hopNo in range(len(tracerouteHopsList)):
                try:
                    hopAddr = str(tracerouteHopsList[hopNo][0]) + "." + \
                        str(tracerouteHopsList[hopNo][1]) + "." + \
                        str(tracerouteHopsList[hopNo][2]) + "." + \
                              str(tracerouteHopsList[hopNo][3])
                    tracerouteHopsListAsString += str(hopNo + 1) + "\t" + hopAddr.ljust(16)
                    # Now query the hop name to see if it's in the whois cache
                    hopName = WhoisResolver.queryWhoisCache(hopAddr)
                    if hopName is not None:
                        tracerouteHopsListAsString += hopName[0]['asn_description']
                    tracerouteHopsListAsString += "\r\n"

                except Exception as e:
                    Utils.Message.addMessage("DBUG: RtpReceiveCommon.generateReport() Create traceroute string: " + str(e))
                    tracerouteHopsListAsString += "--Invalid traceroute data--"
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

    # This utility method witll generate a filename based on the stream parameters.
    # The optional includePath will create a filename with a complete path
    def createFilenameForReportExport(self, includePath=True):
        # Get info about the stream (to be used in the title)
        syncSourceID, srcAddr, srcPort, friendlyName = self.getRTPStreamID()
        fileName = Registry.streamReportFilename + \
                   str(syncSourceID) + "_" + \
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


    # This method will call self.generateReport() and write the output to disk
    # If no filename is supplied, it will use an auto-generated filename based on the stream parameters
    # It will take an optional exportFilterList[] and pass it directly to generateReport()
    # See self.generateReport() for info on how this list can be used to filter the Event types that appear
    # in the exported report
    # Returns True for a successful save, otherwise an error message
    def writeReportToDisk(self, fileName = None, exportFilterList=None):

        #  Generate the report to be written to disk
        report = self.generateReport(eventFilterList=exportFilterList)

        # If filename hasn't been overridden, auto-generate one. Note filename validation should have happened prior
        if fileName is None:
            fileName = self.createFilenameForReportExport()

        try:
            # Open the file for writing
            fh = open(fileName, "w+")
            fh.write(report)
            fh.close()
            Utils.Message.addMessage("Saved: " + str(fileName))
            return True
        except Exception as e:
            Utils.Message.addMessage("ERR: RtpReceiveCommon.writeReportToDisk() " + str(e))
            return str(e)

# Define a class to represent a stream of received rtp packets (and associated stats)
class RtpReceiveStream(RtpReceiveCommon):
    # Constructor method.
    # The RtpReceiveStream object should be created with a unique id no
    # (for instance the rtp sync-source value would be perfect)
    def __init__(self, syncSource, srcAddress, srcPort, rxAddress, rxPort, glitchEventTriggerThreshold,
                 rtpRxStreamsDict, rtpRxStreamsDictMutex, txMessageQueue):
        # Call super constructor
        super().__init__()
        # Create Queue to accept the received packets
        self.rtpStreamQueue = SimpleQueue()
        self.rtpStreamQueueCurrentSize = 0  # Tracks the current size of the receive queue
        self.rtpStreamQueueMaxSize = 0     # Tracks the historic maximum size of the receive queue
        self.packetsAddedToRxQueueCount = 0 # Tracks the packets going into the receive queue

        self.resultsTxQueue = txMessageQueue    # Shared queue for sending results back to the transmitter

        self.rtpRxStreamsDict = rtpRxStreamsDict
        self.rtpRxStreamsDictMutex = rtpRxStreamsDictMutex
        # Create private empty dictionary to hold stats for this RtpReceiveStream object. Accessible via a getter method
        self.__stats = {}
        # Assign to instance variable
        self.__stats["stream_syncSource"] = syncSource
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
        self.__stats["stream_transmitter_txRate_bps"] = 0 # Will be populated by incoming isptest header data

        Utils.Message.addMessage("INFO: RtpReceiveStream:: Creating RtpReceiveStream with syncSource: " + str(self.__stats["stream_syncSource"]))

        # Var to store the traceroute checksum value extracted from the isptestheader data
        self.tracerouteReceivedChecksum = 0
        # Create a mutex lock to be used by the a thread
        # To set the lock use: __accessRtpDataMutex.acquire(), To release use: __accessRtpDataMutex.release()
        self.__accessRtpDataMutex = threading.Lock()
        self.__accessRtpStreamStatsMutex = threading.Lock()
        self.__accessRtpStreamEventListMutex = threading.Lock()
        self.__udpSocketMutex = threading.Lock()

        # Add a name field (which can be set with a friendly name (via a setter method) to identify the stream)
        # This value is pulled from the RtpGenerator object
        self.maxNameLength = RtpGenerator.getMaxFriendlyNameLength()

        # On init, set friendly name to be the same as the sync source ID (padded out with spaces)
        self.__stats["stream_friendly_name"] = \
            str(str(self.__stats["stream_syncSource"])[0:self.maxNameLength]).ljust(self.maxNameLength, " ")

        # Query (and store) the length of the headers sent by RtpGenerator so we know how to decode them
        self.ISPTEST_HEADER_SIZE = RtpGenerator.getIsptestHeaderSize()

        # Create empty list to hold rtp stream data as it is received by the socket
        # self.rtpStreamData = []

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
        self.__rxTTL = 0 # The most recent TTL value from the IP Header (that conveyed the Rtp packet)

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
        # array to store (any number of) moving glitch counters
        self.movingGlitchCounters = []
        # Add some  moving glitch counters to the array:-

        # 10 second duration, 1 second sampling period
        self.movingGlitchCounters.append(MovingTotalEventCounter("historic_glitch_counter_last_10Sec", 10, 1))
        # 1 min duration, 10 second sample period
        self.movingGlitchCounters.append(MovingTotalEventCounter("historic_glitch_counter_last_1Min", 60, 10))
        # 10 min duration, 1 minute sample period
        self.movingGlitchCounters.append(MovingTotalEventCounter("historic_glitch_counter_last_10Min", 600, 60))
        # 1hr duration, 10 minute sample period
        self.movingGlitchCounters.append(MovingTotalEventCounter("historic_glitch_counter_last_1Hr", 3600, 600))
        # 24hr duration, 1hr sample period
        self.movingGlitchCounters.append(MovingTotalEventCounter("historic_glitch_counter_last_24Hr", 86400, 3600))

        # define timedelta object to store an aggregate of of Glitch length
        self.__stats["glitch_length_total_time"] = datetime.timedelta()
        # self.__glitch_most_recent_timestamp = datetime.timedelta()
        self.__stats["glitch_most_recent_timestamp"] = datetime.timedelta()
        self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.timedelta()
        self.__stats["glitch_mean_time_between_glitches"] = datetime.timedelta()
        self.__stats["glitch_mean_glitch_duration"] = datetime.timedelta()
        self.__stats["glitch_max_glitch_duration"] = datetime.timedelta()
        self.__stats["glitch_min_glitch_duration"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastGlitch = datetime.timedelta()
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
        self.sumOfTimeElapsedSinceLastExcessJitterEvents = datetime.timedelta()

        # IPRoutingChange traceroute stats
        self.__stats["route_time_elapsed_since_last_route_change_event"] = datetime.timedelta()
        self.__stats["route_time_of_last_route_change_event"] = datetime.timedelta()
        self.__stats["route_change_events_total"] = 0
        self.__stats["route_mean_time_between_route_change_events"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastRouteChange = datetime.timedelta()

        # Ip routing Rx TTL stats
        self.__stats["route_time_elapsed_since_last_TTL_change_event"] = datetime.timedelta()
        self.__stats["route_time_of_last_TTL_change_event"] = datetime.timedelta()
        self.__stats["route_TTl_change_events_total"] = 0
        self.__stats["route_mean_time_between_TTl_change_events"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastRxTTLChange = datetime.timedelta()


        # Amount of time to elapse before a lossOfStream alarm event is triggered
        self.lossOfStreamAlarmThreshold_s = Registry.lossOfStreamAlarmThreshold_s

        # Amount of time to elapse before a stream is believed completely dead (and automatically
        # destroyed)
        self.streamIsDeadThreshold_s = Registry.streamIsDeadThreshold_s
        # Create a flag to signal when the stream is believed dead (is therefore scheduled to delete itself)
        # self.believedDeadFlag = False

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

        # Finally, add this RtpReceiveStream object to rtpRxStreamsDictMutex
        self.rtpRxStreamsDictMutex.acquire()
        self.rtpRxStreamsDict[self.__stats["stream_syncSource"]] = self
        self.rtpRxStreamsDictMutex.release()


    def killStream(self):
        # Kill the  __queueReceiverThread associated with this receive stream
        self.queueReceiverThreadActiveFlag = False
        self.queueReceiverThread.join()
        Utils.Message.addMessage("DBUG: self.queueReceiverThread.join() complete")

        # Kill the __samplingThread associated with this stream
        self.samplingThreadActiveFlag = False
        # self.samplingThread.join()
        # Utils.Message.addMessage("DBUG: self.samplingThread.join() complete")

        # Finally remove this RtpReceiveStream (itself) from rtpRxStreamsDict
        self.rtpRxStreamsDictMutex.acquire()
        try:
            Utils.Message.addMessage("Removing RtpReceiveStream object " + str(self.__stats["stream_syncSource"]))
            del self.rtpRxStreamsDict[self.__stats["stream_syncSource"]]
        except Exception as e:
            Utils.Message.addMessage("ERR: RtpReceiveStream.killStream() (remove from rtpRxStreamsDict{})" + str(self.__stats["stream_syncSource"]))
        self.rtpRxStreamsDictMutex.release()


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
                # update the self.__tracerouteHopsList[] with the latest received address/hopNo
                self.updateTraceRouteHopsList(hopNo, noOfHops, isptestHeaderData[4:8])
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
                    # And enable transmission of results back to sender
                    # self.resultsTransmitter.transmitActiveFlag = True
                    # Utils.Message.addMessage(isptestHeaderDataFriendlyName)
                    # Now decode the messages contained within the isptest header
                    self.__parseIsptestHeaderData(isptestHeaderData)
                else:
                    # Otherwise, stream is not recognised, so disable transmission of results
                    # Utils.Message.addMessage("DBUG:__RtpReceiveStream.__extractIsptestHeaderData(): Unable to decode stream, setting resultsTransmitter.transmitActiveFlag to False")
                    self.resultsTransmitter.transmitActiveFlag = False
                    pass
        except Exception as e:
            pass
            # Utils.Message.addMessage("DBUG: Decoded header: " + str(e) + str(self.rtpStream[0].isptestHeaderData))

    # This thread updates the 1sec averages, moving counters and also housekeeps
    def __samplingThread(self):
        # Tests the decision making within detectRouteChanges by seeding it with a range of possible traceroute combinations
        def detectRouteChangesTest():
            # testList is an array of tuples
            # [prevHopsList[], hopsList[], prevRxTTL, rxTTL, expected result, description"
            testList = [
                [
                    [],
                    [],
                    None,
                    None,
                    False,
                    "0)Zero length current and prev hops lists, rxTTL and prevRxTTL are None"
                ]
                ,
                [
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 0], [127, 0, 0, 4]],
                    None,
                    None,
                    False,
                    "1) same length current and prev hops lists, current hops list flaps to 0  rxTTL and prevRxTTL are None. Should carry forward"
                ]
                ,
                [
                    [[0, 0, 0, 0]],
                    [[0, 0, 0, 0]],
                    None,
                    None,
                    False,
                    "2) prv and current hoplist are 0.0.0.0"
                ]
                ,
                [
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 7], [127, 0, 0, 4]],
                    None,
                    None,
                    True,
                    "3) prv and current hoplist are same length but different"
                ]
                ,
                [
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3]],
                    4,
                    4,
                    False,
                    "4) prv and current hoplist are different lengths but prevTTL and currentTTL are the same"
                ]
                ,
                [
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3]],
                    4,
                    3,
                    True,
                    "5) prv and current hoplist are different lengths. prevTTL and currentTTL have also changed"
                ]
                ,
                [
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
                    [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3]],
                    None,
                    None,
                    True,
                    "6) prv and current hoplist are different lengths. prevTTL and currentTTL have not been set"
                ]
            ]

            # iterate over test list
            for testNo in range(0, len(testList)):
                test = testList[testNo]
                result = detectRouteChanges(test[0], test[1], test[2], test[3])
                # Test result against expected result
                if result == test[4]:
                    print(str(test[5]) + ", " + str(result) + ", PASS\n")
                else:
                    print(str(test[5]) + ", " + str(result) + ", FAIL\n")

        # Compares prev and current traceroute hops lists to determine whether the route has changed
        # if prevRxTTL and rxTTL values are None, they will be ignored, and the decision about whether a
        # route has changed will be made solely on the length/contents of prevHopsList[], hopsList[]
        def detectRouteChanges(prevHopsList, hopsList, prevRxTTL=None, rxTTL=None):
            ######## Detect route changes using traceroute hops list
            # Compare each of the traceroute hops to the previous value for that hop
            #  If it has changed, signal a route change.
            # Note: some routers don't always respond (so that hop value oscillates between a valid IP address
            # and 0.0.0.0. Even though the rest of the hops have stayed the same, this could look like a
            # route change
            # Therefore we can also look at the IP TTl value to see if that has changed or not.
            # if it hasn't then that suggests it's just an intermediate router not responding rather than a route change

            # Flag to signal the detection of a route change
            hopsListHasChanged = False

            # Shorthand for 0.0.0.0 (i.e no response)
            noResponse = [0, 0, 0, 0]

            # Wait until all the traceroute hops have been populated with values before calculating
            if len(hopsList) > 0 and None not in hopsList:
                # Set initial value for prevHopsList
                if len(prevHopsList) == 0:
                    prevHopsList = hopsList
                    hopsListHasChanged = True

                # # Test to see if the rxTTL value has changed, if so, set hopsListHasChanged flag
                # elif self.__stats["packet_instantaneous_ttl"] != prevRxTTL:
                #     hopsListHasChanged = True

                # Test If length of list has changed then set hopsListHasChanged flag
                # However, if the rxTTL value hasn't also changed*, this suggests an erroneous
                # traceroute hops list possibly caused by a series of routers not responding.
                # * Note if prevRxTTL is 'None' (because the rxTTL isn't able to be decoded)
                # then all we have to go on is the length of the hops list

                # Test If length of list has changed, then test rxTTL for confirmation of the change (if possible)
                elif (len(hopsList) != len(prevHopsList)):
                    # Test to see if rxTTL values contain any further info on which to base a route-change decision
                    if prevRxTTL is not None and rxTTL is not None:
                        # rxTTL does contain a value which we can use to see if the route has changed.
                        # Compare current and prev rxTTL values
                        if prevRxTTL == rxTTL:
                            # This change in the length of hopsList is a red herring because rxTTL did not change.
                            # Therefore ignore.
                            hopsListHasChanged = False
                            Utils.Message.addMessage("DBUG:hopsList len changed but rxTTL didn't. Ignored hopList change " +\
                                "prevLen: " + str(len(prevHopsList)) + ", Len:" + str(len(hopsList)) + ", prevTTL:" + \
                                                     str(prevRxTTL) + ", TTL:" + str(rxTTL))
                        else:
                            # rxTTL has changed, therefore the route must have changed
                            hopsListHasChanged = True
                    else:
                        # It doesn't, so we can only go on the change in length of hopsList[]
                        hopsListHasChanged = True

                # If the lengths of the two lists are the same, test the contents
                else:
                    # Otherwise, if list length is the same compare latest and previous hopsList members
                    for hopNo in range(len(hopsList)):
                        # Iterate over hopsList, comparing the the octets of the individual hops
                        prevHop = prevHopsList[hopNo]
                        currentHop = hopsList[hopNo]

                        # Check to see if either the current or previous values are NOT 0.0.0.0.
                        if prevHop != noResponse and currentHop != noResponse:
                            # These hops contains a value, so see if they have changed
                            if currentHop == prevHop:
                                # The hop value has remained the same, no route change
                                hopsListHasChanged = False
                            else:
                                # The hop value has changed. New route
                                hopsListHasChanged = True

                        # Check to see if either and current values are zero
                        elif prevHop == noResponse and currentHop == noResponse:
                            hopsListHasChanged = False


                        # Now check to see if we previously had a zero hop value but we now have a non zero value
                        # If so, this suggests a route change
                        elif prevHop == noResponse and currentHop != noResponse:
                            hopsListHasChanged = True

                        # Now check to see if we previously had a non-zero value for this hop. If so, make
                        # an educated guess and carry the prev hop value into the current hop value
                        # This means that we might have something to compare this hop value to if it changes
                        # to another non-zero value
                        elif prevHop != noResponse and currentHop == noResponse:
                            # print("carry forward hop " + str(hopNo))
                            hopsList[hopNo] = prevHopsList[hopNo]
                            hopsListHasChanged = False
                        else:
                            # We don't know if the route has changed or not
                            hopsListHasChanged = False

                        # At the end of each hop comparison check the status of hopsListHasChanged
                        # If it has, break out of the loop, otherwise continue onto the next hop
                        if hopsListHasChanged:
                            return True
                        else:
                            # Continue on the the next hop comparison
                            pass
                # At the end of the iteration over all hops, return the latest value of hopsListHasChanged
                return hopsListHasChanged
            else:
                return False

        # Puts the current stream stats and events (the results) in a queue to be transmitted back to the transmitter
        # (if the transmitter is an instance of isptest)
        # Rather than sending the entire events list, we only send the last five events.
        # The correspoinding results receiver is able to ignore any events it has already received
        def addResultsToTxQueue(stats, eventsToBeSent, resultsTxQueue, destAddr, destPort):
            try:
                # Create a dictionary containing the stats and eventList data and pickle it (so it can be sent)
                msg = {"stats": stats, "eventList": eventsToBeSent}
                pickledMessage = pickle.dumps(msg, protocol=2)
                # add the pickled message to the txMessageQueue
                resultsTxQueue.put([pickledMessage, destAddr, destPort])

            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread.addResultsToTxQueue() " + str(e))

        Utils.Message.addMessage("DBUG: __samplingThread started for stream " + str(self.__stats["stream_syncSource"]))
        # Initialise variables to be used within the loop
        loopCounter = 0
        # Initialise variables to hold final calculated values
        meanRxPeriod_1Sec = 0
        meanJitter_1Sec = 0
        meanJitter_10Sec = 0
        rxBps = 0
        meanPacketLengthBytes = 0
        packetsRxdPerSecond = 0
        elapsedTime = datetime.timedelta()
        # Counter used to determine whether a stream has been lost or should be purged (because it has been lost forever)
        secondsWithNoBytesRxdTimer = 0
        # This flag will go high once a stream is believed lost
        lossOfStreamFlag = False

        # This flag will go high when a stream is declared dead
        streamIsDeadFlag = False

        # Stores the previous long-term jitter value.
        jitterLongterm_uS = 0

        # Stores the prev packets received count value. Required for calculating averages over particular periods
        prevPacketsReceivedCount = 0

        # Create circular buffer for rx bytes/sec counter (using 200mS windows, so buffersize of 5
        rxBpsBuffer = deque(maxlen=5)
        prevRxdBytesCount = 0

        # Create a circular buffer for the average receive period
        rxPeriodBuffer = deque(maxlen=5)
        prevRxPeriodCount = 0

        # Create circular buffer for the no of packets per second
        packetsPerSecondBuffer = deque(maxlen=5)
        prevPacketsPeriodCount = 0

        # Create circular buffer for jitter calculations
        # For 1 sec jitter calculation
        jitterPerSecBuffer = deque(maxlen=5)
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

        # Infinite loop
        while self.samplingThreadActiveFlag:
            time.sleep(0.2)
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
            # Snapshot last packet seen timestamp
            self.__stats["packet_last_seen_received_timestamp"] = self.__packet_last_seen_received_timestamp
            # Snapshot packetCounterTransmittedTotal (packets Tx'd according to the transmitter
            self.__stats["packet_counter_transmitted_total"] = self.__packetCounterTransmittedTotal
            # Snapshot streamTransmitterTxRateBps (intended tx rate, according to the transmitter)
            self.__stats["stream_transmitter_txRate_bps"] = self.__streamTransmitterTxRateBps
            # Snapshot latest packet IP TTL value
            self.__stats["packet_instantaneous_ttl"] = self.__rxTTL
            # self.__stats["packet_instantaneous_ttl"] = 10
            # Snapshot latest src address
            self.__stats["stream_srcAddress"] = self.__srcAddress
            # Snapshot latest src port
            self.__stats["stream_srcPort"] = self.__srcPort

            try:
                ########### Calculate how many packets received in the latest 200mS period - required for 'mean' calculations
                packetsReceivedThisPeriod = latestPacketsReceivedCount - prevPacketsReceivedCount
                # Store latest count for next time around the loop
                prevPacketsReceivedCount = latestPacketsReceivedCount

                ########### Calculate packets received per sec
                # Add the latest count of packets received (this period) to the buffer
                packetsPerSecondBuffer.append(packetsReceivedThisPeriod)
                # Sum the buffer to get packets received for the last second
                packetsRxdPerSecond = 0
                for x in packetsPerSecondBuffer:
                    packetsRxdPerSecond += x
                self.__stats["packet_counter_1S"] = packetsRxdPerSecond

                ############ Calculate received bits per second
                # calculate bytes received since the last count
                RxdBytesCountThisPeriod = latestRxdBytesCount - prevRxdBytesCount
                # Snapshot the latest value for next time around the loop
                prevRxdBytesCount = latestRxdBytesCount
                # Append the bytes received this period to the rxBpsBuffer circular buffer
                rxBpsBuffer.append(RxdBytesCountThisPeriod)
                # Now sum the contents of rxBpsBuffer to get the latest rx bps
                rxBytesPerSec = 0
                for bytesPerPeriod in rxBpsBuffer:
                    rxBytesPerSec += bytesPerPeriod
                rxBps = rxBytesPerSec * 8
                self.__stats["packet_data_received_1S_bytes"] = rxBytesPerSec


                ########### Calculate elapsed time
                elapsedTime = datetime.datetime.now() - self.__stats["packet_first_packet_received_timestamp"]
                self.__stats["stream_time_elapsed_total"] = elapsedTime

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
                try:
                    ########### Calculate 10sec jitter mean -- self.__stats["jitter_mean_10S_uS"] = 0
                    # Add the latest 1sec jitter mean to the meanJitter_1Sec circular buffer
                    jitter10SecBuffer.append(meanJitter_1Sec)
                    # Calculate mean value of jitter10SecBuffer contents
                    sumOfjitter10SecBuffer = sum(jitter10SecBuffer)
                    self.__stats["jitter_mean_10S_uS"] = int(sumOfjitter10SecBuffer / 10)
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread calc 10 sec jitter " + str(e))


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
                            meanPeriodBetweenEvents = (sumOfTimePeriodsBetweenEvents + timeElapsedSinceMostRecentEvent)/\
                                                      (totalNoOfEvents + 1)
                            return meanPeriodBetweenEvents
                        else:
                            # The time elapsed since the last event is less than the calculated actual mean.
                            # Therefore we ignore the effect of it, as it will only worsen the mean period
                            return actualPeriodBetweenEvents
                    except Exception as e:
                        Utils.Message.addMessage("RtpReceiveStream.__samplingThread.calculateMeanPeriodBetweenEvents() " +\
                                                 str(e))
                        return None

                try:
                    ########### Update Mean Jitter averages
                    if (self.__stats["jitter_excess_jitter_events_total"] > 0) and (streamIsDeadFlag is False):
                        ########### Now update the self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] timer
                        self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = \
                            datetime.datetime.now() - self.__stats["jitter_time_of_last_excess_jitter_event"]

                        ########### Calculate meanTimeBetweenExcessJitterEvents (jitter Period)
                        self.__stats["jitter_mean_time_between_excess_jitter_events"] = \
                            calculateMeanPeriodBetweenEvents(self.sumOfTimeElapsedSinceLastExcessJitterEvents,
                                                             self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"],
                                                             self.__stats["jitter_excess_jitter_events_total"])
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread Jitter means " + str(e))

                try:
                    ########## Calculate Glitch stats
                    # (But only if there has actually been a glitch in the past to measure against) AND stream is alive
                    if (self.__stats["glitch_counter_total_glitches"] > 0) and (streamIsDeadFlag is False):
                        ########## Calculate time elapsed since last glitch
                        # Calculate new value
                        self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.datetime.now() - self.__stats[
                            "glitch_most_recent_timestamp"]

                        ########## Calculate Glitch mean averages -
                        ########## Calculate mean time between glitches (glitch period)
                        self.__stats["glitch_mean_time_between_glitches"] = \
                            calculateMeanPeriodBetweenEvents(self.sumOfTimeElapsedSinceLastGlitch,
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
                        # Dynamically create new stats keys using the name field of the moving glitch counter
                        self.__stats[name] = movingTotal
                        self.__stats[name + "_events"] = events
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
                    if packetsRxdPerSecond > 0:
                        # Packets have been received so clear the timer
                        secondsWithNoBytesRxdTimer = 0
                        # Clear the flag so another StreamLost Event can be generated
                        lossOfStreamFlag = False
                    else:
                        # No packets received this period so increment the timer
                        secondsWithNoBytesRxdTimer += 1
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread check packets per sec " + str(e))

                try:
                    ######## Check to see if we've lost the stream (but only do this once, via the lossOfStreamFlag)
                    if secondsWithNoBytesRxdTimer >= Registry.lossOfStreamAlarmThreshold_s and not lossOfStreamFlag:
                        # Set flag (this Event can only fire again if the flag is subsequently cleared)
                        lossOfStreamFlag = True
                        # Add event to the list (but only do this once)
                        streamLostEvent = StreamLost(self.__stats)
                        self.__eventList.append(streamLostEvent)
                        # Increment the all_events counter
                        self.__stats["stream_all_events_counter"] += 1
                        Utils.Message.addMessage(streamLostEvent.getSummary(includeStreamSyncSourceID=False)['summary'])
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

                ######## Detect changes in the value of rxTTL
                try:
                    if self.__stats["packet_instantaneous_ttl"] != prevRxTTL:
                        # Change in the value of rxTTL detected
                        oldLen = len(self.getTraceRouteHopsList())
                        # Utils.Message.addMessage("rxTTL change " + str(prevRxTTL) + ">>" + \
                        #                          str(self.__stats["packet_instantaneous_ttl"]))
                        # RxTTL change detected, create a new IPRoutingTTLChange event
                        ipRoutingTTLChange = IPRoutingTTLChange(self.__stats, prevRxTTL, self.__stats["packet_instantaneous_ttl"])
                        # Add the event to the event list
                        self.__eventList.append(ipRoutingTTLChange)
                        # # Increment the all_events counter
                        self.__stats["stream_all_events_counter"] += 1
                        # Update the rx TTL stats
                        self.__stats["route_TTl_change_events_total"] += 1
                        self.__stats["route_time_of_last_TTL_change_event"] = ipRoutingTTLChange.timeCreated

                        # Take snapshot of new time delta and add to the sum of existing values (to calculate mean)
                        self.sumOfTimeElapsedSinceLastRxTTLChange \
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
                    if (self.__stats["route_TTl_change_events_total"] > 0) and (streamIsDeadFlag is False):
                        self.__stats["route_time_elapsed_since_last_TTL_change_event"] = \
                            datetime.datetime.now() - self.__stats["route_time_of_last_TTL_change_event"]

                    ########### Calculate mean time between Rx TTL changes.
                    # Note: Ignore the first route change, because it's not really a 'change', just the initial value
                    if (self.__stats["route_TTl_change_events_total"] > 1) and (streamIsDeadFlag is False):
                        self.__stats["route_mean_time_between_TTl_change_events"] = \
                            calculateMeanPeriodBetweenEvents(self.sumOfTimeElapsedSinceLastRxTTLChange,
                                                             self.__stats[
                                                                 "route_time_elapsed_since_last_TTL_change_event"],
                                                             (self.__stats["route_TTl_change_events_total"] - 1))

                    # Utils.Message.addMessage("ttl  events " + str(self.__stats["route_TTl_change_events_total"]) + \
                    #         ", elapsed " + str(self.__stats["route_time_elapsed_since_last_TTL_change_event"].total_seconds()) +\
                    #                          ", period " + str(Utils.dtstrft(self.__stats["route_mean_time_between_TTl_change_events"])))

                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Calculate Rx TTL Change stats " + str(e))


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
                try:
                    # Get the current hops list
                    hopsList = self.getTraceRouteHopsList()
                    # Calculate checksum of current hops list. Does it match that of self.tracerouteReceivedChecksum?
                    # if it doesn't, that suggests we have an incomplete or jumbled up hopsList
                    # This could happen if the traceroute hops have jjst changed but the transmitter bitrate is slow
                    # leading to a long time for the entire traceroute hops list to be transmitted
                    localTracerouteChecksum = self.createTracerouteChecksum(hopsList)
                    if localTracerouteChecksum == self.tracerouteReceivedChecksum:
                        # If the checksum's match, we can be reasonably confident our hopsList data is valid
                        # Utils.Message.addMessage("Checksums match local " +str(localTracerouteChecksum) + ", rx" +\
                        #               str(self.tracerouteReceivedChecksum))
                        # Attempt to detect a route change
                        if hopsListChangeExpected is False:
                            # Under normal circumstances, take the rxTTL into account to determine route changes
                            # This *should* mean that even if the hopList lengths differ, if the RxTTL values *haven't*
                            # changed, we can ignore the change in prevHopsList/hopsList
                            routeHasChanged = detectRouteChanges(prevHopsList, hopsList,
                                                                prevRxTTL=prevRxTTL,
                                                                 rxTTL=self.__stats["packet_instantaneous_ttl"])
                        else:
                            # Otherwise, if the rxTTL has recently changed, we can only go on the prevHopsList and hopsList
                            # to determine route changes because the hopsList changes will lag behind those of rxTTL
                            routeHasChanged = detectRouteChanges(prevHopsList, hopsList)

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
                            self.sumOfTimeElapsedSinceLastRouteChange \
                                    += self.__stats["route_time_elapsed_since_last_route_change_event"]

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
                    if (self.__stats["route_change_events_total"] > 0) and (streamIsDeadFlag is False):

                        self.__stats["route_time_elapsed_since_last_route_change_event"] = \
                            datetime.datetime.now() - self.__stats["route_time_of_last_route_change_event"]

                    ########### Calculate mean time between route changes.
                    # Note: Ignore the first route change, because it's not really a 'change', just the initial value
                    if (self.__stats["route_change_events_total"] > 1) and (streamIsDeadFlag is False):
                        self.__stats["route_mean_time_between_route_change_events"] = \
                            calculateMeanPeriodBetweenEvents(self.sumOfTimeElapsedSinceLastRouteChange,
                                                             self.__stats["route_time_elapsed_since_last_route_change_event"],
                                                             (self.__stats["route_change_events_total"] - 1))
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Calculate Route Change stats " + str(e))

                ############ Now send results back to transmitter
                try:
                    # Confirm that the stream is being sent from an instance of isptest AND only send if we're
                    # currently receiving bytes
                    if (self.__stats["stream_transmitterVersion"] > 0) and \
                            self.__stats["packet_data_received_1S_bytes"] > 0:

                            # Get the last 5 events for this stream
                            NO_OF_PREV_EVENTS_TO_SEND = 5
                            eventsList = self.getRTPStreamEventList(NO_OF_PREV_EVENTS_TO_SEND)
                            addResultsToTxQueue(self.__stats, eventsList, self.resultsTxQueue,
                                                self.__stats["stream_srcAddress"],
                                                self.__stats["stream_srcPort"])
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveStream. Transmit results for stream " +\
                                             str(self.__stats["stream_syncSource"]) + ", " + str(e))

                ######## 1 second counter end of code ########

            try:
                ######## Check to see if the stream is dead (has been permanently lost). If so, set streamIsDeadFlag
                # but only do this once, so need to check that the flag has not already been set
                if secondsWithNoBytesRxdTimer >= Registry.streamIsDeadThreshold_s and lossOfStreamFlag and\
                        streamIsDeadFlag is False:
                    streamIsDeadFlag = True
                    Utils.Message.addMessage("Stream " + str(self.__stats["stream_syncSource"]) + \
                                             "(" + str(self.__stats["stream_friendly_name"]).rstrip() + \
                                             ") believed dead")
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread detect dead stream " + str(e))

            try:
                ######## If the stream has been declared 'dead' and auto-remove is enabled, kill it
                if streamIsDeadFlag and Registry.autoRemoveDeadRxStreamsEnable:
                    # Generate and save a report
                    # Retrieve the auto-generated filename
                    _filename = self.createFilenameForReportExport()
                    # Write a report to disk
                    self.writeReportToDisk(fileName=_filename)
                    # Kill itself
                    self.killStream()
            except Exception as e:
                Utils.Message.addMessage("ERR:RtpReceiveStream.__samplingThread auto remove stream " + str(e))

            # Increment 1 sec loop counter
            loopCounter += 1
        Utils.Message.addMessage("DBUG: __samplingThread ended for stream " + str(self.__stats["stream_syncSource"]))
    # This thread monitors the packet receive Queue
    # To implement:-
    #   self.__stats["packet_counter_1S"] 'packets per second'
    #                   self.__stats["packet_counter_received_total"]
    #   self.__stats["packet_data_received_1S_bytes"]
    #                   self.__stats["packet_data_received_total_bytes"]
    #   self.__stats["packet_payload_size_mean_1S_bytes"]
    #   self.__stats["packet_instantaneous_receive_period_uS"]
    #
    #   Events
    #   StreamStarted Event self.__stats["packet_first_packet_received_timestamp"]
    #   All events counter self.__stats["stream_all_events_counter"]
    #   self.__stats["packet_last_seen_received_timestamp"]
    #   Loss of Stream alarm
    #
    #   Jitter
    #   self.__stats["jitter_long_term_uS"]
    #   self.__stats["jitter_mean_1S_uS"]
    #   self.__stats["jitter_mean_10S_uS"]
    #   self.__stats["jitter_min_uS"]
    #   self.__stats["jitter_max_uS"]
    #   self.__stats["jitter_max_uS"]
    #   self.__stats["jitter_range_uS"]
    #   self.__stats["jitter_instantaneous"]
    #   self.__stats["jitter_alarm_event_timeout_S"]
    #   self.__stats["jitter_excess_jitter_events_total"]
    #   self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"]
    #   self.__stats["jitter_time_of_last_excess_jitter_event"]
    #   self.__stats["jitter_excess_jitter_events_total"]
    #   self.__stats["jitter_mean_time_between_excess_jitter_events"]


    #   Glitches
    #   self.__stats["glitch_counter_total_glitches"]
    #   self.__stats["glitch_time_elapsed_since_last_glitch"
    #   self.__stats["glitch_most_recent_timestamp"]
    #   self.__stats["glitch_packets_lost_total_count"]
    #   self.__stats["glitch_packets_lost_total_percent"]
    #   Moving glitch counters
    #   self.__stats["glitch_Event_Trigger_Threshold_packets"]
    #   self.__stats["glitch_glitches_ignored_counter"]
    #   self.__stats["glitch_length_total_time"]
    #   self.__stats["glitch_mean_glitch_duration"]
    #   self.__stats["glitch_packets_lost_per_glitch_mean"]
    #   self.__stats["glitch_packets_lost_per_glitch_min"]
    #   self.__stats["glitch_packets_lost_per_glitch_max"]
    #   self.__stats["glitch_min_glitch_duration"]
    #   self.__stats["glitch_max_glitch_duration"]
    #   self.__stats["glitch_worst_glitches_list"]


    #   Stream
    #   self.__stats["stream_time_elapsed_total"]

    #   Other
    #   Housekeep eventsList
    #   Test for dead stream --> Save report to disk --> kill itself

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
                qrtInstance.sumOfTimeElapsedSinceLastGlitch += qrtInstance.__stats["stream_time_elapsed_total"]


            # Take snapshot of new time delta and add to the sum of existing values (to calculate mean)
            qrtInstance.sumOfTimeElapsedSinceLastGlitch += qrtInstance.__stats["glitch_time_elapsed_since_last_glitch"]

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
                    qrtInstance.sumOfTimeElapsedSinceLastExcessJitterEvents += \
                        qrtInstance.__stats["stream_time_elapsed_total"]


                # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean period between events)
                qrtInstance.sumOfTimeElapsedSinceLastExcessJitterEvents += qrtInstance.__stats[
                    "jitter_time_elapsed_since_last_excess_jitter_event"]

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
            # Now wait for items to appear in the queue (with a timeout)
            try:
                # Wait for a packet to arrive in the receive queue
                rtpPacketData = self.rtpStreamQueue.get(timeout=0.2)
                # Take a copy of the latest sequence no.
                latestSeqNo = rtpPacketData.rtpSequenceNo

                # Monitor the size of the queue
                # If the queue size starts creeping up, this suggests the CPU csan't can't keep up with the rate
                # of incoming packets
                self.rtpStreamQueueCurrentSize = self.rtpStreamQueue.qsize()
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


                # Add the packet to the circular packet buffer (for glitch, receive period and jitter analysis)
                rtpPackets.append(rtpPacketData)
                # We need to have received at least two packets before we can detect a glitch
                # and three packets before we can calculate the jitter
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
                        glitch = Glitch(self.__stats, rtpPackets[-2], rtpPackets[-1], packetslost)
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
                            # Increment the all_events counter
                            self.__stats["stream_all_events_counter"] += 1
                            # Post a message
                            Utils.Message.addMessage(glitch.getSummary(includeStreamSyncSourceID=False)['summary'])

                        else:
                            # Glitch is below the threshold. Acknowledge it with a message but don't add an Event
                            # increment the 'ignored' counter so that we know that it happened
                            self.__stats["glitch_glitches_ignored_counter"] += 1
                            # Post a message
                            Utils.Message.addMessage("Stream " + str(self.__stats["stream_syncSource"]) + ", " +\
                                                     str(sequenceNoGap) + " packets lost. (<=" +\
                                                     str(self.__stats["glitch_Event_Trigger_Threshold_packets"]) +\
                                                     ", minor loss " + str(rtpPackets[-2].rtpSequenceNo) + ":" +\
                                                     str(rtpPackets[-1].rtpSequenceNo) + ")" )

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

                    ########### Extract isptest header from most recent packet
                    self.__extractIsptestHeaderData(rtpPackets[-1].isptestHeaderData)

                    ############ Snapshot the 'latest IP TTL' value
                    # Note: This TTL value might be 'None' (i.e not set)
                    self.__rxTTL = rtpPackets[-1].rxTTL
                    ############ Snapshot the 'latest src addr' value
                    self.__srcAddress = rtpPackets[-1].srcAddr
                    ############ Snapshot the 'latest src port' value
                    self.__srcPort = rtpPackets[-1].srcPort


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

        Utils.Message.addMessage("DBUG: Ending __queueReceiverThread for stream " + \
                                 str(self.__stats["stream_syncSource"]))


    # Define setter methods
    def setFriendlyName(self, friendlyName):
        # Thread-safe method to set the friendly name field

        # Truncate supplied name to x characters (truncated to preserve the screen layout) or else pad to 12 chars
        if len(friendlyName) < self.maxNameLength:
            # Too short, so Pad out name to x chars
            friendlyName += (self.maxNameLength - len(friendlyName)) * " "
        else:
            # Too big, so truncate
            friendlyName = friendlyName[:self.maxNameLength]

        self.__accessRtpStreamStatsMutex.acquire()
        self.__stats["stream_friendly_name"]=friendlyName
        self.__accessRtpStreamStatsMutex.release()
        return friendlyName

    # Define getter methods
    def getRTPStreamID(self):
        # Thread-safe method to access stream syncSource, src address, src port and name fields
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats["stream_syncSource"], stats["stream_srcAddress"], \
               stats["stream_srcPort"], self.__stats["stream_friendly_name"]

    # Thread-safe method for accessing all RtpStream stats
    def getRtpStreamStats(self):
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats

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
    def getRTPStreamEventList(self, *args, filterList=None):
        self.__accessRtpStreamEventListMutex.acquire()
        # Create copy of events list
        unfilteredEventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()
        # Now apply a filter (if specified)
        filteredEventList = []
        if filterList is not None:
            # Iterate over unfilteredEventList creating a sublist containing objects (Events) that match the entries
            # specified in filterList[]
            # Note:
            # filter() is a built in method that can iterate over an iterable object (unfilteredEventList)
            # We supply it with a lambda function which takes the current event and checks to see if that type of event is
            # present in filterList[]. If it is, that Event gets added to the filteredEventsList
            filteredEventList = list(filter(lambda event: (type(event) in filterList), unfilteredEventList))
        else:
            # If no filter spcified, all take all the events
            filteredEventList = unfilteredEventList

        if len(args) == 2:
            # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
            try:
                # Slice the list
                return filteredEventList[args[0]:args[1] + 1]
            except Exception as e:
                Utils.Message.addMessage("ERR: RtpStream.getRTPStreamEventList(" + str(args[0]) + ":" +
                                   str(args[1]) + ") requested start and end indexes out of range: " + str(e))
        elif len(args) == 1:
            # If one arg supplied, return the last n events.
            # IF event list not as long as n, return what does exist
            try:
                return filteredEventList[(args[0] * -1):]
            except:
                return filteredEventList
        else:
            return filteredEventList

    # Method to strip off the oldest events from the eventList once the threshold is reached
    # Note **this does not** set mutex locks itself, so should only be called from another method that
    # already has guaranteed exclusive access
    ##### DEPRECATED - __houseKeepEventList is now a deque so housekeeps itself
    # def __houseKeepEventList(self):
    #     # Check size of self.__eventList[]
    #     noOfMessagesToPurge = len(self.__eventList) - self.historicEventsLimit
    #     if noOfMessagesToPurge > 0:
    #         # Remove first x events
    #         # oldSize = len(self.__eventList)
    #         del self.__eventList[:noOfMessagesToPurge]
    #         # newSize = len(self.__eventList)
    #         # Utils.Message.addMessage("DBUG: __houseKeepEventList() "+str(noOfMessagesToPurge)+
    #         #                    " events removed"+str(oldSize)+">>"+str(newSize))

    # # This method will generate a formatted report containing the performance of the Rtp Stream
    # def generateReport(self, eventFilterList = None):
    #     # It will include:-
    #     # Source Ip, Dest IP, Port, Sync Source ID, Friendly Name
    #     # Duration of test, % Loss, Glitch period, bitrate, packet size
    #     # % Loss
    #     # Get a dump of the current stats
    #     stats = self.getRtpStreamStats()
    #     # Get a dump of the current events (taking into account whether display filtering has been applied)
    #     # Retrieve the desired event types from the RTP Stream object
    #     eventsList = self.getRTPStreamEventList(filterList = eventFilterList)
    #     separator = ("-" * 63) + "\r"
    #     title = "Report for stream " + str(stats["stream_syncSource"]) + ", (" + str(stats["stream_friendly_name"]).rstrip() + ")" + "\r"
    #     streamIPDetails  = \
    #         str(stats["stream_srcAddress"]) + ":" + str(stats["stream_srcPort"])+" ---> " + \
    #             str(stats["stream_rxAddress"]) + ":" + str(stats["stream_rxPort"]) + "\r" +\
    #             "Packet size: " + str(stats["packet_payload_size_mean_1S_bytes"]) + " bytes" +\
    #             ", Bitrate: " + str(bToMb(8 * stats["packet_data_received_1S_bytes"])) + "bps" + "\r"
    #
    #     labelWidth = 33
    #     streamPerformance = \
    #         "Duration of test: ".rjust(labelWidth) + str(dtstrft(stats["stream_time_elapsed_total"])) + "\r" +\
    #         "Packet loss: ".rjust(labelWidth) + str(math.ceil(stats["glitch_packets_lost_total_percent"])) + "%" + "\r" +\
    #         "Total packets lost: ".rjust(labelWidth) + str(int(stats["glitch_packets_lost_total_count"])) + "\r" +\
    #         "Maximum glitch dur: ".rjust(labelWidth) + str(dtstrft(stats["glitch_max_glitch_duration"])) + "\r" +\
    #         "Mean glitch dur: ".rjust(labelWidth) + str(dtstrft(stats["glitch_mean_glitch_duration"])) + "\r" +\
    #         "Mean interval between glitches: ".rjust(labelWidth) + str(dtstrft(stats["glitch_mean_time_between_glitches"])) + "\r"
    #
    #     # Create list of glitches (as a string)
    #     eventsListAsAString = "Events:\r"
    #     # Display the events list in reverse order (most recent first)
    #     for event in range(len(eventsList)-1, -1, -1):
    #
    #         # Retrieve each Event summary, ommiting the syncSourceID and the friendlyName (for display purposes)
    #         eventDetails = eventsList[event].getSummary(includeStreamSyncSourceID=False, includeFriendlyName=False)
    #         # Creata a formatted string for the event
    #         eventsListAsAString += (str(eventDetails['timeCreated'].strftime("%d/%m %H:%M:%S")) +\
    #                                 ", " + str(eventDetails['summary']) + "\r")
    #
    #     outputString = title + separator + streamIPDetails + separator + streamPerformance + separator +\
    #         eventsListAsAString
    #
    #     # Return a string containing the output
    #     return outputString




    # Define setter methods
    def addData(self, rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData, rxTTl, srcAddress, srcPort):
        # Create a new rtp data object to hold the rtp packet data and add it to the receive queue
        # newData = RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData)
        try:
            self.rtpStreamQueue.put(RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData, \
                                            rxTTl, srcAddress, srcPort))
            # Increment the counter. Packets out should equal packets in
            self.packetsAddedToRxQueueCount += 1
        except Exception as e:
            Utils.Message.addMessage("RtpReceiveStream.addData() " + str(e))


# # An object that will transmit stream results back from the receiving end to to the sender
# # It is designed as a counterpart to class ResultsReceiver
# # Note. This will reply from the same UDP binding as used in main() socket.recvfrom
# class ResultsTransmitter(object):
#     def __init__(self, rtpStream):
#         self.parentRtpRxStream = rtpStream
#         self.udpSocket = 0
#         self.destAddr = 0
#         self.destPort = 0
#         self.syncSource = 0
#         self.friendlyName = ""
#         self.threadActiveFlag = True # Used to control the lifespan of __resultsTransmitterThread
#         self.transmitActiveFlag = False  # Used to enable/disable transmit of UDP packets
#                                     # For RTP stream sources not identified as being from isptest (eg an NTT), this will
#                                     # inhibit needless reverse traffic
#                                     # At start-up, inhibit tx traffic by default.
#                                     # The corresponding RtpReceiveStream.__calculateThread() will enable it,
#                                     # if approproate
#
#         self.sendtoErrorCounter = 0 # Count's the no. of socket.sendto() errors
#         self.sendtoErrorCounterThreshold = 10 # No of consecutive socket.sendto() errors that the thread will
#                                             # tolerate before it gives up
#
#         # Get the destination addr and src port from the supplied rtpStream object
#         self.syncSource, self.destAddr, self.destPort, self.friendlyName =\
#             self.parentRtpRxStream.getRTPStreamID()
#
#         # Start the transmitter thread
#         self.resultsTransmitterThread = threading.Thread(target=self.__resultsTransmitterThread, args=())
#         self.resultsTransmitterThread.daemon = True
#         self.resultsTransmitterThread.setName(str(self.syncSource) + ":ResultsTransmitter")
#         self.resultsTransmitterThread.start()
#
#     def kill(self):
#         # Forces the self.transmitterActiveFlag to False which will cause the __resultsTransmitterThread
#         # to end
#         self.threadActiveFlag = False
#
#
#     def __resultsTransmitterThread(self):
#         Utils.Message.addMessage("INFO: __resultsTransmitterThread started for stream: "+ str(self.syncSource))
#
#         # oldSocket = self.parentRtpRxStream.getSocket()
#         # Utils.Message.addMessage("__resultsTransmitterThread. Initial socket" + str(id(oldSocket)))
#         selectTimeout = 1 # timeout for the select() function used to poll the OS for the availability of the socket
#         while self.threadActiveFlag:
#             self.udpSocket = self.parentRtpRxStream.getSocket()
#             # if oldSocket is not self.udpSocket:
#             #     Utils.Message.addMessage("__resultsTransmitterThread. Socket changed to " + str(id(self.udpSocket)))
#             #     oldSocket = self.udpSocket
#
#             # Check that the the socket is a valid socket.socket object
#             if type(self.udpSocket) == socket.socket:
#                 # Confirm that transmission is active
#                 if self.transmitActiveFlag == True:
#                     # Utils.Message.addMessage("__resultsTransmitterThread. Current TX socket " + str(id(self.udpSocket)))
#                     # Get the destination addr and src port from the supplied rtpStream object
#                     self.syncSource, self.destAddr, self.destPort, self.friendlyName = \
#                         self.parentRtpRxStream.getRTPStreamID()
#
#                     try:
#                         # We have a valid socket binding we can use, so transmit the data
#                         # Use pickle to serialise the data we want to send
#                         stats = self.parentRtpRxStream.getRtpStreamStats()
#
#                         # Get the last 5 events for this stream
#                         NO_OF_PREV_EVENTS_TO_SEND = 5
#                         eventsList = self.parentRtpRxStream.getRTPStreamEventList(NO_OF_PREV_EVENTS_TO_SEND)
#
#                         # Create a dictionary containing the stats and eventList data and pickle it (so it can be sent)
#
#                         msg = {"stats": stats, "eventList": eventsList}
#                         pickledMessage = pickle.dumps(msg,protocol=2)
#
#                         # add the pickled message to the txMessageQueue
#                         # self.parentRtpRxStream.resultsTxQueue.put([pickledMessage, self.destAddr, self.destPort])
#
#                         # Set max safe UDP tx size to 576 (based on this:-
#                         # https://www.corvil.com/kb/what-is-the-largest-safe-udp-packet-size-on-the-internet
#                         MAX_UDP_TX_LENGTH = 512
#                         # Split the message up
#                         fragmentedMessage = Utils.fragmentString(pickledMessage, MAX_UDP_TX_LENGTH)
#                         if fragmentedMessage is not None and len(fragmentedMessage) > 0:
#
#                             # iterate over fragments and send
#                             for fragment in fragmentedMessage:
#                                 # Pickle and send each fragment one at a time
#                                 txMessage = pickle.dumps(fragment,protocol=2)
#                                 # Wait for socket to become available
#                                 # r, w, x = select.select([self.udpSocket], [], [], selectTimeout)
#                                 # select() will return a list w containing the writable sockets
#                                 # if self.udpSocket is present in that list, we can safely write to it
#                                 # Utils.Message.addMessage("DBUG: tx'd: (" +str(len(txMessage)) + ") "+ txMessage)
#                                 # if self.udpSocket in w:
#                                 # self.udpSocket.sendto(txMessage, (self.destAddr, self.destPort))
#                                 # clear the socket.sendto() error counter
#                                 self.sendtoErrorCounter = 0
#                                 # else:
#                                 #     # tx socket is not available within the timeout period
#                                 #     # Increment the counter
#                                 #     self.sendtoErrorCounter += 1
#                                 #     Utils.Message.addMessage("__resultsTransmitterThread tx error count " + \
#                                 #                              str(self.sendtoErrorCounter) + ", " +\
#                                 #                              str(self.udpSocket))
#                                 #     # Abort the transmission of all fragments
#                                 #     break
#                         else:
#                             # Utils.Message.addMessage("DBUG:__resultsTransmitterThread  - fragmentedMessage[] is None or empty")
#                             pass
#
#                     except Exception as e:
#                         # Increment the error counter
#                         self.sendtoErrorCounter += 1
#                         Utils.Message.addMessage("ERR:__resultsTransmitterThread sendto() socket id:" + str(id(self.udpSocket)) +", " + str(e))
#                         # Test to see if we've exceeeded the no of consequtive tolerable socket errors
#                         if self.sendtoErrorCounter >= self.sendtoErrorCounterThreshold:
#                             Utils.Message.addMessage("__resultsTransmitterThread. socket.sendto() error threshold exceeded (" +
#                                                      str(self.sendtoErrorCounterThreshold) +\
#                                                         "). Killing object for stream: " + str(self.syncSource))
#                             # Now kill the object itself
#                             self.kill()
#
#                 else:
#                     # Results transmission inhibited
#                     pass
#             else:
#                 Utils.Message.addMessage("ERR: __resultsTransmitterThread - invalid UDP socket?")
#             time.sleep(0.5)

# Define a class to encompass the results sent back from the receiving to the transmitting side (via the
# ResultsTransmitter and ResultsReceiver objects)
# It does't perform any calculations itself (unlike RtpReceiveStream) but it does have similar getter methods for results,
# which should allow displayThread to treat this like an RtpStream object without any additional code alteration
class RtpStreamResults(RtpReceiveCommon):
    def __init__(self, syncSourceID, rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex):

        super().__init__()
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
        # NOTE: It won't check for duplicate entries. It will blindly just append to what's already there
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
            Utils.Message.addMessage(event.getSummary()["summary"])

    # This method will remove this stream object from the rtpTxStreamResultsDict dictionary
    def killStream(self):
        self.rtpTxStreamResultsDictMutex.acquire()
        Utils.Message.addMessage("Deleting RtpStreamResults object for stream: " + str(self.syncSourceID))
        del self.rtpTxStreamResultsDict[self.syncSourceID]
        self.rtpTxStreamResultsDictMutex.release()

    # def setFriendlyName(self, friendlyName):
    #     # Thread-safe method to set the friendly name field
    #
    #     # Truncate supplied name to x characters (truncated to preserve the screen layout) or else pad to 12 chars
    #     if len(friendlyName) < self.maxNameLength:
    #         # Too short, so Pad out name to x chars
    #         friendlyName += (self.maxNameLength - len(friendlyName)) * " "
    #     else:
    #         # Too big, so truncate
    #         friendlyName = friendlyName[:self.maxNameLength]
    #
    #     self.__accessRtpStreamStatsMutex.acquire()
    #     self.__stats["stream_friendly_name"]=friendlyName
    #     self.__accessRtpStreamStatsMutex.release()
    #     return friendlyName

    # Define getter methods
    def getRTPStreamID(self):
        # Thread-safe method to access stream syncSource, src address, src port and name fields
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats["stream_syncSource"], stats["stream_srcAddress"], \
               stats["stream_srcPort"], self.__stats["stream_friendly_name"]

    # Thread-safe method for accessing all RtpStream stats
    def getRtpStreamStats(self):
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats

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
    def getRTPStreamEventList(self, *args, filterList = None):
        self.__accessRtpStreamEventListMutex.acquire()
        # Create copy of events list
        unfilteredEventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()
        # Now apply a filter (if specified)
        filteredEventList = []
        if filterList is not None:
            # Iterate over unfilteredEventList creating a sublist containing objects (Events) that match the entries
            # specified in filterList[]
            # Note:
            # filter() is a built in method that can iterate over an iterable object (unfilteredEventList)
            # We supply it with a lambda function which takes the current event and checks to see if that type of event is
            # present in filterList[]. If it is, that Event gets added to the filteredEventsList
            filteredEventList = list(filter(lambda event: (type(event) in filterList), unfilteredEventList))
        else:
            # If no filter spcified, all take all the events
            filteredEventList = unfilteredEventList

        if len(args) == 2:
            # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
            try:
                # Slice the list
                return filteredEventList[args[0]:args[1] + 1]
            except Exception as e:
                Utils.Message.addMessage("ERR: RtpStream.getRTPStreamEventList(" + str(args[0]) + ":" +
                                   str(args[1]) + ") requested start and end indexes out of range: " + str(e))
        elif len(args) == 1:
            # If one arg supplied, return the last n events.
            # IF event list not as long as n, return what does exist
            try:
                return filteredEventList[(args[0] * -1):]
            except:
                return filteredEventList
        else:
            return filteredEventList

    # Method to strip off the oldest events from the eventList once the threshold is reached
    # Unlike the similar method in RtpStream, this does actually set/release mutex locks itself
    ## DEPRECATED - __eventList[] is a deque so automaticall triums itself
    # def houseKeepEventList(self):
    #     self.__accessRtpStreamEventListMutex.acquire()
    #     # Check size of self.__eventList[] and therefore no of events to purge
    #     currentNoOfEventsInMemory = len(self.__eventList)
    #     noOfMessagesToPurge = currentNoOfEventsInMemory - self.historicEventsLimit
    #     if noOfMessagesToPurge > 0:
    #         # Remove first x events
    #         del self.__eventList[:noOfMessagesToPurge]
    #         # Utils.Message.addMessage("Purging " + str(noOfMessagesToPurge) + " events from events list for stream " +\
    #         #                     str(self.syncSourceID) + " Old length: " + str(currentNoOfEventsInMemory) +\
    #         #                          ", New length: " + str(len(self.__eventList)))
    #     self.__accessRtpStreamEventListMutex.release()


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
    rtpParams = 0b01000000
    rtpPayloadType = 0b00000000

    @classmethod
    def getMaxFriendlyNameLength(cls):
        return cls.MAX_FRIENDLY_NAME_LENGTH

    @classmethod
    def getIsptestHeaderSize(cls):
        return cls.ISPTEST_HEADER_SIZE

    @classmethod
    def getUniqueIDforISPTESTstreams(cls):
        return cls.UNIQUE_ID_FOR_ISPTEST_STREAMS

    def __init__(self, UDP_TX_IP, UDP_TX_PORT, txRate, payloadLength, syncSourceID, timeToLive, \
                 rtpTxStreamsDict, rtpTxStreamsDictMutex,\
                 rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex, uiInstance = None, **kwargs):
        # The last arguments (**kwargs) are optional. it allows you to specify a source port or friendly name on creation
        # kwargs are "friendlyName" and "UDP_SRC_PORT"

        # Assign instance variables
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
        self.tracerouteHopsList = []  # A list of tuples containing [IP octet1, IP octet2, IP octet3, Ipopctet4]
        self.tracerouteHopsListMutex = threading.Lock()
        self.tracerouteCarouselIndexNo = 0  # Keeps track of which traceroute hop value is currently being transmitted
                                            # in the isptest header (in RtpGenerator.generateIsptestHeader()

        self.tracerouteChecksum = 0# Calculated by XORing an entire hops list, once it's been successfully validated
        self.isptestHeaderMessageIndex = 0 # Keeps track of which type of message we are sending in the header
        self.noOfMessageTypes = 6 # The current message types are:
                                    # 0 Traceroute
                                    # 1 private LAN Address of the local interface used for transmitting
                                    # 2 The 'public' destination address
                                    # 3 The current version of isptest
                                    # 4 The specified TX rate
                                    # 5 The transmitted packet count

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

        self.rtpTxStreamsDict = rtpTxStreamsDict
        self.rtpTxStreamsDictMutex = rtpTxStreamsDictMutex
        self.rtpTxStreamResultsDict = rtpTxStreamResultsDict
        self.rtpTxStreamResultsDictMutex = rtpTxStreamResultsDictMutex

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

        # Create a FIFO queue to hold control messages/instructions. These will be picked up in the __samplingThread
        # This messages can be used to modify the RtpGenrator parameters as an alternative to calling the
        # various setxx() methods directly
        # The ResultsReceiver.__resultsReceiverThread() is able to receive control messages from the corresponding
        # RECEIVER instance, and will put the received control messages onto the controlMessageQueue
        # self.addControlMessage() will put a message onto the queue
        # self.parseControlMessage() will decode a message

        # Each message is a list of at least length = 2
        # The first element of the list is a number which identifies the sync source ID
        # The second element is a string that identifies the type of message
        # current messages are:
        #   [xxxxx,"txbps_inc"] Increase the tx bitrate
        #   [xxxx,"txbps_dec"] Decrease the tx bitrate
        self.__controlMessageQueue = SimpleQueue()


        ######## Actual code starts here

        # Start the traffic generator thread
        self.rtpGeneratorThread = threading.Thread(target=self.__rtpGeneratorThread, args=())
        self.rtpGeneratorThread.daemon = False
        self.rtpGeneratorThread.setName(str(self.syncSourceIdentifier) + ":RtpGenerator")
        self.rtpGeneratorThread.start()

        # Query the OS to determine which traceroute routine to run
        os = Utils.getOperatingSystem()
        # os = "Windows"
        if (os == "Windows"):
            # Start the Windows (Scapy-based) traceroute thread
            # self.tracerouteThread = threading.Thread(target=self.__tracerouteThreadScapyWindows, args=())
            self.tracerouteThread = threading.Thread(target=self.__tracerouteThreadScapyWindowsRewrite, args=())
            self.tracerouteThread.daemon = False
            self.tracerouteThread.setName(str(self.syncSourceIdentifier) + ":tracerouteScapyRewrite (" + str(os) + ")")

        else:
            # Start the Linux/OSX traceroute thread
            self.tracerouteThread = threading.Thread(target=self.__tracerouteLinuxOSXThread, args=())
            self.tracerouteThread.daemon = False
            self.tracerouteThread.setName(str(self.syncSourceIdentifier) + ":tracerouteLinuxOSX ("+ str(os) + ")")
        # Test the Registry var. If traceroute is enabled, start the thread
        if Registry.rtpGeneratorEnableTraceroute:
            self.tracerouteThread.start()

        # create a stream results receiver object for this tx stream
        self.rtpStreamResultsReceiver = ResultsReceiver(self)

        # Add the object to the specified dictionary with using rtpStreamID as the key
        self.rtpTxStreamsDictMutex.acquire()
        self.rtpTxStreamsDict[self.syncSourceIdentifier] = self
        self.rtpTxStreamsDictMutex.release()

        # start the 1 second sampling thread
        self.samplingThread = threading.Thread(target=self.__samplingThread, args=())
        self.samplingThread.daemon = False
        self.samplingThread.setName(str(self.syncSourceIdentifier) + ":samplingThread")
        self.samplingThread.start()


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
                'Tx period': self.txPeriod
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
        # [byte1] Message type (3: Transmitter isptest version no.
        #         # [byte2] major version no
        #         # [byte3] minor version no
        #         # [byte4][byte5][byte6][byte7] all 0/not used
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

        header = b""  # Specify byte string
        # Initialise messageData to zero
        messageData = [0,0,0,0,0,0,0]

        try:
            # Note: a short is 16 bits - max value 65535
            uniqueValue = RtpGenerator.UNIQUE_ID_FOR_ISPTEST_STREAMS & 0xFFFF
            # Test what type of message we are scheduled to send
            if self.isptestHeaderMessageIndex == 0:
                # This is traceroute message - Get copy of tracerouteHopsList[]
                tracerouteHopsList = self.getTraceRouteHopsList()
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
                # This is 'isptest version' message
                try:
                    # Split the version no into a major and minor part
                    version = str(Registry.version).split('.')
                    messageData = [3 & 0xFF,  # Message type 3: Destination addr
                                   int(version[0]) & 0xFF,  # Major version no
                                   int(version[1]) & 0xFF,  # Minor version no
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
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
            Utils.Message.addMessage("ERR: RtpGenerator.generatePayload(). Header err: " + str(e))

        # Return the isptestheader data (as a bytestring)
        return header

    def setSyncSourceIdentifier(self,value):
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
    def setTxRate(self, newTxRate_bps, autoIncrement=False, autoDecrement=False):

        txRateChange_bps = 0
        # calculate step change value (up or down) based on current txRate
        # If 100kbps or less, change in 10kbps steps
        if self.txRate <= 102400:
            txRateChange_bps = 10240
        # Else if tx rate between 100kbps and 1Mbps, change in 256kbps steps
        elif self.txRate <= 1048576:
            txRateChange_bps = 262144
        # Otherwise change in 512Mbps steps
        else:
            txRateChange_bps = 524288

        # Check to see if autoIncrement or autoDecrement have been set. If so, override newTxRate_bps value
        if autoIncrement:
            # Auto increment is set
            newTxRate_bps = self.txRate + txRateChange_bps
        elif autoDecrement:
            # Auto decrement is set
            newTxRate_bps = self.txRate - txRateChange_bps


        # Confirm that the new TX rate isn't below the minimum permitted
        if newTxRate_bps < Registry.minimumPermittedTXRate_bps:
            newTxRate_bps = Registry.minimumPermittedTXRate_bps

        Utils.Message.addMessage("Setting new tx rate " + str(Utils.bToMb(newTxRate_bps)) + \
                                 "bps, for stream " + str(self.syncSourceIdentifier))

        # Update instance variable
        self.txRate = newTxRate_bps
        # Calculate then set the new txPeriod for a given newTxRate_bps
        self.txPeriod = self.calculateTxPeriod(newTxRate_bps)


    def setPayloadLength(self, payloadLength_bytes):
        # Modifies the payload length of this RTP TX stream
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

    def setTimeToLive(self, newTimeToLive):
        # Modifies the existing time to live value
        # Setting this to a -ve value will mean the tx stream object last for ever
        self.timeToLive = newTimeToLive

    def killStream(self):
        # Kills the stream by setting the time to live to zero. This will cause the main thread to exit
        self.setTimeToLive(0)
        # Wait for __rtpGeneratorThread to end
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __rtpGeneratorThread to end")
        self.rtpGeneratorThread.join()
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __rtpGeneratorThread has ended")
        # Check to see if __tracerouteThread exists (it may have been intentionally disabled)
        if self.tracerouteThread.is_alive():
            # Wait for __tracerouteThread to end
            Utils.Message.addMessage("DBUG: RtpGenerator.killStream()  Waiting for __tracerouteThread has ended")
            self.tracerouteThread.join()
            Utils.Message.addMessage("DBUG: RtpGenerator.killStream()  __tracerouteThread has ended")
        # Wait for __samplingThread to end
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __samplingThread to end")
        self.samplingThread.join()
        Utils.Message.addMessage("DBUG: RtpGenerator.killStream() Waiting for __samplingThread has ended")

        # Now kill corresponding RtpResultsReceiver object (should be a blocking call)
        self.rtpStreamResultsReceiver.kill()
        # Finally, remove this RtpGenerator object from rtpTxStreamsDict
        self.rtpTxStreamsDictMutex.acquire()
        Utils.Message.addMessage("INFO: Deleting RtpGenerator entry in rtpTxStreamsDict for stream: " + str(self.syncSourceIdentifier))
        del self.rtpTxStreamsDict[self.syncSourceIdentifier]
        self.rtpTxStreamsDictMutex.release()

        # Now kill UDP socket
        self.udpTxSocket.close()

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

    def simulatePacketLoss(self, packetsToSkip):
        # Used to simulate packet loss by skipping x packets (whilst incrementing the seq no internally)
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
    def parseControlMessage(self, controlMessage):
        Utils.Message.addMessage("DBUG:Control Message " + str(self.syncSourceIdentifier) + ":" + str(controlMessage))
        # parse the incoming message
        try:
            # Get message type
            messageSyncSourceID = controlMessage[0]
            messageType = controlMessage[1]
            # Confirm that this is a message destined for this RtpGenerator Object
            if messageSyncSourceID == self.syncSourceIdentifier:
                if messageType == "txbps_inc":
                    self.setTxRate(0, autoIncrement=True)
                elif messageType == "txbps_dec":
                    self.setTxRate(0, autoDecrement=True)

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
                if (self.txActualTxRate_bps > self.txRate) and self.burstTimer == 0:
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
                # Decrement timeToLive seconds counter but only if current value is +ve
                # A -ve value is used to denote 'live for ever'
                if self.timeToLive > 0:
                    self.timeToLive -= 1

                # Decrement the burst timer, but only if current value is +ve
                if self.burstTimer >0:
                    self.burstTimer -= 1
                    # If we've only got 1 second left, recalculate txPeriod to revert the stream to the original tx rate
                    if self.burstTimer < 2:
                        self.txPeriod = self.calculateTxPeriod(self.txRate)
                        Utils.Message.addMessage("Burst mode ending for stream " + str(self.syncSourceIdentifier) + \
                                      ". Reverting to " + str(Utils.bToMb(self.txRate)) + "bps")



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
                    # Send the data
                    sentBytes = rtpGeneratorInstance.udpTxSocket.sendto(rtpGeneratorInstance.udpTxData,
                                                            (rtpGeneratorInstance.UDP_TX_IP,
                                                             rtpGeneratorInstance.UDP_TX_PORT))
                    # Confirm that we appear to have sent the correct no. of bytes
                    if sentBytes == len(rtpGeneratorInstance.udpTxData):
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

                # sleep
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

                # Deliberately modify the traceroute hops list every 50 packets
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
            # Now check to see if there is a corresponding RtpStreamResults object for this Tx stream
            self.rtpTxStreamResultsDictMutex.acquire()
            if self.syncSourceIdentifier in self.rtpTxStreamResultsDict:
                try:
                    # Get a handle on the RtpStreamResults object
                    rtpTxStreamResults = self.rtpTxStreamResultsDict[self.syncSourceIdentifier]
                    # invoke the writeReportToDisk() method to dump a report to disk automatically
                    # Retrieve the auto-generated filename
                    _filename = rtpTxStreamResults.createFilenameForReportExport()
                    Utils.Message.addMessage("Stream " + str(self.syncSourceIdentifier) + " expiring")
                    # Write a report to disk
                    rtpTxStreamResults.writeReportToDisk(fileName=_filename)
                except Exception as e:
                    Utils.Message.addMessage(
                        "ERR: RtpGenerator.killStream() rtpTxStreamResults.generateReport(): " + str(e))
            self.rtpTxStreamResultsDictMutex.release()
            Utils.Message.addMessage("DBUG: __newImprovedRtpGeneratorThread ending for stream " + str(self.syncSourceIdentifier))

        except Exception as e:
            Utils.Message.addMessage("ERR:__newImprovedRtpGeneratorThread " + str(e))

    # Thread-safe method to return a list of the traceroute hops
    # If trimEndOfList=True, all the trailing '0.0.0.0' hops will omitted from the returned list
    def getTraceRouteHopsList(self, trimEndOfList=True):
        self.tracerouteHopsListMutex.acquire()
        tracerouteHopsList = deepcopy(self.tracerouteHopsList)
        self.tracerouteHopsListMutex.release()
        if trimEndOfList and len(tracerouteHopsList) > 1:
            # Clean up the tail end of the hops list which is liable to be full of 0.0.0.0's if
            # a series of routers didn't respond. This isn't very helpful, so get rid of them
            # Iterate over the list starting at the last element. matching [0,0,0,0]
            # If matched, delete that element
            elementsToTrim = 0
            for x in range(len(tracerouteHopsList) - 1, 0, -1):
                if tracerouteHopsList[x] == [0,0,0,0]:
                    elementsToTrim +=1
                else:
                    # Otherwise a non-0.0.0.0 address present, so break out of the loop
                    break
            # Now actually trim the redundant trailing 0.0.0.0's from the tracerouteHopsList list
            if elementsToTrim > 0:
                try:
                    # Slice the unwanted elements from the top of the list (keeping only the bottom of the list)
                    tracerouteHopsList = tracerouteHopsList[:(len(tracerouteHopsList) - elementsToTrim)]
                except Exception as e:
                    Utils.Message.addMessage("ERR:RtpReceiveCommon.getTracerouteHopsList() trim trailing 0.0.0.0s " + str(e))
            return tracerouteHopsList
        else:
            # Otherwise, return the list as-is
            return tracerouteHopsList

    def __tracerouteLinuxOSXThread(self):
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
        class TracerouteLinuxOSXThreadError(Exception):
            pass

        # Creates and returns two seperate sockets, one for tx (udp) and one for rx (icmp)
        # Returns a UDPTxSocketSetupError or ICMPRxSocketSetupError Exception
        def createSockets(ipAddrofInterface):
            # Set up udp transmit socket
            try:
                # Create UDP socket
                udpTx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udpTx.settimeout(timeOut)
            except Exception as createSocketsError:
                raise UDPTxSocketSetupError(str(createSocketsError))
                # print("udpTxSocket socket setup error " + str(e))
                # exit()

            # Set up icmp receiving socket to receive ICMP
            try:
                # Create raw socket
                icmpRx = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                icmpRx.settimeout(timeOut)
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

        # This function decodes the icmp Header and icmp payload (which should contain a copy of the header
        # that caused the icmp reply to be generated).
        # It expects an ICMPHeader and IPHeader object as arguments
        # If the function can match the srcAddress, srcTtl, icmpType and icmpCode to that of the original sending
        # message we can infer that this ICMP message is for us.
        # Returns True if all the  optional parameters were matched, False if not, or None of there was an error
        def icmpReplyMatcher(__icmpHeader, __ipHeaderOfSrc, srcAddress=None, destAddress=None, \
                             srcTtl=None, icmpType=None, icmpCode=None):

            # Test the fields within __icmpHeader and __ipHeaderOfSrc to see if they're what we're looking for
            try:
                if ((srcAddress == __ipHeaderOfSrc.s_addr) or (srcAddress is None)) and \
                        ((destAddress == __ipHeaderOfSrc.d_addr) or (destAddress is None)) and \
                        ((srcTtl == __ipHeaderOfSrc.ttl) or (srcTtl is None)) and \
                          ((icmpType == __icmpHeader.type) or (icmpType is None)) and \
                        ((icmpCode == __icmpHeader.code) or (icmpCode is None)):
                    return True
                else:
                    return False
            except:
                return None


        # Utility function to tidy up the main loop. Sends a UDP message, allowing IP Header TTL parameter to be set
        def sendUDP(txSock, txTTL, payload, destIPAddr, destUDPPort):
            try:
                # Update socket with latest ttl value
                txSock.setsockopt(socket.SOL_IP, socket.IP_TTL, txTTL)
                # Send the UDP message
                bytesSent = txSock.sendto(payload, (destIPAddr, destUDPPort))
                return bytesSent
            except Exception as e:
                raise UDPTxError("UDPTxError " + str(e))

        # Define a socket timeout value
        timeOut = 0.1
        # Define the number of times the traceroute will attempt to illicit a response from the router.
        # This is becuse some routers will fail to respond due to rate limiting of requests.
        # Note: Each subsquent attempt alternates between two possible ports
        # The first attempt will be to use the destination port for the stream
        # If that fails, a fallback port specified in the Registry will be used. Routers are more likely to respond
        # on this other port (33434)
        noOfRetries = 6
        # Get the max no of hops before traceroute gives up
        maxNoOfHops = Registry.tracerouteMaxHops
        # Get the UDP 'fallback' port
        fallbackPort = Registry.tracerouteFallbackUDPDestPort
        # The no. of consecqutive 'no response from router' requests we'll tolerate before giving up
        maxNoOfNoResponse = 5
        # Counts the number of consequtive 0 responses. If this exceeds maxNoOfNoResponse, traceroute will abort
        noResponseCounter = 0
        # Flag to signal that the tx udp and icmp rx flags were created successfully
        socketsCreatedSuccesfullyFlag = False

        Utils.Message.addMessage("DBUG:__tracerouteLinuxOSXThread starting for stream " + str(self.syncSourceIdentifier))
        try:
            # Create tx (udp) and rx (icmp) sockets, specifying the ip address we will be transmitting from
            udpTx, icmpRx = createSockets(self.SRC_IP_ADDR)
            # Set the 'sockets okay' flag so that the main while loop will start
            socketsCreatedSuccesfullyFlag = True
        except Exception as e:
            Utils.Message.addMessage("ERR: __tracerouteLinuxOSXThread.createSockets() " + str(e))
            Utils.Message.addMessage("\033[31mHint: Run as sudo to enable traceroute functionality")
            # If a UI instance (user interface) reference was supplied, display an error message on the UI
            maxWidth = 60
            errorText = "Insufficient rights to enable traceroute functionality.".center(maxWidth) + \
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


        tracerouteHopsListMustMatchThreshold = 2
        # Additionally, it's possible a mismatch would occur if a hop flapped to/from zero. This is likely to be quite a
        # frequent occurance. And, given the length of time it takes a traceroute to complete, we don't necessarily want
        # to write-off the results we have
        tracerouteHopsListMismatchCounterThreshold = 5 # No of consecutive failures before clearing the hopsList
        tracerouteHopsListMismatchCounter = 0 # Counts the no of consecutive failures
        try:
            # Perform the traceroute in an infinite loop as long as the transmit stream is alive
            # The traceroute is performed n times. Only when the same route has been confirmed will the
            # tracerouteHopsList be updated. This is to guard against situations where the route changes mid-traceroute
            while self.timeToLive != 0 and socketsCreatedSuccesfullyFlag:
                # A list to contain two (or more) tracerouteHopsList lists. The lists can then be compared. Only when n
                # consecqutive identical lists have been determined can we say that we have a 'stable' route
                # Create empty list to put the results of each traceroute attempt into
                tracerouteResultsList = []
                for tracerouteAttempt in range (0,tracerouteHopsListMustMatchThreshold):
                    # Utils.Message.addMessage("traceroute attempt " + str(tracerouteAttempt))
                    # This is the main outer traceroute loop and counts the hops
                    # Set initial ttl
                    ttl = 0
                    # This list will be populated with the results of the traceroute
                    hopsList = []
                    # Utils.Message.addMessage("Starting traceroute....ttl = 1")
                    while ttl < maxNoOfHops and self.timeToLive != 0:
                        attemptsCount = 1
                        ttl += 1
                        # Initialise hop addr. This will be overwritten if an ICMP reply is received for this hop
                        icmpSrcAddr = None
                        # print("hop counter starting: ttl: " + str(ttl))
                        # This loop counts the attempts for each hop
                        while (attemptsCount < noOfRetries) and self.timeToLive != 0:
                            # print ("Attempts loop starting. Hop: " + str(ttl) + ", Attempt: " + str(attemptsCount))
                            # Send UDP packet
                            # determine which destination port we should be using (based on the no of attempts so far)
                            if attemptsCount % 2 == 1:
                                udpTxPort = self.UDP_TX_PORT
                            else:
                                udpTxPort = fallbackPort
                            try:
                                sendUDP(udpTx, ttl, b'isptest', self.UDP_TX_IP, udpTxPort)
                            except Exception as e:
                                Utils.Message.addMessage("ERR: __tracerouteLinuxOSXThread.sendUDP() . Aborting" + str(e))
                            # Increment the attempts counter
                            attemptsCount += 1


                            # Receive ICMP packet(s)
                            # This loop waits to receive icmp packets
                            # It's possible we might receive icmp packets not destined for us. Therfore we can't just accept
                            # the first icmp packet we receive. We have to examine its contents
                            # Either a socket.timeout, an elapsedTime timeout or a icmpReplyMatcher=True will cause this while
                            # loop to break

                            # Create elapsed timer
                            startTime = timer()
                            # print("Receive loop started....: ")
                            while True:
                                # Infinite loop to receive all icmp packets
                                # Break out of loop:
                                #   If timeOut period has been exceeded
                                #   if socket timeout exception raised
                                #   If matcher matches an icmp reply
                                elapsedTime = timer() - startTime
                                if elapsedTime > (timeOut * 2) or self.timeToLive == 0:
                                    # print("elapsedTimer exceeded twice timeout " + str(round(elapsedTime,1)) + "/" + str(timeOut * 2))
                                    break
                                try:
                                    # Receive from socket
                                    data, addr = icmpRx.recvfrom(5012)
                                    # Snapshot the source address (of the received icmp packet)
                                    __icmpSrcAddr = addr[0]
                                    # Create ICMPHeader object from the received data. This will unpack and decode the fields
                                    # The IP Header is contained within the first 20 bytes
                                    # The ICMP Message Header is contained within the next 8 bytes
                                    # The data after that is copy of the entire IPv4 header (20 bytes)
                                    # ipHeaderOfReply = IPHeader(data[0:20])
                                    # Decode the ICMP header
                                    icmpHeader = ICMPHeader(data[20:28])
                                    # Decode the ICMP payload, which contains a copy of the IP header originally sent
                                    # From this we can verify that the TTL and source IP address were the same as that sent
                                    # Therefore we can infer that this particular ICMP message is our reply, otherwise we discard the
                                    # message and listen again (within the timeout period)
                                    ipHeaderOfOriginalSender = IPHeader(data[28:48])

                                    # print(str(ttl) + ":" + "tx src addr: " + str(ipHeaderOfOriginalSender.s_addr) +\
                                    #         ", ttl when received: " + str(ipHeaderOfOriginalSender.ttl) +\
                                    #         ", attempt: " + str(attemptsCount) +\
                                    #         ", tx port: " + str(udpTxPort) +\
                                    #           ", icmp type: " + str(icmpHeader.type) +\
                                    #           ", icmp code: " + str(icmpHeader.code) + \
                                    #           ", reply from addr: " + str(addr[0]) +\
                                    #       " elapsed time: " + str(round(elapsedTime,1)))

                                    # Test to see if this icmp packet is addressed to 'us'
                                    # Detect TTL Expired messages (icmp type 11, code 0)
                                    if icmpReplyMatcher(icmpHeader,ipHeaderOfOriginalSender, icmpType=11, icmpCode=0,\
                                                                            srcAddress=self.SRC_IP_ADDR, srcTtl=1,\
                                                                            destAddress=self.UDP_TX_IP):

                                        # This is a TTL expired in transit message, for us - snapshot the address
                                        icmpSrcAddr = __icmpSrcAddr
                                        # Cause the outer 'attempts counter' loop to break
                                        attemptsCount = noOfRetries
                                        # Break out of this (the icmp receive) loop
                                        break

                                    # Detect Destination Host Port unreachable, destination reached
                                    if icmpReplyMatcher(icmpHeader,ipHeaderOfOriginalSender, icmpType=3, icmpCode=3,\
                                                                            srcAddress=self.SRC_IP_ADDR, srcTtl=1,
                                                                            destAddress=self.UDP_TX_IP):

                                        # This is a Destination Port Unreaschable address, destination reached
                                        icmpSrcAddr = __icmpSrcAddr
                                        # Cause the outer 'attempts counter' loop to break
                                        attemptsCount = noOfRetries
                                        # Cause the outer-outer hops counter loop to break
                                        ttl = maxNoOfHops
                                        # Break out of this (the icmp receive) loop
                                        break

                                except socket.timeout:
                                    # print("socket timeout")
                                    pass

                                except Exception as e:
                                    udpTx.close()
                                    icmpRx.close()
                                    raise ICMPRxError("ICMPRxError " + str(e))
                        # At the end of each attempts count per hop, append the address to the hops list
                        # To remain comptibilty with the original traceroute, break the address into a list of octets

                        ############# The 'result' (if there was a response) of the current hop is in var icmpSrcAddr.
                        # Has icmpSrcAddr been populated with an address?
                        if icmpSrcAddr is not None:
                            # The upstream router responded
                            # Reset the 'no response' counter
                            noResponseCounter = 0
                            # Utils.Message.addMessage("tracerouteLinux icmpSrcAddr " + str(icmpSrcAddr))
                            # Query the WhoisResolver to find the owner of the domain
                            Utils.WhoisResolver.queryWhoisCache(icmpSrcAddr)
                            # If so, break the address up into a list of octets - this is how they're stored in self.tracerouteHopsList
                            icmpSrcAddrOctets = str(icmpSrcAddr).split('.')
                            hopsList.append([int(icmpSrcAddrOctets[0]), int(icmpSrcAddrOctets[1]), int(icmpSrcAddrOctets[2]),
                                               int(icmpSrcAddrOctets[3])])
                        else:
                            # The upstream router didn't respond
                            # Utils.Message.addMessage("no response. Setting hop " + str(ttl) + " to 0.0.0.0")
                            # Increment the 'no response' counter
                            noResponseCounter += 1
                            # If there was no router response for this hop, add 0.0.0.0 as the hop address
                            hopsList.append([0,0,0,0])

                        # Now check to see if we've received five 'no replies' in a row, if so, give up
                        # Or else, if we've reached the max no of hops, give up
                        if (noResponseCounter > maxNoOfNoResponse) or (ttl == maxNoOfHops):
                            # print ("5 in a row, aborting")
                            # Utils.Message.addMessage(str(noResponseCounter) + " None's in a row or hop limit reached. Aborting")
                            # Cause the outer-outer hops counter loop to break
                            ttl = maxNoOfHops
                            # Break out of this (hops) loop
                            break

                    # Traceroute pass completed,Now strip off any trailing 0.0.0.0 (no responses)
                    if len(hopsList) > 0:
                        elementsToTrim = 0
                        # Work backwards from the end of the list
                        for x in range(len(hopsList) - 1, 0, -1):
                            if hopsList[x] == [0, 0, 0, 0]:
                                elementsToTrim += 1
                            else:
                                # Otherwise a non-0.0.0.0 address present, so break out of the loop
                                break
                        # Now actually trim the redundant trailing 0.0.0.0's from the tracerouteHopsList list
                        if elementsToTrim > 0:
                            try:
                                # Slice the unwanted elements from the top of the list (keeping only the bottom of the list)
                                hopsList = hopsList[:(len(hopsList) - elementsToTrim)]
                            except Exception as e:
                                Utils.Message.addMessage(
                                    "ERR:__tracerouteLinuxOSXThread() trim trailing 0.0.0.0s " + str(e))

                    # Traceroute pass completed and hopslist trimmed. Now append to tracerouteResultsList for later validation
                    # Add the latest traceroute result to tracerouteResultsList
                    tracerouteResultsList.append(hopsList)

                # Now compare the contents of the lists within tracerouteResultsList for equality
                if len(tracerouteResultsList) > 0:
                    listsAreEqual = False
                    for n in range(1,len(tracerouteResultsList)):
                        # compare lists n and n-1 for equality
                        if tracerouteResultsList[n-1] == tracerouteResultsList[n]:
                            # If equal, move onto the next pair
                            listsAreEqual = True
                        else:
                            # If the lists aren't equal, set the flag and break out of the loop
                            listsAreEqual = False
                            break
                    if listsAreEqual is True:
                        # If the lists are all identical that means that n consecutive traceroutes gave the same result
                        # so the traceroute has been validated
                        # Check to see if the existing instance variable version of hopsList is different to
                        # the latest validated traceroute hopslist. If it's different, update the instance variable version
                        # Otherwise leave it alone. This should minimise the risk of access violations
                        self.tracerouteHopsListMutex.acquire()
                        self.tracerouteHopsList = hopsList
                        self.tracerouteHopsListMutex.release()
                        # Successful (replicated) traceroute has completed, so reset the mismatch counter
                        tracerouteHopsListMismatchCounter = 0
                        # Recalculate the checksum for the hopsList
                        self.tracerouteChecksum = self.createTracerouteChecksum(hopsList)
                        # # Dump successful hopslist to the log
                        # hopsListAsString = ""
                        # for x in hopsList:
                        #     hopsListAsString += str(x[0]) + "." + str(x[1]) + "." + str(x[2]) + "." + str(x[3]) + ","
                        # Utils.Message.addMessage(
                        #     "DBUG:Traceroute successful match: (" + str(len(hopsList)) + "), " + str(hopsListAsString))
                    else:
                        # Consequtive traceroutes were not identical. Perhaps the route changed, mid-traceroute?
                        # Increment the mismatch counter
                        tracerouteHopsListMismatchCounter += 1
                        # # Dump attempt 1 to the log
                        # hopsListAsString = ""
                        # for x in tracerouteResultsList[0]:
                        #     hopsListAsString += str(x[0])+"."+str(x[1])+"."+str(x[2])+"."+str(x[3])+","
                        # Utils.Message.addMessage(
                        #     "DBUG:Traceroute results discrepency (attempt 1). MismatchCounter: " + \
                        #     str(tracerouteHopsListMismatchCounter) + ", " + str(hopsListAsString))
                        # # Dump attempt 2 to the log
                        # hopsListAsString = ""
                        # for x in tracerouteResultsList[1]:
                        #     hopsListAsString += str(x[0]) + "." + str(x[1]) + "." + str(x[2]) + "." + str(x[3]) + ","
                        # Utils.Message.addMessage(
                        #     "DBUG:Traceroute results discrepency (attempt 2). MismatchCounter: " + \
                        #     str(tracerouteHopsListMismatchCounter) + ", " + str(hopsListAsString))

                        # Now test to see if we have exceeded the max no of allowed mismatches
                        if tracerouteHopsListMismatchCounter > tracerouteHopsListMismatchCounterThreshold:
                            Utils.Message.addMessage(\
                                "DBUG:Traceroute. Stream (" + str(self.syncSourceIdentifier) +\
                                ") Exceeded consecutive mismatch Threshold, clearing hopsList ")
                            self.tracerouteHopsListMutex.acquire()
                            self.tracerouteHopsList = []
                            self.tracerouteHopsListMutex.release()
                            # Clear the traceroute checksum
                            self.tracerouteChecksum = 0

                # Now update the tracerouteHops list in the corresponding RtpStreamResults object (if it exists)
                # Note: This is not transmitted by the receiver (because it's not part of the stats dictionary)
                # So has to be updated manually here
                try:
                    # get the instance of the corresponding RtpStreamResults object
                    rtpStreamResults = self.rtpTxStreamResultsDict[self.syncSourceIdentifier]
                    # Copy the entire RtpGenerator tracerouteHops list into the rtpStreamResults tracerouteHops list
                    rtpStreamResults.setTraceRouteHopsList(hopsList)

                except Exception as e:
                    # Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread() update RtpStreamResults tracerouteHopList " + str(e))
                    pass

                # Sleep for 1 sec between completed traceroutes
                time.sleep(1)
        except Exception as e:
            Utils.Message.addMessage("ERR: __tracerouteLinuxOSXThread outer loop error. " + str(type(e)) + ", " + str(e))

        finally:
            try:
                if socketsCreatedSuccesfullyFlag:
                    # Thread is ending. Close sockets
                    udpTx.close()
                    icmpRx.close()
            except Exception as e:
                Utils.Message.addMessage(
                    "ERR: __tracerouteLinuxOSXThread couldn't close sockets. " + str(type(e)) + ", " + str(e))

        Utils.Message.addMessage("DBUG:__tracerouteLinuxOSXThread ending ")

    # This is a rewrite of the original __tracerouteThreadScapyWindows using Scapy to send/receive packets still, but
    # based on the logic/mechanics of __tracerouteLinuxOSXThread (which was my own design)
    def __tracerouteThreadScapyWindowsRewrite(self):
        # Define a socket timeout value
        timeOut = 0.5
        # Define the number of times the traceroute will attempt to illicit a response from the router.
        # This is becuse some routers will fail to respond due to rate limiting of requests.
        # Note: Each subsquent attempt alternates between two possible ports
        # The first attempt will be to use the destination port for the stream
        # If that fails, a fallback port specified in the Registry will be used. Routers are more likely to respond
        # on this other port (33434)
        noOfRetries = 4
        # Get the max no of hops before traceroute gives up
        maxNoOfHops = Registry.tracerouteMaxHops
        # Get the UDP 'fallback' port
        fallbackPort = Registry.tracerouteFallbackUDPDestPort
        # The no. of consecqutive 'no response from router' requests we'll tolerate before giving up
        maxNoOfNoResponse = 5
        # Counts the number of consequtive 0 responses. If this exceeds maxNoOfNoResponse, traceroute will abort
        noResponseCounter = 0

        Utils.Message.addMessage(\
            "DBUG:__tracerouteThreadScapyWindowsRewrite starting for stream " + str(self.syncSourceIdentifier))
        # A list to contain two (or more) tracerouteHopsList lists. The lists can then be compared. Only when n
        # consecqutive identical lists have been determined can we say that we have a static route
        tracerouteHopsListMustMatchThreshold = 2
        try:
            # Perform the traceroute in an infinite loop as long as the transmit stream is alive
            while self.timeToLive != 0:
                # Create empty list to put the results of each traceroute attempt into
                tracerouteResultsList = []
                for tracerouteAttempt in range(0, tracerouteHopsListMustMatchThreshold):
                    # This is the main outer traceroute loop and counts the hops
                    # Set initial ttl
                    ttl = 0
                    # This list will be populated with the results of the traceroute
                    hopsList = []
                    # Utils.Message.addMessage("Starting traceroute....ttl = 1")
                    while ttl < maxNoOfHops and self.timeToLive != 0:
                        attemptsCount = 1
                        ttl += 1
                        # Initialise hop addr. This will be overwritten if an ICMP reply is received for this hop
                        icmpSrcAddr = None
                        # Utils.Message.addMessage("hop counter starting: ttl: " + str(ttl))
                        # This loop counts the attempts for each hop
                        while (attemptsCount < noOfRetries) and self.timeToLive != 0:
                            # print ("Attempts loop starting. Hop: " + str(ttl) + ", Attempt: " + str(attemptsCount))
                            # Send UDP packet
                            # determine which destination port we should be using (based on the no of attempts so far)
                            # and create a packet accordingly
                            if attemptsCount % 2 == 1:
                                pkt = IP(dst=self.UDP_TX_IP, ttl=ttl) / UDP(dport=self.UDP_TX_PORT)
                            else:
                                pkt = IP(dst=self.UDP_TX_IP, ttl=ttl) / UDP(dport=fallbackPort)

                            # Now send the packet and wait for a reply
                            reply = sr1(pkt, verbose=0, timeout=timeOut)

                            # Increment the attempts counter
                            attemptsCount += 1
                            # Test the reply (should be an ICMP message, or None if the router doesn't respond)
                            if reply is not None:
                                # Utils.Message.addMessage("Message reply type " + str(reply.type))
                                # Detect TTL Expired messages (icmp type 11, code 0)
                                if reply.type == 11:
                                    # This is a TTL expired in transit message, for us - snapshot the address
                                    icmpSrcAddr = reply.src
                                # Detect Destination Host Port unreachable, destination reached
                                if reply.type == 3 or reply.src == self.UDP_TX_IP:
                                    icmpSrcAddr = reply.src
                                    # Cause the outer-outer hops counter loop to break. The traceroute is complete
                                    ttl = maxNoOfHops
                                # Reset the 'no response' counter
                                noResponseCounter = 0
                                # We have a reply for this hop, so break out of the attempts loop
                                # This will cause the ttl to increment (to the next hop value)
                                break
                        # Has icmpSrcAddr been populated with an address?
                        if icmpSrcAddr is not None:
                            # It has - the upstream router did respond
                            # Query the WhoisResolver to find the owner of the domain
                            Utils.WhoisResolver.queryWhoisCache(icmpSrcAddr)
                            # If so, break the address up into a list of octets - this is how they're stored in self.tracerouteHopsList
                            icmpSrcAddrOctets = str(icmpSrcAddr).split('.')
                            hopsList.append(
                                [int(icmpSrcAddrOctets[0]), int(icmpSrcAddrOctets[1]), int(icmpSrcAddrOctets[2]),
                                 int(icmpSrcAddrOctets[3])])
                        else:
                            # icmpSrcAddr has not been overwritten with an addres so the upstream did not respond
                            # Increment the 'no response' counter
                            noResponseCounter += 1
                            # As there was no router response for this hop, add 0.0.0.0 as the hop address
                            hopsList.append([0, 0, 0, 0])

                        # Now check to see if we've received five 'no replies' in a row, if so, give up
                        # Or else, if we've reached the max no of hops, give up
                        if (noResponseCounter > maxNoOfNoResponse) or (ttl == maxNoOfHops):
                            # print ("5 in a row, aborting")
                            # Utils.Message.addMessage(str(noResponseCounter) + " None's in a row or hop limit reached. Aborting")
                            # Cause the outer-outer hops counter loop to break
                            ttl = maxNoOfHops
                            # Break out of this (hops) loop
                            break
                    # Traceroute pass completed, now append to tracerouteResultsList for later validation
                    # Add the latest traceroute result to tracerouteResultsList
                    tracerouteResultsList.append(hopsList)

                # Now compare the contents of the lists within tracerouteResultsList for equality
                if len(tracerouteResultsList) > 0:
                    listsAreEqual = False
                    for n in range(1,len(tracerouteResultsList)):
                        # compare lists n and n-1 for equality
                        if tracerouteResultsList[n-1] == tracerouteResultsList[n]:
                            # If equal, move onto the next pair
                            listsAreEqual = True
                        else:
                            # If the lists aren't equal, set the flag and break out of the loop
                            listsAreEqual = False
                            break
                    if listsAreEqual is True:
                        # If the lists are all identical that means that n consecqutive traceroutes gave the same result
                        # so the traceroute has been validated
                        # copy the new tracerouteHopsList back into the instance variable version
                        # Utils.Message.addMessage("traceroute results are identical, updating tracerouteHopsList")
                        self.tracerouteHopsListMutex.acquire()
                        self.tracerouteHopsList = hopsList
                        self.tracerouteHopsListMutex.release()
                    else:
                        # Consequtive traceroutes were not identical. Perhaps the route changed, mid-traceroute?
                        # Empty the tracerouteHopsList - it can't now be trusted
                        Utils.Message.addMessage("DBUG:Traceroute results discrepency. emptying tracerouteHopsList ")
                        self.tracerouteHopsListMutex.acquire()
                        self.tracerouteHopsList = []
                        self.tracerouteHopsListMutex.release()


                # Now update the tracerouteHops list in the corresponding RtpStreamResults object (if it exists)
                # Note: This is not transmitted by the receiver (because it's not part of the stats dictionary)
                # So has to be updated manually here
                try:
                    # get the instance of the corresponding RtpStreamResults object
                    rtpStreamResults = self.rtpTxStreamResultsDict[self.syncSourceIdentifier]
                    # Copy the entire RtpGenerator tracerouteHops list into the rtpStreamResults tracerouteHops list
                    rtpStreamResults.setTraceRouteHopsList(hopsList)

                except Exception as e:
                    # Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThreadScapyWindowsRewrite() update RtpStreamResults tracerouteHopList " + str(e))
                    pass

                # Sleep for 2 sec between completed traceroutes
                time.sleep(2)


        except Exception as e:
            # If the traceroute routine fails, this is mostly because the program was started without admin rights
            # Put up an error message on screen to warn the user
            Utils.Message.addMessage("ERR: RtpGenerator.__tracerouteThreadScapyWindows.sr1() " + str(e))
            Utils.Message.addMessage("\033[31mHint: Run as sudo to enable traceroute functionality")
            # If a UI instance (user interface) reference was supplied, display an error message on the UI
            maxWidth = 60
            errorText = "Insufficient rights to enable traceroute functionality.".center(maxWidth) + \
                        "\n\n" + "isptest TRANSMITTER will continue to run, but without traceroute.".center(maxWidth) + \
                        "\n" + "To enable this function, exit the app and run as sudo ".center(maxWidth) + \
                        "\n" + "(or as Administrator, if running on Windows)".center(maxWidth) + \
                        "\n\n" + "<Press any key to continue>".center(maxWidth)
            if self.uiInstance is not None:
                try:
                    self.uiInstance.showErrorDialogue("Traceroute error", errorText)
                except Exception as e:
                    Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThreadScapyWindows: display error message on UI " + \
                                             str(e))
        Utils.Message.addMessage("DBUG:__tracerouteThreadScapyWindows ending for stream " + str(self.syncSourceIdentifier))



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

        self.rtpTxStreamResultsDict = rtpGeneratorObject.rtpTxStreamResultsDict
        self.rtpTxStreamResultsDictMutex = rtpGeneratorObject.rtpTxStreamResultsDictMutex

        # This counts the receive errors reported by the unpickler routine in __resultsReceiverThread()
        # (normally caused by UDP transmission errors. Better than generating an error message and clogging
        # up the log file)
        self.receiveDecodeErrorCounter = 0

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

        # Check to see if the RtpStreamResults object exists in rtpTxStreamResultsDict
        if self.relatedRtpGenerator.syncSourceIdentifier in self.rtpTxStreamResultsDict:
            # If so, invoke its killStream method (to remove itself from rtpTxStreamResultsDict
            self.rtpTxStreamResultsDict[self.relatedRtpGenerator.syncSourceIdentifier].killStream()


    def __resultsReceiverThread(self):
        Utils.Message.addMessage("INFO: ResultsReceiver thread starting")

        rxMssage = b""  # Array (string IN BYTE FORMAT) to store the reconstructed message
        lastReceivedFragment = 0  # Tracks the most recently received fragment

        while self.receiverActiveFlag:
            # Wait for relatedRtpGenerator object to set up a socket binding
            self.udpSocket = self.relatedRtpGenerator.getUDPSocket()
            if self.udpSocket != 0:
                try:
                    # Wait for data (blocking function call)
                    data, addr = self.udpSocket.recvfrom(4096)  # buffer size is 4096 bytes
                    # Utils.Message.addMessage("DBUG: ResultsReceiver.__receiverThread()" + ", " + str(data))
                    # attempt to unpickle the received data to yield a stats dictionary

                    # Create empty dictionary to hold incoming stats updates
                    stats = {}
                    # Create empty list to store incoming events list updates
                    latestEventsList =[]

                    # First round of unpickling - extract the fragment (a tuple)
                    try:
                        fragment = pickle.loads(data)
                        # detect first fragment
                        if fragment[0] == 0:
                            # Clear away any existing contents of rxMessage
                            rxMssage = b""
                            # Append the message portion of this fragment to rxMessage
                            # rxMssage += fragment[3]
                            rxMssage =b"".join([rxMssage,fragment[3]])

                            # Record the index no of the last received fragment
                            lastReceivedFragment = fragment[0]

                        # Detect next expected fragment
                        if fragment[0] == (lastReceivedFragment +1):
                            # Append the message portion of this fragment to rxMessage
                            # rxMssage += fragment[3]
                            rxMssage =b"".join([rxMssage,fragment[3]])
                            # Record the index no of the last received fragment
                            lastReceivedFragment = fragment[0]

                        # Detect final fragment of message
                        if fragment[0] == (fragment[1] - 1):
                            # Append the final message portion of this fragment to rxMessage
                            # rxMssage += fragment[3]
                            rxMssage =b"".join([rxMssage,fragment[3]])
                            # Whole message has hopefully been reassembled
                            # Now unpickle (for a second time) to reconstruct the originally pickled and tx'd Python object

                            # We're expecting a dictionary containing a stats dictionary{} and an eventsList{} containing the
                            # last 5 events
                            try:
                                # Attempt to reconsctruct the original message sent by ResultsTransmitter
                                # unPickledMessage = pickle.loads(rxMssage, fix_imports=True)
                                unPickledMessage = pickle.loads(rxMssage)
                                # Utils.Message.addMessage("DBG:" + str(unPickledMessage))

                                # Attempt to extract the stats dictionary and eventsList list
                                try:
                                    stats = unPickledMessage["stats"]
                                    latestEventsList = unPickledMessage["eventList"]
                                except Exception as e:
                                    Utils.Message.addMessage(
                                        "ERR: __resultsReceiverThread (error unpacking stats and eventList): " + str(e))

                            except Exception as e:
                                # Utils.Message.addMessage("ERR: __resultsReceiverThread(pickle.loads(all fragments)): " + str(e))
                                # Increment the receive error counter
                                self.receiveDecodeErrorCounter += 1

                        # Detect too many fragments
                        if fragment[0] > (fragment[1] - 1):
                            # More fragments than expected
                            Utils.Message.addMessage("ERR: __resultsReceiverThread. More fragments received than expected")

                    except Exception as e:
                            Utils.Message.addMessage("ERR: __resultsReceiverThread(single fragment): Is Receiving running Python2 If so, switch to Python 2 at this end - Incompatible pickles?" + str(e))

                    # Check if we have some new stats data
                    if len(stats) > 0:
                        try:
                            # Firstly check to see a stream object with this id exists in self.rtpTxStreamResultsDict
                            if stats["stream_syncSource"] in self.rtpTxStreamResultsDict:
                                # If it does, add the new data
                                self.rtpTxStreamResultsDict[stats["stream_syncSource"]].updateStats(stats)

                            else:
                                # Otherwise that stream object doesn't exist yet, so create it
                                Utils.Message.addMessage("INFO:_resultsReceiverThread(). Stream doesn't exist, adding: "
                                                   + str(stats["stream_syncSource"]))
                                # Create new RtpStreamResults object
                                rtpStreamResults = RtpStreamResults(stats["stream_syncSource"],
                                                                    self.rtpTxStreamResultsDict,
                                                                    self.rtpTxStreamResultsDictMutex)
                                # Immediately update the stats
                                rtpStreamResults.updateStats(stats)
                                # Add the new RtpStreamResults object to the self.rtpStreamResultsDict{}
                                # addRtpStreamToDict(stats["stream_syncSource"], rtpStreamResults,
                                #                    self.rtpTxStreamResultsDict, self.rtpTxStreamResultsDictMutex)
                        except Exception as e:
                            Utils.Message.addMessage("ERR: __resultsReceiverThread. Invalid stats dict or can't add new stream to rtpTxStreamResultsDict. " + str(e))

                    # Check to see if the new eventList contains any data and also that there exists a stream object to add the data to
                    if len(latestEventsList) > 0 and len(stats) > 0:
                        try:
                            # Utils.Message.addMessage("DBUG: **latestEventsList: " + str(latestEventsList[-1].eventNo))
                            # Get handle on an (existing) rtpStreamResults object
                            syncSourceID = stats["stream_syncSource"]
                            rtpStreamResults = self.rtpTxStreamResultsDict[syncSourceID]

                            # Work out whether the eventList contains any new events that we haven't already seen
                            firstEventNoInNewList = latestEventsList[0].eventNo
                            lastEventNoInNewList = latestEventsList[-1].eventNo

                            # # Get latest known event no from the rtpStreamResults stream object
                            existingEventsList = []
                            try:
                                existingEventsList = rtpStreamResults.getRTPStreamEventList(1) # Request last event in the list

                                if len(existingEventsList) > 0:
                                    # rtpStreamResults.updateEventsList(latestEventsList)
                                    # # Extract the event no from the last known event
                                    lastKnownEventNo = existingEventsList[-1].eventNo
                                    # Utils.Message.addMessage("DBUG: firstEventNoInNewList: " + str(firstEventNoInNewList) + \
                                    #                    ", lastEventNoInNewList: " + str(lastEventNoInNewList) + \
                                    #                    ", lastKnownEventNo: " + str(lastKnownEventNo))

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
                            Utils.Message.addMessage("ERR:_resultsReceiverThread(): rtpStreamResults.updateEventsList() " + str(e))

                    # if len(stats) > 0:
                    #     try:
                    #         stream= self.rtpTxStreamResultsDict[stats["stream_syncSource"]]
                    #         x=stream.getRTPStreamEventList(1)
                    #         if len(x) > 0:
                    #             Utils.Message.addMessage("DBUG: Last known event: " + str(x[-1].type))
                    #     except Exception as e:
                    #         Utils.Message.addMessage("DBUG: wtf " + str(e))
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
