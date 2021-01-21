#!/usr/bin/env python
# Defines useful non-core objects for use by isptest
import http.client
import json
import os
import pickle
import random
import re
import struct
import array
import subprocess
import sys
import time
import datetime
import socket
import threading
import platform
# psutil seems to be broken on Linux
# import psutil
from abc import abstractmethod
from collections import deque
from functools import reduce
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import PurePosixPath
from queue import SimpleQueue, Empty
from urllib.parse import urlparse, unquote, urlencode, parse_qs

from Registry import Registry
from ipwhois import IPWhois, exceptions
import math
import requests
import multiprocessing as mp

# Formats a datetime.timedelta object as a simple string hh:mm:ss
# If showDays=True, returns dd:hh:mm:ss
def dtstrft(timeDelta, showDays=True):
    try:
        daysString = ""
        # Get the timedelta as a total in seconds
        total_seconds = int(timeDelta.total_seconds())
        if showDays is False:
            # return hh:mm:ss
            hours, remainder = divmod(total_seconds, 60 * 60)
            minutes, seconds = divmod(remainder, 60)
            # return str(hours).zfill(2)+":"+str(minutes).zfill(2)+":"+str(seconds).zfill(2)
        else:
            # return dd:mm:ss

            # Calculate how many complete days have elapsed
            days, remainder = divmod(total_seconds, 60 * 60 * 24)
            if days > 0:
                # Construct a string containing the no of days
                daysString= str(days) +"d"
            # Calculate the remaining no of hours
            hours, remainder = divmod(remainder, 60 * 60)
            # Calculate the remaining no of minutes/seconds
            minutes, seconds = divmod(remainder, 60)
            # return ret + str(hours).zfill(2)+":"+str(minutes).zfill(2)+":"+str(seconds).zfill(2)
        # Construct the string to be returned
        return daysString + str(hours).zfill(2) + ":" + str(minutes).zfill(2) + ":" + str(seconds).zfill(2)

    except:
        return None

# Returns the IP address of the network interface currently used as the default route to the internet (if no args supplied)
# Alternatively, for a supplied destination ip address, it will return ip address of the interface that, according to the OS
# routing table will be used to send from.
def get_ip(ipAddrToTest = '10.255.255.255'):
    # Lifted from here https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect((ipAddrToTest, 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Attempts to determine what flavour of operating system is running
# Should return 'Windows' for Windows, or "Darwin" for OSX
def getOperatingSystem():
    current_os = platform.system()
    return current_os
# Returns a string listing the names of the currently running threads
# if asList = True, will return as a list of strings
def listCurrentThreads(asList=False):
    activeThreads = threading.enumerate()
    if asList is False:
        s = ""
        for x in activeThreads:
            s += str(x.getName()) + ", "
        return s
    else:
        threadsList =[]
        for thread in activeThreads:
            threadsList.append(thread.getName())
        return threadsList


# This function will break a string into a list of tuples containing smaller strings (portions).
def fragmentString(inputString, maxLength):
    # Each tuple will be of the form [a,b,c,d,e] where
    # a = the index no of this portion,
    # b = the total no of portions
    # c = total length of reconstructed string
    # d is the portion itself
    # e is a random integer that serves as unique ID for this set of fragments
    inputLength=len(inputString)
    # Generate unique ID
    uniqueID = random.randint(1000, 65535)
    # Determine whether input string is long enough to need fragmenting
    if maxLength <2:
        # The routine below breaks if maxLength = 1
        return -1
    if inputLength <= maxLength:
        return [[0, 1, inputLength, inputString, uniqueID]] # Notice it's a tuple within a list [[ ]]

    else:
        # input string does need fragmenting
        noOfCompleteFragments = int(inputLength / maxLength)
        remainderLength = inputLength % maxLength

        if remainderLength == 0:
            totalNumberOfFragments = noOfCompleteFragments
        else:
            totalNumberOfFragments = noOfCompleteFragments + 1

            outputList = []
            startIndex = 0

            for x in range(0,totalNumberOfFragments):
                endIndex = startIndex + maxLength
                if endIndex < inputLength:
                    portion = inputString[startIndex:endIndex]
                else:
                    portion = inputString[startIndex:]

                # append the fragment to the outputList
                outputList.append([x,totalNumberOfFragments, inputLength, portion, uniqueID])
                startIndex += maxLength
            return outputList

# Takes a list of tuples created by fragmentString() and reassembles them into a complete string
def unfragmentString(fragments):
    output = ""
    try:
        # Check that the first fragment in the supplied list is actually the first message of the sent list by checking the index no
        if fragments[0][0] == 0:
            for fragment in fragments:
                # print (str(fragment))
                output += str(fragment[3])
            #Check no part of the message has been lost by comapring decoded message length with total length value within the fragment.
            if len(output) == fragments[0][2]:
                return output
            else:
                # The assembled string is a different length to that suggested by the length indicator (fragment[2]
                return -2
        else:
            # The list didn't start with the first fragment
            return -1
    except Exception as e:
        raise Exception("ERR:unfragmentString() "+ str(e))

# Utility function convert a value in bytes to kB or MB with a suffix
def bToMb(value):
    # Utility function convert a value in bytes to kB or MB with a suffix
    if value >= 1099511627776:
        # Convert value to Tb
        value = round(value / 1099511627776.0, 1)
        return str(value) + "T"
    elif value >= 1073741824:
        # Convert value to Gb
        value = round(value / 1073741824.0, 1)
        return str(value) + "G"
    elif value >= 1048576:
        # Convert bytes to Mb
        value = round(value / 1048576.0, 1)
        return str(value) + "M"
    elif value >= 1024:
        # Convert bytes to kb
        value = int(value / 1024)
        return str(value) + "k"
    else:
        return str(value)

# Utility function to convert an integer value in micros to millies (eg uS to mS)
def uTom(value):
    # It will append a 'u' or 'm' suffix and return a string
    # If > 1000u, express as a m
    if int(value) > 1000 or int(value) < -1000:
        value = str(math.ceil(value / 1000)) + "m"
    else:
        # Append u to the value
        value = str(math.ceil(value)) + "u"
    return value

# # Defines a class to measure CPU usage
# class CPU(object):
#     try:
#         # __process = psutil.Process()
#         # # Take initial CPU usage sample
#         # __cpuUsage = __process.cpu_percent()
#         pass
#     except:
#         pass
#     # Class method to return CPU usage
#     @classmethod
#     def getUsage(cls):
#         try:
#             return cls.__process.cpu_percent()
#             pass
#         except:
#             return 0

# Define a class to act as a general message store/server for error/info messages
# generated by this script. This class will auto-housekeep. It will discard
# messages the oldest messages if the messages[] list length exceeds historicMessagesToKeep
class Message(object):
    # Define deque list to hold messages (this will auto-housekeep. Set to the max length specified in Registry)
    messages = deque(maxlen=Registry.historicMessagesToKeepInMemory)
    messagesMutex = threading.Lock() #mutex to protect messages[]

    # Private flag to control the operation of the disk writing thread
    __writeMessagesToDiskThreadIsActive = False
    # A class object that will (when started) be the disk writing thread
    writeMessagesToDiskThread = None
    # FIFO queue to hold the messages to be written to disk
    __diskWriteQueue = SimpleQueue()

    # Determines which messages will be revealed by getMessages
    # 0 = no warning messages, > 0 = warning messages displayed
    verbosityLevel = 0
    outputFileName = "isptest_messages_default.txt"

    # posts a message using HTTP POST
    # tcpPort is mandatory
    # Returns True if successful, None if tied out or an error depending upon success
    @classmethod
    def postMessage(cls, newMessage, tcpPort, logToDisk=True, server="http://127.0.0.1", path="/log", timeout=0.1):
        try:
            # create URL
            postURL = server + f":{tcpPort}{path}"
            # Create a dict containing the data to be posted
            postData= {"message":newMessage, "logToDisk":str(logToDisk)}
            # POST the data to the log server
            r = requests.post(postURL, postData, timeout=timeout)
            statusCode = r.status_code
            r.raise_for_status()  # If this doesn't raise an exception, all is good!
            return True
        except requests.Timeout:
            return None
        except Exception as e:
            return str(e)



    @classmethod
    def setVerbosity(cls, verbosity):
        cls.verbosityLevel = verbosity

    # This method will override the default filename
    @classmethod
    def setOutputFileName(cls, fileName):
        cls.outputFileName = fileName

    # Returns the current value of cls.outputFileName
    @classmethod
    def getOutputFileName(cls):
        return cls.outputFileName

    # Thread-safe method to append messages to the cls.messages deque
    @classmethod
    def __appendMessageToDeque(cls, newMessage):
        # Acquire the mutex lock
        cls.messagesMutex.acquire()
        # Append the new item to the deque[]
        cls.messages.append(newMessage)
        #Release the mutex
        cls.messagesMutex.release()

    # Thread-safe method to get a copy of the current messages list (deque)
    @classmethod
    def __getMessagesFromDeque(cls):
        # Acquire the mutex lock
        cls.messagesMutex.acquire()
        # Take a shallow copy snapshot of the deque
        copyOfMessages = list(cls.messages)
        # Release the mutex
        cls.messagesMutex.release()
        return copyOfMessages



    # Class method to add a new message to the list
    # If logToDisk==True (the default), the message will also be also added to the diskWriteQueue
    # This employed to stop the disk log filling up with unwanted messages
    # Additionally, this method checks to see if the disk writing thread is active. If it is not, it will start it
    @classmethod
    def addMessage(cls, message, logToDisk=True):
        # Check status of disk writing thread. If it has not yet been started, it will be
        if cls.__writeMessagesToDiskThreadIsActive is False:
            try:
                # Set the flag to signal that the thread has been (or is being) started
                cls.__writeMessagesToDiskThreadIsActive = True
                # Create the thread object
                cls.writeMessagesToDiskThread = threading.Thread(target=cls.__writeMessagesToDiskThread, args=())
                # The daemon will automatically shut down one the main app ends
                cls.writeMessagesToDiskThread.daemon = True
                cls.writeMessagesToDiskThread.setName("__writeMessagesToDiskThread")
                cls.writeMessagesToDiskThread.start()

            except Exception as e:
                Message.addMessage("Message.addMessage() Couldn't start disk writing thread " + str(e))
                # Thread failed to start, so clear the flag
                cls.__writeMessagesToDiskThreadIsActive = False


        # Add the supplied message to the messages list as a tuple containing a timestamp and the message
        newMessage = [datetime.datetime.now(), message]

        # Append newMessage to the deque via the thread-safe __appendMessageToDeque() method
        cls.__appendMessageToDeque(newMessage)

        # Now put the new message in the queue, to be picked up by the disk writer thread
        if logToDisk:
            cls.__diskWriteQueue.put(newMessage)

    # class method to filter cls.messages[] based on the message prefix and cls.verbosityLevel and return a sublist
    @classmethod
    def getFilteredMessagesList(cls):
        # prefixes are ERR:, INFO: etc. Messages containing these prefixes may/may not be displayed
        # according to cls.verbosityLevel.
        # Currently for verbosityLevel = 0, all messages containing the strings in listOfFilters[] will be hidden
        # For verbosityLevel = 1, ERR: messages will be displayed
        # For verbosityLevel = 2, ERR: and INFO: messages will be displayed
        # For verbosityLevel = 3, ERR:, INFO: and DBUG: messages will be displayed
        # etc...

        # Verbosity definitions (in ascending order of importance)
        listOfFilters = ["LEV3:", "DBUG:", "INFO:", "ERR:"]

        # Calculate how many of the filters to mask, depending upon cls.verbosityLevel
        mask = len(listOfFilters) - cls.verbosityLevel
        if mask < 0:
            mask =0

        # Now truncate (or mask) listOfFilters[] according to the verbosity level
        filtersInUse = listOfFilters[:mask]

        filteredList = []
        # Iterate over cls.messages[] filtering messages according to the contents of filtersInUse[]
        # for message in cls.messages:
        for message in cls.__getMessagesFromDeque():
            # If any of the contents of filtersInUse are found in message[1], omit them from filteredList[]
            if any(x in message[1] for x in filtersInUse):
                # Add messages that would be filtered back into the 'filtered list' with a ** suffix
                # filteredList.append([datetime.datetime.now().strftime("%H:%M:%S"), "*OMMITED*"+message[1]])
                pass
            else:
                # Otherwise add that message to the filtered list
                filteredList.append(message)

        return filteredList

    # Class method to return the messages list
    @classmethod
    def getMessages(cls, *args):
        filteredMessages = cls.getFilteredMessagesList()
        if len(args) == 2:
            # If two args supplied, take the first and second as the range of requested messages to return (inclusive)
            try:
                return list (filteredMessages[args[0]:args[1] + 1])
            except Exception as e:
                Message.addMessage("DBUG: Messages:getMessage(" + str(args[0]) + ":" +
                                   str(args[1]) + ") requested start and end indexes out of range: " + str(e))
                return None
        elif len(args) == 1:
            # If one arg supplied, return the last n messages.
            try:
                return list(filteredMessages[(args[0] * -1):])
            except Exception as e:
                # return list (cls.messages)
                Message.addMessage("DBUG: Messages.getMessages(" + str(args) + ") " + str(e))
                return filteredMessages
        else:
            # if no args supplied, return complete list
            return list (filteredMessages)


    # Background thread to write messages to disk (in batches, every second)
    @classmethod
    def __writeMessagesToDiskThread(cls):
        Message.addMessage("Message.__writeMessagesToDiskThread starting")
        while cls.__writeMessagesToDiskThreadIsActive:
            # Test the message queue size every second. If there are messages, write them to disk
            if cls.__diskWriteQueue.qsize() > 0:
                # Test size of existing log file. If larger than the threshold set in Registry, auto archive
                # This will cause the log file to be recreated
                try:
                    ret = archiveLogs(cls.outputFileName, Registry.maximumLogFileSize_bytes)
                    if ret == True:
                        Message.addMessage("Message.__writeMessagesToDiskThread. " + str(cls.outputFileName) + \
                                           " auto archived")
                except Exception as e:
                    Message.addMessage("ERR:Message.__writeMessagesToDiskThread. " + str(cls.outputFileName) + \
                                       " auto archive error")

                # Create the file object for appending
                # Now log the message to disk
                try:
                    fh = open(cls.outputFileName, "a+")
                    # Keep pulling messages from the queue and writing them until the queue is empty
                    while cls.__diskWriteQueue.qsize() > 0:
                        # Get the message item from the queue
                        latestItem = cls.__diskWriteQueue.get(timeout=0.2)
                        # Check the length of the item matches what we expect (a tuple)
                        if len(latestItem) > 0:
                            # Format the string to be written to the file
                            logString = latestItem[0].strftime("%Y:%m:%d-%H:%M:%S") + ":" + latestItem[1] + "\n"
                            # Append to the file
                            fh.write(logString)
                    fh.close()
                except Exception as e:
                    Message.addMessage("Message.__writeMessagesToDiskThread couldn't write " + str(e))
            # Sleep for 1 second
            time.sleep(1)
        Message.addMessage("Message.__writeMessagesToDiskThread ending")


