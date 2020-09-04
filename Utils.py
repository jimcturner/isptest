#!/usr/bin/env python
# Defines useful non-core objects for use by isptest
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
from collections import deque
from functools import reduce
from queue import SimpleQueue

from Registry import Registry
from ipwhois import IPWhois, exceptions
import math

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
# Should return 'Windows' for Windows, or
def getOperatingSystem():
    current_os = platform.system()
    return current_os
# Returns a string listing the names of the currently running threads
# if asList = True, will return as a list of strings
def listCurrentThreads(asList = False):
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

    inputLength=len(inputString)
    # Determine whether input string is long enough to need fragmenting
    if maxLength <2:
        # The routine below breaks if maxLength = 1
        return -1
    if inputLength <= maxLength:
        return [[0, 1, inputLength, inputString]] # Notice it's a tuple within a list [[ ]]

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
                outputList.append([x,totalNumberOfFragments, inputLength, portion])
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
        Message.addMessage("ERR: unfragmentString() "+ str(e))

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

# This function will delete the specified streamID from an rtpRxStreamsDict{}
# It uses mutexes, so should be thread safe
# def removeRtpStreamFromDict(streamID, rtpStreamsDict, rtpStreamsDictMutex):
#     rtpStreamsDictMutex.acquire()
#     try:
#         # Attempt to remove the rtpStream from the dictionary
#         del rtpStreamsDict[streamID]
#     except Exception as e:
#         Message.addMessage("ERR: deleteRtpStreamObject(): ["+str(streamID)+"], "+str(e))
#     rtpStreamsDictMutex.release()

# A shortcut function that will create a new entry in the supplied dictionary
# It is used to (safely) populate rtpTxStreamsDict, rtpRxStreamsDict and rtpStreamResultsDict
# def addRtpStreamToDict(rtpStreamID, rtpStream, rtpStreamsDict, rtpStreamsDictMutex):
#     rtpStreamsDictMutex.acquire()
#     # Add the object to the specified dictionary with using rtpStreamID as the key
#     rtpStreamsDict[rtpStreamID] = rtpStream
#     rtpStreamsDictMutex.release()


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

    @classmethod
    def setVerbosity(cls, verbosity):
        cls.verbosityLevel = verbosity

    # This method will override the default filename
    @classmethod
    def setOutputFileName(cls, fileName):
        cls.outputFileName = fileName

    # Class method to add a new message to the list
    # Additionally, this method checks to see if the disk writing thread is active. If it is not, it will start it
    @classmethod
    def addMessage(cls, message):
        # Check status of disk writing thread. If it has not yet been started, it will be
        if cls.__writeMessagesToDiskThreadIsActive is False:
            try:
                # Set the flag to signal that the thread has been (or is being) started
                cls.__writeMessagesToDiskThreadIsActive = True
                # Create the thread object
                cls.writeMessagesToDiskThread = threading.Thread(target=cls.__writeMessagesToDiskThread, args=())
                # The daemon will automatically shut down one the main app ends
                cls.writeMessagesToDiskThread.daemon = True
                cls.writeMessagesToDiskThread.setName("____writeMessagesToDiskThread")
                cls.writeMessagesToDiskThread.start()

            except Exception as e:
                Message.addMessage("Message.addMessage() Couldn't start disk writing thread " + str(e))
                # Thread failed to start, so clear the flag
                cls.__writeMessagesToDiskThreadIsActive = False


        # Add the supplied message to the messages list as a tuple containing a timestamp and the message
        # newMessage = [datetime.datetime.now().strftime("%H:%M:%S"), message]
        newMessage = [datetime.datetime.now(), message]
        cls.messages.append(newMessage)

        # Now put the new message in the queue, to be picked up by the disk writer thread
        cls.__diskWriteQueue.put(newMessage)

    # class method to filter cls.messages[] based on the message prefix and cls.verbosityLevel and return a sublist
    @classmethod
    def getFilteredMessagesList(cls):
        # prefixes are ERR:, INFO: etc. Messages containing these prefixes may/may not be displayed
        # according to cls.verbosityLevel.
        # Currently for verbosityLevel = 0, all messages containing the strings in listOfFilters[] will be hidden
        # For verbosityLevel = 1, ERR: messages will be displayed
        # For verbosityLevel = 2, ERR: and INFO: messages will be displayed
        # For verbosityLevel = 3, ERR:, INFO: and DBUG: messages will be diplayed
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
        for message in cls.messages:
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
            # Test the message queue size. If there are messages, write them to disk
            if cls.__diskWriteQueue.qsize() > 0:
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

