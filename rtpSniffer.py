#!/usr/bin/env python
#
# Python packet sniffer
#
import socket
import os
#import binascii
import sys
import struct
import time
import datetime
import threading


UDP_RX_IP = "192.168.56.1"
UDP_RX_PORT = 5004

# Define global vars
noOfPacketsReceived=0
totalBytesReceived=0

# Define an obkect to hold data about an individual received rtp packet
class rtpData(object):
	# Constructor method
	def __init__(self,rtpSequenceNo,payloadSize,timestamp):
		
		self.rtpSequenceNo=rtpSequenceNo
		self.payloadSize=payloadSize
		self.timestamp=timestamp
		# timeDelta will store the timestamp diff between this and the previous packet
		self.timeDelta=0


# Define a class to represent a flow of received rtp packets (and associated stats)
class RtpStream(object):
	# Constructor method.
	# The RtpStream object should be created with a unique id no 
	# (for instance the rtp sync-source value would be perfect)
	def __init__(self,id,srcAddress,srcPort):
		# Assign to instance variable
		self.__streamID=id
		self.srcAddress=srcAddress
		self.srcPort=srcPort

		# Define a flag to signal when new data is available (to be processed by the calulateThread)
		self.dataAvailableFlag=False
		print "creating RtpStream with id:",self.__streamID

		# Create a mutex lock to be used by the a thread
		# To set the lock use: __accessRtpDataMutex.acquire(), To release use: __accessRtpDataMutex.release()
		self.__accessRtpDataMutex = threading.Lock()

		# Create empty list to hold rtp stream data as it is received by the socket
		self.rtpStreamData=[] 

		# Create a __displayThread
		self.displayThread=threading.Thread(target=self.__displayThread, args=())
		self.displayThread.daemon=True	# Thread will auto shutdown when the prog ends
		self.displayThread.start()

		# Create a __calculateThread
		self.calculateThread=threading.Thread(target=self.__calculateThread, args=())
		self.calculateThread.daemon=True	# Thread will auto shutdown when the prog ends
		self.calculateThread.start()


	# Define a private calculation method that will run autonomously as a thread
	# This thread will
	def __calculateThread(self):
		print "__calculateThread started with id: ",self.__streamID

		prevTimestamp=0
		prevRtpSequenceNo=0
		totalDataReceivedPerInterval=0
		timestampOfLastGlitch=datetime.datetime.now()
		secondTimer=0
		totalPacketsPerInterval=0
		totalDataReceivedPerInterval=0

		while True:
			# Lock the access mutex
			self.__accessRtpDataMutex.acquire()
			# Copy the contents of self.rtpStreamData into a temporary list so the accessRtpDataMutex can be released
			rtpStreamDataCopy=list(self.rtpStreamData)
			# Now we have a working copy of rtpStreamData[] we can clear the original source list
			del self.rtpStreamData[:]
			# Release the mutex
			self.__accessRtpDataMutex.release()
			# Test for new data
			if(len(rtpStreamDataCopy)>0):
				# Get number of packets received (from list length)
				totalPacketsPerInterval+=len(rtpStreamDataCopy)

				# Calculate received data rate by iterating and summing over rtpStreamDataCopy.payloadSize
				for x in rtpStreamDataCopy:
					totalDataReceivedPerInterval+=x.payloadSize

				

				

				# print "__calculateThread: Latest Sequence no: ",rtpStreamDataCopy[-1].rtpSequenceNo," Packets per sec",packetsPerSecond,"Rx rate",dataRatePerSecond
				# print "__calculateThread: Latest payloadSize",rtpStreamDataCopy[-1].payloadSize
				
				# Test for out of sequence packet by comparing last recieved sequence no with that of first rtpObject in new list of data in rtpStreamDataCopy[]
 				if(prevRtpSequenceNo!= (rtpStreamDataCopy[0].rtpSequenceNo-1)):
 					print timeNow," Out of sequence packet received (prev list). Expected sequence no",(prevRtpSequenceNo+1)," but received ",rtpStreamDataCopy[0].rtpSequenceNo
 					# Take timestamp of most recent glitch 
 					timestampOfLastGlitch=datetime.datetime.now()
 				# Now test for sequence errors within current data set
 				
 				# Get sequence no of first item in the list
 				prevSeq=rtpStreamDataCopy[0].rtpSequenceNo
 				# Iterate over the the remainder of the list (starting at index 1 to the end '-1')
 				# print prevSeq,":",
 				for x in rtpStreamDataCopy[1:]:
 					# Test seqeuence no of current packet against previous packet
 					# print x.rtpSequenceNo,
 					if (x.rtpSequenceNo!=(prevSeq+1)):
 						print timeNow," Out of sequence packet received (within list). Expected sequence no",(rtpStreamDataCopy[x-1].rtpSequenceNo+1)," but received ",rtpStreamDataCopy[x].rtpSequenceNo
						# Take timestamp of most recent glitch 
 						timestampOfLastGlitch=datetime.datetime.now()
					# store current seq no for the next iteration around the loop
 					prevSeq=x.rtpSequenceNo
				
				# Capture most recent sequence no for next time around loop
				prevRtpSequenceNo=rtpStreamDataCopy[-1].rtpSequenceNo
 				
 				
			# Time elapsed since last glitch
 			timeElapsedSinceLastGlitch=datetime.datetime.now()-timestampOfLastGlitch

 			# 1 second timer (assumes 100mS delay)
 			if(secondTimer>10):
 				print "1 second elapsed"
 				# Reset seconds timer
 				secondTimer=0

 				print "__calculateThread: Latest Sequence no: ",prevRtpSequenceNo," Packets per sec",totalPacketsPerInterval,"Rx rate",totalDataReceivedPerInterval
 				#Now clear totalDataReceivedPerInterval for the next time around the loop
				totalDataReceivedPerInterval=0
				totalPacketsPerInterval=0
			

 			# Increment second counter
 			secondTimer+=1

			time.sleep(0.100)	# 100mS delay		

	# Define a private display method that will run autonomously as a thread
	def __displayThread(self):
		print "__displayThread started with id: ",self.__streamID
		x=0
		while True:
			print "__displayThread running...", x
			x+=1
			time.sleep(1)		


	# Define getter methods
	def getRTPStreamID(self):
		return self.__streamID

	# Define setter methods
	def addData(self,rtpSequenceNo,payloadSize,timestamp):
		self.rtpSequenceNo=rtpSequenceNo
		self.payloadSize=payloadSize
		self.timestamp=timestamp
		# print "addData():",self.rtpSequenceNo,self.payloadSize,self.timestamp

		# Create a new rtp data object to hold the rtp packet data
		newData=rtpData(rtpSequenceNo,payloadSize,timestamp)

		# NOW ADD DATA TO A LIST

		# Lock the access mutex
		self.__accessRtpDataMutex.acquire()
		# Add the  rtpData obect containing the latest packet info, to the rtpStreamData[] list
		self.rtpStreamData.append(newData)
		# Release the mutex
		self.__accessRtpDataMutex.release()
		# Now we've added the newData object to the list rtpStreamData[] we cab delete the newData object
		del newData


