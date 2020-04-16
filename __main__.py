#!/usr/bin/env python
#
# Python packet sniffer
#
# 
from __future__ import unicode_literals # Required for prompt_toolkit
import sys
# Tests the current Python interpreter version
def testPythonVersion(majorVersionNo, minorVersionNumber):
    # If the major and minor version number is not satisfied
    # i.e the installed version is < than majorVersionNo.minorVersionNumber (eg 3.6) it will
    # call exit() with an error message
    import sys
    # Get current Python version
    version = sys.version_info
    def printErrorMessage():
        print("You're not running a latest enough version of Python " +
              str(version[0]) + "." + str(version[1]) + ". isptest requires >3.6:\r")
        print("\t------\r")
        print("\tHint: Python3 *might* be installed. Try re-running using 'python3 [args]'\r")
        print("\tor else, try python [tab] which (on OSX and Linux) should list the possible python\r")
        print("\tversions installed on this system\r")

    if int(version[0]) < majorVersionNo:  # Check major release version):
        if int(version[1]) < minorVersionNumber:  # Check minor version
            printErrorMessage()
            exit()
        printErrorMessage()
        exit()
    else:
        # Else Installed Python version satisfies minimum requirements
        pass
# Check for minimum python version (currently 3.6)
testPythonVersion(3,6)


import socket
import os
# import binascii
import signal # used for trappoing ctrl-c (SIGINT)
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
import json
from abc import ABCMeta, abstractmethod  # Used for event abstract class
from copy import deepcopy
import pickle
# Non standard external libraries (need importing with pip)
from terminaltables import SingleTable  # Used for pretty tables in displayThread
from colorama import init, Fore, Back, Style # Used to allow ansi escape sequences to work on Windows
from validator_collection import validators, errors
import six  # Required for strings being passed to prompt_toolkit dialogues (they won't accept Python2 strings)


# from prompt_toolkit import prompt, shortcuts   # Note, had to be installed with  pip install --ignore-installed six prompt_toolkit --user
from prompt_toolkit.shortcuts import message_dialog, yes_no_dialog, input_dialog
from prompt_toolkit.styles import Style

# Additional experimental libraries
import pyperclip
# Additonal libraries required (of my own making)
from RtpStreams import RtpReceiveStream, RtpGenerator, RtpStreamResults, Glitch
from Utils import *
from Custom_prompt_toolkit_mods import multi_input_dialog



####################################################################################
# Utility Classes


# Define a utility class to help with screen drawing
class Term(object):
    # Define a function to get the size of the current console terminal.
    # This should hopefully work on Windows, OSX and Linux
    # From https://stackoverflow.com/questions/566746/how-to-get-linux-console-window-width-in-python
    # Returns a tuple contain the no of columns, rows
    @classmethod
    def getTerminalSize(cls):
        import platform
        current_os = platform.system()
        tuple_xy = None
        if current_os == 'Windows':
            tuple_xy = cls._getTerminalSize_windows()
            if tuple_xy is None:
                tuple_xy = cls._getTerminalSize_tput()
                # needed for window's python in cygwin's xterm!
        if current_os == 'Linux' or current_os == 'Darwin' or current_os.startswith('CYGWIN'):
            tuple_xy = cls._getTerminalSize_linux()
        if tuple_xy is None:
            tuple_xy = (80, 25)  # default value
        return tuple_xy

    @classmethod
    def _getTerminalSize_windows(cls):
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

    @classmethod
    def _getTerminalSize_tput(cls):
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
            return cols, rows
        except:
            return None

    @classmethod
    def _getTerminalSize_linux(cls):
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

    @classmethod
    def getch(cls):
    # Define a getch() function to catch keystrokes (for control of the RTP Generator thread)
    # This code has been lifted from https://gist.github.com/jfktrey/8928865
        if platform.system() == "Windows":
            import msvcrt
            return msvcrt.getch()

        else:
            import tty, termios, sys
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch

    # Use the following colour enumerations in place of unfriendly numbers when specifying colours
    # in calls to Term.printAt() etc
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    RESET = 9
    # Black on White, normal brightness - shorthand
    BlaWh = "\033[22m"+"\033[30m"+"\033[47m"
    # Black on Cyan, dim brightness
    BlaCy = "\033[2m"+"\033[30m"+"\033[46m"
    # Cyan on black
    CyBla = "\033[36m"+"\033[40m"
    # White on blue
    WhiBlu = "\033[37m"+"\033[44m"
    # White on black
    WhBla = "\033[37m"+"\033[40m"
    # white on red
    WhiRed = "\033[37m"+"\033[41m"
    # Red on White
    RedWhi = "\033[31m"+"\033[47m"

    DIM = "\033[2m"

    # Ascii seq to move the cursor to 1,1 (the origin)
    HOME = "\033[0;0H"

    # Utility function to convert a colour index no into the equivalent ASCII foreground colour escape sequence
    # invoke using y=FG(x)
    @classmethod
    def FG (cls,x):
        return "\033[3"+str(int(x))+"m"

    # Utility function to convert a colour index no into the equivalent ASCII background colour escape sequence
    # invoke using y=BG(x)
    @classmethod
    def BG (cls,x):
        return "\033[4"+str(int(x))+"m"

    # Utility function to convert x,y (column,row) into an ascii escape sequence to move the cursor
    # invoke using z=FG(x,y) where x is the column, y is the row
    @classmethod
    def XY (cls,x,y):
        return "\033["+str(int(y))+";"+str(int(x))+"f"

    @classmethod
    def clearScreen(cls):
        # Clears the screen and moves cursor to (0,0)
        # Clear screen
        print ("\033[2J")
        # Move cursor to 0,0,
        print ("\033[0;0H")

    @classmethod
    def clearLine(cls, yPos):
        # clears the line specified in yPos
        # Go to specified line and clear it
        print ("\033["+str(int(yPos))+";0H"+"\033[2K")

    @classmethod
    def enterAlternateScreen(cls):
        # Switch to an alternate screen buffer (may not work predictably in Windows)
        if platform.system() != "Windows":
            print ("\033[?1049h")



    @classmethod
    def clearTerminalScrollbackBuffer(cls):
        # Clear scrollback buffer
        print ("\033[3J")

    @classmethod
    def exitAlternateScreen(cls):

        # Revert to original terminal screen
        if platform.system() != "Windows":
            print ("\033[?1049l")

    @classmethod
    def printAt(cls,text, xPos, yPos, *args):
        # Prints text at screen position xPos, yPos (NOTE: 1,1 is top left)
        # Last argument is an optional colour [foreground],
        # or [foreground, background]
        # 0 black, 1 red, 2 green, 3 yellow, 4 blue, 5 magenta, 6 cyan, 7 white, 9 reset

        try:
            if len(args) == 1:
                try:

                    # Foreground Colour parameter supplied
                    print (Term.FG(args[0]) +
                           Term.XY(xPos,yPos)+
                           str(text) + Term.HOME)
                except:
                    # invalid colour parameter supplied
                    print (Term.XY(xPos,yPos) + str(text) + Term.HOME)

            elif len(args) == 2:
                try:
                    # Foreground and background colour parameter supplied
                    print (Term.FG(args[0]) +      # Foreground
                           Term.BG(args[1]) +    # Background
                           Term.XY(xPos,yPos)+
                           str(text) + Term.HOME)
                except:
                    # invalid colour parameter supplied
                    print (Term.XY(xPos) + str(text) + Term.HOME)
            else:
                # No colour parameter supplied
                print (Term.XY(xPos,yPos) + str(text) + Term.HOME)

        except Exception as e:
            # Failing everything else, do a plain old print with a CR at the end
            print(str(text)+", "+str(e)+"\r")

    @classmethod
    def printCentered(cls,text,yPos, *args):
        # Centres text on the page.
        # Optional foreground or [foreground,background] options
        # 0 black, 1 red, 2 green, 3 yellow, 4 blue, 5 magenta, 6 cyan, 7 white, 9 reset
        # Get terminal width
        width,height = cls.getTerminalSize()
        stringLength=len(text)
        xPos = (width/2) - (stringLength/2)
        # cls.printAt(text, xPos, yPos, *args)
        cls.printAt(text, xPos, 1, *args)

    @classmethod
    def printRightJustified(cls, text, yPos, *args):
        # Right justifies text on the page.
        # Optional foreground or [foreground,background] options
        # 0 black, 1 red, 2 green, 3 yellow, 4 blue, 5 magenta, 6 cyan, 7 white, 9 reset
        # Get terminal width
        width, height = cls.getTerminalSize()
        stringLength = len(text)
        xPos=width - stringLength + 1
        if xPos < 0:
            xPos = 0
        cls.printAt(text, xPos, yPos, *args)

    @classmethod
    def setBackgroundColourSingleLine(cls, xPos, yPos, colour):

        # Paints the specified line a colour from the starting xPos position
        # It will then return the cursor to the origin
        # 0 black, 1 red, 2 green, 3 yellow, 4 blue, 5 magenta, 6 cyan, 7 white, 9 reset
        width, height = cls.getTerminalSize()
        # Create a string of spaces to fill an entire terminal width
        blankString = ""
        for x in range (0,(width- xPos+1)):
            blankString += " "
        try:
            print ("\033[4" + str(int(colour)) + "m" +
                   "\033[" + str(yPos) + ";" + str(xPos)
                   + "H" + blankString + "\033[" + str(yPos)+";" + str(1)+"H"+"\033[1;1H")
        except:
            pass

    @classmethod
    def setBackgroundColour(cls, colour):
        # Paints the specified background colour
        # 0 black, 1 red, 2 green, 3 yellow, 4 blue, 5 magenta, 6 cyan, 7 white, 9 reset
        # Get terminal width
        width, height = cls.getTerminalSize()
        for lineNo in range (1,height):
            cls.setBackgroundColourSingleLine(1,lineNo,colour)

    @classmethod
    def printTitleBar(cls,text,row, fgColour, bgColour):
        # Draws an inverse video bar with a centered title string
        # Draw inverse video horizontal bar
        Term.setBackgroundColourSingleLine(1,row,bgColour)
        # Write text
        Term.printCentered(text,row,fgColour,bgColour)

    # Prints a table generated by createTable() at position xPos,Ypos
    @classmethod
    def printTable(cls,list,xPos,yPos,tableWidth,*colourArgs):
        # Renders a list (such as table data) at specified xPos, Ypos
        # Optional colourargs are foreground or [foreground, background]
        # It will create a pseudo shadow beneath the list (table)

        # Move cursor to start position and set colour
        print(Term.XY(xPos,yPos))
        # Test to see if a foreground colour has been specified
        if len(colourArgs)== 1:
            colourString = Term.FG(colourArgs[0])
        # Otherwise test to see if a foreground and background colour has been specified
        elif len(colourArgs) > 1:
            colourString = Term.FG(colourArgs[0])+Term.BG(colourArgs[1])
        shadowRHS = ""

        # Iterate over list
        for x in range(0,len(list)):
            if x>0:
                shadowRHS=Term.BG(Term.BLACK)+" "
            # Term.printAt(list[x]),xPos,yPos+x)
            print(Term.XY(xPos,yPos)+colourString + list[x]+shadowRHS)
            yPos+=1
        # Create bottom black line as a shadow (consists of a string of blank spaces with black as bg colour)
        # the same width as the table but offset by 1
        shadowBottom = Term.BG(Term.BLACK)+(" " * tableWidth)

        print (Term.XY(xPos+1,yPos)+shadowBottom+Term.HOME)

    # This method will take a dictionary and turn it into a two column table using terminaltables.Singletable
    @classmethod
    def createTable(self, inputDictionary, title):
        # This method will take a dictionary and turn it into a two column table using terminaltables.Singletable
        # it will return the table as a list of strings

        # Create two separate lists, one of the dictionary keys and one of the values
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

        # Remove all padding to save space on the screen
        table.padding_left=0
        table.padding_right=0
        width = table.table_width
        height = len(keys) + 2  # Takes into account the top/bottom border
        # Note: width parameter doesn't take into account the fact I've disabled cell
        # padding. Therefore manually deduct '4' from the width as this is by definition
        # a two column table (because its data is sourced from a dictionary (with keys and values)
        # return (width-4), height, table.table.splitlines()
        return width, height, table.table.splitlines()

######### Utility functions



# Creates and maintains an updated list from the contents of a changing dictionary
def __updateAvailableStreamsList(rtpStreamList, rtpStreamDict, rtpStreamDictMutex):
    # This is a utility function for __displayThread
    # It's job is to compare the current working list in use by __displayThread (currentStreamList[])
    # with the rtpStreamDict{} dictionary of active rtpRxStreams or rtpTxStreams (maintained by main())
    # If will replicate any additions/deletions to objects in rtpStreamDict{} to currentStreamList[]
    # Crucially, the order of currentStreamList[] will be maintained so that it will represent a
    # chronological record of the order in which streams were added. This is very useful for display purposes
    # because __displayThread relies upon the index no of the entries in currentStreamList[]

    # It's a bit like a C function in that it doesn't return anything. Instead, the arguments supplied
    # (a list and a dictionary) are mutable, and therefore act like pointers. Therefore this function
    # can manipulate them directly.

    # 1) Iterate over keys of rtpStreamDict{} to get latest list of streams
    rtpStreamDictMutex.acquire()
    newStreamsList = []
    for k, v in rtpStreamDict.items():
        newStreamsList.append(k)
    rtpStreamDictMutex.release()

    # 2) Create sublist of current known rtpStreamList
    currentStreamsList = []
    for k in rtpStreamList:
        currentStreamsList.append(k[0])

    # 3) Do set(new)^set(current) to get difference between the two lists (as another list)
    diff = set(currentStreamsList) ^ set(newStreamsList)
    # 4) do set(new)&set(diff) to get add list
    addList = set(newStreamsList) & set(diff)
    # 5) do set (current)&set(diff) to get del list
    deleteList = set(currentStreamsList) & set(diff)

    # 6) Add new streams to rtpStreamList
    for streamID in addList:
        # Create tuple containing the stream id, the stream object itself and an index
        x = [streamID, rtpStreamDict[streamID], 0]
        # Append the new tuple to rtpStreamList[]
        rtpStreamList.append(x)
        Message.addMessage("INFO: __updateAvailableStreamsList() Added stream: " + str(x[0]) + ", " + str(type(x[1])))
    for streamID in deleteList:
        # Iterate over tuples in rtpStreamList[] searching for a match
        for index, stream in enumerate(rtpStreamList):
            if stream[0] == streamID:
                # If stream found, delete that tuple from the list
                Message.addMessage("INFO: __updateAvailableStreamsList() Removing stream " + str(stream[0]) + ", " + str(type(stream[1])))
                try:
                    rtpStreamList.pop(index)
                except Exception as e:
                    Message.addMessage("ERR: __updateAvailableStreamsList: "+str(e))
                break

    # 8) Check that rtpStreamList and rtpStreamDict are actually looking at the same objects in memory
    # It's possible that duplicate streams with the same stream ID can lead to orphan streams remaining
    # in rtpStreamList.
    # To check, we actually need to compare the objects in both lists of objects. Using the 'is' keyword
    # confirms that they are the same object (as opposed to the same type of object)
    rtpStreamDictMutex.acquire()
    for stream in rtpStreamList:
        try:
            if stream[1] is not rtpStreamDict[stream[0]]:
                Message.addMessage("ERR:__updateAvailableStreamsList() Object mismatch for streamID "+str(stream[0])+". Repointing to correct object")
                # Now re-point rtpStreamList to the correct version of that object
                # by assigning the correct object to the entry in rtpStreamList[]
                stream[1]=rtpStreamDict[stream[0]]
        except Exception as e:
            Message.addMessage("ERR:__updateAvailableStreamsList(), rtpStreamDictkey error for stream "+str(stream[0])+", "+str(e))
    rtpStreamDictMutex.release()
    # 9) delete newStreamsList, currentStreamsList, diff, addList and deleteList
    del newStreamsList
    del currentStreamsList
    del diff
    del addList
    del deleteList

    # 10) Optionally recalculate rtpStreamList indices - Note these shouldn't change unless a stream has been deleted
    for index, stream in enumerate(rtpStreamList):
        # Write the list index value to the third element of the stream tuple
        stream[2]=index

class InvalidTxRateSpecifier(Exception):
    pass

