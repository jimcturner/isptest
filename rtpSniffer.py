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
		self.firstPacketdReceived=firstPacketReceived

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
	def __init__(self, lastPacketReceived,instantaneousJitter, meanJitter_1s, meanJitter_10s):
		self.timeCreated = datetime.datetime.now()
		self.lastPacketReceived = lastPacketReceived
		self.instantaneousJitter=instantaneousJitter
		self.meanJitter_1s=meanJitter_1s
		self.meanJitter_10s=meanJitter_10s

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
	type="Glitch"
	description=""

	# Constructor
	def __init__(self, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap):
		# Create timestamp of event
		self.timeCreated=datetime.datetime.now()
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

		# Create empty list to hold rtp stream data as it is received by the socket
		self.rtpStreamData = []

		# Create empty dictionary to hold publicly accessible stats for this RtpStream object
		self.stats= {}

		# Create a __calculateThread
		self.calculateThread = threading.Thread(target=self.__calculateThread, args=())
		self.calculateThread.daemon = True  # Thread will auto shutdown when the prog ends
		self.calculateThread.start()


	# Define a private calculation method that will run autonomously as a thread
	# This thread will
	def __calculateThread(self):
		print "__calculateThread started with id: ", self.__streamID, "\r"
		# Create a dictionary to contain all calculated stats
		# This dictionary is private but will be copied to the public stats{} dictionary by the getter method
		__stats = {}

		# Prev timestamp doesn't exist yet as this is the first packet, so create datetime object with value 0
		lastReceivedRtpPacket=RtpData(0, 0, datetime.timedelta())
		__stats["firstPacketReceivedAtTimestamp"] = datetime.timedelta()


		# General Counters
		loopCounter = 0
		__stats["totalPacketsPerSecond"]= 0
		__stats["totalDataReceivedPerSecond"] = 0
		__stats["totalDataReceived"] = 0
		__stats["totalPacketsReceived"] = 0
		secondsElapsed = 0

		# Glitch counters
		__stats["totalPercentPacketsLost"] = 0
		__stats["totalPacketsLost"] = 0
		__stats["totalGlitches"] = 0
		# define timedelta object to store an aggregate of of Glitch length
		totalGlitchLength = datetime.timedelta()
		__stats["timestampOfLastGlitch"]=datetime.timedelta()
		__stats["timeElapsedSinceLastGlitch"]=datetime.timedelta()

		# Jitter counters
		__stats["minJitter"]=0
		__stats["maxJitter"]=0
		__stats["rangeOfJitter"]=0
		__stats["instantaneousJitter"]=0
		__stats["meanJitter_1s"]=0
		sumOfJitter_1s=0
		averageRtpPacketArrivalPeriod=datetime.timedelta()
		historicJitter = []
		__stats["meanJitter_10s"]=0
		# Declare flags
		lossOfStreamFlag = True
		lossOfStreamTimer=0
		lossOfStreamAlarmThreshold=2

		# datetime object to allow calculation of processing time (to guard against processor overload)
		calculationStartTime=datetime.timedelta()
		calculationEndTime=datetime.timedelta()

		# Declare empty list of 'event' objects. This will contain a list of the disruptions relating to this rtpStream object
		__stats["eventList"] = []

		__stats["POLL_INTERVAL"] = 0.1  # Loop will execute every 100mS

		# Calculate the no of loops equating to a second
		loopsPerSecond = 1 / __stats["POLL_INTERVAL"]

		while True:
			# Lock the access mutex
			self.__accessRtpDataMutex.acquire()
			# Copy the contents of self.rtpStreamData into a temporary list so the accessRtpDataMutex can be released
			rtpStream =list(self.rtpStreamData)

			# Now we have a working copy of rtpStreamData[] we can clear the original source list
			del self.rtpStreamData[:]
			# Release the mutex
			self.__accessRtpDataMutex.release()

			# Test for new data
			if (len(rtpStream) > 0):
				calculationStartTime=datetime.datetime.now()

				# Take timestamp of the very first packet received of this rtpStream
				if __stats["totalPacketsReceived"] < 1:
					__stats["firstPacketReceivedAtTimestamp"] = rtpStream[0].timestamp
					# Add a StreamStarted event to the event list
					__stats["eventList"].append(StreamStarted(rtpStream[0]))
					# Stream now being received so clear flag

				if lossOfStreamFlag==True:
					# We're now receiving a stream, so clear alarm flag
					lossOfStreamFlag=False
					# Reset loss of stream timer
					lossOfStreamTimer=0


				# Get timestamp of final packet of prev data set
				if(__stats["totalPacketsReceived"]<1):
					# For the very first packet, take the prev packet to be that of the first packet received (to give a
					# delta of zero, otherwise the delta will be the diff between 0 and today's date!
					prevX=rtpStream[0]
				else:
					# Get copy of final packet of prev data set
					prevX=lastReceivedRtpPacket

				# Iterate over rtpStream to get total count of data received in this batch of data, no. of packets and also calculate
				# rx time deltas and jitter
				sumOfInterPacketJitter = 0
				sumOfTimeDeltas =0
				for x in rtpStream:
					# Per second counter
					__stats["totalDataReceivedPerSecond"] += x.payloadSize
					# Total aggregate
					__stats["totalDataReceived"] += x.payloadSize
					# Calculate and write time delta into RtpData object
					x.timeDelta = x.timestamp - prevX.timestamp

					# Now calculate the diff (jitter) between consecutive timeDelta values (should be in order of mS)
					# It should be simple. Just take mean of interPacketJitter
					# interPacketJitter=abs(x.timeDelta.microseconds-prevX.timeDelta.microseconds)
					x.jitter = x.timeDelta.microseconds - prevX.timeDelta.microseconds
					# print x.timestamp,x.timeDelta,x.jitter,"\r"
					# Calculate minimum and maximum jitter
					# But wait until 'steady' state reached by testing for loopCounter>1
					if loopCounter>1:
						if __stats["minJitter"] == 0:
							# Set initial value
							__stats["minJitter"] =x.jitter
						if x.jitter < __stats["minJitter"]:
							__stats["minJitter"] = x.jitter
						# Calculate maximum jitter
						if __stats["maxJitter"] == 0:
							# Set initial value
							__stats["maxJitter"] = x.jitter
						if x.jitter > __stats["maxJitter"]:
							__stats["maxJitter"] = x.jitter
						__stats["rangeOfJitter"]=__stats["maxJitter"]-__stats["minJitter"]

					# Sum the abs interPacketJitter values  for the subsequent jitter calculation
					# For 'instantaneous' jitter value
					sumOfInterPacketJitter += abs(x.jitter)
					# For 1 second jitter value
					sumOfJitter_1s += abs(x.jitter)

					# Sum the timeDeltas to calculate the average time between packets arriving
					sumOfTimeDeltas += x.timeDelta.microseconds
					# Update prevTimestamp for next time around loop
					prevX=x

				# Calculate jitter
				# Find the mean value of the microsecond portion of the jitter values in rtpStream
				# and also the mean time period between packets arriving (should, on average match the rtp
				# generator period)
				if len(rtpStream)>1:
					__stats["instantaneousJitter"]=sumOfInterPacketJitter/(len(rtpStream)-1)
					__stats["meanRxPeriod"]=sumOfTimeDeltas/(len(rtpStream)-1)

				# print 	"minJitter",__stats["minJitter"],", maxJitter",__stats["maxJitter"],", instantaneousJitter",__stats["instantaneousJitter"],"\r"
				# Now attempt to detect excessive jitter by comparing the instantaneous value with the 10s averaged value
				# Check that 10s value has actually been calculated
				if __stats["meanJitter_10s"] >0:
					if __stats["instantaneousJitter"] > (5* __stats["meanJitter_10s"]):
						print "*******Excessive jitter","\r"
						__stats["eventList"].append(ExcessiveJitter(rtpStream[-1],__stats["instantaneousJitter"],__stats["meanJitter_1s"],__stats["meanJitter_10s"]))


				# Glitch Detection ###############################################################
				# Test for out of sequence packet by comparing last received sequence no with that of first rtpObject in new list of data in rtpStream[]
				# This musn't run the first time around the loop (because there's nothing to compare the first packet to)
				if (lastReceivedRtpPacket.rtpSequenceNo != (rtpStream[0].rtpSequenceNo - 1)) and (__stats["totalPacketsReceived"] > 0):
					# Take timestamp of most recent glitch
					__stats["timestampOfLastGlitch"] = datetime.datetime.now()
					print __stats["timestampOfLastGlitch"], " Out of sequence packet received between data sets. Expected sequence no", (
							prevRtpPacket.rtpSequenceNo + 1), " but received ", rtpStream[0].rtpSequenceNo, "\r"
					# Capture packets either side of the 'hole' and store them in the event list
					# Create an object representing the glitch
					glitch = Glitch(prevRtpPacket, rtpStream[0])
					# Add the latest glitch to the evenList[]
					__stats["eventList"].append(glitch)
					# Now update aggregate glitch stats
					__stats["totalPacketsLost"]+=glitch.packetsLost
					totalGlitchLength+=glitch.glitchLength
					__stats["totalGlitches"]+=1

				# Now test for sequence errors within current data set
				# Take a copy of the first item in the list
				prevRtpPacket = rtpStream[0]
				# Iterate over the the remainder of the list (starting at index 1 to the end '-1')
				for rtpPacket in rtpStream[1:]:
					# Test sequence no of current packet against previous packet
					if rtpPacket.rtpSequenceNo != (prevRtpPacket.rtpSequenceNo + 1):
						# Take timestamp of most recent glitch
						__stats["timestampOfLastGlitch"] = datetime.datetime.now()
						print __stats["timestampOfLastGlitch"], " Out of sequence packet received (within current data set). Expected sequence no", (
								prevRtpPacket.rtpSequenceNo + 1), " but received ", rtpPacket.rtpSequenceNo, "\r"

						# Capture packets either side of the 'hole' and store them in the event list
						# Create an object representing the glitch
						glitch = Glitch(prevRtpPacket, rtpPacket)
						# Add the glitch to the evenList[]
						__stats["eventList"].append(glitch)
						# Now update aggregate glitch stats
						__stats["totalPacketsLost"] += glitch.packetsLost
						totalGlitchLength += glitch.glitchLength
						__stats["totalGlitches"] += 1
					# Store current rtp packet for the next iteration around the loop
					prevRtpPacket = rtpPacket


				# Capture most recent packet (last item of current data set) for next time around loop
				lastReceivedRtpPacket=rtpStream[-1]

				# Get number of packets received (from list length)
				# Per second counter
				__stats["totalPacketsPerSecond"] += len(rtpStream)
				# Total aggregate
				__stats["totalPacketsReceived"] += len(rtpStream)

			else:
				# No data, so set lossOfStreamFlag (unless it's already been set)
				# Check for changes and that we also have an active stream. If so, set the flag and add an event to the eventlist
				lossOfStreamTimer +=1
				if lossOfStreamTimer > (lossOfStreamAlarmThreshold * loopsPerSecond)\
					and lossOfStreamFlag==False and __stats["totalPacketsReceived"]>0:
					# Set flag
					lossOfStreamFlag=True
					# Add event to the list (but only do this once)
					__stats["eventList"].append(StreamLost(lastReceivedRtpPacket))

			# Calculate elapsed since last glitch
			# But only if there has actually been a glitch
			if __stats["totalGlitches"] >0:
				__stats["timeElapsedSinceLastGlitch"] = datetime.datetime.now() - __stats["timestampOfLastGlitch"]

			# Calculate % packet loss
			if __stats["totalPacketsReceived"]>0:
				totalExpectedPackets = __stats["totalPacketsReceived"]+__stats["totalPacketsLost"]
				__stats["totalPercentPacketsLost"] = __stats["totalPacketsLost"]*100/totalExpectedPackets

			# 1 second timer
			# Take modulus of loopcounter to give a one-second timer
			if loopCounter%loopsPerSecond > loopsPerSecond-2:
				# Increment seconds elapsed
				secondsElapsed += 1
				# Calculate 1 second jitter
				if __stats["totalPacketsPerSecond"]>0:
					__stats["meanJitter_1s"]=sumOfJitter_1s/__stats["totalPacketsPerSecond"]

				# Reset sumOfJitter_1s
				sumOfJitter_1s=0
				# if (len(rtpStream) > 0):
				# 	print "__calculateThread: [", secondsElapsed, ":", rtpStream[
				# 		-1].rtpSequenceNo, "] Packets/s", __stats["totalPacketsPerSecond"], ", Rx bytes/s", __stats["totalDataReceivedPerSecond"], ', Total packets', \
				# 		__stats["totalPacketsReceived"], ", Total bytes received", __stats["totalDataReceived"], ", event count", len(
				# 		__stats["eventList"]), "\r"
				# print "totalPacketsLost:", __stats["totalPacketsLost"], ", %loss:", __stats["totalPercentPacketsLost"], ", totalGlitches:", __stats["totalGlitches"], \
				# 	", totalGlitchLength:", totalGlitchLength, ", meanJitter_1s",__stats["meanJitter_1s"], "\r"
				# print "minJitter",__stats["minJitter"],", maxJitter ",__stats["maxJitter"], ", rangeOfJitter",__stats["rangeOfJitter"],"\r"
				# # print "__stats["firstPacketReceivedAtTimestamp"]:", __stats["firstPacketReceivedAtTimestamp"], "\r"
				# print "Events--------------", "\r"
				# for event in eventList:
				# 	print event.type, event.timeCreated, "\r"
				# print "--------------", "\r"

				# 10 second timer to calculate 10s jitter moving average
				# if secondsElapsed % 10 > (10-2):
				# Add the latest 1s jitter value to the moving 10s jitter results array
				historicJitter.append(__stats["meanJitter_1s"])
				# Check that we have enough results (10s worth) to calculate the 10s value
				if len(historicJitter)>10:
					# Remove the oldest value
					historicJitter.remove(historicJitter[0])
					# Clear sum var prior to recalculation of mean
					sumOfJitter_10s=0
					# Calculate mean of previous 10 1s jitter values
					for x in historicJitter:
						sumOfJitter_10s += x
					__stats["meanJitter_10s"]=sumOfJitter_10s/len(historicJitter)
				# print "instantaneousJitter",__stats["instantaneousJitter"],", meanJitter_1s",__stats["meanJitter_1s"],", meanJitter_10s",__stats["meanJitter_10s"],"\r"
				# for x,y in __stats.items():
				# 	print x,y,"\r"

				# Now clear totalDataReceivedPerInterval for the next time around the loop
				__stats["totalDataReceivedPerSecond"] = 0
				__stats["totalPacketsPerSecond"] = 0

			# Calculate how long it has taken for the stats analysis to have been performed
			calculationEndTime = datetime.datetime.now()
			try:
				# Take the calculation time in microseconds and combine with the period between
				# packets arriving to work out how much processor headroom there is
				# If the processor can't keep up, generate an event
				__stats["calculationDuration"] = (calculationEndTime-calculationStartTime).microseconds
				__stats["processorUtilisationPercent"]=__stats["calculationDuration"] * 100 / __stats["meanRxPeriod"]

				# If the CPU is >99% utilised, add event to the list (but only do this once)
				if __stats["processorUtilisationPercent"] > 99:
					__stats["eventList"].append(ProcessorOverload(lastReceivedRtpPacket))
			except Exception as e:
				pass


			# Copy contents of private _stats dictionary into the public dictionary
			self.stats=__stats.copy()

			# Increment loop counter
			loopCounter += 1

			# Empty the rtpStream list
			del rtpStream


			time.sleep(__stats["POLL_INTERVAL"])

	# Define getter methods
	def getRTPStreamID(self):
		return self.__streamID

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
		for x, y in rtpStream.stats.items():
			print x, y, "\r"

		for event in rtpStream.stats["eventList"]:
			print event.type, event.timeCreated, "\r"
		print "--------------", "\r"
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

		if(keyPressed[0]=='j'):
			# Turn jitter on/off by pressing 'j'
			# Clear keyboard buffer
			keyPressed[0] = ''
			if enableJitter==False:
				enableJitter=True
				print "[j] jitter enabled","\r"
			else:
				enableJitter=False
				print "[j] jitter disabled", "\r"


		# Increment rtp sequence number for next iteration of the loop
		rtpSequenceNo += 1
		# If flag set, generate random delay centred around txPeriod (0.01 = 10mS period)
		if enableJitter==True:
			jitter=random.uniform(-1*maxDeviation,maxDeviation)
		else:
			jitter=0
		# print "txPeriod",txPeriod+jitter,"\r"
		time.sleep(txPeriod+jitter)


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