# Utility finctions to validate user input
# Check for integer (with optional min or max range)
# Raises an exception if not an integer or integer out of range
# class NotAnInteger(Exception):
#     def __init__(self, val):
#         self.val = val
#     # Define an error message to be returned
#     def __str__(self):
#         return "NotAnInteger Exception. " + str(self.val) + " is not a valid integer"
# class InvalidRangeSpecifier(Exception):
#     def __init__(self, val):
#         self.val = val
#         print ("InvalidRangeSpecifier raised\r")
#     # Define an error message to be returned
#     def __str__(self):
#         return "InvalidRangeSpecifier Exception. " + str(self.val) + " is not a valid integer"
# class IntegerTooSmall(Exception):
#     def __init__(self, val, min):
#         self.val = val
#         self.min = min
#         print ("IntegerTooSmall raised\r")
#     # Define an error message to be returned
#     def __str__(self):
#         return "IntegerTooSmall Exception. " + str(self.val) + " is less than the minimum specified " + str(self.min)
#
# class IntegerTooLarge(Exception):
#     def __init__(self, val, max):
#         self.val = val
#         self.min = max
#         print ("IntegerTooLarge raised\r")
#     # Define an error message to be returned
#     def __str__(self):
#         return "IntegerTooLarge Exception. " + str(self.val) + " is greater than the maximum specified " + str(self.max)
#
# def isInteger(val, min = None, max = None):
#     try:
#         # Test val to see if it is an integer, if not, raise a NotAnInteger Exception
#         val = int(val) + 1 -1
#         # Has a minimum value been specified?
#         if min != None:
#             print ("min: " + str(min) + "\r")
#             try:
#                 # Test to see if the 'min' value is an int
#                 min = int(min) + 1 - 1
#                 # if it is, test val against it
#                 if int(val) < int(min):
#                     # If val to small, raise an exception
#                     raise IntegerTooSmall(min)
#             except:
#                 # If min is not an integer, raise an InvalidRangeSpecifier Exception
#                 raise InvalidRangeSpecifier(min)
#         # Has a max value been specified?
#         if max != None:
#             # Test to see if the 'max' value is an integer
#             print ("max: " + str(max) + "\r")
#             try:
#                 max = int(max) + 1 - 1
#                 # if 'max' is a valid integer, check val against it
#                 if val > max:
#                     # If val is larger than allowed by 'max', raise an exception
#                     raise IntegerTooLarge(max)
#             except:
#                 raise InvalidRangeSpecifier(max)
#
#     except:
#         # Raise an Exception (and pass val to it, so we can report an error message)
#         raise NotAnInteger(val)


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

    # A list of ip addresses in the process of being looked up (by the __whoisReolverThread)
    pendingQueries = {}

    whoisAuthorities = ["whois.ripe.net", "whois.iana.org"]

    # Self-rolled whois querier based on scapy.utils.whois
    # It will return a dictionary of the whois information
    # 'netname' seems to be the most useful parameter to me - this holds
    # Example usage:
    # z = WhoisResolver.whoisLookup("212.58.231.0", "whois.ripe.net")
    # print(z["netname"])
    # In theory, it should be able to do a reverse lookup (by supplying domain name as an argument, although this doesn't
    # seem to work terribly well
    # Note: this is a blocking method
    # example whoisAuthorities are ["whois.ripe.net", "whois.iana.org"]
    # Note: Each authority only looks a geographic region. If they don't know about a domain, then they should be
    # able to redirect you to an authority that does know
    # In practice, I decided it would just be easier to make use of the IPWhois library becasuse this already takes
    # redirections (and probably may other things that I haven't thought about)
    @classmethod
    def simpleWhoisLookup(cls, ip_address, authorityHostname):
        """Whois client for Python"""
        whois_ip = str(ip_address)
        try:
            query = socket.gethostbyname(whois_ip)
            # print ("result from socket.gethostbyname() " + str(query))
        except Exception:
            query = whois_ip
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # s.connect(("whois.ripe.net", 43))
        s.connect(("whois.iana.org", 43))
        s.send(query.encode("utf8") + b"\r\n")
        answer = b""
        while True:
            d = s.recv(4096)
            answer += d
            if not d:
                break
        s.close()
        ignore_tag = b"remarks:"
        # ignore all lines starting with the ignore_tag
        # This will create a list with each new line as an element
        lines = [line for line in answer.split(b"\n") if
                 not line or (line and not line.startswith(ignore_tag))]  # noqa: E501
        # remove empty lines at the bottom
        for i in range(1, len(lines)):
            if not lines[-i].strip():
                del lines[-i]
            else:
                break
        # return lines[3:]
        # Now convert lines[] into a dictionary (as this is more useful)
        # Headings are always proceeded with a colon, so use this as the indicator for a heading. This will become the key
        # The next list entry will be presumed to be the value
        # The first three lines can be ignored as they contain Ts and Cs text
        whoisDict = {}
        try:
            if len(lines) > 3:
                for line in range(3, len(lines)):
                    # isolate individual line as a string. Remove newline char from end
                    x = str(lines[line],'utf-8').split("\n")[0]
                    # Does the array element contain a colon? If so, split into a list
                    splitLine = x.split(":")
                    if len(splitLine) > 1:
                        key = splitLine[0]
                        value = splitLine[1].lstrip()
                        # Create new dictionary element
                        whoisDict[key] = value
        except:
            whoisDict = None
        return whoisDict
        # return b"\n".join(lines[3:])

    # This is non-blocking method to query the cls.whoisCache{} dict.
    # If the entry exists it will return it, otherwise it will add the request to pendingQueries{} to be picked up
    # by __whoisResolverThread
    @classmethod
    def queryWhoisCache(cls, ip_address):
        # Is there already an entry for this address in whoisCache?
        if ip_address in cls.whoisCache:
            # Update the 'last accessed' timestamp
            cls.whoisCache[ip_address][2] = datetime.datetime.now()
            return cls.whoisCache[ip_address]
        else:
            # There doesn't yet exist an entry, so add to the pending list (and in the mean time, return None
            cls.pendingQueries[ip_address] = None
            return None

    # Returns the current whoisCache dict
    @classmethod
    def getWhoisCache(cls):
        return cls.whoisCache

    # Returns the current pendingQueries dict
    @classmethod
    def getPendingQueries(cls):
        return cls.pendingQueries


    # This constructor method sets running a background thread to maintain a cache of the previously queried domains
    def __init__(self):
        self.whoisLookupThreadActive = True

        # Create a background thread to do the querying
        self.whoisLookupThread = threading.Thread(target=self.__whoisLookupThread, args=())
        self.whoisLookupThread.daemon = False
        self.whoisLookupThread.setName("__whoisLookupThread")
        self.whoisLookupThread.start()

    # This method queries the internet whois servers to determine thw owner (ASN_Description) of the IP address
    @classmethod
    def whoisLookup(cls, addr, retries=1):
        # See here for docs: https://ipwhois.readthedocs.io/en/latest/index.html
        # Create an IPWhois object
        obj = IPWhois(addr)
        # The function for retrieving and parsing whois information for an IP address via port 43
        # lookup
        whoisInfo = obj.lookup_whois(retry_count=retries)

        # return ret['asn_description'] # This is probably the most useful field
        return whoisInfo

    # Blocking method to cause the object to die (by killing the thread)
    def kill(self):
        # Set the flag to false
        self.whoisLookupThreadActive = False
        # Block until the thread ends
        Message.addMessage("Waiting for whoisLookupThread to timeout. Please be patient....")
        self.whoisLookupThread.join()
        Message.addMessage("DBUG:WhoisResolver. whoisLookupThread has ended")

    # This method will examine the lastAccessedTimestamp of the entries in the self.whoIsCache{} dict
    # and automatically re-check or purge old entries
    def __houseKeep(self):
        pass

    # Background thread to continually monitor the lists of IP addresses picked added to pendingQueries{}
    # and determine the owner of that address
    # Once the address has been looked up, it's details will be added to whoisCache{} and thus removed from the
    # pendingQueries{} dict because it has been dealt with
    def __whoisLookupThread(self):
        Message.addMessage("DBUG:WhoisResolver.__whoisLookupThread started")
        while self.whoisLookupThreadActive:
            address = None

            if len(WhoisResolver.pendingQueries) > 0:
                # Take a snapshot of the class var WhoisResolver.pendingQueries{}
                # This may be modified outside of this thread so can't use original
                #Iterate over pendingQueries dict
                addressesToQuery = dict(WhoisResolver.pendingQueries)
                for address in addressesToQuery:
                    # Check status of thread controller flag (otherwise we'd have to wait for the entire  loop to iterate)
                    if self.whoisLookupThreadActive is False:
                        break
                    dateCreated = datetime.datetime.now()
                    lastAccessed = dateCreated
                    try:
                        # Query the supplied ip address
                        whoisDetails = WhoisResolver.whoisLookup(address)
                        # Add the the ip details and time created entry to whoisCache{}
                        WhoisResolver.whoisCache[address] = [whoisDetails, dateCreated, lastAccessed]
                    except exceptions.IPDefinedError as e:
                        # This exception will occur if a non-public address is queried (eg 0.0.0.0, 192.168.0.0, 127.0.0.1 etc)
                        dateCreated = datetime.datetime.now()
                        lastAccessed = dateCreated
                        # Create an entry for each address with a useful description by parsing the error message
                        # Or by looking at the address itself
                        desc = ""
                        if address == "127.0.0.1":
                            desc = "Loopback"
                        elif address == "0.0.0.0":
                            desc = "Router didn't respond"
                        elif str(e).find('Private') > 0:
                            desc = "Local address"
                        else:
                            desc = str(e)
                        # Create a new entry for this address (with a locally generated 'asn_description' key)
                        WhoisResolver.whoisCache[address] = [{'asn_description':desc}, dateCreated, lastAccessed]
                    except (exceptions.WhoisLookupError, exceptions.ASNRegistryError) as e:
                        # Create an entry for the address with the error message as the description
                        WhoisResolver.whoisCache[address] = [{'asn_description': str(e)}, dateCreated, lastAccessed]

                    # Catch all other errors
                    except Exception as e:
                        # Create an entry for the address with the error message as the description
                        WhoisResolver.whoisCache[address] = [{'asn_description': str(e)}, dateCreated, lastAccessed]
                        Message.addMessage("ERR:WhoisResolver.__whoisLookupThread().whoisLookup(" + \
                                             str(address) + ") "+ str(type(e)) + ", " + str(e))

            # Now check for duplicate addresses in both the whoisCache and pendingQueries dicts.
            # If present in both, remove from the pendingQueries as already dealt with
            try:
                for address in WhoisResolver.whoisCache:
                    if address in WhoisResolver.pendingQueries:
                        # Remove from pending dict
                        del WhoisResolver.pendingQueries[address]
            except Exception as e:
                Message.addMessage("ERR:WhoisResolver.__whoisLookupThread().del pendingQueries (" + \
                                         str(address) + ") " + str(e))

            time.sleep(0.5)
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
        "11) Berlin not detecting a completely different route"
        ]
        ,
        [
            [(192, 168, 224, 252), (82, 194, 125, 65), (84, 19, 200, 41), (62, 214, 37, 142), (80, 81, 192, 59), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (132, 185, 249, 7)],
            [(192, 168, 224, 253), (0, 0, 0, 0), (212, 74, 73, 101), (212, 74, 73, 101), (80, 81, 192, 59), (0, 0, 0,0),(0, 0, 0, 0), (0, 0, 0, 0), (132, 185, 249, 9), (212, 58, 231, 65)],
            117,
            117,
            True,
            "12) Berlin not detecting a completely different route"
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
                    # Utils.Message.addMessage("DBUG:hopsList len changed but rxTTL didn't. Ignored hopList change " +\
                    #     "prevLen: " + str(len(prevHopsList)) + ", Len:" + str(len(hopsList)) + ", prevTTL:" + \
                    #                          str(prevRxTTL) + ", TTL:" + str(rxTTL))
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
                # Note, we can only compare lists with lists. For some reason, the hops within hopList
                # seem to be being converted to tuples. Therefore we must cast the hop as a list just in case
                prevHop = list(prevHopsList[hopNo])
                currentHop = list(hopsList[hopNo])

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
                elif prevHop == noResponse and currentHop != noResponse:
                    hopsListHasChanged = False

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
