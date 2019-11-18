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
class rtpData(object):
	# Constructor method
	def __init__(self, rtpSequenceNo, payloadSize, timestamp):
		self.rtpSequenceNo = rtpSequenceNo
		self.payloadSize = payloadSize
		self.timestamp = timestamp
		# timeDelta will store the timestamp diff between this and the previous packet
		self.timeDelta = 0


# Define an object that represent a glitch
# This will be in the form of the packets (rtpData objects) either side of the 'hole' in received data
class Glitch(object):
	# Define class variables
	totalPacketsLost = 0
	totalGlitches = 0
	# define timedelta object to store an aggregate of all the 'holes' in data reception
	totalGlitchLength = datetime.timedelta()

	# Constructor
	def __init__(self, lastReceivedPacketBeforeGap, firstPackedReceivedAfterGap):
		self.startOfGap = lastReceivedPacketBeforeGap
		self.endOfGap = firstPackedReceivedAfterGap
		# Calculate packets lost by taking the diff of the sequence nos at the end and start of hole
		# The '-1' is because it's fences and fenceposts
		self.packetsLost = firstPackedReceivedAfterGap.rtpSequenceNo - lastReceivedPacketBeforeGap.rtpSequenceNo - 1
		# Update class 'static, if this were Java' variable for the total no. of packets lost in this rtpStream
		Glitch.totalPacketsLost += self.packetsLost
		# Calculate length of this glitch
		self.glitchLength = firstPackedReceivedAfterGap.timestamp - lastReceivedPacketBeforeGap.timestamp
		# Update class var for aggregate of all the glitch times
		Glitch.totalGlitchLength += self.glitchLength
		# increment class var for total no of glitches
		Glitch.totalGlitches += 1


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

		# Define a flag to signal when new data is available (to be processed by the calulateThread)
		self.dataAvailableFlag = False
		print "creating RtpStream with id:", self.__streamID, "\r"

		# Create a mutex lock to be used by the a thread
		# To set the lock use: __accessRtpDataMutex.acquire(), To release use: __accessRtpDataMutex.release()
		self.__accessRtpDataMutex = threading.Lock()

		# Create empty list to hold rtp stream data as it is received by the socket
		self.rtpStreamData = []

		# Create a __displayThread
		self.displayThread = threading.Thread(target=self.__displayThread, args=())
		self.displayThread.daemon = True  # Thread will auto shutdown when the prog ends
		self.displayThread.start()

		# Create a __calculateThread
		self.calculateThread = threading.Thread(target=self.__calculateThread, args=())
		self.calculateThread.daemon = True  # Thread will auto shutdown when the prog ends
		self.calculateThread.start()

	# Define a private calculation method that will run autonomously as a thread
	# This thread will
	def __calculateThread(self):
		print "__calculateThread started with id: ", self.__streamID, "\r"

		# Prev timestamp doesn't exist yet as this is the first packet, so create datetime object with value 0
		prevTimestamp = datetime.timedelta()
		prevRtpPacket = rtpData(0, 0, datetime.timedelta())
		timestampOfLastGlitch = datetime.timedelta()
		firstPacketReceivedAtTimestamp = datetime.timedelta()

		# Counters
		loopCounter = 0
		totalPacketsPerSecond = 0
		totalDataReceivedPerSecond = 0
		totalDataReceived = 0
		totalPacketsReceived = 0
		secondsElapsed = 0
		totalPercentPacketsLost = 0

		# Declare empty list of 'event' objects. This will contain a list of the interruptions in sequence errors caused by packet loss
		eventList = []

		POLL_INTERVAL = 0.1  # Loop will execute every 100mS

		# Calculate the no of loops equating to a second
		loopsPerSecond = 1 / POLL_INTERVAL

		while True:
			# Lock the access mutex
			self.__accessRtpDataMutex.acquire()
			# Copy the contents of self.rtpStreamData into a temporary list so the accessRtpDataMutex can be released
			rtpStream = list(self.rtpStreamData)
			# Now we have a working copy of rtpStreamData[] we can clear the original source list
			del self.rtpStreamData[:]
			# Release the mutex
			self.__accessRtpDataMutex.release()
			# Test for new data
			if (len(rtpStream) > 0):

				# Take timestamp of the very first packet received of this rtpStream
				if totalPacketsReceived < 1:
					firstPacketReceivedAtTimestamp = rtpStream[0].timestamp

				# Iterate over rtpStream to get total count of data received in this batch of data, no. of packets and also calculate rx time deltas
				# Get timestamp of final packet of prev data set
				prevTimestamp = prevRtpPacket.timestamp
				for x in rtpStream:
					# Per second counter
					totalDataReceivedPerSecond += x.payloadSize
					# Total aggregate
					totalDataReceived += x.payloadSize
					# Calculate and write time delta into rtpData object
					x.timeDelta = x.timestamp - prevTimestamp
					# print "[",x.rtpSequenceNo,"]",x.timestamp,prevTimestamp,x.timeDelta,x.timeDelta.microseconds,"\r"
					# Update prevTimestamp for next time around loop
					prevTimestamp = x.timestamp

				# Test for out of sequence packet by comparing last recieved sequence no with that of first rtpObject in new list of data in rtpStream[]
				# This musn't run the first time around the loop (because there's nothing to compare the first packet to)
				if (prevRtpPacket.rtpSequenceNo != (rtpStream[0].rtpSequenceNo - 1)) and (totalPacketsReceived > 0):
					# Take timestamp of most recent glitch
					timestampOfLastGlitch = datetime.datetime.now()
					print timestampOfLastGlitch, " Out of sequence packet received between data sets. Expected sequence no", (
							prevRtpPacket.rtpSequenceNo + 1), " but received ", rtpStream[0].rtpSequenceNo, "\r"
					# Capture packets either side of the 'hole' and store them in the event list
					# Create an object representing the glitch
					glitch = Glitch(prevRtpPacket, rtpStream[0])
					# Add the glitch to the evenList[]
					eventList.append(glitch)

				# Now test for sequence errors within current data set
				# Take a copy of the first item in the list
				prevRtpPacket = rtpStream[0]
				# Iterate over the the remainder of the list (starting at index 1 to the end '-1')
				# print prevSeq,":",
				for rtpPacket in rtpStream[1:]:
					# Test seqeuence no of current packet against previous packet
					if rtpPacket.rtpSequenceNo != (prevRtpPacket.rtpSequenceNo + 1):
						# Take timestamp of most recent glitch
						timestampOfLastGlitch = datetime.datetime.now()
						print timestampOfLastGlitch, " Out of sequence packet received (within current data set). Expected sequence no", (
								prevRtpPacket.rtpSequenceNo + 1), " but received ", rtpPacket.rtpSequenceNo, "\r"

						# Capture packets either side of the 'hole' and store them in the event list
						# Create an object representing the glitch
						glitch = Glitch(prevRtpPacket, rtpPacket)
						# Add the glitch to the evenList[]
						eventList.append(glitch)
					# Store current rtp packet for the next iteration around the loop
					prevRtpPacket = rtpPacket

				# Capture most recent packet (last item of current data set) for next time around loop
				prevRtpPacket = rtpStream[-1]

				# Get number of packets received (from list length)
				# Per second counter
				totalPacketsPerSecond += len(rtpStream)
				# Total aggregate
				totalPacketsReceived += len(rtpStream)

			# Time elapsed since last glitch
			timeElapsedSinceLastGlitch = datetime.datetime.now() - timestampOfLastGlitch

			# Calculate % packet loss
			if totalPacketsReceived>0:
				totalExpectedPackets = totalPacketsReceived+Glitch.totalPacketsLost
				totalPercentPacketsLost = Glitch.totalPacketsLost*100/totalExpectedPackets

			# 1 second timer
			if (loopCounter > loopsPerSecond):
				# Reset loopCounter timer
				loopCounter = 0
				# Increment seconds elapsed
				secondsElapsed += 1
				if (len(rtpStream) > 0):
					print "__calculateThread: [", secondsElapsed, ":", rtpStream[
						-1].rtpSequenceNo, "] Packets/s", totalPacketsPerSecond, ", Rx bytes/s", totalDataReceivedPerSecond, ', Total packets', \
						totalPacketsReceived, ", Total bytes received", totalDataReceived, ", glitch count", len(
						eventList), "\r"
				print "totalPacketsLost:", Glitch.totalPacketsLost, ",", ", %loss:",totalPercentPacketsLost,", totalEvents:", Glitch.totalGlitches, ", totalGlitchLength:", Glitch.totalGlitchLength, "\r"
				# print "firstPacketReceivedAtTimestamp:", firstPacketReceivedAtTimestamp, "\r"
				print "--------------", "\r"
				# Now clear totalDataReceivedPerInterval for the next time around the loop
				totalDataReceivedPerSecond = 0
				totalPacketsPerSecond = 0

			# Increment loop counter
			loopCounter += 1

			# Empty the rtpStream list
			del rtpStream
			time.sleep(POLL_INTERVAL)

	# Define a private display method that will run autonomously as a thread
	def __displayThread(self):
		print "__displayThread started with id: ", self.__streamID, "\r"
		x = 0
		while True:
			# print "__displayThread running...", x
			x += 1
			time.sleep(1)

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
		newData = rtpData(rtpSequenceNo, payloadSize, timestamp)

		# NOW ADD DATA TO A LIST

		# Lock the access mutex
		self.__accessRtpDataMutex.acquire()
		# Add the  rtpData obect containing the latest packet info, to the rtpStreamData[] list
		self.rtpStreamData.append(newData)
		# Release the mutex
		self.__accessRtpDataMutex.release()
		# Now we've added the newData object to the list rtpStreamData[] we cab delete the newData object
		del newData


# Define a thread that will trap keys pressed
def __catchKeyboardPresses(keyPressed):
	print "Starting __catchKeyboardPresses thread", "\r"
	while True:
		ch = getch()
		keyPressed[0] = ch
		time.sleep(0.2)


# define a traffic generator thread
def __rtpGenerator(keyPressed):
	UDP_DEST_IP = "192.168.56.1"
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

		# Increment rtp sequence number for next iteration of the loop
		rtpSequenceNo += 1
		# time.sleep(.005)
		time.sleep(.01)


####################################################################################


# Main prog starts here
# #####################
def main():
	UDP_RX_IP = "192.168.56.1"
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
				runOnce = False

			# Add new data to rtpStream object rtpSequenceNo,payloadSize,timestamp
			s.addData(rtpSequenceNo, payloadSize, timeNow)


		except Exception as e:
			print str(e), "Length:", len(data), "bytes received"


# Invoke main() method (entry point for Python script)
if __name__ == "__main__":
	main()
