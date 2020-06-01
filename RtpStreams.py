#!/usr/bin/env python
# Defines RtpStream objects for use by isptest
# James Turner 20/2/20
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
from timeit import default_timer as timer  # Used to calculate elapsed time
import math
import json
from abc import ABCMeta, abstractmethod  # Used for event abstract class
from copy import deepcopy
import pickle
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
    # NOTE: The following line may/may not be necessary for Python 2.7. Python 3 should use the class declaration
    # class Event(ABC) but this causes an error in Python 2.7
    __metaclass__ = ABCMeta
    @abstractmethod
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

    # Returns a string summary of the event, with optional fields
    @abstractmethod
    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        # Returns a dictionary containing a timestamp and a concise description of the event as a string
        # It invokes the method from the parent class (Event) Event.createCommonSummaryText() to allow
        # some control over the construction of the string (i.e how much detail it contains) via the optional args
        # By default, all the optional args are set to True, so the Summary will actually be quite detailed!
        optionalFields = ""
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)
        summary += optionalFields


        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    @abstractmethod
    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = ""
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",eventNo," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
              "," + optionalFields
        return csv

    @abstractmethod
    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Add additional keys as required
        data = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats}
        return json.dumps(data, sort_keys=True, indent=4, default=str)


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
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",Event no," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
              ",friendlyName," +self.stats["stream_friendly_name"]+ "," +optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        data = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats,
                'rtpSequenceNo': self.firstPacketReceived.rtpSequenceNo}
        return json.dumps(data, sort_keys=True, indent=4, default=str)

# Define an event that represents a loss of rtpStream
class StreamLost(Event):

    def __init__(self, stats, lastPacketReceived):
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

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        optionalFields = ", Most recent rtp sequence no: "+str(self.lastPacketReceived.rtpSequenceNo)
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "lastRtpSequenceNo,"+str(self.lastPacketReceived.rtpSequenceNo)
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",eventNo," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
              ",friendlyName," +self.stats["stream_friendly_name"]+ "," +optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Add additional keys as required
        data = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats,
                'lastRtpSequenceNo': self.lastPacketReceived.rtpSequenceNo}
        return json.dumps(data, sort_keys=True, indent=4, default=str)

# Define an event object that represents a excessive jitter event
class ExcessiveJitter(Event):

    def __init__(self, stats, lastPacketReceived):
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
    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        optionalFields = " "+str(int(self.stats["jitter_mean_1S_uS"])) + "/" + str(int(self.stats["jitter_long_term_uS"])) + "uS"
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)
        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "jitter_mean_1S_uS,"+str(int(self.stats["jitter_mean_1S_uS"]))+\
            ",jitter_long_term_uS,"+str(int(self.stats["jitter_long_term_uS"]))
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",eventNo," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
              ",friendlyName," +self.stats["stream_friendly_name"]+ "," +optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Add additional keys as required
        data = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats}
        return json.dumps(data, sort_keys=True, indent=4, default=str)

# Define an event object that represents a processor overload. This might happen if the calculateThread can't process
# incoming packets fast enough
class ProcessorOverload(Event):
    def __init__(self, stats, lastPacketReceived):
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

    def getSummary(self, includeStreamSyncSourceID=True, includeEventNo=True, includeType=True, includeFriendlyName=True):
        optionalFields =  " "+str(int(self.stats["stream_processor_utilisation_percent"])) + "% cpu usage. "
        summary = Event.createCommonSummaryText(self, includeStreamSyncSourceID=includeStreamSyncSourceID,
                                                includeEventNo=includeEventNo,
                                                includeType=includeType,
                                                includeFriendlyName=includeFriendlyName)

        summary += optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "stream_processor_utilisation_percent,"+ str(self.stats["stream_processor_utilisation_percent"])+\
            ",lastRtpSequenceNo," + str(self.lastPacketReceived.rtpSequenceNo)
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",eventNo," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
              ",friendlyName," +self.stats["stream_friendly_name"]+ "," +optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Add additional keys as required
        data = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats,
                'lastRtpSequenceNo': self.lastPacketReceived.rtpSequenceNo}
        return json.dumps(data, sort_keys=True, indent=4, default=str)

# Define an event that represent a glitch
# This will be in the form of the packets (RtpData objects) either side of the 'hole' in received data
class Glitch(Event):
    def __init__(self, stats, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap):
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

        # Calculate packets lost by taking the diff of the sequence nos at the end and start of hole
        # The '-1' is because it's fences and fenceposts
        self.packetsLost = abs(
            firstPackedReceivedAfterGap.rtpSequenceNo - lastReceivedPacketBeforeGap.rtpSequenceNo) - 1
        # Guard against the possibility of a -ve packetsLost value
        if self.packetsLost < 0:
            self.packetsLost =0
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
        csv = self.type + ",timeCreated," + self.timeCreated.strftime("%d/%m/%Y %H:%M:%S") + \
              ",eventNo," + str(self.eventNo) + ",syncSource," + str(self.stats["stream_syncSource"]) + \
              ",friendlyName," +self.stats["stream_friendly_name"]+ "," +optionalFields
        return csv

    def getJSON(self):
        # Returns a json object representation of the event as a string
        # Add additional keys as required
        data = {'type': self.type, 'timeCreated': self.timeCreated,
                'eventNo': self.eventNo,
                'syncSource': self.stats["stream_syncSource"], 'stats': self.stats,
                'packetsLost': self.packetsLost, 'duration': self.glitchLength,
                'lastReceivedPacketBeforeGap.rtpSequenceNo': self.startOfGap.rtpSequenceNo,
                'firstPackedReceivedAfterGap.rtpSequenceNo': self.endOfGap.rtpSequenceNo,
                'expectedSequenceNo': self.expectedSequenceNo,
                'actualReceivedSequenceNo': self.actualReceivedSequenceNo}
        return json.dumps(data, sort_keys=True, indent=4, default=str)


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
    def __init__(self, rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData):
        self.rtpSequenceNo = rtpSequenceNo
        self.payloadSize = payloadSize
        self.timestamp = timestamp
        self.syncSource = syncSource
        self.isptestHeaderData = isptestHeaderData
        # timeDelta will store the timestamp diff between this and the previous packet
        self.timeDelta = 0
        # jitter will store the diff between the timeDelta of this and the prev packet
        self.jitter = 0

