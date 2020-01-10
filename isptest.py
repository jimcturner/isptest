#!/usr/bin/env python
#
# Python packet sniffer
#
# 

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
import getopt  # Used to parse command line arguments
import re  # Regex 'regular expression' module
from timeit import default_timer as timer  # Used to calculate elapsed time
import math
from terminaltables import SingleTable  # Used for pretty tables in displayThread

####################################################################################
# Utility Functions
# #################

# Define a getch() function to catch keystrokes (for control of the RTP Generator thread)
# This code has been lifted from https://gist.github.com/jfktrey/8928865
if platform.system() == "Windows":
    import msvcrt


    def getch():
        return msvcrt.getch()
# Otherwise assume Linux or MacOS
else:
    import tty, termios, sys


    def getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


# Define a function to get the size of the current console terminal.
# This should hopefully work on Windows, OSX and Linux
# From https://stackoverflow.com/questions/566746/how-to-get-linux-console-window-width-in-python
# Returns a tuple contain the no of columns, rows
def getTerminalSize():
    import platform
    current_os = platform.system()
    tuple_xy = None
    if current_os == 'Windows':
        tuple_xy = _getTerminalSize_windows()
        if tuple_xy is None:
            tuple_xy = _getTerminalSize_tput()
            # needed for window's python in cygwin's xterm!
    if current_os == 'Linux' or current_os == 'Darwin' or current_os.startswith('CYGWIN'):
        tuple_xy = _getTerminalSize_linux()
    if tuple_xy is None:
        print "default"
        tuple_xy = (80, 25)  # default value
    return tuple_xy