# A class that will be responsible for rendering the display and catching keyboard output
class UI(object):
    def __init__(self,operationMode, specialFeaturesModeFlag,
                    rtpTxStreamsDict, rtpTxStreamsDictMutex,
                    rtpRxStreamsDict, rtpRxStreamsDictMutex,
                    rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex,
                    UDP_RX_IP, UDP_RX_PORT):

        self.operationMode = operationMode
        self.specialFeaturesModeFlag = specialFeaturesModeFlag
        self.rtpTxStreamsDict = rtpTxStreamsDict
        self.rtpTxStreamsDictMutex = rtpTxStreamsDictMutex
        self.rtpRxStreamsDict = rtpRxStreamsDict
        self.rtpRxStreamsDictMutex = rtpRxStreamsDictMutex
        self.rtpTxStreamResultsDict = rtpTxStreamResultsDict
        self.rtpTxStreamResultsDictMutex = rtpTxStreamResultsDictMutex
        self.UDP_RX_IP = UDP_RX_IP
        self.UDP_RX_PORT = UDP_RX_PORT

        # If true, this will cause renderDisplayThread to put up a quit y/n? prompt
        self.displayQuitDialogueFlag = False
        # threading.Event object used to intentionally block the showShutDownDialogue() method
        self.quitDialogueNotActiveFlag = threading.Event()
        # This will store the result of the user response
        self.quitConfirmed = False

        # Use to control the display of the Events List dialogue
        self.displayEventsTable = False
        # Used by the EventsTable (and Traceroute table). Keeps track of the current display page
        self.tablePageNo = 0
        # Used by the EventsTable and CopyToClipboard/PasteBin.
        # Currently, if the list is populated, the events table will only show that type of Event
        self.filterListForDisplayedEvents = None

        # Thread running flags
        self.keysPressedThreadActive = True
        self.renderDisplayThreadActive = True
        self.detectTerminalSizeThreadActive = True

        # Stores the last pressed keystroke
        self.keyPressed = None

        # Enables keyboard key press detection via __getch()
        self.enableGetch = threading.Event()
        self.wakeUpUI = threading.Event()

        # Flag to trigger redrawing of the screen
        self.redrawScreen = True
        # Get initial size of terminal
        self.currentTermWidth, self.currentTermHeight = Term.getTerminalSize()

        # Declare lists to hold list of available rx and tx streams that can be displayed

        # These lists are a list of tuples [x,y,z] where
        # [x=streamID (as a string), y=the tx/rx object itself, z=an index value]
        #
        # The array is populated by the use of the utility function __updateAvailableStreamsList()
        # Meanwhile, main() is declaring three dictionaries, rtpTxStreamsDict, rtpTxResultsDict and  rtpRxStreamsDict
        # The issue with these dictionaries is that the order of them can change (when you iterate through them) making them
        # unsuitable for __displayThread which needs to maintain a chronological order of streams added/removed for display
        # and control purposes
        #
        # Therefore the job of __updateAvailableStreamsList() is to poll the supplied dictionary and synchronise any changes
        # (additions or deletions) in the dictionaries to the corresponding lists

        self.availableRtpRxStreamList = []
        self.availableRtpTxStreamList = []
        self.availableRtpTxResultsList = []

        self.selectedView = 0  # Keeps track of which view is currently being displayed
        self.selectedTableRow = 0  # Keeps track of the selected row on the stream table
        self.streamTableFirstRow = 0  # Tracks the current starting row of the stream table data
        self.streamTableLastRow = 0  # Tracks the current end row of the stream table data
        self.selectedStream = None  # Tracks the stream currently highlighted in the streams table
        self.selectedStreamID = 0 # Tracks the sync source ID of the stream currebtly highlighted
        # Screen label showing the available key commands (depending upon mode)
        self.keyCommandsString = "[<][>][^][v] navigate, [d]elete, [s]et name, [e]rrors, abo[u]t even[t]s"

        self.txStreamModifierCommandsString = "TX  modifier: [o/p] src ID, [k/l] length, [n/m] tx bps, [h/j] lifetime, [a]dd"
        # Extra command strip for 'special features' mode
        self.extraKeyCommandsString = "[z] enable/disable stream, [x] jitter on/off, [c] minor loss, [v] major  loss"

        # define views, tables headings and keys
        # view definition as follows. It pulls together the list of available tables (views of the available data), the table headings
        # and the relevant stats keys all within a single data structure. This should make adding over new views in the future straightforward
        # views =[name of view 1, [[column 1 title, column 1 key], [column 2 title, column 2 key], [column n title, column n key]],
        #           name of view n, [[column 1 title, column 1 key], [column 2 title, column 2 key], [column n title, column n key]],dataSet[]]
        # view [n][0] will be the name of the view (used to generate the navigation bar)
        # view [n][1] is a tuple containing [column title, the stats dictionary key relating to that parameter]
        # view [n][2] is a reference to the dataset for this view
        self.views = []

        if self.operationMode == 'LOOPBACK' or self.operationMode == 'TRANSMIT':
            self.views.append([Term.FG(Term.RED) + "Tx Streams",
                          [["#", 0],  # Used as an index[]
                           ["Name", 'Friendly Name'],
                           ["Src\nPort", 'Tx Source Port'],
                           ["Dest\n IP", 'Dest IP'],
                           ["Dest\nPort", 'Dest Port'],
                           ["Sync\nsrcID", 'Sync Source ID'],
                           ["Tx\nbps", 'Tx Rate'],
                           ["Size", 'Packet size'],
                           ["Bytes\n tx'd", 'Bytes transmitted'],
                           [" Time\nremain", 'Time to live']
                           ], self.availableRtpTxStreamList])

        # If actually the receiving end, use availableRtpRxStreamList[] as a source for the stream tables
        if self.operationMode == 'RECEIVE':  # or operationMode == 'LOOPBACK':
            self.streamResultsDataSet = self.availableRtpRxStreamList

        # Otherwise, assume this a tx end, and it's relying on results sent from the receiving end
        else:
            self.streamResultsDataSet = self.availableRtpTxResultsList

        self.views.append(["Summary",
                      [["#", 0],  # Used as an index
                       ["Name", "stream_friendly_name"],
                       ["Src Addr", "stream_srcAddress"],
                       # ["port", "stream_srcPort"],
                       ["bps", "packet_data_received_1S_bytes"],
                       ["Pkts\nlost", "glitch_packets_lost_total_count"],
                       [" %\nloss", "glitch_packets_lost_total_percent"],
                       ["Last\nglitch", "glitch_most_recent_timestamp"],
                       ["glitch\nperiod", "glitch_mean_time_between_glitches"],
                       ["Count", "glitch_counter_total_glitches"]
                       # ["CPU\n %","stream_processor_utilisation_percent"]
                       ], self.streamResultsDataSet])

        self.views.append(["Stream",
                      [["#", 0],  # Used as an index
                       ["Name", "stream_friendly_name"],
                       ["Sync \nSrcID", "stream_syncSource"],
                       ["Src Addr", "stream_srcAddress"],
                       ["Src\nport", "stream_srcPort"],
                       ["Dst Addr", "stream_rxAddress"],
                       ["Dst\nport", "stream_rxPort"],
                       ["  Time\nelapsed", "stream_time_elapsed_total"]
                       ], self.streamResultsDataSet])

        self.views.append(["Packet",
                      [["#", 0],  # Used as an index[]
                       ["Name", "stream_friendly_name"],
                       ["First Seen\npacket", "packet_first_packet_received_timestamp"],
                       ["Last seen\npacket", "packet_last_seen_received_timestamp"],
                       ["pack\np/s", "packet_counter_1S"],
                       ["Length\n(bytes)", "packet_payload_size_mean_1S_bytes"],
                       ["Recv\nperiod", "packet_mean_receive_period_uS"],
                       ["Bytes\nRcvd", "packet_data_received_total_bytes"],
                       ["CPU\n %", "stream_processor_utilisation_percent"]
                       # ["",""],
                       ], self.streamResultsDataSet])

        self.views.append(["Glitch",
                      [["#", 0],  # Used as an index[]
                       ["Name", "stream_friendly_name"],
                       ["Mean\nloss", "glitch_packets_lost_per_glitch_mean"],
                       ["Max\nloss", "glitch_packets_lost_per_glitch_max"],
                       ["Total\nloss", "glitch_packets_lost_total_count"],
                       ["Mean\nduration", "glitch_mean_glitch_duration"],
                       ["Max\nduration", "glitch_max_glitch_duration"],
                       ["Total\nGlitch", "glitch_counter_total_glitches"],
                       ["Ignored", "glitch_glitches_ignored_counter"],
                       ["Threshold", "glitch_Event_Trigger_Threshold_packets"]
                       ], self.streamResultsDataSet])

        self.views.append(["Historic",
                      [["#", 0],  # Used as an index[],
                       ["Name\n", "stream_friendly_name"],
                       ["24Hr\n", "historic_glitch_counter_last_24Hr"],
                       ["1Hr\n", "historic_glitch_counter_last_1Hr"],
                       ["10Min\n", "historic_glitch_counter_last_10Min"],
                       ["1Min\n", "historic_glitch_counter_last_1Min"],
                       ["10Sec\n", "historic_glitch_counter_last_10Sec"]
                       # ["", ""],
                       ], self.streamResultsDataSet])

        self.views.append(["Jitter",
                      [["#", 0],  # Used as an index[]
                       ["Name", "stream_friendly_name"],
                       ["Long term\n  mean", "jitter_long_term_uS"],
                       ["Min", "jitter_min_uS"],
                       ["Max", "jitter_max_uS"],
                       ["Range", "jitter_range_uS"],
                       ["1S \nmean", "jitter_mean_1S_uS"]
                       ], self.streamResultsDataSet])

        # views.append(["Misc",
        #               [["#", 0],  # Used as an index[]
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ],DATASET_TO_DISPLAY,ROW_SELECTOR])

        # Stores the most recent message - used to determine whether we need to redraw the message table
        self.lastMessageAdded = ""

        # Get Initial snapshot of current verbosity level
        self.intialVerbosityLevel = Message.verbosityLevel
        # Flag to turn on/off error messages (verbosity level 1)
        self.showErrorsFlag = False


        # Create/start a thread to monitor the size of the terminal window
        self.detectTerminalSizeThread = threading.Thread(target=self.__detectTerminalSizeThread, args=())
        self.detectTerminalSizeThread.daemon = False
        self.detectTerminalSizeThread.setName("__detectTerminalSizeThread")
        self.detectTerminalSizeThread.start()


        # Create/Start the display rendering thread
        self.renderDisplayThread = threading.Thread(target=self.__renderDisplayThread, args=())
        self.renderDisplayThread.daemon = False
        self.renderDisplayThread.setName("__renderDisplayThread")
        self.renderDisplayThread.start()

        # Create/Start the keyboard thread
        self.keysPressedThread = threading.Thread(target=self.__keysPressedThread, args=())
        self.keysPressedThread.daemon = False
        self.keysPressedThread.setName("__keysPressedThread")
        self.keysPressedThread.start()


        # Reset the keyPressedEvent event
        self.wakeUpUI.clear()
        # Arm the getch thread
        self.enableGetch.set()


    # A method to destroy this UI object and all associated threads
    def kill(self):
        print ("UI.kill() method called\r")
        # Signal the __keysPressedThread to end
        if self.keysPressedThread.is_alive():
            self.keysPressedThreadActive = False
            # Block until the thread ends
            print("UI.kill() Waiting for __keysPressedThread to end\r")
            self.keysPressedThread.join()
        # else:
        #     print("UI.kill() keysPressedThread.is_alive() didn't return True\r")

        if self.renderDisplayThread.is_alive():
            # End the __renderDisplayThread
            self.renderDisplayThreadActive = False
            # Block until the thread ends
            print("UI.kill() Waiting for renderDisplayThread to end\r")
            self.renderDisplayThread.join()
        if self.detectTerminalSizeThread.is_alive():
            # End the __detectTerminalSizeThread
            self.detectTerminalSizeThreadActive = False
            # Block until the thread ends
            print("UI.kill() Waiting for detectTerminalSizeThread to end\r")
            self.detectTerminalSizeThread.join()

    # This method will pause the normal screen rendering/key catching and cause a
    # 'do you want to quit? dialogue to be displayed
    # It is designed to be a blocking method. It will return True/False depending upon whether
    # the user confirms the shutdown request
    def showShutDownDialogue(self):
        # Cause the UI render thread to put up a Quit Y/N prompt
        self.displayQuitDialogueFlag = True
        # Clear the threading.Event signal for self.quitDialogueActiveFlag
        self.quitDialogueNotActiveFlag.clear()
        # Wake up the UI
        self.wakeUpUI.set()
        # Now wait for the __renderDisplayThread to signal that the prompt has been answered (blocking call)
        # by 'setting' self.quitDialogueNotActiveFlag
        self.quitDialogueNotActiveFlag.wait()
        # Return the response to the caller
        return self.quitConfirmed
        # return True



    # A cross-platform method to catch keypresses (and not echo them to the screen)
    def __getch(self):
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

    ######### Print Navigation bar (shows the available views)
    def __drawNavigationBar(self):
        navigationBar = ""  # Clear navigation bar for next time
        # Iterate over the views definition extracting the name of the view (view[0])
        # and create a printable string with colour coding
        # If the view is currently selected, black on white, otherwise black on cyan
        for view in self.views:
            if view[0] == self.views[self.selectedView][0]:
                # If this is the 'current' view, create black on white
                navigationBar += Term.BlaWh + " " + view[0] + " " + Term.WhiBlu + " "
            else:
                # Otherwise create as dimmed white on cyan
                navigationBar += Term.BlaCy + " " + view[0] + " " + Term.WhiBlu + " "
        # To avoid stale characters appearing on the second line, do a periodic clear of line 2
        Term.setBackgroundColourSingleLine(1, 2, Term.BLUE)
        # Print the rendered nav bar
        Term.printAt(navigationBar, 2, 3)

    ######### Print Navigation bar (shows the available views)
    def __drawStreamsTable(self):
        # Step 1) Establish the titles, data source and row selector (key list) for the table

        # Create a title row
        titleRow = []
        # Create a list of keys that will be accessed for this view
        keyList = []
        # Extract the column titles and stats keys for the current view
        for view in self.views:
            # Is this view the currently selected view?
            if view[0] == self.views[self.selectedView][0]:
                # view[1] represents a tuple containing a column title and a key pair
                columns = view[1]
                for column in columns:
                    titleRow.append(column[0])
                    keyList.append(column[1])

        # Create a table data list with the title row at the head
        tableData = [titleRow]

        # Step 2) Populate the remaining table rows with data
        # Calculate the maximum no. of rows that can be displayed in the stream table - determined by the terminal height
        streamTableNoOfRows = int(self.currentTermHeight / 2) - 9

        # Get a handle on the dataset to be displayed in this particular table
        # The dataset is pointed to by the 3rd element of each view array
        dataSetToDisplay = self.views[self.selectedView][2]
        streamTableDataSetLength = len(dataSetToDisplay)

        if streamTableDataSetLength == 0:
            self.selectedTableRow = 0

        # Attempt to create the table data
        if streamTableDataSetLength > 0:
            if self.selectedTableRow == 0:
                self.streamTableFirstRow = 0

            # Is the last selected row outside the range of data (this could happen if the
            # data gets modified whilst the table is not being displayed
            if self.selectedTableRow > (streamTableDataSetLength - 1):
                # If so, point the selector to the last item on the list
                self.selectedTableRow = (streamTableDataSetLength - 1)

            # Are we about to scroll off the end of the currenty displayed rows?
            if self.selectedTableRow > self.streamTableLastRow:
                # If so, increment the index of the first row
                self.streamTableFirstRow = self.selectedTableRow - streamTableNoOfRows + 1

            # Are we about to scroll off the top of the currently displayed rows?
            if self.selectedTableRow < self.streamTableFirstRow:
                # If so, decrement the index of the first row
                self.streamTableFirstRow = self.selectedTableRow

            # Calculate the last row to display based on the starting row and the height of the table
            self.streamTableLastRow = self.streamTableFirstRow + streamTableNoOfRows - 1

            # Will the last row be outside the actual range of available stream?
            if self.streamTableLastRow > (streamTableDataSetLength - 1):
                # If so, set streamTableLastRow to point to the last line of the available data array
                self.streamTableLastRow = streamTableDataSetLength - 1
                # And add appropriate padding if required
                streamTableBlankRowsToAdd = streamTableNoOfRows - (self.streamTableLastRow - self.streamTableFirstRow) - 1
            else:
                streamTableBlankRowsToAdd = 0

        else:
            # No data to display, so padding out the table instead
            streamTableBlankRowsToAdd = streamTableNoOfRows
        try:
            # Confirm that there are some available streams
            if streamTableDataSetLength > 0:
                # Iterate over a specified portion of the dataSetToDisplay[]
                for x in range(self.streamTableFirstRow, self.streamTableLastRow + 1):
                    # Isolate the stream from the dataSetToDisplay[]
                    streamData = dataSetToDisplay[x]
                    # Retrieve the stats dictionary for that key
                    streamDataStats = streamData[1].getRtpStreamStats()
                    # iterate over the keys list for each stream - this will list in a new tableData row per stream
                    tableRow = []  # Create new row to hold the data
                    ###################################### These are the lines that actually populate the table
                    for key in keyList:
                        # Check to see if the key value= 0. If it does, this is a special case, it's an index no.
                        # which is stored as the third element of a streamData tuple in the dataSetToDisplay[]
                        if key == 0:
                            # Grab the index number and assign to table cell
                            # The index stored in the array is zero indexed, but for useability, start the
                            # displayed no starting from 1
                            tableCell = str(streamData[2] + 1)

                        else:
                            # This is a normal cell with a lookup key specified in the view definition
                            try:
                                # Retrieve the data from the rtpStream object by looking up it's key
                                # Attempt to humanise the data based on object type or clues given by the key name
                                tableCell = str(self.__humanise(key, streamDataStats[key]))

                                try:
                                    # Now attempt to colour code the table based on some tests
                                    # is it a receive stream?
                                    if type(streamData[1]) == RtpReceiveStream or type(
                                            streamData[1]) == RtpStreamResults:
                                        # If so, test the stream stats
                                        if streamDataStats["packet_data_received_1S_bytes"] == 0:
                                            # If so, make the row red
                                            tableCell = Term.FG(Term.RED) + tableCell

                                        if type(streamData[1]) == RtpStreamResults:
                                            # If so, check to see that the data is fresh by looking at the
                                            # timestamp inside RtpStreamResults
                                            # If no fresh data received after 5 seconds, assume there's a problem
                                            # and colour code the stream red
                                            if (datetime.datetime.now() - streamData[1].lastUpdatedTimestamp) > \
                                                    datetime.timedelta(seconds=5):
                                                tableCell = Term.FG(Term.RED) + tableCell

                                    # is it a transmit stream?
                                    if type(streamData[1]) == RtpGenerator:
                                        if streamDataStats["Time to live"] == 0:
                                            # If tx stream has 'died', dim
                                            tableCell = Term.DIM + tableCell
                                except Exception as e:
                                    Message.addMessage(
                                        "ERR: __displayThread: (colour coding of stream tables) " + str(e) + "**")

                            except Exception as e:
                                # If the key doesn't exist within the rtpStream stats dict, copy in an error code instead
                                tableCell = "keyErr"
                                Message.addMessage("ERR: __displayThread (for key in keyList): " + str(e))

                        # Check to see if this is the currently selected stream
                        # If so, highlight the row on the table
                        if streamData[2] == self.selectedTableRow:
                            # prefix tableCell with White-on-black ASCII code
                            tableCell = Term.WhBla + str(tableCell)
                        else:
                            # Normal text: prefix tableCell with Black-on-White ASCII code
                            tableCell = Term.BlaWh + str(tableCell)
                        # Append the formatted table cell data to the tableRow list
                        tableRow.append(tableCell)
                    # Now append this complete row to the tableData list (of lists)
                    tableData.append(tableRow)
                    del tableRow
            ###################################### End of lines that actually add data
            # If the table isn't large enough yet, pad it out with blanks to the length set by streamTableNoOfRows
            if streamTableBlankRowsToAdd > 0:
                for x in range(0, streamTableBlankRowsToAdd):
                    # Create a blank list with the same no. of blanks as there are table columns
                    tableRow = [] * len(titleRow)
                    tableData.append(tableRow)

        except Exception as e:
            Message.addMessage("ERR: __displayThread. streamTable. selected row (" + str(self.selectedTableRow) + \
                               ") doesn't exist. (streamTableDataSetLength:" + str(
                streamTableDataSetLength) + "), " + str(e))

        # Step 3) Render the table
        table = SingleTable(tableData)
        # Remove all padding to save space on the screen
        table.padding_left = 0
        table.padding_right = 0
        if streamTableDataSetLength > 0:
            table.title = str(self.selectedTableRow + 1) + "/" + str(streamTableDataSetLength)
        else:
            table.title = "0/0"
        tableWidth = table.table_width
        tableRowsRendered = table.table.splitlines()
        xPos = 2
        yPos = 4
        tableHeight = len(tableRowsRendered)
        # To stop the screen getting corrupted (by tables of different widths), clear the lines behind
        # the table, just in case
        for x in range(yPos, yPos + tableHeight + 2):
            Term.setBackgroundColourSingleLine(1, x, Term.BLUE)
        Term.printTable(tableRowsRendered, xPos, yPos, tableWidth, Term.BLACK, Term.WHITE)

    ##################### Create table showing messages - only redraws if there are new messages
    def __drawMessageTable(self):
        ##################### Create table showing messages - only redraws if there are new messages
        redrawMessageTable = False
        # Message table should fill lower half of window
        yPos = int(self.currentTermHeight / 2) + 2
        # Every toolbar at the bottom of the screen will allow less room for messages
        maxNoOfMessagesThatWillFitScreen = int(self.currentTermHeight / 2) - 9

        # Get last x messages. Make a deep copy as we're going to add blankspace padding
        messages = deepcopy(Message.getMessages(maxNoOfMessagesThatWillFitScreen))
        if len(messages) > 0:
            if self.lastMessageAdded != messages[-1][1]:
                # New messages have been added, so set the redraw flag
                redrawMessageTable = True
            # Take a copy of the most recent message for next time around the loop
            lastMessageAdded = messages[-1][1]

        if redrawMessageTable or self.redrawScreen:
            redrawMessageTable = False  # Clear flag
            # Now iterate over actual messages to make sure they're not too long for display
            # If they are, truncate them. (Terminal width - 12 chars) seems to work
            # If they're too short, make them longer (to fill the space)
            maxMessageDisplayLength = self.currentTermWidth - 12
            for message in messages:
                # If message to long to fit the screen, truncate it
                if len(message[1]) > maxMessageDisplayLength:
                    message[1] = message[1][:maxMessageDisplayLength - 2]
                else:
                    # Otherwise pad the message out with spaces
                    paddingLength = (maxMessageDisplayLength - 2) - len(message[1])
                    if paddingLength > 0:
                        paddingString = " " * paddingLength
                        try:
                            message[1] += paddingString
                        except Exception as e:
                            Message.addMessage("__displayThread: Invalid message")

            if len(messages) > 0:
                width, height, tableData = Term.createTable(messages, "Messages")
                # Overwrite previous messages table
                for y in range(yPos, yPos + (maxNoOfMessagesThatWillFitScreen + 3)):
                    Term.setBackgroundColourSingleLine(1, y, Term.BLUE)
                Term.printTable(tableData, 2, yPos, width, Term.BLACK, Term.WHITE)
        del messages[:]

    def __renderTopToolbar(self):
        Term.printTitleBar("IBEOO ISP Analyser V1.3", 1, Term.BLACK, Term.WHITE)
        # Print operation mode (plus receive IP:Port if in Receive mode)
        if self.operationMode == 'TRANSMIT' or self.operationMode == 'LOOPBACK':
            Term.printAt(self.operationMode + " MODE", 1, 1, Term.BLACK, Term.WHITE)
        elif self.operationMode == 'RECEIVE':
            Term.printAt(self.operationMode + " " + str(self.UDP_RX_IP) + ":" + \
                         str(self.UDP_RX_PORT), 1, 1, Term.BLACK, Term.WHITE)

    def __updateClock(self):
        # Update clock on top RHS of screen
        Term.printRightJustified(str(datetime.datetime.now().strftime("%H:%M:%S")), 1, Term.BLACK, Term.WHITE)

    def __renderBottomToolbar(self):
        Term.setBackgroundColourSingleLine(1, (self.currentTermHeight - 1), Term.WHITE)
        # Print list of key commands
        Term.printAt(self.keyCommandsString, 1, (self.currentTermHeight - 1), Term.BLACK, Term.WHITE)
        # For tx mode, add an extra row of commands
        if self.operationMode == 'TRANSMIT' or self.operationMode == 'LOOPBACK':
            Term.setBackgroundColourSingleLine(1, (self.currentTermHeight - 2), Term.WHITE)
            Term.printAt(self.txStreamModifierCommandsString, 1, (self.currentTermHeight - 2), Term.BLACK, Term.WHITE)

            # For special features mode, add yet another row of commands
            if self.specialFeaturesModeFlag == True:
                Term.setBackgroundColourSingleLine(1, (self.currentTermHeight - 3), Term.WHITE)
                Term.printAt(self.extraKeyCommandsString, 1, (self.currentTermHeight - 3), Term.BLACK, Term.WHITE)

    # Draws a popup table list - auto sizes to fit the terminal
    def __renderPagedList(self, pageNo, title, titleRow, tableData, footerRow = None, pageNoDisplayInFooterRow = False,
                          reverseList = False, marginOffset = 0):
        # Get Terminal size so we can centre the table
        termW, termH = Term.getTerminalSize()
        # Calculate the maximum no. of lines that will fit within the table, given the terminal height
        maxLines = termH - 20

        # Calculate the no of pages required to show all the items (given the terminal size)
        noOfPages = int(math.ceil(len(tableData) / maxLines))
        # Check that we're not trying to display a non-existent page
        # if pageNo > (noOfPages - 1):
        #     pageNo = (noOfPages - 1)

        # Take the modulo of the supplied pageNo
        # This will mean that the pages loop around and around
        if noOfPages > 0: # guard against divide by zero
            pageNo = pageNo % noOfPages

        if pageNo < 0:
            pageNo =0

        # Create the table contents
        tableContents = []
        # Append the title row to the table contents
        tableContents.append(titleRow)
        tableRow = []

        if len(tableData) > 0:
            if reverseList == True:
                # Display the table in reverse order (last element of tableData first)
                # Calculate first event of list (given current page no)
                indexOfFirstItem = len(tableData) - 1 - (pageNo * maxLines)
                # Calculate last event to list (given current page no and maximum no of lines allowed in the table)
                indexOfLastItem = indexOfFirstItem - maxLines

                # Confirm that we haven't run off the end of tableContents[]
                if indexOfFirstItem >= len(tableData):
                    indexOfFirstItem = len(tableData) -1
                if indexOfFirstItem < 0:
                    indexOfFirstItem = 0
                if indexOfLastItem < 0:
                    indexOfLastItem = 0


                # The list will be created in reverse order - newest entry first
                for row in range(int(indexOfFirstItem), int(indexOfLastItem) -1, -1):
                    # Iterate over row, to extract the individual columns and create a tuple containing a row of data
                    for column in tableData[row]:
                        tableRow.append(column)
                    # Now append the complete row to tableContents[]
                    tableContents.append(tableRow)
                    # Clear the tableRow list ready for next time around the loop
                    tableRow = []

            else:
                # display the info in the original order of the supplied list
                # Calculate first item of list to be displayed (given current page no)
                indexOfFirstItem = pageNo * maxLines
                # Calculate last item of list to be displayed (given current page no)
                indexOfLastItem = indexOfFirstItem + maxLines -1
                # Confirm that we haven't run of the end of the list
                if indexOfFirstItem < 0:
                    indexOfFirstItem =0
                if indexOfFirstItem > (len(tableData) -1):
                    indexOfFirstItem = (len(tableData) -1)
                if indexOfLastItem > (len(tableData) -1):
                    indexOfLastItem = len(tableData) -1

                # Iterate over the rows of data in tableData to create the table contents
                for row in range(int(indexOfFirstItem), int(indexOfLastItem) + 1):
                    # Iterate over row, to extract the individual columns and create a tuple containing a row of data
                    for column in tableData[row]:
                        tableRow.append(column)
                    # Now append the complete row to tableContents[]
                    tableContents.append(tableRow)
                    # Clear the tableRow list ready for next time around the loop
                    tableRow = []

        # Finally, add the footer row (if supplied)
        if footerRow is not None:
            # If pageNoDisplayInFooterRow = True, overwrite the first column of the footer with a 'Page x of Y' label
            if pageNoDisplayInFooterRow is True:
                footerRow[0] = "Page " + str(pageNo + 1) + "/" + str(noOfPages)
            # Append the footer row to the table data
            tableContents.append(footerRow)
        # Create a SingleTable to tabulate the data
        pagedTable = SingleTable(tableContents)
        # Set the title
        pagedTable.title = title
        pagedTable.padding_left = 0
        pagedTable.padding_right = 0
        # If a footer row specified, add a seperator for the bottom row
        if footerRow is not None:
            pagedTable.inner_footing_row_border = True
        pagedTable.inner_column_border = False
        width = pagedTable.table_width
        height = len(tableContents) + 2

        # Centre the table vertically
        yPos = int((termH - height) / 2)

        Term.printTable(pagedTable.table.splitlines(), marginOffset, yPos, width, Term.BLACK, Term.CYAN)


    # Toggles the filtering of displayed Events on the events table created by UI.__renderEventsListTable()
    def __onfilterEventsTable(self):
        # Apply filtering to show/export only Glitch events
        if self.filterListForDisplayedEvents is None:
            self.filterListForDisplayedEvents = [Glitch]
        # Disable filtering. All events to be displayed/exported
        else:
            self.filterListForDisplayedEvents = None


    # Overlays on the screen a paged list of recent events relating to this stream
    def __renderEventsListTable(self):

        # Get Terminal size so we can centre the table
        termW, termH = Term.getTerminalSize()
        # Calculate the maximum no. of lines that will fit within the table, given the terminal height
        maxLines = termH - 20

        # Get the last n events from the list (either the rtpRxStreamsDict or rtpTxStreamResultsDict
        # depending upon whether we're in RECEIVE or TRANSMIT mode
        # The amount of events diaplayed will adjust to the terminal height
        # Get a handle on the selected RxRtpStream or TxResults
        # Note, if we are in TRANSMIT mode, the selected stream could be an RtpGenerator. This is no good,
        # hence we have to manually retrieve the appropriate stream object by using the self.selectedStreamID
        # and looking in the appropriate streams dictionary
        selectedRxOrResultsStream = None

        if self.operationMode == 'RECEIVE' or self.operationMode == 'LOOPBACK':
            try:
                selectedRxOrResultsStream = self.rtpRxStreamsDict[self.selectedStreamID]
            except:
                pass
        elif self.operationMode == 'TRANSMIT':
            try:
                selectedRxOrResultsStream = self.rtpTxStreamResultsDict[self.selectedStreamID]
            except:
                pass

        eventsList = []
        friendlyName = ""
        syncSourceID = 0
        if selectedRxOrResultsStream is not None:
            try:
                # Get eventlist of the selected Rx or TxResults stream
                eventsList = selectedRxOrResultsStream.getRTPStreamEventList(filterList = self.filterListForDisplayedEvents)
                # Get friendly name of the selected stream and strip off the trailing whitespace (if any)
                friendlyName = str(selectedRxOrResultsStream.getRtpStreamStatsByKey("stream_friendly_name")).rstrip()
                syncSourceID = str(selectedRxOrResultsStream.getRtpStreamStatsByKey("stream_syncSource"))

            except Exception as e:
                Message.addMessage("ERR. UI.__renderEventsListTable. getRTPStreamEventList()")

        # Create a list of tuples containing the timestamp and the summary
        tableContents =[]
        if len(eventsList) > 0:
            tableRow = []
            for event in eventsList:
                # Get event details (in the form of a dictionary)
                try:
                    # Retrieve each Event summary, ommiting the syncSourceID and the friendlyName (for display purposes)
                    eventDetails = event.getSummary(includeStreamSyncSourceID=False, includeFriendlyName=False)
                    # Create a complete row of the table
                    tableRow.append(str(eventDetails['timeCreated'].strftime("%d/%m %H:%M:%S")))
                    tableRow.append(" " + str(eventDetails['summary']).ljust(50))
                except Exception as e:
                    Message.addMessage("UI.__renderEventsListTable: " + str(e))
                #Append the complate table row to tableContents[]
                tableContents.append(tableRow)
                # Clear the tableRow list ready for next time around the loop
                tableRow = []
        else:
            tableContents.append(["","No events to display"])

        # # Set the title/footer for the Eventslist table
        # title = "All events for stream " + str(syncSourceID) + " (" + str(friendlyName) + ")"


        # Additional check to see if the event filtering has been enabled and modify the title/footer labels accordingly
        if self.filterListForDisplayedEvents is not None:
                title = "Glitches for stream " + str(syncSourceID) + " (" + str(friendlyName) + ")"
                footer = ["","[<][>]back/fwd, [t]exit, [r]copy to clipboard\n[y]show All events"]
        else:
            title = "All events for stream " + str(syncSourceID) + " (" + str(friendlyName) + ")"
            footer = ["", "[<][>]back/fwd, [t]exit, [r]copy to clipboard\n[y]show glitches only"]

        # Now actually display the paged table list
        self.__renderPagedList(self.tablePageNo, title, ["Timestamp".ljust(15), "Event".ljust(50)], tableContents,
                               footerRow=footer,
                               pageNoDisplayInFooterRow= True, reverseList= True, marginOffset= 7)

    # Displays a pop-up message box
    def __renderMessageBox(self, messageText, title, textColour=Term.BLACK, bgColour=Term.CYAN):
        # Create a single-celled table
        aboutDialogue = SingleTable([[messageText]])
        aboutDialogue.title = title
        width = aboutDialogue.table_width
        height = messageText.count('\n') + 2

        # Get Terminal size so we can centre the table
        termW, termH = Term.getTerminalSize()
        xPos = int((termW - width) / 2)
        yPos = int((termH - height) / 2)

        Term.printTable(aboutDialogue.table.splitlines(), xPos, yPos, width, textColour, bgColour)
        # Wait for a key press
        ch = None
        # Endless loop until either a key is pressed or the self.renderDisplayThreadActive flag is cleared
        while ch == None or self.renderDisplayThreadActive == False:
            # Blocking call to self.__getch() with timeout
            ch = self.__getch()


    # If the Event Lists Table is currently displayed, this method will copy the events to the local clipboard
    # If that is not possible (if for instance, you are connected to a remote instance of isptext via SSH)
    # it will attempt to export the data to pastebin.com (a website that allows you to share text via a webpage)
    def __onCopyEventsToClipboard(self):
        if self.displayEventsTable == True:
            selectedRxOrResultsStream = None
            # Get a handle on the selected stream
            if self.operationMode == 'RECEIVE' or self.operationMode == 'LOOPBACK':
                try:
                    selectedRxOrResultsStream = self.rtpRxStreamsDict[self.selectedStreamID]
                except:
                    pass
            elif self.operationMode == 'TRANSMIT':
                try:
                    selectedRxOrResultsStream = self.rtpTxStreamResultsDict[self.selectedStreamID]
                except:
                    pass
            streamReport = selectedRxOrResultsStream.generateReport(eventFilterList = self.filterListForDisplayedEvents)
            self.__renderMessageBox(streamReport, "Copy to Clipboard", textColour=Term.WHITE, bgColour=Term.RED)



    # Cursor right
    def __onNavigateRight(self):
        if self.displayEventsTable is False:
            # Inhibit, if Events Table is currently being displayed
            self.selectedView += 1
            # Prevent an 'out of range' view being selected
            if self.selectedView > (len(self.views) - 1):
                self.selectedView = len(self.views) - 1

        # Used to increment to the display page of the Events table
        # Note, this has to be bounds-checked in the table display code
        self.tablePageNo += 1

    # Cursor left
    def __onNavigateLeft(self):
        # Inhibit, if Events Table is currently being displayed
        if self.displayEventsTable is False:
            self.selectedView -= 1
            # Prevent an 'out of range' view being selected
            if self.selectedView < 0:
                self.selectedView = 0

        # Used to decrement to the display page of the Events table
        self.tablePageNo -= 1
        if self.tablePageNo < 0:
            self.tablePageNo = 0

    # Cursor up
    def __onNavigateUp(self):
        # Decrement the row selector associated with this view
        self.selectedTableRow -= 1
        # Bounds check
        if self.selectedTableRow < 0:
            self.selectedTableRow = 0

    # Cursor down
    def __onNavigateDown(self):
        # Increment the row selector associated with this view
        self.selectedTableRow += 1
        # Bounds check the data set associated with this view
        if self.selectedTableRow > (len(self.views[self.selectedView][2]) - 1):
            self.selectedTableRow = len(self.views[self.selectedView][2]) - 1

    # 's' pressed
    def __onEnterFriendlyName(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpGenerator or type(self.selectedStream) == RtpReceiveStream:
            styleDefinition = Style.from_dict({
                'dialog': 'bg:ansiblue',        # Screen background
                'dialog frame.label': 'bg:ansiwhite ansired ',
                'dialog.body': 'bg:ansiwhite ansiblack',
                'dialog shadow': 'bg:ansiblack'})
            text = input_dialog(
                title='Enter friendly name',
                text='Please enter friendly name for stream ' + str(self.selectedStreamID) + ':',
                style=styleDefinition).run()
            if text != '':
                self.selectedStream.setFriendlyName(text)
        else:
            Message.addMessage("Can't modify stream results. Change the name in the Transmit pane instead")

    # This method is called if a previously expired stream (that is still listed in
    # self.rtpTxStreamsDict{} is requested to be restarted
    def __recreateExpiredStream(self, RtpGeneratorToBeResurrected):
        # Attempt to get the parameters of the dead stream
        try:
            # Attempt to get the parameters of the dead stream
            stats = RtpGeneratorToBeResurrected.getRtpStreamStats()
            # Remove the expired stream from self.rtpTxStreamsDict
            Message.addMessage("UI.__recreateExpiredStream() Removing stream " + str(stats['Sync Source ID']))
            RtpGeneratorToBeResurrected.killStream()
            time.sleep(1)
            # Create new RtpStream based on the parameters of the old stream
            # Confirm that the stream has been succesfully deleted by checking whether there already exists
            # a key stats['Sync Source ID'] in self.rtpTxStreamsDict

            try:
                # If the RtpGenerator object still exists in the rtpTxStreamsDict, the killStream() must have failed
                if stats['Sync Source ID'] in self.rtpTxStreamsDict:
                    Message.addMessage("ERR: UI.__recreateExpiredStream() Expired stream" +
                                       str(stats['Sync Source ID']) + " still exists, can't replace")
                else:
                    # It has been removed, so add the new stream (a copy of the old, expired stream)
                    RtpGenerator(stats['Dest IP'], stats['Dest Port'], stats['Tx Rate'], stats['Packet size'],
                                 stats['Sync Source ID'], 3600, \
                                 self.rtpTxStreamsDict, self.rtpTxStreamsDictMutex, \
                                 self.rtpTxStreamResultsDict, self.rtpTxStreamResultsDictMutex,
                                 friendlyName=stats['Friendly Name'], UDP_SRC_PORT=stats['Tx Source Port'])
            except Exception as e:
                Message.addMessage("ERR: UI.__recreateExpiredStream() inner " + str(e))
        except Exception as e:
            Message.addMessage("ERR: UI.__recreateExpiredStream() outer " + str(e))





    # 'a' pressed (only when in Tx or Loopback mode)
    def __onAddTxStream(self):
        # Attempt to add a new tx stream (if we're in loopback or transmit mode)
        # If a tx stream already exists, the new stream will be created with an incremented
        # source UDP port and an incremented sync source id.
        # If there are no current streams, the new stream will be created with a random
        # UDP source port and a random sync source id
        if self.operationMode == 'LOOPBACK' or self.operationMode == 'TRANSMIT':

            # Grab the stats of the most recent added tx stream, and make a copy derived from it's settings
            # Check that there are actually some stream settings to copy
            if len(self.latestTxStreamStats) > 0:

                # Use stats of existing tx stream to derive setup parameters for new stream
                syncSourceID = self.latestTxStreamStats['Sync Source ID'] + 1
                sourcePort = self.latestTxStreamStats['Tx Source Port'] + 1
                destPort = self.latestTxStreamStats['Dest Port']
                destAddr = self.latestTxStreamStats['Dest IP']
                packetLength = self.latestTxStreamStats['Packet size']
                friendlyName = str(syncSourceID)

                # As a default, set time to live to be 1hr
                timeToLive = 3600
                # As a default, set tx rate to be 1 Mbps
                # txRate = 1048576
                txRate = "1M"

                # Now generate a multi_input_dialog to allow modification of defaults
                # Define the user fields and default values
                # Query RtpGenerator to find out the max length of the friendly name field
                maxFriendlyNameLength = RtpGenerator.getMaxFriendlyNameLength()
                # Dynamically create the user field text label
                friendlyNameLabelText = "Friendly name (" + str(maxFriendlyNameLength) + " chars max)"
                # 'Packet Size' minimum is dependant upon the size the isptest header (determined in RtpGenerator)
                packetSizeLabelText = "Packet size (bytes, min:" + str(RtpGenerator.getIsptestHeaderSize()) +", max:1488)"

                dialogUserFieldsList = [["Destination address", six.text_type(destAddr)],
                                        ["UDP destination port (1024-65535)", six.text_type(destPort)],
                                        ["UDP source port (1024-65535)", six.text_type(sourcePort)],
                                        ["Transmit bitrate (append K for Kbps or M for Mbps (minimum: 100k)", six.text_type(txRate)],
                                        [packetSizeLabelText, six.text_type(packetLength)],
                                        ["Sync Source identifier (1-4294967295", six.text_type(syncSourceID)],
                                        ["Time to live (seconds)", six.text_type(timeToLive)],
                                        [friendlyNameLabelText, six.text_type(friendlyName)]]

                # Define the dialogue colours
                styleDefinition = Style.from_dict({
                    'dialog': 'bg:ansiblue',  # Screen background
                    'dialog frame.label': 'bg:ansiwhite ansired ',
                    'dialog.body': 'bg:ansiwhite ansiblack',
                    'dialog shadow': 'bg:ansiblack'})

                # Create the dialogue
                # dialogUserFieldsList = [["dest addr", six.text_type(destAddr)], ["port", six.text_type(destPort)]]

                allFieldsValidatedFlag = False  # Flag to indicate that all user-entered tx stream parameters have been validated
                # Nested Exception to indicate a bad user-entered parameter
                class InvalidUserresponse(Exception):
                    pass

                # Simple fucntion to parse a number-letter suffix (k or m) and return the actuak value
                def parseSuffix(input):
                    try:
                        # Use regex to split -b argument into numerical and string parts
                        splitArg = re.split(r'(\d+)', input)
                        # Extract numerical part
                        x = int(splitArg[1])
                        # Extract string part
                        multiplier = splitArg[2]

                        if multiplier == 'k' or multiplier == 'K':
                            return x * 1024
                        elif multiplier == 'm' or multiplier == 'M':
                            return x * 1024 * 1024
                        else:
                            # Uknown suffix
                            return None
                    except:
                        return None

                # newTxStreamParametersDict = multi_input_dialog(dialogUserFieldsList, title='Enter parameters for new transmit stream', style=styleDefinition)

                # Defsult title for the user dialogue
                title = 'Enter parameters for new transmit stream'

                # Keep displaying the dialogue until either ALL the input fields have been validated OR
                # 'Cancel' was selected
                while allFieldsValidatedFlag is False:
                    try:
                        # Display the user dialogue
                        newTxStreamParametersDict = multi_input_dialog(dialogUserFieldsList,
                                                                   title=title,
                                                                   style=styleDefinition).run()
                        # Break out of endless while loop if 'Cancel' selected
                        if newTxStreamParametersDict is None:
                            break
                        # Now validate all user responses. If validation fails, an InvalidUserresponse
                        # Exception will be raised and the loop will re-run causing the
                        # dialogue to be redisplayed (until either all values are validated, or 'Cancel'
                        # selected

                        # Capture the (new) friendly name and truncate if necessary
                        friendlyName = str(newTxStreamParametersDict[friendlyNameLabelText])
                        if len(friendlyName) > maxFriendlyNameLength:
                            friendlyName = friendlyName[:maxFriendlyNameLength] # Slice the bottom n chars

                        # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                        dialogUserFieldsList[7][1] = six.text_type(friendlyName)

                        try:
                            # Validate dest address
                            destAddr = validators.ip_address(newTxStreamParametersDict["Destination address"])
                            # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                            dialogUserFieldsList[0][1] = six.text_type(destAddr)
                        except (errors.EmptyValueError, errors.InvalidIPAddressError):
                            title = 'ERROR: INVALID DESTINATION ADDRESS'
                            raise InvalidUserresponse


                        # Validate destination port
                        try:
                            destPort = validators.integer(int(newTxStreamParametersDict["UDP destination port (1024-65535)"]),
                                                          minimum=1024, maximum=65535)
                            # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                            dialogUserFieldsList[1][1] = six.text_type(destPort)
                        except Exception as e:
                            title = 'ERROR: INVALID DESTINATION PORT'
                            raise InvalidUserresponse

                        # Validate UDP source port
                        try:
                            sourcePort = validators.integer(int(newTxStreamParametersDict["UDP source port (1024-65535)"]),
                                                          minimum=1024, maximum=65535)
                            # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                            dialogUserFieldsList[2][1] = six.text_type(sourcePort)
                        except:
                            title = 'ERROR: INVALID SOURCE PORT'
                            raise InvalidUserresponse

                        # Validate transmit bitrate
                        try:
                            # Specify 100kbps as the minimum
                            txRate_bps = validators.integer(parseSuffix(
                                newTxStreamParametersDict["Transmit bitrate (append K for Kbps or M for Mbps (minimum: 100k)"]),
                            minimum=parseSuffix("100k"))

                        except:
                            title = 'ERROR: TRANSMIT BITRATE SPECIFIER - Use "m" for mbps or "k" for kbps'
                            raise InvalidUserresponse

                        # Validate packet size
                        try:
                            packetLength = validators.integer(int(newTxStreamParametersDict[packetSizeLabelText]),
                                                          minimum=RtpGenerator.getIsptestHeaderSize(), maximum=1488)
                            # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                            dialogUserFieldsList[4][1] = six.text_type(packetLength)
                        except:
                            # Redisplay the dialogue indicating the error
                            title = 'ERROR: INVALID PACKET LENGTH'
                            raise InvalidUserresponse

                        # Validate the Sync Source ID
                        try:
                            syncSourceID = validators.integer(int(newTxStreamParametersDict["Sync Source identifier (1-4294967295"]),
                                                          minimum=1, maximum=4294967295)
                            # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                            dialogUserFieldsList[5][1] = six.text_type(syncSourceID)
                        except:
                            # Redisplay the dialogue indicating the error
                            title = 'ERROR: INVALID SYNC SOURCE IDENTIFIER'
                            raise InvalidUserresponse

                        # Validate the time to live
                        try:
                            timeToLive = validators.integer(int(newTxStreamParametersDict["Time to live (seconds)"]),
                                                          minimum=1, maximum=4294967295)
                            # Update dialogUserFieldsList with validated value (so this (new?) value is not lost
                            dialogUserFieldsList[6][1] = six.text_type(timeToLive)

                            # If execution gets this far, all parameters must have been validated
                            # Last field validated so we can set clear the flag
                            allFieldsValidatedFlag = True
                        except:
                            # Redisplay the dialogue indicating the error
                            title = 'ERROR: INVALID TIME TO LIVE'
                            raise InvalidUserresponse

                    # Catch any invalid user responses
                    except InvalidUserresponse:
                        pass


                if allFieldsValidatedFlag:

                    # All tx stream parameters validated so create the new RtpGenerator object
                    rtpGenerator = RtpGenerator(destAddr, destPort, txRate_bps, packetLength, syncSourceID, timeToLive, \
                                                self.rtpTxStreamsDict, self.rtpTxStreamsDictMutex, \
                                                self.rtpTxStreamResultsDict, self.rtpTxStreamResultsDictMutex,
                                                friendlyName=friendlyName, UDP_SRC_PORT=sourcePort)

                    Message.addMessage("[a] Added new " + str(bToMb(txRate_bps)) + "bps stream with id " + str(syncSourceID))
                # Force redraw
                redrawScreen = True
            else:
                # Note. This code should never be reachable because it shouldn't be possible to start in TRANSMIT mode
                # without ever having specified an initial stream
                Message.addMessage("ERR: No previous Tx stream stats to copy from. New stream not added")

    # 'd' -  Delete selected stream
    def __onDeleteStream(self):
        # Delete selected stream (selected table row)

        # Confirm that the dataset associated with this view actually has some data in it
        if self.selectedStream != None:
            try:

                Message.addMessage(
                    "INFO: streamToDelete: " + str(self.selectedStreamID) + " of type " + str(type(self.selectedStream)))

                # Now determine the type of stream (RtpGenerator (tx) or RtpStream (rx) )
                if type(self.selectedStream) == RtpGenerator:
                    # It is a generator object
                    Message.addMessage("[d] Deleting Tx Stream: " + str(self.selectedStreamID))
                    # Instruct the RtpGenerator object to die (and it's associated corrseponding RtpStreamResults, if it exists)
                    self.selectedStream.killStream()
                    # Additionally, remove the corrseponding RtpStreamResults object for this stream


                elif type(self.selectedStream) == RtpReceiveStream:
                    # It is an RtpReceiveStream (receiver) object
                    Message.addMessage("[d] Deleting Rx Stream: " + str(self.selectedStreamID))
                    # Safely shutdown the RtpStream object itself
                    self.selectedStream.killStream()

                elif type(self.selectedStream) == RtpStreamResults:
                    Message.addMessage("Can't delete Results line for stream. " + str(self.selectedStreamID) + \
                                       " Did you mean to delete the transmit stream instead?")

            except Exception as e:
                Message.addMessage(
                    "ERR: __displayThread. [d] Delete Stream request failed: " + str(self.selectedStreamID) +
                    ", " + str(e))


    # 'm' pressed
    def __onIncreaseTxRate(self):
        self.__modifyTxRate(1)

    # 'n' pressed
    def __onDecreaseTxRate(self):
        self.__modifyTxRate(-1)

    # This is called by __onIncreaseTxRate() and  __onDecreaseTxRate() and is the method that actually does the work
    def __modifyTxRate(self, direction):
        # If called with a +ve value it will increase the tx rate, if called with a -1 it will reduce the tx rate

        # bounds limit the input
        if direction < 0:
            # For all negative values, set direction to -1
            direction = -1
        else:
            # For all other values, set direction to '1'
            direction = 1
        # Confirm that the selected stream is a generator object
        if type(self.selectedStream) == RtpGenerator:
            # Get tx rate from currently selected stream
            currentTxRate = int(self.selectedStream.getRtpStreamStatsByKey('Tx Rate'))
            # If less than 1Mbps increment/decrement by 256kbps
            if currentTxRate < 1048576:
                newTxRate = currentTxRate + (262144 * direction)
                self.selectedStream.setTxRate(newTxRate)
            # Otherwise increment/decrement by 500kbps
            else:
                newTxRate = currentTxRate + (524288 * direction)
                self.selectedStream.setTxRate(newTxRate)

    # 'j'
    def __onIncreaseTimeToLive(self):
        self.__modifyTimeToLive(1)

    # 'h'
    def __onDecreaseTimeToLive(self):
        self.__modifyTimeToLive(-1)

    # This is called by __onIncreaseTimeToLive() and __onDecreaseTimeToLive() and is the actual worker method
    def __modifyTimeToLive(self, direction):

        # If called with a +ve value it will increase the TTL, if called with a -1 it will reduce the TTL
        # bounds limit the input
        if direction < 0:
            # For all negative values, set direction to -1
            direction = -1
        else:
            # For all other values, set direction to '1'
            direction = 1
        # Confirm that the selected stream is a generator object
        if type(self.selectedStream) == RtpGenerator:
            # Get TTL of currently selected stream
            currentTTL = int(self.selectedStream.getRtpStreamStatsByKey('Time to live'))
            # Has the selected stream TTL already expired?
            if currentTTL == 0:
                # If so, recreate the stream with identical parameters
                self.__recreateExpiredStream(self.selectedStream)
            else:
                # Calculate new TTL (either adding/removing time, or setting 'forever')
                # Add/subtract 1hr (3600 secs)
                newTTL = currentTTL + (3600 * direction)
                # If the new calculated value is -ve, interpret as 'forever'
                if newTTL < 0:
                    # Set stream TTL to 'forever'
                    self.selectedStream.setTimeToLive(-1)
                    Message.addMessage("Setting stream " + str(self.selectedStreamID) + " time to live to 'forever'")
                else:
                    # Otherwise update the stream with the new calculated TTL
                    self.selectedStream.setTimeToLive(newTTL)
                    Message.addMessage("Setting stream " + str(self.selectedStreamID) + " time to live to dur " + dtstrft(
                        datetime.timedelta(seconds=newTTL)))


    # 'l'
    def __onIncreasePayloadSize(self):
        self.__modifyPayloadSize(1)

    # 'k'
    def __onDecreasePayloadSize(self):
        self.__modifyPayloadSize(-1)

    # Called from __onIncreasePayloadSize() and __onDecreasePayloadSize(). Direction flag determines increment/decrement
    def __modifyPayloadSize(self, direction):
        # bounds limit the input
        if direction < 0:
            # For all negative values, set direction to -1
            direction = -1
        else:
            # For all other values, set direction to '1'
            direction = 1
        # Confirm that the selected stream is a generator object
        if type(self.selectedStream) == RtpGenerator:
            # Get current payload size
            currentTxPayloadSize = int(self.selectedStream.getRtpStreamStatsByKey('Packet size'))
            # Increment/decrement current size by 10 bytes
            self.selectedStream.setPayloadLength(currentTxPayloadSize + (10 * direction))
            # Verify new payload size
            currentTxPayloadSize = int(self.selectedStream.getRtpStreamStatsByKey('Packet size'))
            Message.addMessage(
                " Stream " + str(self.selectedStreamID) + " packet size changed to " + str(currentTxPayloadSize) + " bytes")

    # 'p'
    def __onIncrementSyncSourceID(self):
        self.__modifySyncSourceID(1)

    # 'o'
    def __onDecrementSyncSourceID(self):
        self.__modifySyncSourceID(-1)

    # Called from __onIncrementSyncSourceID() and __onDecrementSyncSourceID(). Increments/decrements according to dir flag
    def __modifySyncSourceID(self, direction):
        # bounds limit the input
        if direction < 0:
            # For all negative values, set direction to -1
            direction = -1
        else:
            # For all other values, set direction to '1'
            direction = 1
        # Confirm that the selected stream is a generator object
        if type(self.selectedStream) == RtpGenerator:
            # Get current Sync source ID
            currentSyncSourceID = int(self.selectedStream.getRtpStreamStatsByKey('Sync Source ID'))
            # Increment/decrement  sync source by 1
            self.selectedStream.setSyncSourceIdentifier(currentSyncSourceID + (1 * direction))
            # Verify new sync source id
            currentSyncSourceID = int(self.selectedStream.getRtpStreamStatsByKey('Sync Source ID'))
            Message.addMessage(
                " Stream " + str(self.selectedStreamID) + " sync source id changed to " + str(currentSyncSourceID))



    # 'e'
    def __onToggleErrorMessages(self):
        if self.showErrorsFlag == False:
            # Set flag to true
            self.showErrorsFlag = True
            # Force a change of Message verbosity level to show errors
            Message.setVerbosity(1)
            Message.addMessage("[e] Error messages on")
        else:
            # Set flag to false
            self.showErrorsFlag = False
            # Force a change of Message verbosity back to intial setting
            Message.setVerbosity(self.intialVerbosityLevel)
            Message.addMessage("[e] Reverting to initial verbosity level")

    # 'z'
    def __onTogglePacketGenerationOnOff(self):
        # Confirm special features enabled and selected stream is an RtpGenerator
        if self.specialFeaturesModeFlag == True and type(self.selectedStream) == RtpGenerator:
            # Get current transit status and toggle accordingly
            if self.selectedStream.getEnableStreamStatus():
                # If currently enabled, disable it
                self.selectedStream.disableStream()
                Message.addMessage("[z] Stream " + str(self.selectedStreamID) + " packet generation disabled")
            else:
                # otherwise, enable it
                self.selectedStream.enableStream()
                Message.addMessage("[z] Stream " + str(self.selectedStreamID) + " packet generation enabled")


    # 'x'
    def __onToggleJitterSimulationOnOff(self):
        if self.specialFeaturesModeFlag == True and type(self.selectedStream) == RtpGenerator:
            if self.selectedStream.getJitterStatus():
                # if jitter simulation currently enabled, disable it
                self.selectedStream.disableJitter()
                Message.addMessage("[x] Stream " + str(self.selectedStreamID) + " jitter simulation disabled")
            else:
                self.selectedStream.enableJitter()
                Message.addMessage("[x] Stream " + str(self.selectedStreamID) + " jitter simulation enabled")

    # 'c'
    def __onInsertMinorPacketLoss(self):
        # Insert minor packet loss for the selected stream (< glitch threshold)
        if self.specialFeaturesModeFlag == True and type(self.selectedStream) == RtpGenerator:
            # As a default, set an arbitrarily low no of packets to lose
            packetsToLose = 1
            # Otherwise, get current glitch threshold from first available Stream Results objects (if available)
            if (len(self.availableRtpTxResultsList) > 0):
                receiverGlitchThreshold = \
                    int(self.availableRtpTxResultsList[0][1].getRtpStreamStatsByKey(
                        "glitch_Event_Trigger_Threshold_packets"))
                packetsToLose = receiverGlitchThreshold - 1

            # Simulate packet loss
            self.selectedStream.simulatePacketLoss(packetsToLose)
            Message.addMessage(
                "[c] Stream " + str(self.selectedStreamID) + " simulate minor packet loss (" + str(packetsToLose) + \
                " packets)")

    # 'v'
    def __onInsertMajorPacketloss(self):
        if self.specialFeaturesModeFlag == True and type(self.selectedStream) == RtpGenerator:
            # As a default, set an arbitrarily high no of packets to lose
            packetsToLose =20
            # Otherwise, get current glitch threshold from first available Stream Results objects (if available)
            if (len(self.availableRtpTxResultsList) > 0):
                receiverGlitchThreshold = \
                    int(self.availableRtpTxResultsList[0][1].getRtpStreamStatsByKey("glitch_Event_Trigger_Threshold_packets"))
                packetsToLose = receiverGlitchThreshold + 1

            # Simulate packet loss
            self.selectedStream.simulatePacketLoss(packetsToLose)
            Message.addMessage("[v] Stream " + str(self.selectedStreamID) + " simulate major packet loss (" + str(packetsToLose) +\
                               " packets)")


    # 't' - display the About dialogue
    def __onAboutDialogue(self):
        # Create a dialogue box (using a table with a single cell and no headings)
        # NOTE: This is a blocking method

        maxWidth = 55
        tableContents = "BBC IBEOO Team ISP Analyser V1.2 (beta)".center(maxWidth, " ") + \
                        "\n\n" + "(c) James Turner 2020".center(maxWidth, " ") + \
                        "\n\n" + "<tl;dr> A UDP based packet loss and jitter".center(maxWidth, " ") + \
                        "\n" + " measurement tool supporting multiple tx/rx streams".center(maxWidth, " ") + \
                        "\n" + "  and event logging".center(maxWidth, " ") + \
                        "\n\n\n" + "Comments/feedback to: james.c.turner@bbc.co.uk".center(maxWidth, " ") + \
                        "\n See https://confluence.dev.bbc.co.uk/x/ioKKD for support" + \
                        "\n\n\n\n" + \
                        "Press the [any] key to continue".center(maxWidth, " ")

        # Render the message in a pop-up box
        self.__renderMessageBox(tableContents, "About")

    def __onDisplayEvents(self):
        # Toggle display of Events list dialogue
        if self.displayEventsTable == False:
            self.displayEventsTable = True
            # Reset display page to 0 when initially displaying the table
            self.tablePageNo = 0
            # Turn off filtering of displayed events when initially displaying the table
            self.filterListForDisplayedEvents = None
        else:
            self.displayEventsTable = False

    # Tests the key pressed, and calls the appropriate method
    def __parseKeyPressed(self):
        # Parse keyboard commands
        # print ("__renderDisplayThread() " + str(self.keyPressed)+"\r")
        if self.keyPressed == None:
            pass
        else:
            # 'Ctrl-C' - request shutdown
            if self.keyPressed == 3:
                Message.addMessage("DBUG: Ctrl-C Pressed")

                # For Linux/OSX - Kill self (Windows will detect the SIGTERM in the signalHandler itself
                os.kill(os.getpid(), signal.SIGINT)
                self.wakeUpUI.set()
            # Cursor Right
            elif self.keyPressed == 67 or self.keyPressed == 77:
                self.__onNavigateRight()
            # Cursor left
            elif self.keyPressed == 68 or self.keyPressed == 75:
                self.__onNavigateLeft()
            # Cursor up
            elif self.keyPressed == 65 or self.keyPressed == 72:
                self.__onNavigateUp()
            # Cursor down
            elif self.keyPressed == 66 or self.keyPressed == 80:
                self.__onNavigateDown()
            # 's' Set friendly name
            elif self.keyPressed == ord('s'):
                self.__onEnterFriendlyName()
            # 'a' Add TX stream
            elif self.keyPressed == ord('a'):
                self.__onAddTxStream()
            # 'd' Delete stream
            elif self.keyPressed == ord('d'):
                self.__onDeleteStream()
            # 'u' About dialogue
            elif self.keyPressed == ord('u'):
                self.__onAboutDialogue()
            # 'm' Increase tx rate of selected stream
            elif self.keyPressed == ord('m'):
                self.__onIncreaseTxRate()
            # 'n' Decrease tx rate of selected stream
            elif self.keyPressed == ord('n'):
                self.__onDecreaseTxRate()
            # 'j' Increase Tx Stream Time to Live
            elif self.keyPressed == ord('j'):
                self.__onIncreaseTimeToLive()
            # 'h' Decrease Tx Stream Time to Live
            elif self.keyPressed == ord('h'):
                self.__onDecreaseTimeToLive()
            # 'l' Increase payload size
            elif self.keyPressed == ord('l'):
                self.__onIncreasePayloadSize()
            # 'k' Decrease payload size
            elif self.keyPressed == ord('k'):
                self.__onDecreasePayloadSize()
            # 'p' Increment sync source ID of stream
            elif self.keyPressed == ord('p'):
                self.__onIncrementSyncSourceID()
            # 'o' Decrement sync source ID of stream
            elif self.keyPressed == ord('o'):
                self.__onDecrementSyncSourceID()
            # 'e' Toggle error messages on/off
            elif self.keyPressed == ord('e'):
                self.__onToggleErrorMessages()
            # 't' Display events list for selected stream
            elif self.keyPressed == ord('t'):
                self.__onDisplayEvents()
            # 'y' Show only glitches on events list table
            elif self.keyPressed == ord('y'):
                self.__onfilterEventsTable()
            # 'r' Copy events to clipboard
            elif self.keyPressed == ord('r'):
                self.__onCopyEventsToClipboard()

            # Special features
            # 'z' Toggle packet generation on/off for selected stream
            elif self.keyPressed == ord('z'):
                self.__onTogglePacketGenerationOnOff()
            # 'x' Toggle jitter simulation for selected stream
            elif self.keyPressed == ord('x'):
                self.__onToggleJitterSimulationOnOff()
            # 'c' Insert minor packet loss for selected stream
            elif self.keyPressed == ord('c'):
                self.__onInsertMinorPacketLoss()
            # 'v' Insert major packet loss for selected stream
            elif self.keyPressed == ord('v'):
                self.__onInsertMajorPacketloss()
            else:
                # print ("UI: key pressed not known: " + str(self.keyPressed))
                pass
            # # Clear key buffer
            self.keyPressed = None
            # Trigger a screen redraw
            self.redrawScreen = True

    # Utility method to create create an up to date list, from a dictionary (taking additions and deletions into account)
    def __updateAvailableStreamsList(self, rtpStreamList, rtpStreamDict, rtpStreamDictMutex):
        # This is a utility function for UI.__renderDisplayThread
        # It's job is to compare the current working list inn use by __displayThread (currentStreamList[])
        # with the rtpStreamDict{} dictionary of active rtpRxStreams or rtpTxStreams (maintained by main())
        # If will replicate any additions/deletions to objects in rtpStreamDict{} to currentStreamList[]
        # Crucially, the order of currentStreamList[] will be maintained so that it will represent a
        # chronological record of the order in which streams were added. This is very useful for display purposes
        # because __displayThread relies upon the index no of the entries in currentStreamList[]

        # It's a bit like a C function in that it doesn't return anything. Instead, the arguments supplied
        # (a list and a dictionary) are mutable, and therefore act like pointers. Therefore this function
        # can manipulate them directly.

        # 1) Iterate over keys of rtpStreamDict{} to get latest list of streams
        rtpStreamDictMutex.acquire()
        newStreamsList = []
        for k, v in rtpStreamDict.items():
            newStreamsList.append(k)
        rtpStreamDictMutex.release()

        # 2) Create sublist of current known rtpStreamList
        currentStreamsList = []
        for k in rtpStreamList:
            currentStreamsList.append(k[0])

        # 3) Do set(new)^set(current) to get difference between the two lists (as another list)
        diff = set(currentStreamsList) ^ set(newStreamsList)
        # 4) do set(new)&set(diff) to get add list
        addList = set(newStreamsList) & set(diff)
        # 5) do set (current)&set(diff) to get del list
        deleteList = set(currentStreamsList) & set(diff)

        # 6) Add new streams to rtpStreamList
        for streamID in addList:
            # Create tuple containing the stream id, the stream object itself and an index
            x = [streamID, rtpStreamDict[streamID], 0]
            # Append the new tuple to rtpStreamList[]
            rtpStreamList.append(x)
            Message.addMessage(
                "INFO: __updateAvailableStreamsList() Added stream: " + str(x[0]) + ", " + str(type(x[1])))
        for streamID in deleteList:
            # Iterate over tuples in rtpStreamList[] searching for a match
            for index, stream in enumerate(rtpStreamList):
                if stream[0] == streamID:
                    # If stream found, delete that tuple from the list
                    Message.addMessage(
                        "INFO: __updateAvailableStreamsList() Removing stream " + str(stream[0]) + ", " + str(
                            type(stream[1])))
                    try:
                        rtpStreamList.pop(index)
                    except Exception as e:
                        Message.addMessage("ERR: __updateAvailableStreamsList: " + str(e))
                    break

        # 8) Check that rtpStreamList and rtpStreamDict are actually looking at the same objects in memory
        # It's possible that duplicate streams with the same stream ID can lead to orphan streams remaining
        # in rtpStreamList.
        # To check, we actually need to compare the objects in both lists of objects. Using the 'is' keyword
        # confirms that they are the same object (as opposed to the same type of object)
        rtpStreamDictMutex.acquire()
        for stream in rtpStreamList:
            try:
                if stream[1] is not rtpStreamDict[stream[0]]:
                    Message.addMessage("ERR:__updateAvailableStreamsList() Object mismatch for streamID " + str(
                        stream[0]) + ". Repointing to correct object")
                    # Now re-point rtpStreamList to the correct version of that object
                    # by assigning the correct object to the entry in rtpStreamList[]
                    stream[1] = rtpStreamDict[stream[0]]
            except Exception as e:
                Message.addMessage("ERR:__updateAvailableStreamsList(), rtpStreamDictkey error for stream " + str(
                    stream[0]) + ", " + str(e))
        rtpStreamDictMutex.release()
        # 9) delete newStreamsList, currentStreamsList, diff, addList and deleteList
        del newStreamsList
        del currentStreamsList
        del diff
        del addList
        del deleteList

        # 10) Optionally recalculate rtpStreamList indices - Note these shouldn't change unless a stream has been deleted
        for index, stream in enumerate(rtpStreamList):
            # Write the list index value to the third element of the stream tuple
            stream[2] = index

    # This function tests the supplied key against some specified key values, and formats the corresponding value
    # to make it more readable
    def __humanise(self, key, value):
        # This function tests the supplied key against some specified key values, and formats the corresponding value
        # to make it more readable
        if key == "packet_data_received_1S_bytes":
            # We want this value in bps
            # Convert bytes to bits
            value *= 8
            value = bToMb(value)
            return value

        if key == "stream_syncSource" or key == 'Sync Source ID':
            value = str(value).rjust(10)

        # Render dates concisely
        if type(value) == datetime.datetime:
            value = value.strftime("%d/%m %H:%M:%S")
            return value

        if type(value) == datetime.timedelta:
            # Pass to (my) dtstrft() function to create a much shorter string
            return dtstrft(value)

        if key == "packet_data_received_total_bytes" or key == "Bytes transmitted":
            value = bToMb(value) + "B"
            return value

        if key == key == 'Tx Rate':
            value = bToMb(value)
            return value

        if key.find('percent') > 0:
            # Convert % value to an integer
            value = int(value)
            return value

        if key.find('_uS') > 0:
            # If > 1000uS, express as a mS
            if int(value) > 1000 or int(value) < -1000:
                value = str(int(value / 1000)) + "mS"
            else:
                # Append _uS to the value
                value = str(int(value)) + "uS"
            return value

        if key == 'Time to live':
            # If this is am endless stream (created with a negative time to live)
            if value < 0:
                value = "forever"
            elif value == 0:
                value = "Expired"
            else:
                value = datetime.timedelta(seconds=value)
            return value

        if key == "stream_srcAddress" or key == "stream_rxAddress" or key == 'Dest IP':
            # Should pad ip addresses to the max no of characters aaa.bbb.ccc.ddd
            value = value.ljust(15)
            return value

        else:
            return value

    # Autonomous thread to render the screen and parse keyboard presses
    def __renderDisplayThread(self):
        # Set up display window
        # Initialise Colorama module (which transcodes ascii escape sequences for Windows)
        init(autoreset=True)
        Term.enterAlternateScreen()
        Term.clearTerminalScrollbackBuffer()

        if self.operationMode == 'RECEIVE':
            Message.addMessage("Waiting for incoming RTP streams on " + str(self.UDP_RX_IP) + ":" + str(self.UDP_RX_PORT))
        elif self.operationMode == 'TRANSMIT':
            Message.addMessage("Waiting for receiving end to make contact..... ")

        # Endless 'state-driven' loop to render the screen
        while self.renderDisplayThreadActive == True:
            # Blocking Wait for the wakeUpUi Event (or a 1 sec timeout, whichever first)
            self.wakeUpUI.wait(timeout=1)
            # Now clear the 'wakeupUI event' flag (because we've processed this key press)
            self.wakeUpUI.clear()

            # Check status of self.displayQuitDialogueFlag. If so, display the Quit Y/N prompt
            if self.displayQuitDialogueFlag:
                # Clear the flag
                self.displayQuitDialogueFlag = False
                # disable _getch() key capture (it will interfere with the Prompt_Toolkit code
                self.enableGetch.clear()
                time.sleep(0.2) # for safety, wait for timeout period of getch (to make sure it's disabled)
                # Put up the user prompt (blocking call)
                styleDefinition = Style.from_dict({
                    'dialog': 'bg:ansiblue',  # Screen background
                    'dialog frame.label': 'bg:ansiwhite ansired ',
                    'dialog.body': 'bg:ansiwhite ansiblack',
                    'dialog shadow': 'bg:ansiblack'})
                Term.clearScreen()
                self.quitConfirmed = yes_no_dialog(title='Quit Isptest', text='Do you want to quit?',
                                                   style=styleDefinition).run()
                # Re-enter alternate screen buffer
                Term.enterAlternateScreen()
                Term.clearTerminalScrollbackBuffer()
                self.redrawScreen = True

                # Now we have a response, update the Threading.Event flag (to unblock UI.showShutDownDialogue())
                self.quitDialogueNotActiveFlag.set()


            # Update available streams lists
            if self.operationMode == 'TRANSMIT' or self.operationMode == 'LOOPBACK':
                self.__updateAvailableStreamsList(self.availableRtpTxStreamList, self.rtpTxStreamsDict, self.rtpTxStreamsDictMutex)
                self.__updateAvailableStreamsList(self.availableRtpTxResultsList, self.rtpTxStreamResultsDict, self.rtpTxStreamResultsDictMutex)
            elif self.operationMode == 'RECEIVE':
                self.__updateAvailableStreamsList(self.availableRtpRxStreamList, self.rtpRxStreamsDict, self.rtpRxStreamsDictMutex)


            # Grab the stats of the latest added tx stream - this info is used for the 'add stream with defaults' option
            if len(self.availableRtpTxStreamList) > 0:
                latestTxStream = self.availableRtpTxStreamList[-1][1]
                # Take a deep copy so that we're not dependent upon this stream existing
                self.latestTxStreamStats = deepcopy(latestTxStream.getRtpStreamStats())

            # Get a handle on the currently highlighted stream and corresponding sync source ID
            # Confirm that the streamList associated with this view actual has data in it
            lengthOfDataSetToDisplay = len(self.views[self.selectedView][2])
            # Local function to confirm that the 'selected stream' pointed to by the streams table actually exists
            # (it might not still, if the user deleted the stream via the UI
            # If the stream has been deleted, the selction moves to the last stream added, or None
            # if there are no streams at all
            # This will make sure that self.self.selectedStream and self.selectedStreamID are up to date
            def validateSelectedStream():
                if lengthOfDataSetToDisplay > 0:
                    # Now confirm that we're not off the end of the list of streams (possible if the last stream
                    # in the list was deleted)
                    if self.selectedTableRow > (lengthOfDataSetToDisplay - 1):
                        # If so, point the selector to the last item on the list
                        self.selectedTableRow = (lengthOfDataSetToDisplay - 1)

                    self.selectedStream = self.views[self.selectedView][2][self.selectedTableRow][1]
                    self.selectedStreamID = self.views[self.selectedView][2][self.selectedTableRow][0]
                else:
                # Otherwise, if there are no streams available, set the instance variables accordingly
                    self.selectedStream = None
                    self.selectedStreamID = 0
            validateSelectedStream()

            # Determine which key pressed, and call the appropriate method
            self.__parseKeyPressed()

            ########## Start rendering the screen
            if self.redrawScreen:
                Term.setBackgroundColour(Term.BLUE)
                self.__renderTopToolbar()
                self.__renderBottomToolbar()
                self.__drawNavigationBar()
            # Term.printAt(str(datetime.datetime.now()) + ", " + str(self.selectedView), 1, 10, Fore.BLACK)

            # Update the clock on the top toolbar
            self.__updateClock()
            # draw the stream table
            self.__drawStreamsTable()

            # Message.addMessage(str(listCurrentThreads()))
            # draw the messages table
            self.__drawMessageTable() # Should only take effect if there are any new messages/or self.redrawScreen is True

            # Check to see if Events List is to be overlaid?
            if self.displayEventsTable:
                # Confirm that self.selectedStream and self.selectedStreamID are up to date, before drawing the table
                # Without this update, the Events Table update lags behind the selected stream
                validateSelectedStream()
                self.__renderEventsListTable()

            # Clear flag
            self.redrawScreen = False

            # Now re-arm the getch thread
            self.enableGetch.set()

        # Exit alternate screen
        Term.exitAlternateScreen()
        Term.clearScreen()
        print ("UI.__renderDisplayThread ended")

    # Autonomous thread to monitor the size of the terminal window
    def __detectTerminalSizeThread(self):
        while self.detectTerminalSizeThreadActive == True:
            # Check to see if terminal has been resized
            # NOTE: Safe max print area height seems to be currentTermHeight -1
            w, h = Term.getTerminalSize()
            if (w != self.currentTermWidth) or (h != self.currentTermHeight):
                # If it has, set a flag
                self.redrawScreen = True
                # And store the new values
                self.currentTermWidth = w
                self.currentTermHeight = h
                Message.addMessage(
                    "INFO: Terminal size has changed to " + str(self.currentTermWidth) + "," + str(self.currentTermHeight))
            time.sleep(0.2)
        print ("UI.__detectTerminalSizeThread ended\r")


    # Autonomous thread to monitor key presses
    def __keysPressedThread(self):
        while self.keysPressedThreadActive == True:
            # Wait for getch to be enabled (with a timeout)
            self.enableGetch.wait(timeout = 0.2)
            # Confirm that enableGetch was actually set (or was it just a timeout)
            if self.enableGetch.is_set():
                # Capture keyboard presses via the getch method (with a 1 second timeout)
                self.keyPressed = None  #clear the keyboard buffer
                ch = self.__getch()
                # Term.printAt("getch() : " + str(ch), 1, 7)
                # Check to see if a genuine key has been pressed

                if ch != None:
                    # If a key has been pressed, store it
                    self.keyPressed = ch
                    # Signal that a key has been pressed
                    self.wakeUpUI.set()
                    # Now disarm key checking (until it is re-enabled elsewhere)
                    self.enableGetch.clear()
        print("UI.__keysPressedThread ended\r")

def __diskLoggerThread(operationMode, rtpStreamsDict, rtpStreamsDictMutex, shutdownFlag):
    # Autonomous thread to iterate over rtpStreamsDict and poll RtpStream eventLists for new events
    # and write them  to disk
    Message.addMessage("INFO: diskLoggerThread starting")
    # Prefix the filenames created when in RECEIVE mode
    if operationMode == 'RECEIVE':
        prefix = "receiver_report_"
    else:
        prefix = ""

    filename_csv = prefix + "eventLog_" + datetime.datetime.now().strftime("%H-%M-%S") + ".csv"
    filename_json = prefix + "eventLog_" + datetime.datetime.now().strftime("%H-%M-%S") + ".json"
    lastWrittenEventNoDict = {} # Dictionary to hold the last written event no for each stream
    latestEvents = []

    file_json = None # File handle
    file_csv = None # File handle

    # Create a file and write a header
    try:
        # Write summary file
        file_csv = open(filename_csv, "w+")
        file_csv.write("Event Log summary created by isptest. Created at: " + str(datetime.datetime.now()) +
                       "\r\n-------------------------------------------------------------------------\n")
        file_csv.close()

        # Write detailed json file
        file_json = open(filename_json, "w+")
        file_json.write("Event Log json created by isptest. Created at: " + str(datetime.datetime.now()) +
                        "\r\n-------------------------------------------------------------------------\n")
        file_json.close()
    except Exception as e:
        Message.addMessage("DBUG:__diskLoggerThread " + str(e))

    while True:
        # Check status of shutdownFlag
        if shutdownFlag.is_set():
            # If down, break out of the endless while loop
            break
        # Get dictionary of available rtpRxStreams as a list
        # This will return a list of tuples [0]= sync Source id, [1]=the actual RtpStream object
        availableRtpRxStreamList = []
        # temp =[]
        # Iterate over tuples returned by items() to create a list of tuples
        rtpStreamsDictMutex.acquire()
        for k,v in rtpStreamsDict.items():
            temp = [k, v]
            availableRtpRxStreamList.append(temp)
        rtpStreamsDictMutex.release()

        if len(availableRtpRxStreamList) > 0:
            # Iterate over availableRtpRxStreamList looking for new events
            for currentRtpStream in availableRtpRxStreamList:

                # Attempt to access rtpStream events list
                # and create a sublist of the just the latest elements
                try:
                    allEvents = currentRtpStream[1].getRTPStreamEventList()

                    # Now check to see if there are any previously unwritten events in the allEvents list
                    # Subtract lastWrittenEventNo from most recent eventNo
                    if len(allEvents) > 0:
                        # Determine the new events for this particular stream
                        # Note, if this stream is 'brand new' the key for that stream won't exist yet, so create it
                        # and set it to a default value of 0 (because we haven't written any events yet from that RtpStream object)
                        if not currentRtpStream[0] in lastWrittenEventNoDict:
                            lastWrittenEventNoDict[currentRtpStream[0]] = 0

                        # Calculate how many new (i.e not yet written to disk) events there in are in this RtpStream object
                        newEvents = allEvents[-1].eventNo - lastWrittenEventNoDict[currentRtpStream[0]]

                        if newEvents > 0:
                            # There are outstanding events to be written
                            # Slice the latest portion of the allEvents list into a sub list
                            latestEvents = allEvents[(newEvents * -1):]
                except Exception as e:
                    Message.addMessage("DBUG: __diskLoggerThread - determining new events" + str(e))

                # Confirm to see that there are some events in the list
                if len(latestEvents) > 0:
                    # Open the files for writing (a denotes 'append', + denotes read/write
                    try:
                        file_csv = open(filename_csv, "a+")
                        file_json = open(filename_json, "a+")
                        for event in latestEvents:
                            # Get the event data in csv format
                            eventString = event.getCSV()+"\n"
                            # Write the event(s) to disk
                            file_csv.write(eventString)
                            # Get a json object from the event (as a string)
                            eventAsJson = event.getJSON() + "\n"
                            file_json.write(eventAsJson)
                            lastWrittenEventNo = event.eventNo
                            # Make a note of the last written event no against this stream id key
                            lastWrittenEventNoDict[currentRtpStream[0]] = event.eventNo
                        # Close the files
                        file_csv.close()
                        file_json.close()
                        # Empty the latestEvents list
                        del latestEvents[:]
                    except Exception as e:
                        Message.addMessage("DBUG: __diskLoggerThread - appending to file" + str(e))

        # Finally, iterate over lastWrittenEventNoDict{} to confirm that all the stream objects listed
        # inside it still exist in rtpStreamsDict{} (in other words, synchronise the deletions within
        # rtpStreamsDict{} to lastWrittenEventNoDict{}
        # This will prevent lastWrittenEventNoDict from filling up with orphan streams
        orphanStreamsToDelete =[]
        rtpStreamsDictMutex.acquire()
        for stream in lastWrittenEventNoDict:
            # Check for existence of key[stream] within rtpStreamsDict
            if stream in rtpStreamsDict:
                # If it is, do nothing
                pass
            else:
                # If key no longer exists, add it to the list to be purged from lastWrittenEventNoDict{}
                orphanStreamsToDelete.append(stream)
        rtpStreamsDictMutex.release()

        # Now delete all keys listed in orphanStreamsToDelete[] from lastWrittenEventNoDict{}
        for stream in orphanStreamsToDelete:
            Message.addMessage("INFO: _diskLoggerThread: Deleting orphan stream " + str(stream) + " from lastWrittenEventNoDict")
            del lastWrittenEventNoDict[stream]
        time.sleep(1)

    # If execution gets here, the thread is eding....
    print("_diskLoggerThread ending\r")
    try:
        Message.addMessage("__diskloggerThread: Closing files " + str(filename_json) + " and " + str(filename_csv))
        file_csv.close()
        file_json.close()
    except Exception as e:
        Message.addMessage("ERR: __diskloggerThread. Error closing files " + str(e))

# Autonomous thread to decode rtp streams and pass the data into the relevant RtpRXStream
def __receiveRtpThread(rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,
                       UDP_RX_IP, UDP_RX_PORT, ISPTEST_HEADER_SIZE, glitchEventTriggerThreshold):
    # An RTP header is 12 bytes long
    RTP_HEADER_SIZE = 12

    # Create a dictionary to initially hold the sync source of a potential rx stream
    rtpRxStreamTempDict = {}

    # Flag to signal whether RtpStream (Receive stream) socket vars have to be refreshed.
    # This will happen if the receive socket has to be recreated (due to an OS (Windows) error
    # and there are currently active receive streams
    # (Nb. Windows has a habit of terminating a socket if it receives a bad packet. Since all the receive streams
    # (and their corresponding ResultsTransmitters) are sharing a reference to this single socket, this is a problem.
    refreshRtpStreamSocketsFlag = False

    # # Create a diskLogging Thread - pass rtpStream object to it
    # diskLoggerThread = threading.Thread(target=__diskLoggerThread,
    #                                     args=(operationMode, rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,))
    # diskLoggerThread.daemon = True  # Thread will auto shutdown when the prog ends
    # diskLoggerThread.setName("__diskLoggerThread")
    # diskLoggerThread.start()

    while True:
        # Create receive UDP socket
        try:
            udpSocket = socket.socket(socket.AF_INET,  # Internet
                                 socket.SOCK_DGRAM)  # UDP

            # Set a timeout of 1 second. This should mean that socket.recvfrom() only blocks for a maximum
            # of 1 second if there's no data incoming
            udpSocket.settimeout(1)
            udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))

            # If this a 'regeneration' of the existing socket, we need to inform all the existing RtpStream objects of the change
            if refreshRtpStreamSocketsFlag == True:
                # Clear the flag
                refreshRtpStreamSocketsFlag = False
                try:
                    # For Python3 (which has the id() function)
                    Message.addMessage(Term.RedWhi + "Regenerated UDP Rx socket " + str(id(socket)))
                except:
                    # For Python2 which doesn't
                    Message.addMessage(Term.RedWhi + "Regenerated UDP Rx socket " + str(socket))
                # Update all streams in rtpRxStreamsDict
                for stream in rtpRxStreamsDict:
                    rtpRxStreamsDict[stream].setSocket(udpSocket)


        except Exception as e:
            Message.addMessage(Term.FG(Term.RED) + "__main(): Cannot create socket listen on " + UDP_RX_IP + ":" + str(
                UDP_RX_PORT) + ", " + str(e) + \
                               ". Try another port. Exiting" + Term.FG(Term.RESET))
            Message.addMessage("__main(): " + str(e))
            time.sleep(2)
            exit()

        data = b""  # Will hold the data received - specify a bytes string

        while True:
            # Check status of shutdownFlag
            if shutdownFlag.is_set():
                # If down, break out of the endless while loop
                break

            # Endless UDP receive loop
            # recvfrom() returns two parameters, the src address:port (addr) and the actual data (data)
            try:
                # Wait for data (blocking function call)
                data, addr = udpSocket.recvfrom(4096)  # buffer size is 4096 bytes
                # Confirm that we have some data (RTP header is 12 bytes long)
                if len(data) == 0:
                    Message.addMessage("socket is broken")
                if len(data) >= RTP_HEADER_SIZE:
                    # Get timestamp at the point the packet was received
                    timeNow = datetime.datetime.now()
                    try:
                        srcAddress = addr[0]
                        srcPort = addr[1]

                        # Split rtp header into an array of values
                        # RTP header is 12 bytes long. Unpack it as an array.
                        # !=big endian, B=unsigned char(1), H=unsigned short(2), L=unsigned long(4)
                        # This is the size of my own header prefix values (18 bytes)
                        rtpHeader = struct.unpack("!BBHLL", data[:RTP_HEADER_SIZE])

                        # Calculate the data payload size
                        payloadSize = len(data) - RTP_HEADER_SIZE

                        # Take copies of the data values that we need
                        # 	sequence no=rtpHeader[2]
                        #	timestamp=rtpHeader[3]
                        # 	sync-source identifier =rtpHeader[4]

                        rtpSequenceNo = rtpHeader[2]
                        rtpSyncSourceIdentifier = rtpHeader[4]

                        # Attempt to extract and make sense of the payload (has it been sent by isptest?)
                        isptestHeaderData = b""
                        if payloadSize >= ISPTEST_HEADER_SIZE:
                            # Substring the isptest header part of the payload
                            isptestHeaderData = data[RTP_HEADER_SIZE:(RTP_HEADER_SIZE + ISPTEST_HEADER_SIZE)]

                        # Attempt to add the data to an existing rtpStream object keyed by the rtpSyncSourceIdentifier
                        try:
                            # For the sake of speed, this operation won't use the rtpRxStreamsDictMutex
                            rtpRxStreamsDict[rtpSyncSourceIdentifier].addData(rtpSequenceNo, payloadSize, timeNow,
                                                                              rtpSyncSourceIdentifier,
                                                                              isptestHeaderData)

                        except:

                            # Test to see if the latest rtpSyncSourceIdentifier already exists as a key in tpRxStreamTempDict

                            if rtpSyncSourceIdentifier in rtpRxStreamTempDict:
                                # If successful, create a new rxStream and add to the rtpRxStreamsDict{}
                                Message.addMessage(Fore.GREEN + "INFO: " + str(rtpSyncSourceIdentifier) +
                                                   " exists in rtpRxStreamTempDict, creating entry in rtpRxStreamsDict")
                                # Create and add the new stream to the rtpRxStreamsDict
                                newRtpStream = RtpReceiveStream(rtpSyncSourceIdentifier, srcAddress, srcPort, UDP_RX_IP, \
                                                                UDP_RX_PORT, glitchEventTriggerThreshold, udpSocket,
                                                                rtpRxStreamsDict, rtpRxStreamsDictMutex)

                                # Now delete the entry from the temporary dict
                                rtpRxStreamTempDict.pop(rtpSyncSourceIdentifier, None)

                            else:
                                # If the stream doesn't exist as a key in either or rtpRxStreamsDict{} rtpRxStreamTempDict{},
                                # create a entry in the temporary list (with a timestamp)
                                Message.addMessage(
                                    Fore.RED + "INFO: Stream doesn't exist yet, adding to temp list: " + str(
                                        rtpSyncSourceIdentifier))
                                rtpRxStreamTempDict[rtpSyncSourceIdentifier] = timer()

                    except Exception as e:
                        # Problem decoding RTP headers
                        message = Fore.RED + "Cannot decode RTP headers. Is this an RTP packet? " + str(
                            e) + " Length:" + str(len(data)) + \
                                  " bytes received\r"
                        print (message)
                        Message.addMessage(message)
                else:
                    message = Fore.RED + "ERR: Invalid/no data received: " + str(addr) + ", " + str(data)
                    print (message)
                    Message.addMessage(message)

                # Now delete contents of data[]
                data = b""

            # Catch timeout exception (and ignore it)
            except socket.timeout:
                # Message.addMessage("DBUG: main() recvfrom. timeout exception")
                pass


            # Catch all other exceptions
            except Exception as e:
                Message.addMessage(Term.WhiRed + "ERR: __main()udpSocket.recvfrom():" + UDP_RX_IP + ":" + \
                                   str(UDP_RX_PORT) + ", " + str(id(udpSocket)))

                Message.addMessage("__main() recvfrom: " + str(e))
                try:
                    # Close existing socket
                    udpSocket.close()
                except Exception as e:
                    Message.addMessage("ERR: main() udpSocket.close() " + str(e))

                # Now try to recreate the socket
                # break out of this inner while loop to the outer while loop (where the socket is created)
                break

            # Iterate over tpRxStreamTempDict to purge it of old, non-existant streams that never made it into rtpRxStreamTempDict
            # If an RTP packet with the matching sync source id doesn;t appear within nonExistentStreamTimout_seconds seconds,
            # the stream will be deleted from tpRxStreamTempDict{}
            nonExistentStreamTimout_seconds = 5
            streamsToPurge = []
            # Compile list of orphan streams
            for stream in rtpRxStreamTempDict:
                if (timer() - rtpRxStreamTempDict[stream]) > nonExistentStreamTimout_seconds:
                    # Add to list
                    streamsToPurge.append(stream)

            # If there are some streams to purge, purge them
            if len(streamsToPurge) > 0:
                for stream in streamsToPurge:
                    Message.addMessage("INFO: Deleting orphan stream: " + str(stream) + " from rtpRxStreamTempDict{}")
                    # Delete the stream (key) from the dictionary as not wanted
                    rtpRxStreamTempDict.pop(stream, None)

        # Check status of shutdownFlag
        if shutdownFlag.is_set():
            # If down, break out of the endless while loop
            break

        # If program execution gets here, the udp socket must have been corrupted
        Message.addMessage(
            Term.WhiRed + "WARNING. Recreating UDP receive socket. Glitches might not be genuine          ")
        refreshRtpStreamSocketsFlag = True


        time.sleep(1)

    try:
        # Close the recvfrom socket in
        udpSocket.close()
    except Exception as e:
        Message.addMessage("ERR: main() Can't close recvfrom socket. " + str(e))

    Message.addMessage("__receiveRTPThread exiting")
    print("__receiveRTPThread exiting\r")