# Define a Super Class for RTP Receive streams. This will contain methods that are common to both
# RtpReceiveStream and RtpStreamResults
class RtpReceiveCommon(object):

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

        labelWidth = 33
        streamPerformance = \
            "Duration of test: ".rjust(labelWidth) + str(Utils.dtstrft(stats["stream_time_elapsed_total"])) + "\r\n" + \
            "Packet loss: ".rjust(labelWidth) + str(
                math.ceil(stats["glitch_packets_lost_total_percent"])) + "%" + "\r\n" + \
            "Total packets lost: ".rjust(labelWidth) + str(int(stats["glitch_packets_lost_total_count"])) + "\r\n" + \
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

        # Create a traceroute list of hops
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

        outputString = title + subtitle + separator + streamIPDetails + separator + streamPerformance + separator +\
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
    def __init__(self, syncSource, srcAddress, srcPort, rxAddress, rxPort, glitchEventTriggerThreshold, rxSocket,
                 rtpRxStreamsDict, rtpRxStreamsDictMutex):

        super().__init__()
        self.rtpRxStreamsDict = rtpRxStreamsDict
        self.rtpRxStreamsDictMutex = rtpRxStreamsDictMutex
        # Create private empty dictionary to hold stats for this RtpReceiveStream object. Accessible via a getter method
        self.__stats = {}
        # Assign to instance variable
        self.__stats["stream_syncSource"] = syncSource
        self.__stats["stream_srcAddress"] = srcAddress
        self.__stats["stream_srcPort"] = srcPort
        self.__stats["stream_rxAddress"] = rxAddress
        self.__stats["stream_rxPort"] = rxPort
        self.__stats["stream_transmitter_localAddress"] = "" # Will be populated by incoming isptest header data
        self.__stats["stream_transmitter_local_srcPort"] = 0  # Will be populated by incoming isptest header data
        self.__stats["stream_transmitter_destAddress"] = "" # Will be populated by incoming isptest header data
        self.__stats["stream_transmitterVersion"] = 0
        Utils.Message.addMessage("INFO: RtpReceiveStream:: Creating RtpReceiveStream with syncSource: " + str(self.__stats["stream_syncSource"]))

        # This is a reference to the UDP listening socket created in main() (to receive all incoming streams)
        # We need it, because we want to be able to reply to the sending end using the same src/dest UDP ports
        # that were used in sending the data to us (by the corresponding RtpGenerator at the far end
        self.socket = rxSocket

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
        self.rtpStreamData = []

        # Create private empty list to hold Events for this RtpReceiveStream object. Accessible via a getter method
        self.__eventList = []

        # Counter to be used by __calculateJitter()
        self.sumOfJitter_1s = 0

        # No of events to keep before purging self.__eventList = []
        self.historicEventsLimit = 50
        self.__stats["glitch_Event_Trigger_Threshold_packets"]= glitchEventTriggerThreshold
        self.__stats["glitch_glitches_ignored_counter"] = 0

        self.__stats["packet_first_packet_received_timestamp"] = datetime.timedelta()
        self.__stats["packet_last_seen_received_timestamp"] = datetime.timedelta()
        self.__stats["packet_counter_1S"] = 0
        self.__stats["packet_data_received_1S_bytes"] = 0
        self.__stats["packet_data_received_total_bytes"] = 0
        self.__stats["packet_payload_size_mean_1S_bytes"] = 0
        self.__stats["packet_counter_received_total"] = 0
        self.__stats["stream_time_elapsed_total"] = datetime.timedelta()
        self.__stats["packet_instantaneous_receive_period_uS"] = 0
        self.__stats["packet_mean_receive_period_uS"] = 0
        self.aggregateSumOfTimeDeltas = 0  # Used to calculate self.__stats["packet_mean_receive_period_uS"]

        # Aggregate Glitch counters
        self.__stats["glitch_packets_lost_total_percent"] = 0
        self.__stats["glitch_packets_lost_total_count"] = 0
        self.__stats["glitch_packets_lost_per_glitch_mean"] = 0
        self.__stats["glitch_packets_lost_per_glitch_min"] = 0
        self.__stats["glitch_packets_lost_per_glitch_max"] = 0
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
        self.__stats["glitch_most_recent_timestamp"] = datetime.timedelta()
        self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.timedelta()
        self.__stats["glitch_mean_time_between_glitches"] = datetime.timedelta()
        self.__stats["glitch_mean_glitch_duration"] = datetime.timedelta()
        self.__stats["glitch_max_glitch_duration"] = datetime.timedelta()
        self.__stats["glitch_min_glitch_duration"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastGlitch = datetime.timedelta()

        # Jitter counters
        self.__stats["jitter_min_uS"] = 0
        self.__stats["jitter_max_uS"] = 0
        self.__stats["jitter_range_uS"] = 0
        self.__stats["jitter_instantaneous"] = 0
        self.__stats["jitter_mean_1S_uS"] = 0
        self.__stats["jitter_mean_10S_uS"] = 0
        self.__stats["jitter_long_term_uS"] = 0

        self.__stats["stream_processor_utilisation_percent"] = 0

        # % ratio of 1S Jitter_uS to packet_mean_receive_period_uS that will trigger an excessJitterEvent
        self.__stats["jitter_excessive_alarm_threshold_percent"] = 30
        self.excessJitterThresholdFactor = (self.__stats["jitter_excessive_alarm_threshold_percent"] / 100.0)

        # No of seconds to inhibit an excessive jitter alarm
        self.__stats["jitter_alarm_event_timeout_S"] = 2
        self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = datetime.timedelta()
        self.__stats["jitter_time_of_last_excess_jitter_event"] = datetime.timedelta()
        self.__stats["jitter_excess_jitter_events_total"] = 0
        self.__stats["jitter_mean_time_between_excess_jitter_events"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastExcessJitterEvents = datetime.timedelta()

        # Initially, __CalculateThread loop will execute every 1mS (but will then be modified dynamically
        # based on the packet Rx period)
        self.DEFAULT_CALCULATE_THREAD_SAMPLING_INTERVAL = 0.001
        self.__stats["calculate_thread_sampling_interval_S"] = self.DEFAULT_CALCULATE_THREAD_SAMPLING_INTERVAL

        # Amount of time to elapse before a lossOfStream alarm event is triggered
        self.lossOfStreamAlarmThreshold_s = Registry.lossOfStreamAlarmThreshold_s

        # Amount of time to elapse before a stream is believed completely dead (and automatically
        # destroyed)
        self.streamIsDeadThreshold_s = Registry.streamIsDeadThreshold_s
        # Create a flag to signal when the stream is believed dead (is therefore scheduled to delete itself)
        self.believedDeadFlag = False

        # Create a __calculateThread
        self.calculateThreadActiveFlag = True # Used as a signal to shut down the calculateThread
        self.calculateThread = threading.Thread(target=self.__calculateThread, args=())
        self.calculateThread.daemon = True  # Thread will auto shutdown when the prog ends
        self.calculateThread.setName(str(self.__stats["stream_syncSource"]) + ":calculateThread")
        self.calculateThread.start()

        # create a potential stream results transmitter object for this rx stream
        # (this will only transmit data if the stream being received can be verified as being generated by
        # an instance of isptest running in TRANSMIT mode (detected in __calculateThread)
        self.resultsTransmitter = ResultsTransmitter(self)

        # Finally, add this RtpReceiveStream object to rtpRxStreamsDictMutex
        self.rtpRxStreamsDictMutex.acquire()
        self.rtpRxStreamsDict[self.__stats["stream_syncSource"]] = self
        self.rtpRxStreamsDictMutex.release()


    def killStream(self):
        # This kills the ResultsTransmitter object created by this stream  - because
        # Resultstransmitter runs as an automonomous thread created by this object.
        # Therefore unless we kill it, this RtpReceiveStream object will never be allowed to die
        self.resultsTransmitter.kill()

        # Also kill the __calculateThread associated with this receive stream
        self.calculateThreadActiveFlag = False

        # Finally remove this RtpReceiveStream (itself) from rtpRxStreamsDict
        self.rtpRxStreamsDictMutex.acquire()
        try:
            Utils.Message.addMessage("Removing RtpReceiveStream object " + str(self.__stats["stream_syncSource"]))
            del self.rtpRxStreamsDict[self.__stats["stream_syncSource"]]
        except Exception as e:
            Utils.Message.addMessage("ERR: RtpReceiveStream.killStream() (remove from rtpRxStreamsDict{})" + str(self.__stats["stream_syncSource"]))
        self.rtpRxStreamsDictMutex.release()


    def getSocket(self):
        # Thread-safe method that returns the receive UDP socket associated with this stream
        self.__udpSocketMutex.acquire()
        sock = self.socket
        self.__udpSocketMutex.release()
        return sock

    def setSocket(self, newSocket):
        # Thread-safe method that sets the UDP receive/transmit socket associated with the stream
        # Utils.Message.addMessage("RtpReceiveStream.setSocket -old() " + str(id(self.socket)))
        self.__udpSocketMutex.acquire()
        self.socket = newSocket
        self.__udpSocketMutex.release()
        # Utils.Message.addMessage("RtpReceiveStream.setSocket -New() " + str(id(self.socket)))

    def __calculateJitter(self, prevRtpPacket):
        # Iterate over self.rtpStream to get total count of data received in this batch of data, no. of packets and also calculate
        # rx time deltas and jitter
        sumOfInterPacketJitter = 0
        sumOfTimeDeltas = 0

        # Keep prevRtpPacket value safe for later (because we'll be overwriting it as we iterate over self.rtpStream[])
        z = prevRtpPacket
        # Iterate over packets received
        for y in self.rtpStream:
            # Calculate and write time delta into RtpData object
            y.timeDelta = y.timestamp - prevRtpPacket.timestamp

            # Now calculate the diff (jitter) between consecutive timeDelta values (should be in order of mS)
            # It should be simple. Just take mean of interPacketJitter
            # interPacketJitter=abs(x.timeDelta.microseconds-prevRtpPacket.timeDelta.microseconds)
            y.jitter = y.timeDelta.microseconds - prevRtpPacket.timeDelta.microseconds
            # print y.timestamp,y.timeDelta,y.jitter,"\r"
            # Calculate minimum and maximum jitter
            # But wait until 'steady' state reached by testing for totalPacketsReceived>10
            if self.__stats["packet_counter_received_total"] > 10:
                if self.__stats["jitter_min_uS"] == 0:
                    # Set initial value
                    self.__stats["jitter_min_uS"] = y.jitter
                if y.jitter < self.__stats["jitter_min_uS"]:
                    self.__stats["jitter_min_uS"] = y.jitter
                # Calculate maximum jitter
                if self.__stats["jitter_max_uS"] == 0:
                    # Set initial value
                    self.__stats["jitter_max_uS"] = y.jitter
                if y.jitter > self.__stats["jitter_max_uS"]:
                    self.__stats["jitter_max_uS"] = y.jitter
                self.__stats["jitter_range_uS"] = self.__stats["jitter_max_uS"] - self.__stats["jitter_min_uS"]

            # Sum the abs interPacketJitter values  for the subsequent jitter calculation
            # For 'instantaneous' jitter value
            sumOfInterPacketJitter += abs(y.jitter)
            # For 1 second jitter value
            self.sumOfJitter_1s += abs(y.jitter)

            # Sum the timeDeltas to calculate the instantaneous average time between packets arriving
            sumOfTimeDeltas += y.timeDelta.microseconds

            # Update prevTimestamp for next time around loop
            prevRtpPacket = y

        # Calculate jitter
        # Find the mean value of the microsecond portion of the jitter values in self.rtpStream
        # and also the instantaneous  time period between packets arriving (should, on average match the rtp
        # generator period)
        if len(self.rtpStream) > 1:
            self.__stats["jitter_instantaneous"] = sumOfInterPacketJitter / (len(self.rtpStream) - 1)
            self.__stats["packet_instantaneous_receive_period_uS"] = sumOfTimeDeltas / (len(self.rtpStream) - 1)

        else:
            # This batch of data only contains a single packet.
            # as this requires at least two packets worth of data (the difference of a difference!)
            # The meanRxPeriod is possible to deduce by comparing this new single packet with the last received
            self.__stats["jitter_instantaneous"] = self.rtpStream[-1].jitter - z.jitter
            self.__stats["packet_instantaneous_receive_period_uS"] = self.rtpStream[-1].timeDelta.microseconds


        ### Calculate long term mean packet receive period
        # Aggregate the time deltas for ever to calculate the long term average time between packets arriving
        self.aggregateSumOfTimeDeltas += sumOfTimeDeltas
        self.__stats["packet_mean_receive_period_uS"] = \
            self.aggregateSumOfTimeDeltas / self.__stats["packet_counter_received_total"]

        # Now attempt to detect excessive jitter by comparing the 1S jitter with the mean receive period.
        # Jitter should only be a problem if the packets start crashing into each other on receipt.
        # Check that long term value has actually been calculated
        if self.__stats["packet_mean_receive_period_uS"] > 0:
            if self.__stats["jitter_mean_1S_uS"] > \
                    (self.excessJitterThresholdFactor * self.__stats["packet_mean_receive_period_uS"]):
                # If jitter alarms not inhibited, add a new jitter event
                # Take diff between time.now() and the time of the last event
                if self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"].total_seconds() >= \
                        self.__stats["jitter_alarm_event_timeout_S"] or \
                        self.__stats["jitter_excess_jitter_events_total"] == 0:
                    excessiveJitterEvent = ExcessiveJitter(self.__stats, self.rtpStream[-1])
                    # Add the event to the event list
                    self.__eventList.append(excessiveJitterEvent)
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                    Utils.Message.addMessage(excessiveJitterEvent.getSummary(includeStreamSyncSourceID=False)['summary'])

                # Update the event counter for Excess Jitter
                self.__stats["jitter_excess_jitter_events_total"] += 1

                # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean period between events)
                self.sumOfTimeElapsedSinceLastExcessJitterEvents += self.__stats[
                    "jitter_time_elapsed_since_last_excess_jitter_event"]

                # Take timestamp fo this (the most recent) Excess Jitter event
                self.__stats["jitter_time_of_last_excess_jitter_event"] = datetime.datetime.now()
        # Now update the self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] timer
        if self.__stats["jitter_excess_jitter_events_total"] > 0:
            self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = datetime.datetime.now() - \
                                                                                 self.__stats[
                                                                                     "jitter_time_of_last_excess_jitter_event"]

        # Calculate meanTimeBetweenExcessJitterEvents (requires at least two jitter events)
        if self.__stats["jitter_excess_jitter_events_total"] > 1:
            self.__stats["jitter_mean_time_between_excess_jitter_events"] = \
                (self.sumOfTimeElapsedSinceLastExcessJitterEvents + self.__stats[
                    "jitter_time_elapsed_since_last_excess_jitter_event"]) / \
                self.__stats["jitter_excess_jitter_events_total"]

    def __updateGlitchStats(self, latestGlitch):
        # This method takes code out of __detectGlitches to reduce duplication
        # It's primary purpose is to update __stats keys relating to glitches (depending upon whether the
        # size of the glitch exceeds self.__stats["glitch_Event_Trigger_Threshold_packets"] or not)

        # Update packets lost counter
        self.__stats["glitch_packets_lost_total_count"] += latestGlitch.packetsLost

        # If the glitch is insignificant, increment the 'ignored' counter so we record that it happened
        if latestGlitch.packetsLost <= self.__stats["glitch_Event_Trigger_Threshold_packets"]:
            self.__stats["glitch_glitches_ignored_counter"] += 1

        # If the glitch is significant then it's worth updating the stats
        # if latestGlitch.packetsLost > self.__stats["glitch_Event_Trigger_Threshold_packets"]:
        else:
            # update aggregate glitch stats
            self.__stats["glitch_length_total_time"] += latestGlitch.glitchLength
            self.__stats["glitch_counter_total_glitches"] += 1

            # Add event to moving counters
            for x in self.movingGlitchCounters:
                x.addEvent(1)

            # Take snapshot of new time delta and add to the sum of existing values (to calculate mean)
            self.sumOfTimeElapsedSinceLastGlitch += self.__stats["glitch_time_elapsed_since_last_glitch"]

            # Calculate aggregate mean glitch stats
            if self.__stats["glitch_counter_total_glitches"] > 1:
                self.__stats["glitch_mean_glitch_duration"] = \
                    (self.__stats["glitch_mean_glitch_duration"] + latestGlitch.glitchLength) / 2
                self.__stats["glitch_packets_lost_per_glitch_mean"] = \
                    int(math.ceil((self.__stats["glitch_packets_lost_per_glitch_mean"] + latestGlitch.packetsLost) / 2.0))

            # Update glitch min/max packet loss stats
            if self.__stats["glitch_packets_lost_per_glitch_min"] < 1:
                self.__stats["glitch_packets_lost_per_glitch_min"] = latestGlitch.packetsLost

            # Update min/max counters
            if latestGlitch.packetsLost < self.__stats["glitch_packets_lost_per_glitch_min"]:
                self.__stats["glitch_packets_lost_per_glitch_min"] = latestGlitch.packetsLost

            if latestGlitch.packetsLost > self.__stats["glitch_packets_lost_per_glitch_max"]:
                self.__stats["glitch_packets_lost_per_glitch_max"] = latestGlitch.packetsLost

            # update glitch min/max duration stats
            # Test for 'zero' duration (the initial value)
            if self.__stats["glitch_min_glitch_duration"] == datetime.timedelta():
                self.__stats["glitch_min_glitch_duration"] = latestGlitch.glitchLength

            if latestGlitch.glitchLength < self.__stats["glitch_min_glitch_duration"]:
                self.__stats["glitch_min_glitch_duration"] = latestGlitch.glitchLength

            if latestGlitch.glitchLength > self.__stats["glitch_max_glitch_duration"]:
                self.__stats["glitch_max_glitch_duration"] = latestGlitch.glitchLength

            # Add the glitch to the worstGlitches leaderboard Where it will be analysed to see if it's in the top 'n')
            self.addToWorstGlitchesList(latestGlitch)
            # Get a text version of the worst glitches, and copy to the __stats[] dict
            self.__stats["glitch_worst_glitches_list"] = self.getWorstGlitches(returnSummaries=True)

        # Inhibit immediate jitter-event triggering by setting self.__stats["jitter_time_of_last_excess_jitter_event"]
        # to the current time
        self.__stats["jitter_time_of_last_excess_jitter_event"] = datetime.datetime.now()

        # Finally, reset min/max/range jitter values as they're corrupted by a glitch
        self.__stats["jitter_min_uS"] = 0
        self.__stats["jitter_max_uS"] = 0
        self.__stats["jitter_range_uS"] = 0

    def __detectGlitches(self, lastReceivedRtpPacket):

        # Test for out of sequence packet by comparing last received sequence no with that of first rtpObject in new list of data in self.rtpStream[]
        # Inhibit this for the first second (because there's nothing to compare the first packet to)
        # Also, when the seq no hits 65535 it will wrap around to zero giving a false diff. Musn't interpret this as a glitch
        if lastReceivedRtpPacket.rtpSequenceNo == 65535:
            lastReceivedRtpPacket.rtpSequenceNo = -1

        if (lastReceivedRtpPacket.rtpSequenceNo != (self.rtpStream[0].rtpSequenceNo - 1)) and \
                self.__stats["stream_time_elapsed_total"].seconds > 0:

            # Capture packets either side of the 'hole' and store them in the event list
            # Create an object representing the glitch
            glitch = Glitch(self.__stats, lastReceivedRtpPacket, self.rtpStream[0])

            # Check to see if this glitch is significant enough to be considered an event
            if glitch.packetsLost > self.__stats["glitch_Event_Trigger_Threshold_packets"]:
                # Take timestamp of most recent glitch
                self.__stats["glitch_most_recent_timestamp"] = datetime.datetime.now()
                # Add the latest glitch to the evenList[]
                self.__eventList.append(glitch)
                # Increment the all_events counter
                self.__stats["stream_all_events_counter"] += 1
                # Post a message
                Utils.Message.addMessage(glitch.getSummary(includeStreamSyncSourceID=False)['summary'])
            else:
                Utils.Message.addMessage(glitch.getSummary(includeStreamSyncSourceID=False)['summary'] + " (ignore)")
            # update glitch stats
            self.__updateGlitchStats(glitch)

        # Now test for sequence errors within current data set
        # Take a copy of the first item in the list
        prevRtpPacket = self.rtpStream[0]

        # Test if the seq no hits 65535 it will wrap around to zero giving a false diff. Musn't interpret this as a glitch
        if prevRtpPacket.rtpSequenceNo == 65535:
            prevRtpPacket.rtpSequenceNo = -1

        # Iterate over the the remainder of the list (starting at index 1 to the end '-1')
        for rtpPacket in self.rtpStream[1:]:
            # Test if the seq no hits 65535 it will wrap around to zero giving a false diff. Musn't interpret this as a glitch
            if prevRtpPacket.rtpSequenceNo == 65535:
                prevRtpPacket.rtpSequenceNo = -1

            # Test sequence no of current packet against previous packet
            if rtpPacket.rtpSequenceNo != (prevRtpPacket.rtpSequenceNo + 1):

                # Capture packets either side of the 'hole' and store them in the event list
                # Create an object representing the glitch
                glitch = Glitch(self.__stats, prevRtpPacket, rtpPacket)

                # Check to see if this glitch is significant enough to be considered an event
                if glitch.packetsLost > self.__stats["glitch_Event_Trigger_Threshold_packets"]:
                    # Take timestamp of most recent glitch
                    self.__stats["glitch_most_recent_timestamp"] = datetime.datetime.now()
                    # Add the latest glitch to the evenList[]
                    self.__eventList.append(glitch)
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                    # Post a message
                    Utils.Message.addMessage(glitch.getSummary(includeStreamSyncSourceID=False)['summary'])
                else:
                    Utils.Message.addMessage(glitch.getSummary(includeStreamSyncSourceID=False)['summary'] + " (ignore)")

                # update glitch stats
                self.__updateGlitchStats(glitch)

            # Store current rtp packet for the next iteration around the loop
            prevRtpPacket = rtpPacket


        if self.__stats["glitch_counter_total_glitches"] > 1:
            # Calculate mean of new and prev value
            self.__stats["glitch_mean_time_between_glitches"] = \
                (self.sumOfTimeElapsedSinceLastGlitch + self.__stats["glitch_time_elapsed_since_last_glitch"]) / \
                self.__stats["glitch_counter_total_glitches"]

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
                self.updateTraceRouteHopsList(hopNo, noOfHops, isptestHeaderData[4:])
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
            isptestHeaderData = struct.unpack("!HBBBBBBB", isptestHeaderDataStruct)
            # Utils.Message.addMessage("INFO: Decoded header: " + str(isptestHeaderData) + ", " + str(isptestHeaderDataFriendlyName))
            # Check to see if we've managed to unpack the data
            if len(isptestHeaderData) > 0:
                # Check to see that if this a stream sent by an instance of isptest
                if isptestHeaderData[0] == RtpGenerator.getUniqueIDforISPTESTstreams():
                    # If so, make use the friendly name field to name this receive stream
                    self.__stats["stream_friendly_name"] = isptestHeaderDataFriendlyName
                    # And enable transmission of results back to sender
                    self.resultsTransmitter.transmitActiveFlag = True
                    # Utils.Message.addMessage(isptestHeaderDataFriendlyName)
                    # Now decode the messages contained within the isptest header
                    self.__parseIsptestHeaderData(isptestHeaderData)
                else:
                    # Otherwise, stream is not recognised, so disable transmission of results
                    Utils.Message.addMessage("DBUG:__RtpReceiveStream.__extractIsptestHeaderData(): Unable to decode stream, setting resultsTransmitter.transmitActiveFlag to False")
                    self.resultsTransmitter.transmitActiveFlag = False
                    pass
        except Exception as e:
            pass
            # Utils.Message.addMessage("DBUG: Decoded header: " + str(e) + str(self.rtpStream[0].isptestHeaderData))


    # Define a private calculation method that will run autonomously as a thread
    # This thread will
    def __calculateThread(self):
        Utils.Message.addMessage("DBUG: Starting __calculateThread with sync Source: " + \
                           str(self.__stats["stream_syncSource"]))

        # Prev timestamp doesn't exist yet as this is the first packet, so create datetime object with value 0
        lastReceivedRtpPacket = RtpData(0, 0, datetime.timedelta(), self.__stats["stream_syncSource"], "")

        # Start the loop timer (used to provide a 1sec interval)
        loopTimerStart = timer()
        # Timer used to detect loss of streams against an alarm threshold
        lossOfStreamTimerStart = timer()

        runningTotalPacketsPerSecond = 0
        runningTotalDataReceivedPerSecond = 0

        historicJitter = []
        sumOfJitter_1s = 0

        # Declare flags
        lossOfStreamFlag = True
        possibleLossOfStreamFlag = False

        # Constants. Used in calculation of received data rate
        UDP_HEADER_LENGTH_BYTES = 8
        RTP_HEADER_LENGTH_BYTES = 12

        # Endless loop whilst permitted by the flag
        while self.calculateThreadActiveFlag == True:

            # Lock the access mutex
            self.__accessRtpDataMutex.acquire()
            # Copy the contents of self.rtpStreamData into a temporary list so the accessRtpDataMutex can be released
            self.rtpStream = list(self.rtpStreamData)

            # Now we have a working copy of rtpStreamData[] we can clear the original source list
            del self.rtpStreamData[:]
            # Release the mutex
            self.__accessRtpDataMutex.release()

            # Take a timestamp in order to calculate the processor time required for packet analysis
            calculationStartTime = timer()
            # Lock self.__stats and self.__eventList mutexes
            self.__accessRtpStreamStatsMutex.acquire()
            self.__accessRtpStreamEventListMutex.acquire()
            # Test for new data
            if len(self.rtpStream) > 0:
                # Data is present
                # Take timestamp of the very first packet received of this rtpStream
                if self.__stats["packet_counter_received_total"] < 1:
                    self.__stats["packet_first_packet_received_timestamp"] = self.rtpStream[0].timestamp
                    # Add a StreamStarted event to the event list
                    streamStartedEvent = StreamStarted(self.__stats, self.rtpStream[0])
                    self.__eventList.append(streamStartedEvent)
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                    Utils.Message.addMessage(streamStartedEvent.getSummary(includeStreamSyncSourceID=False)['summary'])

                # Stream now being received so clear flag
                if lossOfStreamFlag == True:
                    # We're now receiving a stream, so clear alarm flag
                    lossOfStreamFlag = False

                if possibleLossOfStreamFlag == True:
                    possibleLossOfStreamFlag = False

                # Get copy of final packet of prev data set
                if self.__stats["packet_counter_received_total"] < 1:
                    # For the very first packet, take the prev packet to be that of the first packet received (to give a
                    # delta of zero, otherwise the delta will be the diff between 0 and today's date!
                    # prevRtpPacket=self.rtpStream[0]
                    lastReceivedRtpPacket = self.rtpStream[0]

                # Calculate and update per second and aggregate data counters
                for x in self.rtpStream:
                    # Per second counter
                    runningTotalDataReceivedPerSecond += x.payloadSize
                    # Total aggregate
                    self.__stats["packet_data_received_total_bytes"] += x.payloadSize

                # Calculate and update per second and aggregate packet counters
                # Per second counter
                runningTotalPacketsPerSecond += len(self.rtpStream)
                # Total aggregate
                self.__stats["packet_counter_received_total"] += len(self.rtpStream)

                # Calculate jitter ###############################################################
                self.__calculateJitter(lastReceivedRtpPacket)

                # Glitch Detection ###############################################################
                self.__detectGlitches(lastReceivedRtpPacket)

                # Capture most recent packet (last item of current data set) for next time around loop
                lastReceivedRtpPacket = self.rtpStream[-1]
                # Take timestamp of last packet in this batch
                self.__stats["packet_last_seen_received_timestamp"] = lastReceivedRtpPacket.timestamp

                # # Extract isptest header using data from first packet in this batch
                self.__extractIsptestHeaderData(self.rtpStream[0].isptestHeaderData)

            else:
                # No data, so set lossOfStreamFlag (unless it's already been set)
                # Check for changes and that we also have an active stream. If so, set the flag and add an event to the eventlist

                if possibleLossOfStreamFlag == False:
                    # Set the flag
                    possibleLossOfStreamFlag = True
                    # And start the lossOfStream Timer
                    lossOfStreamTimerStart = timer()

                if (timer() - lossOfStreamTimerStart) >= self.lossOfStreamAlarmThreshold_s \
                        and lossOfStreamFlag == False and self.__stats["packet_counter_received_total"] > 0:
                    # Set flag
                    lossOfStreamFlag = True
                    # Add event to the list (but only do this once)
                    streamLostEvent = StreamLost(self.__stats, lastReceivedRtpPacket)
                    self.__eventList.append(streamLostEvent)
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                    Utils.Message.addMessage(streamLostEvent.getSummary(includeStreamSyncSourceID=False)['summary'])
                    ######## POSSIBLY REVISIT THIS.....
                    # # Finally, reset min/max/range jitter values as they're corrupted by a loss of signal
                    # self.__stats["jitter_min_uS"] = 0
                    # self.__stats["jitter_max_uS"] = 0
                    # self.__stats["jitter_range_uS"] = 0
                    #
                    # # Think these should be cleared too, but there could be consequences
                    # self.__stats["jitter_instantaneous"] = 0
                    # self.__stats["packet_instantaneous_receive_period_uS"] = 0

            # Calculate elapsed since last glitch
            # But only if there has actually been a glitch in the past to measure against
            if self.__stats["glitch_counter_total_glitches"] > 0:
                # Calculate new value
                self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.datetime.now() - self.__stats[
                    "glitch_most_recent_timestamp"]

            # Calculate % packet loss
            if self.__stats["packet_counter_received_total"] > 0:
                totalExpectedPackets = self.__stats["packet_counter_received_total"] + \
                                       self.__stats["glitch_packets_lost_total_count"]
                # Guard against divide by zero errors
                if totalExpectedPackets > 0:
                    self.__stats["glitch_packets_lost_total_percent"] = \
                        self.__stats["glitch_packets_lost_total_count"] * 100 / totalExpectedPackets

            ################# 1 second timer
            if (timer() - loopTimerStart) >= 1:
                # Reset loop timer starting reference
                loopTimerStart = timer()
                # Increment seconds elapsed
                self.__stats["stream_time_elapsed_total"] += datetime.timedelta(seconds=1)
                # Take snapshots of running totals
                self.__stats["packet_counter_1S"] = runningTotalPacketsPerSecond
                # Calculate rx data rate including UDP and RTP headers
                bytesPerSecIncHeaders = runningTotalDataReceivedPerSecond + \
                                        runningTotalPacketsPerSecond * (UDP_HEADER_LENGTH_BYTES+RTP_HEADER_LENGTH_BYTES)
                self.__stats["packet_data_received_1S_bytes"] = bytesPerSecIncHeaders

                # Calculate self.__stats["packet_payload_size_mean_1S_bytes"]
                # Need to deduct 20 (8 bytes for the UDP header and 12 bytes for the RTP header)
                totalHeaderLength_bytes = UDP_HEADER_LENGTH_BYTES + RTP_HEADER_LENGTH_BYTES
                if self.__stats["packet_counter_1S"] > 0:
                    self.__stats["packet_payload_size_mean_1S_bytes"] = \
                        int(self.__stats["packet_data_received_1S_bytes"] / self.__stats["packet_counter_1S"]) -\
                            totalHeaderLength_bytes
                # Clear running totals
                runningTotalPacketsPerSecond = 0
                runningTotalDataReceivedPerSecond = 0

                # Calculate 1 second jitter
                if self.__stats["packet_counter_1S"] > 0:
                    self.__stats["jitter_mean_1S_uS"] = self.sumOfJitter_1s / self.__stats["packet_counter_1S"]


                # Reset self.sumOfJitter_1s
                self.sumOfJitter_1s = 0

                # Calculate 10s jitter moving average using a 10 element array of the prev 10 1s values
                # Add the latest 1s jitter value to the moving 10s jitter results array
                historicJitter.append(self.__stats["jitter_mean_1S_uS"])
                # Calculate a long-term jitter value by averaging all meanJitter_1s value over time elapsed
                sumOfJitter_1s += self.__stats["jitter_mean_1S_uS"]
                self.__stats["jitter_long_term_uS"] = sumOfJitter_1s / self.__stats["stream_time_elapsed_total"].seconds
                # Check that we have enough results (10s worth) to calculate the 10s value
                if len(historicJitter) > 10:
                    # Remove the oldest value
                    historicJitter.remove(historicJitter[0])
                    # Clear sum var prior to recalculation of mean
                    sumOfJitter_10s = 0
                    # Calculate mean of previous 10 1s jitter values
                    for x in historicJitter:
                        sumOfJitter_10s += x
                    self.__stats["jitter_mean_10S_uS"] = sumOfJitter_10s / len(historicJitter)

                # Dynamically modify POLL_INTERVAL based on a value of 10 times the Rx packet rate
                # This will ensure that self.rtpStream[] length never gets too large.
                # Otherwise, for high packet receive rates, the calculation time will become excessive
                # Wait a second, in order to know we're in a steady state
                if self.__stats["packet_instantaneous_receive_period_uS"] > 0 and \
                        self.__stats["stream_time_elapsed_total"].seconds > 1:
                    # self.__stats["calculate_thread_sampling_interval_S"] = 10.0 * \
                    #                                                        self.__stats[
                    #                                                            "packet_instantaneous_receive_period_uS"] / 1000000.0
                    ### NEW CODE TO HELP WITH CHOPPY LOSSY LINKS - OLD CODE USED TO CAUSE EXXCESSIVE CPU USAGE ###
                    ###ERROR:  File "/usr/local/Cellar/python/3.7.7/Frameworks/Python.framework/Versions/3.7/lib/python3.7/threading.py",$
                    #     self._target(*self._args, **self._kwargs)
                #   File "/Volumes/Transcend/Dropbox (BBC)/Software_Dev/Python/isptest/RtpStreams.py", line 1470, in __calcula$
                #     time.sleep(self.__stats["calculate_thread_sampling_interval_S"])
                # ValueError: sleep length must be non-negative


                    # snapshot the previous timing interval
                    oldSamplingRateInterval = self.__stats["calculate_thread_sampling_interval_S"]
                    # Calculate the current timing interval based on the current rate of incoming packets
                    newSamplingRateInterval = 10.0 *self.__stats["packet_instantaneous_receive_period_uS"] / 1000000.0
                    # If the timing interval has to be reduced, apply the change immediately
                    if newSamplingRateInterval < oldSamplingRateInterval:
                        self.__stats["calculate_thread_sampling_interval_S"] = newSamplingRateInterval
                    else:
                        # If the timing interval can be increased, apply the change more slowly
                        diff = newSamplingRateInterval - oldSamplingRateInterval

                        self.__stats["calculate_thread_sampling_interval_S"] += 0.2 * diff

                # Utils.Message.addMessage("sampling interval " + str(self.__stats["calculate_thread_sampling_interval_S"])+\
                #                          " Len " + str(len(self.rtpStream)))
                ######### Now calculate moving glitch counters by iterating over the self.movingGlitchCounters array
                # firstly recalculate, then generate stats keys automatically for any moving totals counters
                # within self.movingGlitchCounters
                for x in self.movingGlitchCounters:
                    # Force the moving counters to increment their timers and recalculate totals
                    x.recalculate()
                    name, movingTotal, events = x.getResults()
                    # Dynamically create new stats keys using the name field of the moving glitch counter
                    self.__stats[name] = movingTotal
                    self.__stats[name + "_events"] = events

                ######### Now housekeep
                # Purge __eventList[] to remove the oldest events
                self.__houseKeepEventList()

                # Check to see if this is a truly dead receive stream. If so, auto generate and save a stream report,
                # and kill the associated this calculateThread and corresponding ResultsTransmitter.__resultsTransmitterThread.
                #  Finally, remove this RtpStream object from the dictionary
                try:
                    if (datetime.datetime.now() - self.__stats["packet_last_seen_received_timestamp"]) > \
                            datetime.timedelta(seconds=self.streamIsDeadThreshold_s):
                        # Set the 'to be deleted' flag
                        self.believedDeadFlag = True


                except Exception as e:
                    Utils.Message.addMessage("ERR: RtpStream.__calc..Thread. Testing for dead receive stream: " + str(e))


            # Calculate how long it has taken for the stats analysis to have been performed
            calculationEndTime = timer()
            # Take the calculation time in microseconds and combine with the period between
            # packets arriving multiplied by the no of packets in this batch of rtpStream
            # to work out how much processor headroom there is (as a ratio of times).
            # If the total calculation time for rtpStream[] is > than the gap between packets
            # arriving then the the processor can't keep up, so generate an event
            # This is to guard against false-positives
            # Calculate calculationDuration (in uS)
            #   the %1 throws away the whole number part, *1000000 converts from s to uS
            self.__stats["calculate_thread_calculation_duration_uS"] = \
                ((calculationEndTime - calculationStartTime) % 1) * 1000000

            if len(self.rtpStream) > 0 and self.__stats["packet_instantaneous_receive_period_uS"] > 0:
                # Calculate processorUtilisationPercent. All time values in uS
                self.__stats["stream_processor_utilisation_percent"] = \
                    self.__stats["calculate_thread_calculation_duration_uS"] * 100.0 / (
                            self.__stats["packet_instantaneous_receive_period_uS"] * len(self.rtpStream))
            else:
                self.__stats["stream_processor_utilisation_percent"] = 0

            # If the CPU is >99% utilised, add event to the list (but only do this once)
            if self.__stats["stream_processor_utilisation_percent"] > 99:
                processorOverloadEvent = ProcessorOverload(self.__stats, lastReceivedRtpPacket)
                # Check to see if processorOverloadEvent Event creation is enabled
                if Registry.allowProcessorOverloadEventGeneration:
                    # if so, add the event
                    self.__eventList.append(processorOverloadEvent)
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                Utils.Message.addMessage(processorOverloadEvent.getSummary(includeStreamSyncSourceID=False)['summary'])
                Utils.Message.addMessage("["+ str(self.__stats["stream_syncSource"]) +"][" + \
                                         str(self.__stats["stream_friendly_name"]).rstrip() +
                                         "] Bursty incoming data " + str(len(self.rtpStream)) + " packets")



            # Unlock  self.__stats and self.__eventList mutexes
            self.__accessRtpStreamStatsMutex.release()
            self.__accessRtpStreamEventListMutex.release()

            # Empty the self.rtpStream list
            del self.rtpStream

            # Now test self.believedDeadFlag, and if set, auto generate and save areport to disk, and
            # kill the RtpReceiveStream
            if self.believedDeadFlag == True:
                Utils.Message.addMessage("Stream " + str(self.__stats["stream_syncSource"]) + \
                                   "(" + str(self.__stats["stream_friendly_name"]).rstrip() + \
                                   ") believed dead, removing from list")

                # Generate and save a report
                # Retrieve the auto-generated filename
                _filename = self.createFilenameForReportExport()
                # Write a report to disk
                self.writeReportToDisk(fileName=_filename)
                # Kill itself
                self.killStream()

            time.sleep(self.__stats["calculate_thread_sampling_interval_S"])

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
    def __houseKeepEventList(self):
        # Check size of self.__eventList[]
        noOfMessagesToPurge = len(self.__eventList) - self.historicEventsLimit
        if noOfMessagesToPurge > 0:
            # Remove first x events
            # oldSize = len(self.__eventList)
            del self.__eventList[:noOfMessagesToPurge]
            # newSize = len(self.__eventList)
            # Utils.Message.addMessage("DBUG: __houseKeepEventList() "+str(noOfMessagesToPurge)+
            #                    " events removed"+str(oldSize)+">>"+str(newSize))

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
    def addData(self, rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData):
        # Create a new rtp data object to hold the rtp packet data
        newData = RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource, isptestHeaderData)

        # NOW ADD DATA TO A LIST

        # Lock the access mutex
        self.__accessRtpDataMutex.acquire()
        # Add the  RtpData object containing the latest packet info, to the rtpStreamData[] list
        self.rtpStreamData.append(newData)
        # Release the mutex
        self.__accessRtpDataMutex.release()
        # Now we've added the newData object to the list rtpStreamData[] we cab delete the newData object
        del newData

# An object that will transmit stream results back from the receiving end to to the sender
# It is designed as a counterpart to class ResultsReceiver
# Note. This will reply from the same UDP binding as used in main() socket.recvfrom
class ResultsTransmitter(object):
    def __init__(self, rtpStream):
        self.parentRtpRxStream = rtpStream
        self.udpSocket = 0
        self.destAddr = 0
        self.destPort = 0
        self.syncSource = 0
        self.friendlyName = ""
        self.threadActiveFlag = True # Used to control the lifespan of __resultsTransmitterThread
        self.transmitActiveFlag = False  # Used to enable/disable transmit of UDP packets
                                    # For RTP stream sources not identified as being from isptest (eg an NTT), this will
                                    # inhibit needless reverse traffic
                                    # At start-up, inhibit tx traffic by default.
                                    # The corresponding RtpReceiveStream.__calculateThread() will enable it,
                                    # if approproate

        self.sendtoErrorCounter = 0 # Count's the no. of socket.sendto() errors
        self.sendtoErrorCounterThreshold = 10 # No of consecutive socket.sendto() errors that the thread will
                                            # tolerate before it gives up

        # Get the destination addr and src port from the supplied rtpStream object
        self.syncSource, self.destAddr, self.destPort, self.friendlyName =\
            self.parentRtpRxStream.getRTPStreamID()

        # Start the transmitter thread
        self.resultsTransmitterThread = threading.Thread(target=self.__resultsTransmitterThread, args=())
        self.resultsTransmitterThread.daemon = True
        self.resultsTransmitterThread.setName(str(self.syncSource) + ":ResultsTransmitter")
        self.resultsTransmitterThread.start()

    def kill(self):
        # Forces the self.transmitterActiveFlag to False which will cause the __resultsTransmitterThread
        # to end
        self.threadActiveFlag = False


    def __resultsTransmitterThread(self):
        Utils.Message.addMessage("INFO: __resultsTransmitterThread started for stream: "+ str(self.syncSource))

        oldSocket = self.parentRtpRxStream.getSocket()
        # Utils.Message.addMessage("__resultsTransmitterThread. Initial socket" + str(id(oldSocket)))

        while self.threadActiveFlag:
            self.udpSocket = self.parentRtpRxStream.getSocket()
            # if oldSocket is not self.udpSocket:
            #     Utils.Message.addMessage("__resultsTransmitterThread. Socket changed to " + str(id(self.udpSocket)))
            #     oldSocket = self.udpSocket

            # Check that the the socket is a valid socket.socket object
            if type(self.udpSocket) == socket.socket:
                # Confirm that transmission is active
                if self.transmitActiveFlag == True:
                    # Utils.Message.addMessage("__resultsTransmitterThread. Current TX socket " + str(id(self.udpSocket)))
                    # Get the destination addr and src port from the supplied rtpStream object
                    self.syncSource, self.destAddr, self.destPort, self.friendlyName = \
                        self.parentRtpRxStream.getRTPStreamID()

                    try:
                        # We have a valid socket binding we can use, so transmit the data
                        # Use pickle to serialise the data we want to send
                        stats = self.parentRtpRxStream.getRtpStreamStats()

                        # Get the last 5 events for this stream
                        NO_OF_PREV_EVENTS_TO_SEND = 5
                        eventsList = self.parentRtpRxStream.getRTPStreamEventList(NO_OF_PREV_EVENTS_TO_SEND)

                        # Create a dictionary containing the stats and eventList data and pickle it (so it can be sent)

                        msg = {"stats": stats, "eventList": eventsList}
                        pickledMessage = pickle.dumps(msg,protocol=2)

                        # Set max safe UDP tx size to 576 (based on this:-
                        # https://www.corvil.com/kb/what-is-the-largest-safe-udp-packet-size-on-the-internet
                        MAX_UDP_TX_LENGTH = 512
                        # Split the message up
                        fragmentedMessage = Utils.fragmentString(pickledMessage, MAX_UDP_TX_LENGTH)
                        if len(fragmentedMessage) > 0:

                            # iterate over fragments and send
                            for fragment in fragmentedMessage:
                                # Pickle and send each fragment one at a time
                                txMessage = pickle.dumps(fragment,protocol=2)
                                # Utils.Message.addMessage("DBUG: tx'd: (" +str(len(txMessage)) + ") "+ txMessage)
                                self.udpSocket.sendto(txMessage, (self.destAddr, self.destPort))
                                # clear the socket.sendto() error counter
                                self.sendtoErrorCounter = 0
                        else:
                            Utils.Message.addMessage("DBUG:__resultsTransmitterThread  - fragmentedMessage[] is empty")

                    except Exception as e:
                        Utils.Message.addMessage("ERR:__resultsTransmitterThread sendto() socket id:" + str(id(self.udpSocket)) +", " + str(e))
                        # Test to see if we've exceeeded the no of tolerable socket errors
                        if self.sendtoErrorCounter >= self.sendtoErrorCounterThreshold:
                            Utils.Message.addMessage("__resultsTransmitterThread. socket.sendto() error threshold exceeded (" +
                                                     str(self.sendtoErrorCounterThreshold) +\
                                                        "). Killing object for stream: " + str(self.syncSource))
                            # Now kill the object itself
                            self.kill()

                else:
                    # Results transmission inhibited
                    pass
            else:
                Utils.Message.addMessage("ERR: __resultsTransmitterThread - invalid UDP socket?")
            time.sleep(0.5)

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
        self.__eventList = []

        # No of historic events to keep in memory (before housekeeping)
        self.historicEventsLimit = 50

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

    def updateEventsList(self, eventsList):
        # Will take a list of new events and append them to the existing eventsList list
        # NOTE: It won't check for duplicate entries. It will blindly just append to what's already there
        # Take control of the mutex
        self.__accessRtpStreamEventListMutex.acquire()
        # Append the new events list to the existing list
        self.__eventList.extend(eventsList)
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
    def houseKeepEventList(self):
        self.__accessRtpStreamEventListMutex.acquire()
        # Check size of self.__eventList[] and therefore no of events to purge
        noOfMessagesToPurge = len(self.__eventList) - self.historicEventsLimit
        if noOfMessagesToPurge > 0:
            # Remove first x events
            del self.__eventList[:noOfMessagesToPurge]
        self.__accessRtpStreamEventListMutex.release()


# Define an RTP Generator that can run autonomously as a thread
class RtpGenerator(object):
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
    ISPTEST_HEADER_SIZE = 19

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
        self.payloadLength = int(payloadLength)
        self.txCounter_bytes = 0
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

        self.isptestHeaderMessageIndex = 0 # Keeps track of which type of message we are sending in the header
        self.noOfMessageTypes = 4 # The current message types are:
                                    # 0 Traceroute
                                    # 1 private LAN Address of the local interface used for transmitting
                                    # 2 The 'public' destination address
                                    # 3 The current version of isptest

        self.uiInstance = uiInstance   # This allows access to the methods of the UI class
        self.minSleepTime = None
        self.maxSleepTime = None
        self.meanSleepTime = None
        self.minCalculationTime = None
        self.maxCalculationTime = None
        self.meanCalculationTime = None

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

        # # Test to see if a UDP source port was specified
        # if len(srcPort) > 0:
        #     # Test to see if the supplied value is an int
        #     try:
        #         # check to see whether srcPort is a valid UDP port choice (has to be >1024)
        #         if int(srcPort[0]) > 1024:
        #             self.UDP_TX_SRC_PORT = int(srcPort[0])
        #     except Exception as e:
        #         Utils.Message.addMessage("INFO: RtpGenerator.__init(): Invalid UDP source port."+str(srcPort)+", "+str(e))

        # Start the traffic generator thread
        self.rtpGeneratorThread = threading.Thread(target=self.__rtpGeneratorThread, args=())
        self.rtpGeneratorThread.daemon = False
        self.rtpGeneratorThread.setName(str(self.syncSourceIdentifier) + ":RtpGenerator")
        self.rtpGeneratorThread.start()

        # Start the traceroute thread
        self.tracerouteThread = threading.Thread(target=self.__tracerouteThread, args=())
        self.tracerouteThread.daemon = False
        self.tracerouteThread.setName(str(self.syncSourceIdentifier) + ":traceroute")
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
                'Calculation time mean': self.meanCalculationTime
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
        # Header currently consists of 19 bytes of data NOTE. This is defined in RtpGenerator.getIsptestHeaderSize():
        # [uniqueValue(David's birthday)(short, 2 bytes)
        # plus....
        # [byte1] Message type (0: Traceroute)
        # [byte2] Hop no
        # [byte3] Total no of hops
        # [byte4][byte5][byte6][byte7] Hop id address octets
        # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (1: SRC IP address (the local LAN address of the transmitting machine)
        #         # [byte2] src port (MSB)
        #         # [byte3] src port (LSB)
        #         # [byte4][byte5][byte6][byte7] local ip address octets
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (2: DST IP address) (the destination PUBLIC address that the transmitter is sending to)
        #         # [byte2] 0/not used
        #         # [byte3] 0/not used
        #         # [byte4][byte5][byte6][byte7] dest ip address octets
        #         # [friendlyName] 10 bytes

        # OR
        # [byte1] Message type (3: Transmitter isptest version no.
        #         # [byte2] major version no
        #         # [byte3] minor version no
        #         # [byte4][byte5][byte6][byte7] all 0/not used
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
                if len(tracerouteHopsList) > 0:
                    try:
                        messageData = [0 & 0xFF,  # Message type 0: traceroute
                                       self.tracerouteCarouselIndexNo & 0xFF,  # Traceroute Hop no
                                       len(tracerouteHopsList) & 0xFF,  # # Traceroute total no of hops
                                      tracerouteHopsList[self.tracerouteCarouselIndexNo][0] & 0xFF,  # IP address octet 1
                                      tracerouteHopsList[self.tracerouteCarouselIndexNo][1] & 0xFF,  # IP address octet 2
                                      tracerouteHopsList[self.tracerouteCarouselIndexNo][2] & 0xFF,  # IP address octet 3
                                      tracerouteHopsList[self.tracerouteCarouselIndexNo][3] & 0xFF]  # IP address octet 4
                        # Now increment the carousel index so that the next hop value will be transmitted the next time this
                        # method is called
                        self.tracerouteCarouselIndexNo += 1

                    except Exception as e:
                        Utils.Message.addMessage("DBUG: RtpGenerator.generateIsptestHeader():tracerouteHopsList[] " + str(e))
                else:
                    # Create a dummy traceroute message
                    messageData = [0 & 0xFF,  # Message type 0: traceroute
                                   0 & 0xFF,  # Traceroute Hop no
                                   0 & 0xFF,  # Traceroute total no of hops
                                   0 & 0xFF,  # IP address octet 1
                                   0 & 0xFF,  # IP address octet 2
                                   0 & 0xFF,  # IP address octet 3
                                   0 & 0xFF]  # IP address octet 4

                # Bounds check tracerouteCarouselIndexNo
                if self.tracerouteCarouselIndexNo > (len(tracerouteHopsList) - 1):
                    # Reset the carousel value
                    self.tracerouteCarouselIndexNo = 0

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
                                   int(localAddr[3]) & 0xFF]  # IP address octet 4
                except Exception as e:
                    messageData = [1 & 0xFF,  # Message type 0: traceroute
                                   0 & 0xFF,  # Top byte (MSB) of the source port
                                   0 & 0xFF,  # Bottom byte (LSB) of the source port
                                   0 & 0xFF,  # IP address octet 1
                                   0 & 0xFF,  # IP address octet 2
                                   0 & 0xFF,  # IP address octet 3
                                   0 & 0xFF]  # IP address octet 4
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
                                   int(destAddr[3]) & 0xFF]  # IP address octet 4
                except Exception as e:
                    messageData = [2 & 0xFF,  # Message type 2: destination addr
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # IP address octet 1
                                   0 & 0xFF,  # IP address octet 2
                                   0 & 0xFF,  # IP address octet 3
                                   0 & 0xFF]  # IP address octet 4
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
                                   0 & 0xFF]  # not used
                except Exception as e:
                    messageData = [3 & 0xFF,  # Message type 3: Destination addr
                                   0 & 0xFF,  # Major version no
                                   0 & 0xFF,  # Minor version no
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF,  # not used
                                   0 & 0xFF]  # not used
                    Utils.Message.addMessage("DBUG:RtpGenerator.generateIsptestHeader(): tx version info " + str(e))

            # Now That the message data list has been created, increment the message type index
            self.isptestHeaderMessageIndex += 1
            # Bounds check isptestHeaderMessageIndex
            if self.isptestHeaderMessageIndex >=self.noOfMessageTypes:
                self.isptestHeaderMessageIndex = 0


            # Now assemble the header
            header = struct.pack("!HBBBBBBB", uniqueValue, messageData[0], messageData[1], messageData[2], \
                                 messageData[3], messageData[4], messageData[5], messageData[6])

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

    def setTxRate(self, newTxRate_bps):
        # Specify Minimum tx rate 100kbps
        minimumRate=102400
        if newTxRate_bps < minimumRate:
            newTxRate_bps = minimumRate
        # Update instance variable
        self.txRate = newTxRate_bps
        # Calculates then set the new txPeriod for a given newTxRate_bps
        txPeriod = self.calculateTxPeriod(newTxRate_bps)
        self.txPeriod = txPeriod


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

    # This thread runs a 1 second timer and updates
    # self.elapsedTime

    # Controlled by:
    # self.enablePacketGeneration
    # self.timeToLive ==0
    # self.elapsedTime
    # self.txBps_1s, self.txActualTxRate_bps # Are these the same?

    # This thread collects time averaged values and performs housekeeping
    def __samplingThread(self):
        loopCounter =0
        # The tx bps counter is a 1 second moving average with 0.2 sec accuracy
        bpsCounterList = []
        # Snapshot current value
        prevTxCounter_Bytes = self.txCounter_bytes
        # Infinite loop
        while self.timeToLive != 0:
            # Take snapshot of current tx byte counter
            currentTxCounter_Bytes = self.txCounter_bytes
            # Append the latest bytes transmitted (during the last 0.2 seconds) to the list
            bpsCounterList.append(currentTxCounter_Bytes - prevTxCounter_Bytes)
            # If we have more than 5 historic samples, remove the oldest item from the list
            if len(bpsCounterList)>5:
                del bpsCounterList[0]
            # Store current value of currentTxCounter_Bytes for next time around the loop
            prevTxCounter_Bytes = currentTxCounter_Bytes


            # 1 second counter
            if loopCounter % 5 == 0:
                # 1 Second has elapsed
                # Calculate the actual tx bps by summing the bpsCounterList and converting bytes to bits
                bps = 0
                for x in bpsCounterList:
                    bps += x
                self.txActualTxRate_bps = bps * 8

                # Decrement timeToLive seconds counter but only if current value is +ve
                # A -ve value is used to denote 'live for ever'
                if self.timeToLive > 0:
                    self.timeToLive -= 1

            # Increment loop counter
            loopCounter += 1
            # Sleep for a fifth of a second
            time.sleep(0.2)

        Utils.Message.addMessage("RtpGenerator.samplingLoop() ending for stream " + str(self.syncSourceIdentifier))



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
            if rtpGeneratorInstance.minSleepTime is None:
                rtpGeneratorInstance.minSleepTime = sleepTime
            elif sleepTime < rtpGeneratorInstance.minSleepTime:
                # record new minimum
                rtpGeneratorInstance.minSleepTime = sleepTime

            if rtpGeneratorInstance.maxSleepTime is None:
                rtpGeneratorInstance.maxSleepTime = sleepTime
            elif sleepTime > rtpGeneratorInstance.maxSleepTime:
                # record new maximum
                rtpGeneratorInstance.maxSleepTime = sleepTime

            if rtpGeneratorInstance.meanSleepTime is None:
                rtpGeneratorInstance.meanSleepTime = sleepTime
            else:
                # Calculate mean
                rtpGeneratorInstance.meanSleepTime = (rtpGeneratorInstance.meanSleepTime + sleepTime) / 2.0

        # This utility method will update the stats relating to the time taken for the RtpGenerator thread to prepare
        # and transmit each rtp packet
        def updateCalculationTimeStats(rtpGeneratorInstance, calculationTime):
            if rtpGeneratorInstance.minCalculationTime is None:
                rtpGeneratorInstance.minCalculationTime = calculationTime
            elif calculationTime < rtpGeneratorInstance.minCalculationTime:
                rtpGeneratorInstance.minCalculationTime = calculationTime

            if rtpGeneratorInstance.maxCalculationTime is None:
                rtpGeneratorInstance.maxCalculationTime = calculationTime
            elif calculationTime > rtpGeneratorInstance.maxCalculationTime:
                rtpGeneratorInstance.maxCalculationTime = calculationTime

            if rtpGeneratorInstance.meanCalculationTime is None:
                rtpGeneratorInstance.meanCalculationTime = calculationTime
            else:
                rtpGeneratorInstance.meanCalculationTime = \
                    (rtpGeneratorInstance.meanCalculationTime + calculationTime) / 2.0

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
                    # Update tx bytes counter (taking packet headers into account)
                    rtpGeneratorInstance.txCounter_bytes += sentBytes

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
                    if prevTxPeriod != txPeriod:
                        # Reset the initial time reference
                        t = time.time()
                        # Reset the counter
                        count = 1
                        # Capture the latest txPeriod value
                        prevTxPeriod = txPeriod

                    yield max(t + count * txPeriod - time.time(), 0)

            # This is the infinite loop that actually transmits the rtp packet at an interval determined
            # by the tx period. The sleep period is determined by the calculateSleepPeriod() 'generator' function
            # Infinite loop until timeToLive == 0
            g = calculateSleepPeriod()
            while rtpGeneratorInstance.timeToLive != 0:
                # Get (dynamic) sleep interval. This should ensure that the next packet is sent at precisely the correct
                # time with any processing delays compensated for
                sleepTime = next(g)
                # sleep
                time.sleep(sleepTime)
                # start timer
                processingStartTime = timer()
                # send previously prepared packet
                sendPacket(rtpGeneratorInstance)
                # Prepare the next packet
                rtpGeneratorInstance.prepareNextRtpPacket()

                # Update sleepTime stats
                updateSleepTimeStats(rtpGeneratorInstance, sleepTime)

                # Stop calculation timer - calculate how long the packet preparation and transmission has taken
                calculationPeriod = timer() - processingStartTime
                # Update calculation time stats
                updateCalculationTimeStats(rtpGeneratorInstance, calculationPeriod)

        Utils.Message.addMessage("DBUG:New RtpGen thread. Thread starting")
        # Prepare the first rtp packet to be sent
        self.prepareNextRtpPacket()
        # Calculate tx period required to provide supplied txRate for a given stringLength
        # Note: txPeriod = self.payloadLength * 8.0 / self.txRate
        self.txPeriod = self.calculateTxPeriod(self.txRate)

        # Calculate the maximum intentional timing deviation to be add/subtracted from txPeriod if jitter is enabled
        maxDeviation = self.txPeriod * Registry.simulatedJitterPercent / 100

        try:
            # Create a UDP socket for UDP transmission and reception
            self.__createUDPSocket()

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



    def __oldrtpGeneratorThread(self):
        # Constants. Used in calculation of transmitted data rate
        UDP_HEADER_LENGTH_BYTES = 8
        RTP_HEADER_LENGTH_BYTES = 12

        # Generate payload (consisting of a random string)
        self.generatePayload()
        # Attempt to create UDP socket
        try:
            self.udpTxSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP
            # Set a timeout of 1 second (required because we will use recvfrom() in the corresponding
            # ResultsReceiver object (which will use this same socket, but to receive)
            self.udpTxSocket.settimeout(1)
            # Utils.Message.addMessage(str(self.udpTxSocket.get))
            # If a UDP source port has been specified, use it
            if self.UDP_TX_SRC_PORT >1024:
                # Bind to the socket, allows you to specify the source port
                try:
                    self.udpTxSocket.bind(('0.0.0.0',int(self.UDP_TX_SRC_PORT)))
                except Exception as e:
                    Utils.Message.addMessage("ERR: RtpGenerator.__rtpGeneratorThread. self.udpTxSocket.bind (User supplied source port). "+ str(e))
            else:
                # Let the OS determine the source port
                self.udpTxSocket.bind(('0.0.0.0', 0))
                self.UDP_TX_SRC_PORT = self.udpTxSocket.getsockname()[1]
        except Exception as e:
            Utils.Message.addMessage("ERR:\x1B[31__rtpGeneratorThread() socket.socket(): Cannot create socket. Please quit now\x1B[0m" + self.UDP_TX_IP + ":" + \
                               str(self.UDP_TX_PORT) + ", " + str(e))
            time.sleep(2)

        msg = "INFO: TX stream thread started. Sending to " + self.UDP_TX_IP + ":" + str(self.UDP_TX_PORT) + \
              ", " + str(self.txRate) + "bps, Length:" + str(self.payloadLength) +" bytes, src Port: "+ str(self.UDP_TX_SRC_PORT)
        Utils.Message.addMessage(msg)

        rtpParams = 0b01000000
        rtpPayloadType = 0b00000000
        rtpSequenceNo = 0

        # Calculate tx period required to provide supplied txRate for a given stringLength
        # Note: This is an estimate because time.sleep() is inherently unreliable so we have
        # to recalculate once the generator is running by averaging over a 1 sec period
        # txPeriod = self.payloadLength * 8.0 / self.txRate
        self.txPeriod = self.calculateTxPeriod(self.txRate)

        jitterPercentage = 50
        maxDeviation = self.txPeriod * jitterPercentage / 100

        # start elapsed timer
        startTime = timer()

        while True:
            # Start an execution timer (if we know the time required to construct the packet we can deduct this from the
            # txPeriod sleep time which should, in theory, reduce the jitter of the generator
            calculationStartTime = timer()

            # Create a 32 bit timestamp (needs truncating to 32 bits before passing to struct.pack)
            # 0xFFFFFFFF is 32 '1's, so the '&' operation will throw away MSBs larger than this
            rtpTimestamp = int(datetime.datetime.now().strftime("%H%M%S%f")) & 0xFFFFFFFF

            # Construct 12 byte header
            # B: unsigned char, H: unsigned short (2 bytes), L: unsigned long (4 bytes)
            txRtpHeader = struct.pack("!BBHLL", rtpParams, rtpPayloadType, rtpSequenceNo, rtpTimestamp,
                                      self.syncSourceIdentifier)
            # Force an update of the isptest header
            self.generateIsptestHeader()
            # Now create the actual message to be send across the wire
            self.payloadMutex.acquire()
            MESSAGE = txRtpHeader + self.isptestHeader + self.rtpPayload.encode('ascii')
            self.payloadMutex.release()

            # If all tx flags are set then transmit the rtp packet
            if self.enablePacketGeneration == True and self.packetsToSkip < 1:
                try:
                    self.udpTxSocket.sendto(MESSAGE, (self.UDP_TX_IP, self.UDP_TX_PORT))
                    # Update tx bytes counter (taking packet headers into account)
                    self.txCounter_bytes += self.payloadLength + UDP_HEADER_LENGTH_BYTES + RTP_HEADER_LENGTH_BYTES
                    # Update tx bps data counter (*8 converts bytes to bits)
                    self.txBps_1s += (self.payloadLength + UDP_HEADER_LENGTH_BYTES + RTP_HEADER_LENGTH_BYTES) * 8

                except Exception as e:
                    Utils.Message.addMessage("\x1B[31m__rtpGenerator() self.udpTxSocket.sendto(). Exiting. \x1B[0m " + str(e))
                    time.sleep(1)  # Throttle rate of error messages from this thread
            else:
                # Decrement self.packetsToSkip. Once this var reaches zero, packet generation will resume
                self.packetsToSkip -= 1

            ###########
            # Increment rtp sequence number for next iteration of the loop
            rtpSequenceNo += 1
            # Seq no is only a 16 bit value, so reset at max value (65535)
            if rtpSequenceNo > 65535:
                rtpSequenceNo = 0
                Utils.Message.addMessage("INFO: rtpGenerator. " + str(self.syncSourceIdentifier) + " Seq no wrapping to zero")
            # If flag set, generate random delay centred around self.txPeriod (0.01 = 10mS period)
            if self.jitterGenerationFlag == True:
                jitter = random.uniform(-1 * maxDeviation, maxDeviation)
            else:
                jitter = 0

            # Calculate (inevitable) error in tx rate (bps)
            # If there is an error between the desired tx speed and the actual tx speed (due to timing inaccuracies of the time.sleep() command)
            # dynamically modify the self.txPeriod to actually generate the desired rate
            # 1 second timer

            # Has 1 second elapsed?
            if (timer() - startTime) >= 1 and self.enablePacketGeneration == True:
                # Reset elapsed timer (for 1 second timer)
                startTime = timer()

                # Increment elapsed time counter by 1 second
                self.elapsedTime += datetime.timedelta(seconds=1)

                # Test actual tx rate (averaged over a second) against 99% of desired tx rate
                if self.txBps_1s < (0.99 * self.txRate):
                    # Data not being sent fast enough, so reduce txPeriod time
                    # Measure difference between desired bps tx rate and actual bps tx rate
                    txRateError = self.txRate - self.txBps_1s
                    # Convert the difference a fraction by which will modify txPeriod
                    errorFactor = (txRateError * 1.0 / self.txRate)
                    # Modify txPeriod to compensate for error
                    # Prevent overshoots of the desired rate, only reduce self.txPeriod by 'half' the error amount in one go
                    self.txPeriod -= self.txPeriod * (errorFactor / 2.0)
                    # Utils.Message.addMessage("DBUG: Compensating for timing error - Actual txData rate too low. Desired tx rate:" +
                    #                    str(self.txRate) + ", Actual tx rate:" + str(self.txBps_1s))
                # Test for overshoots
                if self.txBps_1s > (1.05 * self.txRate):
                    # Data being sent too fast, so need to reduce
                    # Measure difference between desired bps tx rate and actual bps tx rate
                    txRateError = self.txBps_1s - self.txRate
                    # Convert the difference a fraction by which will modify txPeriod
                    errorFactor = (txRateError * 1.0 / self.txRate)
                    # Reduce by 'half' the errorFactor (per adjustment) to prevent hunting
                    self.txPeriod += self.txPeriod * (errorFactor / 2.0)
                    # Utils.Message.addMessage("DBUG: Data rate too high. Reducing.)")

                # Take copy of current actual tx rate
                self.txActualTxRate_bps = self.txBps_1s
                # Utils.Message.addMessage("DBUG: txActualTxRate_bps: "+str(bToMb((self.txActualTxRate_bps))))
                # Clear counter
                self.txBps_1s = 0

                # Decrement timeToLive seconds counter but only if current value is +ve
                # A -ve value is used to denote 'live for ever'
                if self.timeToLive > 0:
                    self.timeToLive -= 1

            # The calculation time will be deducted from the sleep time, which should make the generator
            # output less jittery (because the calculation time is taken into account)
            calculationPeriod = timer() - calculationStartTime

            compensatedTxPeriod = self.txPeriod + jitter - calculationPeriod
            # Have to guard against a negative time value
            if compensatedTxPeriod > 0:
                # Sleep between packet transmission
                time.sleep(compensatedTxPeriod)
            else:
                # print "__rtpGenerator() - non-positive compensatedTxPeriod value",compensatedTxPeriod,"\r"
                pass

            # Now housekeep the associated rtpTxStreamResults object for this stream
            # Check to see that rtpTxStreamResultsDict contains this stream objects
            if self.syncSourceIdentifier in self.rtpTxStreamResultsDict:
                try:
                    # Get a handle on the rtpTxStreamResults object
                    rtpTxStreamResults = self.rtpTxStreamResultsDict[self.syncSourceIdentifier]
                    if type(rtpTxStreamResults) == RtpStreamResults:
                        # Invoke the housekeeping method to purge any really old events
                        rtpTxStreamResults.houseKeepEventList()
                except Exception as e:
                    Utils.Message.addMessage("ERR: __rtpGenerator rtpTxStreamResults.houseKeepEventList(): " + str(e))


            # If timeToLive has decremented to zero, break out of the while loop (an therefore kill the object)
            if self.timeToLive ==0:

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
                        Utils.Message.addMessage("ERR: RtpGenerator.killStream() rtpTxStreamResults.generateReport(): " + str(e))
                self.rtpTxStreamResultsDictMutex.release()

                # Now break out of the while loop to end the thread finally kill the object.
                break

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

    # Define a seperate thread to run a traceroute
    def __tracerouteThread(self):
        # Specify initial hopNo
        hopNo = 0
        # Run indefinitely unless timeToLive falls to zero
        replies = [] # Used to keep track of replies that are 'None'
        while self.timeToLive != 0:
            # Create a UDP packet with an ever incrementing TTL
            # In the first instance, a packet will be sent to the dest port specified by the stream
            # However, should this elicit no reply, a second attempt will be made using the standard traceroute port 33434
            # dst=self.UDP_TX_IP
            # self.UDP_TX_PORT
            # dport=33434   # This seems to be the standard port for traceroute according to man traceroute
            # dst="8.8.8.8"
            # Get local working copy of self.tracerouteHopsList
            tracerouteHopsList = self.getTraceRouteHopsList(trimEndOfList=False)
            pkt = IP(dst=self.UDP_TX_IP, ttl=hopNo + 1) / UDP(dport=self.UDP_TX_PORT)
            # pkt = IP(dst=self.UDP_TX_IP, ttl=hopNo + 1) / UDP(dport=33434)
            pkt_fallback = IP(dst=self.UDP_TX_IP, ttl=hopNo + 1) / UDP(dport=33434)
            # Send the packet and get a reply (with a timeout of 1 second)
            try:
                reply = sr1(pkt, verbose=0, timeout=1)
                # If timeToLive has decremented to zero, break out of the while loop (an therefore kill the object)
                if self.timeToLive == 0:
                    break

                if reply is None:
                    # No reply from upstream router or sr1() timed out on second attempt, using standard port
                    # This could be because the upstream router is set to not return icmp reports
                    # Retry the same test, but using the standard traceroute port

                    reply = sr1(pkt_fallback, verbose=0, timeout=1)
                # If reply is still None
                if reply is None:
                    hopAddr = [0,0,0,0]
                    # Utils.Message.addMessage("No response or timeout:" + str(hopNo))

                    try:
                        # Attempt to update this list location
                        tracerouteHopsList[hopNo] = hopAddr
                    except:
                        # If it fails, it's because the list location doesn't exist yet
                        tracerouteHopsList.append(hopAddr)
                    # increment hopNo
                    hopNo += 1
                else:
                    # Split the reply source ip address into a list of octets
                    replyFromAddr = str(reply.src).split('.')
                    # Create the IP address as a list of Octets
                    hopAddr = [int(replyFromAddr[0]),int(replyFromAddr[1]),int(replyFromAddr[2]),int(replyFromAddr[3])]
                    # Utils.Message.addMessage(str(hopNo) + ":" + str(hopAddr) + ", " + str(reply.type))
                    # Now determine where we are, within the traceroute

                    if reply.type == 3 or reply.src == self.UDP_TX_IP:
                    #(type 3 equates to port unreachable. Only the destination host knows about the port.
                    # Ergo, the destination IP address must have been reached
                    # Note: The Scapy 'type' code maps to the ICMP 'code'

                        # We've reached our destination. So append the final address to the traceroute hops list
                        # Utils.Message.addMessage("DBUG: dest reached. hopNo:" + str(hopNo))
                        try:
                            # Attempt to update this list location
                            tracerouteHopsList[hopNo] = hopAddr
                            # Now trim off any old hops beyond this point of the list
                            if len(tracerouteHopsList) > (hopNo + 1):
                                tracerouteHopsList = tracerouteHopsList[:hopNo+1]
                        except:
                            # If it fails, it's because the list location doesn't exist yet, so add it
                            # Utils.Message.addMessage("appending")
                            tracerouteHopsList.append(hopAddr)
                        # Reset hopNo to restart the traceroute
                        # Utils.Message.addMessage("Resetting hopNo")
                        hopNo = 0
                    else:
                        # Utils.Message.addMessage("In the middle hopNo:" + str(hopNo))
                        # We're in the middle somewhere
                        try:
                            # Attempt to update this list location
                            tracerouteHopsList[hopNo] = hopAddr
                        except:
                            # If it fails, it's because the list location doesn't exist yet, so add it
                            tracerouteHopsList.append(hopAddr)
                        # Increment the TTL of the packet by incrementing hopNo
                        hopNo += 1

                # Pass the most recent hopAddress to the Whois cache so that the address can be queried in the
                # background, for later use
                hopAddrAsString = str(hopAddr[0]) + "." + str(hopAddr[1]) + "." + str(hopAddr[2]) + "." + str(hopAddr[3])
                Utils.WhoisResolver.queryWhoisCache(hopAddrAsString)

                # Now check for five 'None' replies in a row
                maxNoOfNoResponse = 5
                # Append reply to replies[]
                replies.append(reply)
                # Check last five results of replies[]. If last 5 '-5' in a row are None, assume a dead end
                if all(response is None for response in replies[(-1 * maxNoOfNoResponse):]):
                    # Utils.Message.addMessage("5 None replies in a row, assuming dead traceroute")

                    # Trim any remaining hop entries beyond the last hop no.
                    tracerouteHopsList = tracerouteHopsList[:hopNo]
                    # Reset hopNo to restart the traceroute
                    hopNo = 0
                if hopNo >= Registry.tracerouteMaxHops:
                    # Reset the hopNo to 0 for the next time around the loop
                    hopNo = 0
                # Utils.Message.addMessage("Hops:" + str(len(tracerouteHopsList)) + ", " + str(tracerouteHopsList))

            except Exception as e:
                Utils.Message.addMessage("ERR: RtpGenerator.__tracerouteThread.sr1() " + str(e))
                Utils.Message.addMessage("\033[31mHint: Run as sudo to enable traceroute functionality")
                # If a UI instance (user interface) reference was supplied, display an error message on the UI
                maxWidth = 60
                errorText = "Insufficient rights to enable traceroute functionality.".center(maxWidth) +\
                    "\n\n" + "isptest TRANSMITTER will continue to run, but without traceroute.".center(maxWidth) +\
                    "\n" + "To enable this function, exit the app and run as sudo ".center(maxWidth) + \
                    "\n" + "(or as Administrator, if running on Windows)".center(maxWidth) + \
                    "\n\n" + "<Press any key to continue>".center(maxWidth)
                if self.uiInstance is not None:
                    try:
                        self.uiInstance.showErrorDialogue("Traceroute error", errorText)
                    except Exception as e:
                        Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread: display error message on UI " +\
                                                 str(e))
                # Now break out of while loop
                break
            finally:
                # copy the working tracerouteHopsList back into the instance variable version
                self.tracerouteHopsListMutex.acquire()
                self.tracerouteHopsList = tracerouteHopsList
                self.tracerouteHopsListMutex.release()

            # Now update the tracerouteHops list in the corresponding RtpStreamResults object (if it exists)
            # Note: This is not transmitted by the receiver (because it's not part of the stats dictionary)
            # So has to be updated manually here
            try:
                # get the instance of the corresponding RtpStreamResults object
                rtpStreamResults = self.rtpTxStreamResultsDict[self.syncSourceIdentifier]
                # Copy the entire RtpGenerator tracerouteHops list into the rtpStreamResults tracerouteHops list
                rtpStreamResults.setTraceRouteHopsList(self.getTraceRouteHopsList())

            except Exception as e:
                # Utils.Message.addMessage("DBUG:RtpGenerator.__tracerouteThread() update RtpStreamResults tracerouteHopList " + str(e))
                pass
            time.sleep(0.5)
        Utils.Message.addMessage("DBUG:__tracerouteThread ending for stream " + str(self.syncSourceIdentifier))

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
                                Utils.Message.addMessage("ERR: __resultsReceiverThread(pickle.loads(all fragments)): "+str(e))

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
                            rtpStreamResults = self.rtpTxStreamResultsDict[stats["stream_syncSource"]]
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

                                    # Check if the latest item in the new list is more recent than the last item of the known list
                                    if lastEventNoInNewList > lastKnownEventNo:
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