# class GetchWithTimeout(object):
#     """Gets a single character from standard input.  Does not echo to the
#     screen."""
#     def __init__(self):
#         try:
#             self.impl = _GetchWindows()
#         except ImportError:
#             self.impl = _GetchUnix()
#
#     def __call__(self): return self.impl()
#
#
# class _GetchUnix:
#     """Fetch and character using the termios module."""
#     def __init__(self):
#         import tty, sys
#         from select import select
#
#     def __call__(self):
#         import sys, tty, termios
#         from select import select
#
#         fd = sys.stdin.fileno()
#         old_settings = termios.tcgetattr(fd)
#
#         try:
#             tty.setraw(sys.stdin.fileno())
#
#             # [ Wait until ready for reading,
#             #   wait until ready for writing
#             #   wait for an "exception condition" ]
#             # The below line times out after 1 second
#             # This can be changed to a floating-point value if necessary
#             [i, o, e] = select([sys.stdin.fileno()], [], [], 1)
#             if i:
#                 ch = sys.stdin.read(1)
#             else:
#                 ch = None
#
#         finally:
#             termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
#
#         return ch
#
#
# class _GetchWindows:
#     """Fetch a character using the Microsoft Visual C Runtime."""
#     def __init__(self):
#         import msvcrt
#
#     def __call__(self):
#         import msvcrt
#         import time
#
#         # Delay timeout to match UNIX behaviour
#         time.sleep(1)
#
#         # Check if there is a character waiting, otherwise this would block
#         if msvcrt.kbhit():
#             return msvcrt.getch()
#
#         else:
#             return


# Simple function, lifted from here: https://pastebin.com/m4kZey1v
# Pastes text to PastBin.com (using either the default (pulled from the Registry), or supplied Dev key)
# Returns a URL of the page showing the text
# Note: Pastes are instructed to delete after 10 minutes
def pasteBin(textToPaste, title='', api_dev_key=Registry.pastebinApiDeveloperkey):
    import urllib.parse
    import urllib.request

    url = "http://pastebin.com/api/api_post.php"
    values = {'api_option': 'paste',
              'api_dev_key': api_dev_key,
              'api_paste_code': textToPaste,
              'api_paste_private': '0',
              'api_paste_name': title,
              'api_paste_expire_date': '10M',
              'api_paste_format': 'text',
              'api_user_key': '',
              'api_paste_name': title,
              'api_paste_code': textToPaste}

    data = urllib.parse.urlencode(values)
    data = data.encode('utf-8')  # data should be bytes
    req = urllib.request.Request(url, data)
    with urllib.request.urlopen(req) as response:
        the_page = response.read()
    # print(the_page)
    # Return the URL of the Pastebin page
    return the_page

# A cross-platform method to catch keypresses (and not echo them to the screen)
def getch():
    # Define a getch() function to catch keystrokes (for control of the RTP Generator thread)
    # This code has been lifted from https://gist.github.com/jfktrey/8928865
    # It implements a 1sec timeout (on Linux) or 0.2secs (Windows). If no key was detected in the mean time,
    # it will return None
    if platform.system() == "Windows":
        import msvcrt
        time.sleep(0.2)  # 0.2sec timeout
        if msvcrt.kbhit():
                # return ord(msvcrt.getch())
            ch = msvcrt.getch()
                # Trap Escape sequences prefix codes (only interested in the final digit - Windows esc seq start with 224,x)
            while ord(ch) == 224:
                ch = msvcrt.getch()
            return ord(ch)
        else:
            # print("Getch timeout\r")
            return None

    else:
        import tty, termios, sys
        from select import select  # For timeout functionality
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            # Add additional lines for a 1 sec timeout
            [i, o, e] = select([sys.stdin.fileno()], [], [], 1)
            # ch = sys.stdin.read(1)
            if i:
                ch = sys.stdin.read(1)
                # Trap Escape sequences prefix codes (only interested in the final digit - Linux esc seq start with 27,91,x)
                while ord(ch) == 27 or ord(ch) == 91:
                    ch = sys.stdin.read(1)

            else:
                ch = ""
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Return the ascii value of the key pressed
        try:
            # print ("getch() " + str (ord(ch)) + "\r")
            return ord(ch)
        except:
            # print("Getch timeout\r")
            return None


# This class continually monitors the getTraceRouteHopsList() method of an Rtp transmit/receive/results object
# and quietly queries the IP address it finds in the background.
# It then provides a dictionary where the IP addresses are the Keys and domnain names are the values.
# These can then be used to populate the Traceroute tables/reports
class WhoisResolver(object):
    # A dictionary to hold the results of the whois query
    # The key is the IP address, the Value is a tuple ['dictionary of details',  timeCreatedTimestamp, lastAccessedTimestamp,]
    whoisCache = {}

    # A list of previously unseen ip addresses to be looked up (by the __whoisReolverThread)
    pendingQueries = SimpleQueue()

    whoisAuthorities = ["whois.ripe.net", "whois.iana.org"]

    # This is non-blocking method to query the cls.whoisCache{} dict.
    # If the entry exists it will return it, otherwise it will add the request to pendingQueries{} to be picked up
    # by __whoisResolverThread
    @classmethod
    def queryWhoisCache(cls, ip_address):
        # Is there already an entry for this address in whoisCache or a pending lookup?
        if ip_address in cls.whoisCache:
            # If this Whois entry has previously been created, update the 'last accessed' timestamp
            if cls.whoisCache[ip_address] is not None:
                cls.whoisCache[ip_address][2] = datetime.datetime.now()
        else:
            # This is a previously unseen address.
            # Create a 'placeholder' for the new address
            # The key is the IP address, the Value is a tuple ['dictionary of details',  timeCreatedTimestamp, lastAccessedTimestamp,]
            cls.whoisCache[ip_address] = None
            # Add the unseen address to the pending queue
            cls.pendingQueries.put(ip_address)
        # Return the Whois details (will be None, if the WhoIs for this entry hasn't been resolved yet)
        return cls.whoisCache[ip_address]

    # Returns the current whoisCache dict
    @classmethod
    def getWhoisCache(cls):
        return cls.whoisCache

    # This constructor method sets running a background thread to maintain a cache of the previously queried domains
    def __init__(self):
        self.whoisLookupThreadActive = True

        # Create a background thread to do the querying
        self.whoisLookupThread = threading.Thread(target=self.__whoisLookupThread, args=())
        self.whoisLookupThread.daemon = False
        self.whoisLookupThread.setName("__whoisLookupThread")
        self.whoisLookupThread.start()

    # Blocking method to cause the object to die (by killing the thread)
    def kill(self):
        # Set the flag to false
        self.whoisLookupThreadActive = False
        # Block until the thread ends
        Message.addMessage("Waiting for whoisLookupThread to timeout. Please be patient....")
        self.whoisLookupThread.join()
        Message.addMessage("DBUG:WhoisResolver. whoisLookupThread has ended")

    # # This method **will** examine the lastAccessedTimestamp of the entries in the self.whoIsCache{} dict
    # # and automatically re-check or purge old entries
    # # ***********NOT IMPLEMENTED YET**********
    # def __houseKeep(self):
    #     pass

    # Background thread to continually monitor the lists of IP addresses picked added to pendingQueries{}
    # and determine the owner of that address
    # Once the address has been looked up, it's details will be added to whoisCache{} and thus removed from the
    # pendingQueries{} dict because it has been dealt with
    def __whoisLookupThread(self):
        Message.addMessage("DBUG:WhoisResolver.__whoisLookupThread started")
        # Create dict of known (non public addresses) and their descriptions
        # We won't bother querying Whois because these are known to not be public
        knownAddresses = {"127.0.0.1": "Loopback",
                          "0.0.0.0": "Router didn't respond"}

        while self.whoisLookupThreadActive:
            address = None
            # Empty the queue
            try:
                # Check status of thread controller flag (otherwise we'd have to wait for the entire  loop to iterate)
                if self.whoisLookupThreadActive is False:
                    # Break out of while loop
                    break
                # Retrieve the ip address to be looked up from the queue (will block for timeout seconds)
                address = WhoisResolver.pendingQueries.get(timeout=0.5)
                # Snapshot the current time
                dateCreated = datetime.datetime.now()
                lastAccessed = dateCreated

                # Check to see if the address is already known of in knownAddresses
                # if str(address).startswith(knownAddresses):
                if address in knownAddresses:
                    # Create a 'bogus' entry for this address (with a locally generated 'asn_description' key)
                    WhoisResolver.whoisCache[address] = [{'asn_description': knownAddresses[address]},
                                                                dateCreated, lastAccessed]
                else:
                    try:
                        Message.addMessage(f"DBUG:WhoisResolver whois lookup:{address}")
                        # Query the WhoIs database - See here for docs: https://ipwhois.readthedocs.io/en/latest/index.html
                        # Create an IPWhois object
                        obj = IPWhois(address)
                        # Perform the lookup (using rdap (via http))
                        whoisDetails = obj.lookup_rdap()
                        # Add the the ip details and time created entry to whoisCache{}
                        WhoisResolver.whoisCache[address] = [whoisDetails, dateCreated, lastAccessed]
                    except exceptions.IPDefinedError as e:
                        # This exception will occur if a non-public address is queried (eg 192.168.0.0 etc)
                        # Create an entry for each address with a useful description by parsing the error message
                        # Or by looking at the address itself
                        if str(e).find('Private') > 0:
                            desc = "Local address"
                        else:
                            desc = str(e)
                        # Create a new entry for this address (with a locally generated 'asn_description' key)
                        WhoisResolver.whoisCache[address] = [{'asn_description': desc}, dateCreated, lastAccessed]
                    except (exceptions.WhoisLookupError, exceptions.ASNRegistryError) as e:
                        # Create an entry for the address with the error message as the description
                        WhoisResolver.whoisCache[address] = [{'asn_description': str(e)}, dateCreated, lastAccessed]

            except Empty:
                # Queue was empty
               pass
            except Exception as e:
                Message.addMessage("ERR:WhoisResolver.__whoisLookupThread()" + str(e))

        Message.addMessage("DBUG:WhoisResolver.__whoisLookupThread ending")

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