####################################################################################

class RequestShutdown(Exception):
    """
    Custom exception which is used to trigger the clean exit
    of all running threads and the main program.
    This Exception will be used to trap Ctrl-C from the keyobard (SIGINT)
    It will be used to trigger a 'do you want to quit? dialogue

    """
    # It might not look important, but it is!
    # This empty class provides a means of forcing main() to jump out of whatever while() loop it's in under normal
    # running conditions to execute the shutdown sequence
    pass

class ShutdownApplication(Exception):
    """
        Custom exception which is used to trigger the clean exit
        of all running threads and the main program.
        it will likely be triggered by a SIGTERM signal, or else from a user generated shutdown request
        via the RequestShutdown Exception
        """
    # It might not look important, but it is!
    # This empty class provides a means of forcing main() to jump out of whatever while() loop it's in under normal
    # running conditions to execute the shutdown sequence
    pass


# Define a callback function to handle SIGINT and SIGTERM messages from the OS

# This function will be invoked by SIGTERM (i.e by the OS sending a kill signal)
def requestShutdownSignalHandler(signum, frame):
    Message.addMessage("DBUG: requestShutdownSignalHandler called")
    print('Caught signal ' + str(signum) + "\r")
    raise RequestShutdown

# This function will be invoked by SIGTERM (i.e by the OS sending a kill signal)
def shutdownApplicationSignalHandler(signum, frame):
    Message.addMessage("DBUG: shutdownApplicationSignalHandler called")
    print('Caught signal ' + str(signum) + "\r")
    raise ShutdownApplication





