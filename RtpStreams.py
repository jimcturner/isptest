#!/usr/bin/env python
# Defines RtpStream objects for use by isptest
# James Turner 20/2/20
import socket
import os
# import binascii
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

# Additonal libraries required (of my own making)
from Utils import Message, dtstrft, removeRtpStreamFromDict, addRtpStreamToDict, fragmentString


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

    @abstractmethod
    def getSummary(self):
        optionalFields =""
        summary = "[" + str(self.stats["stream_syncSource"]) + "]" + \
                  "[" + str(self.eventNo) + "] " + self.type + optionalFields
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

    def getSummary(self):
        # Returns a dictionary containing a timestamp and a concise description of the event as a string
        optionalFields = ", first rtp sequence no:"+str(self.firstPacketReceived.rtpSequenceNo)
        summary = "[" + str(self.stats["stream_syncSource"]) + "]" + \
                  "[" + str(self.eventNo) + "] " + self.type + optionalFields
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

    def getSummary(self):
        optionalFields = ", Most recent rtp sequence no: "+str(self.lastPacketReceived.rtpSequenceNo)
        summary = "[" + str(self.stats["stream_syncSource"]) + "]" + \
                  "[" + str(self.eventNo) + "] " + self.type + optionalFields
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
    def getSummary(self):
        optionalFields = " "+str(int(self.stats["jitter_mean_1S_uS"])) + "/" + str(int(self.stats["jitter_long_term_uS"])) + "uS"
        summary = "[" + str(self.stats["stream_syncSource"]) + "]" + \
                  "[" + str(self.eventNo) + "] " + self.type + optionalFields
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

    def getSummary(self):
        optionalFields =  " "+str(int(self.stats["stream_processor_utilisation_percent"])) + "%"
        summary = "[" + str(self.stats["stream_syncSource"]) + "]" + \
                  "[" + str(self.eventNo) + "] " + self.type + optionalFields
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

    def getSummary(self):
        optionalFields = " " + dtstrft(self.glitchLength) + ", " + str(self.packetsLost) + " lost. "+\
                "Exptd." +str(self.expectedSequenceNo)+", Got."+ str(self.actualReceivedSequenceNo)
        summary = "[" + str(self.stats["stream_syncSource"]) + "]" + \
                  "[" + str(self.eventNo) + "] " + self.type + optionalFields
        data = {'timeCreated': self.timeCreated, 'summary': summary}
        return data

    def getCSV(self):
        # returns a CSV formatted string suitable for import into Excel
        optionalFields = "Duration,"+str(self.glitchLength)+", packet(s) lost,"+str(self.packetsLost)+\
            ",Expected seq no"+str(self.expectedSequenceNo)+",Actual received seq no,"+ str(self.actualReceivedSequenceNo)
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
    def __init__(self, rtpSequenceNo, payloadSize, timestamp, syncSource):
        self.rtpSequenceNo = rtpSequenceNo
        self.payloadSize = payloadSize
        self.timestamp = timestamp
        self.syncSource = syncSource
        # timeDelta will store the timestamp diff between this and the previous packet
        self.timeDelta = 0
        # jitter will store the diff between the timeDelta of this and the prev packet
        self.jitter = 0