# Decodes the supplied UDP header (which should be 8 bytes long)
class UDPHeader(object):
    # Custom Exception to be raised if the supplied header data can't be unpacked
    class DecodeException(Exception):
        pass
    def __init__(self, udp_header):
        # unpack header
        try:
            self.udpHeader = struct.unpack("!HHHH", udp_header)
            self.sourcePort = self.udpHeader[0]
            self.destPort = self.udpHeader[1]
            self.dataLength = self.udpHeader[2]
            self.checksum = self.udpHeader[3]

        except Exception as e:
            raise UDPHeader.DecodeException(str(e))

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

# Takes a list of octets [[a,b,c,d],[a,b,c,d]....] and XORs all contents to a single byte to create a checksum value
def createTracerouteChecksum(hopsList):
    if len(hopsList) > 0:
        try:
            # Create lambda function to xor two values
            xor = lambda x, y: x ^ y
            # Use reduce() to iterate over a the list of octets in sequence using our lambda function
            xorSingleHop = lambda hopOctets:reduce(xor, hopOctets)

            output = 0
            # Iterate over the all the hops, xor'ing each hop in turn
            for hop in hopsList:
                output = output ^ xorSingleHop(hop)
            return output
        except Exception as e:
            return None
    else:
        return None

#### Experimental functions
def rawReceive():
    import select
    UDP_RX_PORT = 5000
    UDP_RX_IP = "127.0.0.1"
    # create UDP socket
    udpSocket = socket.socket(socket.AF_INET,  # Internet
                              socket.SOCK_DGRAM)  # UDP

    # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
    rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
    rawSocket.setblocking(0)


    udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    # rawSocket.settimeout(1)
    rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
    print ("udpSocket :" +str(udpSocket))
    print("rawSocket :" + str(rawSocket))
    while True:
        r, w, x = select.select([rawSocket], [], [])
        for i in r:
            receiveSocket = i
            data, addr = receiveSocket.recvfrom(131072)
            print(str(receiveSocket.type) + ", " + str(data))
        # rawData, rawAddr = rawSocket.recvfrom(131072)
        # print("raw " + str(rawData))

            # # extract IP Header
            # ipHeader = Utils.IPHeader(data[:20])
            # udpHeader = Utils.UDPHeader(data[20:28])
            # icmpMessage = Utils.ICMPHeader(data[20:28])
            # message = data[28:]
            # # print(str(i) + ", " + str(i.recvfrom(131072)))
            # print(str(ipHeader.d_addr) + ":" + ", " + str(ipHeader.protocol) + ", type:" + str(icmpMessage.type) +\
            #       ", code:" + str(icmpMessage.code))

# This function is from here: https://stackoverflow.com/questions/3305287/python-how-do-you-view-output-that-doesnt-fit-the-screen
# It will launch the linux/OSX viewer 'less' as a subprocess and display textToDisplay
# Quitting less will return to the calling thread
# less is installed by default on linux/OSX but probably isn;t present on Windows
def displayTextUsingLess(textToDisplay):
    less = subprocess.Popen("less", stdin=subprocess.PIPE)
    less.stdin.write(textToDisplay.encode("utf-8"))
    less.stdin.close()
    less.wait()

# This function is from here: https://stackoverflow.com/questions/3305287/python-how-do-you-view-output-that-doesnt-fit-the-screen
# It will launch the text viewer 'more' as a subprocess and display textToDisplay
# Quitting less will return to the calling thread
# more is installed by default on Windows, OSX and Linux
def displayTextUsingMore(textToDisplay):
    # subprocess.run(["more", "-d"], input=textToDisplay, text=True, check=True)
    # subprocess.run(["more", "testfile"], text=True, check=True, stdin=subprocess.PIPE)
    less = subprocess.Popen(["more", "-d"], stdin=subprocess.PIPE)
    less.stdin.write(textToDisplay.encode("utf-8"))
    less.stdin.close()
    less.wait()

# Creates and returns a customised UDP packet
# To send these packets, you need admin rights because you have to create a raw socket as follows:-
# Create a layer 3 socket  - we will interface at IP level (socket.IPPROTO_RAW)
#       s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
# Set socket.IP_HDRINCL = 1. This means we must supply the IP header ourselves (although the OS will calculate the checksum)
#   s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
# Finally we can send using:-
#   s.sendto(udpPacket, (destAddr,0))
# NOTE: On OSX at least, the destAddr in sendo() doesn't have to match that specified in the IP header
# This means that it *is* possible to spoof packets
def createCustomUdpPacket(srcAddr, destAddr, id_field, TTL, srcPort, dstPort, payload):
    # Creates an IP header - specifying the source/dest address, ID field, TTL and protocol carried within
    def createIPHeader(srcAddr, destAddr, ID, TTL, protocol):
        version = 4
        ihl = 5
        DF = 0
        Tlen = 0  # OSX *WILL* validate this field so it has to be calculated (OSX won't do it). Additionally,
        # unlike all the other header fields which should be written in 'network (= big-endian)) byte order
        # (basically, by prepending the struct/pack() format string with '!') this should be packed in
        # 'native byte order' (that is, that of the OS, which for OSX seems to be little-endian)
        # Will will preset this to a known value and verify it against the copy of the IP header
        # returned in the ICMP message payload
        Flag = 0
        Fragment = 0
        ip_checksum = 0  # It seems like the OSX calculates this automatically (if set to zero, according to Wireshark, anyway)

        SIP = socket.inet_aton(srcAddr)
        DIP = socket.inet_aton(destAddr)
        ver_ihl = (version << 4) + ihl
        f_f = (Flag << 13) + Fragment
        ip_hdr = struct.pack("!BBHHHBBH4s4s", ver_ihl, DF, Tlen, ID, f_f, TTL, protocol, ip_checksum, SIP, DIP)
        return ip_hdr

    # Creates a complete UDP Datagram complete with UDP header (and calculated checksum)
    def createUdpDatagram(srcAddr, destAddr, srcPort, dstPort, payload):
        # Checksum calculation fn pinched from here:
        # https://medium.com/@NickKaramoff/tcp-packets-from-scratch-in-python-3a63f0cd59fe
        # https://gist.github.com/NickKaramoff/b06520e3cb458ac7264cab1c51fa33d6
        # I'm not entirely sure how this works, but it does the folllowing:-
        # The RFC tells us the following:
        # The checksum field is the 16 bit one’s complement of the one’s complement sum
        # of all 16 bit words in the header and text.
        # This method makes use of Python’s built-in array module, that creates an array with fixed element types.
        # This lets us calculate the sum of 16-bit words more easily than using a loop.
        # Then the function simply applies some bit arithmetic magic to the sum and returns it.
        def chksum(packet: bytes) -> int:
            # Check for an even length. If odd, pad with an additional binary 0 (this will make no difference to the sum)
            if len(packet) % 2 != 0:
                packet += b'\0'

            # Convert each pair of bytes into an array element and sum the contents of that array
            res = sum(array.array("H", packet))
            # Expand the sum (res) to 32 bits (bytes) by masking with 0xFFFF
            # Also, add the top 16 bits to the bottom 16 bits
            res = (res >> 16) + (res & 0xffff)
            # Add the top 16 bits to the bottom 16 bits once more
            res += res >> 16
            return (~res) & 0xffff

        UDP_HEADER_LENGTH = 8
        length = UDP_HEADER_LENGTH + len(payload)
        # Initially set the UDP checksum value to zero (will be overwritten by the calculated checksum value)
        checksum = 0  #
        # UDP checksum is calculated by summing the source addr, dest addr, protocol ID (17, for UDP) and UDP packet length
        # known as the 'pseudo header'. Create the pseudo header first
        # and then adding that to the sum of the UDP header, before inverting all the bits (1's complimenting)
        udp_hdr = struct.pack("!HHHH", srcPort, dstPort, length, checksum) + payload
        pseudo_hdr = struct.pack(
            '!4s4sHH',
            socket.inet_aton(srcAddr),  # Source Address
            socket.inet_aton(destAddr),  # Destination Address
            socket.IPPROTO_UDP,  # PTCL
            length  # UDP Length
        )
        # Calculate the checksum
        udp_checksum = chksum(pseudo_hdr + udp_hdr)
        # print("udp_checksum: " + str(hex(udp_checksum)))
        # Now insert the newly calculated checksum back into the udp header *in native byte order* (so no '!' in struct.pack)
        udp_hdr = udp_hdr[:6] + struct.pack('H', udp_checksum) + udp_hdr[8:]
        return udp_hdr

    # Create a custom UDP Datagram (IP length field will be filled in later, IP checksum to be calculated by the OS)
    pkt = createIPHeader(srcAddr, destAddr, id_field, TTL, socket.IPPROTO_UDP) + \
          createUdpDatagram(srcAddr, destAddr, srcPort, dstPort, payload)
    # overwrite total length field of IP header in 'host or 'native' byte order' otherwise sendto() will complain
    # under OSX with an unhelpful 'invalid argument' error
    # It seems (on OSX at least) that this field is the only value that's validated by the OS
    # All other fields seem to be able to be spoofed.
    # See http://cseweb.ucsd.edu/~braghava/notes/freebsd-sockets.txt and
    # https://stackoverflow.com/questions/32575558/creating-raw-packets-with-go-1-5-on-macosx
    # Calculate total length of packet
    totalLength = len(pkt)
    # Re-insert packet length into IP header (in native byte order, so no ! in struct.pack)
    pkt = pkt[:2] + struct.pack("H", totalLength) + pkt[4:]
    return pkt

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
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 7], [127, 0, 0, 4]], # Hop 3 has changed
            None,
            None,
            True,
            "3) prv and current hoplist are same length but different. No TTL"
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
            False,
            "6) prv and current hoplist are different lengths. prevTTL and currentTTL have not been set"
        ]
        ,
        [
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 0], [127, 0, 0, 4]],
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
            None,
            None,
            False,
            "7) same length current and prev hops lists, current hops list flaps from 0 to populated rxTTL and prevRxTTL are None. Should carry forward"
        ]
        ,
        [
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 0], [127, 0, 0, 4]],
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
            4,
            4,
            False,
            "8) same length current and prev hops lists, current hops list flaps from 0 to populated rxTTL and prevRxTTL are 4. Should carry forward"
        ]
        ,
        [
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 3], [127, 0, 0, 4]],
            [[127, 0, 0, 1], [127, 0, 0, 2], [0, 0, 0, 0], [127, 0, 0, 4]],
            4,
            4,
            False,
            "9) same length current and prev hops lists, current hops list flaps from populated to 0. rxTTL and prevRxTTL are 4. Should carry forward"
        ]
        ,
        [
            [(192, 168, 203, 254), (118, 185, 50, 113), (118, 185, 55, 98), (182, 19, 106, 113), (195, 89, 101, 185),
             (0, 0, 0, 0), (195, 2, 2, 73), (195, 2, 24, 126), (195, 66, 236, 103), (0, 0, 0, 0), (0, 0, 0, 0),
             (132, 185, 249, 9), (212, 58, 231, 65)],
            [(192, 168, 203, 254), (118, 185, 50, 113), (118, 185, 55, 98), (182, 19, 106, 113), (195, 89, 101, 185),
             (195, 2, 16, 105), (195, 2, 2, 73), (195, 2, 24, 126), (195, 66, 236, 103), (0, 0, 0, 0), (0, 0, 0, 0),
             (132, 185, 249, 9), (212, 58, 231, 65)],
            114,
            114,
            False,
            "10) Mumbai false detection, hops as tuples, not lists. RxTTL constant, flapping 0>value in hop 6"
        ]
        ,
        [
            [(192,168,224,252), (82,194,125,65), (84,19,200,41), (62,214,37,142), (80,81,192,59), (0,0,0,0), (0,0,0,0), (0,0,0,0), (132,185,249,7), (212,58,231,65)],
            [(192,168,224,253), (0,0,0,0), (212,74,73,101), (212,74,73,101), (80,81,192,59), (0,0,0,0), (0,0,0,0), (0,0,0,0), (132,185,249,9), (212,58,231,65)],
            117,
            117,
            True,
            "11) Berlin not detecting a completely different route. Same lengths (10)"
        ]
        ,
        [
            [(192, 168, 224, 252), (82, 194, 125, 65), (84, 19, 200, 41), (62, 214, 37, 142), (80, 81, 192, 59), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (132, 185, 249, 7)],
            [(192, 168, 224, 253), (0, 0, 0, 0), (212, 74, 73, 101), (212, 74, 73, 101), (80, 81, 192, 59), (0, 0, 0,0),(0, 0, 0, 0), (0, 0, 0, 0), (132, 185, 249, 9), (212, 58, 231, 65)],
            117,
            117,
            True,
            "12) Berlin not detecting a completely different route. Hoplists are a different length and have different values"
        ]
    ]

    # iterate over test list
    for testNo in range(0, len(testList)):
    # for testNo in range(5, 7):
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

    # Compares the contents of two hopLists
    # If they are different lengths, it will only compare to the length of the shortest list
    # If either the prev hop or hop are 0.0.0.0 (no response) these will be ignored
    # Thus it will only compare 'actual IP addresses' that aren't 0.0.0.0
    # It will return True or False depending upon whether the lists are interpreted as being the same or different
    def compareHops(prevHopsList, hopsList):
        # Define pattern for 'no response' to compare hops to
        noResponse = [0, 0, 0, 0]
        hopHasChanged = False

        # establish the hoplist with shortest length
        if len(hopsList) < len(prevHopsList):
            noOfHopsToCompare = len(hopsList)
            # print("Using len(hopsList)" + str(len(hopsList)))
        else:
            noOfHopsToCompare = len(prevHopsList)

        # Iterate over the hop lists up to the length of the shortest list
        for hopNo in range(noOfHopsToCompare):
            # Iterate over hopsList, comparing the the octets of the individual hops
            # Note, we can only compare lists with lists. For some reason, the hops within hopList
            # seem to be being converted to tuples. Therefore we must cast the hop as a list just in case
            prevHop = list(prevHopsList[hopNo])
            currentHop = list(hopsList[hopNo])
            # print (str(hopNo) + str(prevHop) + str(currentHop))
            # Check to see if either the current or previous values are NOT 0.0.0.0.
            if prevHop != noResponse and currentHop != noResponse:
                # These hops contains a value, so see if they have changed
                if currentHop == prevHop:
                    # The hop value has remained the same, no route change
                    hopHasChanged = False
                    # print("currentHop == prevHop" + str(prevHop) + str(currentHop))
                else:
                    # The hop value has changed. New route
                    hopHasChanged = True
                    # Break out of loop
                    break

            # Check for 0.0.0.0 >> 0.0.0.0 (if so, ignore)
            elif prevHop == noResponse and currentHop == noResponse:
                hopHasChanged = False

            # Check for 0.0.0.0 >> a.b.c.d (if so, ignore)
            elif prevHop == noResponse and currentHop != noResponse:
                hopHasChanged = False

            # Now check for a.b.c.d >> 0.0.0.0.
            # If so, make an educated guess and carry the prev hop value into the current hop value
            # This means that we might have something to compare this hop value to if it changes
            # to another non-zero value
            # Note: lists in python are mutable, so this *should* modify the source list
            elif prevHop != noResponse and currentHop == noResponse:
                hopsList[hopNo] = prevHopsList[hopNo]
                # print("carry forward hop " + str(hopNo) + str(hopsList[hopNo]))
                hopHasChanged = False

            # Trap any other conditions we haven't thought of
            else:
                # We don't know if the route has changed or not
                hopHasChanged = False


        return hopHasChanged

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

        # Test to see if the rxTTL has been set
        elif prevRxTTL is not None and rxTTL is not None:
            # Compare current and prev rxTTL values
            if prevRxTTL != rxTTL:
                # If they are different, then the route must have changed
                hopsListHasChanged = True
                return hopsListHasChanged
            else:
                # If they are the same, it's still possible that the route has changed, but the no of hops is the same
                # so we still need to test
                hopsListHasChanged = compareHops(prevHopsList,hopsList)
        # Otherwise rxTTL has not been set, so have to just compare lists
        else:
            hopsListHasChanged = compareHops(prevHopsList, hopsList)

        return hopsListHasChanged
    else:
        return False

