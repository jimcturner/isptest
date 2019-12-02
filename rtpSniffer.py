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
        self.packetsLost = firstPackedReceivedAfterGap.rtpSequenceNo - lastReceivedPacketBeforeGap.rtpSequenceNo - 1
        # Calculate length of this glitch
        self.glitchLength = firstPackedReceivedAfterGap.timestamp - lastReceivedPacketBeforeGap.timestamp


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
        z=prevRtpPacket

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
            self.__stats["instantaneousJitter"]=self.rtpStream[-1].jitter - z.jitter
            self.__stats["meanRxPeriod"]=self.rtpStream[-1].timeDelta

        # Now attempt to detect excessive jitter by comparing the instantaneous value with the 10s averaged value
        # Check that 10s value has actually been calculated
        if self.__stats["meanJitter_10s"] > 0:
            if self.__stats["instantaneousJitter"] > (10 * self.__stats["meanJitter_10s"]):
                print "*******Excessive jitter", "\r"
                self.__eventList.append(ExcessiveJitter(self.rtpStream[-1], self.__stats["instantaneousJitter"],
                                                        self.__stats["meanJitter_1s"], self.__stats["meanJitter_10s"]))

    def __detectGlitches(self, lastReceivedRtpPacket):
        # Test for out of sequence packet by comparing last received sequence no with that of first rtpObject in new list of data in self.rtpStream[]
        # Inhibit this for the first second (because there's nothing to compare the first packet to)
        if (lastReceivedRtpPacket.rtpSequenceNo != (self.rtpStream[0].rtpSequenceNo - 1)) and self.__stats["secondsElapsed"] > 0:
            print "self.__stats[totalPacketsReceived]",self.__stats["totalPacketsReceived"],"\r"
            # Take timestamp of most recent glitch
            self.__stats["timestampOfLastGlitch"] = datetime.datetime.now()
            print self.__stats[
                "timestampOfLastGlitch"], " Out of sequence packet received between data sets. Expected sequence no", (
                    lastReceivedRtpPacket.rtpSequenceNo + 1), " but received ", self.rtpStream[0].rtpSequenceNo, "\r"
            # Capture packets either side of the 'hole' and store them in the event list
            # Create an object representing the glitch
            glitch = Glitch(lastReceivedRtpPacket, self.rtpStream[0])
            # Add the latest glitch to the evenList[]
            self.__eventList.append(glitch)
            # Now update aggregate glitch stats
            self.__stats["totalPacketsLost"] += glitch.packetsLost
            self.__stats["totalGlitchLength"] += glitch.glitchLength
            self.__stats["totalGlitches"] += 1

            #Finally, reset min/max/range jitter values as they're corrupted by a glitch
            self.__stats["minJitter"] = 0
            self.__stats["maxJitter"] = 0
            self.__stats["rangeOfJitter"] = 0

        # Now test for sequence errors within current data set
        # Take a copy of the first item in the list
        prevRtpPacket = self.rtpStream[0]
        # Iterate over the the remainder of the list (starting at index 1 to the end '-1')
        for rtpPacket in self.rtpStream[1:]:
            # Test sequence no of current packet against previous packet
            if rtpPacket.rtpSequenceNo != (prevRtpPacket.rtpSequenceNo + 1):
                # Take timestamp of most recent glitch
                self.__stats["timestampOfLastGlitch"] = datetime.datetime.now()
                print self.__stats[
                    "timestampOfLastGlitch"], " Out of sequence packet received (within current data set). Expected sequence no", (
                        prevRtpPacket.rtpSequenceNo + 1), " but received ", rtpPacket.rtpSequenceNo, "\r"

                # Capture packets either side of the 'hole' and store them in the event list
                # Create an object representing the glitch
                glitch = Glitch(prevRtpPacket, rtpPacket)
                # Add the glitch to the evenList[]
                self.__eventList.append(glitch)
                # Now update aggregate glitch stats
                self.__stats["totalPacketsLost"] += glitch.packetsLost
                self.__stats["totalGlitchLength"] += glitch.glitchLength
                self.__stats["totalGlitches"] += 1

                # Finally, reset min/max/range jitter values as they're corrupted by a glitch
                self.__stats["minJitter"] = 0
                self.__stats["maxJitter"] = 0
                self.__stats["rangeOfJitter"] = 0
            # Store current rtp packet for the next iteration around the loop
            prevRtpPacket = rtpPacket

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
        lossOfStreamTimerStart=datetime.timedelta()

        runningTotalPacketsPerSecond = 0
        runningTotalDataReceivedPerSecond = 0

        self.__stats["totalPacketsPerSecond"] = 0
        self.__stats["totalDataReceivedPerSecond"] = 0
        self.__stats["totalDataReceived"] = 0
        self.__stats["totalPacketsReceived"] = 0
        self.__stats["secondsElapsed"] = 0

        # Glitch counters
        self.__stats["totalPercentPacketsLost"] = 0
        self.__stats["totalPacketsLost"] = 0
        self.__stats["totalGlitches"] = 0
        # define timedelta object to store an aggregate of of Glitch length
        self.__stats["totalGlitchLength"] = datetime.timedelta()
        self.__stats["timestampOfLastGlitch"] = datetime.timedelta()
        self.__stats["timeElapsedSinceLastGlitch"] = datetime.timedelta()

        # Jitter counters
        self.__stats["minJitter"] = 0
        self.__stats["maxJitter"] = 0
        self.__stats["rangeOfJitter"] = 0
        self.__stats["instantaneousJitter"] = 0
        self.__stats["meanJitter_1s"] = 0

        # averageRtpPacketArrivalPeriod = datetime.timedelta()
        self.__stats["processorUtilisationPercent"] = 0
        historicJitter = []
        self.__stats["meanJitter_10s"] = 0
        # Declare flags
        lossOfStreamFlag = True
        possibleLossOfStreamFlag = False
        lossOfStreamAlarmThreshold = 2

        self.__stats["POLL_INTERVAL"] = 0.001  # Loop will execute every 10mS

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
                #lossOfStreamTimer += 1

                if possibleLossOfStreamFlag == False:
                    # Set the flag
                    possibleLossOfStreamFlag = True
                    # And start the lossOfStream Timer
                    lossOfStreamTimerStart=datetime.datetime.now()

                if (datetime.datetime.now()-lossOfStreamTimerStart).seconds >= lossOfStreamAlarmThreshold \
                        and lossOfStreamFlag == False and self.__stats["totalPacketsReceived"] > 0:
                    # Set flag
                    lossOfStreamFlag = True
                    # Add event to the list (but only do this once)
                    self.__eventList.append(StreamLost(lastReceivedRtpPacket))

            # Calculate elapsed since last glitch
            # But only if there has actually been a glitch
            if self.__stats["totalGlitches"] > 0:
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
                self.__stats["secondsElapsed"] += 1
                # Take snapshots of running totals
                self.__stats["totalPacketsPerSecond"] = runningTotalPacketsPerSecond
                self.__stats["totalDataReceivedPerSecond"] = runningTotalDataReceivedPerSecond
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

                # Now clear totalDataReceivedPerInterval for the next time around the loop
                # self.__stats["totalDataReceivedPerSecond"] = 0
                # self.__stats["totalPacketsPerSecond"] = 0

            # Calculate how long it has taken for the stats analysis to have been performed
            calculationEndTime = datetime.datetime.now()
            try:
                # Take the calculation time in microseconds and combine with the period between
                # packets arriving to work out how much processor headroom there is
                # If the processor can't keep up, generate an event
                self.__stats["calculationDuration"] = (calculationEndTime - calculationStartTime).microseconds
                self.__stats["processorUtilisationPercent"] = \
                    self.__stats["calculationDuration"] * 100 / self.__stats["meanRxPeriod"]

                # If the CPU is >99% utilised, add event to the list (but only do this once)
                if self.__stats["processorUtilisationPercent"] > 99:
                    self.__eventList.append(ProcessorOverload(lastReceivedRtpPacket))
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

    while True:
        for x, y in rtpStream.getRtpStreamStats().items():
            print x, y, "\r"
            # pass
        print "--------------------", "\r"
        for event in rtpStream.getRTPStreamEventList():
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
def __rtpGenerator(keyPressed):
    # UDP_DEST_IP = "192.168.56.1"
    UDP_DEST_IP = "127.0.0.1"
    UDP__DEST_PORT = 5004

    # Generate random string
    # Supposedly the max safe UDP payload over the internet is 508 bytes. Minus 12 bytes for the rtp header gives 496 available bytes
    stringLength = 496
    # Create string containing all uppercase and lowercase letters
    letters = string.ascii_letters
    # iterate over stringLength picking random letters from
    payload = ''.join(random.choice(letters) for i in range(stringLength))

    txSock = socket.socket(socket.AF_INET,  # Internet
                           socket.SOCK_DGRAM)  # UDP
    print "Traffic Generator thread started"

    rtpParams = 0b01000000
    rtpPayloadType = 0b00000000
    rtpSequenceNo = 0
    # Create a 32 bit timestamp (needs truncating to 32 bits before passing to struct.pack)
    # 0xFFFFFFFF is 32 '1's, so the '&' operation will throw away MSBs larger than this
    rtpTimestamp = int(datetime.datetime.now().strftime("%H%M%S%f")) & 0xFFFFFFFF
    rtpSyncSourceIdentifier = 12345678

    enablePacketGeneration = True
    enableJitter = False

    txPeriod = 0.001
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
                print " 'z' Inhibiting packet generator"
            else:
                # Empty keyboard buffer
                keyPressed[0] = ''
                # Set enable flag
                enablePacketGeneration = True

        # Spacebar will introduce a single packet loss
        # If temporaryInhibit was set, clear it
        temporaryInhibit = False
        if (keyPressed[0] == ' '):
            # Clear keyboard buffer
            keyPressed[0] = ''
            temporaryInhibit = True
            print "[Spacebar] - Inhibit single packet\r"

        # If all tx flags are set then transmit the rtp packet
        if enablePacketGeneration == True and temporaryInhibit == False:
            txSock.sendto(MESSAGE, (UDP_DEST_IP, UDP__DEST_PORT))

        if (keyPressed[0] == 'j'):
            # Turn jitter on/off by pressing 'j'
            # Clear keyboard buffer
            keyPressed[0] = ''
            if enableJitter == False:
                enableJitter = True
                print "[j] jitter enabled", "\r"
            else:
                enableJitter = False
                print "[j] jitter disabled", "\r"

        # Increment rtp sequence number for next iteration of the loop
        rtpSequenceNo += 1
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
def main():
    # UDP_RX_IP = "192.168.56.1"
    UDP_RX_IP = "127.0.0.1"
    UDP_RX_PORT = 5004

    sock = socket.socket(socket.AF_INET,  # Internet
                         socket.SOCK_DGRAM)  # UDP
    sock.bind((UDP_RX_IP, UDP_RX_PORT))

    runOnce = True

    # Create dummy list to allow 'pass by reference' (i.e a 'pointer')
    # The first (and only) item of this 'list' will be our pointer
    keyPressed = ['']

    # Start keyboard monitoring thread
    catchKeyboardPresses = threading.Thread(target=__catchKeyboardPresses, args=(keyPressed,))
    catchKeyboardPresses.daemon = True  # Thread will auto shutdown when the prog ends
    catchKeyboardPresses.start()

    # Start traffic generator thread
    rtpGenerator = threading.Thread(target=__rtpGenerator, args=(keyPressed,))
    rtpGenerator.daemon = True  # Thread will auto shutdown when the prog ends
    rtpGenerator.start()

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


# Invoke main() method (entry point for Python script)
if __name__ == "__main__":
    main()
