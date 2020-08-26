#!/usr/bin/env python
#
# Python packet sniffer
#
# 
from __future__ import unicode_literals # Required for prompt_toolkit

from Registry import Registry # This class contains constants/defaults used throughout the program

# Tests the current Python interpreter version
def testPythonVersion(majorVersionNo, minorVersionNumber):
    # If the major and minor version number is not satisfied
    # i.e the installed version is < than majorVersionNo.minorVersionNumber (eg 3.6) it will
    # call exit() with an error message
    import sys
    # Get current Python version
    version = sys.version_info
    def printErrorMessage():

        print("You're not running a latest enough version of Python.\r")
        print("This is v" +\
              str(version[0]) + "." + str(version[1]) + ". isptest requires at least v" +\
              str(majorVersionNo) + "." + str(minorVersionNumber) + "\r")
        print("\r")
        print("Hint: Python3 *might* be installed. Try re-running using 'python3 [args]'\r")
        print("or else, try python [tab] which (on OSX and Linux) should list the possible\r")
        print("versions of the Python interpreter installed on this system.\r")


    # print("you're running Python version " + str(int(version[0])) + "." + str(int(version[1])) + "\r")
    # Check major release version):
    if int(version[0]) < majorVersionNo:
        # Major version doesn't meet requirements
        printErrorMessage()
        return False
    else:
        # Major version is okay, now check minor version
        if int(version[1]) < minorVersionNumber:
            # Minor version doesn't meet requirements
            printErrorMessage()
            return False
        # Else Installed Python version satisfies minimum requirements
        return True
# Check for minimum python version (currently 3.6)
if (testPythonVersion(Registry.pythonMinimumVersionRequired_Major,Registry.pythonMinimumVersionRequired_Minor)):
    pass
else:
    # Python version not satisfied so exit
    exit()


import select
import sys

# from icmplib import ICMPv4Socket, TimeoutExceeded, ICMPRequest
# from Custom_icmplib import customICMPv4Socket
from functools import reduce
from queue import SimpleQueue, Empty

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
import textwrap
import pickle

# import cgitb
# cgitb.enable(format='text')

# Non standard external libraries (need importing with pip)
from terminaltables import SingleTable  # Used for pretty tables in displayThread
from colorama import init, Fore, Back, Style # Used to allow ansi escape sequences to work on Windows
from validator_collection import validators, checkers, errors
import six  # Required for strings being passed to prompt_toolkit dialogues (they won't accept Python2 strings)


# from prompt_toolkit import prompt, shortcuts   # Note, had to be installed with  pip install --ignore-installed six prompt_toolkit --user
from prompt_toolkit.shortcuts import message_dialog, yes_no_dialog, input_dialog
from prompt_toolkit.styles import Style
import pyperclip
from pathvalidate import ValidationError, validate_filename, sanitize_filepath

# Additional experimental libraries