# Define a class to represent a flow of received rtp packets (and associated stats)
class RtpReceiveStream(object):
    # Constructor method.
    # The RtpReceiveStream object should be created with a unique id no
    # (for instance the rtp sync-source value would be perfect)
    def __init__(self, syncSource, srcAddress, srcPort, rxAddress, rxPort, glitchEventTriggerThreshold, rxSocket, rtpRxStreamsDict, rtpRxStreamsDictMutex):

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
        Message.addMessage("INFO: RtpReceiveStream:: Creating RtpReceiveStream with syncSource: " + str(self.__stats["stream_syncSource"]))

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
        self.maxNameLength = 10
        # self.__stats["stream_friendly_name"] = " " * self.maxNameLength
        # On init, set friendly name to be the same as the sync source ID
        self.__stats["stream_friendly_name"] = \
            str(str(self.__stats["stream_syncSource"])[0:self.maxNameLength]).ljust(self.maxNameLength, " ")

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

        # Initially, __CalculateThread loop will execute every 10mS (but will then be modified dynamically
        # based on the packet Rx period)
        self.DEFAULT_CALCULATE_THREAD_SAMPLING_INTERVAL = 0.01
        self.__stats["calculate_thread_sampling_interval_S"] = self.DEFAULT_CALCULATE_THREAD_SAMPLING_INTERVAL

        # Amount of time to elapse before a lossOfStream alarm event is triggered
        self.lossOfStreamAlarmThreshold_s = 1

        # Amount of time to elapse before a stream is believed completely dead (and automatically
        # destroyed)
        self.streamIsDeadThreshold_s = 30

        # Create a __calculateThread
        self.calculateThreadActiveFlag = True # Used as a signal to shut down the calculateThread
        self.calculateThread = threading.Thread(target=self.__calculateThread, args=())
        self.calculateThread.daemon = True  # Thread will auto shutdown when the prog ends
        self.calculateThread.setName(str(self.__stats["stream_syncSource"]) + ":calculateThread")
        self.calculateThread.start()

        # create a stream results transmitter object for this rx stream
        self.resultsTransmitter = ResultsTransmitter(self)

    def killStream(self):
        # This kills the ResultsTransmitter object created by this stream  - because
        # Resultstransmitter runs as an automonomous thread created by this object.
        # Therefore unless we kill it, this RtpReceiveStream object will never be allowed to die
        self.resultsTransmitter.kill()

        # Also kill the __calculateThread associated with this receive stream
        self.calculateThreadActiveFlag = False

        # # Finally forcibly remove this RtpReceiveStream (itself) from rtpRxStreamsDict
        # self.rtpRxStreamsDictMutex.acquire()
        # try:
        #     del self.rtpRxStreamsDict[self.__stats["stream_syncSource"]]
        # except Exception as e:
        #     Message.addMessage("ERR: RtpReceiveStream.killStream() (remove from rtpRxStreamsDict{})" + str(self.__stats["stream_syncSource"]))
        # self.rtpRxStreamsDictMutex.release()

    def getSocket(self):
        # Thread-safe method that returns the receive UDP socket associated with this stream
        self.__udpSocketMutex.acquire()
        sock = self.socket
        self.__udpSocketMutex.release()
        return sock

    def setSocket(self, newSocket):
        # Thread-safe method that sets the UDP receive/transmit socket associated with the stream
        # Message.addMessage("RtpReceiveStream.setSocket -old() " + str(id(self.socket)))
        self.__udpSocketMutex.acquire()
        self.socket = newSocket
        self.__udpSocketMutex.release()
        # Message.addMessage("RtpReceiveStream.setSocket -New() " + str(id(self.socket)))

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
                    Message.addMessage(excessiveJitterEvent.getSummary()['summary'])

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
                Message.addMessage(glitch.getSummary()['summary'])
            else:
                Message.addMessage(glitch.getSummary()['summary'] + " (ignore)")
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
                    Message.addMessage(glitch.getSummary()['summary'])
                else:
                    Message.addMessage(glitch.getSummary()['summary'] + " (ignore)")

                # update glitch stats
                self.__updateGlitchStats(glitch)

            # Store current rtp packet for the next iteration around the loop
            prevRtpPacket = rtpPacket


        if self.__stats["glitch_counter_total_glitches"] > 1:
            # Calculate mean of new and prev value
            self.__stats["glitch_mean_time_between_glitches"] = \
                (self.sumOfTimeElapsedSinceLastGlitch + self.__stats["glitch_time_elapsed_since_last_glitch"]) / \
                self.__stats["glitch_counter_total_glitches"]

    # Define a private calculation method that will run autonomously as a thread
    # This thread will
    def __calculateThread(self):
        Message.addMessage("DBUG: Starting __calculateThread with sync Source: " + \
                           str(self.__stats["stream_syncSource"]))

        # Prev timestamp doesn't exist yet as this is the first packet, so create datetime object with value 0
        lastReceivedRtpPacket = RtpData(0, 0, datetime.timedelta(), self.__stats["stream_syncSource"])

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
                    Message.addMessage(streamStartedEvent.getSummary()['summary'])

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
                    Message.addMessage(streamLostEvent.getSummary()['summary'])
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
                if self.__stats["packet_counter_1S"] > 0:
                    self.__stats["packet_payload_size_mean_1S_bytes"] = \
                        int(self.__stats["packet_data_received_1S_bytes"] / self.__stats["packet_counter_1S"])
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
                    self.__stats["calculate_thread_sampling_interval_S"] = 10.0 * \
                                                                           self.__stats[
                                                                               "packet_instantaneous_receive_period_uS"] / 1000000.0

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

                # Check to see if this is a truly dead receive stream. If so, kill the associated this calculateThread and
                # also the corresponding ResultsTransmitter.__resultsTransmitterThread. Finally, remove this RtpStream object
                # from the dictionary
                try:
                    if (datetime.datetime.now() - self.__stats["packet_last_seen_received_timestamp"]) > \
                            datetime.timedelta(seconds = self.streamIsDeadThreshold_s):

                        Message.addMessage("Stream " + str(self.__stats["stream_syncSource"]) +\
                                           "(" + str(self.__stats["stream_friendly_name"]).rstrip() +\
                                           ") believed dead, removing from list")
                        # Kill itself
                        self.killStream()

                        # Finally remove itself from the rtpRxStreamsDict
                        removeRtpStreamFromDict(self.__stats["stream_syncSource"], self.rtpRxStreamsDict, self.rtpRxStreamsDictMutex)
                except Exception as e:
                    Message.addMessage("ERR: RtpStream.__calc..Thread. auto self.killStream: " + str(e))
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
                self.__eventList.append(ProcessorOverload(self.__stats, lastReceivedRtpPacket))
                # Increment the all_events counter
                self.__stats["stream_all_events_counter"] += 1



            # Unlock  self.__stats and self.__eventList mutexes
            self.__accessRtpStreamStatsMutex.release()
            self.__accessRtpStreamEventListMutex.release()

            # Empty the self.rtpStream list
            del self.rtpStream

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

    # Thread-safe method for accessing realtime RtpStream eventList
    # No args: Returns the entire list
    # 1 arg: Returns the last n events
    # 2 args: returns the range specified (inclusive)
    def getRTPStreamEventList(self, *args):
        self.__accessRtpStreamEventListMutex.acquire()
        # Create copy of events list
        eventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()

        if len(args) == 2:
            # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
            try:
                # Slice the list
                return eventList[args[0]:args[1] + 1]
            except Exception as e:
                Message.addMessage("ERR: RtpStream.getRTPStreamEventList(" + str(args[0]) + ":" +
                                   str(args[1]) + ") requested start and end indexes out of range: " + str(e))
        elif len(args) == 1:
            # If one arg supplied, return the last n events.
            # IF event list not as long as n, return what does exist
            try:
                return eventList[(args[0] * -1):]
            except:
                return eventList
        else:
            return eventList

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
            # Message.addMessage("DBUG: __houseKeepEventList() "+str(noOfMessagesToPurge)+
            #                    " events removed"+str(oldSize)+">>"+str(newSize))

    # Define setter methods
    def addData(self, rtpSequenceNo, payloadSize, timestamp, syncSource):
        # Create a new rtp data object to hold the rtp packet data
        newData = RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource)

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
        self.transmitterActiveFlag = True


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
        self.transmitterActiveFlag =False



    def __resultsTransmitterThread(self):
        Message.addMessage("INFO: __resultsTransmitterThread started: "+str(self.udpSocket))

        oldSocket = self.parentRtpRxStream.getSocket()
        # Message.addMessage("__resultsTransmitterThread. Initial socket" + str(id(oldSocket)))

        while self.transmitterActiveFlag:
            self.udpSocket = self.parentRtpRxStream.getSocket()
            # if oldSocket is not self.udpSocket:
            #     Message.addMessage("__resultsTransmitterThread. Socket changed to " + str(id(self.udpSocket)))
            #     oldSocket = self.udpSocket

            # Check that the the socket is a valid socket.socket object
            if type(self.udpSocket) == socket.socket:
                # Message.addMessage("__resultsTransmitterThread. Current TX socket " + str(id(self.udpSocket)))
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
                    fragmentedMessage = fragmentString(pickledMessage, MAX_UDP_TX_LENGTH)

                    # iterate over fragments
                    for fragment in fragmentedMessage:
                        # Pickle and send each fragment one at a time
                        txMessage = pickle.dumps(fragment,protocol=2)
                        # Message.addMessage("DBUG: tx'd: (" +str(len(txMessage)) + ") "+ txMessage)
                        self.udpSocket.sendto(txMessage, (self.destAddr, self.destPort))


                except Exception as e:
                    try:
                        # For Python3 (which has the id() function)
                        Message.addMessage("ERR:__resultsTransmitterThread sendto() " + str(id(self.udpSocket)))
                    except:
                        # For Python2 which doesn't
                        Message.addMessage("ERR:__resultsTransmitterThread sendto() " + str(self.udpSocket))
                    finally:
                        Message.addMessage("ERR: __resultsTransmitterThread. Killing object for stream: " + str(self.syncSource))
                        self.kill()

            else:
                Message.addMessage("ERR: __resultsTransmitterThread - invalid UDP socket?")
            time.sleep(0.5)