sock = socket.socket(socket.AF_INET, # Internet
                  socket.SOCK_DGRAM) # UDP
sock.bind((UDP_RX_IP, UDP_RX_PORT))
prevRtpSequenceNo=0


# epoch = datetime(1970, 1, 1, tzinfo=timezone.utc) # use POSIX epoch

#Init timestamp 
prevTimestamp=timeNow = datetime.datetime.now()
timestampOfLastGlitch=datetime.datetime.now()

runOnce=True

while True:
	#recvfrom() returns two parameters, the src address:port (addr) and the actual data (data)
	data, addr = sock.recvfrom(4096) # buffer size is 4096 bytes
	# print addr
	
 	
 	timeNow = datetime.datetime.now()
	
 	# Increment packet received counter
 	noOfPacketsReceived+=1
 	srcAddress=addr[0]
 	srcPort=addr[1]


 	
	try: 
 		# Split rtp header into an array of values
	 	#hexData=binascii.hexlify(data)
	 	# print "received message:", hexData
	 	# RTP header is 12 bytes long. Unpack it as an array. 
	 	# !=big endian, B=unsigned char(1), H=unsigned short(2), L=unsigned long(4)
 		RTP_HEADER_SIZE=12
 		rtpHeader = struct.unpack("!BBHLL", data[:RTP_HEADER_SIZE])


	 	# Calculate the data payload size
	 	payloadSize=len(data)-RTP_HEADER_SIZE
	 	# print"Total data",len(data),"RTP Header size:",RTP_HEADER_SIZE," Payload size",payloadSize,

		# 	sequence no=rtpHeader[2]
	 	#	timestamp=rtpHeader[3]
	 	# 	sync-source identifier =rtpHeader[4]
	 	rtpSequenceNo=rtpHeader[2]
	 	rtpSyncSourceIdentifier=rtpHeader[4]
	 	timeBetweenRxPackets=timeNow-prevTimestamp
	 	timeBetweenRxPacketsInMS=(timeBetweenRxPackets.microseconds//1000)

	 	
	 	if(runOnce==True):
	 		# Create a new rtpStream object (but only once)
	 		s=RtpStream(rtpSyncSourceIdentifier,srcAddress,srcPort)
	 		runOnce=False

	 	# Add new data to rtpStream object rtpSequenceNo,payloadSize,timestamp
	 	s.addData(rtpSequenceNo,payloadSize,timeNow)

	 	# # Time elapsed since last glitch
	 	# timeElapsedSinceLastGlitch=timeNow-timestampOfLastGlitch

	 	# # print srcAddress,":",srcPort,": ",rtpSyncSourceIdentifier,prevRtpSequenceNo,":",rtpSequenceNo,":",timeBetweenRxPacketsInMS, timeElapsedSinceLastGlitch.seconds
	 	# # Test for out of sequence packet
	 	# if(prevRtpSequenceNo!= (rtpSequenceNo-1)):
	 	# 	# print timeNow," Out of sequence packet received. Expected sequence no ",(prevRtpSequenceNo+1)," but received ",rtpSequenceNo

	 	# 	# Take timestamp of most recent glitch 
	 	# 	timestampOfLastGlitch=timeNow

	 	# # Store current sequence no
	 	# prevRtpSequenceNo=rtpSequenceNo

	 	# # Store current timestamp
	 	# prevTimestamp=timeNow
	 	
	 	# for x in rtpHeader:
	 	# 	print x,', ',
	 	# print " "
	 	# print "sequence no: ",rtp_sequenceNo
 	except Exception as e:
 		print str(e),"Length:",len(data),"bytes received"