def _getTerminalSize_windows():
    res = None
    try:
        from ctypes import windll, create_string_buffer

        # stdin handle is -10
        # stdout handle is -11
        # stderr handle is -12

        h = windll.kernel32.GetStdHandle(-12)
        csbi = create_string_buffer(22)
        res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
    except:
        return None
    if res:
        import struct
        (bufx, bufy, curx, cury, wattr,
         left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
        sizex = right - left + 1
        sizey = bottom - top + 1
        return sizex, sizey
    else:
        return None


def _getTerminalSize_tput():
    # get terminal width
    # src: http://stackoverflow.com/questions/263890/how-do-i-find-the-width-height-of-a-terminal-window
    try:
        import subprocess
        proc = subprocess.Popen(["tput", "cols"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = proc.communicate(input=None)
        cols = int(output[0])
        proc = subprocess.Popen(["tput", "lines"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = proc.communicate(input=None)
        rows = int(output[0])
        return (cols, rows)
    except:
        return None


def _getTerminalSize_linux():
    def ioctl_GWINSZ(fd):
        try:
            import fcntl, termios, struct, os
            cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
        except:
            return None
        return cr

    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass
    if not cr:
        try:
            cr = (env['LINES'], env['COLUMNS'])
        except:
            return None
    return int(cr[1]), int(cr[0])


####################################################################################

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


# Define an object that represents a start of signal
class StreamStarted(object):
    # Define descriptive names. These might be useful later
    type = "StreamStarted"
    description = ""

    # Constructor
    def __init__(self, firstPacketReceived, stats):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        self.firstPacketdReceived = firstPacketReceived
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo=self.stats["stream_all_events_counter"] + 1

    def getData(self, verbosityLevel):
        # Returns a dictionary containing information about this event
        # If verbosityLevel > 0, returns the entire stats dictionary associated with this event
        if verbosityLevel == 0:
            summary = "["+ str(self.eventNo)+"]" + \
                      "[" + str(self.stats["stream_syncSource"]) + "] " + "Stream Started"
            data = {'timeCreated': self.timeCreated, 'summary': summary}
        elif verbosityLevel == 1:
            data = {'type': StreamStarted.type, 'timeCreated': self.timeCreated, \
                    'rtpSequenceNo': self.firstPacketdReceived.rtpSequenceNo,
                    'syncSource': self.stats["stream_syncSource"],
                    'eventNo': self.eventNo}
        elif verbosityLevel == 2:
            data = {'type': StreamStarted.type, 'timeCreated': self.timeCreated,
                    'rtpSequenceNo': self.firstPacketdReceived.rtpSequenceNo,
                    'syncSource': self.stats["stream_syncSource"], 'stats': self.stats, 'eventNo': self.eventNo}
        return data


# Define an event that represents a loss of rtpStream
class StreamLost(object):
    # Define descriptive names. These might be useful later
    type = "StreamLost"
    description = ""

    # Constructor
    def __init__(self, lastPacketReceived, stats):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        self.lastPacketReceived = lastPacketReceived
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1

    def getData(self, verbosityLevel):
        # Returns a dictionary containing information about this event
        # If verbosityLevel > 0, returns the entire stats dictionary associated with this event

        if verbosityLevel == 0:
            summary = "["+ str(self.eventNo)+"]" + \
                "[" + str(self.stats["stream_syncSource"]) + "] " + "Stream lost"
            data = {'timeCreated': self.timeCreated, 'summary': summary}
        elif verbosityLevel == 1:
            data = {'type': StreamLost.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"], 'eventNo': self.eventNo}

        elif verbosityLevel == 2:
            data = {'type': StreamLost.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"], 'stats': self.stats,
                    'eventNo': self.eventNo}
        return data


# Define an event object that represents a excessive jitter event
class ExcessiveJitter(object):
    # Define descriptive names. These might be useful later
    type = "ExcessiveJitter"
    description = ""

    def __init__(self, lastPacketReceived, stats):
        self.timeCreated = datetime.datetime.now()
        self.lastPacketReceived = lastPacketReceived
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1

    def getData(self, verbosityLevel):
        # Returns a dictionary containing information about this event
        # If verbosityLevel > 0, returns increasing level of detail associated with this event
        if verbosityLevel == 0:
            summary = "["+ str(self.eventNo)+"]" + \
                "[" + str(self.stats["stream_syncSource"]) + "] " + "Excessive jitter: " + \
                      str(self.stats["jitter_mean_1S_uS"]) + "/" + str(self.stats["jitter_long_term_uS"]) + "uS"
            data = {'timeCreated': self.timeCreated, 'summary': summary}

        elif verbosityLevel == 1:
            data = {'type': ExcessiveJitter.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"],
                    'jitter_long_term_uS': self.stats["jitter_long_term_uS"],
                    'jitter_mean_1S_uS': self.stats["jitter_mean_1S_uS"],
                    'eventNo': self.eventNo}

        elif verbosityLevel == 2:
            data = {'type': ExcessiveJitter.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"],
                    'jitter_long_term_uS': self.stats["jitter_long_term_uS"],
                    'jitter_mean_1S_uS': self.stats["jitter_mean_1S_uS"], 'stats': self.stats,
                    'eventNo': self.eventNo}

        return data


# Define an event object that represents a procesor overload. This might happen if the calculateThread can't process
# incoming packets fast enough
class ProcessorOverload(object):
    # Define descriptive names. These might be useful later
    type = "ProcessorOverload"
    description = ""

    def __init__(self, lastPacketReceived, stats):
        self.timeCreated = datetime.datetime.now()
        self.lastPacketReceived = lastPacketReceived
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1

    def getData(self, verbosityLevel):
        # Returns a dictionary containing information about this event
        # If verbosityLevel > 0, returns the entire stats dictionary associated with this event
        if verbosityLevel == 0:
            summary = "["+ str(self.eventNo)+"]" + \
                "[" + str(self.stats["stream_syncSource"]) + "] " + "Processor overload: " + \
                      str(self.stats["stream_processor_utilisation_percent"]) + "%"
            data = {'timeCreated': self.timeCreated, 'summary': summary}

        elif verbosityLevel == 1:
            data = {'type': ProcessorOverload.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"], \
                    'processor_utilisation_percent': self.stats["stream_processor_utilisation_percent"],
                    'eventNo': self.eventNo}

        elif verbosityLevel == 2:
            data = {'type': ProcessorOverload.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"],
                    'processor_utilisation_percent': self.stats["stream_processor_utilisation_percent"],
                    'stats': self.stats, 'eventNo': self.eventNo}
        return data


# Define an event that represent a glitch
# This will be in the form of the packets (RtpData objects) either side of the 'hole' in received data
class Glitch(object):
    # Define descriptive names. These might be useful later
    type = "Glitch"
    description = ""

    # Constructor
    def __init__(self, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap, stats):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        # Update instance variables
        self.startOfGap = lastReceivedPacketBeforeGap
        self.endOfGap = firstPackedReceivedAfterGap
        # Take local copy of stats dictionary
        self.stats = dict(stats)
        # This is a new event, so set eventNo to be an increment of the current self.stats["stream_all_events_counter"] value
        self.eventNo = self.stats["stream_all_events_counter"] + 1

        # Calculate packets lost by taking the diff of the sequence nos at the end and start of hole
        # The '-1' is because it's fences and fenceposts
        self.packetsLost = abs(
            firstPackedReceivedAfterGap.rtpSequenceNo - lastReceivedPacketBeforeGap.rtpSequenceNo) - 1
        # print firstPackedReceivedAfterGap.rtpSequenceNo,lastReceivedPacketBeforeGap.rtpSequenceNo,"\r"
        # Calculate length of this glitch
        self.glitchLength = firstPackedReceivedAfterGap.timestamp - lastReceivedPacketBeforeGap.timestamp
        # Calculate useful values showing expected and actual rtpSequence no
        self.expectedSequenceNo = self.startOfGap.rtpSequenceNo + 1
        self.actualReceivedSequenceNo = self.endOfGap.rtpSequenceNo

    def getData(self, verbosityLevel):
        # Returns a dictionary containing information about this event
        # If verbosityLevel > 0, returns the entire stats dictionary associated with this event
        if verbosityLevel == 0:
            summary = "["+ str(self.eventNo)+"]" + \
                "[" + str(self.stats["stream_syncSource"]) + "] " + "Glitch: " + \
                      "Duration: " + str(self.glitchLength) +", " + str(self.packetsLost) + " packet(s) lost"
            data = {'timeCreated': self.timeCreated, 'summary': summary}

        elif verbosityLevel == 1:
            data = {'type': Glitch.type, 'timeCreated': self.timeCreated,
                    'syncSource': self.stats["stream_syncSource"], 'packetsLost': self.packetsLost,
                    'duration': self.glitchLength, 'eventNo': self.eventNo}

        elif verbosityLevel == 2:
            data = {'type': Glitch.type, 'timeCreated': self.timeCreated, 'syncSource': self.stats["stream_syncSource"],
                    'packetsLost': self.packetsLost, 'duration': self.glitchLength, 'stats': self.stats,
                    'eventNo': self.eventNo}
        return data


class MovingTotalEventCounter(object):
    # Stores a running total of events that happened within the last x seconds with y granualarity
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


# Define a class to represent a flow of received rtp packets (and associated stats)
class RtpStream(object):
    # Constructor method.
    # The RtpStream object should be created with a unique id no
    # (for instance the rtp sync-source value would be perfect)
    def __init__(self, syncSource, srcAddress, srcPort, rxAddress, rxPort):

        # Create private empty dictionary to hold stats for this RtpStream object. Accessible via a getter method
        self.__stats = {}
        # Assign to instance variable
        self.__stats["stream_syncSource"] = syncSource
        self.__stats["stream_srcAddress"] = srcAddress
        self.__stats["stream_srcPort"] = srcPort
        self.__stats["stream_rxAddress"] = rxAddress
        self.__stats["stream_rxPort"] = rxPort
        print "creating RtpStream with syncSource:", self.__stats["stream_syncSource"], "\r"

        # Create a mutex lock to be used by the a thread
        # To set the lock use: __accessRtpDataMutex.acquire(), To release use: __accessRtpDataMutex.release()
        self.__accessRtpDataMutex = threading.Lock()
        self.__accessRtpStreamStatsMutex = threading.Lock()
        self.__accessRtpStreamEventListMutex = threading.Lock()

        # Create empty list to hold rtp stream data as it is received by the socket
        self.rtpStreamData = []

        # Create private empty list to hold Events for this RtpStream object. Accessible via a getter method
        self.__eventList = []

        # Counter to be used by __calculateJitter()
        self.sumOfJitter_1s = 0

        # Create a __calculateThread
        self.calculateThread = threading.Thread(target=self.__calculateThread, args=())
        self.calculateThread.daemon = True  # Thread will auto shutdown when the prog ends
        self.calculateThread.start()

    def __calculateJitter(self, prevRtpPacket):
        # Iterate over self.rtpStream to get total count of data received in this batch of data, no. of packets and also calculate
        # rx time deltas and jitter
        sumOfInterPacketJitter = 0
        sumOfTimeDeltas = 0

        # Keep prevRtpPacket value safe for later (because we'll be overwriting it as we iterate over self.rtpStream[])
        z = prevRtpPacket

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

            # Sum the timeDeltas to calculate the average time between packets arriving
            sumOfTimeDeltas += y.timeDelta.microseconds
            # Update prevTimestamp for next time around loop
            prevRtpPacket = y

        # Calculate jitter
        # Find the mean value of the microsecond portion of the jitter values in self.rtpStream
        # and also the mean time period between packets arriving (should, on average match the rtp
        # generator period)
        if len(self.rtpStream) > 1:
            self.__stats["jitter_instantaneous"] = sumOfInterPacketJitter / (len(self.rtpStream) - 1)
            self.__stats["packet_mean_receive_period_uS"] = sumOfTimeDeltas / (len(self.rtpStream) - 1)
        else:
            # This batch of data only contains a single packet.
            # as this requires at least two packets worth of data (the difference of a difference!)
            # The meanRxPeriod is possible to deduce by comparing this new single packet with the last received
            self.__stats["jitter_instantaneous"] = self.rtpStream[-1].jitter - z.jitter
            self.__stats["packet_mean_receive_period_uS"] = self.rtpStream[-1].timeDelta.microseconds

        # Now attempt to detect excessive jitter bycomparing the 1S jitter with the mean receive period.
        # Jitter should only be a problem if the packets
        # start crashing into each other on receipt.
        # Check that long term value has actually been calculated
        if self.__stats["jitter_long_term_uS"] > 0:
            if self.__stats["jitter_mean_1S_uS"] > \
                    (self.excessJitterThresholdFactor * self.__stats["packet_mean_receive_period_uS"]):
                    # (self.excessJitterThresholdFactor * self.__stats["jitter_long_term_uS"]):
                # If jitter alarms not inhibited, add a new jitter event
                # Take diff between time.now() and the time of the last event
                if self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"].total_seconds() >= \
                        self.__stats["jitter_alarm_event_timeout_S"] or \
                        self.__stats["jitter_excess_jitter_events_total"] == 0:
                    # Add the event to the event list
                    self.__eventList.append(ExcessiveJitter(self.rtpStream[-1], self.__stats))
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1

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
                self.__stats["jitter_time_of_last_excess_jitter_event"]

        # Calculate meanTimeBetweenExcessJitterEvents (requires at least two jitter events)
        if self.__stats["jitter_excess_jitter_events_total"] > 1:
            self.__stats["jitter_mean_time_between_excess_jitter_events"] = \
                (self.sumOfTimeElapsedSinceLastExcessJitterEvents + self.__stats[
                    "jitter_time_elapsed_since_last_excess_jitter_event"]) / \
                self.__stats["jitter_excess_jitter_events_total"]

    def __updateGlitchStats(self, latestGlitch):
        # This method takes code out of __detectGlitches to reduce duplication
        # It's primary purpose is to update __stats keys relating to glitches

        # Now update aggregate glitch stats
        self.__stats["glitch_packets_lost_total"] += latestGlitch.packetsLost
        self.__stats["glitch_length_total_time"] += latestGlitch.glitchLength
        self.__stats["glitch_counter_total"] += 1
        # Add event to moving counters
        for x in self.movingGlitchCounters:
            x.addEvent(1)

        # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean)
        self.sumOfTimeElapsedSinceLastGlitch += self.__stats["glitch_time_elapsed_since_last_glitch"]

        # Calculate aggregate mean glitch stats
        if self.__stats["glitch_counter_total"] > 1:
            self.__stats["glitch_mean_duration"] = \
                (self.__stats["glitch_mean_duration"] + latestGlitch.glitchLength) / 2
            self.__stats["glitch_packets_lost_per_glitch_mean"] = \
                int(math.ceil((self.__stats["glitch_packets_lost_per_glitch_mean"] + latestGlitch.packetsLost) / 2.0))

        # Update glitch min/max packet loss stats
        if self.__stats["glitch_packets_lost_per_glitch_min"] < 1:
            self.__stats["glitch_packets_lost_per_glitch_min"] = latestGlitch.packetsLost

        if latestGlitch.packetsLost < self.__stats["glitch_packets_lost_per_glitch_min"]:
            self.__stats["glitch_packets_lost_per_glitch_min"] = latestGlitch.packetsLost

        if latestGlitch.packetsLost > self.__stats["glitch_packets_lost_per_glitch_max"]:
            self.__stats["glitch_packets_lost_per_glitch_max"] = latestGlitch.packetsLost

        # update glitch min/max duration stats
        # Test for 'zero' duration (the initial value)
        if self.__stats["glitch_min_duration"] == datetime.timedelta():
            self.__stats["glitch_min_duration"] = latestGlitch.glitchLength

        if latestGlitch.glitchLength < self.__stats["glitch_min_duration"]:
            self.__stats["glitch_min_duration"] = latestGlitch.glitchLength

        if latestGlitch.glitchLength > self.__stats["glitch_max_duration"]:
            self.__stats["glitch_max_duration"] = latestGlitch.glitchLength

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
            # Take timestamp of most recent glitch
            self.__stats["glitch_most_recent_timestamp"] = datetime.datetime.now()

            # Capture packets either side of the 'hole' and store them in the event list
            # Create an object representing the glitch
            glitch = Glitch(lastReceivedRtpPacket, self.rtpStream[0], self.__stats)
            # Add the latest glitch to the evenList[]
            self.__eventList.append(glitch)
            # Increment the all_events counter
            self.__stats["stream_all_events_counter"] += 1

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
                # Take timestamp of most recent glitch
                self.__stats["glitch_most_recent_timestamp"] = datetime.datetime.now()

                # Capture packets either side of the 'hole' and store them in the event list
                # Create an object representing the glitch
                glitch = Glitch(prevRtpPacket, rtpPacket, self.__stats)
                # Add the glitch to the evenList[]
                self.__eventList.append(glitch)
                # Increment the all_events counter
                self.__stats["stream_all_events_counter"] += 1

                # update glitch stats
                self.__updateGlitchStats(glitch)

            # Store current rtp packet for the next iteration around the loop
            prevRtpPacket = rtpPacket

        if self.__stats["glitch_counter_total"] > 1:
            # Calculate mean of new and prev value
            self.__stats["glitch_mean_time_between_glitches"] = \
                (self.sumOfTimeElapsedSinceLastGlitch + self.__stats["glitch_time_elapsed_since_last_glitch"]) / \
                self.__stats["glitch_counter_total"]

    # Define a private calculation method that will run autonomously as a thread
    # This thread will
    def __calculateThread(self):
        print "__calculateThread started with sync Source: ", self.__stats["stream_syncSource"], "\r"

        # Prev timestamp doesn't exist yet as this is the first packet, so create datetime object with value 0
        lastReceivedRtpPacket = RtpData(0, 0, datetime.timedelta(), self.__stats["stream_syncSource"])
        self.__stats["packet_first_packet_received_timestamp"] = datetime.timedelta()

        # General Counters
        loopCounter = 0
        # Start the loop timer (used to provide a 1sec interval)
        loopTimerStart = timer()
        # Timer used to detect loss of streams against an alarm threshold
        lossOfStreamTimerStart = timer()

        runningTotalPacketsPerSecond = 0
        runningTotalDataReceivedPerSecond = 0

        self.__stats["packet_counter_1S"] = 0
        self.__stats["packet_data_received_1S_bytes"] = 0
        self.__stats["packet_data_received_total_bytes"] = 0
        self.__stats["packet_payload_size_mean_1S_bytes"] = 0
        self.__stats["packet_counter_received_total"] = 0
        self.__stats["stream_time_elapsed_total"] = datetime.timedelta()
        self.__stats["packet_mean_receive_period_uS"] = 0

        # Aggregate Glitch counters
        self.__stats["glitch_packets_lost_total_percent"] = 0
        self.__stats["glitch_packets_lost_total"] = 0
        self.__stats["glitch_packets_lost_per_glitch_mean"] = 0
        self.__stats["glitch_packets_lost_per_glitch_min"] = 0
        self.__stats["glitch_packets_lost_per_glitch_max"] = 0
        self.__stats["glitch_counter_total"] = 0

        # Keeps a count of all events recorded against this rtpStream
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
        self.__stats["glitch_mean_duration"] = datetime.timedelta()
        self.__stats["glitch_max_duration"] = datetime.timedelta()
        self.__stats["glitch_min_duration"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastGlitch = datetime.timedelta()

        # Jitter counters
        self.__stats["jitter_min_uS"] = 0
        self.__stats["jitter_max_uS"] = 0
        self.__stats["jitter_range_uS"] = 0
        self.__stats["jitter_instantaneous"] = 0
        self.__stats["jitter_mean_1S_uS"] = 0
        self.__stats["jitter_mean_10S_uS"] = 0
        self.__stats["jitter_long_term_uS"] = 0
        historicJitter = []
        sumOfJitter_1s = 0

        self.__stats["stream_processor_utilisation_percent"] = 0

        # % ratio of 1S Jitter_uS to packet_mean_receive_period_uS that will trigger an excessJitterEvent
        self.__stats["jitter_excessive_alarm_threshold_percent"] = 50
        self.excessJitterThresholdFactor = (self.__stats["jitter_excessive_alarm_threshold_percent"] / 100.0)

        # No of seconds to inhibit an excessive jitter alarm
        self.__stats["jitter_alarm_event_timeout_S"] = 2
        self.__stats["jitter_time_elapsed_since_last_excess_jitter_event"] = datetime.timedelta()
        self.__stats["jitter_time_of_last_excess_jitter_event"] = datetime.timedelta()
        self.__stats["jitter_excess_jitter_events_total"] = 0
        self.__stats["jitter_mean_time_between_excess_jitter_events"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastExcessJitterEvents = datetime.timedelta()

        # Declare flags
        lossOfStreamFlag = True
        possibleLossOfStreamFlag = False
        lossOfStreamAlarmThreshold = 1

        self.__stats["calculate_thread_sampling_interval_S"] = 0.01  # Loop will execute every 10mS

        # Calculate the no of loops equating to a second
        loopsPerSecond = 1 / self.__stats["calculate_thread_sampling_interval_S"]

        while True:

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
                    self.__eventList.append(StreamStarted(self.rtpStream[0], self.__stats))
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                # Stream now being received so clear flag

                if lossOfStreamFlag == True:
                    # We're now receiving a stream, so clear alarm flag
                    lossOfStreamFlag = False

                if possibleLossOfStreamFlag == True:
                    possibleLossOfStreamFlag = False

                # Get copy of final packet of prev data set
                if (self.__stats["packet_counter_received_total"] < 1):
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

            else:
                # No data, so set lossOfStreamFlag (unless it's already been set)
                # Check for changes and that we also have an active stream. If so, set the flag and add an event to the eventlist

                if possibleLossOfStreamFlag == False:
                    # Set the flag
                    possibleLossOfStreamFlag = True
                    # And start the lossOfStream Timer
                    lossOfStreamTimerStart = timer()

                if (timer() - lossOfStreamTimerStart) >= lossOfStreamAlarmThreshold \
                        and lossOfStreamFlag == False and self.__stats["packet_counter_received_total"] > 0:
                    # Set flag
                    lossOfStreamFlag = True
                    # Add event to the list (but only do this once)
                    self.__eventList.append(StreamLost(lastReceivedRtpPacket, self.__stats))
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                    # Finally, reset min/max/range jitter values as they're corrupted by a loss of signal
                    self.__stats["jitter_min_uS"] = 0
                    self.__stats["jitter_max_uS"] = 0
                    self.__stats["jitter_range_uS"] = 0

            # Calculate elapsed since last glitch
            # But only if there has actually been a glitch in the past to measure against
            if self.__stats["glitch_counter_total"] > 0:
                # Calculate new value
                self.__stats["glitch_time_elapsed_since_last_glitch"] = datetime.datetime.now() - self.__stats[
                    "glitch_most_recent_timestamp"]

            # Calculate % packet loss
            if self.__stats["packet_counter_received_total"] > 0:
                totalExpectedPackets = self.__stats["packet_counter_received_total"] + self.__stats[
                    "glitch_packets_lost_total"]
                self.__stats["glitch_packets_lost_total_percent"] = self.__stats[
                                                                        "glitch_packets_lost_total"] * 100 / totalExpectedPackets

            # 1 second timer
            if (timer() - loopTimerStart) >= 1:
                # Reset loop timer starting reference
                loopTimerStart = timer()
                # Increment seconds elapsed
                self.__stats["stream_time_elapsed_total"] += datetime.timedelta(seconds=1)
                # Take snapshots of running totals
                self.__stats["packet_counter_1S"] = runningTotalPacketsPerSecond
                self.__stats["packet_data_received_1S_bytes"] = runningTotalDataReceivedPerSecond

                # Calculate self.__stats["packet_payload_size_mean_1S_bytes"]
                if self.__stats["packet_counter_1S"] > 0:
                    self.__stats["packet_payload_size_mean_1S_bytes"] = \
                        self.__stats["packet_data_received_1S_bytes"] / self.__stats["packet_counter_1S"]
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
                prevMeanJitter_10s = self.__stats["jitter_mean_10S_uS"]
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
                # Otherwise, for high packet receieve rates, the calculation time will become excessive
                # Wait a second, in order to know we're in a steady state
                if self.__stats["packet_mean_receive_period_uS"] > 0 and self.__stats["stream_time_elapsed_total"].seconds > 1:
                    self.__stats["calculate_thread_sampling_interval_S"] = 10.0 * self.__stats[
                        "packet_mean_receive_period_uS"] / 1000000.0

                ######### Now calculate moving glitch counters by iterating over the self.movingGlitchCounters array
                # firstly reculculate, then generate stats keys automatically for any moving totals counters
                # within self.movingGlitchCounters
                for x in self.movingGlitchCounters:
                    # Force the moving counters to increment their timers and recalculate totals
                    x.recalculate()
                    name, movingTotal, events = x.getResults()
                    # Dynamically create new stats keys using the name field of the moving glitch counter
                    self.__stats[name] = movingTotal
                    self.__stats[name + "_events"] = events

            # Calculate how long it has taken for the stats analysis to have been performed
            calculationEndTime = timer()
            try:
                # Take the calculation time in microseconds and combine with the period between
                # packets arriving multiplied by the no of packets in this batch of rtpStream
                # to work out how much processor headroom there is (as a ratio of times).
                # If the total calculation time for rtpStream[] is > than the gap between packets
                # arriving then the the processor can't keep up, so generate an event
                # This is to guard against false-postives
                # Calculate calculationDuration (in uS)
                #   the %1 throws away the whole number part, *1000000 converts from s to uS
                self.__stats["calculate_thread_calculation_duration_uS"] = ((
                                                                                        calculationEndTime - calculationStartTime) % 1) * 1000000

                # Calculate processorUtilisationPercent. All time values in uS
                self.__stats["stream_processor_utilisation_percent"] = \
                    self.__stats["calculate_thread_calculation_duration_uS"] * 100.0 / (
                                self.__stats["packet_mean_receive_period_uS"] * len(self.rtpStream))

                # If the CPU is >99% utilised, add event to the list (but only do this once)
                if self.__stats["stream_processor_utilisation_percent"] > 99:
                    self.__eventList.append(ProcessorOverload(lastReceivedRtpPacket, self.__stats))
                    # Increment the all_events counter
                    self.__stats["stream_all_events_counter"] += 1
                    pass
            except Exception as e:
                # print str(e),"\r"
                pass

            # Unlock  self.__stats and self.__eventList mutexes
            self.__accessRtpStreamStatsMutex.release()
            self.__accessRtpStreamEventListMutex.release()

            # Increment loop counter
            loopCounter += 1

            # Empty the self.rtpStream list
            del self.rtpStream

            time.sleep(self.__stats["calculate_thread_sampling_interval_S"])

    # Define getter methods
    def getRTPStreamID(self):
        return self.__stats["stream_syncSource"], self.__stats["stream_srcAddress"], self.__stats["stream_srcPort"]

    # Thread-safe method for accessing all RtpStream stats
    def getRtpStreamStats(self):
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats

    def getRtpStreamStatsByFilter(self, filter):
        # Thread-safe method to return specific stats who's dictionary key starts with 'filter'
        # Returns a list of tuples
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        # Filter keys of stats by startswith('filter') into a new dictionary
        filteredStats = {k: v for k, v in stats.items() if k.startswith(filter)}
        return filteredStats

    # Thread-safe method for accessing realtime RtpStream eventList
    def getRTPStreamEventList(self):
        self.__accessRtpStreamEventListMutex.acquire()
        # Create copy of events list
        eventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()
        return eventList

    # Define setter methods
    def addData(self, rtpSequenceNo, payloadSize, timestamp, syncSource):
        # Create a new rtp data object to hold the rtp packet data
        newData = RtpData(rtpSequenceNo, payloadSize, timestamp, syncSource)

        # NOW ADD DATA TO A LIST

        # Lock the access mutex
        self.__accessRtpDataMutex.acquire()
        # Add the  RtpData obect containing the latest packet info, to the rtpStreamData[] list
        self.rtpStreamData.append(newData)
        # Release the mutex
        self.__accessRtpDataMutex.release()
        # Now we've added the newData object to the list rtpStreamData[] we cab delete the newData object
        del newData


def createTable(inputDictionary, title):
    # This function will take a dictionary and turn it into a two column table using terminaltables.Singletable
    # it will return the table as a list of strings

    # Create two seperate lists, one of the dictionary keys and one of the values
    keys = []
    values = []
    for key, value in inputDictionary:
        keys.append(key)  # Append key
        values.append(value)  # Append value

    # iterate over keys list to create a 2D array of the table contents
    table_data = []
    for x in range(len(keys)):
        row = [keys[x], values[x]]  # Create a complete row containing a key and value column
        table_data.append(row)  # Append the complete row to the table_data list (of lists)
        del row  # Remove the existing row

    # Create the table
    table = SingleTable(table_data)
    table.title = title
    table.inner_heading_row_border = False  # No headings on this table
    # Split the table into a list containing separate lines and return (and also the width/height of the table
    width = table.table_width
    height = len(keys) + 2  # Takes into account the top/bottom border
    return width, height, table.table.splitlines()


def printTable(xPos, yPos, tableData):
    # Prints a table generated by createTable() at position xPos,Ypos
    # At the end, it will leave the cursor at the start of the next available line
    lineCount = 0  # Used to increment the y cursor
    for row in tableData:
        # Generate an ascii escape sequence \033[<yPos>;<xPos>H to move the cursor
        asciiCode = "\033[" + str((yPos + lineCount)) + ";" + str(xPos) + "H"
        printString = asciiCode + row + "\r"
        print printString
        lineCount += 1
    # Finally, move cursor to start of next available line
    print "\033[" + str(yPos + lineCount) + ";" + str(0) + "H", "\r"

def humanise(inputDictionary):
    # This function will examine the key/value pairs of the stats dictionary and
    # prettify the values. It will return a list of tuples containing the value/key pairs

    # You're not allowed to modify a dictionary whilst iterating over it, therefore create a new dictionary that will
    # hold the modified values

    # List of prefixes to be removed from the key names
    prefixes = ["stream_", "glitch_", "historic_", "jitter_", "packet_"]
    # List of suffixes to be removed from the key names
    suffixes = ["_percent","_uS","_timestamp","_S","_bytes"]

    # Create a list to hold the humanised output
    newDictionary = {}
    for key, value in inputDictionary:
        # Next, Scan 'keys' to see if they contain any of the prefix or suffix terms. If they do, replace them with ""
        # Take a copy of the key to be examined
        tempKeyName=key
        # Iterate over prefixes
        for prefix in prefixes:
            tempKeyName=str(key).replace(prefix,"",1)
            # Check to see if tempKeyName has been modified?
            if tempKeyName != key:
                break
        # Take a copy of the key with the prefix removed
        keyWithoutPrefix=tempKeyName

        # Now iterate over suffixes list
        tempKeyName=keyWithoutPrefix
        for suffix in suffixes:
            tempKeyName = str(keyWithoutPrefix).replace(suffix,"",1)
            # Check to see if tempKeyName has been modified?
            if tempKeyName != keyWithoutPrefix:
                break
        # Take a copy of the key with the suffix removed
        keyWithoutSuffix=tempKeyName

        # To improve readability, remove underscore characters
        tempKeyName=keyWithoutSuffix.replace("_"," ")

        # Now capitalise
        # tempKeyName=tempKeyName.title()
        # Now capture the finished 'humanised' key name
        humanisedKey=tempKeyName

        # Scan the (original) key name for clues about the format of the corresponding value

        if str(key).find("uS") > 0:
            # Create human readable value
            humanisedValue = str(value) + "uS"

        elif str(key).find("percent") > 0:
            # Create human readable value
            # Format to two decimal places
            value=round(value,2)
            humanisedValue = str(value) + "%"

        elif str(key).find("_S") > 0:
            # Create human readable value
            humanisedValue = str(value) + "s"

        # elif str(key).find("data_received_1S_bytes") > 0:
        elif key == "packet_data_received_1S_bytes":
            # Convert bytes/sec to bps
            bps = value * 8
            if bps >= 1048576:
                # Convert bps to Mbps
                Mbps = bps / 1048576
                humanisedValue = str(Mbps) + " Mbps"

            elif bps >= 1024:
                # Convert bps to kbps
                kbps = bps / 1024
                humanisedValue = str(kbps) + " kbps"

            else:
                humanisedValue = str(bps) + " bps"


        elif key == "packet_data_received_total_bytes":
            if value >= 1048576:
                # Convert bytes to Mb
                value = value / 1048576
                humanisedValue = str(value) + " Mb"
            elif value >= 1024:
                # Convert bytes to kb
                value = value / 1024
                humanisedValue = str(value) + " kb"
            else:
                humanisedValue = str(value) + " bytes"

        elif key == "packet_payload_size_mean_1S_bytes":
            humanisedValue = str(value) + " bytes"

        elif key == "packet_counter_1S":
            humanisedValue = str(value)+" packets/s"

        elif key == "packet_counter_received_total":
            humanisedValue = str(value) + " packets"

        else:
            # Otherwise, keep the original value
            humanisedValue=value

        # Assign existing value to the new dictionary key
        newDictionary[humanisedKey] = humanisedValue

    # Return dictionary of humanised keys and values
    return newDictionary.items()

# Define a display thread that will run autonomously
def __displayThread(rtpStream):
    print "__displayThread started with id: ", rtpStream.getRTPStreamID(), "\r"

    padding = 1  # Gap between tables
    margin = 2
    while True:
        # Get all keys/values from rtpStream
        stats = rtpStream.getRtpStreamStats()
        # Clear screen and move cursor to origin
        print "\033[2J", "\r"
        print "\033[0;0HIBEOO ISP Analyser---------------------------------------------------------------------------------------------------", "\r"
        # print "Terminal size",getTerminalSize(),"\r"
        nextUseableLine = 3  # Takes into account the title
        nextUseableColumn = 0
        # Create a table of stream stats

        width, height, table = createTable(humanise(rtpStream.getRtpStreamStatsByFilter("stream").items()), "Stream info")
        printTable(margin, nextUseableLine, table)
        nextUseableLine += (height + padding)
        if (width + padding + margin) > nextUseableColumn:
            nextUseableColumn = width + padding + margin
        # Create a Glitch Stats table
        width, height, table = createTable(humanise(rtpStream.getRtpStreamStatsByFilter("glitch").items()), "Glitch Stats")
        printTable(margin, nextUseableLine, table)
        nextUseableLine += (height + padding)
        if (width + padding + margin) > nextUseableColumn:
            nextUseableColumn = width + padding + margin

        # Create a table of historic glitch stats
        width, height, table = createTable(humanise(rtpStream.getRtpStreamStatsByFilter("historic").items()),
                                           "Historic glitch stats")
        printTable(margin, nextUseableLine, table)
        nextUseableLine += (height + padding)
        nextUseableLineWholeScreen = nextUseableLine
        # if (width + padding + margin) > nextUseableColumn:
        #     nextUseableColumn = width + padding + margin

        # Now create tables on the RHS of the screen.
        # Reset nextUseableLine to top of screen
        nextUseableLine = 2
        # Create a table of jitter stats
        width, height, table = createTable(humanise(rtpStream.getRtpStreamStatsByFilter("jitter").items()), "Jitter Stats")
        printTable(nextUseableColumn, nextUseableLine, table)
        nextUseableLine += (height + padding)
        # if (width + padding + margin) > nextUseableColumn:
        #     nextUseableColumn = width + padding + margin

        # Create a table of Packet stats beside the jitter table
        width, height, table = createTable(humanise(rtpStream.getRtpStreamStatsByFilter("packet").items()), "Packet Stats")
        # # Print the table to the screen line by line
        printTable(nextUseableColumn, nextUseableLine, table)
        nextUseableLine += (height + padding)

        # # Move cursor to start of next available line
        print "\033[" + str(nextUseableLineWholeScreen) + ";" + str(0) + "H", "\r"


        # Now create table from eventList
        eventTableRows = []
        allEvents = rtpStream.getRTPStreamEventList()
        noOfHistoricEventsToView = 10
        # Display the last x events
        # Get no of events in list
        if len(allEvents) > noOfHistoricEventsToView:
            # Create a sub-list of of the last x event items
            events = allEvents[(noOfHistoricEventsToView * -1):]
        else:
            events = allEvents

        for event in events:
            # Get dictionary from Event.getData() method containing timestamp and summary
            eventData=event.getData(0)
            # Create the new row
            tableRow=[eventData["timeCreated"].strftime("%H:%M:%S"),eventData["summary"]]
            # Append the new row to the list of rows
            eventTableRows.append(tableRow)
            # Now stored, delete the row, ready for next time around the loop
            del tableRow

        title = "Event list (last "+str(noOfHistoricEventsToView)+"/" +\
            str(stats["stream_all_events_counter"])+" events)"
        width, height, table = createTable(eventTableRows,title)
        printTable(margin,nextUseableLineWholeScreen,table)

        # # # Get all available keys
        # stats =rtpStream.getRtpStreamStatsByFilter("stream")
        # for k in stats:
        #     print k,", ",
        # print "\r"
        stats = rtpStream.getRtpStreamStats()
        # print stats["stream_time_elapsed_total"].seconds, "\r"
        # print stats["stream_all_events_counter"], "\r"
        print "-----------------------------------------------------------------------------------------------------------------------", "\r"


        time.sleep(1)


# Define a thread that will trap keys pressed
def __catchKeyboardPresses(keyPressed):
    print "Starting __catchKeyboardPresses thread", "\r"
    while True:
        ch = getch()
        keyPressed[0] = ch
        time.sleep(0.2)


# define a traffic generator thread
def __rtpGenerator(keyPressed, UDP_TX_IP, UDP_TX_PORT, txRate, payloadLength):
    # UDP_DEST_IP = "127.0.0.1"
    # UDP__DEST_PORT = 5004
    txBps_1s = 0
    # Generate random string
    # Supposedly the max safe UDP payload over the internet is 508 bytes. Minus 12 bytes for the rtp header gives 496 available bytes
    # stringLength = payloadLength
    # Create string containing all uppercase and lowercase letters
    letters = string.ascii_letters
    # iterate over stringLength picking random letters from
    payload = ''.join(random.choice(letters) for i in range(payloadLength))

    txSock = socket.socket(socket.AF_INET,  # Internet
                           socket.SOCK_DGRAM)  # UDP
    print "Traffic Generator thread started. Sending to ", UDP_TX_IP, ":", UDP_TX_PORT, ", txRate:", txRate, "bps, payloadLength:", payloadLength, "\r"
    print "[spacebar] insert single packet loss, [z] Inhibit/Re-enable packet generation, [j] Toggle jitter on/off", "\r"

    rtpParams = 0b01000000
    rtpPayloadType = 0b00000000
    rtpSequenceNo = 65535
    # Create a 32 bit timestamp (needs truncating to 32 bits before passing to struct.pack)
    # 0xFFFFFFFF is 32 '1's, so the '&' operation will throw away MSBs larger than this
    rtpTimestamp = int(datetime.datetime.now().strftime("%H%M%S%f")) & 0xFFFFFFFF
    rtpSyncSourceIdentifier = 12345678

    enablePacketGeneration = True
    enableJitter = False

    # Caulculate tx period required to provide supplied txRate for a given stringLength
    # Note: This is an estimate because time.sleep() is inherently unreliable so we have
    # to recalculate once the generator is running by averaging over a 1 sec period
    txPeriod = payloadLength * 8.0 / txRate
    print "txPeriod", txPeriod, "\r"

    jitterPerecentage = 50
    maxDeviation = txPeriod * jitterPerecentage / 100

    # start elapsed timer
    startTime = timer()

    while True:
        # Start an execution timer (if we know the time required to construct the packet we can deduct this from the
        # txPeriod sleep time which should, in theory, reduce the jitter of the generator
        calculationStartTime = timer()

        # Construct 12 byte header
        txRtpHeader = struct.pack("!BBHLL", rtpParams, rtpPayloadType, rtpSequenceNo, rtpTimestamp,
                                  rtpSyncSourceIdentifier)
        MESSAGE = txRtpHeader + payload

        # If 'z' pressed, toggle packet generation on/off
        if (keyPressed[0] == 'z'):
            if (enablePacketGeneration == True):
                # Empty keyboard buffer
                keyPressed[0] = ''
                # Clear enable flag
                enablePacketGeneration = False
                print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), " 'z' Inhibiting packet generator\r"
            else:
                # Empty keyboard buffer
                keyPressed[0] = ''
                # Set enable flag
                enablePacketGeneration = True
                print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), " 'z' Enabling packet generator\r"
                # Restart the 1 second timer used for txData averaging
                startTime = timer()
        # Spacebar will introduce a single packet loss
        # If temporaryInhibit was set, clear it
        temporaryInhibit = False
        if (keyPressed[0] == ' '):
            # Clear keyboard buffer
            keyPressed[0] = ''
            temporaryInhibit = True
            print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "[Spacebar] - Inhibit single packet\r"

        # If all tx flags are set then transmit the rtp packet
        if enablePacketGeneration == True and temporaryInhibit == False:
            try:
                txSock.sendto(MESSAGE, (UDP_TX_IP, UDP_TX_PORT))
                # Update tx data counter (*8 converts bytes to bits)
                txBps_1s += len(payload) * 8
                # print rtpSequenceNo,txPeriod,txBps_1s,"\r"
            except Exception as e:
                print "__rtpGenerator()", str(e), "\r"
                exit()

        if (keyPressed[0] == 'j'):
            # Turn jitter on/off by pressing 'j'
            # Clear keyboard buffer
            keyPressed[0] = ''
            if enableJitter == False:
                enableJitter = True
                print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "[j] jitter enabled\r"
            else:
                enableJitter = False
                print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "[j] jitter disabled\r"

        # Increment rtp sequence number for next iteration of the loop
        rtpSequenceNo += 1
        # Seq no is only a 16 bit value, so reset at max value (65535)
        if rtpSequenceNo > 65535:
            rtpSequenceNo = 0
        # print "rtpSequenceNo",rtpSequenceNo,"\r"
        # If flag set, generate random delay centred around txPeriod (0.01 = 10mS period)
        if enableJitter == True:
            jitter = random.uniform(-1 * maxDeviation, maxDeviation)
        else:
            jitter = 0

        # Calculate (inevitable) error in tx rate (bps)
        # If there is an error between the desired tx speed and the actual tx speed (due to timing inaccuracies of the time.sleep() command)
        # dynamically modify the txPeriod to actually generate the desired rate
        # 1 second timer

        # Has 1 second elapsed?
        if (timer() - startTime) >= 1 and enablePacketGeneration == True:
            # Reset elapsed timer
            startTime = timer()
            # Test actual tx rate (averaged over a second) against 99% of desired tx rate
            if (txBps_1s < (0.99 * txRate)):
                # Data not being sent fast enough, so reduce txPeriod time
                # Measure difference between desired bps tx rate and actual bps tx rate
                txRateError = txRate - txBps_1s
                # Convert the difference a fraction by which will modify txPeriod
                errorFactor = (txRateError * 1.0 / txRate)
                # Modify txPeriod to compensate for error
                # Correction only happens in one direction (we can only dynamically reduce the txPeriod, so to prevent
                # overshoots of the desired rate, only reduce txPeriod by 'half' the error amount in one go
                txPeriod -= txPeriod * (errorFactor / 2.0)
                print "Compensating for timing error - Actual txData rate too low", "Desired tx rate:", txRate, "Actual tx rate:", txBps_1s, "\r"

            # Clear counter
            txBps_1s = 0

        # The calculation time will be deductced from the sleep time, which should make the generator
        # output less jittery (because the calculation time is taken into account)
        calculationPeriod = timer() - calculationStartTime

        compensatedTxPeriod = txPeriod + jitter - calculationPeriod
        # Have to guard against a negative time value
        if (compensatedTxPeriod > 0):
            # Sleep between packet transmision
            time.sleep(compensatedTxPeriod)
        else:
            # print "__rtpGenerator() - non-positive compensatedTxPeriod value",compensatedTxPeriod,"\r"
            pass

def __diskLoggerThread(rtpStream):
    # Autonomous thread to poll RtpStream eventList for new events
    # and write them  to disk
    print "diskLoggerThread starting\r"
    x = 0
    while True:
        print "\033[1;0HdiskLoggerThread",x,"\r"
        x += 1
        time.sleep(0.2)


####################################################################################


# Main prog starts here
# #####################
def main(argv):
    MODE = ""
    # Specify a default txRate of 1Mbps if no rate specified
    txRate = 1 * 1024 * 1024

    # Specify a default packet size for the tx stream (if none supplied)
    payloadLength = 496

    # print 'Argument List:', str(argv)
    try:
        # options are:
        # -h: help
        # -l: loopback mode
        # -t: transmit mode usage: address:port
        # -r receive mode usage: address:port
        # -b bandwidth (append k for kbps, m for mbps eg 1m or 500k). Default 1Mbps
        # -d udp packet size

        address = ""
        opts, args = getopt.getopt(argv, "hlt:r:i:t:b:d:")

        # Iterate over opts array and test opt. Then retrieve the corresponding arg
        for opt, arg in opts:
            if opt == '-h':
                print "Version 0.5\r"
                print "options are:\r"
                print "-h: help (this message)\r"
                print "-l: loopback mode\r"
                print "-t: transmit mode usage: address:port\r"
                print "-r receive mode usage: address:port\r"
                print "-b bandwidth (append k for kbps, m for mbps eg 1m or 500k). Default 1Mbps\r"
                print "-d rtp payload size (bytes)\r"
                exit()

            elif opt == '-l':
                MODE = "LOOPBACK"
                print MODE
                UDP_RX_IP = "127.0.0.1"
                UDP_RX_PORT = 5004
                UDP_TX_IP = "127.0.0.1"
                UDP_TX_PORT = 5004


            elif opt in ("-t"):
                MODE = "TRANSMIT"
                # check for two parameters seperated by a colon
                if len(arg.split(':')) == 2:
                    UDP_TX_IP = arg.split(':')[0]
                    UDP_TX_PORT = int(arg.split(':')[1])
                    # Validate supplied IP address
                    try:
                        socket.inet_aton(UDP_TX_IP)
                    except socket.error:
                        print "Invalid TRANSMIT IP address:port combinbation supplied:", arg
                        exit()
                    print MODE, UDP_TX_IP, UDP_TX_PORT
                else:
                    print "Invalid TRANSMIT IP address:port combinbation supplied:", arg
                    exit()

            elif opt in ("-r"):
                MODE = "RECEIVE"
                # check for two parameters seperated by a colon
                if len(arg.split(':')) == 2:
                    UDP_RX_IP = arg.split(':')[0]
                    UDP_RX_PORT = int(arg.split(':')[1])
                    # Validate supplied IP address
                    try:
                        socket.inet_aton(UDP_RX_IP)
                    except socket.error:
                        print "Invalid RECEIVE IP address:port combinbation supplied:", arg
                        exit()
                    print MODE, UDP_RX_IP, UDP_RX_PORT
                else:
                    print "Invalid RECEIVE IP address:port combinbation supplied:", arg
                    exit()

            elif opt in ("-b"):
                try:
                    # Use regex to split -b argument into numerical and string parts
                    splitArg = re.split('(\d+)', arg)
                    # Extract numerical part
                    x = int(splitArg[1])
                    # Extract string part
                    multiplier = splitArg[2]
                    print "x", x, "multiplier", multiplier
                    if multiplier == 'k' or multiplier == 'K':
                        txRate = x * 1024
                    elif multiplier == 'm' or multiplier == 'M':
                        txRate = x * 1024 * 1024
                    else:
                        print "Invalid -b bandwidth specfied. Unknown multiplier", multiplier
                        exit()
                except:
                    print "Invalid -b bandwidth specfied. Should be xy wheher x is anumerical value and y is k or m (kbps or mbps).", \
                        "If no multiplier supplied then assuming x mbps. eg. 500k, 1m, 5m etc"
                    exit()
                print "txRate", txRate

            elif opt in ("-d"):
                # Maximum Ethernet frame size is 1500 bytes (minus 12 bytes for the RTP header)
                MAX_PAYLOAD_SIZE_bytes = 1500 - 12
                MIN_PAYLOAD_SIZE_bytes = 20
                try:
                    if int(arg) > MAX_PAYLOAD_SIZE_bytes:
                        print  "requested payload size (", arg, ") exceeds maximum Ethernet frame size (1488 bytes with 12 byte RTP header), "
                        payloadLength = MAX_PAYLOAD_SIZE_bytes
                    elif int(arg) < MIN_PAYLOAD_SIZE_bytes:
                        print  "requested payload size (", arg, ") less than minimum permitted (", MIN_PAYLOAD_SIZE_bytes, ")"
                    else:
                        payloadLength = int(arg)
                except Exception as e:
                    print "Invalid payload size specified '", arg, "'"
                    exit()

    except getopt.GetoptError:
        print 'invalid options supplied', argv
        exit()

    # UDP_RX_IP = "192.168.56.1"
    # if MODE=='LOOPBACK':
    #
    # elif MODE=='RECEIVE':
    #     UDP_RX_PORT = 6100
    #     UDP_RX_IP = "172.26.203.1"

    runOnce = True

    # Create dummy list to allow 'pass by reference' (i.e a 'pointer')
    # The first (and only) item of this 'list' will be our pointer
    keyPressed = ['']

    # Start keyboard monitoring thread
    catchKeyboardPresses = threading.Thread(target=__catchKeyboardPresses, args=(keyPressed,))
    catchKeyboardPresses.daemon = True  # Thread will auto shutdown when the prog ends
    catchKeyboardPresses.start()

    if MODE == 'LOOPBACK' or MODE == 'TRANSMIT':
        # Start traffic generator thread
        rtpGenerator = threading.Thread(target=__rtpGenerator,
                                        args=(keyPressed, UDP_TX_IP, UDP_TX_PORT, txRate, payloadLength))
        rtpGenerator.daemon = True  # Thread will auto shutdown when the prog ends
        rtpGenerator.start()

    if MODE == 'RECEIVE' or MODE == 'LOOPBACK':

        # Create receive UDP socket
        sock = socket.socket(socket.AF_INET,  # Internet
                             socket.SOCK_DGRAM)  # UDP
        sock.bind((UDP_RX_IP, UDP_RX_PORT))
        while True:
            # recvfrom() returns two parameters, the src address:port (addr) and the actual data (data)
            data, addr = sock.recvfrom(4096)  # buffer size is 4096 bytes
            # print addr

            # Get timestamp at the point the packet was received
            timeNow = datetime.datetime.now()

            srcAddress = addr[0]
            srcPort = addr[1]

            # if (keyPressed[0]!=''):
            # 	print "keyPressed",keyPressed[0]
            # 	keyPressed[0]=''

            try:
                # Split rtp header into an array of values
                # print "received message:", hexData
                # RTP header is 12 bytes long. Unpack it as an array.
                # !=big endian, B=unsigned char(1), H=unsigned short(2), L=unsigned long(4)
                RTP_HEADER_SIZE = 12
                rtpHeader = struct.unpack("!BBHLL", data[:RTP_HEADER_SIZE])

                # Calculate the data payload size
                payloadSize = len(data) - RTP_HEADER_SIZE
                # print"Total data",len(data),"RTP Header size:",RTP_HEADER_SIZE," Payload size",payloadSize,

                # 	sequence no=rtpHeader[2]
                #	timestamp=rtpHeader[3]
                # 	sync-source identifier =rtpHeader[4]
                rtpSequenceNo = rtpHeader[2]
                rtpSyncSourceIdentifier = rtpHeader[4]

                if (runOnce == True):
                    # Create a new rtpStream object (but only once)
                    s = RtpStream(rtpSyncSourceIdentifier, srcAddress, srcPort, UDP_RX_IP, UDP_RX_PORT)

                    # Create a __displayThread. Pass the RtpStream object (s) to it
                    displayThread = threading.Thread(target=__displayThread, args=(s,))
                    displayThread.daemon = True  # Thread will auto shutdown when the prog ends
                    displayThread.start()

                    # Create a diskLogging Thread - pass rtpStream object to it
                    diskLoggerThread = threading.Thread(target=__diskLoggerThread, args=(s,))
                    diskLoggerThread.daemon = True # Thread will auto shutdown when the prog ends
                    diskLoggerThread.start()

                    runOnce = False

                # Add new data to rtpStream object rtpSequenceNo,payloadSize,timestamp, syncSource
                s.addData(rtpSequenceNo, payloadSize, timeNow, rtpSyncSourceIdentifier)


            except Exception as e:
                print str(e), "Length:", len(data), "bytes received"

    # Sit in endless loop
    while True:
        time.sleep(1)


# Invoke main() method (entry point for Python script)
if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    main(sys.argv[1:])
