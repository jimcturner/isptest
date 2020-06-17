#!/usr/bin/env python
# Defines useful non-core objects for use by isptest

import time
import datetime
import socket
import threading
import platform

import psutil

from Registry import Registry
from ipwhois import IPWhois, exceptions
import math
# Formats a datetime.timedelta object as a simple string hh:mm:ss
def dtstrft(timeDelta):
    total_seconds = int(timeDelta.total_seconds())
    hours, remainder = divmod(total_seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)

    return str(hours).zfill(2)+":"+str(minutes).zfill(2)+":"+str(seconds).zfill(2)

# Returns the IP address of the network interface currently used as the default route to the internet (if no args supplied)
# Alternatively, for a supplied ip address, it will return ip address of the interface that, according to the OS
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
    if value >= 1048576:
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


# Defines a class to measure CPU usage
class CPU(object):
    process = psutil.Process()
    # Take initial CPU usage sample
    __cpuUsage = process.cpu_percent()

    # Class method to return CPU usage
    @classmethod
    def getUsage(cls):
        return cls.process.cpu_percent()

# Define a class to act as a general message store/server for error/info messages
# generated by this script. This class will auto-housekeep. It will discard
# messages the oldest messages if the messages[] list length exceeds historicMessagesToKeep
class Message(object):
    # Define list to hold messages
    messages = []
    # No. of messages to keep before they're discarded
    historicMessagesToKeep = 50

    # Determines which messages will be revealed by getMessages
    # 0 = no warning messages, > 0 = warning messages displayed
    verbosityLevel = 0

    @classmethod
    def setVerbosity(cls, verbosity):
        cls.verbosityLevel = verbosity

    # Class method to add a new message to the list
    @classmethod
    def addMessage(cls, message):
        # Add the supplied message to the messages list as a tuple containing a timestamp
        cls.messages.append([datetime.datetime.now().strftime("%H:%M:%S"), message])
        # Test length of messages list. Longer than historicMessagesToKeep?
        if len(cls.messages) > cls.historicMessagesToKeep:
            # Remove first (oldest) message
            del cls.messages[:1]
        # Now log the message to disk
        try:

            fh = open(Registry.messageLogFilename,"a+")
            logString = datetime.datetime.now().strftime("%H:%M:%S") + ": " + str(message) + "\n"
            fh.write(logString)
            fh.close()
        except Exception as e:
            pass


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
# Pastes text to PastBin.com (using either the default, or supplied Dev key)
# Returns a URL of the page showing the text
# Note: Pastes are instructed to delete after 10 minutes
def pasteBin(textToPaste, title='', api_dev_key='78c625162b816673e6b3ecc2750ee741'):
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