# This function will write the string object 'report' to disk
# If no filename is supplied, it will use an auto-generated filename based on the stream parameters
# Returns True for a successful save, otherwise raises an Exception
def writeReportToDisk(report, fileName=None):
    # If filename hasn't been overridden, auto-generate one. Note filename validation should have happened prior
    if fileName is None:
        fileName = "report_" + str(datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S"))
    try:
        # Open the file for writing
        fh = open(fileName, "w+")
        fh.write(report)
        fh.close()
        return True
    except Exception as e:
        raise Exception(f"ERR:Utils.writeReportToDisk() {e}")

# Function to monitor the existing log file size to if they've reached the threshold. If so, rename them
# to a new file with a date added to the filename. The file extension will be preserved
# Returns True is archival occurred (i.e source file was larger than the threshold), False if not, or
# raises an Exception on error
def archiveLogs(file, maxSize):
    # Determine size of existing log file
    # check to see if the file exists at all

    if os.path.isfile(file):
        # File does exist, so check the size
        try:
            if os.path.getsize(file) > maxSize:
                # separate the filename and the extension
                nameNoExtension, fileExtension = os.path.splitext(file)
                # File is larger than the max threshold so rename it
                archivedFilenameSuffix = "_ending_at_" + datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S")
                os.rename(file, nameNoExtension+archivedFilenameSuffix+fileExtension)
                # Message.addMessage("Auto archived " + file)
                return True
            else:
                return False
        except Exception as e:
            # Message.addMessage("ERR:Utils.archiveLogs() " + str(e))
            raise Exception("ERR:Utils.archiveLogs() " + str(e))
            # return None
    else:
        return None

# Test object, used to test exportObjectToDisk() and importObjectFromDisk()
class TestObject(object):

    def __init__(self) -> None:
        super().__init__()
        self.myDict = {"a": 1, "b": 2, "c": 3, "d": 4}
        self.__privateVar = "this is private"
        self.publicVar = "this is public"

    def __str__(self):
        return "TestObject"
    def getMyDict(self):
        return self.myDict
    def getPrivateVar(self):
        return self.__privateVar

class TestSubClass(TestObject):
    def __init__(self) -> None:
        super().__init__()
    def modifySuperClassPrivateVar(self, newVal):
        self.__privateVar = newVal


#  Takes a python object (likely to be an RTPReceiveStream object and writes it to disk
# The object is first serialised using Pickle
# If filename is None, the function will auto genrate one based on thew current date
def exportObjectToDisk(objectToExport, filename=Registry.streamsSnapshotFilename):
    try:
        with open(filename, 'wb') as file: #Open for writing in binary mode
            file.write(pickle.dumps(objectToExport))
        return True
    # Return an error as a string on failure
    except Exception as e:
        raise Exception(f"Utils.exportObjectToDisk {e}")

# Loads, deserialises and returns an object created by exportObjectToDisk()
def importObjectFromDisk(filename):
    try:
        with open(filename, 'rb') as file: # open for reading in binary mode
            importedObject = pickle.load(file)
        return importedObject
    # Return an error as a string on failure
    except Exception as e:
        raise Exception(f"Utils.importObjectFromDisk() {e}")

# Modifes the print function in pympler.summary.print_() to return a formatted table as a list strings representing the lines
def pymplerprintRenderer(muppyObjects, limit=15, sort='size', order='descending'):
    from pympler import summary
    """Print the rows as a summary.

        Keyword arguments:
        limit -- the maximum number of elements to be listed
        sort  -- sort elements by 'size', 'type', or '#'
        order -- sort 'ascending' or 'descending'

        """
    # list to hold the output
    tableLines = []
    # converts the muppy objects
    rows = summary.summarize(muppyObjects)

    for line in summary.format_(rows, limit=limit, sort=sort, order=order):
        # append each new line to tableLines
        tableLines.append(line)
    return tableLines

# Returns the peak (not current) memory usage of this process and all threads in bytes
# or None on error. Currently only works on OSX/Linux
def getPeakMemoryUsage():
    try:
        # Check operating system
        os = getOperatingSystem()
        peakMemUsage = 0
        if os == "Darwin":
            import resource
            # OSX returns the peak memory usage in bytes
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        elif os=="Linux":
            import resource
            # Linux returns the OS in kb so convert to bytes first
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        else:
            # Doesn't currently work on Windows
            return None
    except Exception as e:
        raise Exception("ERR: Utils.sampleMemoryUsage() " + str(e))

# Uses pympler.asizeof() to determine the size of any object or None on error
def getObjectSize(objectToBeMeasured):
    try:
        from pympler import asizeof
        return asizeof.asizeof(objectToBeMeasured)
    except Exception as e:
        raise Exception("ERR: Utils.getObjectSize() " + str(e))

# This Class will yield an available TCP port number (allocated by the OS)
# It is used to ensure that each instance of an http server is created with a unique TCP listen port
class TCPListenPortCreator(object):
    # Get the starting TCP listener port from the Registry
    # tcpPort = Registry.httpServerStartingTCPPort
    lastProvidedTCPPort = 0

    # Return the next available TCP port number
    @classmethod
    def getNext(cls, failLimit=1000, address='127.0.0.1'):
        # No of failure attempts (busy ports) before the method gives up
        while failLimit > 0:
            # Increment the class port value
            # cls.tcpPort += 1
            # Test to see if the TCP port is free
            try:
                # # Create a TCP/IP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Let the OS pick a free port by binding to port '0'
                sock.bind((address, 0))
                # Query the OS allocated port no from the socket
                cls.lastProvidedTCPPort = sock.getsockname()[1]
                sock.close()
                return cls.lastProvidedTCPPort
            except Exception as e:
                # print(f"Can't bind to 127.0.0.1: {cls.tcpPort}, {e}")
                # Decrement the fail counter
                failLimit -= 1
        # If execution reaches the point, the failLimit counter must have decremented to zero
        # print(f"failLimit exceeded {cls.tcpPort}")
        raise Exception(f"Utils.TCPListenPortCreator failLimit exceeded. Last provided port no: {cls.getLastProvided()}")

    # Retrieve the last provided tcpPort value
    @classmethod
    def getLastProvided(cls):
        return cls.lastProvidedTCPPort

# # Define a custom HTTPServer. This will allow access to the associated object that created it,
# # from the server (and httpHandler)
# class CustomHTTPServer(HTTPServer):
#     def __init__(self, *args, **kwargs):
#         # Because HTTPServer is an old-style class, super() can't be used.
#         HTTPServer.__init__(self, *args, **kwargs)
#         self.parentObject = None
#
#     # Provide a setter method to allow the server to have access to the instance of the object that created it
#     # The reason not to have this set by the Constructor method is that I didn't want to modify the existing
#     # constructor method of HTTPServer
#     def setParentObjectInstance(self, parentObjectInstance):
#         self.parentObject = parentObjectInstance

# Define a custom HTTPServer. This will allow access to the associated object that created it,
# from the server (and httpHandler)
# Note this inherits from ThreadingHTTPServer in an attempt to make it 'Google Chrome proof'
class CustomHTTPServer(ThreadingHTTPServer):
    def __init__(self, *args, **kwargs):
        # Because HTTPServer is an old-style class, super() can't be used.
        HTTPServer.__init__(self, *args, **kwargs)
        self.parentObject = None

    # Provide a setter method to allow the server to have access to the instance of the object that created it
    # The reason not to have this set by the Constructor method is that I didn't want to modify the existing
    # constructor method of HTTPServer
    def setParentObjectInstance(self, parentObjectInstance):
        self.parentObject = parentObjectInstance


# # Splits a url path into its component parts. Ignores the initial '/'
# Returns a list
def splitPath(completePath):
    pathList = str(completePath).split("/")[1:]
    # Strip off trailing '/' if there is one
    if pathList[-1] == '':
        pathList = pathList[:-1]  # Take all except the last item of the list
    return pathList

# Re-encodes the incoming string as UTF-8 and terminates with a '/n' character
def formatHttpResponse(input):
    output = (str(input) + "\n").encode('utf-8')
    return output

# This function is designed to take the key/value pairs sent as a query at the end of a URL
# It will then reformat the dictionary so that it can be passed straight into an existing
# function/method as a set of kwargs
# It's expecting to be fed from the output of urllib.parse.parse_qs()
# parse_qs will return a key and value. However, the value will always be as a list,
#  even if there is only a single value associated with that key.
# Therefore we need to reformat the query_components so that they appear as key:value
# NOT key:[value]
# Additionally, test vfor presence of boolean values and convert them from strings to bools as expected
# by the destination function/method
def mapURLQueryToFnArgs(query_componentsDict):
    # Take a shallow copy of the incoming dict
    functionArgsDict = dict(query_componentsDict)
    # Iterate over all the key/value pairs
    for key in functionArgsDict:
        # Iterate over each of the values in the list associated with each key and convert from strings to normal
        # Python types, based on the contents
        for listItem in range(len(functionArgsDict[key])):
            # Values will be a list
            # Test to see if this is a boolean val. If so, recast as a bool (since all
            # incoming values are strings)
            if functionArgsDict[key][listItem] in ["False", "false", "No", "no"]:
                functionArgsDict[key][listItem] = False
            elif functionArgsDict[key][listItem] in ["True", "true", "Yes", "yes"]:
                functionArgsDict[key][listItem] = True
            else:
                # Test if the value is an integer
                if str(functionArgsDict[key][listItem]).isnumeric():
                    # only values 0-9 present, so cast as an integer
                    functionArgsDict[key][listItem] = int(functionArgsDict[key][listItem])
                else:
                    # See if the value is float by trying to cast it as a float (this will fail, if it's not)
                    try:
                        functionArgsDict[key][listItem] = float(functionArgsDict[key][listItem])
                    except:
                    # Casting as a float failed, so ignore
                        pass

        # Finally, test to see if there is only a single value corresponding with that key
        # i.e does the list only contain a single element?
        if len(functionArgsDict[key]) == 1:
            # If so, get rid of the list encompassing the value and assign the
            # value directly to the key instead
            functionArgsDict[key] = functionArgsDict[key][0]

    return functionArgsDict

# Simple shortcut function to remove a list[] of keys from the supplied dictionary
# If the searched-for key is missing, it will be ignored
# NOTE: It acts on the src dictionary (a bit like a C function)
# Returns a list of the keys that were actually removed
def removeMultipleDictKeys(dictToBeModified, keysToBeRemoved):
    # List returned by function to contain a list of the keys that were actually removed
    keysRemoved = []
    for k in keysToBeRemoved:
        if k in dictToBeModified:
            # Delete key k from the dict
            dictToBeModified.pop(k, None)
            # Record the deletion
            keysRemoved.append(k)
    return keysRemoved

# Shortcut function to create a subset of the supplied dictionary containing only wantedKeys[]
# If the wanted keys are missing from sourceDict, they will be ignored
# Answer from here: https://stackoverflow.com/a/5352649
def extractWantedKeysFromDict(sourceDict, wantedKeys):
    filteredDict = dict((k, sourceDict[k]) for k in wantedKeys if k in sourceDict)
    return filteredDict

# Utility function that takes a dictionary of keys and allows the dict keys to be filtered
# Based on the name of the key
# listKeys will return a list, otherwise all other args will return a dict
def filterDictByKey(sourceDict, keyIs=None, keyContains=None, keyStartsWith=None, listKeys=False):
    # If all optional filter parameters are set to their defaults, return the source dict unmodified
    if keyIs is None and keyContains is None and keyStartsWith is None and listKeys is False:
        return sourceDict
    elif listKeys == True:
        # Overrides all other args, just returns a list of keys, but not the values
        return [keys for keys in sourceDict]
    elif keyIs in sourceDict:
        # If a specific key is requested, return a dict containing only that key
        return {keyIs:sourceDict[keyIs]}
    elif keyContains is not None:
        # Return a dict of keys/values whose key name contains the string in 'keyContains'
        return {k: v for k, v in sourceDict.items() if k.find(keyContains) > -1}
    elif keyStartsWith is not None:
        # Return a dict of keys/values whose key name starts with the string in 'keyStartWith'
        return {k: v for k, v in sourceDict.items() if k.startswith(keyStartsWith)}
    else:
        # Otherwise, return an empty dict
        return {}

# Contains  methods to ease the the retreival of data from the API
class APIHelper(object):
    # Creates an API helper object
    # Takes the ip address and port no of the
    def __init__(self, port, addr="127.0.0.1") -> None:
        super().__init__()
        self.addr = addr
        self.port = port
        self.timeout = Registry.httpRequestTimeout

    # Performs a whois lookup of the supplied hops list
    # hopsList is a list of ip addresses to be queried
    # Each address is represented as a list of octets (as expected to be returned by getTraceRouteHopsList()
    # It will attempt to decode the data returned from the API as json, and return it as-is
    # This should be a list of tuples [[ip address, whois name], [ip address, whois name],...]
    def whoisLookup(self, tracerouteHopsList):
            # Iterate over tracerouteHopsList creating a query string to be passed to the WhoisResolver
            # via the /whoIs API
            httpQueryList = []  # List of tuples of the form (indexNo, hopAddr)
            for hopNo in range(len(tracerouteHopsList)):
                # Render each list of IP address octets as a string a.b.c.d
                hopAddr = f"{tracerouteHopsList[hopNo][0]}" \
                          f".{tracerouteHopsList[hopNo][1]}" \
                          f".{tracerouteHopsList[hopNo][2]}" \
                          f".{tracerouteHopsList[hopNo][3]}"
                # Create a tuple of (index, hopAddr) and append to httpQueryList
                httpQueryList.append((hopNo, hopAddr))
            # Now create an HTTP GET query string URL (of the form key1=value1&key2=value2 etc.
            httpQuery = urlencode(httpQueryList)
            # Request the whois lookup via the API
            url = f"http://{self.addr}:{self.port}/whois?{httpQuery}"
            r = requests.get(url, timeout=self.timeout)
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to parse the contents as JSON
            apiResponseBody = r.json()  # Decode HTTP response as JSON (should return a list of tuples)
            # This should be a list of tuples [[ip address, whois name], [ip address, whois name],...]
            return apiResponseBody

    # POST a message the the isptest logger using the api
    # Fails silently (so as not to cause blocks)
    def addMessage(self, message, logToDisk=True):
        url = url = f"http://{self.addr}:{self.port}/log"
        try:
            r = requests.post(url, {"message":message, "logToDisk":logToDisk}, timeout=self.timeout)
        except Exception as e:
            # Fail silently
            pass

    # Adds the stream to the streams directory service
    # POSTS to /streams/add
    # A stream definition is a dict. Example {"streamID":9876, "httpPort":5555, "streamType":"RtpReceiveStream"}
    def addToStreamsDirectory(self, streamDefinition):
        url = f"http://{self.addr}:{self.port}/streams/add"
        try:
            r = requests.post(url, streamDefinition, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
        except Exception as e:
            raise Exception(f"ERR: APIHelper.addToStreamsDirectory() {streamDefinition}, error: {e}")

    # Removes the stream from the streams directory service
    # HTTP DELETE to /streams/delete/[streamType]/[streamID]
    # The streamID is the RTP sync source ID
    def removeFromStreamsDirectory(self, streamType, streamID):
        url = f"http://{self.addr}:{self.port}/streams/delete/{streamType}/{streamID}"
        try:
            r = requests.delete(url, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
        except Exception as e:
            raise Exception(f"ERR: APIHelper.removeFromStreamsDirectory() {streamType}/{streamID}, error: {e}")

    # Gets a list of Events as JSON. Kwargs are additional options to filter the returned results
    def getRTPStreamEventListAsJson(self, **kwargs):
        url = f"http://{self.addr}:{self.port}/events/json"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            return r.json()
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getRTPStreamEventListAsJson() params: {kwargs}, error: {e}")


    # Gets a list of Events as CSV. Kwargs are additional options to filter the returned results
    def getRTPStreamEventListAsCSV(self, **kwargs):
        url = f"http://{self.addr}:{self.port}/events/csv"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            return r.json()
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getRTPStreamEventListAsCSV() params: {kwargs}, error: {e}")


    # Gets a list of Events summaries. Kwargs are additional options to filter the returned results
    def getRTPStreamEventListAsSummary(self, **kwargs):
        url = f"http://{self.addr}:{self.port}/events/summary"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            return r.json()
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getRTPStreamEventListAsSummary() params: {kwargs}, error: {e}")

    # Gets a list of the available streams
    # This will return a list of dicts (each dict contains a stream definition)
    def getStreamsList(self, **kwargs):
        url = f"http://{self.addr}:{self.port}/streams"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            return r.json()
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getStreamsList() params: {kwargs}, error: {e}")

    # Queries the GET /stats endpoint
    def getStats(self, **kwargs):
        url = f"http://{self.addr}:{self.port}/stats"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            return r.json()
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getStats() params: {kwargs}, error: {e}")

    # Queries the GET /txstats endpoint (only works on RTPgenerator objects)
    def getTxStats(self, **kwargs):
        url = f"http://{self.addr}:{self.port}/txstats"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            return r.json()
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getTxStats() params: {kwargs}, error: {e}")

    # This is a generic function that will take any url path, and attempt to do an HTTP GET using that path
    # It will also pass in **kwargs
    # If the api has a matching endpoint, the response will be returned
    # If returnAsBytes is set, return the response as , otherswise attempt to decode it as json, and then, if
    # that fails, as pure text

    def getByURL(self, path, returnAsBytes=False, **kwargs):
        url = f"http://{self.addr}:{self.port}{path}"
        try:
            r = requests.get(url, params=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            if returnAsBytes:
                return r.content
            else:
                # Attempt to decode the response as json and return it
                try:
                    # Try parsing the response as json first (this will recreate any lists or dicts)
                    return r.json()
                except:
                    # Otherwise just return the response as-is
                    return r.text
        except Exception as e:
            raise Exception(f"ERR: APIHelper.getByURL() path: {path}, params: {kwargs}, error: {e}")

    # This is a generic function that will take any url path, and attempt to do an HTTP POST using that path
    # It will also pass in kwargs (a dict of keys/values)
    def postByURL(self, path, **kwargs):
        url = f"http://{self.addr}:{self.port}{path}"
        try:
            r = requests.post(url, data=kwargs, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
            # Attempt to decode the response as json and return it
            try:
                # Try parsing the response as json first (this will recreate any lists or dicts)
                return r.json()
            except:
                # Otherwise just return the response as-is
                return r.text
        except Exception as e:
            raise Exception(f"ERR: APIHelper.postByURL() path: {path}, params: {kwargs}, error: {e}")

    # Shortcut function to create a pop-up message on the user interface.
    # *****NOTE: This will fail silently! so as not to block the caller***
    # i.e it won't raise an Exceptions
    # Ultimately it invokes  the UI.showErrorDialogue() method (via the HTTP do__POST() handler)
    # Currently the required kwargs are title=xxx, body=yyy but see the do__POST() handler for the kwargs
    def alertUser(self, **kwargs):
        url = "/alert"
        try:
            self.postByURL(url, **kwargs)
        except:
            # FAIL SILENTLY
            pass



    # This is a generic function that will take any url path, and attempt to do an HTTP DELETE using that path
    def deleteByURL(self, path):
        url = f"http://{self.addr}:{self.port}{path}"
        try:
            r = requests.delete(url, timeout=self.timeout)
            # test the response
            r.raise_for_status()  # Will raise an Exception if there was a problem
        except Exception as e:
            raise Exception(f"ERR: APIHelper.deleteByURL() path: {path}, error: {e}")




# Renders a nested dict of dicts as an html table
# columnTitles is a list of string reprresenting the column titles
# columnKeys is list of keys to be picked from the nested dict within each key of srcDict
def createHTMLTable(srcDict, title, columnTitles, columnKeys):
    tableData = f"<table>"
    # Create title row
    tableData += f"<tr><td>{title}</tr></td>"
    # Create table column headings
    if len(columnTitles) > 0:
        tableData += f"<tr><td>{'</td><td>'.join(columnTitles)}</td></tr>"
    # Extract values from srcDict to create the data rows
    if len(columnKeys) > 0:
        # Iterate over srcDict to create the rows
        for row in srcDict:
            tableData += f"<tr><td><a href={row}>{row}</a></td>" # The srcDict key itself should be the first cell data
            if len(columnKeys) > 0:
                for key in columnKeys:
                    if key in srcDict[row]:
                        cellData = srcDict[row][key]
                    else:
                        cellData = f"key {key} missing"
                    tableData += f'<td>{cellData}</td>'
            tableData += f"</tr>"
    tableData += f"</table>"
    return tableData

# Define a custom HTTPRequestHandler class to handle HTTP GET, POST requests
class HTTPRequestHandlerRTP(BaseHTTPRequestHandler):
    # For JSON, use contentType='application/json'
    # For plain text use contentType='text/plain'
    def _set_response(self, responseCode=200, contentType='text/html'):
        self.send_response(responseCode)
        self.send_header('Content-type', contentType)
        self.end_headers()

    # Override log_message() to return *nothing*, otherwise the HTTP server will continually log all HTTP requests
    # See here: https://stackoverflow.com/a/3389505
    def log_message(self, format, *args):
        try:
            # Access parent Rtp Stream object methods via server attribute
            parent = self.server.parentObject
            # parent.postMessage(f"DBUG: HTTPRequestHandlerRTP({parent.syncSourceIdentifier}).log_message() {format%args}", logToDisk=False)
            pass
        except:
            # Fail silently
            pass

    # Override log_error(), otherwise the HTTP server will continually log all HTTP errors to stderr
    # See here: https://stackoverflow.com/a/3389505
    def log_error(self, format, *args):
        try:
            # Access parent HTTP Server controllerTCPPort and controllerIPAddress variables
            # Note: This might not have actually been set. If not, fail silently
            parent = self.server.parentObject
            parent.postMessage(
                f"ERR: HTTPRequestHandlerRTP({parent.syncSourceIdentifier}).log_error() {format % args}",
                logToDisk=False)
        except:
            # Fail silently
            pass

    # Method to retrieve list of Events and return them as a list that is **already json encoded**
    @abstractmethod
    def getEventsListAsJson(self, **kwargs):
        pass

    @abstractmethod
    # Returns a list of Event summaries
    def getEventsSummaries(self, **kwargs):
        pass

    @abstractmethod
    def getEventsListAsCSV(self, **kwargs):
        pass

    @abstractmethod
    # Acts a repository for the GET endpoints provided by the HTTP API
    def apiGETEndpoints(self):
        # Access parent Rtp Stream object methods via server attribute
        parent = self.server.parentObject
        # A dictionary to map incoming GET URLs to an existing RtpGenerator method
        # The "args" key contains a list with the preset values that will be passed to targetMethod()
        # "optKeys" is a list of keys that  targetMethod will accept as a kwarg
        # that particular URL is requested
        # "contentType" is an additional key that specifies the type of data returned by targetMethod (if known)
        # The default behaviour of do_GET() will be to try and encode all targetMethod() return values as json
        # Some methods (eg getEventsListAsJson()) already return json, so there is no need to re-encode it
        # Additionally, the /report generation methods return plaintext so the "contentType" key is a means of
        # signalling to do_GET() how to handle the returned values
        getMappings = {
            "/url": {"targetMethod": None, "args": [], "optKeys": [], "contentType": 'application/json'}
        }
        return getMappings

    @abstractmethod
    # Acts a repository for the POST endpoints provided by the  HTTP API
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
            "/url": {"targetMethod": None, "reqKeys": [], "optKeys": []}
        }
        return postMappings

    @abstractmethod
    # Acts a repository for the DELETE endpoints provided by the HTTP API
    def apiDELETEEndpoints(self):
        # Access parent Rtp Stream object methods via server attribute
        parent = self.server.parentObject
        deleteMappings = {"/delete": {"targetMethod": None, "reqKeys": [], "optKeys": []}}
        return deleteMappings

    # Shortcut method to take raw POST or GET Query data (*as unicode*, of the form key1=value1&key2=value2...
    # (TIP use .decode('UTF-8') to convert an ASCII string to unicode)
    # It will then return two items a list of args and a dict of kwargs that can be passed straight to a function/method.
    # Required args are contained within a list, and optional args as a dict
    # The parameters should be passed to the target method as follows reVal = myFunc(*requiredArgs, **optionalArgs)
    # The '*' and '**' will expand out the requiredArgsList and optionalArgsDict respectively
    # Additionally, it will check to see that all the keys in rawKeysValuesString have been used.
    # If not, it will raise an Exception
    def convertKeysToMethodArgs(self, rawKeysValuesString, requiredArgKeysList, optionalArgKeysList):
        # parse the rawKeysValuesString and convert to a dict
        post_data_dict = parse_qs(rawKeysValuesString)
        # 'Pythonize' post_data_dict to convert it from all strings to ints/bools etc
        # and reduce values of single length lists to a single value
        parsedPostDataDict = mapURLQueryToFnArgs(post_data_dict)
        # Create list of mandatory args. *This will fail* if not al the keys are present in post_data_dict
        requiredArgsList = [parsedPostDataDict[key] for key in requiredArgKeysList]
        # Now create a sub-dict of the just the optional keys
        optionalArgsDict = extractWantedKeysFromDict(parsedPostDataDict, optionalArgKeysList)
        # Finally remove the 'expected' keys from parsedPostDataDict to see if any unexpected keys are left over
        removeMultipleDictKeys(parsedPostDataDict, requiredArgKeysList + optionalArgKeysList)
        if len(parsedPostDataDict) > 0:
            raise Exception(f"convertKeysToMethodArgs() unexpected keys provided {parsedPostDataDict}."\
                            f" Permitted optional keys are: {optionalArgKeysList},"\
                            f"mandatory keys are: {requiredArgKeysList}")
        return requiredArgsList, optionalArgsDict

    # Shows the available endpoints
    def listEndpoints(self):
        # Get HTML rendered tables of all the types of endpoints
        getEndpoints = createHTMLTable(self.apiGETEndpoints(), 'GET', ['Path', 'Optional keys'], ['optKeys'])
        postEndpoints = createHTMLTable(self.apiPOSTEndpoints(), 'POST',
                                              ['Path', 'Required keys', 'Optional keys'], ['reqKeys', 'optKeys'])
        deleteEndpoints = createHTMLTable(self.apiDELETEEndpoints(), 'DELETE',
                                                ['Path', 'Required keys', 'Optional keys'], ['reqKeys', 'optKeys'])

        # Create an output string
        helpText = f"Available  API endpoints:<br>" \
                   f"{getEndpoints}<br><br>" \
                   f"{postEndpoints}<br><br>" \
                   f"{deleteEndpoints}<br><br>"

        return helpText


    @abstractmethod
    # render HTML index page
    def renderIndexPage(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        response = f"<html>Index page for {parent.__class__.__name__}</html>"
        return response

    @abstractmethod
    # Http server methods
    def do_GET(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        # Get the dict of url/method mappings
        getMappings = self.apiGETEndpoints()
        syncSourceID = None
        try:
            syncSourceID = parent.syncSourceIdentifier
            # Does the URL match any of those key entries in in getMappings{}?
            # Create a version of the URL that doesn't include any ?key=value suffixes
            # pathMinusQuery = str(self.path).split('?')[0]
            # Split of the URL and query (?key=value suffixes)
            urlDecoded = urlparse(self.path)
            path = urlDecoded.path
            query = urlDecoded.query
            # Utils.Message.addMessage(f"path:{path}, Query:{query}")

            # Test the path to see if it is recognised
            if path in getMappings:
                # Extract the method to be called
                fn = getMappings[path]["targetMethod"]
                # Extract the 'preset' method arguments
                args = getMappings[path]["args"]
                # Extract the 'optional' method arguments list (i.e the kwarg keys that targetMethod() would accept)
                optionalArgKeys = getMappings[path]["optKeys"]
                # Test to see if a 'contentType' is specified for this method. If not, set as 'None'
                if "contentType" in getMappings[path]:
                    contentType = getMappings[path]["contentType"]
                else:
                    # Otherwise set a 'default/unknown' contentType
                    contentType = None

                # Parse query to create a list of optional parameters to be passed to targetMethod()
                # Note: Since this is a GET, we don't specify any requiredArgKeys, just optionalArgKeys
                notUsed, optionalArgs = self.convertKeysToMethodArgs(query, [], optionalArgKeys)

                # Message.addMessage(f"GET fn:{fn}, args:{args}, opt:{optionalArgs}")
                # Execute the specified method, expanding out the parameter list
                retVal = fn(*args, **optionalArgs)

                # Test the contentType expected to be returned by fn() and set headers/encode as JSON accordingly
                if contentType == 'text/html' or contentType == 'text/plain':
                    response = retVal.encode('utf-8')
                    # Create the headers useing the content type specified in the getMappings{} dict
                    self._set_response(contentType=contentType)

                elif contentType in ['application/json', 'application/python-pickle']:
                    # Return value of fn() already encoded as JSON (or in Picle format), pass it on as-is
                    response = retVal
                    # Set the headers
                    self._set_response(contentType=contentType)

                else:
                    # We don't know the format, so encode as JSON as a default
                    response = (json.dumps(retVal, sort_keys=True, indent=4, default=str) + "\n").encode('utf-8')
                    # Set the headers
                    self._set_response(contentType='application/json')

            else:
                # path not recognised
                raise Exception(f"Path not recognised {self.path}")

            # Write the response back to the client
            self.wfile.write(response)
        except Exception as e:
            self.send_error(404,f"{parent.__class__.__name__} HttpRequestHandler.do_GET() " + str(syncSourceID) + ", " + str(e))

    @abstractmethod
    def do_POST(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        # Get the dict of url/method mappings
        postMappings = self.apiPOSTEndpoints()
        syncSourceID = None
        retVal = None  # Captures the return value of the mapped method (if there is one)
        try:
            syncSourceID = parent.syncSourceIdentifier
            # Split off the URL and query (?key=value suffixes)
            urlDecoded = urlparse(self.path)
            path = urlDecoded.path
            query = urlDecoded.query
            # Does the URL match any of those in postMappings{}?
            if path in postMappings:
                # Extract the target function
                fn = postMappings[path]["targetMethod"]
                # Extract the mandatory args for the mapped-to method
                requiredArgKeys = postMappings[path]["reqKeys"]
                # Extract optional args (kwargs) for the mapped-to method
                optionalArgKeys = postMappings[path]["optKeys"]

                # Get POST data
                # Gets the size of data
                content_length = int(self.headers['Content-Length'])
                # Get the data itself as a string ?foo=bar&x=y etc.. NOTE: Arrives as UTF-8, so have to decode back to unicode
                post_data_raw = self.rfile.read(content_length).decode('UTF-8')
                # Examine the supplied keys, divide them up between requiredArgKeys, optionalArgKeys and then
                # generate a list and a dict that can be expanded using * and ** to be used as method parameters
                # Will raise an Exception if unexpected keys are present
                requiredArgs, optionalArgs = self.convertKeysToMethodArgs(post_data_raw, requiredArgKeys,
                                                                          optionalArgKeys)

                retVal = fn(*requiredArgs, **optionalArgs)
                response = formatHttpResponse(f"{type(parent)} do_POST:{syncSourceID} {self.path}, retVal:{retVal}")
                # Set headers
                self._set_response()
            else:
                raise Exception(f"Unrecognised path {self.path}")
            # Write the response back to the client
            self.wfile.write(response)

        except Exception as e:
            self.send_error(404, f"{parent.__class__.__name__}.HttpRequestHandler.do_POST() " + str(syncSourceID) + ", " + str(e))

    @abstractmethod
    def do_DELETE(self):
        # Access parent Rtp Stream object via server attribute
        parent = self.server.parentObject
        # Get the dict of url/method mappings
        deleteMappings = self.apiDELETEEndpoints()
        syncSourceID = None
        retVal = None  # Captures the return value of the mapped method (if there is one)
        try:
            syncSourceID = parent.syncSourceIdentifier
            # Split off the URL and query (?key=value suffixes)
            urlDecoded = urlparse(self.path)
            path = urlDecoded.path
            query = urlDecoded.query

            # Does the URL match any of those in postMappings{}?
            if path in deleteMappings:
                # Extract the target function
                fn = deleteMappings[path]["targetMethod"]
                # Execute the target method
                retVal = fn()
                response = formatHttpResponse(
                    f"{type(parent)} do_DELETE:{syncSourceID} {self.path}, retVal:{retVal}")
                # Set headers
                self._set_response()
            else:
                raise Exception(f"Unrecognised path {self.path}")

            # Write the response back to the client
            self.wfile.write(response)

        except Exception as e:
            self.send_error(404, f"{parent.__class__.__name__}.HttpRequestHandler.do_DELETE() {syncSourceID}, {e}")

# String parser to convert a string reprersentation of a timedelta object (obtained via the api) back into a timedelta
# Copied from https://stackoverflow.com/a/21074460
# if raiseException=True, the function will raise an Exception if the supplied string is not a timedelta object
def convertStringToTimeDelta(s, raiseExceptionOnError=False):
    try:
        if 'day' in s:
            m = re.match(r'(?P<days>[-\d]+) day[s]*, (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d[\.\d+]*)', s)
        else:
            m = re.match(r'(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d[\.\d+]*)', s)
        # Constuct a dict that will for the args for a new timedelta object
        timeDeltaDict = {key: float(val) for key, val in m.groupdict().items()}
        # Create a timedelta object
        return datetime.timedelta(**timeDeltaDict)
    except Exception as e:
        if raiseExceptionOnError:
            # If raiseExceptionOnError enabled, throw an Exception
            raise Exception(f"convertStringToTimeDelta() {e}")
        else:
            # Parsing failed, so just return the source object as-is
            return s

# This function tests the operation of convertStringToPythonDataType
def testConvertStringToPythonDataType(value=None):
    testValues=[
        [str(datetime.timedelta(seconds=8754875638)), datetime.timedelta],
        [str(datetime.timedelta(seconds=1.3)), datetime.timedelta],
        [str(datetime.datetime.now()), datetime.datetime],
        [str("true"), bool],
        [str("True"), bool],
        [str("false"), bool],
        [str("False"), bool],
        [str("none"), type(None)],
        [str("None"), type(None)],
        [str("0"), int],
        [str("-1"), int],
        [str("128"), int],
        [str("3.4"), float],
        [str("+17"), int],
    ]
    # Test testValues array
    if value is None:
        for test in testValues:
            # print(f"{isinstance(convertStringToPythonDataType(test[0]), test[1])}, {test[0]}>>>{convertStringToPythonDataType(test[0])}")
            result = convertStringToPythonDataType(test[0])

            print(f"{test[0]} {type(test[0])}>>>{result} {type(result)} {type(result)==test[1]}")
    # Test suppled value
    else:
        result = convertStringToPythonDataType(value)
        print(f"{value} {type(value)}>>>{result} {type(result)}")


# Utility function to convert a string value back to a Python data type.
# This is typically required when data is retrieved via the API, because the original data type is lost -
# and all values are represented as strings
# It will attempt to detect datetime.datetime, datetime.timedelta, bool, integer and float
# if the type can't be determined, it will just return the value unchanged
def convertStringToPythonDataType(value):
    # Test to see if the value is datetime object encoded in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.mmmmmm)
    # If so, convert it back to a python Datetime object
    try:
        value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
        return value
    except Exception as e:
        # If this fails, test to see if the object is a datetime.timedelta object encoded as a string
        try:
            value = convertStringToTimeDelta(value, raiseExceptionOnError=True)
            return value
        except Exception as e:
            # Now attempt to detect bools
            if value in ["true", "True"]:
                value = True
            elif value in ["false", "False"]:
                value = False
            elif value in ["None", "none"]:
                value = None

            # Test if the value is a +ve integer
            elif str(value).isnumeric():
                value = int(value)
            # # Test if a negative integer (starts with '-') (or starts with a +)
            # elif value.startswith('-') and value[1:].isdigit():
            #     value = int(value)
            elif value[0] in ('-', '+') and value[1:].isdigit():
                value = int(value)
            # Otherwise test to see if it's a float
            else:
                try:
                    # See if the value is float by trying to cast it as a float (this will fail, if it's not)
                    value = float(value)
                except Exception as e:
                    pass
    finally:
        return value


def doubleToPatval10bit(inputVal):
    def chunk(val):
        valAsBin = bin(val)[2:]
        chunks = [valAsBin[i:i + 8] for i in range(0, len(valAsBin), 8)]
        return chunks

    multiplier = [1,10,100,1000]
    scaledValue = 0
    # Calculator multiplier selector no based on the size of the incoming no
    if inputVal >= 102.3:
        selector = 0        # Scale by '1'
    elif inputVal >= 10.23:
        selector = 1        # Scale by '10'
    elif inputVal >= 1.023:
        selector = 2        # Scale by '100'
    else:
        selector = 3        # Scale by '1000'


    scaledValue = int(inputVal * multiplier[selector]) # Multiplies inputVal by 1,10,100 or 1000 depending upon it's magnitude and casts as an int
    print (f"selector:{selector}, multiplier:{multiplier[selector]}, scaledValue:{scaledValue}")
    # The most logical next step is to then do.....
    msb = selector << 14 # Shift selector (a 2 bit value) 14 steps the left to make it the highest two bits of the 16bit value
    lsb = 0x3fff & scaledValue # Mask with '6 zeros and 10 ones' so that only the bottom 10 bits get through

    # Create aggregate value by 'OR'ing msb and lsb together
    msblsb = msb | lsb
    print(f"msblsb {chunk(msblsb)}")

    lsbmsb = (lsb<<8 ) | (msb >> 8) #<<WRONG! because LSB could be a 10 bit value (not a byte) therefore when shifted,
                                    # you could end up with an 18 bit value
    print(f"lsbmsb {chunk(lsbmsb)}")

    shiftedMSB = (msblsb & 0xFF00) >> 8
    shiftedLSB = (msblsb & 0x00FF) << 8
    reversedMsbLsb = shiftedMSB | shiftedLSB

    print(f"reversedMsbLsb {chunk(reversedMsbLsb)}")
    # print(f"lsb<<8 {hex(lsb<<8)}, {bin(lsb<<8)}, msb>>8{hex(msb>>8)}, {bin(msb>>8)}")
    return f"msblsb:{hex(msblsb)}, lsbmsb:{hex(lsbmsb)}, reversedMsbLsb {hex(reversedMsbLsb)}"

def doubleToPatval14bit(inputVal):
    def chunk(val):
        valAsBin = bin(val)[2:]
        chunks = [valAsBin[i:i + 8] for i in range(0, len(valAsBin), 8)]
        return chunks

    multiplier = [1,10,100,1000]
    scaledValue = 0
    # Calculator multiplier selector no based on the size of the incoming no
    if inputVal >= 1638.3:
        selector = 0        # Scale by '1'
    elif inputVal >= 163.83:
        selector = 1        # Scale by '10'
    elif inputVal >= 16.383:
        selector = 2        # Scale by '100'
    else:
        selector = 3        # Scale by '1000'


    scaledValue = int(inputVal * multiplier[selector]) # Multiplies inputVal by 1,10,100 or 1000 depending upon it's magnitude and casts as an int
    print (f"selector:{selector}, multiplier:{multiplier[selector]}, scaledValue:{scaledValue}")
    # The most logical next step is to then do.....
    msb = selector << 14 # Shift selector (a 2 bit value) 14 steps the left to make it the highest two bits of the 16bit value
    lsb = 0x3fff & scaledValue # Mask with '2 zeros and 14 ones' so that only the bottom 14 bits get through

    # Create aggregate value by 'OR'ing msb and lsb together
    msblsb = msb | lsb
    print(f"msblsb {chunk(msblsb)}")

    lsbmsb = (lsb<<8 ) | (msb >> 8) #<<WRONG! because LSB could be a 14 bit value (not a byte) therefore when shifted,
                                    # you could end up with an 18 bit value
    print(f"lsbmsb {chunk(lsbmsb)}")

    shiftedMSB = (msblsb & 0xFF00) >> 8
    shiftedLSB = (msblsb & 0x00FF) << 8
    reversedMsbLsb = shiftedMSB | shiftedLSB

    print(f"reversedMsbLsb {chunk(reversedMsbLsb)}")
    # print(f"lsb<<8 {hex(lsb<<8)}, {bin(lsb<<8)}, msb>>8{hex(msb>>8)}, {bin(msb>>8)}")
    return f"msblsb:{hex(msblsb)}, lsbmsb:{hex(lsbmsb)}, reversedMsbLsb {hex(reversedMsbLsb)}"

# Takes an existing Object, and spins it off as a subprocess
# objectType is the type of object (eg RtpGenerator) and initArgs[] is a list of parameters that would normally
# be expected to be passed to that objects __init__() method when it was first created
# Note: This won't work for all objects. In fact, it can only work for objects that can be pickled
# Therefore objects that take init args like file descriptors, sockets, mutexes etc wonlt work.
# The objects should to be self contained
class ProcessCreator(object):
    def __init__(self, targetObject, *args, processName=None, **kwargs) -> None:
        super().__init__()
        # print ("ProcessCreator called")
        # Take a copy of the source object type to ber created
        self.targetObject = targetObject
        # Take a copy of the list of args that will be passed to the constructor of the object specified
        self.initArgs = args
        self.initKwargs = kwargs
        self.processName = processName
        # Create the sub-process
        self.theNewProcess = self.__createProcess()


    # Returns a reference to the new process
    def getProcess(self):
        return self.theNewProcess

    # This method instantiates the Object specified by self.objectType and passes in args and kwargs
    def createObject(self):
        try:
            newObject = self.targetObject(*self.initArgs, **self.initKwargs)
        except Exception as e:
            raise Exception (f"ProcessCreator.__createObject() {e}")
        # # Now sit in infinite loop until some unspecified flag is set
        # while True:
        #     time.sleep(1)

    # Actually create the subprocess (with a name set accordingly)
    def __createProcess(self):
        try:
            p = mp.Process(target=self.createObject, name=self.processName, args=())
            p.daemon = False # If true, the
            p.start()
            # p.join(timeout=1)
            # If successful, return a reference to the newly created process
            return p
        except Exception as e:
            raise Exception (f"ProcessCreator.__createProcess() {e}")

# # Function to test the ProcessCreator class
# def testProcessCreator():
#     testTXDict = {},
#     testTXDictMutex = threading.Lock(),
#     testResultsDict = {},
#     testResultsDictMutex = threading.Lock()
#
#     args = [
#         "127.0.0.1",
#         2001,
#         1024 * 128,
#         1300,
#         12345,
#         -1,
#         testTXDict,
#         testTXDictMutex,  ## These can't be passed to a subprocess
#         testResultsDict,
#         testResultsDictMutex
#     ]
#     # attempt to create a subprocess
#     rtpGeneratorSubProcess = ProcessCreator(RtpGenerator, args)
#
#     while True:
#         print(str(datetime.datetime.now()))
#         time.sleep(5)

class TestClass(object):
    def __init__(self):
        self.a=1
        self.b="2"
        self.c=[3,4,5,6]
        # Create SecondClass as a child process
        proc = ProcessCreator(SecondClass, processName="SecondClass")
        while True:
            print("TestClass")
            time.sleep(1)
    def getValues(self):
        return self.a, self.b, self.c

class SecondClass(object):
    def __init__(self, ctrlPort, rxQueue, txQueue):
        self.a=1
        self.b="2"
        self.c=[3,4,5,6]
        self.rxQueue = rxQueue
        self.txQueue = txQueue
        x = 0
        # while True:
        #     print(f"SecondClass {x}")
        #     x += 1
        #     time.sleep(1)
        self.api = APIHelper(ctrlPort)
        self.theThread = threading.Thread(target=self.secondClassThread).start()
    def getValues(self):
        return self.a, self.b, self.c
    def secondClassThread(self):
        x = 0
        while True:
            # print(f"SecondClass Thread {x}")
            try:
                self.api.addMessage(f"SecondClass Thread {x} {type(self.rxQueue)}, {type(self.txQueue)}")
                if x > 5:
                    self.api.addMessage(f"SecondClass Thread Ending")
                    break
            except Exception as e:
                print(f"secondClassThread: {e}")
            x += 1
            time.sleep(3)


class ChildProcess(object):
    def __init__(self, ctrlPort):
        api=APIHelper(ctrlPort)
        x =0
        while True:
            # api.addMessage(f"childprocess alive {x}")
            print(f"childprocess alive {x}")
            x +=1
            time.sleep()

# Test Class to replicate an RtpPacketReceiver
class RxStreamDetector(object):
    def __init__(self, newStreamsQ):
        self.newStreamsQ = newStreamsQ  # Queue that will be sent back to main()
        self.mpManager = None # Placeholder - will hold a Multiprocessing.Manager object (to be created in
                                # the rxStreamDetectorThread
                                # For some reason, if you create the Manager object within  __init__(), it fails


        self.txQueue = None # Placeholder - will hold a Multiprocessing.Manager.Queue()


        # Start the thread
        t = threading.Thread(target=self.rxStreamDetectorThread)
        t.start()

    def rxStreamDetectorThread(self):
        self.mpManager = mp.Manager()  # Create Multiprocessor Manager object to allow creation of new queues via a proxy
                                # Manager.Queue() objects are pickleable and therefore able to be passed between proceses
                                # whereas Multiprocessing.Queue objects only seem to be able to be able to be passed
                                # 'downwards' from a parent to a child process.
                                # In this case, I'm dynamically creating rxQueues within a child process (RxStreamDetector)
                                # and wanting to send them back to another unrelated process (RxStream) via main()

        rxQueuesDict = {}       # Create dict to hold all the rxQueues

        self.txQueue = self.mpManager.Queue()      # Queue to hold messages *returned* by the RxStream objects
        streamsPendingDeletionQueue = self.mpManager.Queue()

        # Create a dict of new Rx Queues  with every iteration, put some dummy data onto it, add to newStreamsQ
        id = 1000 # Strating stream id value
        while id < 1011:
            try:
                # Create an rx Queue
                rxQueuesDict[id] = self.mpManager.Queue()
                # Put some dummy data into the rxQueue()
                rxQueuesDict[id].put({"dummyData": datetime.datetime.now()})

                # Create a dict to put onto the queue
                newStreamDefinition = {
                    "id": id,
                    "txQueue": self.txQueue,
                    "rxQueue": rxQueuesDict[id],
                    "streamsPendingDeletionQueue": streamsPendingDeletionQueue
                }
                # Add the newStream to the Q (complete with dummy data)
                self.newStreamsQ.put(newStreamDefinition)
            except Exception as e:
                print(f"ERR: mpQueueTestThread put({id}) {e}")
            id += 1

        x = 0
        # Put some random data (the current time) onto a randomly selected queue
        # and then read the txQueue to see if any new data has arrived
        while x < 20:
            rxQueueSelector = None
            try:
                # select a random rxQueue from rxQueuesDict
                # rxQueueSelector = random.randint(1000, 1010)
                rxQueueSelector = random.choice(list(rxQueuesDict))
                print (f"RxStreamDetector.rxStreamDetectorThread queue {rxQueueSelector} picked")
                # Put some random data (the current time) into that queue
                rxQueuesDict[rxQueueSelector].put(datetime.datetime.now())
            except Exception as e:
                print(f"ERR:RxStreamDetector.rxStreamDetectorThread rxQueuesDict[{rxQueueSelector}].put() + {e}")

            # NOw try to read the txQueue
            try:
                val = self.txQueue.get_nowait()
                print(f"_rxStreamDetectorThread txQueue val: {val}")
            except Empty:
                # print(f"_rxStreamDetectorThread txQueue Empty")
                pass
            except Exception as e:
                print(f"ERR: _rxStreamDetectorThread txQueue.get() {e}")

            # Now try to read the streamsPendingDeletionQueue
            try:
                rxQueueToBeDeleted = streamsPendingDeletionQueue.get_nowait()
                print(f"**RxStreamDetector.rxStreamDetectorThread rxQueue {rxQueueToBeDeleted} DELETE request")
                # Now delete that rxQueue from rxQueuesDict
                del rxQueuesDict[rxQueueToBeDeleted]
            except Empty:
                # print("RxStreamDetector.rxStreamDetectorThread -- No rxQueues to delete")
                pass
            except Exception as e:
                print(f"ERR:RxStreamDetector.rxStreamDetectorThread -- delete rxQueue {e}")


            x += 1
            time.sleep(1)
        print(f"_rxStreamDetectorThread ending {id}")


# Test class to replicate an RtpReceiveStream
class RxStream(object):
    def __init__(self, id, txQueue, rxQueue, streamsPendingDeletionQueue):
        self.id = id
        self.txQueue = txQueue
        self.rxQueue = rxQueue
        self.rxQueueReceivedCounter = 0 # Counts the no of objects received from self.rxQueue via .get()
        self.streamsPendingDeletionQueue = streamsPendingDeletionQueue
        # Start the thread
        t = threading.Thread(target=self.rxStreamThread)
        t.start()

    # Reads the rx Queue associated with this stream and puts on some dummy data into the tx Queue
    def rxStreamThread(self):
        while True:
            # Read the rxQueue
            try:
                val = self.rxQueue.get(timeout=1)
                print(f"RxStream rxQueue val {val}")
                # Increment the read counter
                self.rxQueueReceivedCounter += 1

                # If > 2 objects retrieved from the rxQueue, send a signal back to RxStreamDetector to cause
                # the deletion of the rxQueue associated with this stream
                if self.rxQueueReceivedCounter > 2:
                    print(f"RxStream.rxStreamThread({self.id}): 3 objects retrieved from rxQueue. Trigger queue deletion")
                    self.streamsPendingDeletionQueue.put(self.id)
                    # Now kill this RxStream object by ending this thread
                    break
                # put some dummy data onto the tx Queue
                try:
                    self.txQueue.put(f"RxStream {self.id} acknowledged {val}")
                except Exception as e:
                    print(f"ERR:RxStream txQueue.put {e}")
            except Empty:
                pass
            except Exception as e:
                print(f"ERR:RxStream rxQueue.get() {e}")
                # break
        print(f"##RxStream {self.id} ended")


class TxSimulator(object):
    def __init__(self, rxInstance):
        try:
            self.txQueue = rxInstance.txQueue
        except Exception as e:
            raise Exception(f"ERR: TxSimulator: acquire txQueue, {e}")

        # start the txSimulatorThread
        txThread = threading.Thread(target=self.txSimulatorThread)
        txThread.start()

    # Continually polls self.txQueue for new data
    def txSimulatorThread(self):
        print("txSimulatorThread starting")
        while True:
            # attempt to read the txQueue
            if self.txQueue is not None:
                try:
                    val = self.txQueue.get_nowait()
                    print(f"txSimulatorThread: txQueue incoming data: {val}")
                except Empty:
                    print(f"txSimulatorThread: txQueue EMPTY")
                    time.sleep(1)
                except Exception as e:
                    print(f"ERR:txSimulatorThread {e}")
                    time.sleep(1)
            else:
                print(f"xSimulatorThread: self.txQueue {self.txQueue}")
                time.sleep(1)


# Creates a Rx and TX pair
class TransceiverSimulator(object):
    def __init__(self, streamsPendingCreationQueue):
        self.streamsPendingCreationQueue = streamsPendingCreationQueue # Pass new stream definitions back to main

        try:
            # Create an Rx/Tx pair
            # Create the Rx'er (this generates the queues)
            rx = RxStreamDetector(self.streamsPendingCreationQueue)

            # Create the tx'er
            tx = TxSimulator(rx)
        except Exception as e:
            print(f"ERR:TransceiverSimulator.__init __(), {e}")





# Imports a previous stream snapshot file (*.isp) to allow the stats/event data for multiple streams to be recreated
# It returns a dict of dicts {syncsourceID:{{stats, events}}, ....} or raises an Exception on failure
def importHistoricStreamsSnapshot(filename):
    # Declare dict to hold the results of the import
    importedStreamsDict = {}
    try:
        # Import the snapshot file (which is a list of pickled events and stats dicts)
        importedSnapshotsList = importObjectFromDisk(filename)
        if len(importedSnapshotsList) > 0:
            # Initialise stats and eventsList
            stats = None
            eventsList = None
            for stream in importedSnapshotsList:
                streamID = stream[0]
                # Extract stats dict
                stats = stream[1]
                # Attempt to validate the keys/Values of the stats dict by reading each key
                for stat in stats:  # Iterate over keys
                    # This should (hopefully) cause an exception if a key/value can't be read
                    # We also use this opportunity to convert the exported snapshot stats values (that were
                    # all encoded as strings - on account of being obtained via the api) back to Python data types
                    # BUT Exclude stats["stream_friendly_name"] key, because that is a string and should remain so,
                    # even if it's numeric
                    if stat in ["stream_friendly_name"]:  # 'Exclude' list
                        pass
                    else:
                        x = convertStringToPythonDataType(stats[stat])
                        if not isinstance(stats[stat], type(x)):
                            # Utils.Message.addMessage(f"DBUG: Recreating stream. converted {stat} from {type(stats[stat])} to {type(x)}")
                            # assign the type-converted value back to the value in the dict
                            stats[stat] = x

                eventsList = stream[2]
                # Attempt to validate the keys/Values of the events list by reading the event no
                for event in eventsList:
                    # This should (hopefully) cause an exception if the Event.eventNo can't be read
                    eventNo = event.eventNo

                # stats{} and eventsList[] for this stream validated, so add to the output dict, keyed with the syncSource ID
                importedStreamsDict[stats["stream_syncSource"]] = {"statsDict":stats, "eventsList":eventsList}
        # return the dict contsaining the imported streams
        return importedStreamsDict
    except Exception as e:
        raise Exception(f"Utils.importHistoricStreamsSnapshot() {e}")

# Function to test Utils.importHistoricStreamsSnapshot()
def testImportHistoricStreamsSnapshot():
    importedStreamsDict = importHistoricStreamsSnapshot(Registry.streamsSnapshotFilename)
    print(f"importedStreamsDict {importedStreamsDict.keys()}")

# Creates a snapshot of all the current active streams (via the api) and exports to disk
# Raises an Exception on error
def createStreamsSnapshot(exportFilename, controllerTCPPort, controllerTCPAddress="127.0.0.1"):
    pass