#### Experimental functions
def copyPaste():
    pyperclip.copy("new_clip\n\tNew line")

    print(pyperclip.paste())

# Main prog starts here
# #####################

def main(argv):
    # copyPaste()
    # print(str(pasteBin("Some\n\tnew\n\ttext", title="test paste", api_dev_key="uyddjhg")))
    #
    # exit()
    # # x = multi_input_dialog3(title="will it work?", text="default text").run()
    # x = input_dialog(title="will it work?", text="default text").run()
    # textFieldsList = [["dest addr", "127.0.0.1"], ["port", "5000"]]
    # print(str(multi_input_dialog3(textFieldsList, title='Enter IP addr and port').run()))
    #
    # exit()
    # try:
    #     # x = validators.integer(41, allow_empty=False, minimum=25, maximum=40)
    #     x= validators.ip_address("192.168.0.2", allow_empty=False)
    # except Exception as e:
    #     print (str(e) + "\r")
    # exit()
    # textFieldsList = [["dest addr", "127.0.0.1"], ["port", "5000"]]
    # print(str(multi_input_dialog(textFieldsList, title='Enter IP addr and port')))
    # exit()

    # # Invoke colorama init() method to allow ansi escape sequences to work on Windows
    # init(autoreset=True)

   # String to specify which operation mode we're in (loopback, tx, rx)
    MODE = ""


    # Additonal Operation Mode flag for 'special features'
    specialFeaturesModeFlag = False
    # Specify a default txRate of 1Mbps if no rate specified
    txRate = 1 * 1024 * 1024

    # Specify a default packet size for the tx stream (if none supplied)
    payloadLength = 1300

    # Default level of packet loss that will generate an event
    glitchEventTriggerThreshold  = 4

    UDP_TX_SRC_PORT = 0

    UDP_RX_IP = ""
    UDP_RX_PORT = 0

    # Default Sync Source identifier of first tx stream
    SYNC_SOURCE_ID =random.randint(1000, 2000)

    # Default lifespan of a tx stream (default 1 hr)
    txStreamTimeToLive_sec = 3600

    # Default friendly name of Tx stream (if not overridden, sync source ID is used instead)
    RTP_TX_STREAM_FRIENDLY_NAME = ""

    # An RTP header is 12 bytes long
    RTP_HEADER_SIZE = 12

    # Query the RtpGenerator class to find out the length (in bytes) of the isptest messages it will incorporate into the payload
    ISPTEST_HEADER_SIZE = RtpGenerator.getIsptestHeaderSize()

    # Default message verbosity
    defaultVerbosityLevel = 0
    # Set default value
    Message.setVerbosity(defaultVerbosityLevel)

    # print ('Argument List: '+ str(argv))
    try:
        # options are:
        # -h: help
        # -x: loopback mode
        # -t: transmit mode usage: address:port
        # -l: duration of transmission (in seconds. Default 1hr (3600 sec)
        # -b bandwidth (append k for kbps, m for mbps eg 1m or 500k). Default 1Mbps
        # -d udp packet size
        # -s udp transmit source port (for transmit or loopback mode)
        # -n friendly name for tx stream (10 chars max)
        # -r receive mode usage: address:port
        # -i Glitch event packet loss ignore threshold. Outages below this limit will not generate an event. Default = 4
        # -u sync source ID (for transmit or loopback mode)
        # -v:[int] verbosity
        # -z Enable special features (like simulate packel loss, jitter etc)



        address = ""

        # Check for no no option supplied:
        if len (argv) < 1:
            print ("No options supplied. Use -h for help")
            exit()

        opts, args = getopt.getopt(argv, "hxt:r:i:t:b:d:s:u:l:v:zn:")

        # Iterate over opts array and test opt. Then retrieve the corresponding arg
        for opt, arg in opts:
            if opt == '-h':
                print ("Version 1.1\r")
                print ("options are:\r")
                print ("-h: help (this message)\r")
                print ("-x: loopback mode\r")
                print ("-t: transmit mode usage: address:port\r")
                print("Additional transmit parameters:-\r")
                print ("\t-s [val] udp transmit source port (for transmit or loopback mode)\r")
                print ("\t-u [val] sync source ID (for transmit or loopback mode)")
                print ("\t-l: [val] duration of transmission (in seconds. Default 1hr (3600 sec). A value of -1 means 'forever'\r")
                print ("\t-b [val] tx bandwidth (append k for kbps, m for mbps eg -b 1m or -b 500k). Default 1Mbps\r")
                print ("\t-d [val] rtp payload size (bytes). Default = 1300 bytes\r")
                print ("\t-n: [name] friendly name for tx stream (10 chars max)\r")
                print ("\r")
                print ("-r receive mode usage: -r [port] or -r [address:port]\r")
                print("Additional receive parameters:-\r")
                print ("\t-i [val] Glitch event packet loss ignore threshold (or 'sensitivity'). \r")
                print("\t  Outages below this limit will not generate an event. Default = 4\r")
                print ("\r")
                print ("-v [val] message verbosity level 0-3\r")
                print ("\r")
                print ("-z Enable special features (like simulate packet loss, jitter etc)\r")
                exit()

            elif opt == '-x':
                MODE = "LOOPBACK"
                print (MODE)
                UDP_RX_IP = "127.0.0.1"
                UDP_RX_PORT = 5004
                UDP_TX_IP = "127.0.0.1"
                UDP_TX_PORT = 5004

            elif opt in ("-t"):
                MODE = "TRANSMIT"
                # check for two parameters separated by a colon
                if len(arg.split(':')) == 2:
                    UDP_TX_IP = arg.split(':')[0]
                    UDP_TX_PORT = int(arg.split(':')[1])
                    # Validate supplied IP address
                    try:
                        socket.inet_aton(UDP_TX_IP)
                    except socket.error:
                        print ("Invalid TRANSMIT IP address:port combination supplied: " + str(arg))
                        exit()
                    print (MODE+", "+str(UDP_TX_IP)+", "+str(UDP_TX_PORT))
                else:
                    print ("Invalid TRANSMIT IP address:port combination supplied: "+ str(arg))
                    exit()

            elif opt in ("-r"):
                MODE = "RECEIVE"
                # check for two parameters separated by a colon
                if len(arg.split(':')) == 2:
                    UDP_RX_IP = arg.split(':')[0]
                    UDP_RX_PORT = int(arg.split(':')[1])
                    # Validate supplied IP address
                    try:
                        socket.inet_aton(UDP_RX_IP)
                    except Exception as e:
                        print ("Invalid RECEIVE IP address:port combination supplied: " + str(arg) + ", "+ str(e))
                        exit()
                    print (MODE+", "+str(UDP_RX_IP)+", "+str(UDP_RX_PORT))
                else:
                    # If only a single parameter supplied, use the 'OS supplied' address
                    # and the supplied value as a UDP receive port
                    # Get the ip address of the host machine
                    UDP_RX_IP = get_ip()
                    try:
                        arg = int(arg) + 1 - 1
                        if arg < 1024:
                            print ("Invalid RECEIVE port supplied. Should be an integer > 1024: " + str(arg))
                            exit()
                        UDP_RX_PORT = arg
                        print (MODE + ", " + str(UDP_RX_IP) + ", " + str(UDP_RX_PORT))
                    except:
                        print ("Invalid RECEIVE port supplied. Should be an integer > 1024: " + str(arg))
                        exit()

            elif opt in ("-b"):
                try:
                    # Use regex to split -b argument into numerical and string parts
                    splitArg = re.split(r'(\d+)', arg)
                    # Extract numerical part
                    x = int(splitArg[1])
                    # Extract string part
                    multiplier = splitArg[2]

                    if multiplier == 'k' or multiplier == 'K':
                        txRate = x * 1024
                    elif multiplier == 'm' or multiplier == 'M':
                        txRate = x * 1024 * 1024
                    else:
                        print ("Invalid -b bandwidth specified. Unknown multiplier: " + str(multiplier))
                        exit()
                except:
                    print ("Invalid -b bandwidth specfied. Should be xy whether x is a numerical value and y is k or m (kbps or mbps). "+ \
                        "If no multiplier supplied then assuming x mbps. eg. 500k, 1m, 5m etc")
                    exit()


            elif opt in ("-d"):
                # Maximum Ethernet frame size is 1500 bytes (minus 12 bytes for the RTP header)
                MAX_PAYLOAD_SIZE_bytes = 1500 - 12
                MIN_PAYLOAD_SIZE_bytes = RtpGenerator.getIsptestHeaderSize()
                try:
                    if int(arg) > MAX_PAYLOAD_SIZE_bytes:
                        print ("requested payload size ("+ str(arg)+ \
                                ") exceeds maximum Ethernet frame size (1488 bytes with 12 byte RTP header). Setting to "+\
                               str(MAX_PAYLOAD_SIZE_bytes) + " bytes")
                        payloadLength = MAX_PAYLOAD_SIZE_bytes
                        time.sleep(1)
                    elif int(arg) < MIN_PAYLOAD_SIZE_bytes:
                        print ("requested payload size ("+ str(arg)+ ") less than minimum permitted ("+ str(MIN_PAYLOAD_SIZE_bytes)+
                               "). Setting to " + str(MIN_PAYLOAD_SIZE_bytes)+ "bytes")
                        time.sleep(1)
                    else:
                        payloadLength = int(arg)
                except Exception as e:
                    print ("Invalid payload size specified '"+ str(arg)+ "'")
                    exit()

            elif opt in ("-i"):
                # Test to see if supplied value is an int
                try:
                    # Simple test to see if arg is an integer. If it's a string, this will fail
                    glitchEventTriggerThreshold = int(arg) +1 -1
                    print("glitch -i: "+str(glitchEventTriggerThreshold))
                except:
                    print ("Invalid glitch ignore threshold specified. Must be an integer: " + str(int(arg)))
                    exit()


            elif opt in ("-s"):
                # Specify source UDP port
                # Test to see if supplied value is an int
                # print ("new src port(a): " + str(int(arg)))

                try:
                    # Simple test to see if arg is an integer. If it's a string, this will fail
                    UDP_TX_SRC_PORT = int(arg) + 1 -1
                except Exception as e:
                    print ("Invalid -s UDP source port specified (" + str(arg) + "). Must be an integer > 1024: " + str(e))
                    exit()

                UDP_TX_SRC_PORT = int(arg)
                if UDP_TX_SRC_PORT < 1024:
                    print ("Invalid -s UDP source port specified (" + str(arg) + "). Must be an integer > 1024: ")
                    exit()
                print ("new src port: " + str(UDP_TX_SRC_PORT))

            elif opt in ("-u"):
                # Specify sync source identifier
                # Test to see if supplied value is an int

                try:
                    # Simple test to see if arg is an integer. If it's a string, this will fail
                    SYNC_SOURCE_ID = int(arg) + 1 - 1
                except Exception as e:
                    print ("Invalid -u sync source id specified (" + str(arg) + "). Must be an integer < 2147483647: " + str(e))
                    exit()

                SYNC_SOURCE_ID = int(arg)
                if SYNC_SOURCE_ID > 2147483647:
                    print ("Invalid -u sync source id specified (" + str(arg) + "). Must be an integer < 2147483647: ")
                    exit()
                print ("sync source id: " + str(UDP_TX_SRC_PORT))

            elif opt in ("-l"):
                # Specify duration (or 'time to live' for tx stream)
                # Test to see if supplied value is an int

                try:
                    # Simple test to see if arg is an integer. If it's a string, this will fail
                    txStreamTimeToLive_sec = int(arg)  + 1 - 1
                except Exception as e:
                    print ("Invalid -l duration specified (" + str(arg) + "). Must be an integer. Use -1 for 'forever': " + str(e))
                    exit()

                print ("Tx time to live duration : " + str(txStreamTimeToLive_sec))

            elif opt in ("-v"):
                # Specify message verbosity (to hide warning messages)
                try:
                    # Test for an int
                    arg = int(arg) + 1 -1
                    # assign the value
                    Message.setVerbosity(arg)
                except:
                    print ("Invalid -v message verbosity value supplied. " + str(arg))
                    exit()

            elif opt in ("-z"):
                # Enable 'special features' mode
                specialFeaturesModeFlag = True

            elif opt in ("-n"):
                # Friendly name supplied for tx stream
                RTP_TX_STREAM_FRIENDLY_NAME = arg

    except getopt.GetoptError:
        print ('invalid options supplied'+ str(argv))
        exit()

    # Check for no no option supplied:
    if MODE=="":
        print ("No mode option specified. Do you want Transmit or Receive mode?. Use -h for help")
        exit()

    # Create a dictionaries for all streams
    rtpTxStreamsDict ={}
    # Create a mutex lock for the tx streams dictionary (for deleting objects)
    rtpTxStreamsDictMutex = threading.Lock()

    # Create a dictionary to hold the rx Streams
    rtpRxStreamsDict = {}

    # # Create a dictionary to initially hold the sync source of a potential rx stream
    # rtpRxStreamTempDict = {}

    # Create a mutex lock to be used when writing to the rtpRxStreamsDict (or deleting objects)
    rtpRxStreamsDictMutex = threading.Lock()

    # Create a dictionary to hold the server reports/results of the tx streams
    rtpTxStreamResultsDict = {}
    # Create an associated mutex
    rtpTxStreamResultsDictMutex = threading.Lock()



    # Register signal handler for SIGINT, SIGTERM and SIGKILL
    signal.signal(signal.SIGINT, requestShutdownSignalHandler) # Ctrl-C
    signal.signal(signal.SIGTERM, shutdownApplicationSignalHandler)    # OS kill signal


    # Create a UI object (which will spawn a renderDisplay and catchKeyboardPresses thread)
    # Create flag that will be used by UI to signal back to main() that a shutdown has been requested
    shutdownFlag = threading.Event()
    # Make sure flag is initially cleared
    shutdownFlag.clear()
    # Create flag that will be used to remotely enable/disable the disklogger and __receiveRtpStream threads
    # enableUIFlag = threading.Event()
    # # Make sure flag is initially set
    # enableUIFlag.set()

    # # Create a UI flag that will allow the UI thread to be woken up (to force a redraw)
    # wakeUpUI = threading.Event()

    ui = UI(MODE, specialFeaturesModeFlag,\
        rtpTxStreamsDict, rtpTxStreamsDictMutex,\
        rtpRxStreamsDict, rtpRxStreamsDictMutex,\
        rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex,\
        UDP_RX_IP, UDP_RX_PORT)

    # Start traffic generator thread
    if MODE == 'LOOPBACK' or MODE == 'TRANSMIT':
        # If UDP source port specified
        # if UDP_TX_SRC_PORT >0:
        rtpGenerator = RtpGenerator(UDP_TX_IP, UDP_TX_PORT, txRate,
                                    payloadLength, SYNC_SOURCE_ID, txStreamTimeToLive_sec,
                                    rtpTxStreamsDict, rtpTxStreamsDictMutex,
                                    rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex,
                                    UDP_SRC_PORT=UDP_TX_SRC_PORT, friendlyName=RTP_TX_STREAM_FRIENDLY_NAME)

        # Create a diskLogging Thread - pass rtpStream object to it
        diskLoggerThread = threading.Thread(target=__diskLoggerThread, args=(MODE, rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex, shutdownFlag,))
        diskLoggerThread.daemon = True  # Thread will auto shutdown when the prog ends
        diskLoggerThread.setName("__diskLoggerThread")
        diskLoggerThread.start()

    # Main program execution loops
    # # Declare a var to be used as the socket.recvfrom UDP socket
    # sock = None

    # Define a local function that will perform a graceful shutdown of all threads and resources
    def shutdownApplication():
        Message.addMessage("main.shutdownApplication() called")
        # Attempt to remove all rtp stream objects
        for dict in [rtpTxStreamsDict, rtpRxStreamsDict]:
            if len(dict) > 0:
                # Temporary list to hold the streams currently in rtpStreamsDict
                # Note: We can't iterate over the dict cal the the killStream methods directly. This is because
                # killStream() acts on the rtpTxStreamsDict or rtpRxStreamsDict dictionary itself -
                # and you can't iterate over a dictionary whilst simultaneously modifying it
                tempStreamList = []
                # take a copy of the dict to iterate over
                for stream in dict:
                    # Take a copy of the key value (the stream ID)
                    tempStreamList.append(stream)
                # Now iterate of the new streamList, calling .killStream() on all the objects within
                for stream in tempStreamList:
                    Message.addMessage("INFO: Killing " + str(type(dict[stream])) + ": " + str(stream))
                    print("Killing stream " + str(stream) + "\n")
                    # Invoke the kill method of each stream
                    dict[stream].killStream()


        ############ Stop DiskLogger and __receiveRTP threads (currently they stop themselves)
        shutdownFlag.set()
        # Wait for diskLogger Thread to end
        diskLoggerThread.join()

        # wait for __receiveRtpStream Thread to end (if it exists)
        if MODE == 'RECEIVE' or MODE == 'LOOPBACK':
            receiveRtpThread.join()
        time.sleep(0.2)
        Term.clearScreen()
        Term.printAt("main.shutdownApplication() in progress", 1, 1)

        # Now kill UI
        ui.kill()
        exit()


    if MODE == 'RECEIVE' or MODE == 'LOOPBACK':


        # Create a diskLogging Thread - pass rtpStream object to it
        diskLoggerThread = threading.Thread(target=__diskLoggerThread,
                                            args=(MODE, rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,))
        diskLoggerThread.daemon = True  # Thread will auto shutdown when the prog ends
        diskLoggerThread.setName("__diskLoggerThread")
        diskLoggerThread.start()

        # Create a thread to receive the RTP streams
        receiveRtpThread = threading.Thread(target=__receiveRtpThread,
                                            args=(rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,
                   UDP_RX_IP, UDP_RX_PORT, ISPTEST_HEADER_SIZE, glitchEventTriggerThreshold,))
        receiveRtpThread.setName("__receiveRtpThread")
        receiveRtpThread.start()

    # Endless loop
    while True:
        try:
            while True:
                # Term.printAt(str(listCurrentThreads()),1,2)
                time.sleep(1)

        # This code will execute if the RequestShutdown Exception is raised (SIGINT, Ctrl-C)
        except RequestShutdown:
            Message.addMessage("DBUG: RequestShutdown Exception raised")
            # Put up a Quit y/n dialogue
            userResponse = ui.showShutDownDialogue()
            # Message.addMessage(str(datetime.datetime.now()) + ", main() except RequestShutdown: " + str(userResponse))
            # If yes, quit
            if userResponse:
                shutdownApplication()
            # Otherwise ignore
            else:
                pass

        # This code will execute if the ShutdownApplication Exception is raised (SIGTERM)
        # It will cause the pgram to end, with no user prompt
        except ShutdownApplication:
            Message.addMessage("DBUG: ShutdownApplication Exception raised (SIGTERM)")
            shutdownApplication()


# Invoke main() method (entry point for Python script)
if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    main(sys.argv[1:])
