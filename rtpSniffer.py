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


####################################################################################

# Define an object to hold data about an individual received rtp packet
class RtpData(object):
    # Constructor method
    def __init__(self, rtpSequenceNo, payloadSize, timestamp):
        self.rtpSequenceNo = rtpSequenceNo
        self.payloadSize = payloadSize
        self.timestamp = timestamp
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
    def __init__(self, firstPacketReceived):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        self.firstPacketdReceived = firstPacketReceived


# Define an event that represents a loss of rtpStream
class StreamLost(object):
    # Define descriptive names. These might be useful later
    type = "StreamLost"
    description = ""

    # Constructor
    def __init__(self, lastPacketReceived):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        self.lastPacketReceived = lastPacketReceived


# Define an event object that represents a excessive jitter event
class ExcessiveJitter(object):
    # Define descriptive names. These might be useful later
    type = "ExcessiveJitter"
    description = ""

    def __init__(self, lastPacketReceived, instantaneousJitter, meanJitter_1s, meanJitter_10s):
        self.timeCreated = datetime.datetime.now()
        self.lastPacketReceived = lastPacketReceived
        self.instantaneousJitter = instantaneousJitter
        self.meanJitter_1s = meanJitter_1s
        self.meanJitter_10s = meanJitter_10s


# Define an event object that represents a procesor overload. This might happen if the calculateThread can't process
# incoming packets fast enough
class ProcessorOverload(object):
    # Define descriptive names. These might be useful later
    type = "ProcessorOverload"
    description = ""

    def __init__(self, lastPacketReceived):
        self.timeCreated = datetime.datetime.now()
        self.lastPacketReceived = lastPacketReceived


# Define an event that represent a glitch
# This will be in the form of the packets (RtpData objects) either side of the 'hole' in received data
class Glitch(object):
    # Define descriptive names. These might be useful later
    type = "Glitch"
    description = ""

    # Constructor
    def __init__(self, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap):
        # Create timestamp of event
        self.timeCreated = datetime.datetime.now()
        # Update instance variables
        self.startOfGap = lastReceivedPacketBeforeGap
        self.endOfGap = firstPackedReceivedAfterGap
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