# Additonal libraries required (of my own making)
from RtpStreams import RtpReceiveStream, RtpGenerator, RtpStreamResults, Glitch, RtpData
import Utils
from Custom_prompt_toolkit_mods import multi_input_dialog
from Traceroute import *


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
        Utils.Message.addMessage("INFO: __updateAvailableStreamsList() Added stream: " + str(x[0]) + ", " + str(type(x[1])))
    for streamID in deleteList:
        # Iterate over tuples in rtpStreamList[] searching for a match
        for index, stream in enumerate(rtpStreamList):
            if stream[0] == streamID:
                # If stream found, delete that tuple from the list
                Utils.Message.addMessage("INFO: __updateAvailableStreamsList() Removing stream " + str(stream[0]) + ", " + str(type(stream[1])))
                try:
                    rtpStreamList.pop(index)
                except Exception as e:
                    Utils.Message.addMessage("ERR: __updateAvailableStreamsList: "+str(e))
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
                Utils.Message.addMessage("ERR:__updateAvailableStreamsList() Object mismatch for streamID "+str(stream[0])+". Repointing to correct object")
                # Now re-point rtpStreamList to the correct version of that object
                # by assigning the correct object to the entry in rtpStreamList[]
                stream[1]=rtpStreamDict[stream[0]]
        except Exception as e:
            Utils.Message.addMessage("ERR:__updateAvailableStreamsList(), rtpStreamDictkey error for stream "+str(stream[0])+", "+str(e))
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
                    receiversAndSendersList):

        self.operationMode = operationMode
        self.specialFeaturesModeFlag = specialFeaturesModeFlag
        self.rtpTxStreamsDict = rtpTxStreamsDict
        self.rtpTxStreamsDictMutex = rtpTxStreamsDictMutex
        self.rtpRxStreamsDict = rtpRxStreamsDict
        self.rtpRxStreamsDictMutex = rtpRxStreamsDictMutex
        self.rtpTxStreamResultsDict = rtpTxStreamResultsDict
        self.rtpTxStreamResultsDictMutex = rtpTxStreamResultsDictMutex

        self.receiversAndSendersList = receiversAndSendersList # This will contain the UDP_RX_IP and  UDP_RX_PORT(s)
        self.pid = os.getpid() # Stores the processID (pid of this process. Used as a source id in
        # control messages sent back to the transmitter (so that the source of the message can be identified)


        # self.UDP_RX_IP = ""
        # self.UDP_RX_PORT = 0

        # If true, this will cause renderDisplayThread to put up a quit y/n? prompt
        self.displayQuitDialogueFlag = False
        # threading.Event object used to intentionally block the showShutDownDialogue() method
        self.quitDialogueNotActiveFlag = threading.Event()
        # This will store the result of the user response
        self.quitConfirmed = False

        # Use to control the display of the Events List dialogue
        self.displayEventsTable = False
        # Use to control the display of the Traceroute dialogue
        self.displayTraceRouteTable = False
        # Used to control the display of the help pages
        self.displayHelpTable = False
        # Used by the EventsTable (and Traceroute table). Keeps track of the current display page
        self.tablePageNo = 0
        # Used to send popup error messages to UI.__renderDisplayThread
        self.displayFatalErrorDialogue = False
        self.fatalErrorDialogueMessageText = ""
        self.fatalErrorDialogueTitle = ""
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
        # Allows other parts of the program to query the current status of the __keysPressedThread
        self.getchIsDisabled = threading.Event()
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
        self.keyCommandsString = "[<][>][^][v]navigate, [d]elete, [l]abel, [a]bout, [r]eport, [h]elp, [t]raceroute"

        self.txStreamModifierCommandsString = "TX  modifiers: [1/2] packet size, [3/4] tx rate, [5/6] lifetime, [n]ew [b]urst"
        # Extra command strip for 'special features' mode
        self.extraKeyCommandsString = "[7] enable/disable stream, [8] jitter on/off, [9] minor loss, [0] major  loss"

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
                           ["Name", 'Friendly Name'], # [column title, dictionary key containing that value]
                           ["Src\nPort", 'Tx Source Port'],
                           ["Dest\n IP", 'Dest IP'],
                           ["Dest\nPort", 'Dest Port'],
                           ["Sync\nsrcID", 'Sync Source ID'],
                           ["Tx\nbps", 'Tx Rate (actual)'],
                           ["Size", 'Packet size'],
                           ["Bytes\n tx'd", 'Bytes transmitted'],
                           [" Time\nremain", 'Time to live']
                           ], self.availableRtpTxStreamList]) # data source

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
                       ["Time since\nlast glitch", "glitch_time_elapsed_since_last_glitch"],
                       ["glitch\nperiod", "glitch_mean_time_between_glitches"],
                       ["Count", "glitch_counter_total_glitches"]
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
                       ["TTL", "packet_instantaneous_ttl"]
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
                       ["10Sec\n", "historic_glitch_counter_last_10Sec"],
                       [" Time of\nlast glitch", "glitch_most_recent_timestamp"]
                       # ["", ""],
                       ], self.streamResultsDataSet])

        self.views.append(["Jitter",
                      [["#", 0],  # Used as an index[]
                       ["Name", "stream_friendly_name"],
                       ["Long term\n  mean", "jitter_long_term_uS"],
                       ["Min", "jitter_min_uS"],
                       ["Max", "jitter_max_uS"],
                       ["Range", "jitter_range_uS"],
                       ["1S \nmean", "jitter_mean_1S_uS"],
                       ["10S \nmean", "jitter_mean_10S_uS"]
                       ], self.streamResultsDataSet])

        self.views.append(["NAT",
                      [["#", 0],  # Used as an index[]
                       ["src\nport", "stream_transmitter_local_srcPort"],
                       ["Tx Local addr", "stream_transmitter_localAddress"],
                       ["Tx Natted addr", "stream_srcAddress"],
                       ["src\nport", "stream_srcPort"],
                       ["Rx Public addr", "stream_transmitter_destAddress"],
                       ["Rx Local addr", "stream_rxAddress"]
                       ],self.streamResultsDataSet])

        # Additionally, for RECEIVE mode, add a further table that will show the transmitter parameters
        if self.operationMode == 'RECEIVE':
            self.views.append([Term.FG(Term.RED) + "Transmitter",
                          [["#", 0],  # Used as an index[]
                           ["Name", "stream_friendly_name"],
                           ["Target\nTx Bps", 'stream_transmitter_txRate_bps'],
                           [" Time\nremain", 'stream_transmitter_TimeToLive_sec']
                           ], self.streamResultsDataSet])
        # self.views.append(["Misc",
        #               [["#", 0],  # Used as an index[]
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ["", ""],
        #                ],DATASET_TO_DISPLAY])

        # Stores the most recent message - used to determine whether we need to redraw the message table
        self.lastMessageAdded = ""

        # Get Initial snapshot of current verbosity level
        self.intialVerbosityLevel = Utils.Message.verbosityLevel
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

    # This method will cause an error message to be shown by the main __renderDisplayThread
    # it will wait for a key press, and then cause the app to shut down (without user confirmation) via a SIGTERM
    def showErrorDialogue(self, errorTitle, errorMessageText):
        Utils.Message.addMessage("DBUG: UI.showFatalErrorDialogue() called")
        self.fatalErrorDialogueTitle = errorTitle
        self.fatalErrorDialogueMessageText = errorMessageText
        self.displayFatalErrorDialogue = True


    # This method will pause the normal screen rendering/key catching and cause a
    # 'do you want to quit? dialogue to be displayed
    # It is designed to be a blocking method. It will return True/False depending upon whether
    # the user confirms the shutdown request
    def showShutDownDialogue(self):
        Utils.Message.addMessage("DBUG: UI.showShutDownDialogue() called")
        # Cause the UI render thread to put up a Quit Y/N prompt
        self.displayQuitDialogueFlag = True
        # Clear the threading.Event signal for self.quitDialogueActiveFlag
        self.quitDialogueNotActiveFlag.clear()
        # Wake up the UI
        self.wakeUpUI.set()
        # Now wait for the __renderDisplayThread to signal that the prompt has been answered (blocking call)
        # by 'setting' self.quitDialogueNotActiveFlag
        Utils.Message.addMessage("DBUG: UI.showShutDownDialogue() waiting for self.quitDialogueNotActiveFlag to clear")
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
                                    # is it a receive stream?
                                    # If so, test the stream stats
                                    if type(streamData[1]) == RtpReceiveStream or type(
                                            streamData[1]) == RtpStreamResults:
                                        # Is the source of this stream an instance of an isptest transmitter?
                                        # If not (eg. from an NTT) mask the 'Transmitter' pane values as these would
                                        # be carried in the isptestheader, and will therefore be missing
                                        if streamDataStats["stream_transmitterVersion"] > 0:
                                            # If these are isptest-generated packets, leave alone
                                            pass
                                        else:
                                            # Otherwise overwrite the tablecell value for certain keys where the
                                            # data is not available
                                            if key == 'stream_transmitter_txRate_bps' or \
                                                key == 'stream_transmitter_TimeToLive_sec':
                                                tableCell = "-"

                                        # Colour code the table based on some received bitrate
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
                                    Utils.Message.addMessage(
                                        "ERR: __displayThread: (colour coding of stream tables) " + str(e) + "**")

                            except Exception as e:
                                # If the key doesn't exist within the rtpStream stats dict, copy in an error code instead
                                tableCell = "keyErr"
                                Utils.Message.addMessage("ERR: __displayThread (for key in keyList): " + str(e))

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
            Utils.Message.addMessage("ERR: __displayThread. streamTable. selected row (" + str(self.selectedTableRow) + \
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
        messages = deepcopy(Utils.Message.getMessages(maxNoOfMessagesThatWillFitScreen))
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
                            Utils.Message.addMessage("__displayThread: Invalid message")

            if len(messages) > 0:
                width, height, tableData = Term.createTable(messages, "Messages")
                # Overwrite previous messages table
                for y in range(yPos, yPos + (maxNoOfMessagesThatWillFitScreen + 3)):
                    Term.setBackgroundColourSingleLine(1, y, Term.BLUE)
                Term.printTable(tableData, 2, yPos, width, Term.BLACK, Term.WHITE)
        del messages[:]

    def __renderTopToolbar(self):
        Term.printTitleBar("IBEOO ISP Analyser v" + Registry.version, 1, Term.BLACK, Term.WHITE)
        # Print operation mode (plus receive IP:Port if in Receive mode)
        if self.operationMode == 'TRANSMIT' or self.operationMode == 'LOOPBACK':
            Term.printAt(self.operationMode + " MODE", 1, 1, Term.BLACK, Term.WHITE)
        elif self.operationMode == 'RECEIVE':
            try:
                # Extract the receive IP and receive port(s) (if in RECEIVE mode - these are displayed on the top toolbar)
                if len(self.receiversAndSendersList) > 0:
                    # Take the Rx IP address from the first RtpPacketReceiver in the list (we assume that we will only be
                    # listening on a single IP address, but might be listening to multiple ports on that interface)
                    UDP_RX_IP = self.receiversAndSendersList[0][0].UDP_RX_IP
                    # Get a list of Rx UDP ports from the RtpPacketReceiver objects and create a string
                    UDP_RX_PORTS = ""
                    for n in range(0,len(self.receiversAndSendersList)):
                        # Extract the port no for the current RtpPacketReceiver object
                        UDP_RX_PORTS += str(self.receiversAndSendersList[n][0].UDP_RX_PORT)
                        # For all but the last port, append a "," to divide the port no.s
                        if n == (len(self.receiversAndSendersList) - 1):
                            # We're at the last item in the list, don't append a ','
                            pass
                        else:
                            # If we're still in the middle of the list, append a ','
                            UDP_RX_PORTS += ","


            except Exception as e:
                Utils.Message.addMessage(
                    "ERR:UI.__init() Couldn't extract UDP_RX_IP and UDP_RX_PORT(s) from receiversAndSendersList " + \
                    str(e))
            Term.printAt(self.operationMode + " " + str(UDP_RX_IP) + ":" + \
                         str(UDP_RX_PORTS), 1, 1, Term.BLACK, Term.WHITE)

    def __updateClock(self):
        # Update clock and CPU mon on top RHS of screen
        # clockString = datetime.datetime.now().strftime("%H:%M:%S") + " " + str(round(Utils.CPU.getUsage())) + "%"
        clockString = datetime.datetime.now().strftime("%H:%M:%S")
        Term.printRightJustified(clockString, 1, Term.BLACK, Term.WHITE)

    def __renderBottomToolbar(self):
        Term.setBackgroundColourSingleLine(1, (self.currentTermHeight - 1), Term.WHITE)
        # Print list of key commands
        Term.printAt(self.keyCommandsString, 1, (self.currentTermHeight - 1), Term.BLACK, Term.WHITE)
        Term.setBackgroundColourSingleLine(1, (self.currentTermHeight - 2), Term.WHITE)
        Term.printAt(self.txStreamModifierCommandsString, 1, (self.currentTermHeight - 2), Term.BLACK, Term.WHITE)

        # For tx mode special features, add an extra row of commands
        if self.operationMode == 'TRANSMIT' or self.operationMode == 'LOOPBACK':
            # Term.setBackgroundColourSingleLine(1, (self.currentTermHeight - 2), Term.WHITE)
            # Term.printAt(self.txStreamModifierCommandsString, 1, (self.currentTermHeight - 2), Term.BLACK, Term.WHITE)

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

        # Count how many newlines there are in the table data
        noOfNewlinesInTableData = 0
        # Iterate over the rows
        for row in tableData:
            # Iterate over the cells within each row
            # Each cell might have different no of lines, so have to find the cell with the most no of newline char
            maxLinesCurrentRow = 0
            for cell in row:
                # Count the no of lines in this cell
                linesInCurrentCell = len(str(cell).split('\n'))
                # See if the no of lines in this cell exceeds those of the previous cells in this row
                if linesInCurrentCell > maxLinesCurrentRow:
                    maxLinesCurrentRow = linesInCurrentCell
            # Update the tableData line count
            noOfNewlinesInTableData += maxLinesCurrentRow
        # Utils.Message.addMessage("Current table has " + str(maxLinesCurrentRow) + " lines")

        # Calculate the no of pages required to show all the items (given the terminal size and no of lines of data)
        noOfPages = int(math.ceil(len(tableData) / maxLines))
        # noOfPages = int(math.ceil(noOfNewlinesInTableData / maxLines))
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
                Utils.Message.addMessage("ERR. UI.__renderEventsListTable. getRTPStreamEventList()")

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
                    Utils.Message.addMessage("UI.__renderEventsListTable: " + str(e))
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
                footer = ["","[<][>]page, [^][v]select stream, [r]exit\n"+\
                          "[c]opy to clipboard, [f]ilter off, [s]ave file"]
        else:
            title = "All events for stream " + str(syncSourceID) + " (" + str(friendlyName) + ")"
            footer = ["", "[<][>]page, [^][v] select stream, [r]exit \n" + \
                      "[c]opy to clipboard, [f]ilter on, [s]ave file"]

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
        # Disable existing getch thread
        self.enableGetch.clear()
        # Check to see that  getch to have been disabled
        self.getchIsDisabled.wait()
        # Wait for a key press
        ch = None
        # Endless loop until either a key is pressed or the self.renderDisplayThreadActive flag is cleared
        while ch == None or self.renderDisplayThreadActive == False:
            # Blocking call to self.__getch() with timeout
            ch = self.__getch()


    # If the Event Lists Table is currently displayed, this method will copy the events to the local clipboard
    # If that is not possible (if for instance, you are connected to a remote instance of isptext via SSH)
    # it will attempt to export the data to pastebin.com (a website that allows you to share text via a webpage)
    def __onCopyReportToClipboard(self):
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

            # Confirm that a valid stream exists
            if selectedRxOrResultsStream is not None:
                # Get a textual, formatted report for this stream
                streamReport = selectedRxOrResultsStream.generateReport(eventFilterList = self.filterListForDisplayedEvents)
                # Attempt to copy the report to the local clipboard
                try:
                    # Utils.displayTextUsingMore(streamReport)
                    pyperclip.copy(streamReport)
                    self.__renderMessageBox("Success!".center(30) + "\n\n" +\
                            "<Press a key to continue>".center(30),\
                            "Copy to Clipboard", textColour=Term.WHITE, bgColour=Term.GREEN)

                except Exception as e:
                    # pyperclip error messages typically have newline chars in them. This will mess up my message
                    # table! So need to strip them - reaplce \n chars with ,
                    modifiedErrorString = str(e).replace("\n", ", ")
                    Utils.Message.addMessage("DBUG: UI.__onCopyReportToClipboard (using less) " + modifiedErrorString)

                    # # Copy to clipboard failed. Paste to pastebin.com instead
                    # url = ""
                    # try:
                    #     url = Utils.pasteBin(streamReport, "isptest stream report for stream " +\
                    #                 str(self.selectedStreamID)).decode('utf-8')
                    # except Exception as e:
                    #     url = "Error pasting to pastebin:- \n" + str(e)
                    #
                    #
                    # # Display a message box with a URL or an error message
                    # self.__renderMessageBox("\nUnable to copy to the local clipboard.\n" +\
                    #         "\nThis is mostly likely because you are connected to a text-only\n" +\
                    #         "terminal (e.g via an SSH session?)\n" +\
                    #         "\nSending the report to pastebin.com instead. Please follow this URL:-\n" +\
                    #         "\n " + str(url).center(70) + "\n\n" +\
                    #         "<Press a key to continue>".center(70), \
                    #         "Copy to Clipboard Failed", textColour=Term.WHITE, bgColour=Term.RED)

                    # Copy to clipboard failed, attempt to launch 'less' viewer instead - only works on Linux/OSX
                    # Display a message box
                    os = Utils.getOperatingSystem()
                    if  os != "Windows":
                        # Only attempt to launch 'less' oif we're not running Windows
                        self.__renderMessageBox("\nUnable to copy to the local clipboard.\n" + \
                                                "\nThis is mostly likely because you are connected to a text-only\n" + \
                                                "terminal (e.g via an SSH session?)\n" + \
                                                "\nAttempting to open the report in 'less' instead.\n" + \
                                                 "\nWhen done, press 'q' to return to isptest\n" +\
                                                "TIP: When in less, press 'h' for help\n\n" +\
                                                "<Press a key to continue>".center(70), \
                                                "Copy to Clipboard Failed", textColour=Term.WHITE, bgColour=Term.RED)
                        try:
                            # Clear the screen
                            Term.clearScreen()
                            # Open 'less' as a subprocess (blocking)
                            Utils.displayTextUsingLess(streamReport)
                        except Exception as e:
                            Utils.Message.addMessage("ERR: UI.__onCopyReportToClipboard (using less) " + str(e))
                    else:
                        Utils.Message.addMessage("ERR: UI.__onCopyReportToClipboard (using less) . Wrong OS " + str(os))

    # This method will call the currently selected Receive (or TxResults writeReportToDisk() method
    # causing a report of the current stream to be saved to disk
    # Note, this option is only available if the Events Table is currently being displayed
    def __onSaveReportToDisk(self):
        if self.displayEventsTable == True:
            selectedRxOrResultsStream = None
            # Get a handle on the selected stream
            # Depending upon the mode, we'll have to retrieve it from the correct dictionary
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

            # Confirm that the stream has been found
            if selectedRxOrResultsStream is not None:
                # Get a default filename (excluding the path)
                defaultFilename = selectedRxOrResultsStream.createFilenameForReportExport(includePath=False)

                # Now create an input box prefilling with the initial filename created by createFilenameForReportExport()
                styleDefinition = Style.from_dict({
                    'dialog': 'bg:ansiblue',  # Screen background
                    'dialog frame.label': 'bg:ansiwhite ansired ',
                    'dialog.body': 'bg:ansiwhite ansiblack',
                    'dialog shadow': 'bg:ansiblack'})


                # Create a multi_input_dialog (i.e my modified version of prompt_toolkit.input_dialog()
                # This is because my version allows you to specify the default text in the user field
                # Keep displaying the dialog until the filename is validated/cancel

                filenameValidated = False
                dialogueTitle = 'Export stream report to file (stream ' + str(self.selectedStreamID) + ')'
                # Create a footer label containing the full os path of the save location
                footerText = "Current save folder:\n" + str(os.path.abspath(Registry.resultsSubfolder))
                while filenameValidated is False:
                    try:
                        enteredText = multi_input_dialog(
                        [['Please enter a filename', defaultFilename]],\
                                title=dialogueTitle,\
                                style=styleDefinition,
                                optionalFooterText=footerText).run()
                        if enteredText is None:
                            # If 'cancel' selected
                            break
                        else:
                            # Attempt to validate the filename. If it fails, an Exception will be raised
                            validate_filename(enteredText['Please enter a filename'])

                            # filename has been validated
                            filenameValidated = True
                            # Extract the filename from the dictionary
                            filename = enteredText['Please enter a filename']

                            # Create the path for the saved file
                            fullSavePath = Registry.resultsSubfolder + filename
                            # Invoke that stream's writeReportToDisk method
                            # Use the current display filter for events to determine which events are exported to the file
                            fileSavedStatus = selectedRxOrResultsStream.writeReportToDisk(fullSavePath,\
                                                                        exportFilterList=self.filterListForDisplayedEvents)
                            maxWidth = 70
                            if fileSavedStatus == True:
                                # Display a message box showing the successful save path + filname
                                # Query the OS for the the absolute file path (this will be displayed)

                                absoluteSavePath = textwrap.fill(str(os.path.abspath(fullSavePath)), width=maxWidth)
                                self.__renderMessageBox("File saved to:-".center(maxWidth + 3) + "\n" +\
                                                        str(absoluteSavePath).center(maxWidth + 3)+ "\n\n" + \
                                                        "<Press a key to continue>".center(maxWidth + 3), \
                                                        "File save Successful", textColour=Term.WHITE, bgColour=Term.GREEN)
                            else:
                                # Save failed, so show an error
                                errorMessage = textwrap.fill(str(fileSavedStatus), width=maxWidth)
                                self.__renderMessageBox("Error: Unable to save file:-".center(maxWidth + 3) + "\n" + \
                                                        str(errorMessage).center(maxWidth + 3) + "\n\n" + \
                                                        "<Press a key to continue>".center(maxWidth + 3), \
                                                        "File save error", textColour=Term.WHITE,
                                                        bgColour=Term.RED)

                    except ValidationError as e:
                        # Modify the dialogue table to show the erroneous chars
                        dialogueTitle = str(e)





    # Cursor right
    def __onNavigateRight(self):
        if self.displayEventsTable is False and self.displayTraceRouteTable is False and self.displayHelpTable is False:
            # Inhibit, if Events Table, Traceroute or help tables are currently being displayed
            self.selectedView += 1
            # Prevent an 'out of range' view being selected
            if self.selectedView > (len(self.views) - 1):
                self.selectedView = len(self.views) - 1

        # Used to increment to the display page of the Events table
        # Note, this has to be bounds-checked in the table display code
        self.tablePageNo += 1

    # Cursor left
    def __onNavigateLeft(self):
        # Inhibit, if Events Table, Traceroute or help tables are currently being displayed
        if self.displayEventsTable is False and self.displayTraceRouteTable is False and self.displayHelpTable is False:
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

    # 'l' pressed
    def __onEnterFriendlyName(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        elif type(self.selectedStream) == RtpGenerator or type(self.selectedStream) == RtpReceiveStream:
            # We're either in TRANSIT mode vieing the TX Stream pane, or in RECEIVE mode
            styleDefinition = Style.from_dict({
                'dialog': 'bg:ansiblue',        # Screen background
                'dialog frame.label': 'bg:ansiwhite ansired ',
                'dialog.body': 'bg:ansiwhite ansiblack',
                'dialog shadow': 'bg:ansiblack'})
            # Now wait for confirtmation that __keysPressedThread is definitely disabled
            self.getchIsDisabled.wait()
            text = input_dialog(
                title='Enter friendly name',
                text='Please enter friendly name for stream ' + str(self.selectedStreamID) + ':',
                style=styleDefinition).run()
            if text is not None:
                # Now pass the new name to the correct method (based on the currently selected stream type)
                if type(self.selectedStream) == RtpReceiveStream:
                    # We must be in RECEIVER mode,
                    # If this stream originates from an instance of isptest, transmit the name change request back to
                    # transmitter and this will be picked up by the Receiver via the isptestheader
                    # Or else, if the stream is originating from another source (eg an NTT), directly modify the
                    # friendly name field in the RtpReceiveStream object
                    if self.selectedStream.getRtpStreamStatsByKey("stream_transmitterVersion") > 0:
                        # This stream originated from an isptest transmitter so need to remotely set it via a control msg
                        self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txname",
                                                                "name": text})
                    else:
                        # This stream is from an unknown source, set it directly using the object setter method
                        self.selectedStream.setFriendlyName(text)

                elif type(self.selectedStream) == RtpGenerator:
                    # We must be in TRANSMIT mode, currently viewing the transmit pane
                    # Send a local control message
                    self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Transmitter" + str(self.pid),
                                                                 "type": "txname",
                                                                "name": text})


    # This method is called if a previously expired stream (that is still listed in
    # self.rtpTxStreamsDict{} is requested to be restarted
    def __recreateExpiredStream(self, RtpGeneratorToBeResurrected):
        # Attempt to get the parameters of the dead stream
        try:
            # Attempt to get the parameters of the dead stream
            stats = RtpGeneratorToBeResurrected.getRtpStreamStats()
            # Remove the expired stream from self.rtpTxStreamsDict
            Utils.Message.addMessage("UI.__recreateExpiredStream() Removing stream " + str(stats['Sync Source ID']))
            RtpGeneratorToBeResurrected.killStream()
            time.sleep(1)
            # Create new RtpStream based on the parameters of the old stream
            # Confirm that the stream has been succesfully deleted by checking whether there already exists
            # a key stats['Sync Source ID'] in self.rtpTxStreamsDict

            try:
                # If the RtpGenerator object still exists in the rtpTxStreamsDict, the killStream() must have failed
                if stats['Sync Source ID'] in self.rtpTxStreamsDict:
                    Utils.Message.addMessage("ERR: UI.__recreateExpiredStream() Expired stream" +
                                       str(stats['Sync Source ID']) + " still exists, can't replace")
                else:
                    # It has been removed, so add the new stream (a copy of the old, expired stream)
                    RtpGenerator(stats['Dest IP'], stats['Dest Port'], stats['Tx Rate'], stats['Packet size'],
                                 stats['Sync Source ID'], 3600, \
                                 self.rtpTxStreamsDict, self.rtpTxStreamsDictMutex, \
                                 self.rtpTxStreamResultsDict, self.rtpTxStreamResultsDictMutex, uiInstance=self,
                                 friendlyName=stats['Friendly Name'], UDP_SRC_PORT=stats['Tx Source Port'])
            except Exception as e:
                Utils.Message.addMessage("ERR: UI.__recreateExpiredStream() inner " + str(e))
        except Exception as e:
            Utils.Message.addMessage("ERR: UI.__recreateExpiredStream() outer " + str(e))


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
                timeToLive = Registry.defaultTxStreamTimeToLive_sec
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
                                        ["Transmit bitrate (append K for Kbps or M for Mbps (minimum: " +\
                                            six.text_type(Utils.bToMb(Registry.minimumPermittedTXRate_bps)) + "bps)",\
                                            six.text_type(txRate)],
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

                # Simple fucntion to parse a number-letter suffix (k or m) and return the actual value
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
                            # Unknown suffix
                            return None
                    except Exception as e:
                        return None

                # newTxStreamParametersDict = multi_input_dialog(dialogUserFieldsList, title='Enter parameters for new transmit stream', style=styleDefinition)

                # Default title for the user dialogue
                title = 'Enter parameters for new transmit stream'

                # Keep displaying the dialogue until either ALL the input fields have been validated OR
                # 'Cancel' was selected
                while allFieldsValidatedFlag is False:
                    try:
                        # Now wait for confirtmation that __keysPressedThread is definitely disabled
                        # (otherwise my getch() would interfere with prompt_toolkits' getch())
                        self.getchIsDisabled.wait()
                        # Display the user dialogue
                        Utils.Message.addMessage("DBUG:UI.__onAddTxStream() Display multi_input_dialog")
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
                            # Get the minimum allowed value from Registry
                            txRate_bps = validators.integer(parseSuffix(
                                newTxStreamParametersDict["Transmit bitrate (append K for Kbps or M for Mbps (minimum: " +\
                                            six.text_type(Utils.bToMb(Registry.minimumPermittedTXRate_bps)) + "bps)"]),
                                minimum=Registry.minimumPermittedTXRate_bps)

                        except Exception as e:
                            title = 'ERROR: TRANSMIT BITRATE SPECIFIER - Use "m" for mbps or "k" for kbps ' + str(e)
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
                                                self.rtpTxStreamResultsDict, self.rtpTxStreamResultsDictMutex, uiInstance=self,\
                                                friendlyName=friendlyName, UDP_SRC_PORT=sourcePort)

                    Utils.Message.addMessage("[a] Added new " + str(Utils.bToMb(txRate_bps)) + "bps stream with id " + str(syncSourceID))
                # Force redraw
                redrawScreen = True
            else:
                # Note. This code should never be reachable because it shouldn't be possible to start in TRANSMIT mode
                # without ever having specified an initial stream
                Utils.Message.addMessage("ERR: No previous Tx stream stats to copy from. New stream not added")

    # 'd' -  Delete selected stream
    def __onDeleteStream(self):
        # Delete selected stream (selected table row)

        # Confirm that the dataset associated with this view actually has some data in it
        if self.selectedStream != None:
            try:

                Utils.Message.addMessage(
                    "INFO: streamToDelete: " + str(self.selectedStreamID) + " of type " + str(type(self.selectedStream)))

                # Confirm that this operation is allowed on  the current stream type
                if type(self.selectedStream) == RtpStreamResults:
                    # We must be in TRANSMIT mode, currently viewing one of the results panes
                    #  - you can't Put up an info message
                    Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

                # Now determine the type of stream (RtpGenerator (tx) or RtpStream (rx) )
                elif type(self.selectedStream) == RtpGenerator:
                    # It is a generator object
                    Utils.Message.addMessage("[d] Deleting Tx Stream: " + str(self.selectedStreamID))
                    # Instruct the RtpGenerator object to die (and it's associated corrseponding RtpStreamResults, if it exists)
                    self.selectedStream.killStream()
                    # Additionally, remove the corrseponding RtpStreamResults object for this stream


                elif type(self.selectedStream) == RtpReceiveStream:
                    # It is an RtpReceiveStream (receiver) object
                    Utils.Message.addMessage("[d] Deleting Rx Stream: " + str(self.selectedStreamID))
                    # Safely shutdown the RtpStream object itself
                    self.selectedStream.killStream()


            except Exception as e:
                Utils.Message.addMessage(
                    "ERR: __displayThread. [d] Delete Stream request failed: " + str(self.selectedStreamID) +
                    ", " + str(e))


    # '4' pressed
    def __onIncreaseTxRate(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Construct the control message:-
        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Transmitter" + str(self.pid),
                                                                 "type": "txbps_inc"})

        # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txbps_inc"})

    # '3' pressed
    def __onDecreaseTxRate(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Transmitter" + str(self.pid),
                                                                 "type": "txbps_dec"})
        # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txbps_dec"})

    # '6'
    def __onIncreaseTimeToLive(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                             "source": "Transmitter" + str(self.pid),
                                                             "type": "txttl_inc"})
            # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                             "source": "Receiver" + str(self.pid),
                                                             "type": "txttl_inc"})

    # '5'
    def __onDecreaseTimeToLive(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Transmitter" + str(self.pid),
                                                                 "type": "txttl_dec"})
            # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txttl_dec"})

    # 'b'
    def __onEnableBurstMode(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                   "source": "Transmitter" + str(self.pid),
                                                   "type": "txburst"})
            # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txburst"})


    # '2'
    def __onIncreasePayloadSize(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                   "source": "Transmitter" + str(self.pid),
                                                   "type": "txpayload_inc"})
            # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txpayload_inc"})

    # '1'
    def __onDecreasePayloadSize(self):
        # Confirm that this operation is allowed on  the current stream type
        if type(self.selectedStream) == RtpStreamResults:
            # We must be in TRANSMIT mode, currently viewing one of the results panes
            #  - you can't Put up an info message
            Utils.Message.addMessage("**HINT: Use 'TX Streams' pane to modify transmit parameters **")

        # Confirm that the selected stream is a generator object
        elif type(self.selectedStream) == RtpGenerator:
            self.selectedStream.addControlMessage({"syncSourceID": self.selectedStreamID,
                                                   "source": "Transmitter" + str(self.pid),
                                                   "type": "txpayload_dec"})
            # Otherwise send a message to the remote end
        elif type(self.selectedStream) == RtpReceiveStream:
            self.selectedStream.sendControlMessageToTransmitter({"syncSourceID": self.selectedStreamID,
                                                                 "source": "Receiver" + str(self.pid),
                                                                 "type": "txpayload_dec"})

    # Deprecated
    def __onIncrementSyncSourceID(self):
        self.__modifySyncSourceID(1)

    # Deprecated
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
            Utils.Message.addMessage(
                " Stream " + str(self.selectedStreamID) + " sync source id changed to " + str(currentSyncSourceID))



    # 'e'
    def __onToggleErrorMessages(self):
        if self.showErrorsFlag == False:
            # Set flag to true
            self.showErrorsFlag = True
            # Force a change of Message verbosity level to show errors
            Utils.Message.setVerbosity(1)
            Utils.Message.addMessage("[e] Error messages on")
        else:
            # Set flag to false
            self.showErrorsFlag = False
            # Force a change of Message verbosity back to intial setting
            Utils.Message.setVerbosity(self.intialVerbosityLevel)
            Utils.Message.addMessage("[e] Reverting to initial verbosity level")

    # 'z'
    def __onTogglePacketGenerationOnOff(self):
        # Confirm special features enabled and selected stream is an RtpGenerator
        if self.specialFeaturesModeFlag == True and type(self.selectedStream) == RtpGenerator:
            # Get current transit status and toggle accordingly
            if self.selectedStream.getEnableStreamStatus():
                # If currently enabled, disable it
                self.selectedStream.disableStream()
                Utils.Message.addMessage("[z] Stream " + str(self.selectedStreamID) + " packet generation disabled")
            else:
                # otherwise, enable it
                self.selectedStream.enableStream()
                Utils.Message.addMessage("[z] Stream " + str(self.selectedStreamID) + " packet generation enabled")


    # 'x'
    def __onToggleJitterSimulationOnOff(self):
        if self.specialFeaturesModeFlag == True and type(self.selectedStream) == RtpGenerator:
            if self.selectedStream.getJitterStatus():
                # if jitter simulation currently enabled, disable it
                self.selectedStream.disableJitter()
                Utils.Message.addMessage("[x] Stream " + str(self.selectedStreamID) + " jitter simulation disabled")
            else:
                self.selectedStream.enableJitter()
                Utils.Message.addMessage("[x] Stream " + str(self.selectedStreamID) + " jitter simulation enabled")

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
            Utils.Message.addMessage(
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
            Utils.Message.addMessage("[v] Stream " + str(self.selectedStreamID) + " simulate major packet loss (" + str(packetsToLose) +\
                               " packets)")

    # 't' - display the About dialogue
    def __onAboutDialogue(self):
        # NOTE: This is a blocking method
        maxWidth = 55
        tableContents = ("BBC IBEOO Team ISP Analyser v" + Registry.version).center(maxWidth, " ") + \
                        "\n\n" + "(c) James Turner 2020".center(maxWidth, " ") + \
                        "\n" + "With special thanks to Gary Podmore".center(maxWidth, " ") +\
                        "\n\n" + "<tl;dr> A UDP based packet loss and jitter".center(maxWidth, " ") + \
                        "\n" + " measurement tool supporting multiple tx/rx streams".center(maxWidth, " ") + \
                        "\n" + "  and event logging".center(maxWidth, " ") + \
                        "\n\n\n" + "Comments/feedback to: james.c.turner@bbc.co.uk".center(maxWidth, " ") + \
                        "\n See https://confluence.dev.bbc.co.uk/x/ioKKD for support" + \
                        "\n\n\n\n" + \
                        "Press the [any] key to continue".center(maxWidth, " ")

        # Render the message in a pop-up box
        self.__renderMessageBox(tableContents, "About")

    # Show a help page
    def __onShowHelpTable(self):
        # Toggle the display of the help pages
        if self.displayHelpTable:
            self.displayHelpTable = False
        else:
            self.displayHelpTable = True
            self.displayTraceRouteTable = False
            self.displayEventsTable = False
            # Reset display page to 0 when initially displaying the table
            self.tablePageNo = 0

        # maxWidth = 55
        # tableContents = ("This will show help... ") + \
        #                 "\n\n...but in the mean time.." +\
        #                 "\n see https://confluence.dev.bbc.co.uk/x/ioKKD for support" + \
        #                 "\n\n\n\n" + \
        #                 "Press the [any] key to continue".center(maxWidth, " ")
        #
        # # Render the message in a pop-up box
        # self.__renderMessageBox(tableContents, "Help")

    # Renders the Help page table
    def __renderHelpTable(self):
        termW, termH = Term.getTerminalSize()
        # Calculate the maximum no. of lines that will fit within the table, given the terminal height
        maxLines = termH - 20
        # Calculate max width of the second table column given the current screen size
        maxWidth = 80 - 18
        if termW > 80:
            maxWidth = maxWidth + (termW - 80)

        # Display filenames of log files in the help table
        outputFileNames = [["",""],["Filenames",""]]
        outputFileNames.append(["results path ",
                                textwrap.fill(str(os.path.abspath((Registry.resultsSubfolder))), width=maxWidth)])
        if self.operationMode == "RECEIVE":
            outputFileNames.append(["event list ", Registry.receiverLogFilename + ".csv"])
            outputFileNames.append(["logfile ", Registry.messageLogFilenameRx])
        elif self.operationMode == "TRANSMIT":
            outputFileNames.append(["events ", Registry.transmitterLogFilename + ".csv"])
            outputFileNames.append(["logfile ", Registry.messageLogFilenameTx])

        # Create some debug information to append to the end of the help list
        debugInfo = [["",""],["Debug info",""]]
        debugInfo.append(["Process ID ", str(os.getpid())])
        if self.operationMode == "RECEIVE":
            # Display aggregate socket receive stats
            try:
                # # NOTE: These are all global vars declared in __receiveRtpThread NOW DEPRECATED.
                # SEE RtpPacketReceiver and UDPMessageSender objects for these counters instead
                # debugInfo.append(["\nReceiver ", ""])
                # debugInfo.append(["raw Rx'd ", str(rawPacketsReceivedByRxThreadCount)])   # Total Rx'd Raw packets
                # debugInfo.append(["raw ignored ", str(rawPacketsDiscardedByRxThreadCount)]) # Raw packets ignored
                # debugInfo.append(["raw decoded ", str(rawPacketsDecodedByRxThreadCount)])   # Raw packets with an rtp header
                # debugInfo.append(["udp Rx'd ", str(udpPacketsReceivedByRxThreadCount)])   # Total Rx'd UDP packets
                # debugInfo.append(["udp ignored ", str(udpPacketsDiscardedByRxThreadCount)])   # UDP packets ignored
                # debugInfo.append(["udp decoded ", str(udpPacketsDecodedByRxThreadCount)]) # UDP packets with an rtp header
                # # Note: These are global vars declared in __sendUDPThread
                # debugInfo.append(["udp tx ", str(sendUDPThreadTxPacketCounter)])
                # debugInfo.append(["udp Q ", str(sendUDPThreadMessageQueueSize)])
                pass
            except:
                pass

        if self.selectedStream is not None:
            # Get copy of latest stats
            stats = self.selectedStream.getRtpStreamStats()
            # Determine what type of stream this is, and display stats accordingly
            if type(self.selectedStream) == RtpGenerator:
                try:
                    # This will only work if the stream type is an RtpGenerator object
                    debugInfo.append(["\nTransmitter ", ""])
                    debugInfo.append(["sleep time ", str("%0.20f" %stats['Sleep Time mean']) + "S"])
                    debugInfo.append(["Tx period ", str("%0.10f" %stats['Tx period']) + "S"])
                    debugInfo.append(["Tx'd packets ", str(self.selectedStream.txCounter_packets)])
                    debugInfo.append(["Tx err ", str(self.selectedStream.txErrorCounter)])
                    debugInfo.append(["Rx error ",
                                      str(self.selectedStream.rtpStreamResultsReceiver.receiveDecodeErrorCounter)])
                    debugInfo.append(["traceroute\n function ", str(self.selectedStream.tracerouteFunctionInUse)])
                except Exception as e:
                    Utils.Message.addMessage("ERR:UI.__renderHelpTable() add debug information " + str(e))
            if type(self.selectedStream) == RtpReceiveStream:
                try:
                    # This will only work if the selected stream type is an RtpreceiveStream object
                    # Query the RtpReceiveStream receive Queue. If this no > 1 then it suggests that
                    # the receiver is struggling to empty the queue fast enough
                    debugInfo.append(["Tx'd packets ", str(stats["packet_counter_transmitted_total"])])
                    debugInfo.append(["Tx bps ", str(Utils.bToMb(stats["stream_transmitter_txRate_bps"]))])
                    debugInfo.append(["Rx Q size ", str(self.selectedStream.rtpStreamQueueCurrentSize)])
                    debugInfo.append(["Rx max Q  ", str(self.selectedStream.rtpStreamQueueMaxSize)])
                    debugInfo.append(["Rx Q in ", str(self.selectedStream.packetsAddedToRxQueueCount)])
                    debugInfo.append(["Rx Q out ", str(self.selectedStream.packetCounterReceivedTotal)])
                except:
                    pass
        try:
            # Get list of running threads
            runningThreads = Utils.listCurrentThreads(asList=True)
            # runningThreads = ["cake"]
            # Now format the running threads list (by adding a column to each list event, in order to fit the help table)
            if len(runningThreads) > 0:
                debugInfo.append(["Threads..", str(len(runningThreads))])
                for thread in runningThreads:
                     debugInfo.append(["",thread])
        except Exception as e:
            Utils.Message.addMessage("ERR:UI.__renderHelpTable() add debug information " + str(e))

        # Get help table contents from Registry
        # append the two lists to create a single list
        tableContents = Registry.helpTableContents + outputFileNames + debugInfo
        # Now actually display the paged table list
        title = "Help"
        footer = ["", "[<][>]page, [h]exit"]
        self.__renderPagedList(self.tablePageNo, title, ["Key".ljust(5), "Function".ljust(50)], tableContents,
                               footerRow=footer,
                               pageNoDisplayInFooterRow=True, reverseList=False, marginOffset=7)



    # Controls the display of the Traceroute dialogue
    def __onDisplayTraceroute(self):
        # Toggle the display of the traceroute table by toggling the display flag
        if self.displayTraceRouteTable:
            self.displayTraceRouteTable = False
        else:
            self.displayTraceRouteTable = True
            self.displayEventsTable = False
            self.displayHelpTable = False
            # Reset display page to 0 when initially displaying the table
            self.tablePageNo = 0


    # Renders the Traceroute dialogue
    def __renderTracerouteTable(self):
        termW, termH = Term.getTerminalSize()
        # Calculate the maximum no. of lines that will fit within the table, given the terminal height
        # maxLines = termH - 20
        maxWidth = 40 + (termW - 80) # Used to automatically truncate the whois table column data
        if maxWidth < 10:
            maxWidth = 10

        # Get the traceroute hops list
        # depending upon whether we're in RECEIVE or TRANSMIT mode
        # The amount of lines displayed will adjust to the terminal height
        # Get a handle on the selected RxRtpStream or TxResults
        # Note, if we are in TRANSMIT mode, the selected stream should be the RtpGenerator dict.
        # hence we have to manually retrieve the appropriate stream object by using the self.selectedStreamID
        # and looking in the appropriate streams dictionary
        selectedStream = None

        if self.operationMode == 'RECEIVE' or self.operationMode == 'LOOPBACK':
            try:
                selectedStream = self.rtpRxStreamsDict[self.selectedStreamID]
            except:
                pass
        elif self.operationMode == 'TRANSMIT':
            try:
                selectedStream = self.rtpTxStreamsDict[self.selectedStreamID]
            except:
                pass
        tracerouteHopsList = []

        friendlyName = ""
        syncSourceID = 0
        if selectedStream is not None:
            try:
                # Get tracerouteHopsList from selected stream
                tracerouteHopsList = selectedStream.getTraceRouteHopsList()
                # Get friendly name of the selected stream and strip off the trailing whitespace (if any)
                friendlyName = str(selectedStream.getRtpStreamStatsByKey("stream_friendly_name")).rstrip()
                syncSourceID = str(selectedStream.getRtpStreamStatsByKey("stream_syncSource"))
            except Exception as e:
                Utils.Message.addMessage("ERR: UI.__onShowTracerouteDialogue(). getTraceRouteHopsList() " + str(e))
            # Create a list of tuples containing the index no and the IP address
            tableContents = []
            if len(tracerouteHopsList) > 0:
                tableRow = []
                whoisNetName = ""
                hopAddr = ""
                for hopNo in range(len(tracerouteHopsList)):
                    # Construct a string containing the IP address octets
                    try:
                        # This will fail if the tracerouteHopsList hop hasn't been received in the carousel yet
                        # If so, the hopAddr entry in tracerouteHopsList will still be 'None'
                        hopAddr = str(tracerouteHopsList[hopNo][0]) + "." + \
                                  str(tracerouteHopsList[hopNo][1]) + "." + \
                                  str(tracerouteHopsList[hopNo][2]) + "." + \
                                  str(tracerouteHopsList[hopNo][3])
                        # Now query the isptest whois cache for the address
                        whoisResult = Utils.WhoisResolver.queryWhoisCache(hopAddr)
                        if whoisResult is not None:
                            whoisNetName = " " + whoisResult[0]['asn_description']
                            # Truncate the string (if too long to fit on the table)
                            whoisNetName = (whoisNetName[:maxWidth] + '..') if len(whoisNetName) > maxWidth else whoisNetName
                    except:
                        hopAddr = "Waiting...."

                    # Create a table row containing the hop no and ip address of the hop
                    tableRow=[str(hopNo + 1), hopAddr, whoisNetName]
                    # Clear whoisNetName ready for next line
                    whoisNetName = ""
                    # Append the table row tuple to the tableContents[] list
                    tableContents.append(tableRow)
                    # Clear the tableRow list ready for next time around the loop
                    tableRow = []
            else:
                tableContents.append(["", "", "No traceroute data to display yet. Please wait".ljust(maxWidth)])
            # Now actually display the paged table list
            title = "UDP Traceroute for stream " + str(syncSourceID) + " (" + str(friendlyName) + ") " +\
                    str(len(tracerouteHopsList)) + " hops"
            footer = ["", "", "[<][>]page, [^][v] select stream, [t]exit\nTo save/export, go to [report] page"]
            self.__renderPagedList(self.tablePageNo, title, ["Hop".ljust(5), "Address".ljust(15), "Whois".ljust(maxWidth)], tableContents,
                                   footerRow=footer,
                                   pageNoDisplayInFooterRow=True, reverseList=False, marginOffset=7)

    def __onDisplayEvents(self):
        # Toggle display of Events list dialogue
        if self.displayEventsTable == False:
            self.displayEventsTable = True
            self.displayTraceRouteTable = False
            self.displayHelpTable = False
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
                Utils.Message.addMessage("DBUG: Ctrl-C Pressed")

                # For Linux/OSX - Kill self (Windows will detect the SIGINT in the signalHandler itself
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
            # 'l' Set friendly name (label)
            elif self.keyPressed == ord('l'):
                self.__onEnterFriendlyName()
            # 'n' Add TX stream
            elif self.keyPressed == ord('n'):
                self.__onAddTxStream()
            # 'd' Delete stream
            elif self.keyPressed == ord('d'):
                self.__onDeleteStream()
            # 'a' About dialogue
            elif self.keyPressed == ord('a'):
                self.__onAboutDialogue()
            # '4' Increase tx rate of selected stream
            elif self.keyPressed == ord('4'):
                self.__onIncreaseTxRate()
            # '3' Decrease tx rate of selected stream
            elif self.keyPressed == ord('3'):
                self.__onDecreaseTxRate()
            # '6' Increase Tx Stream Time to Live
            elif self.keyPressed == ord('6'):
                self.__onIncreaseTimeToLive()
            # '5' Decrease Tx Stream Time to Live
            elif self.keyPressed == ord('5'):
                self.__onDecreaseTimeToLive()
            # '2' Increase payload size
            elif self.keyPressed == ord('2'):
                self.__onIncreasePayloadSize()
            # '1' Decrease payload size
            elif self.keyPressed == ord('1'):
                self.__onDecreasePayloadSize()
            # # 'p' Increment sync source ID of stream
            # elif self.keyPressed == ord('p'):
            #     self.__onIncrementSyncSourceID()
            # # 'o' Decrement sync source ID of stream
            # elif self.keyPressed == ord('o'):
            #     self.__onDecrementSyncSourceID()
            # 'b' enable Burst Mode for the current tx stream
            elif self.keyPressed == ord('b'):
                self.__onEnableBurstMode()
            # 'e' Toggle error messages on/off
            elif self.keyPressed == ord('e'):
                self.__onToggleErrorMessages()
            # 'r' Display events list for selected stream (report)
            elif self.keyPressed == ord('r'):
                self.__onDisplayEvents()
            # 'f' Show only glitches on events list table (filter on/off)
            elif self.keyPressed == ord('f'):
                self.__onfilterEventsTable()
            # 'c' Copy report to clipboard
            elif self.keyPressed == ord('c'):
                self.__onCopyReportToClipboard()
            # 's' Save stream report to disk
            elif self.keyPressed == ord('s'):
                self.__onSaveReportToDisk()
            # 'h' Show help page
            elif self.keyPressed == ord('h'):
                self.__onShowHelpTable()
            # 't' Show traceroute
            elif self.keyPressed == ord('t'):
                self.__onDisplayTraceroute()

            # Special features
            # 'z' Toggle packet generation on/off for selected stream
            elif self.keyPressed == ord('7'):
                self.__onTogglePacketGenerationOnOff()
            # 'x' Toggle jitter simulation for selected stream
            elif self.keyPressed == ord('8'):
                self.__onToggleJitterSimulationOnOff()
            # 'c' Insert minor packet loss for selected stream
            elif self.keyPressed == ord('9'):
                self.__onInsertMinorPacketLoss()
            # 'v' Insert major packet loss for selected stream
            elif self.keyPressed == ord('0'):
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
            Utils.Message.addMessage(
                "INFO: __updateAvailableStreamsList() Added stream: " + str(x[0]) + ", " + str(type(x[1])))
        for streamID in deleteList:
            # Iterate over tuples in rtpStreamList[] searching for a match
            for index, stream in enumerate(rtpStreamList):
                if stream[0] == streamID:
                    # If stream found, delete that tuple from the list
                    Utils.Message.addMessage(
                        "INFO: __updateAvailableStreamsList() Removing stream " + str(stream[0]) + ", " + str(
                            type(stream[1])))
                    try:
                        rtpStreamList.pop(index)
                    except Exception as e:
                        Utils.Message.addMessage("ERR: __updateAvailableStreamsList: " + str(e))
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
                    Utils.Message.addMessage("ERR:__updateAvailableStreamsList() Object mismatch for streamID " + str(
                        stream[0]) + ". Repointing to correct object")
                    # Now re-point rtpStreamList to the correct version of that object
                    # by assigning the correct object to the entry in rtpStreamList[]
                    stream[1] = rtpStreamDict[stream[0]]
            except Exception as e:
                Utils.Message.addMessage("ERR:__updateAvailableStreamsList(), rtpStreamDictkey error for stream " + str(
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
        if value == None:
            value = " - "
        if key == "packet_data_received_1S_bytes":
            # We want this value in bps
            # Convert bytes to bits
            value *= 8
            value = Utils.bToMb(value)
            return value

        if key == "stream_syncSource" or key == 'Sync Source ID':
            value = str(value).rjust(10)

        # Render dates concisely
        if type(value) == datetime.datetime:
            value = value.strftime("%d/%m %H:%M:%S")
            return value

        if type(value) == datetime.timedelta:
            # Pass to (my) dtstrft() function to create a much shorter string
            return Utils.dtstrft(value)

        if key == "packet_data_received_total_bytes" or key == "Bytes transmitted":
            value = Utils.bToMb(value) + "B"
            return value

        if key == 'Tx Rate (actual)' or key == 'stream_transmitter_txRate_bps':
            value = Utils.bToMb(value)
            return value

        if key.find('percent') > 0:
            # Round % values to 2 dec place if less than 10.0
            if value < 10:
                value = "%0.2f" % value
            # Othewise round to 1 decimal place (so that the value fixes into a screen space 4 chars wide)
            else:
                value = "%0.1f" % value
            return value

        if key.find('_uS') > 0:
            # If > 1000uS, express as a mS
            if int(value) > 1000 or int(value) < -1000:
                value = str(math.ceil(value / 1000.0)) + "mS"
            else:
                # Append _uS to the value
                value = str(math.ceil(value)) + "uS"
            return value

        if key == 'Time to live' or key == 'stream_transmitter_TimeToLive_sec':
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
            Utils.Message.addMessage("Waiting for incoming RTP streams....")
        elif self.operationMode == 'TRANSMIT':
            Utils.Message.addMessage("Waiting for receiving end to make contact..... ")


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
                Utils.Message.addMessage("DBUG: UI.__renderDisplayThread self.enableGetch.clear()")
                self.enableGetch.clear()
                # Now wait for UI.__keysPressedThreasd() to acknowledge the self.enableGetch.clear() signal
                Utils.Message.addMessage("DBUG: UI.__renderDisplayThread: Waiting for UI.__keysPressedThread to acknowledge self.enableGetch.clear()")
                self.getchIsDisabled.wait()
                Utils.Message.addMessage("DBUG: UI.__renderDisplayThread:  self.getchIsDisabled acknowledged")

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

            # draw the messages table
            self.__drawMessageTable() # Should only take effect if there are any new messages/or self.redrawScreen is True



            # Check to see if Events List is to be overlaid?
            if self.displayEventsTable:
                # Confirm that self.selectedStream and self.selectedStreamID are up to date, before drawing the table
                # Without this update, the Events Table update lags behind the selected stream
                validateSelectedStream()
                self.__renderEventsListTable()

            # Check to see if Traceroute table is to be overlaid
            if self.displayTraceRouteTable:
                # Confirm that self.selectedStream and self.selectedStreamID are up to date, before drawing the table
                # Without this update, the traceroute table update lags behind the stream selection
                validateSelectedStream()
                self.__renderTracerouteTable()

            # Check to see if Help table is to be overlaid
            if self.displayHelpTable:
                self.__renderHelpTable()

            # Clear flag
            self.redrawScreen = False

            # Finally, Check to see if Fatal Error Message is to be displayed
            if self.displayFatalErrorDialogue:
                # clear flag
                self.displayFatalErrorDialogue = False

                # Put up error message (this is a blocking call)
                self.__renderMessageBox(self.fatalErrorDialogueMessageText, self.fatalErrorDialogueTitle, \
                                        textColour=Term.WHITE, bgColour=Term.RED)
                Utils.Message.addMessage("DBUG: __renderDisplayThread() displayFatalErrorDialogue..key pressed")



            # Now re-arm the getch thread
            self.enableGetch.set()

        Utils.Message.addMessage("UI.__renderDisplayThread ending *****")
        # Exit alternate screen
        Term.exitAlternateScreen()
        Term.clearScreen()
        print(Term.FG(Term.BLACK) + "UI.__renderDisplayThread ended")


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
                Utils.Message.addMessage(
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
                # Set a revertive to show that getch is enabled
                self.getchIsDisabled.clear()
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
                    # Set a revertive to show that ____keysPressedThread (i.e getch) has been disabled
                    # Utils.Message.addMessage("DBUG: UI.__keysPressedThread: getchIsDisabled.set() ")
                    self.getchIsDisabled.set()
            # If getch has been disabled, set a revertive to show other parts of the program it has been acknowledged
            if self.enableGetch.is_set() is False:
                # Set a revertive to show that ____keysPressedThread (i.e getch) has been disabled
                # Utils.Message.addMessage("DBUG: UI.__keysPressedThread: getchIsDisabled.set() ")
                self.getchIsDisabled.set()

        Utils.Message.addMessage("DBUG: UI.__keysPressedThread ended")

def __diskLoggerThread(operationMode, rtpStreamsDict, rtpStreamsDictMutex, shutdownFlag):
    # Autonomous thread to iterate over rtpStreamsDict and poll RtpStream eventLists for new events
    # and write them  to disk
    Utils.Message.addMessage("INFO: diskLoggerThread starting")
    filename = ""
    # Create the full filename including path depending upon opersation mode (excluding file extension eg. csv/.json)
    if operationMode == 'RECEIVE':
        # prefix = "receiver_report_"
        filename = sanitize_filepath(Registry.resultsSubfolder + Registry.receiverLogFilename)
    else:
        filename = sanitize_filepath(Registry.resultsSubfolder + Registry.transmitterLogFilename)

    lastWrittenEventNoDict = {}  # Dictionary to hold the last written event no for each stream
    latestEvents = []
    # Create versions of filename with the desired extensions
    filename_csv = filename + ".csv"
    filename_json = filename + ".json"

    # Function to monitor the existing log file size to if they've reached the threshold. If so, rename them
    # to a new file with a date added to the filename. The file extension will be preserved
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
                    Utils.Message.addMessage("Auto archived " + file)
            except Exception as e:
                Utils.Message.addMessage("ERR: __diskloggerThread.archiveLogs() " + str(e))


    # This function checks tp see if fileToCreate already exists. if it doesn't, it will create the file
    # along with a header at the top containing the program version and the current time
    def createLogFile(fileToCreate, headerTextPrefix):
        if not os.path.isfile(fileToCreate):
            # File doesn't exist yet, so create it
            try:
                # Open the file for writing
                fh = open(fileToCreate, "w+")
                fh.write(headerTextPrefix + " created by isptest v" + str(Registry.version) + \
                               ". Created at: " + datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S") + \
                               "\r\n-------------------------------------------------------------------------\n")
                fh.close()
            except Exception as e:
                Utils.Message.addMessage("ERR: __diskloggerThread.createLogFile() " + fileToCreate + ", " + str(e))

    # Sit in an infinite loop looking for new events (on all streams) and appending them to the log file(s)
    # Create file handles for the csv and json files
    file_csv = None
    file_json = None
    while True:
        # Check status of shutdownFlag
        if shutdownFlag.is_set():
            # If down, break out of the endless while loop
            break
        # Check to see if the existing log files (if they exist) are below the max size threshold
        archiveLogs(filename_csv, Registry.maximumLogFileSize_bytes)
        archiveLogs(filename_json, Registry.maximumLogFileSize_bytes)
        # Create a file and write a header (if necessary)
        # For the CSV file
        createLogFile(filename_csv, "Event summary")
        # For the Json file
        createLogFile(filename_json, "Event Log json file")

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

                        # Determine the last event no for this stream written to disk
                        lastWrittenEventNo = lastWrittenEventNoDict[currentRtpStream[0]]
                        # Determine the latest event no present in the allEvents list
                        latestEventNo = allEvents[-1].eventNo

                        # Check to see if the eventsList has been reset in the mean time. This could happen if the
                        # Receiver resets its stats/deletes a receive stream. In which case the event no's would restart
                        if latestEventNo < lastWrittenEventNo:
                            Utils.Message.addMessage("DBUG:__diskLoggerThread()Stats/Events for stream " +\
                                                     str(currentRtpStream[0]) + " reset by Receiver")
                            # If so, we'll need to re-add all the events from the events list
                            newEvents = len(allEvents)

                        else:
                            # This is the default case, where the most recent events in allEvents are likely to have
                            # not been written to disk yet
                            # Calculate how many new (i.e not yet written to disk) events there in are in this
                            # RtpStream object
                            newEvents = latestEventNo - lastWrittenEventNo

                        if newEvents > 0:
                            # There are outstanding events to be written
                            # Slice the latest portion of the allEvents list into a sub list
                            latestEvents = allEvents[(newEvents * -1):]
                except Exception as e:
                    Utils.Message.addMessage("DBUG: __diskLoggerThread - determining new events" + str(e))

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
                        Utils.Message.addMessage("DBUG: __diskLoggerThread - appending to file" + str(e) +\
                                                 " len(latestEvents) " + str(len(latestEvents)) +\
                                                ", lastWrittenEventNo " + str(lastWrittenEventNo) +\
                                                 ", " + str(latestEvents))
                        Utils.Message.addMessage("ERR:__diskLoggerThread() Possibly corrupted event. Skipping event " +\
                                                 str(lastWrittenEventNoDict[currentRtpStream[0]] + 1))
                        # inncrement lastWrittenEventNoDict for this stream id
                        lastWrittenEventNoDict[currentRtpStream[0]] += 1

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
            Utils.Message.addMessage("INFO: _diskLoggerThread: Deleting orphan stream " + str(stream) + " from lastWrittenEventNoDict")
            del lastWrittenEventNoDict[stream]
        time.sleep(1)

    # If execution gets here, the thread is ending....
    try:
        # check to see if object file_csv has a close() method (it won't if it hasn't been written to yet)
        if "close" in dir(file_csv):
            Utils.Message.addMessage("__diskloggerThread: Closing file " + str(filename_csv))
            file_csv.close()
        # check to see if object file_json has a close() method (it won't if it hasn't been written to yet)
        if "close" in dir(file_json):
            Utils.Message.addMessage("__diskloggerThread: Closing file " + str(filename_json))
            file_json.close()
    except Exception as e:
        Utils.Message.addMessage("ERR: __diskloggerThread. Error closing file " + str(e))


# Autonomous object to send UDP messages. It spawns a thread that will permanently monitor the txMessageQueue
# All other threads that need to send using the udpSocket can do so by putting items on the queue
# The thread relies upon a UDP socket having been previously created
# The messages themselves are a tuple of the form [byteString, destIPAddr, destport]
# The thread will monitor the status of shutdownFlag (type Threading.Event) and automatically shut down
# when this is detected to have been set
# This class fragments the message to be sent so that it will fit within self.MAX_UDP_TX_LENGTH
# Utils.fragmentString() is used to create seperate fragmnents in the form of a tuple which contains things like
# the no of fragments in the message, which fragment this is etc
# pickle is then used to actually send this tuple containing the fragment through the udp socket
class UDPMessageSender(object):

    def __init__(self, txMessageQueue, udpSocket, shutdownFlag):
        # Define some stats counters
        self.sendUDPThreadTxPacketCounter = 0
        self.sendUDPThreadMessageQueueSize = 0
        # Set max safe UDP tx size to 576 (based on this:-
        # https://www.corvil.com/kb/what-is-the-largest-safe-udp-packet-size-on-the-internet
        self.MAX_UDP_TX_LENGTH = 576
        self.txMessageQueue = txMessageQueue # of type Queue.SimpleQueue
        self.udpSocket = udpSocket
        self.shutdownFlag = shutdownFlag


        # Check that udp socket is a valid socket by retrieving the receive port no it is bound to
        # This will be used as the 'source port' for all udp packets sent by __udpTransmitterThread
        try:
            # Retrieve port no)
            self.UDP_RX_PORT = self.udpSocket.getsockname()[1]
            # If successful, socket is valid, so create the message transmitter thread
            udpTransmitterThread = threading.Thread(target=self.__udpTransmitterThread, args=())
            udpTransmitterThread.setName("__udpTransmitterThread("+ str(self.UDP_RX_PORT) + ")")
            udpTransmitterThread.start()
        except Exception as e:
            Utils.Message.addMessage("DBUG:__udpTransmitterThread(" + str(self.UDP_RX_PORT) + \
                                     ") Aborted. Invalid or no socket " + str(e))


    # autonomous thread to monitor self.txMessageQueue for new messages
    def __udpTransmitterThread(self):
        Utils.Message.addMessage("DBUG:__udpTransmitterThread("+ str(self.UDP_RX_PORT) + ") starting")
        while True:
            # Check status of shutdownFlag
            if self.shutdownFlag.is_set():
                # If down, break out of the endless while loop
                break
            # Poll the message queue to see if it contains any data to be sent
            # The txMessageQueue is a tuple of the form [byteString, destIPAddr, destport]

            # Get current size of self.txMessageQueue
            self.sendUDPThreadMessageQueueSize = self.txMessageQueue.qsize()
            try:
                # Wait for the message queue to be populated (with a 0.2 sec timeout)
                txData = self.txMessageQueue.get(timeout=0.2)
                txData_msg = txData[0]
                txData_ipAddr = txData[1]
                txData_udpPort = txData[2]

                # Utils.Message.addMessage("__udpTransmitterThread sending from udp:" + str(self.UDP_RX_PORT) + \
                #                          " to udp:" + str(txData_udpPort))
                # Now break the message up into a list of fragments so that it can be fitted into a udp frame
                fragmentedMessage = Utils.fragmentString(txData_msg, self.MAX_UDP_TX_LENGTH)

                # iterate over fragments and send
                if fragmentedMessage is not None and len(fragmentedMessage) > 0:
                    # iterate over fragments and send
                    for fragment in fragmentedMessage:
                        # Each fragment is actually a tuple, so itself needs pickling before it can be sent
                        # Pickle and send each fragment one at a time
                        # pickledFragment = pickle.dumps(fragment, protocol=2)
                        pickledFragment = pickle.dumps(fragment)
                        self.udpSocket.sendto(pickledFragment, (txData_ipAddr, txData_udpPort))
                        # Increment the counter
                        self.sendUDPThreadTxPacketCounter += 1
            # if Queue timed out without any data in it
            except Empty:
                pass
            except Exception as e:
                Utils.Message.addMessage("ERR:__udpTransmitterThread(" + str(self.UDP_RX_PORT) + \
                                         ").txMessageQueue.get() " + str(e))
        Utils.Message.addMessage("DBUG:__udpTransmitterThread(" + str(self.UDP_RX_PORT) + ") ending")


# A class that will spawn an rtp listener thread on a specified UDP port.
# Based on the OS, and sudo/admin rights it will decide whether to listen on a raw or udp socket
# As it detects an incoming rtp stream, it will spawn a new RtpReceiveStream object to capture and process the incoming stream
# It will also create a txMessageQueue which is used by a corresponding object (UdpMessageTransmitter) to send packets
# back to the transmitter using a shared UDP socket
# Currently the thread is controlled by the Threading.Event shutdownFlag
class RtpPacketReceiver(object):
    # Custom Exception for createUDPSocket()
    class CreateUDPSocketError(Exception):
        pass

    # Creates a UDP socket and binding
    def createUDPSocket(self, UDP_RX_IP, UDP_RX_PORT, timeout=1, txTTL=128):

        try:
            # create UDP socket
            udpSocket = socket.socket(socket.AF_INET,  # Internet
                                      socket.SOCK_DGRAM)  # UDP
            # Update socket with ttl value
            udpSocket.setsockopt(socket.SOL_IP, socket.IP_TTL, txTTL)
            udpSocket.bind((UDP_RX_IP, UDP_RX_PORT))
            return udpSocket
        except Exception as e:
            raise RtpPacketReceiver.CreateUDPSocketError(str(e))

    # Custom Exceptions for createRawSocket()
    class CreateRawSocketError(Exception):
        pass

    class RawSocketNotPossibleForOSXError(Exception):
        pass

    # Creates a raw socket and initialises it to suit the running OS
    def createRawSocket(self, UDP_RX_IP, UDP_RX_PORT):

        try:
            # Create Raw socket
            # The socket initialisation for Windows and Linux is different
            # OSX won't permit Raw sockets to receive UDP or TCP data at all
            # The aim of this function is to create a raw socket in parallel with the udp socket
            # For Linux and Windows

            # Determine what OS is running
            current_os = platform.system()
            if current_os == 'Windows':
                # Create  a raw socket. This *should* get copies of the data received by udpSocket but including the IP header
                rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
                rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
                rawSocket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                # Enable promiscuous mode
                rawSocket.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
                return rawSocket
            elif current_os == 'Linux':
                rawSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)  # Works on Linux
                rawSocket.bind((UDP_RX_IP, UDP_RX_PORT))
                return rawSocket

            elif current_os == 'Darwin':
                # The raw socket we want isn't possible for OSX, raise an Exception
                raise RtpPacketReceiver.RawSocketNotPossibleForOSXError("Not supported on OSX (Darwin)")

        except RtpPacketReceiver.RawSocketNotPossibleForOSXError as e:
            # Set rawSocket to None
            rawSocket = None
            # Pass the Exception outwards
            raise RtpPacketReceiver.RawSocketNotPossibleForOSXError(str(e))

        except Exception as e:
            # Socket creation failed. Raise an Exception
            # Set rawSocket to None
            rawSocket = None
            # print ("createRawSocket() " + str(e))
            raise RtpPacketReceiver.CreateRawSocketError(str(e))

    def parseRawPacket(self, _rawData):
        # Useful constants
        RTP_HEADER_SIZE = 12
        UDP_HEADER_SIZE = 8
        IP_HEADER_SIZE = 20
        try:
            # Check to see that the supplied bytearray is large enough to accommodate an RTP header
            rawBytesReceived = len(_rawData)
            if rawBytesReceived >= (IP_HEADER_SIZE + UDP_HEADER_SIZE + RTP_HEADER_SIZE):
                # Split off the various IP, UDP and RTP headers
                ipHeader = _rawData[:IP_HEADER_SIZE]
                udpHeader = _rawData[IP_HEADER_SIZE:(IP_HEADER_SIZE + UDP_HEADER_SIZE)]
                # Extract the Protocol field from the IP header to confirm that this contains a UDP packet.
                # Also extract the ttl from the IP header (since they're adjacent)
                rxTTL, ipProtocol = struct.unpack("!BB", ipHeader[8:10])
                if ipProtocol == 17: # Contains a UDP header
                    # Extract the src and dest port from the UDP header
                    srcUDPPort, destUDPPort = struct.unpack("!HH", udpHeader[0:4])
                    # Extract the rtp header
                    rtpHeader = _rawData[(IP_HEADER_SIZE + UDP_HEADER_SIZE): \
                                         (IP_HEADER_SIZE + UDP_HEADER_SIZE + RTP_HEADER_SIZE)]
                    # If there's any payload data, strip that off too.
                    if rawBytesReceived > (IP_HEADER_SIZE + UDP_HEADER_SIZE + RTP_HEADER_SIZE):
                        payload = _rawData[IP_HEADER_SIZE + UDP_HEADER_SIZE + RTP_HEADER_SIZE:]
                    else:
                        payload = None
                    return rtpHeader, payload, rxTTL, srcUDPPort, destUDPPort
                else:
                    # Utils.Message.addMessage("parseRawPacket() protocol is not UDP")
                    return None, None, None, None, None
            # Otherwise check to see if this packet is only large enough to accommodate a UDP header
            # Even if it doesn't contain an RTP header, we can still extract the rxTTL, srcUDPPort and  destUDPPort
            elif rawBytesReceived >= (IP_HEADER_SIZE + UDP_HEADER_SIZE):
                # Split off the various IP, UDP and RTP headers
                ipHeader = _rawData[:IP_HEADER_SIZE]
                udpHeader = _rawData[IP_HEADER_SIZE:(IP_HEADER_SIZE + UDP_HEADER_SIZE)]
                # Extract the Protocol field from the IP header to confirm that this contains a UDP packet.
                # Also extract the ttl from the IP header (since they're adjacent)
                rxTTL, ipProtocol = struct.unpack("!BB", ipHeader[8:10])
                if ipProtocol == 17:  # Contains a UDP header
                    # Extract the src and dest port from the UDP header
                    srcUDPPort, destUDPPort = struct.unpack("!HH", udpHeader[0:4])
                    # Utils.Message.addMessage("parseRawPacket() no rtp header or payload")
                    return None, None, rxTTL, srcUDPPort, destUDPPort
                else:
                    Utils.Message.addMessage("parseRawPacket() no udp header, too short for rtp ")
                    return None, None, None, None, None

            # Otherwise this packet doesn't contain a UDP packet
            else:
                # Utils.Message.addMessage("parseRawPacket() unrecognised payload")
                return None, None, None, None, None
        except Exception as e:
            # Utils.Message.addMessage("ERR: Exception within parseRawPacket () " + str(e))
            return None, None, None, None, None

    # Takes a udp packet and splits off the RTP header and payload
    def parseUDPPacket(self, _rawData):
        # Useful constants
        RTP_HEADER_SIZE = 12
        try:
            if len(_rawData) >= RTP_HEADER_SIZE:
                rtpHeader = _rawData[:RTP_HEADER_SIZE]
                if len(_rawData) > RTP_HEADER_SIZE:
                    payload = _rawData[RTP_HEADER_SIZE:]
                else:
                    payload = None
                return rtpHeader, payload
            else:
                return None, None
        except Exception as e:
            # Utils.Message.addMessage("ERR:parseUDPPacket() " + str(e))
            return None, None

    # Splits out the fields from the supplied rtp header
    def parseRTPHeader(self, _rtpHeader):
        # Useful constants
        RTP_HEADER_SIZE = 12
        try:
            if len(_rtpHeader) == RTP_HEADER_SIZE:
                version, type, seqNo, timestamp, syncSourceID = struct.unpack("!BBHLL", _rtpHeader)
                return version, type, seqNo, timestamp, syncSourceID
            else:
                return None, None, None, None, None
        except Exception as e:
            # Utils.Message.addMessage("ERR:parseRTPHeader() " + str(e))
            return None, None, None, None, None


    def __init__(self, rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,
                       UDP_RX_IP, UDP_RX_PORT, ISPTEST_HEADER_SIZE, glitchEventTriggerThreshold, uiInstance,
                       txMessageQueue):
        self.rtpRxStreamsDict = rtpRxStreamsDict
        self.rtpRxStreamsDictMutex = rtpRxStreamsDictMutex
        self.shutdownFlag = shutdownFlag
        self.UDP_RX_IP = UDP_RX_IP
        self.UDP_RX_PORT = UDP_RX_PORT
        self.ISPTEST_HEADER_SIZE = ISPTEST_HEADER_SIZE
        self.glitchEventTriggerThreshold = glitchEventTriggerThreshold
        self.uiInstance = uiInstance
        self.txMessageQueue = txMessageQueue

        # Create and initialise variables used for debugging -tracing lost packets
        self.rawPacketsReceivedByRxThreadCount = 0
        self.rawPacketsDiscardedByRxThreadCount = 0
        self.rawPacketsDecodedByRxThreadCount = 0
        self.udpPacketsReceivedByRxThreadCount = 0
        self.udpPacketsDecodedByRxThreadCount = 0
        self.udpPacketsDiscardedByRxThreadCount = 0

        # # This var indicates which of the two sockets has been selected (raw or UDP), to use as the data source
        # self.__receiveSocket = None
        # This (udp) socket is created within this object but is available to use by other objects via the getter method
        self._sharedUDPSocket = None

        # Create a thread to receive the RTP streams
        receiveRtpThread = threading.Thread(target=self.__rtpPacketReceiverThread, args=())
        receiveRtpThread.setName("__rtpPacketReceiverThread(" + str(self.UDP_RX_PORT) + ")")
        receiveRtpThread.start()

    # returns a udp socket to be used as a channel to send data back to the source
    def getSocket(self):
        return self._sharedUDPSocket

    # Main udp/rtp listener thread
    def __rtpPacketReceiverThread(self):

        # Create a dictionary to initially hold the sync source of a potential rx stream
        rtpRxStreamTempDict = {}

        # IP Receive socket placeholders
        udpSocket = None
        rawSocket = None
        receiveSocket = None # The actual socket picked to receive the incoming packets (raw is the first preference)

        # Constants
        RTP_HEADER_SIZE = 12
        UDP_HEADER_SIZE = 8
        IP_HEADER_SIZE = 20

        rawTimestamp = datetime.timedelta()
        udpTimestamp = datetime.timedelta()
        payload = bytearray()
        syncSourceID = None
        seqNo = None
        packetArrivedTimestamp = datetime.timedelta()
        srcAddress = ""
        srcPort = None
        payloadLength = 0
        rxTTL = None

        inhibitOSXPopupMessage = False  # Used to inhibit repeated showings of the same popup messages
        inhibitRawSocketCreationPopupMessage = False

        while True:
            # Create receive UDP socket and raw socket
            # The raw socket is so that the TTL value of the received packet can be read
            # In theory, there's no reason why I should need a seperate UDP socket, but I do. See below
            # See here: https://stackoverflow.com/questions/9969259/python-raw-socket-listening-for-udp-packets-only-half-of-the-packets-received

            try:
                # Create udp and raw sockets
                # The udp socket is used to receive the incoming udp packets. It is also used by the RtpReceiveStreams to
                # transmit results back to the transmitter
                # A RAW socket is also created in parallel with the udp port. This receives copies of the same packets
                # but also includes the IP header, which allows the TTL value to be read.
                # See here: for an explanation of why a single RAW socket can't be used:-
                # https://stackoverflow.com/questions/9969259/python-raw-socket-listening-for-udp-packets-only-half-of-the-packets-received
                #
                # Also, OSX won't allow UDP ports to be decoded using a raw socket = the OS strips them away before they]
                # See here:
                # https://stackoverflow.com/questions/6878603/strange-raw-socket-on-mac-os-x
                # reach the socket. The upshot is that getting TTL values from the incoming packets is not possible on OSX

                # Create udp socket
                udpSocket = self.createUDPSocket(self.UDP_RX_IP, self.UDP_RX_PORT)
                # update the shared UDP socket object
                # This is used as a pointer to the socket and will allow the other threads to make use of it
                self._sharedUDPSocket = udpSocket
                Utils.Message.addMessage("DBUG:Created udp socket " + str(udpSocket))
                # Create raw socket
                rawSocket = self.createRawSocket(self.UDP_RX_IP, self.UDP_RX_PORT)
                Utils.Message.addMessage("DBUG: Created raw socket " + str(rawSocket))
                # If execution makes it this far without an Exception being thrown, we can safely use the raw socket to receive
                receiveSocket = rawSocket

            except RtpPacketReceiver.CreateRawSocketError as e:
                # Couldn't create raw socket. Most likely because app wasn't run as sudo
                # Set the data source to be the UDP socket
                receiveSocket = udpSocket
                # Post a message
                Utils.Message.addMessage("ERR:CreateRawSocketError " + str(e))
                # Warn the user, but only once
                if inhibitRawSocketCreationPopupMessage is False:
                    # Now the message has been displayed, set the flag
                    inhibitRawSocketCreationPopupMessage = True
                    maxWidth = 70
                    errorText = textwrap.fill(str(e), width=maxWidth) + \
                                "\n\n" + "'raw' receive socket could not be created therefore ttl values of".center(
                        maxWidth) + \
                                "\n" + "the received rtp packets will not be decoded".center(maxWidth) + \
                                "\n" + "Note. isptest will run, but ttl value changes will not be detected".center(
                        maxWidth) + \
                                "\n" + "All other functionality will remain".center(maxWidth) + \
                                "\n" + "Hint: try running as 'sudo' or 'Administrator'".center(maxWidth) + \
                                "\n\n" + "<Press any key to continue>".center(maxWidth)

                    self.uiInstance.showErrorDialogue("Raw Socket creation error", errorText)


            except RtpPacketReceiver.RawSocketNotPossibleForOSXError as e:
                # OSX has been detected. Warn the user that ttl values won't be displayed
                # Set the data source to be the UDP socket
                receiveSocket = udpSocket
                # Post a message
                Utils.Message.addMessage("ERR:RawSocketNotPossibleForOSXError " + str(e))
                if inhibitOSXPopupMessage is False:
                    # Now the message has been displayed, set the flag
                    inhibitOSXPopupMessage = True
                    # Now signal to the user (via the UI object) that there is a problem, but only once
                    maxWidth = 70
                    errorText = "\n" + str("Mac OSX detected").center(maxWidth) + \
                                "\n" + "Note. isptest will run, but the ttl values of the received rtp".center(
                        maxWidth) + \
                                "\n" + "packets will not be decoded. This is due to restrictions within OSX".center(
                        maxWidth) + \
                                "\n" + "itself. ttl value changes will not be detected but all other".center(maxWidth) + \
                                "\n" + "functionality will remain".center(maxWidth) + \
                                "\n\n" + "<Press any key to continue>".center(maxWidth)

                    self.uiInstance.showErrorDialogue("OSX detected", errorText)


            # Catch fatal errors that will stop isptest from receiving packets
            # isptest can live without a raw socket (all that will be missing is the ttl detection),
            # but without a working udp port socket it can't receive anything
            except (RtpPacketReceiver.CreateUDPSocketError, Exception) as e:
                # Indicate no functioning receive socket
                receiveSocket = None
                Utils.Message.addMessage(
                    Term.FG(Term.RED) + "__receiveRtpThread(): Cannot listen on " + self.UDP_RX_IP + ":" + str(
                        self.UDP_RX_PORT) + ", " + str(e) + Term.FG(Term.RESET))
                Utils.Message.addMessage("DBUG:__receiveRtpThread(): " + str(e))
                # Display a message box with a URL or an error message

                # Now signal to the UI object that there is a problem
                maxWidth = 70
                Utils.Message.addMessage("DBUG:__receiveRtpThread(): calling UI.showFatalErrorDialogue()")
                errorText = textwrap.fill(str(e), width=maxWidth) + \
                            "\n\n" + str("This could be due to the UDP Listen port (" + str(self.UDP_RX_PORT) + ")").center(
                    maxWidth) + \
                            "\n" + "already in use (eg. by vlc, or another instance of isptest?)".center(maxWidth) + \
                            "\n" + "Or perhaps a non-existent listen address has been specified?".center(maxWidth) + \
                            "\n" + "You must exit this app and either restart it using a different port,".center(
                    maxWidth) + \
                            "\n" + "or else shut down the competing application first, and then restart".center(
                    maxWidth) + \
                            "\n\n" + "TIP: To query what's listening on ports already, run the following:".center(
                    maxWidth) + \
                            "\n" + "Linux: 'netstat -lnup'".center(maxWidth) + \
                            "\n" + "OSX: 'lsof -nP | grep UDP'".center(maxWidth) + \
                            "\n" + "Windows: 'netstat -an | find \"UDP\"'".center(maxWidth) + \
                            "\n\n" + "<Press any key to continue>".center(maxWidth)

                self.uiInstance.showErrorDialogue("Network Error", errorText)
                # Cause thread to end by breaking out of while loop
                break
            Utils.Message.addMessage("Receiving on socket " + str(receiveSocket))

            # Specify a timeout for select()
            selectTimeout = 1
            # Create a list of sockets that select() will monitor
            socketsToBePolled = [udpSocket]
            # If rawSocket was sucessfully created, add it to the list
            if rawSocket is not None:
                socketsToBePolled.append(rawSocket)

            # Endless UDP/IP receive loop.
            # Use select() to poll the OS to see if packets have arrived
            destUDPPort = 0
            while True:
                # Check status of shutdownFlag
                if self.shutdownFlag.is_set():
                    # If down, break out of the endless while loop
                    break

                # select() will return a list of sockets that are ready to have data read from them
                # recvfrom() returns two parameters, the src address:port (addr) and the actual data (data)
                # Note: Because rawSocket and udpSocket are bound to the same IP:port combination, they should
                # contain identical data
                try:
                    # Wait for data (blocking function call)

                    r, w, x = select.select(socketsToBePolled, [], [], selectTimeout)
                    if not r:
                        # select () timeout reached so returned list will be empty
                        # Utils.Message.addMessage("select() timeout")
                        pass
                    else:
                        # Attempt to get data from the raw socket first.
                        if rawSocket in r:
                            # The raw socket contains data to be read
                            rawData, rawAddr = rawSocket.recvfrom(4096)  # buffer size is 4096 bytes
                            rawTimestamp = datetime.datetime.now()
                        else:
                            # If no data to be read, clear the rawData and rawAddr lists
                            rawData = []
                            rawAddr = ("", 0)
                        # rawBytesReceived = len(rawData)

                        # Next, flush the corresponding UDP port binding (if it contains data, which it should)
                        if udpSocket in r:
                            udpSocketData, udpSocketAddr = udpSocket.recvfrom(4096)
                            udpTimestamp = datetime.datetime.now()
                        else:
                            # If no data to be read, clear the udpSocketData and udpSocketAddr lists
                            udpSocketData = []
                            udpSocketAddr = ("", 0)
                        # udpBytesReceived = len(udpSocketData)

                        # Now parse the received packet
                        if receiveSocket is rawSocket:
                            try:
                                # If the data has been rx'd via the raw socket, we have to extract the data as a raw packet
                                # Increment the counter
                                self.rawPacketsReceivedByRxThreadCount += 1
                                try:
                                    rtpHeader, payload, rxTTL, srcUDPPort, destUDPPort = self.parseRawPacket(rawData)
                                except Exception as e:
                                    Utils.Message.addMessage("ERR:parseRawPacket() " + str(e))
                                    rtpHeader = None
                                    payload = None
                                    rxTTL = None
                                    srcUDPPort = None
                                    destUDPPort = None
                                # Note: On Windows, the raw port is running in promiscuous mode. That means it will receive
                                # ALL incoming packets addressed to that interface.
                                # Therefore we need to check that this packet is for us, by comparing the udp dest port
                                # with what we're expecting to receive on
                                if destUDPPort == self.UDP_RX_PORT:
                                    # This UDP packet is addressed to us, so continue to process it

                                    if rtpHeader is not None:
                                        # Packet payload is large enough to contain an rtp header. but does it?
                                        try:
                                            version, type, seqNo, timestamp, syncSourceID = self.parseRTPHeader(rtpHeader)
                                        except Exception as e:
                                            Utils.Message.addMessage("ERR:parseRTPHeader() " + str(e))
                                            version = None
                                            type = None
                                            seqNo = None
                                            timestamp = None
                                            syncSourceID = None


                                        if syncSourceID is not None:
                                            # Increment the global counter
                                            self.rawPacketsDecodedByRxThreadCount += 1
                                            # Get the source address
                                            srcAddress = rawAddr[0]
                                            # Get the source port no
                                            srcPort = srcUDPPort
                                            # Store the packet arrival time
                                            packetArrivedTimestamp = rawTimestamp
                                    else:
                                        # packet ignored. Increment the counter
                                        self.rawPacketsDiscardedByRxThreadCount += 1
                            except Exception as e:
                                Utils.Message.addMessage("DBUG:parse rawSocket data " + str(e))

                        elif receiveSocket is udpSocket:
                            try:
                                # increment the counter
                                self.udpPacketsReceivedByRxThreadCount += 1
                                # If the data has been rx'd via the udp socket, only the rtp header + payload will be present
                                rtpHeader, payload = self.parseUDPPacket(udpSocketData)
                                if rtpHeader is not None:
                                    # Now parse the rtp header
                                    version, type, seqNo, timestamp, syncSourceID = self.parseRTPHeader(rtpHeader)
                                    if syncSourceID is not None:
                                        # Increment the global counter
                                        self.udpPacketsDecodedByRxThreadCount += 1
                                        # Get the source address
                                        srcAddress = udpSocketAddr[0]
                                        # Get the source port no
                                        srcPort = udpSocketAddr[1]
                                        # Store the packet arrival time
                                        packetArrivedTimestamp = udpTimestamp
                                else:
                                    # Increment the global counter
                                    self.udpPacketsDiscardedByRxThreadCount += 1
                            except Exception as e:
                                Utils.Message.addMessage("DBUG:parse udpSocket data " + str(e))

                    # Test to see if we have any new data (by testing the syncSourceID field)
                    if syncSourceID is not None:
                        # create bytestring to hold isptest header data
                        isptestHeaderData = b""
                        # Now process the payload (the bit after the rtp header)
                        try:
                            payloadLength = len(payload)
                            if payloadLength >= self.ISPTEST_HEADER_SIZE:
                                # Substring the isptest header part of the payload
                                isptestHeaderData = payload[:self.ISPTEST_HEADER_SIZE]
                        except Exception as e:
                            Utils.Message.addMessage("payloadLength = len(payload) " + str(e))
                            payloadLength = 0

                        # Calculate the udp payload length (rtp header plus data). This is to allow bitrate calculations
                        udpPayloadLength = payloadLength + RTP_HEADER_SIZE

                        # Finally, if we have a valid rtp packet with all meta data extracted, send it to an RtpReceiveStream
                        # Attempt to add the data to an existing rtpStream object keyed by the rtpSyncSourceIdentifier
                        # This will raise an Exception if the key doesn't yet exist in the dictionary
                        try:
                            # Add the the new rtp data object to the RtpReceiveStream
                            self.rtpRxStreamsDict[syncSourceID].addData( \
                                seqNo, udpPayloadLength, packetArrivedTimestamp, syncSourceID, isptestHeaderData, \
                                rxTTL, srcAddress, srcPort)

                        except:
                            # Test to see if the latest rtpSyncSourceIdentifier already exists as a key in tpRxStreamTempDict
                            # Attempt to add the latest rtpSyncSourceIdentifier to tpRxStreamTempDict
                            # This will fail if it doesn't already exist
                            try:
                                # If this stream does exist in the temporary list, append the latest (possible) data to it
                                # in the form of a list containing the last received seq no

                                rtpRxStreamTempDict[syncSourceID].append(seqNo)
                                # Utils.Message.addMessage(Fore.GREEN + "INFO: " + str(syncSourceID) +
                                #                    " exists in rtpRxStreamTempDict already, adding RtpData(seqNo=" + \
                                #                          str(seqNo) + ")")
                                ######NOW TEST CONTENTS of the list to see if this is a valid stream to be added
                                # For a stream to be considered valid, there has to be a minimum no of packets received
                                # with the same sync source ID. Also, the seq no of the most recent packet must be higher
                                # than the first packet received for this sync source ID.
                                # In this way we can test for a constant sync source ID field and an incrementing seq no
                                # Check to see how many packets with the same sync source ID have been received
                                if (len(rtpRxStreamTempDict[syncSourceID]) > Registry.receiveStreamAcceptThreshold):
                                    # Now check to see if the sequence numbers appear to have incremented by at least the
                                    # no of packets received with this sync source ID
                                    if (rtpRxStreamTempDict[syncSourceID][-1] - rtpRxStreamTempDict[syncSourceID][0]) == \
                                            (len(rtpRxStreamTempDict[syncSourceID]) - 1):

                                        Utils.Message.addMessage(Fore.GREEN + "Rtp stream " + str(syncSourceID) +
                                                                 " validated. Creating new RtpReceiveStream")
                                        # Create and add the new stream to the rtpRxStreamsDict
                                        newRtpStream = RtpReceiveStream(syncSourceID, srcAddress, srcPort, self.UDP_RX_IP, \
                                                                        self.UDP_RX_PORT, self.glitchEventTriggerThreshold,
                                                                        self.rtpRxStreamsDict, self.rtpRxStreamsDictMutex,
                                                                        self.txMessageQueue)
                                        # Add the most recent packet to the newly created stream
                                        newRtpStream.addData(seqNo, udpPayloadLength, packetArrivedTimestamp,
                                                             syncSourceID, isptestHeaderData, rxTTL, srcAddress,
                                                             srcPort)

                                    else:
                                        # The sequence numbers don't appear to have incremented
                                        Utils.Message.addMessage(Fore.RED + "Non-RTP packets received from " + \
                                                                 str(srcAddress) + ":" + str(srcPort) + \
                                                                 ", (" + str(udpPayloadLength) + " bytes)")
                                        # Now delete the entry from the temporary dict
                                        del (rtpRxStreamTempDict[syncSourceID])

                            except:
                                # If the stream doesn't exist as a key in either or rtpRxStreamsDict{} rtpRxStreamTempDict{},
                                # create an entry in the temporary dictionary using the sync Source ID field as a key
                                # The value is a list of (possible) rtpData objects' seq nos
                                # Utils.Message.addMessage(
                                #     Fore.RED + "INFO: Stream doesn't exist yet, adding to rtpRxStreamTempDict list: " + str(
                                #         syncSourceID))

                                rtpRxStreamTempDict[syncSourceID] = [seqNo]
                    # Reset syncSourceID to None. This will inhibit any more data being added until it is set once more
                    syncSourceID = None

                # Catch all other exceptions
                except Exception as e:
                    Utils.Message.addMessage(Term.WhiRed + "ERR: __main()udpSocket.recvfrom():" + self.UDP_RX_IP + ":" + \
                                             str(self.UDP_RX_PORT) + ", " + str(id(udpSocket)))
                    Utils.Message.addMessage("__main() recvfrom: " + str(e))

                    try:
                        # Close udp socket
                        udpSocket.close()
                        Utils.Message.addMessage("DBUG: main()__receiveRtpThread udpSocket closed")
                    except Exception as e:
                        Utils.Message.addMessage("ERR:main()__receiveRtpThread udpSocket.close() " + str(e))
                    try:
                        # Close raw socket
                        if rawSocket is not None:
                            rawSocket.close()
                            Utils.Message.addMessage("DBUG: main()__receiveRtpThread rawSocket closed")
                    except Exception as e:
                        Utils.Message.addMessage("ERR: main()__receiveRtpThread rawSocket.close() " + str(e))

                    # Now try to recreate the socket
                    # break out of this inner while loop to the outer while loop (where the socket is created)
                    break

                # Iterate over tpRxStreamTempDict to purge it of old, non-existant streams that never made it into rtpRxStreamTempDict
                # If an RTP packet with the matching sync source id doesn;t appear within nonExistentStreamTimout_seconds seconds,
                # the stream will be deleted from tpRxStreamTempDict{}
                nonExistentStreamTimout_seconds = 2

                # # Create temporary copy of the dict we want to delete keys from
                # tmpDict = rtpRxStreamTempDict.copy()
                # # Iterate over the copy of the dict
                # for key, value in tmpDict.items():
                #     # Test to see if the most recent packetArrivedTimestamp exceeds the elapsed time threshold. If so, remove it
                #     if (datetime.datetime.now() - value[-1][1]).total_seconds() \
                #                 > nonExistentStreamTimout_seconds:
                #         # Utils.Message.addMessage(
                #         #     "INFO: **Deleting non-rtp stream: " + str(key) + " from rtpRxStreamTempDict{}")
                #         del (rtpRxStreamTempDict[key])

                # Check length of rtpRxStreamTempDict. If it's too large, purge it
                # This is a bit of a blunt instrument because it means that any streams that were 'nearly validated' will
                # be thrown away. However, this is by the the lowest CPU cost means of preventing rtpRxStreamTempDict
                # growing and growing
                if len(rtpRxStreamTempDict) > 50:
                    # Utils.Message.addMessage("Purging rtpRxStreamTempDict")
                    rtpRxStreamTempDict = {}

            # Check status of shutdownFlag
            if self.shutdownFlag.is_set():
                # If down, break out of the endless while loop
                break

            # If program execution gets here, the udp socket must have been corrupted
            Utils.Message.addMessage(
                Term.WhiRed + "WARNING. Recreating receive socket. Glitches might not be genuine          ")

            time.sleep(1)

        try:
            # Close the udpSocket socket in
            udpSocket.close()
            Utils.Message.addMessage("DBUG: main()__receiveRtpThread udpSocket closed")
        except Exception as e:
            Utils.Message.addMessage("ERR: main()__receiveRtpThread udpSocket.close() " + str(e))

        try:
            # Close raw socket
            if rawSocket is not None:
                rawSocket.close()
                Utils.Message.addMessage("DBUG: main()__receiveRtpThread rawSocket closed")
        except Exception as e:
            Utils.Message.addMessage("ERR: main()__receiveRtpThread rawSocket.close() " + str(e))

        Utils.Message.addMessage("DBUG:__receiveRTPThread exiting")


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

# This function will be invoked by SIGINT (e.g from a Ctrl -C i.e by the OS sending a SIGINT signal)
def requestShutdownSignalHandler(signum, frame):
    Utils.Message.addMessage("DBUG: __main_.requestShutdownSignalHandler() called with signal " + str(signum))
    raise RequestShutdown

# This function will be invoked by SIGTERM (i.e by the OS sending a kill signal)
def shutdownApplicationSignalHandler(signum, frame):
    Utils.Message.addMessage("DBUG: shutdownApplicationSignalHandler() called with signal " + str(signum))
    raise ShutdownApplication

# # Takes a list of octets [[a,b,c,d],[a,b,c,d]....] and XORs all contents to a single byte to create a checksum value
# def createTracerouteChecksum(hopsList):
#     if len(hopsList) > 0:
#         try:
#             # Create lambda function to xor two values
#             xor = lambda x, y: x ^ y
#             # Use reduce() to iterate over a the list of octets in sequence using our lambda function
#             xorSingleHop = lambda hopOctets:reduce(xor, hopOctets)
#
#             output = 0
#             # Iterate over the all the hops, xor'ing each hop in turn
#             for hop in hopsList:
#                 output = output ^ xorSingleHop(hop)
#             return output
#         except Exception as e:
#             return None
#     else:
#         return None
# def calcIPChecksum():
#     import struct
#
#     data = "45 00 00 47 73 88 40 00 40 06 a2 c4 83 9f 0e 85 83 9f 0e a1"
#
#     def carry_around_add(a, b):
#         c = a + b
#         return (c & 0xffff) + (c >> 16)
#
#     def checksum(msg):
#         s = 0
#         for i in range(0, len(msg), 2):
#             w = ord(msg[i]) + (ord(msg[i+1]) << 8)
#             s = carry_around_add(s, w)
#         return ~s & 0xffff
#
#     data = data.split()
#     data = map(lambda x: int(x,16), data)
#     data = struct.pack("%dB" % len(data), *data)
#     print(str(' '.join('%02X' % ord(x) for x in data)))
#     print("Checksum: " + str(checksum(data)))


def main(argv):


    # print("main thread")
    # textToDisplay = "Say you're writing a program in Python and all it does is pretty print some stuff. The output is in prettiest_print_ever. You already do weird tricks importing fcntl, termios, struct and friends to get the terminal size so that you can use the full width of the terminal (if any); that also gives you the screen height, so it makes sense to use it. (That also means you've long given up any pretenses of cross-platform compatibility, too.)"
    #
    # Utils.smart_print(textToDisplay,terminal_height=3)
    # print("back in main thread")
    # exit()

    # String to specify which operation mode we're in (loopback, tx, rx)
    MODE = ""

    # Additonal Operation Mode flag for 'special features'
    specialFeaturesModeFlag = False
    # Specify a default txRate of 1Mbps if no rate specified
    txRate = Registry.defaultTXRate_bps

    # Specify a default packet size for the tx stream (if none supplied)
    payloadLength = Registry.defaultPayloadLength_bytes

    # Default level of packet loss that will generate an event
    glitchEventTriggerThreshold  = Registry.rtpReceiveStreamGlitchThreshold

    UDP_TX_SRC_PORT = 0

    UDP_RX_IP = ""
    UDP_RX_PORT = 0

    # A list of UDP receive ports being actively listened to
    receivePortList = []

    # Default Sync Source identifier of first tx stream
    SYNC_SOURCE_ID =random.randint(1000, 2000)

    # Default lifespan of a tx stream (default 1 hr)
    txStreamTimeToLive_sec = Registry.defaultTxStreamTimeToLive_sec

    # Default friendly name of Tx stream (if not overridden, sync source ID is used instead)
    RTP_TX_STREAM_FRIENDLY_NAME = ""

    # An RTP header is 12 bytes long
    RTP_HEADER_SIZE = 12

    # Query the RtpGenerator class to find out the length (in bytes) of the isptest messages it will incorporate into the payload
    ISPTEST_HEADER_SIZE = RtpGenerator.getIsptestHeaderSize()

    # Default message verbosity
    defaultVerbosityLevel = 0
    # Set default value
    Utils.Message.setVerbosity(defaultVerbosityLevel)
    # Utils.Message.addMessage("hello")

    # exit()
    # print ('Argument List: '+ str(argv))
    try:
        # options are:
        # -h: help
        # -x: loopback mode <<<NO LONGER SUPPORTED. WILL ALMOST CERTAINLY ACT STRANGELY
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
                print ("isptest Version " + str(Registry.version) + "\r")
                print ("options are:\r")
                print ("-h: help (this message)\r")
                print ("-t: transmit mode usage: address:port\r")
                print("Additional transmit parameters:-\r")
                print ("\t-s [val] udp transmit source port (for transmit mode)\r")
                print ("\t-u [val] sync source ID (for transmit or loopback mode)")
                print ("\t-l: [val] duration of transmission (in seconds. Default " + \
                       str(Registry.defaultTxStreamTimeToLive_sec) + " sec).\r")
                print ("\t    A value of -1 means 'forever'\r")
                print ("\t-b [val] tx bandwidth (append k for kbps, m for mbps\r")
                print ("\t   eg -b 1m or -b 500k). Default " + str(Utils.bToMb(Registry.defaultTXRate_bps)) + "bps, " +\
                       "minimum " + str(Utils.bToMb(Registry.minimumPermittedTXRate_bps)) + "bps" +"\r")
                print ("\t-d [val] rtp payload size (bytes). Default = " + \
                       str(Registry.defaultPayloadLength_bytes) + " bytes\r")
                print ("\t-n: [name] friendly name for tx stream (10 chars max)\r")
                print ("\r")
                print ("-r receive mode usage: -r [port] or -r [address:port]\r")
                print("Additional receive parameters:-\r")
                print ("\t-i [val] Glitch event packet loss ignore threshold (or 'sensitivity'). \r")
                print("\t  Outages below this limit will not generate an event. Default = " +\
                      str(Registry.rtpReceiveStreamGlitchThreshold) + "\r")
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
                    UDP_RX_PORT = arg.split(':')[1]
                    # Validate the supplied port no
                    try:
                        # If this statement executes, then the port is a valid integer
                        UDP_RX_PORT = int(UDP_RX_PORT) + 1 -1
                        # Now test to see whether it is above >1024
                        if UDP_RX_PORT < 1024:
                            raise Exception
                        # Add the validated receive port to the receivePortList
                        receivePortList.append(UDP_RX_PORT)
                    except:
                        print("Invalid RECEIVE port supplied. Should be an integer > 1024: " + str(arg))
                        exit()

                    # Validate supplied IP address
                    try:
                        socket.inet_aton(UDP_RX_IP)
                    except Exception as e:
                        print ("Invalid RECEIVE IP address:port combination supplied: " + str(arg) + ", "+ str(e))
                        exit()
                    print(MODE+", "+str(UDP_RX_IP)+", "+str(UDP_RX_PORT))
                else:
                    # If only a single parameter supplied, use the 'OS supplied' address
                    # and the supplied value as a UDP receive port
                    # Get the ip address of the host machine
                    UDP_RX_IP = Utils.get_ip()
                    try:
                        arg = int(arg) + 1 - 1
                        if arg < 1024:
                            # print ("Invalid RECEIVE port supplied. Should be an integer > 1024: " + str(arg))
                            # exit()
                            raise Exception
                        UDP_RX_PORT = arg
                        # Add the validated receive port to the receivePortList
                        receivePortList.append(UDP_RX_PORT)
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
                        print ("Invalid -b bandwidth specified. Unknown multiplier: " + str(multiplier) +"\r")
                        exit()
                    # Now check to see if the rate meets the minimum permitted
                    if txRate < Registry.minimumPermittedTXRate_bps:
                        print("Specified tx rate too low. The minimum allowed is " + \
                              str(Utils.bToMb(Registry.minimumPermittedTXRate_bps)) + "bps\r")
                        exit()

                except Exception as e:
                    print ("Invalid -b bandwidth specfied. Should be xy whether x is a numerical value and\n" +\
                           "y is k or m (kbps or mbps). "+ \
                        "\nIf no multiplier supplied then assuming x mbps. eg. 500k, 1m, 5m etc" +\
                        "\nMinimum bandwidth 10kbps, default " + str(Utils.bToMb(Registry.defaultTXRate_bps)) + "bps\r")
                    print("Exception: " + str(e) + "\r")
                    exit()


            elif opt in ("-d"):
                # Maximum Ethernet frame size is 1500 bytes (minus 12 bytes for the RTP header)
                MAX_PAYLOAD_SIZE_bytes = Registry.maximumPayloadSize_bytes
                # Minimum size is determined by the sice of the isptest header
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
                    Utils.Message.setVerbosity(arg)
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

    # Now set the message logging filename depending on the operation mode
    # Get the filename itself, from Registry
    if MODE == "TRANSMIT":
        Utils.Message.setOutputFileName(Registry.messageLogFilenameTx)
    elif MODE == "RECEIVE":
        Utils.Message.setOutputFileName(Registry.messageLogFilenameRx)

    # Check to see if resultsSubfolder already exists (if not, create it)
    try:
        directory = os.path.dirname(Registry.resultsSubfolder)
        if not os.path.exists(directory):
            txt = "subfolder for results doesn't exist. Creating " + Registry.resultsSubfolder
            print(txt + "\r")
            Utils.Message.addMessage(txt)
            os.makedirs(Registry.resultsSubfolder)
    except OSError:
        print("Could not create sub folder " + Registry.resultsSubfolder + \
              ". Check you have write privileges for this folder\r")
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

    # Create a list to hold the instances of RtpPacketReceiver and associated UDPMessageSender objects
    # (which are the objects resposible for actually receiving and sending the rtp/udp data)
    # This will be a list of tuples [[RtpPacketReceiver, UDPMessageSender]
    # It will be passed to the UI object to allow the UI to access the data counters/port no.s etc within the
    # RtpPacketReceiver/UDPMessageSender objects themselves
    receiversAndSendersList = []

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
        receiversAndSendersList)

    # Create new instance of WhoisResolver (which will create a background __whoisLookupThread)
    whoIsResolver = Utils.WhoisResolver()

    # Start traffic generator thread
    if MODE == 'LOOPBACK' or MODE == 'TRANSMIT':
        # If UDP source port specified
        # if UDP_TX_SRC_PORT >0:
        rtpGenerator = RtpGenerator(UDP_TX_IP, UDP_TX_PORT, txRate,
                                    payloadLength, SYNC_SOURCE_ID, txStreamTimeToLive_sec,
                                    rtpTxStreamsDict, rtpTxStreamsDictMutex,
                                    rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex, uiInstance=ui,
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
        Utils.Message.addMessage("main.shutdownApplication() called")
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
                    Utils.Message.addMessage("INFO: Killing " + str(type(dict[stream])) + ": " + str(stream))
                    print("Killing stream " + str(stream) + "\n")
                    # Invoke the kill method of each stream
                    dict[stream].killStream()


        ############ Stop DiskLogger and __receiveRTP threads (currently they stop themselves)
        shutdownFlag.set()
        # Wait for diskLogger Thread to end
        diskLoggerThread.join()

        # # wait for __receiveRtpStream Thread to end (if it exists)
        # if MODE == 'RECEIVE' or MODE == 'LOOPBACK':
        #     receiveRtpThread.join()

        # Kill the whoIsResolver object
        whoIsResolver.kill()

        time.sleep(0.2)
        # Term.clearScreen()
        # Term.printAt("main.shutdownApplication() in progress", 1, 1)

        # Now kill UI
        ui.kill()
        exit()


    if MODE == 'RECEIVE' or MODE == 'LOOPBACK':

        # Create a diskLogging Thread - pass rtpStream object dictionary to it
        diskLoggerThread = threading.Thread(target=__diskLoggerThread,
                                            args=(MODE, rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,))
        diskLoggerThread.daemon = True  # Thread will auto shutdown when the prog ends
        diskLoggerThread.setName("__diskLoggerThread")
        diskLoggerThread.start()

        # Create list of udp ports to listen on (and send from)
        # receivePortList = [UDP_RX_PORT]
        # Iterate over the list creating
        #   1) A txMessageQueue (a Queue.SimpleQueue object to send messages/results back to the source)
        #   2) A RtpPacketReceiver to receive udp/rtp packets and create RtpReceiveStream objects
        #   3) A UDPMessageSender to actually do the transmission of udp packets back to the sender
        for receivePort in receivePortList:
            # Create a simple queue to hold results data to be sent back to the isptest transmitters
            # Each tx message is a tuple containing [txMessage (byteArray), dest ip addr, dest udp port]
            txMessageQueue = SimpleQueue()

            # Create an RtpPacketReceiver to capture incoming rtp packets and create RtpReceiveStreams
            rtpPacketReceiver = RtpPacketReceiver(rtpRxStreamsDict, rtpRxStreamsDictMutex, shutdownFlag,
                       UDP_RX_IP, receivePort, ISPTEST_HEADER_SIZE, glitchEventTriggerThreshold, ui, txMessageQueue)

            # Wait for socket (Created by rtpPacketReceiver) to become available
            while rtpPacketReceiver.getSocket() is None and not shutdownFlag.is_set():
                Utils.Message.addMessage("DBUG:Waiting for udp socket (port " + str(receivePort) + ") to be created")
                time.sleep(0.5)

            # Once the socket has been created, pass it to the udpSend thread
            if rtpPacketReceiver.getSocket() is not None:
                # Create a UDPMessageSender using to correspond to the RtpPacketReceiver sharing the same socket
                udpMessageSender = UDPMessageSender(txMessageQueue, rtpPacketReceiver.getSocket(), shutdownFlag)

            # Add the RtpPacketReceiver/UDPMessageSender pair to the receiversAndSenders[] list
            receiversAndSendersList.append([rtpPacketReceiver, udpMessageSender])


    # Endless loop
    while True:
        try:
            while True:
                # Term.printAt(str(listCurrentThreads()),1,2)
                time.sleep(1)

        # This code will execute if the RequestShutdown Exception is raised (SIGINT, Ctrl-C)
        except RequestShutdown:
            Utils.Message.addMessage("DBUG: __main__.RequestShutdown Exception raised")
            # Put up a Quit y/n dialogue
            userResponse = ui.showShutDownDialogue()
            # Utils.Message.addMessage(str(datetime.datetime.now()) + ", main() except RequestShutdown: " + str(userResponse))
            # If yes, quit
            if userResponse:
                shutdownApplication()
            # Otherwise ignore
            else:
                pass

        # This code will execute if the ShutdownApplication Exception is raised (SIGTERM)
        # It will cause the pgram to end, with no user prompt
        except ShutdownApplication:
            Utils.Message.addMessage("DBUG: ShutdownApplication Exception raised (SIGTERM)")
            shutdownApplication()


# Invoke main() method (entry point for Python script)
if __name__ == "__main__":
    # Call main and pass command line args to it (but ignore the first argument)
    main(sys.argv[1:])