# Define a class to represent a flow of received rtp packets (and associated stats)
class RtpStream(object):
    # Constructor method.
    # The RtpStream object should be created with a unique id no
    # (for instance the rtp sync-source value would be perfect)
    def __init__(self, id, srcAddress, srcPort):
        # Assign to instance variable
        self.__streamID = id
        self.srcAddress = srcAddress
        self.srcPort = srcPort

        print "creating RtpStream with id:", self.__streamID, "\r"

        # Create a mutex lock to be used by the a thread
        # To set the lock use: __accessRtpDataMutex.acquire(), To release use: __accessRtpDataMutex.release()
        self.__accessRtpDataMutex = threading.Lock()
        self.__accessRtpStreamStatsMutex = threading.Lock()
        self.__accessRtpStreamEventListMutex = threading.Lock()

        # Create empty list to hold rtp stream data as it is received by the socket
        self.rtpStreamData = []

        # Create private empty dictionary to hold stats for this RtpStream object. Accessible via a getter method
        self.__stats = {}

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
            if self.__stats["totalPacketsReceived"] > 10:
                if self.__stats["minJitter"] == 0:
                    # Set initial value
                    self.__stats["minJitter"] = y.jitter
                if y.jitter < self.__stats["minJitter"]:
                    self.__stats["minJitter"] = y.jitter
                # Calculate maximum jitter
                if self.__stats["maxJitter"] == 0:
                    # Set initial value
                    self.__stats["maxJitter"] = y.jitter
                if y.jitter > self.__stats["maxJitter"]:
                    self.__stats["maxJitter"] = y.jitter
                self.__stats["rangeOfJitter"] = self.__stats["maxJitter"] - self.__stats["minJitter"]

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
            self.__stats["instantaneousJitter"] = sumOfInterPacketJitter / (len(self.rtpStream) - 1)
            self.__stats["meanRxPeriod"] = sumOfTimeDeltas / (len(self.rtpStream) - 1)
        else:
            # This batch of data only contains a single packet.
            # as this requires at least two packets worth of data (the difference of a difference!)
            # The meanRxPeriod is possible to deduce by comparing this new single packet with the last received
            self.__stats["instantaneousJitter"] = self.rtpStream[-1].jitter - z.jitter
            self.__stats["meanRxPeriod"] = self.rtpStream[-1].timeDelta.microseconds

        # Now attempt to detect excessive jitter by comparing the instantaneous value with the long term value
        # Check that long term value has actually been calculated
        if self.__stats["longTermJitter_uS"] > 0:
            if self.__stats["meanJitter_1s"] > \
                    (self.excessJitterThresholdFactor * self.__stats["longTermJitter_uS"]):

                # If jitter alarms not inhibited, add a new jitter event
                # Take diff between time.now() and the time of the last event
                if self.__stats["timeElapsedSinceLastExcessJitter"].seconds > \
                        self.__stats["excessiveJitterAlarmTimeout"]:
                    self.__eventList.append(ExcessiveJitter(self.rtpStream[-1], self.__stats["instantaneousJitter"],
                                                            self.__stats["meanJitter_1s"],
                                                            self.__stats["meanJitter_10s"]))

                # Update the event counter for Excess Jitter
                self.__stats["totalExcessJitterEvents"] += 1

                # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean period between events)
                self.sumOfTimeElapsedSinceLastExcessJitterEvents += self.__stats["timeElapsedSinceLastExcessJitter"]

                # Take timestamp fo this (the most recent) Excess Jitter event
                self.__stats["timeofLastExcessJitterEvent"] = datetime.datetime.now()
        # Now update the self.__stats["timeElapsedSinceLastExcessJitter"] timer
        if self.__stats["totalExcessJitterEvents"] > 0:
            self.__stats["timeElapsedSinceLastExcessJitter"] = datetime.datetime.now() - \
                                                               self.__stats["timeofLastExcessJitterEvent"]

        # Calculate meanTimeBetweenExcessJitterEvents (requires at least two jitter events)
        if self.__stats["totalExcessJitterEvents"] > 1:
            self.__stats["meanTimeBetweenExcessJitterEvents"] = \
                (self.sumOfTimeElapsedSinceLastExcessJitterEvents + self.__stats["timeElapsedSinceLastExcessJitter"]) / \
                self.__stats["totalExcessJitterEvents"]

    def __detectGlitches(self, lastReceivedRtpPacket):
        # Test for out of sequence packet by comparing last received sequence no with that of first rtpObject in new list of data in self.rtpStream[]
        # Inhibit this for the first second (because there's nothing to compare the first packet to)
        # Also, when the seq no hits 65535 it will wrap around to zero giving a false diff. Musn't interpret this as a glitch
        if lastReceivedRtpPacket.rtpSequenceNo == 65535:
            lastReceivedRtpPacket.rtpSequenceNo = -1

        if (lastReceivedRtpPacket.rtpSequenceNo != (self.rtpStream[0].rtpSequenceNo - 1)) and \
                self.__stats["timeElapsed"].seconds > 0:
            # Take timestamp of most recent glitch
            self.__stats["timestampOfLastGlitch"] = datetime.datetime.now()

            # Capture packets either side of the 'hole' and store them in the event list
            # Create an object representing the glitch
            glitch = Glitch(lastReceivedRtpPacket, self.rtpStream[0])
            # Add the latest glitch to the evenList[]
            self.__eventList.append(glitch)
            # Now update aggregate glitch stats
            self.__stats["totalPacketsLost"] += glitch.packetsLost
            self.__stats["totalGlitchLength"] += glitch.glitchLength
            self.__stats["totalGlitches"] += 1

            # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean)
            self.sumOfTimeElapsedSinceLastGlitch += self.__stats["timeElapsedSinceLastGlitch"]

            # Finally, reset min/max/range jitter values as they're corrupted by a glitch
            self.__stats["minJitter"] = 0
            self.__stats["maxJitter"] = 0
            self.__stats["rangeOfJitter"] = 0

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
                self.__stats["timestampOfLastGlitch"] = datetime.datetime.now()

                # Capture packets either side of the 'hole' and store them in the event list
                # Create an object representing the glitch
                glitch = Glitch(prevRtpPacket, rtpPacket)
                # Add the glitch to the evenList[]
                self.__eventList.append(glitch)
                # Now update aggregate glitch stats
                self.__stats["totalPacketsLost"] += glitch.packetsLost
                self.__stats["totalGlitchLength"] += glitch.glitchLength
                self.__stats["totalGlitches"] += 1

                # Take snapshot of new time delta and add to the sum of existing values (to calcaulate mean)
                self.sumOfTimeElapsedSinceLastGlitch += self.__stats["timeElapsedSinceLastGlitch"]

                # Finally, reset min/max/range jitter values as they're corrupted by a glitch
                self.__stats["minJitter"] = 0
                self.__stats["maxJitter"] = 0
                self.__stats["rangeOfJitter"] = 0

            # Store current rtp packet for the next iteration around the loop
            prevRtpPacket = rtpPacket

        if self.__stats["totalGlitches"] > 1:
            # Calculate mean of new and prev value
            self.__stats["meanTimeBetweenGlitches"] = \
                (self.sumOfTimeElapsedSinceLastGlitch + self.__stats["timeElapsedSinceLastGlitch"]) / \
                self.__stats["totalGlitches"]

    # Define a private calculation method that will run autonomously as a thread
    # This thread will
    def __calculateThread(self):
        print "__calculateThread started with id: ", self.__streamID, "\r"

        # Prev timestamp doesn't exist yet as this is the first packet, so create datetime object with value 0
        lastReceivedRtpPacket = RtpData(0, 0, datetime.timedelta())
        self.__stats["firstPacketReceivedAtTimestamp"] = datetime.timedelta()

        # General Counters
        loopCounter = 0
        # Start the loop timer (used to provide a 1sec interval)
        loopTimerStart = datetime.datetime.now()
        # Timer used to detect loss of streams against an alarm threshold
        lossOfStreamTimerStart = datetime.timedelta()

        runningTotalPacketsPerSecond = 0
        runningTotalDataReceivedPerSecond = 0

        self.__stats["totalPacketsPerSecond"] = 0
        self.__stats["totalDataReceivedPerSecond"] = 0
        self.__stats["totalDataReceived"] = 0
        self.__stats["averagePayloadSizePerSecond"] = 0
        self.__stats["totalPacketsReceived"] = 0
        self.__stats["timeElapsed"] = datetime.timedelta()

        # Glitch counters
        self.__stats["totalPercentPacketsLost"] = 0
        self.__stats["totalPacketsLost"] = 0
        self.__stats["totalGlitches"] = 0
        # define timedelta object to store an aggregate of of Glitch length
        self.__stats["totalGlitchLength"] = datetime.timedelta()
        self.__stats["timestampOfLastGlitch"] = datetime.timedelta()
        self.__stats["timeElapsedSinceLastGlitch"] = datetime.timedelta()
        self.__stats["meanTimeBetweenGlitches"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastGlitch = datetime.timedelta()

        # Jitter counters
        self.__stats["minJitter"] = 0
        self.__stats["maxJitter"] = 0
        self.__stats["rangeOfJitter"] = 0
        self.__stats["instantaneousJitter"] = 0
        self.__stats["meanJitter_1s"] = 0
        self.__stats["meanJitter_10s"] = 0
        self.__stats["longTermJitter_uS"] = 0
        self.__stats["processorUtilisationPercent"] = 0
        historicJitter = []
        sumOfJitter_1s = 0

        # % deviation from longTermJitter_uS that will trigger an excessJitterEvent
        self.__stats["excessJitterThresholdPercent"] = 15
        self.excessJitterThresholdFactor = 1.0 + (self.__stats["excessJitterThresholdPercent"] / 100.0)

        # No of seconds to inhibit an excessive jitter alarm
        self.__stats["excessiveJitterAlarmTimeout"] = 2
        self.__stats["timeElapsedSinceLastExcessJitter"] = datetime.timedelta()
        self.__stats["timeofLastExcessJitterEvent"] = datetime.timedelta()
        self.__stats["totalExcessJitterEvents"] = 0
        self.__stats["meanTimeBetweenExcessJitterEvents"] = datetime.timedelta()
        self.sumOfTimeElapsedSinceLastExcessJitterEvents = datetime.timedelta()

        # Declare flags
        lossOfStreamFlag = True
        possibleLossOfStreamFlag = False
        lossOfStreamAlarmThreshold = 2

        self.__stats["POLL_INTERVAL"] = 0.1  # Loop will execute every 10mS

        # Calculate the no of loops equating to a second
        loopsPerSecond = 1 / self.__stats["POLL_INTERVAL"]

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
            calculationStartTime = datetime.datetime.now()
            # Lock self.__stats and self.__eventList mutexes
            self.__accessRtpStreamStatsMutex.acquire()
            self.__accessRtpStreamEventListMutex.acquire()
            # Test for new data
            if len(self.rtpStream) > 0:
                # Data is present
                # Take timestamp of the very first packet received of this rtpStream
                if self.__stats["totalPacketsReceived"] < 1:
                    self.__stats["firstPacketReceivedAtTimestamp"] = self.rtpStream[0].timestamp
                    # Add a StreamStarted event to the event list
                    self.__eventList.append(StreamStarted(self.rtpStream[0]))
                # Stream now being received so clear flag

                if lossOfStreamFlag == True:
                    # We're now receiving a stream, so clear alarm flag
                    lossOfStreamFlag = False

                if possibleLossOfStreamFlag == True:
                    possibleLossOfStreamFlag = False

                # Get copy of final packet of prev data set
                if (self.__stats["totalPacketsReceived"] < 1):
                    # For the very first packet, take the prev packet to be that of the first packet received (to give a
                    # delta of zero, otherwise the delta will be the diff between 0 and today's date!
                    # prevRtpPacket=self.rtpStream[0]
                    lastReceivedRtpPacket = self.rtpStream[0]

                # Calculate and update per second and aggregate data counters
                for x in self.rtpStream:
                    # Per second counter
                    runningTotalDataReceivedPerSecond += x.payloadSize
                    # Total aggregate
                    self.__stats["totalDataReceived"] += x.payloadSize

                # Calculate and update per second and aggregate packet counters
                # Per second counter
                runningTotalPacketsPerSecond += len(self.rtpStream)
                # Total aggregate
                self.__stats["totalPacketsReceived"] += len(self.rtpStream)

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
                    lossOfStreamTimerStart = datetime.datetime.now()

                if (datetime.datetime.now() - lossOfStreamTimerStart).seconds >= lossOfStreamAlarmThreshold \
                        and lossOfStreamFlag == False and self.__stats["totalPacketsReceived"] > 0:
                    # Set flag
                    lossOfStreamFlag = True
                    # Add event to the list (but only do this once)
                    self.__eventList.append(StreamLost(lastReceivedRtpPacket))
                    # Finally, reset min/max/range jitter values as they're corrupted by a loss of signal
                    self.__stats["minJitter"] = 0
                    self.__stats["maxJitter"] = 0
                    self.__stats["rangeOfJitter"] = 0

            # Calculate elapsed since last glitch
            # But only if there has actually been a glitch in the past to measure against
            if self.__stats["totalGlitches"] > 0:
                # Calculate new value
                self.__stats["timeElapsedSinceLastGlitch"] = datetime.datetime.now() - self.__stats[
                    "timestampOfLastGlitch"]

            # Calculate % packet loss
            if self.__stats["totalPacketsReceived"] > 0:
                totalExpectedPackets = self.__stats["totalPacketsReceived"] + self.__stats["totalPacketsLost"]
                self.__stats["totalPercentPacketsLost"] = self.__stats["totalPacketsLost"] * 100 / totalExpectedPackets

            # 1 second timer
            if (datetime.datetime.now() - loopTimerStart).seconds >= 1:
                # Reset loop timer starting reference
                loopTimerStart = datetime.datetime.now()
                # Increment seconds elapsed
                self.__stats["timeElapsed"] += datetime.timedelta(seconds=1)
                # Take snapshots of running totals
                self.__stats["totalPacketsPerSecond"] = runningTotalPacketsPerSecond
                self.__stats["totalDataReceivedPerSecond"] = runningTotalDataReceivedPerSecond

                # Calculate self.__stats["averagePayloadSizePerSecond"]
                if self.__stats["totalPacketsPerSecond"] > 0:
                    self.__stats["averagePayloadSizePerSecond"] = \
                        self.__stats["totalDataReceivedPerSecond"] / self.__stats["totalPacketsPerSecond"]
                # Clear running totals
                runningTotalPacketsPerSecond = 0
                runningTotalDataReceivedPerSecond = 0

                # Calculate 1 second jitter
                if self.__stats["totalPacketsPerSecond"] > 0:
                    self.__stats["meanJitter_1s"] = self.sumOfJitter_1s / self.__stats["totalPacketsPerSecond"]
                # Reset self.sumOfJitter_1s
                self.sumOfJitter_1s = 0

                # Calculate 10s jitter moving average using a 10 element array of the prev 10 1s values
                # Add the latest 1s jitter value to the moving 10s jitter results array
                historicJitter.append(self.__stats["meanJitter_1s"])
                # Calculate a long-term jitter value by averaging all meanJitter_1s value over time elapsed
                sumOfJitter_1s += self.__stats["meanJitter_1s"]
                self.__stats["longTermJitter_uS"] = sumOfJitter_1s / self.__stats["timeElapsed"].seconds
                prevMeanJitter_10s = self.__stats["meanJitter_10s"]
                # Check that we have enough results (10s worth) to calculate the 10s value
                if len(historicJitter) > 10:
                    # Remove the oldest value
                    historicJitter.remove(historicJitter[0])
                    # Clear sum var prior to recalculation of mean
                    sumOfJitter_10s = 0
                    # Calculate mean of previous 10 1s jitter values
                    for x in historicJitter:
                        sumOfJitter_10s += x
                    self.__stats["meanJitter_10s"] = sumOfJitter_10s / len(historicJitter)

                # Dynamically modify POLL_INTERVAL based on a value of 10 times the Rx packet rate
                # This will ensure that self.rtpStream[] length never gets too large.
                # Otherwise, for high packet receieve rates, the calculation time will become excessive
                # Wait a second, in order to know we're in a steady state
                if self.__stats["meanRxPeriod"] > 0 and self.__stats["timeElapsed"].seconds > 1:
                    self.__stats["POLL_INTERVAL"] = 10.0 * self.__stats["meanRxPeriod"] / 1000000.0

            # Calculate how long it has taken for the stats analysis to have been performed
            calculationEndTime = datetime.datetime.now()
            try:
                # Take the calculation time in microseconds and combine with the period between
                # packets arriving multiplied by the no of packets in this batch of rtpStream
                # to work out how much processor headroom there is (as a ratio of times).
                # If the total calculation time for rtpStream[] is > than the gap between packets
                # arriving then the the processor can't keep up, so generate an event
                # This is to guard against false-postives
                self.__stats["calculationDuration"] = (calculationEndTime - calculationStartTime).microseconds

                self.__stats["processorUtilisationPercent"] = \
                    self.__stats["calculationDuration"] * 100 / (self.__stats["meanRxPeriod"] * len(self.rtpStream))

                # If the CPU is >99% utilised, add event to the list (but only do this once)
                if self.__stats["processorUtilisationPercent"] > 99:
                    self.__eventList.append(ProcessorOverload(lastReceivedRtpPacket))
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

            time.sleep(self.__stats["POLL_INTERVAL"])

    # Define getter methods
    def getRTPStreamID(self):
        return self.__streamID

    # Thread-safe method for accessing realtime RtpStream stats
    def getRtpStreamStats(self):
        self.__accessRtpStreamStatsMutex.acquire()
        stats = self.__stats.copy()
        self.__accessRtpStreamStatsMutex.release()
        return stats

    # Thread-safe method for accessing realtime RtpStream eventList
    def getRTPStreamEventList(self):
        self.__accessRtpStreamEventListMutex.acquire()
        eventList = list(self.__eventList)
        self.__accessRtpStreamEventListMutex.release()
        return eventList

    # Define setter methods
    def addData(self, rtpSequenceNo, payloadSize, timestamp):
        self.rtpSequenceNo = rtpSequenceNo
        self.payloadSize = payloadSize
        self.timestamp = timestamp
        # print "addData():",self.rtpSequenceNo,self.payloadSize,self.timestamp

        # Create a new rtp data object to hold the rtp packet data
        newData = RtpData(rtpSequenceNo, payloadSize, timestamp)

        # NOW ADD DATA TO A LIST

        # Lock the access mutex
        self.__accessRtpDataMutex.acquire()
        # Add the  RtpData obect containing the latest packet info, to the rtpStreamData[] list
        self.rtpStreamData.append(newData)
        # Release the mutex
        self.__accessRtpDataMutex.release()
        # Now we've added the newData object to the list rtpStreamData[] we cab delete the newData object
        del newData


# Define a display thread that will run autonomously
def __displayThread(rtpStream):
    print "__displayThread started with id: ", rtpStream.getRTPStreamID(), "\r"

    tabCounter = 0
    columns = 2
    while True:
        # Get keys/values from rtpStream
        items = rtpStream.getRtpStreamStats().items()
        # Clear screen and move cursor to origin
        print"\033[2J"
        # Clear tabCounter
        tabCounter = 0
        print len(items), "\r"
        for x, y in items:
            if x == "totalDataReceivedPerSecond":
                # Convert received rate from bytes/sec to bits/sec
                rxRate = y * 8
                friendlyValue = 0
                if rxRate < 1024:
                    suffix = "bps"
                elif rxRate <= 1048576:
                    suffix = "kbps"
                    friendlyValue = rxRate / 1024.0
                else:
                    suffix = "Mbps"
                    friendlyValue = rxRate / 1048576.0
                # print x,friendlyValue,suffix,": (",y,")","\r"
                print x, round(friendlyValue, 2), suffix, "\t\t\t\t\t",

            else:
                print x, y, "\t\t\t\t\t",
            # Increment tab counter
            tabCounter += 1
            # If we've exceeded the number of columbs, print a carriage return
            if (tabCounter % columns) >= (columns - 1):
                print "\r"
        print "\r--------------------", "\r"
        for event in rtpStream.getRTPStreamEventList():
            if event.type == 'Glitch':
                print event.type, event.timeCreated, "Expected:", event.expectedSequenceNo, ", Received", event.actualReceivedSequenceNo, "\r"
            else:
                print event.type, event.timeCreated, "\r"
            # pass
        print "------------------------------------------", "\r"
        time.sleep(1)


# Define a thread that will trap keys pressed
def __catchKeyboardPresses(keyPressed):
    print "Starting __catchKeyboardPresses thread", "\r"
    while True:
        ch = getch()
        keyPressed[0] = ch
        time.sleep(0.2)


# define a traffic generator thread
def __rtpGenerator(keyPressed, UDP_TX_IP, UDP_TX_PORT):
    # UDP_DEST_IP = "127.0.0.1"
    # UDP__DEST_PORT = 5004

    # Generate random string
    # Supposedly the max safe UDP payload over the internet is 508 bytes. Minus 12 bytes for the rtp header gives 496 available bytes
    stringLength = 496
    # Create string containing all uppercase and lowercase letters
    letters = string.ascii_letters
    # iterate over stringLength picking random letters from
    payload = ''.join(random.choice(letters) for i in range(stringLength))

    txSock = socket.socket(socket.AF_INET,  # Internet
                           socket.SOCK_DGRAM)  # UDP
    print "Traffic Generator thread started", "\r"
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

    txPeriod = 0.0001
    jitterPerecentage = 50
    maxDeviation = txPeriod * jitterPerecentage / 100

    while True:

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
            txSock.sendto(MESSAGE, (UDP_TX_IP, UDP_TX_PORT))

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
        # print "txPeriod",txPeriod+jitter,"\r"
        time.sleep(txPeriod + jitter)


####################################################################################


# Main prog starts here
# #####################
def main(argv):
    MODE = ""

    # print 'Argument List:', str(argv)
    try:
        # options are:
        # h: help
        # l: loopback mode
        # -t: transmit mode usage: address:port
        # -r receive mode usage: address:port

        address = ""
        opts, args = getopt.getopt(argv, "hlt:r:i:t:")

        # Iterate over opts array and test opt. Then retrieve the corresponding arg
        for opt, arg in opts:
            if opt == '-h':
                print "help"
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
        rtpGenerator = threading.Thread(target=__rtpGenerator, args=(keyPressed, UDP_TX_IP, UDP_TX_PORT))
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
                    s = RtpStream(rtpSyncSourceIdentifier, srcAddress, srcPort)

                    # Create a __displayThread. Pass the RtpStream object (s) to it
                    displayThread = threading.Thread(target=__displayThread, args=(s,))
                    displayThread.daemon = True  # Thread will auto shutdown when the prog ends
                    displayThread.start()

                    runOnce = False

                # Add new data to rtpStream object rtpSequenceNo,payloadSize,timestamp
                s.addData(rtpSequenceNo, payloadSize, timeNow)


            except Exception as e:
                print str(e), "Length:", len(data), "bytes received"

    # Sit in endless loop
    while True:
        time.sleep(1)


# Invoke main() method (entry point for Python script)
if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    main(sys.argv[1:])
