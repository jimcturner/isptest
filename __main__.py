#!/usr/bin/env python
#
# Python packet sniffer
#
# 
from __future__ import unicode_literals # Required for prompt_toolkit

import cgi
import urllib
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse, parse_qs, parse_qsl, urlencode

import requests

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
from queue import SimpleQueue, Empty, Queue, Full

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
import logging

# debugging libraries
import faulthandler

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
import multiprocessing as mp

# Additional experimental libraries


# Additonal libraries required (of my own making)
from RtpStreams import RtpReceiveCommon, RtpReceiveStream, RtpGenerator, RtpStreamResults, RtpStreamComparer, \
    Glitch, RtpData, IPRoutingTracerouteChange, StreamResumed, StreamLost, IPRoutingTTLChange, StreamStarted, \
    RtpPacketTransceiver
import Utils
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
    def __init__(self, operationMode, specialFeaturesModeFlag, receiveAddrList, controllerTCPPort=None,
                 processesCreatedDict=None):
        self.operationMode = operationMode
        self.specialFeaturesModeFlag = specialFeaturesModeFlag
        self.receiveAddrList = receiveAddrList # This will contain the UDP_RX_IP and  UDP_RX_PORT(s)
        self.controllerTCPPort = controllerTCPPort # The TCP listen port for the HTTP server
        # Create an API helper
        self.ctrlAPI = Utils.APIHelper(self.controllerTCPPort, addr="127.0.0.1")
        self.pid = os.getpid() # Stores the processID (pid of this process. Used as a source id in
        # control messages sent back to the transmitter (so that the source of the message can be identified)


        # self.UDP_RX_IP = ""
        # self.UDP_RX_PORT = 0

        # Create a runtime_s counter to count the elapsed time the program has been running
        self.startTime = datetime.datetime.now()
        self.runtime_s = datetime.timedelta()

        # If true, this will cause renderDisplayThread to put up a quit y/n? prompt
        self.displayQuitDialogueFlag = False
        # threading.Event object used to intentionally block the showShutDownDialogue() method
        self.quitDialogueNotActiveFlag = threading.Event()
        # This will store the result of the user response
        self.quitConfirmed = False

        # A pointer to the method which will render the popup (if any) to be displayed by __renderDisplayThread()
        self.displayPopup = None
        # Used by the Pop-Up tables (Events, Traceroute etc) . Keeps track of the current display page
        self.tablePageNo = 0
        # Used to send popup error messages to UI.__renderDisplayThread
        self.displayFatalErrorDialogue = False
        self.fatalErrorDialogueMessageText = ""
        self.fatalErrorDialogueTitle = ""
        # Used by the EventsTable and CopyToClipboard
        # Currently, if the list is populated, the events table will only show that type of Event
        self.filterListForDisplayedEvents = [None,
                                             ["Glitch"],
                                             ["Glitch", "StreamResumed"],
                                             ["StreamStarted", "StreamLost", "StreamResumed"],
                                             ["IPRoutingTracerouteChange", "IPRoutingTTLChange"]
                                             ]
        self.selectedFilterNo = 0    # Specifies which filter option within filterListForDisplayedEvents[] is in use

        self.popupSortDescending = False   # Reverses the order of the results for popup tables

        self.selectedCriteriaForCompareStreams = 0 # Specifies which stream compare criteria is in use
                                                    # (within the Registry.criteriaListForCompareStreams{} dict)

        # Thread running flags
        self.keysPressedThreadActive = True
        self.renderDisplayThreadActive = True
        self.detectTerminalSizeThreadActive = True

        # A dict of the (multiprocessing) child processes spawned by this object (i.e the RtpGenerators)
        # keyed by the pid of the process
        self.processesCreatedDict = processesCreatedDict

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

        # Declare list to hold list of available RtpGenerator/RtpReceiveStream streams that can be displayed
        # This is a list of stream definitions in the form of dicts {"streamID", "streamType", "httpPort", "timeCreated"}
        self.availableRtpStreamList = []

        self.selectedView = 0  # Keeps track of which view is currently being displayed
        self.selectedTableRow = 0  # Keeps track of the selected row on the stream table
        self.streamTableFirstRow = 0  # Tracks the current starting row of the stream table data
        self.streamTableLastRow = 0  # Tracks the current end row of the stream table data

        self.selectedStream = None  # Points to the self.availableRtpStreamList item (a dict containing a stream definition)
                                    # currently highlighted in the streams table

        # Screen label showing the available key commands (depending upon mode)
        self.keyCommandsString = "[h]elp, [a]bout, [d]elete, [l]abel, [r]eport, [t]raceroute, com[p]are"

        self.txStreamModifierCommandsString = "TX  modifiers: [1/2] packet size, [3/4] tx rate, [5/6] lifetime, [b]urst"
        # Add "new" command for TX mode
        if self.operationMode == 'LOOPBACK' or self.operationMode == 'TRANSMIT':
            self.txStreamModifierCommandsString += ", [n]ew "

        # Extra command strip for 'special features' mode
        self.extraKeyCommandsString = "[7] enable/disable stream, [8] jitter on/off, [9] minor loss, [0] major  loss"

        # define views, tables headings and keys
        # view definition as follows. It pulls together the list of available tables (views of the available data), the table headings
        # and the relevant stats keys all within a single data structure. This should make adding over new views in the future straightforward
        # view [n]["title"] will be the name of the view (used to generate the navigation bar)
        # view [n]["keys/values"] is a tuple containing [column title, the stats dictionary key relating to that parameter]
        # view [n]["apiURL"] is a reference to the URL endpoint that will serve the required data
        self.views = []

        if self.operationMode == 'LOOPBACK' or self.operationMode == 'TRANSMIT':
            self.views.append({"title": Term.FG(Term.RED) + "Tx Streams",
                               "keys/values":
                                   [
                                       ["#", 0],  # Used as an index[]
                                        ["Name", 'Friendly Name'],  # [column title, dictionary key containing that value]
                                        ["Src\nPort", 'Tx Source Port'],
                                        ["Dest\n IP", 'Dest IP'],
                                        ["Dest\nPort", 'Dest Port'],
                                        ["Sync\nsrcID", 'Sync Source ID'],
                                        ["Tx\nbps", 'Tx Rate (actual)'],
                                        ["Size", 'Packet size'],
                                        ["Bytes\n tx'd", 'Bytes transmitted'],
                                        [" Time\nremain", 'Time to live']
                                    ],
                               "apiURL": "/txstats"  # data source
                               })

        self.views.append({"title": "Summary",
                      "keys/values":
                          [
                              ["#", 0],  # Used as an index
                                ["Name", "stream_friendly_name"],
                                ["Src Addr", "stream_srcAddress"],
                                 # ["port", "stream_srcPort"],
                                ["bps", "packet_data_received_1S_bytes"],
                                ["Pkts\nlost", "glitch_packets_lost_total_count"],
                                [" %\nloss", "glitch_packets_lost_total_percent"],
                                ["Time since\nlast glitch", "glitch_time_elapsed_since_last_glitch"],
                                ["glitch\nperiod", "glitch_mean_time_between_glitches"],
                                ["Count", "glitch_counter_total_glitches"]
                            ],
                       "apiURL": "/stats"
                           })

        self.views.append({"title": "Stream",
                           "keys/values":
                                [
                                    ["#", 0],  # Used as an index
                                    ["Name", "stream_friendly_name"],
                                    ["Sync \nSrcID", "stream_syncSource"],
                                    ["Src Addr", "stream_srcAddress"],
                                    ["Src\nport", "stream_srcPort"],
                                    ["Dst Addr", "stream_rxAddress"],
                                    ["Dst\nport", "stream_rxPort"],
                                    ["  Time\nelapsed", "stream_time_elapsed_total"]
                                ],
                           "apiURL": "/stats"
                            })

        self.views.append({"title": "Packet",
                           "keys/values":
                                [
                                    ["#", 0],  # Used as an index[]
                                    ["Name", "stream_friendly_name"],
                                    ["First Seen\npacket", "packet_first_packet_received_timestamp"],
                                    ["Last seen\npacket", "packet_last_seen_received_timestamp"],
                                    ["pack\np/s", "packet_counter_1S"],
                                    ["Length\n(bytes)", "packet_payload_size_mean_1S_bytes"],
                                    ["Recv\nperiod", "packet_mean_receive_period_uS"],
                                    ["Bytes\nRcvd", "packet_data_received_total_bytes"],
                                    ["TTL", "packet_instantaneous_ttl"]
                                    # ["",""],
                                ],
                           "apiURL": "/stats"
                           })

        self.views.append({"title": "Glitch",
                           "keys/values":
                                [
                                    ["#", 0],  # Used as an index[]
                                    ["Name", "stream_friendly_name"],
                                    ["Mean\nloss", "glitch_packets_lost_per_glitch_mean"],
                                    ["Max\nloss", "glitch_packets_lost_per_glitch_max"],
                                    ["Total\nloss", "glitch_packets_lost_total_count"],
                                   ["Mean\nduration", "glitch_mean_glitch_duration"],
                                   ["Max\nduration", "glitch_max_glitch_duration"],
                                   ["Total\nGlitch", "glitch_counter_total_glitches"],
                                   ["Ignored", "glitch_glitches_ignored_counter"],
                                   ["Threshold", "glitch_Event_Trigger_Threshold_packets"]
                                ],
                           "apiURL": "/stats"
                           })

        self.views.append({"title": "Historic",
                           "keys/values":
                                [
                                    ["#", 0],  # Used as an index[],
                                    ["Name\n", "stream_friendly_name"],
                                    ["24Hr\n", "historic_glitch_counter_last_24Hr"],
                                    ["1Hr\n", "historic_glitch_counter_last_1Hr"],
                                    ["10Min\n", "historic_glitch_counter_last_10Min"],
                                    ["1Min\n", "historic_glitch_counter_last_1Min"],
                                    ["10Sec\n", "historic_glitch_counter_last_10Sec"],
                                    [" Time of\nlast glitch", "glitch_most_recent_timestamp"]
                                    # ["", ""],
                                ],
                           "apiURL": "/stats"})

        self.views.append({"title": "Jitter",
                           "keys/values":
                                [
                                    ["#", 0],  # Used as an index[]
                                    ["Name", "stream_friendly_name"],
                                    ["Long term\n  mean", "jitter_long_term_uS"],
                                    ["Min", "jitter_min_uS"],
                                    ["Max", "jitter_max_uS"],
                                    ["Range", "jitter_range_uS"],
                                    ["1S \nmean", "jitter_mean_1S_uS"],
                                    ["10S \nmean", "jitter_mean_10S_uS"]
                                ],
                           "apiURL": "/stats"
                           })

        self.views.append({"title": "NAT",
                           "keys/values":
                                [
                                    ["#", 0],  # Used as an index[]
                                    ["src\nport", "stream_transmitter_local_srcPort"],
                                    ["Tx Local addr", "stream_transmitter_localAddress"],
                                    ["Tx Natted addr", "stream_srcAddress"],
                                    ["src\nport", "stream_srcPort"],
                                    ["Rx Public addr", "stream_transmitter_destAddress"],
                                    ["Rx Local addr", "stream_rxAddress"]
                                ],
                            "apiURL": "/stats"
                            })

        # Additionally, for RECEIVE mode, add a further table that will show the transmitter parameters
        if self.operationMode == 'RECEIVE':
            self.views.append({"title": Term.FG(Term.RED) + "Transmitter",
                               "keys/values":
                                    [
                                        ["#", 0],  # Used as an index[]
                                        ["Name", "stream_friendly_name"],
                                        ["Target\nTx Bps", 'stream_transmitter_txRate_bps'],
                                        [" Time\nremain", 'stream_transmitter_TimeToLive_sec'],
                                        ["Return\n loss %", "stream_transmitter_return_loss_percent"]
                                    ],
                               "apiURL": "/stats"
                               })
        # Stores the most recent message - used to determine whether we need to redraw the message table
        self.lastMessageAdded = ""

        self.latestTxStreamStats = None # Used to snapshot the stream parameters of the most recenrtly added stream
                                        # This is used to prepopulate the 'add new stream' table
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
        # Write the current 'uptime' to disk
        Utils.Message.addMessage("********* isptest ending. Total run time: " +
                                 str(Utils.dtstrft(self.runtime_s)) + " *********")

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
    def showErrorDialogue(self, errorTitle, errorMessageText):
        Utils.Message.addMessage("DBUG: UI.showFatalErrorDialogue() called")
        self.fatalErrorDialogueTitle = errorTitle
        self.fatalErrorDialogueMessageText = errorMessageText
        self.displayFatalErrorDialogue = True
        # Force a redraw
        self.wakeUpUI.set()

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
            if view["title"] == self.views[self.selectedView]["title"]:
                # If this is the 'current' view, create black on white
                navigationBar += Term.BlaWh + " " + view["title"] + " " + Term.WhiBlu + " "
            else:
                # Otherwise create as dimmed white on cyan
                navigationBar += Term.BlaCy + " " + view["title"] + " " + Term.WhiBlu + " "
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
            if view["title"] == self.views[self.selectedView]["title"]:
                # Get a list od tuples containing a column title and a key pair
                columns = view["keys/values"]
                for column in columns:
                    titleRow.append(column[0])
                    keyList.append(column[1])

        # Create a table data list with the title row at the head
        tableData = [titleRow]

        # Step 2) Populate the remaining table rows with data
        # Calculate the maximum no. of rows that can be displayed in the stream table - determined by the terminal height
        streamTableNoOfRows = int(self.currentTermHeight / 2) - 9

        # Get the no of items within availableRtpStreamList
        streamTableDataSetLength = len(self.availableRtpStreamList)

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
                for streamIndex in range(self.streamTableFirstRow, self.streamTableLastRow + 1):
                    # Get the HTTP Server port no of the current stream
                    httpPort = self.availableRtpStreamList[streamIndex]["httpPort"]
                    # Get the api URL that will supply the data for this table
                    # (The url is contained within the 3rd element of each view array)
                    dataUrl = self.views[self.selectedView]["apiURL"]
                    # Retrieve the stats dict for the current stream
                    try:
                        streamDataStats = Utils.APIHelper(httpPort).getByURL(dataUrl)
                        if len(streamDataStats) > 0:
                            # iterate over the keys list for each stream - this will create a new tableData row per stream
                            tableRow = []  # Create new row to hold the data
                            ###################################### These are the lines that actually populate the table
                            for key in keyList:
                                # Check to see if the key value= 0. If it does, this is a special case, it's an index no.
                                # which is stored as the third element of a streamData tuple in the dataSetToDisplay[]
                                if key == 0:
                                    # Grab the index number and assign to table cell
                                    # For useability, start the, displayed no starting from 1
                                    tableCell = str(streamIndex + 1)
                                else:
                                    # This is a normal cell with a lookup key specified in the view definition
                                    try:
                                        # Retrieve the data from the rtpStream object by looking up it's key
                                        # Attempt to humanise the data based on object type or clues given by the key name
                                        tableCell = str(RtpReceiveCommon.humanise(key, streamDataStats[key]))
                                        try:
                                            # is it a receive stream?
                                            # If so, test the stream stats
                                            if self.availableRtpStreamList[streamIndex]["streamType"] == "RtpReceiveStream":
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

                                            if self.availableRtpStreamList[streamIndex]["streamType"] == "RtpGenerator":
                                                # If so, check to see that the data is fresh by looking at
                                                # stats["lastUpdatedTimestamp"] inside the stats dict
                                                # If no fresh data received after 5 seconds, assume there's a problem
                                                # and colour code the stream red
                                                noUpdateAlertThreshold = 5
                                                if "lastUpdatedTimestamp" in streamDataStats:
                                                    # Convert streamDataStats["lastUpdatedTimestamp"] key from str to datetime.datetime format
                                                    lastUpdatedTimestamp = datetime.datetime.strptime(streamDataStats["lastUpdatedTimestamp"],
                                                                                                      '%Y-%m-%d %H:%M:%S.%f')
                                                    # Has noUpdateAlertThreshold been exceeded
                                                    if (datetime.datetime.now() - lastUpdatedTimestamp) > \
                                                            datetime.timedelta(seconds=noUpdateAlertThreshold):
                                                        tableCell = Term.FG(Term.RED) + tableCell

                                                # If the RtpGenerator TTL has expired, dim the table row
                                                if "Time to live" in streamDataStats and\
                                                    streamDataStats["Time to live"]  == 1: # TTL=1 denotes expired
                                                        # If tx stream has 'expired', dim the table row
                                                        tableCell = Term.DIM + tableCell

                                        except Exception as e:
                                            Utils.Message.addMessage(
                                                "ERR: __displayThread: (colour coding of stream tables) " + str(e))

                                    except Exception as e:
                                        # If the key doesn't exist within the rtpStream stats dict, copy in an error code instead
                                        tableCell = "keyErr"
                                        Utils.Message.addMessage("ERR: __displayThread (for key in keyList): " + str(e))

                                # Check to see if this is the currently selected stream, if so, highlight the row on the table
                                if streamIndex == self.selectedTableRow:
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
                        else:
                            Utils.Message.addMessage(f"No data to display yet, please wait", logToDisk=False)
                    except Exception as e:
                        # api didn't respond. No data to display
                        pass
                        # Utils.Message.addMessage(
                        #     f"ERR:UI.__drawStreamsTable() streamIndex {streamIndex}, GET HTTP:{httpPort}:{dataUrl}")

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
                # Convert message timestamp column from a datetime object to a string so it can be displayed
                message[0] = message[0].strftime("%H:%M:%S")


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
            UDP_RX_IP = ""
            UDP_RX_PORTS = ""
            try:
                # Extract the receive IP and receive port(s) (if in RECEIVE mode - these are displayed on the top toolbar)
                if len(self.receiveAddrList) > 0:
                    # Take the Rx IP address from the first RtpPacketReceiver in the list (we assume that we will only be
                    # listening on a single IP address, but might be listening to multiple ports on that interface)
                    UDP_RX_IP = self.receiveAddrList[0]["addr"]
                    # Get a list of Rx UDP ports from the receiveAddrList[] and create a comma seperated string
                    UDP_RX_PORTS = ",".join([str(x["port"]) for x in self.receiveAddrList])
            except Exception as e:
                Utils.Message.addMessage(
                    f"ERR:UI.__init() Couldn't extract UDP_RX_IP and/or UDP_RX_PORT(s) from receiveAddrList[],  {e}")
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
                footerRow[0] = "Page\n" + str(pageNo + 1) + "/" + str(noOfPages)
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


    # Cycles through the filtering of displayed Events on the events table created by UI.__renderEventsListTable()
    def __onfilterEventsTable(self):
        # Increment selected display filter no (by cycling around filterListForDisplayedEvents)
        self.selectedFilterNo = (self.selectedFilterNo + 1) % len(self.filterListForDisplayedEvents)


    # Overlays on the screen a paged list of recent events relating to this stream
    def __renderEventsListTable(self):

        # Get Terminal size so we can centre the table
        termW, termH = Term.getTerminalSize()
        # Calculate the maximum no. of lines that will fit within the table, given the terminal height
        maxLines = termH - 20

        eventsList = []
        friendlyName = ""
        syncSourceID = 0

        # Get a list of events (via the API) for the selected stream
        if self.selectedStream is not None:
            try:
                # Get the HTTP Server port no of the currently selected stream
                httpPort = self.selectedStream["httpPort"]
                # Create an APIHelper
                api = Utils.APIHelper(httpPort)
                # Get the (complete) events list
                eventsList = api.getRTPStreamEventListAsSummary(includeStreamSyncSourceID=False, includeFriendlyName=False,
                                                                filterList=self.filterListForDisplayedEvents[self.selectedFilterNo])
                # Get the stats dict
                stats = api.getStats(keyStartsWith="stream")
                # Get friendly name of the selected stream and strip off the trailing whitespace (if any)
                friendlyName = str(stats["stream_friendly_name"]).rstrip()
                syncSourceID = str(stats["stream_syncSource"])

            except Exception as e:
                Utils.Message.addMessage(f"ERR. UI.__renderEventsListTable. getRTPStreamEventList() {self.selectedStream}, {e}")
                eventsList = []

        # Create a list of tuples containing the timestamp and the summary
        tableContents =[]
        if len(eventsList) > 0:
            tableRow = []
            for event in eventsList:
                # Get event details (in the form of a dictionary)
                try:
                    # Retrieve each Event summary, ommiting the syncSourceID and the friendlyName (for display purposes)
                    # and create a table row
                    tableRow.append(str(RtpReceiveCommon.humanise("", event['timeCreated'])))
                    tableRow.append(" " + str(event['summary']).ljust(50))

                except Exception as e:
                    Utils.Message.addMessage("UI.__renderEventsListTable: " + str(e))
                #Append the complate table row to tableContents[]
                tableContents.append(tableRow)
                # Clear the tableRow list ready for next time around the loop
                tableRow = []
        else:
            tableContents.append(["","No events to display"])

        # Additional check to see if the event filtering has been enabled and modify the title/footer labels accordingly
        if self.filterListForDisplayedEvents[self.selectedFilterNo] is not None:
                title = "Filtered events for stream " + str(syncSourceID) + " (" + str(friendlyName) + ")"
                footer = ["","[<][>]page, [^][v]select stream, [r]exit\n"+\
                          "[c]opy to clipboard, [f]ilter, [s]ave file \n" +\
                          "Showing: " + str(self.filterListForDisplayedEvents[self.selectedFilterNo])]
        else:
            title = "All events for stream " + str(syncSourceID) + " (" + str(friendlyName) + ")"
            footer = ["", "[<][>]page, [^][v] select stream, [r]exit \n" + \
                      "[c]opy to clipboard, [f]ilter, [s]ave file"]

        # Now actually display the paged table list
        self.__renderPagedList(self.tablePageNo, title, ["Timestamp".ljust(15), "Event".ljust(50)], tableContents,
                               footerRow=footer,
                               pageNoDisplayInFooterRow= True, reverseList= True, marginOffset= 7)


    # Disables any existing keypress detection
    def __disableKeyChecking(self):
        self.enableGetch.clear()
        # Wait for confirmation that key detection (getch)has been disabled
        self.getchIsDisabled.wait()

    # Renders a pop-up message box
    def renderMessageBox(self, messageText, title, textColour=Term.BLACK, bgColour=Term.CYAN):
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

    # def displayMessageBox(self, *args, **kwargs):
    #     # self.__disableKeyChecking()
    #     # Utils.Message.addMessage(f"UI.displayMessageBox() (BEFORE) enableGetch:{self.enableGetch.is_set()},"
    #     #                          f"getchIsDisabled:{self.getchIsDisabled.is_set()}")
    #     # self.renderMessageBox(*args, **kwargs)
    #     # Utils.Message.addMessage(f"UI.displayMessageBox() (AFTER) enableGetch:{self.enableGetch.is_set()},"
    #     #                          f"getchIsDisabled:{self.getchIsDisabled.is_set()}")
    #     self.showErrorDialogue(*args)

    # If the Event Lists Table is currently displayed, this method will copy the events to the local clipboard
    # Alternatively, if the traceroute table is displayed, it will attempt to render a list of the previous
    # traceroute hop lists and copy that to the clipboard

    # If that is not possible (if for instance, you are connected to a remote instance of isptext via SSH)
    # it will attempt to use linux 'less' as a viewer launched as a seperate process
    def __onCopyReportToClipboard(self):
        streamReport = None
        apiURL = None
        apiQueryArgs = {}
        # Confirm that a valid stream exists
        if self.selectedStream is not None:
            # Query the api for a report based on the current displayPopup
            if self.displayPopup == self.__renderEventsListTable:
                # Get a textual, formatted stream performance summary report for this stream via the API
                # Set the URL that will satisfy the request
                apiURL = "/report/summary"
                # Specify any additional kwargs
                apiQueryArgs = {"eventFilterList": self.filterListForDisplayedEvents[self.selectedFilterNo]}
            elif self.displayPopup == self.__renderTracerouteTable:
                # Get a textual, formatted traceroute report for this stream via the API
                apiURL = "/report/traceroute"

            elif self.displayPopup == self.__renderCompareStreamsTable:
                try:
                    # Create a RtpStreamComparer object. Pass the list of available streams to it
                    rtpStreamComparer = RtpStreamComparer(self.availableRtpStreamList)
                    # Generate a streams comparison report - use the existing criteria list and currently set sort order
                    streamReport = rtpStreamComparer.generateReport(Registry.criteriaListForCompareStreams,
                                                                    listOrder=self.popupSortDescending)
                except Exception as e:
                    Utils.Message.addMessage(f"ERR:UI.onCopyReportToClipboard(compareStreamsTable){e}")
            # Query the api with specified url/kwargs
            if apiURL is not None:
                try:
                    streamReport = Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiURL, **apiQueryArgs)
                except Exception as e:
                    streamReport = None
                    Utils.Message.addMessage(f"ERR:UI.onCopyReportToClipboard {self.displayPopup}, {e}")

            # Check that a textual report has been rendered
            if streamReport is not None:
                # Attempt to copy the report to the local clipboard
                try:
                    # Utils.displayTextUsingMore(streamReport)
                    pyperclip.copy(streamReport)
                    self.renderMessageBox("Success!".center(30) + "\n\n" +\
                            "<Press a key to continue>".center(30),\
                            "Copy to Clipboard", textColour=Term.WHITE, bgColour=Term.GREEN)

                except Exception as e:
                    # pyperclip error messages typically have newline chars in them. This will mess up my message
                    # table! So need to strip them - reaplce \n chars with ,
                    modifiedErrorString = str(e).replace("\n", ", ")
                    Utils.Message.addMessage("DBUG: UI.__onCopyReportToClipboard (using less) " + modifiedErrorString)

                    # Copy to clipboard failed, attempt to launch 'less' viewer instead - only works on Linux/OSX
                    # Display a message box
                    os = Utils.getOperatingSystem()
                    if  os != "Windows":
                        # Only attempt to launch 'less' oif we're not running Windows
                        self.renderMessageBox("\nUnable to copy to the local clipboard.\n" + \
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



    # This method will call the Utils.writeReportToDisk() function
    # causing a report of the current popup to be saved to disk
    # Note, this option is only available if the popup is currently being displayed
    def __onSaveReportToDisk(self):
        # Utility function to generate a filename string containing a timestamp
        def generateFilename(prefix, syncSourceID, srcAddr, friendlyName):
            return f"{prefix}{syncSourceID}_{str(friendlyName).rstrip()}_{srcAddr}_{datetime.datetime.now().strftime('%d-%m-%y_%H-%M-%S')}.txt"

        # Confirm that a stream is selected
        if self.selectedStream is not None:
            streamReport = None
            streamStats = None
            apiURL = None
            apiQueryArgs = {}
            filenamePrefix = ""
            # Generate a report to be saved (via the API) based on the current displayed pop-up
            # Query the api for a report based on the current displayPopup
            if self.displayPopup == self.__renderEventsListTable:
                # Get a textual, formatted stream performance summary report for this stream via the API
                # Set the URL that will satisfy the request
                apiURL = "/report/summary"
                # Specify any additional kwargs
                apiQueryArgs = {"eventFilterList": self.filterListForDisplayedEvents[self.selectedFilterNo]}
                # Specify filename prefix
                filenamePrefix = Registry.streamReportFilename
            elif self.displayPopup == self.__renderTracerouteTable:
                # Get a textual, formatted traceroute report for this stream via the API
                apiURL = "/report/traceroute"
                # Specify filename prefix
                filenamePrefix = "traceroute_history_"

            elif self.displayPopup == self.__renderCompareStreamsTable:
                # Specify filename prefix
                filenamePrefix = "stream_comparison"
                apiURL = None # API not used for this, we'll invoke the RtpStreamComparer object directly
                try:
                    # Create a RtpStreamComparer object. Pass the list of available streams to it
                    rtpStreamComparer = RtpStreamComparer(self.availableRtpStreamList)
                    # Generate a streams comparison report - use the existing criteria list and currently set sort order
                    streamReport = rtpStreamComparer.generateReport(Registry.criteriaListForCompareStreams,
                                                                    listOrder=self.popupSortDescending)
                except Exception as e:
                    Utils.Message.addMessage(f"ERR:UI.onSaveReportToDisk(compareStreamsTable){e}")

            # If required, query the api with specified url/kwargs to retrieve the selected report
            if apiURL is not None:
                try:
                    api = Utils.APIHelper(self.selectedStream["httpPort"])
                    streamReport = api.getByURL(apiURL, **apiQueryArgs)
                    # Get sub-set of stats dict
                    streamStats = api.getStats(keyStartsWith="stream")
                except Exception as e:
                    streamReport = None
                    streamStats = None
                    Utils.Message.addMessage(f"ERR:UI.onSaveReportToDisk query API {self.displayPopup}, {e}")

            # If a report was successfully created, attempt to save it to disk using either an auto generated or
            # manually entered filename
            if streamReport is not None:
                # A report was successfully generated
                try:
                    try:
                        # Auto-generate a filename (this can be overridden in the UI)
                        # Attempt to use the stream-specific stats values
                        defaultFilename = generateFilename(filenamePrefix,
                                                           streamStats["stream_syncSource"],
                                                           streamStats["stream_srcAddress"],
                                                           streamStats["stream_friendly_name"])
                    except:
                        # If stream stats aren't available (e.g for the compare streams report)
                        # simply generate a simple filename with the prefix and creation dater
                        defaultFilename = generateFilename(filenamePrefix, "", "", "")

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
                    try:
                        # Attempt to create a customised title
                        dialogueTitle = f'Export stream report to file (stream {streamStats["stream_syncSource"]})'
                    except:
                        dialogueTitle = f'Export stream report to file'
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
                                # # Generate the actual report
                                # # Use the current display filter for events to determine which events are exported to the file
                                # report = selectedRxOrResultsStream.generateReport(eventFilterList=self.filterListForDisplayedEvents[self.selectedFilterNo])
                                # Invoke the Utils.writeReportToDisk method
                                maxWidth = 70
                                try:
                                    Utils.writeReportToDisk(streamReport, fileName=fullSavePath)
                                    # Display a message box showing the successful save path + filname
                                    # Query the OS for the the absolute file path (this will be displayed)

                                    absoluteSavePath = textwrap.fill(str(os.path.abspath(fullSavePath)), width=maxWidth)
                                    self.renderMessageBox("File saved to:-".center(maxWidth + 3) + "\n" +\
                                                            str(absoluteSavePath).center(maxWidth + 3)+ "\n\n" + \
                                                            "<Press a key to continue>".center(maxWidth + 3), \
                                                            "File save Successful", textColour=Term.WHITE, bgColour=Term.GREEN)
                                except Exception as e:
                                    # Save failed, so show an error
                                    errorMessage = textwrap.fill(str(e), width=maxWidth)
                                    self.renderMessageBox("Error: Unable to save file:-".center(maxWidth + 3) + "\n" + \
                                                            str(errorMessage).center(maxWidth + 3) + "\n\n" + \
                                                            "<Press a key to continue>".center(maxWidth + 3), \
                                                            "File save error", textColour=Term.WHITE,
                                                            bgColour=Term.RED)
                        except ValidationError as e:
                            # Modify the dialogue table to show the erroneous chars
                            dialogueTitle = str(e)

                except Exception as e:
                    Utils.Message.addMessage(f"ERR:UI.__onSaveReportToDisk() save to disk {e}")
            else:
                Utils.Message.addMessage("ERR: UI.__onSaveReportToDisk() no report generated. Nothing to write")


    # Cursor right
    def __onNavigateRight(self):
        # if self.displayEventsTable is False and self.displayTraceRouteTable is False and self.displayHelpTable is False:
        if self.displayPopup is None:
            # Inhibit, if a popup is currently being displayed
            self.selectedView += 1
            # Prevent an 'out of range' view being selected
            if self.selectedView > (len(self.views) - 1):
                self.selectedView = len(self.views) - 1
        else:
            # Used to decrement to the display page of the popup (if there is one)
            # Note, this has to be bounds-checked in the table display code
            self.tablePageNo += 1

    # Cursor left
    def __onNavigateLeft(self):
        # Inhibit, if a popup is currently being displayed
        # if self.displayEventsTable is False and self.displayTraceRouteTable is False and self.displayHelpTable is False:
        if self.displayPopup is None:
            self.selectedView -= 1
            # Prevent an 'out of range' view being selected
            if self.selectedView < 0:
                self.selectedView = 0

        else:
            # Used to decrement to the display page of the popup (if there is one)
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
        if self.selectedTableRow > (len(self.availableRtpStreamList) - 1):
            self.selectedTableRow = len(self.availableRtpStreamList) - 1

    # 'l' pressed
    def __onEnterFriendlyName(self):
        try:
            # Create an onscreen form to enter the new name
            styleDefinition = Style.from_dict({
                'dialog': 'bg:ansiblue',  # Screen background
                'dialog frame.label': 'bg:ansiwhite ansired ',
                'dialog.body': 'bg:ansiwhite ansiblack',
                'dialog shadow': 'bg:ansiblack'})
            # Now wait for confirtmation that __keysPressedThread is definitely disabled
            self.getchIsDisabled.wait()
            text = input_dialog(
                title='Enter friendly name',
                text='Please enter friendly name for stream ' + str(self.selectedStream["streamID"]) + ':',
                style=styleDefinition).run()
            if text is not None:
                # Now pass the new name to the stream api
                    Utils.APIHelper(self.selectedStream["httpPort"]).postByURL("/label", name=text)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onEnterFriendlyName() {e}")

    # 'a' pressed (only when in Tx or Loopback mode)
    def __onAddTxStream(self):
        # Attempt to add a new tx stream (if we're in loopback or transmit mode)
        # If a tx stream already exists, the new stream will be created with an incremented
        # source UDP port and an incremented sync source id.
        # If there are no current streams, the new stream will be created with a random
        # UDP source port and a random sync source id
        if self.operationMode == 'LOOPBACK' or self.operationMode == 'TRANSMIT':

            # Grab the stats of the most recent added tx stream, and make a copy derived from it's settings
            try:
                # Use stats of existing tx stream to derive setup parameters for new stream
                syncSourceID = self.latestTxStreamStats['Sync Source ID'] + 1
                sourcePort = self.latestTxStreamStats['Tx Source Port'] + 1
                destPort = self.latestTxStreamStats['Dest Port']
                destAddr = self.latestTxStreamStats['Dest IP']
                packetLength = self.latestTxStreamStats['Packet size']
                friendlyName = str(syncSourceID)



            except Exception as e:
                # Otherwise specify some defaults
                Utils.Message.addMessage(f"ERR:UI.__onAddTxStream prev stream parameters unavailable, using default values {e}")
                syncSourceID = random.randint(1000, 2000) # Randomly generated value
                sourcePort = 0
                destPort = 0
                destAddr = ""
                packetLength = 1300
                friendlyName = str(syncSourceID)

            try:
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

                    try:
                        rtpGenerator = mp.Process(target=RtpGenerator,
                                                  args=(destAddr, destPort, txRate_bps,
                                                        packetLength, syncSourceID, timeToLive),
                                                  kwargs={"UDP_SRC_PORT": sourcePort,
                                                          "friendlyName": friendlyName,
                                                          "controllerTCPPort": self.controllerTCPPort},
                                                  name=f"RtpGenerator({syncSourceID})",
                                                  daemon=False)
                        rtpGenerator.start()
                        Utils.Message.addMessage("[a] Added new " + str(Utils.bToMb(txRate_bps)) + "bps stream with id " + str(syncSourceID))

                        # Add the process to the processesCreatedDict so we can keep track of it
                        if self.processesCreatedDict is not None:
                            try:
                                Utils.addToProcessesCreatedDict(self.processesCreatedDict, rtpGenerator)
                            except Exception as e:
                                Utils.Message.addMessage(f"ERR:UI add RtpGenerator({syncSourceID}) process to processesCreatedDict")

                        # Stream appears to have been successfully created so
                        # update self.latestTxStreamStats[] with the latest values used
                        self.latestTxStreamStats['Sync Source ID'] = syncSourceID
                        self.latestTxStreamStats['Tx Source Port'] = sourcePort
                        self.latestTxStreamStats['Dest Port'] = destPort
                        self.latestTxStreamStats['Dest IP'] = destAddr
                        self.latestTxStreamStats['Packet size'] = packetLength


                    except Exception as e:
                        Utils.Message.addMessage(f"ERR:UI.__onAddTxStream() failed to create RtpGenerator {syncSourceID}, {e}")
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__onAddTxStream() failed to add new stream {e}")

            # Force redraw
            redrawScreen = True
            # else:
            #     # Note. This code should never be reachable because it shouldn't be possible to start in TRANSMIT mode
            #     # without ever having specified an initial stream
            #     Utils.Message.addMessage("ERR: No previous Tx stream stats to copy from. New stream not added")

    # 'd' -  Delete selected stream
    def __onDeleteStream(self):
        # Delete selected stream (selected table row)

        # Confirm that the dataset associated with this view actually has some data in it
        if self.selectedStream is not None:
            try:
                Utils.Message.addMessage(
                    f"INFO: streamToDelete: {self.selectedStream['streamID']} of type {self.selectedStream['streamType']}")

                # Send an HTTP DELETE to the selected stream using the /delete path
                Utils.APIHelper(self.selectedStream["httpPort"]).deleteByURL("/delete")

            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__onDeleteStream(). Delete Stream request failed: "
                                         f"({self.selectedStream['streamID']}), err: {e}")

    # '4' pressed
    def __onIncreaseTxRate(self):
        apiUrl = "/txrate/inc"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onIncreaseTxRate() {e}")

    # '3' pressed
    def __onDecreaseTxRate(self):
        apiUrl = "/txrate/dec"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onDecreaseTxRate() {e}")

    # '6'
    def __onIncreaseTimeToLive(self):
        apiUrl = "/ttl/inc"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onIncreaseTimeToLive() {e}")

    # '5'
    def __onDecreaseTimeToLive(self):
        apiUrl = "/ttl/dec"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onDecreaseTimeToLive() {e}")

    # 'b'
    def __onEnableBurstMode(self):
        apiUrl = "/burst"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onEnableBurstMode() {e}")

    # '2'
    def __onIncreasePayloadSize(self):
        apiUrl = "/length/inc"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onIncreasePayloadSize() {e}")

    # '1'
    def __onDecreasePayloadSize(self):
        apiUrl = "/length/dec"
        try:
            Utils.APIHelper(self.selectedStream["httpPort"]).getByURL(apiUrl)
        except Exception as e:
            Utils.Message.addMessage(f"ERR:UI.__onDecreasePayloadSize() {e}")

    # # Deprecated 27-11-20 OLD CODE to MODIFY the sync source id of an existing stream. I can't imagine why this would be useful
    # def __onIncrementSyncSourceID(self):
    #     self.__modifySyncSourceID(1)
    #
    # # Deprecated
    # def __onDecrementSyncSourceID(self):
    #     self.__modifySyncSourceID(-1)
    #
    # # Called from __onIncrementSyncSourceID() and __onDecrementSyncSourceID(). Increments/decrements according to dir flag
    # def __modifySyncSourceID(self, direction):
    #     # bounds limit the input
    #     if direction < 0:
    #         # For all negative values, set direction to -1
    #         direction = -1
    #     else:
    #         # For all other values, set direction to '1'
    #         direction = 1
    #     try:
    #         # Confirm that the selected stream is a generator object
    #         if self.selectedStream["streamType"] == "RtpGenerator":
    #             # Get current Sync source ID
    #             currentSyncSourceID = int(self.selectedStream.getRtpStreamStatsByKey('Sync Source ID'))
    #             # Increment/decrement  sync source by 1
    #             self.selectedStream.setSyncSourceIdentifier(currentSyncSourceID + (1 * direction))
    #             # Verify new sync source id
    #             currentSyncSourceID = int(self.selectedStream.getRtpStreamStatsByKey('Sync Source ID'))
    #             Utils.Message.addMessage(
    #                 " Stream " + str(self.selectedStreamID) + " sync source id changed to " + str(currentSyncSourceID))
    #     except Exception as e:


    # 'e'
    def __onToggleErrorMessages(self):
        if self.showErrorsFlag == False:
            # Set flag to true
            self.showErrorsFlag = True
            # Force a change of Message verbosity level to show errors
            Utils.Message.setVerbosity(3)
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
        if self.specialFeaturesModeFlag == True and self.selectedStream is not None and \
                self.selectedStream["streamType"] == "RtpGenerator":
            try:
                # Create API helper
                api = Utils.APIHelper(self.selectedStream["httpPort"])
                # Get current enabled/disabled stats
                txStats = api.getByURL('/txstats')
                currentStatus = txStats["streamEnabledStatus"]
                if currentStatus:
                    # If currentStatus is True, set it to false
                    api.getByURL('/disable')
                else:
                    # Otherwise set it to true
                    api.getByURL('/enable')
                # Get current enabled/disabled stats once more to verify the change
                txStats = api.getByURL('/txstats')
                currentStatus = txStats["streamEnabledStatus"]
                Utils.Message.addMessage(f"UI.__onTogglePacketGenerationOnOff() stream:{self.selectedStream['streamID']},"
                                         f" status: {currentStatus}")
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__onTogglePacketGenerationOnOff() {self.selectedStream['streamID']}, {e}")

    # 'x'
    def __onToggleJitterSimulationOnOff(self):
        # Confirm special features enabled and selected stream is an RtpGenerator
        if self.specialFeaturesModeFlag == True and self.selectedStream is not None and\
                self.selectedStream["streamType"] == "RtpGenerator":
            try:
                # Create API helper
                api = Utils.APIHelper(self.selectedStream["httpPort"])
                # Get current enabled/disabled stats
                txStats = api.getByURL('/txstats')
                currentStatus = txStats["simulateJitterStatus"]
                if currentStatus:
                    # If currentStatus is True, set it to false
                    api.getByURL('/jitter/off')
                else:
                    # Otherwise set it to true
                    api.getByURL('/jitter/on')
                # Get current enabled/disabled stats once more to verify the change
                txStats = api.getByURL('/txstats')
                currentStatus = txStats["simulateJitterStatus"]
                Utils.Message.addMessage(f"UI.__onToggleJitterSimulationOnOff() stream:{self.selectedStream['streamID']},"
                                         f" status: {currentStatus}")
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__onToggleJitterSimulationOnOff() {self.selectedStream['streamID']}, {e}")

    # 'c'
    def __onInsertMinorPacketLoss(self):
        if self.specialFeaturesModeFlag == True and self.selectedStream is not None and\
                self.selectedStream["streamType"] == "RtpGenerator":
            try:
                # Passing 'packetsToSkip=-1' is shorthand for auto generating minor packet loss (i.e < glitch threshold)
                Utils.APIHelper(self.selectedStream["httpPort"]).postByURL("/simulateloss", packetsToSkip=-1)
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__onInsertMinorPacketLoss() {e}")

    # 'v'
    def __onInsertMajorPacketloss(self):
        if self.specialFeaturesModeFlag == True and self.selectedStream is not None and\
                self.selectedStream["streamType"] == "RtpGenerator":
            try:
                # Passing 'packetsToSkip=-2' is shorthand for auto generating major packet loss  (i.e > glitch threshold)
                Utils.APIHelper(self.selectedStream["httpPort"]).postByURL("/simulateloss", packetsToSkip=-2)
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__onInsertMajorPacketloss() {e}")

    def __onAboutDialogue(self):
        # Toggle display of About  dialogue
        # If already, selected, disable it
        if self.displayPopup == self.__renderAboutDialogue:
            self.displayPopup = None
        # Otherwise activate it
        else:
            # Point self.displayPopup to the correct renderer
            self.displayPopup = self.__renderAboutDialogue

    # 'a' - render the About dialogue
    def __renderAboutDialogue(self):
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
                        "\n\n\nmost recent dev branch: rxmp7"+\
                        "\nfinal multiprocessing RtpPacketTransceiver and RtpReceiver version\n\n" + \
                        "Press the [any] key to continue".center(maxWidth, " ")

        # Render the message in a pop-up box
        self.renderMessageBox(tableContents, "About")
        # Clear the self.displayPopup function pointer now that the popup has been displayed
        self.displayPopup = None



    # Show a help page
    def __onShowHelpTable(self):
        # Toggle the display of the help pages
        # If already, selected, disable it
        if self.displayPopup == self.__renderHelpTable:
            self.displayPopup = None
        # Otherwise activate it
        else:
            # Point self.displayPopup to the correct renderer
            self.displayPopup = self.__renderHelpTable
            # Reset display page to 0 when initially displaying the table
            self.tablePageNo = 0
            # Turn off filtering of displayed events when initially displaying the table
            self.selectedFilterNo = 0


        # maxWidth = 55
        # tableContents = ("This will show help... ") + \
        #                 "\n\n...but in the mean time.." +\
        #                 "\n see https://confluence.dev.bbc.co.uk/x/ioKKD for support" + \
        #                 "\n\n\n\n" + \
        #                 "Press the [any] key to continue".center(maxWidth, " ")
        #
        # # Render the message in a pop-up box
        # self.renderMessageBox(tableContents, "Help")

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
        debugInfo.append(["Run time ", str(Utils.dtstrft(self.runtime_s))])
        debugInfo.append(["HTTP Server port ", str(self.controllerTCPPort)])
        # Display return loss
        try:
            # Get the HTTP Server port no of the current stream
            httpPort = self.selectedStream["httpPort"]
            # Request only the return loss value (via the api)
            stats = Utils.APIHelper(httpPort).getStats(keyIs="stream_transmitter_return_loss_percent")
            debugInfo.append(["Return loss % ", str(stats['stream_transmitter_return_loss_percent'])])
        except Exception as e:
            debugInfo.append(["Return loss % ", "please wait"])
        # if self.operationMode == "TRANSMIT":
        #     # Display aggregate socket receive stats
        #     try:
        #         # # NOTE: These are all global vars declared in __receiveRtpThread NOW DEPRECATED.
        #         # SEE RtpPacketReceiver and UDPMessageSender objects for these counters instead
        #         # debugInfo.append(["\nReceiver ", ""])
        #         # debugInfo.append(["raw Rx'd ", str(rawPacketsReceivedByRxThreadCount)])   # Total Rx'd Raw packets
        #         # debugInfo.append(["raw ignored ", str(rawPacketsDiscardedByRxThreadCount)]) # Raw packets ignored
        #         # debugInfo.append(["raw decoded ", str(rawPacketsDecodedByRxThreadCount)])   # Raw packets with an rtp header
        #         # debugInfo.append(["udp Rx'd ", str(udpPacketsReceivedByRxThreadCount)])   # Total Rx'd UDP packets
        #         # debugInfo.append(["udp ignored ", str(udpPacketsDiscardedByRxThreadCount)])   # UDP packets ignored
        #         # debugInfo.append(["udp decoded ", str(udpPacketsDecodedByRxThreadCount)]) # UDP packets with an rtp header
        #         # # Note: These are global vars declared in __sendUDPThread
        #         # debugInfo.append(["udp tx ", str(sendUDPThreadTxPacketCounter)])
        #         # debugInfo.append(["udp Q ", str(sendUDPThreadMessageQueueSize)])
        #         pass
        #     except:
        #         pass

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
        # Toggle the display of the traceroute table

        # If already, selected, disable it
        if self.displayPopup == self.__renderTracerouteTable:
            self.displayPopup = None
        # Otherwise activate it
        else:
            # Point self.displayPopup to the correct renderer
            self.displayPopup = self.__renderTracerouteTable
            # Reset display page to 0 when initially displaying the table
            self.tablePageNo = 0
            # Turn off filtering of displayed events when initially displaying the table
            self.selectedFilterNo = 0

    # Renders the Traceroute dialogue
    def __renderTracerouteTable(self):
        termW, termH = Term.getTerminalSize()
        # Calculate the maximum no. of lines that will fit within the table, given the terminal height
        # maxLines = termH - 20
        maxWidth = 40 + (termW - 80) # Used to automatically truncate the whois table column data
        if maxWidth < 10:
            maxWidth = 10

        tracerouteHopsList = []

        friendlyName = ""
        syncSourceID = 0
        lastUpdated = None
        if self.selectedStream is not None:
            # Create an APIHelper for the selected stream
            api = Utils.APIHelper(self.selectedStream["httpPort"])
            try:
                # Get latest stable tracerouteHopsList from selected stream from the api
                lastUpdated, tracerouteHopsList = api.getByURL("/traceroute")
            except Exception as e:
                Utils.Message.addMessage("ERR: UI.__onShowTracerouteDialogue(). getTraceRouteHopsList() " + str(e))

            # Get the friendly name for the traceroute table title
            # Get the stats dict from the /stats (RECEIVE mode) or txstats (TRANSMIT mode) endpoint -
            apiURL = ""
            try:
                if self.selectedStream["streamType"] == "RtpGenerator":
                    apiURL = "/txstats"
                    kwargs = {}
                else:
                    apiURL = "/stats"
                    kwargs = {"keyStartsWith": "stream"} # Minimise the amount of data requested

                stats = api.getByURL(apiURL, **kwargs)
                friendlyName = str(stats["stream_friendly_name"]).rstrip()
                syncSourceID = str(stats["stream_syncSource"])
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__renderTracerouteTable() GET {apiURL}, {e}")

            # Create a list of tuples containing the index no and the IP address and whois name
            tableContents = []
            if len(tracerouteHopsList) > 0:
                apiResponse = None
                try:
                    # Use the API helper to query the WhoisResolver. This will yield a list of lists [[addr, whois_name],...]
                    apiResponse = self.ctrlAPI.whoisLookup(tracerouteHopsList)
                    # Now create the table contents to be displayed
                    for hopNo in range(len(apiResponse)):
                        # Create each table row as [hopNo, ip address, whois name]
                        addr = apiResponse[hopNo][0]
                        whoisName = apiResponse[hopNo][1]
                        tableContents.append([hopNo+1, addr, whoisName])

                except Exception as e:
                    Utils.Message.addMessage(f"ERR:UI.__renderTracerouteTable() GET /whois {apiResponse}, {e}")


            else:
                tableContents.append(["", "", "No traceroute data to display yet. Please wait".ljust(maxWidth)])
            try:
                # Now actually display the paged table list
                # Create a title for the table
                title = "UDP Traceroute for stream " + str(syncSourceID) + " (" + str(friendlyName) + ") " +\
                        str(len(tracerouteHopsList)) + " hops"
                # Append the last-updated timestamp of the tracsroute data
                if lastUpdated is not None:
                    title += ", updated " + str(RtpReceiveCommon.humanise("", lastUpdated))

                footer = ["", "", "[<][>]page, [^][v] select stream, [t]exit\n[c]opy history to clipboard, [s]ave"]
                self.__renderPagedList(self.tablePageNo, title, ["Hop".ljust(5), "Address".ljust(15), "Whois".ljust(maxWidth)], tableContents,
                                       footerRow=footer,
                                       pageNoDisplayInFooterRow=True, reverseList=False, marginOffset=7)
            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__renderTracerouteTable() generate table {e}")

    def __onDisplayEvents(self):
        # Toggle display of Events list dialogue

        # If already, selected, disable it
        if self.displayPopup == self.__renderEventsListTable:
            self.displayPopup = None
        # Otherwise activate it
        else:
            # Point self.displayPopup to the correct renderer
            self.displayPopup = self.__renderEventsListTable
            # Reset display page to 0 when initially displaying the table
            self.tablePageNo = 0
            # Turn off filtering of displayed events when initially displaying the table
            self.selectedFilterNo = 0


    # Toggles the pop-up table sort order (ascending/descending) (if applicable)
    def __setSortOrder(self):
        if self.popupSortDescending is False:
            self.popupSortDescending = True
        else:
            self.popupSortDescending = False

    # Cycles through the available list of stream comparison criteria
    def __setStreamCompareCriteria(self):
        # Increment selectedCriteriaForCompareStreams. Bounds limit according to the length of
        # Registry.criteriaListForCompareStreams[] using modulo (%) operator
        self.selectedCriteriaForCompareStreams = (self.selectedCriteriaForCompareStreams + 1) %\
                                                    len(Registry.criteriaListForCompareStreams)

    def __onCompareStreams(self):
        # Toggle display of the 'compare streams' table
        # If already, selected, disable it
        if self.displayPopup == self.__renderCompareStreamsTable:
            self.displayPopup = None
        # Otherwise activate it
        else:
            # Point self.displayPopup to the correct renderer
            self.displayPopup = self.__renderCompareStreamsTable


    # Puts up a table that allows the stream performance to be compared (ans a report generated)
    def __renderCompareStreamsTable(self):
        try:
            # Create a RtpStreamComparer object. Pass the list of available streams to it
            rtpStreamComparer = RtpStreamComparer(self.availableRtpStreamList)
            # Extract the key stats key by which to compare the streams by
            keyTosortBy = Registry.criteriaListForCompareStreams[self.selectedCriteriaForCompareStreams]["keyToCompare"]
            displayfriendlyKey = Registry.criteriaListForCompareStreams[self.selectedCriteriaForCompareStreams]["friendlyTitle"]
            # Get a list of streams ordered by a particular stats[] key
            sortedStreamsList = rtpStreamComparer.compareByKey(keyTosortBy, reverseOrder=self.popupSortDescending)

            # Now create the table contents from sortedStreamsList
            # Note: RtpStreamComparer.compareByKey returns a list of dicts
            tableContents = []  # Holds the table rows
            if sortedStreamsList is not None and len(sortedStreamsList) > 0:
                for index in range(len(sortedStreamsList)):
                    # 'humanise' the value depending based on the keyTosortBy
                    value = RtpReceiveCommon.humanise(keyTosortBy, sortedStreamsList[index]["value"], appendUnit=True)
                    # If the relatedEvent key has been populated, we can attempt to retrieve that event from the eventsList
                    # to add some more detail to the comparison table
                    eventSummary = ""
                    eventCreated = ""
                    if sortedStreamsList[index]["relatedEvent"] is not None:
                        try:
                            # Get an eventSummary/timecreated for the Event relating to this stat
                            # Get the time created and humanise
                            eventCreated = RtpReceiveCommon.humanise("",
                                                            sortedStreamsList[index]["relatedEvent"]["timeCreated"])
                            eventSummary = sortedStreamsList[index]["relatedEvent"]["summary"]
                        except Exception as e:
                            Utils.Message.addMessage("ERR: ERR:UI.__renderCompareStreamsTable - lookup event " + str(e))
                    tableContents.append([index + 1, str(sortedStreamsList[index]["friendlyName"]).strip() + "  ", str(value).strip(),
                                          eventCreated, eventSummary])
            else:
                tableContents.append(["", "", "No data to display", "", ""])

            # Now actually display the paged table list
            title = "Comparison of streams (" + displayfriendlyKey
            # Append 'ascending' or 'descending' to table title depending upon value of self.popupSortDescending
            if self.popupSortDescending:
                title += ", descending)"
            else:
                title += ", ascending)"

            footer = ["", " [<][>]page\n [p]exit", " [^][v] select stream\n [c]opy to clipboard", "", "[s]ave, [o]rder\n [m]etric to compare"]
            # .ljust(50)
            self.__renderPagedList(self.tablePageNo, title, ["", "Name ", str(displayfriendlyKey), "", ""], tableContents,
                                   footerRow=footer,
                                   pageNoDisplayInFooterRow=True, reverseList=False, marginOffset=7)
        except Exception as e:
            Utils.Message.addMessage("ERR:UI.__renderCompareStreamsTable() " + str(e))
            # Deactivate this popup
            self.displayPopup = None

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
            # 'f' Cycle through Event display filtering options
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
            # 'p' compare streams
            elif self.keyPressed == ord('p'):
                self.__onCompareStreams()
            # 'o' compare streams set sort order (ascending/descending)
            elif self.keyPressed == ord('o'):
                self.__setSortOrder()
            # 'm' set criteria to compare streams by
            elif self.keyPressed == ord('m'):
                self.__setStreamCompareCriteria()

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
        # It's job is to compare the current working list in use by __displayThread (currentStreamList[])
        # with the rtpStreamDict{} dictionary of active rtpRxStreams or rtpTxStreams (maintained by main())
        # It will replicate any additions/deletions to objects in rtpStreamDict{} to currentStreamList[]
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
            # Recalculate the run-time of the UI thread
            self.runtime_s = datetime.datetime.now() - self.startTime

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


            # Update available streams list
            try:
                # Get a list of streams from the api (these are a list of dicts containing "streamID", "httpPort", "streamType" keys
                self.availableRtpStreamList = self.ctrlAPI.getStreamsList()

            except Exception as e:
                Utils.Message.addMessage(f"ERR:UI.__renderDisplayThread.ctrlAPI.getStreamsList() {e}")
                self.availableRtpStreamList = []

            # Grab the stats of the latest added tx stream (if present) - this info is used for the 'add stream with defaults' option,
            # But only do this at init (when self.latestTxStreamStats is None).
            # Beyond that, self.latestTxStreamStats will be modified by UI.__onAddTXStream()
            if self.latestTxStreamStats is None:
                try:
                    if len(self.availableRtpStreamList) > 0 and self.availableRtpStreamList[-1]["streamType"] == "RtpGenerator":
                        # Grab the stats of the latest added RtpGenerator object
                        latestTxStream = self.availableRtpStreamList[-1]
                        self.latestTxStreamStats = Utils.APIHelper(latestTxStream["httpPort"]).getTxStats()

                except Exception as e:
                    Utils.Message.addMessage(f"ERR:UI.__renderDisplayThread get latestTxStreamStats: {e}")


            # Get a handle on the currently highlighted stream and corresponding sync source ID
            # Confirm that the streamList associated with this view actual has data in it
            # lengthOfDataSetToDisplay = len(self.availableRtpStreamList)

            # Local function to confirm that the 'selected stream' pointed to by the streams table actually exists
            # (it might not still, if the user deleted the stream via the UI
            # If the stream has been deleted, the selection moves to the last stream added, or None
            # if there are no streams at all
            # This will make sure that self.selectedStream is within the range of availableRtpStreamList[]
            def checkSelectedStreamIsWithinRange(ui):
                # Confirm that the streamList actually has data in it
                lengthOfDataSetToDisplay = len(ui.availableRtpStreamList)
                if lengthOfDataSetToDisplay > 0:
                    # Now confirm that we're not off the end of the list of streams (possible if the last stream
                    # in the list was deleted)
                    if ui.selectedTableRow > (lengthOfDataSetToDisplay - 1):
                        # If so, point the selector to the last item on the list
                        ui.selectedTableRow = (lengthOfDataSetToDisplay - 1)
                    # Create a pointer to the stream definition of the currently selected stream
                    ui.selectedStream = ui.availableRtpStreamList[ui.selectedTableRow]
                else:
                # Otherwise, if there are no streams available, set the instance variables accordingly
                    ui.selectedStream = None

            # Check to see that the table selection hasn't overshot the list of items in availableRtpStreamList
            checkSelectedStreamIsWithinRange(self)

            # Determine which key pressed, and call the appropriate method
            self.__parseKeyPressed()

            ########## Start rendering the screen - main screen drawing loop
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

            # Now check to see of any pop-up display has been activated
            if self.displayPopup is not None:
                try:
                    # invoke the popup method pointed to by self.displayPopup
                    self.displayPopup()
                except Exception as e:
                    Utils.Message.addMessage("ERR:__renderDisplayThread() displayPopup " + str(e))

            # Clear flag
            self.redrawScreen = False

            # Finally, Check to see if Fatal Error Message is to be displayed
            if self.displayFatalErrorDialogue:
                # clear flag
                self.displayFatalErrorDialogue = False

                # Put up error message (this is a blocking call)
                self.renderMessageBox(self.fatalErrorDialogueMessageText, self.fatalErrorDialogueTitle, \
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
        print ("Running threads: " + Utils.listCurrentThreads())


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

def __diskLoggerThread(operationMode, shutdownFlag, controllerTCPPort):
    # Autonomous thread to iterate over rtpStreamsDict and poll RtpStream eventLists for new events
    # and write them  to disk
    # Create an API helper to allow access to the HTTP API of the Controller
    ctrlAPI = Utils.APIHelper(controllerTCPPort)

    Utils.Message.addMessage("INFO: diskLoggerThread starting")
    filename = ""
    # Create the full filename including path depending upon opersation mode (excluding file extension eg. csv/.json)
    if operationMode == 'RECEIVE':
        # prefix = "receiver_report_"
        filename = sanitize_filepath(Registry.resultsSubfolder + Registry.receiverLogFilename)
    else:
        filename = sanitize_filepath(Registry.resultsSubfolder + Registry.transmitterLogFilename)

    lastWrittenEventNo = 0
    lastWrittenEventNoDict = {}  # Dictionary to hold the last written event no for each stream

    # Create versions of filename with the desired extensions
    filename_csv = filename + ".csv"
    filename_json = filename + ".json"

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
            Utils.Message.addMessage("__diskloggerThread() shutdownFlag caught. Ending thread")
            break
        try:
            # Check to see if the existing log files (if they exist) are below the max size threshold
            ret = Utils.archiveLogs(filename_csv, Registry.maximumLogFileSize_bytes)
            if ret == True:
                Utils.Message.addMessage("__diskloggerThread. " + str(filename_csv) + \
                                   " auto archived")
        except Exception as e:
            Utils.Message.addMessage("ERR:__diskloggerThread. " + str(filename_csv) + \
                                     " auto archive error")

        # elif ret == None:
        #     Utils.Message.addMessage("ERR:__diskloggerThread. " + str(filename_csv) + \
        #                        " auto archive error")
        # else:
        #     pass

        # Check to see if exporting of Events as JSON is enabled in Registry
        if Registry.enableJsonEventsLog:
            # If so, check size of existing JSON log file and archive if necessary
            try:
                ret = Utils.archiveLogs(filename_json, Registry.maximumLogFileSize_bytes)
                if ret == True:
                    Utils.Message.addMessage("__diskloggerThread. " + str(filename_json) + \
                                       " auto archived")
            except Exception as e:
                Utils.Message.addMessage("ERR:__diskloggerThread. " + str(filename_json) + \
                                         " auto archive error")

            # elif ret == None:
            #     Utils.Message.addMessage("ERR:__diskloggerThread. " + str(filename_json) + \
            #                        " auto archive error")
            # else:
            #     pass

        # Create a file and write a header (if necessary)
        # For the CSV file
        createLogFile(filename_csv, "Event summary")
        # For the Json file
        createLogFile(filename_json, "Event Log json file")

        # Query the API for the current streams list
        try:
            rtpStreamsList = ctrlAPI.getStreamsList()
            # Utils.Message.addMessage(f"diskloggerThread.rtpStreamsList{rtpStreamsList}")
            if len(rtpStreamsList) > 0:
                # Iterate over availableRtpRxStreamList looking for new events
                for streamDefinition in rtpStreamsList:
                    # Attempt to access rtpStream events list
                    # and create a sublist of the just the latest elements
                    try:
                        # Extract the streamID for the current stream definition
                        streamID = streamDefinition["streamID"]

                        # Check to see if this is a new stream
                        if streamID not in lastWrittenEventNoDict:
                            # The stream is not yet known, so add to lastWrittenEventNoDict and assign value 0, as we've
                            # not yet written any events to disk that correspond to this stream
                            lastWrittenEventNoDict[streamID] = 0
                        # Recall the lastWrittenEventNo for this streamID
                        lastWrittenEventNo = lastWrittenEventNoDict[streamID]

                        # Create API helper for the stream
                        streamAPI = Utils.APIHelper(port=streamDefinition["httpPort"])
                        # Get the most recent event no for the current stream
                        # If in TRANSMIT mode, this will fail if the RtpStreamResults object doesn't exist yet (because this
                        # api endpoint is only created once the TRANSMIT end has started receiving data back from the RECEIVE end
                        # Therefore, if this fails, fail silently
                        try:
                            latestEventNo = streamAPI.getRTPStreamEventListAsJson(recent=1)[0]["eventNo"]

                            # Now test latestEventNo to see if any new Events have appeared since we last checked
                            # Also check to see if the eventsList has been reset in the mean time. This could happen if the
                            # Receiver resets its stats/deletes a receive stream. In which case the event no's would restart
                            if latestEventNo < lastWrittenEventNo:
                                Utils.Message.addMessage(
                                    f"DBUG:__diskLoggerThread()Stats/Events for stream {streamID} reset by Receiver")
                                # If so, we'll need to re-add all the events from the events list.
                                # Signify this by setting unwrittenEventsCount to 'latestEventNo' for which the api will interpret as 'all events'
                                unwrittenEventsCount = latestEventNo

                            else:
                                # This is the default case, where the most recent events in allEvents are likely to have
                                # not been written to disk yet
                                # Calculate how many new (i.e not yet written to disk) events there in are in this
                                # RtpStream object
                                unwrittenEventsCount = latestEventNo - lastWrittenEventNo

                            # Now retrieve the unwritten events (if any) from the API to be written to disk
                            if unwrittenEventsCount > 0:
                                # If the feature is enabled, retrieve a list of the most recent Events as json
                                if Registry.enableJsonEventsLog:
                                    try:
                                        unwrittenEventsJson = streamAPI.getRTPStreamEventListAsJson(recent=unwrittenEventsCount)
                                        # Write the batch of Json Events to disk
                                        if len(unwrittenEventsJson) > 0:
                                            # Utils.Message.addMessage(f"Writing {len(unwrittenEventsJson)} Json Events")
                                            # unpack each json-encoded event (basically, a dict) back to a string and put in a list
                                            serialisedJson = [json.dumps(event) for event in unwrittenEventsJson]
                                            Utils.Message.addMessage(f"serialisedJson({len(serialisedJson)}){serialisedJson}")
                                            # Create a string of Json with the events separated by a newline
                                            eventsJsonString = "\n".join(serialisedJson) + "\n"
                                            # Open the file for writing
                                            file_json = open(filename_json, "a+")
                                            file_json.write(eventsJsonString)
                                            # Close the files
                                            file_json.close()
                                    except Exception as e:
                                        Utils.Message.addMessage(f"ERR:Corrupted Json EventsList?: unwrittenEventsCount:{unwrittenEventsCount}, "\
                                                    f"latestEventNo:{latestEventNo}, err: {e}")

                                try:
                                    # Retrieve a list of the most recent Events as CSV
                                    unwrittenEventsCSV = streamAPI.getRTPStreamEventListAsCSV(recent=unwrittenEventsCount)
                                    # Utils.Message.addMessage(f"unwrittenEventsCount: {unwrittenEventsCount}, lastWrittenEventNo:{lastWrittenEventNo}")

                                    # Write the batch of CSV Events to disk
                                    if len(unwrittenEventsCSV) > 0:
                                        # Utils.Message.addMessage(f"Writing {len(unwrittenEventsCSV)} CSV Events")
                                        # Create a string of CSV with the events separated by a newline
                                        eventsCSVString = "\n".join(unwrittenEventsCSV) + "\n"
                                        # Open the file for writing
                                        file_csv = open(filename_csv, "a+")
                                        file_csv.write(eventsCSVString)
                                        # Make a note of the last written event no against this stream id key
                                        lastWrittenEventNoDict[streamID] = latestEventNo
                                        # Close the files
                                        file_csv.close()
                                except Exception as e:
                                    # Possibly corrupted Eventlist, so skip this batch
                                    lastWrittenEventNoDict[streamID] = latestEventNo + 1
                                    Utils.Message.addMessage(f"ERR:Corrupted CSV EventsList? : unwrittenEventsCount:{unwrittenEventsCount}, "\
                                                    f"latestEventNo:{latestEventNo},  err: {e}")
                        except Exception as e:
                            # No response from API
                            # Utils.Message.addMessage(f"DBUG:EventsList unavailable (no response from RECEIVER? {e}", logToDisk=False)
                            pass

                    except Exception as e:
                        Utils.Message.addMessage(f"ERR: __diskLoggerThread: {e}")

            # Finally, compare the list of streams in lastWrittenEventNoDict with those in rtpStreamsList
            # If they are present in lastWrittenEventNoDict{} but not in rtpStreamsList[] thi probably means that
            # they have been unregistered from the streams directory (i.e deleted) therefore we should housekeep
            # lastWrittenEventNoDict{} and remove them

            # Create list of streamIDs from rtpStreamsList
            streamIDList = [stream["streamID"] for stream in rtpStreamsList]
            # Keep only the streamIDs from rtpStreamsList and diccard any other keys that might be in lastWrittenEventNoDict
            lastWrittenEventNoDict = {wantedKey: lastWrittenEventNoDict[wantedKey] for wantedKey in streamIDList}
        except Exception as e:
            Utils.Message.addMessage(f"ERR: __diskloggerThread. getStreamsList(): {e}")

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
    print("__diskloggerThread")


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
# The receiverInstance arg allows the UDPMessageSender object to access the udp socket created within receiverInstance
class UDPMessageSender(object):

    def __init__(self, receiverInstance, shutdownFlag):
        # Define some stats counters
        self.sendUDPThreadTxPacketCounter = 0
        self.sendUDPThreadMessageQueueSize = 0
        # Set max safe UDP tx size to 576 (based on this:-
        # https://www.corvil.com/kb/what-is-the-largest-safe-udp-packet-size-on-the-internet
        self.MAX_UDP_TX_LENGTH = 576
        self.rxInstance = receiverInstance
        self.txMessageQueue = receiverInstance.txQueue  # Retrieve the tx Queue created by the associated RtpPacketReceiver
        self.shutdownFlag = shutdownFlag


        # Check that udp socket is a valid socket by retrieving the receive port no it is bound to
        # This will be used as the 'source port' for all udp packets sent by __udpTransmitterThread
        try:
            # Retrieve port no from socket created by rtpReceiver instance associated with this transmitter
            self.UDP_RX_PORT = self.rxInstance.getSocket().getsockname()[1]
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
        # packetSkipCounter = 0 # Used ot deliberately introduced lost packet errors in the TX'd results stream
        while True:
            # Check status of shutdownFlag
            if self.shutdownFlag.is_set():
                # If down, break out of the endless while loop
                break
            # Poll the message queue to see if it contains any data to be sent
            # The txMessageQueue is a tuple of the form [byteString, destIPAddr, destport]

            # Get current size of self.txMessageQueue - note this may not be implemented on OSX
            try:
                self.sendUDPThreadMessageQueueSize = self.txMessageQueue.qsize()
            except:
                pass
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
                        # # skip a random packet
                        # if int(packetSkipCounter) % 50 == 0:
                        #     Utils.Message.addMessage("Skipping packet. currentuSecs " + str(packetSkipCounter))
                        #     pass
                        # else:
                        #     pass
                        # Calling getSocket() means that we'll always have the latest version of the socket, were it
                        # to be recreated by the corresponding RtpPacketReceiver
                        self.rxInstance.getSocket().sendto(pickledFragment, (txData_ipAddr, txData_udpPort))
                        # Increment the counter
                        self.sendUDPThreadTxPacketCounter += 1
                        # packetSkipCounter +=1
            # if Queue timed out without any data in it
            except Empty:
                pass
            except Exception as e:
                Utils.Message.addMessage("ERR:__udpTransmitterThread(" + str(self.UDP_RX_PORT) + \
                                         ").txMessageQueue.get() " + str(e))
        Utils.Message.addMessage("DBUG:__udpTransmitterThread(" + str(self.UDP_RX_PORT) + ") ending")


# Class to provide an HTTP Server/ web API
# Note, this Class also provides a stream directory service
# externalResourcesDict is a dictionary of external objects that ISPTestHTTPServer would like access to
class ISPTestHTTPServer(object):
    def __init__(self, operationMode=None, tcpListenPort=None, externalResourcesDict=None) -> None:
        super().__init__()
        self.operationMode = operationMode
        self.tcpListenPort = tcpListenPort
        # Dictionary to hold reference to the instances of useful external objects (eg the WhoIsResolver)
        self.externalResourcesDict = externalResourcesDict
        # Create a list of dicts to hold a list of Rtp Streams
        self.streamsList = []
        self.streamsListMutex = threading.Lock()
        # These keys are required for a stream to be added via the /streams/add POST method. Used for validation
        # Note: uses bytestrings because that is what the POST data is encoded as when it arrives
        self.streamRequiredKeys = [b"streamID", b"httpPort", b"streamType"]
        # The possible different type of Rtp Stream - defines valid URL paths
        self.availableStreamTypes = ["RtpGenerator", "RtpReceiveStream", "RtpStreamResults"]
        # # Creates a dummy stream entry and appends it to the streamsList
        # def createDummyStream(streamsList, streamType, streamID=random.randint(1000, 2000)):
        #     try:
        #         streamsList.append({"streamID":streamID,
        #                              "httpPort":Utils.TCPListenPortCreator().getNext(),
        #                              "streamType":streamType,
        #                              "timeCreated":datetime.datetime.now()
        #                              })
        #
        #
        #     except Exception as e:
        #         Utils.Message.addMessage("ERR: ISPTestHTTPServer.createDummyStream() " + str(e))
        # # Create a dummy stream(s)
        # streamID = random.randint(1000, 2000)
        # createDummyStream(self.streamsList, RtpReceiveStream.__name__, streamID=streamID)
        # createDummyStream(self.streamsList, RtpGenerator.__name__, streamID=streamID)
        # streamID = random.randint(1000, 2000)
        # createDummyStream(self.streamsList, RtpReceiveStream.__name__, streamID=streamID)
        # createDummyStream(self.streamsList, RtpGenerator.__name__, streamID=streamID)


        # Start a web server running on the specified port
        # If the port is nor specified at init, call Utils.TCPListenPortCreator.getNext()
        # to get the next free port
        if self.tcpListenPort is None:
            self.tcpListenPort = Utils.TCPListenPortCreator.getNext()

        self.tcpListernAddr = '127.0.0.1' # '' will listen on all interfaces but there is a startup delay
        # start an http server thread
        self.httpd = None
        self.httpServerThread = threading.Thread(target=self.__httpServerThread, args=())
        self.httpServerThread.daemon = False
        self.httpServerThread.setName("ISPTestHTTPServer:" + str(self.tcpListenPort))
        try:
            self.httpServerThread.start()
            # Give the thread time to start
            time.sleep(0.5)
            if self.httpServerThread.is_alive():
                # Server thread must have started
                pass
            else:
                raise Exception("ERR:self.httpServerThread.is_alive()=FALSE")
        except Exception as e:
            raise Exception(f"ERR:ISPTestHTTPServer.__init__() self.httpServerThread.start(),  {e}")


    # Gets the TCP listener port of the HTTP Server
    def getTCPPort(self):
        return self.tcpListenPort

    # Threadsafe method to append an item to the streamsList
    def appendToStreamsListOld(self, item):
        self.streamsListMutex.acquire()
        self.streamsList.append(item)
        self.streamsListMutex.release()

    # Threadsafe method to append a stream definition to the streamsList
    # Note this method checks first to see if an item in the list with the same streamId is already present.
    # If so, it will raise an Exception
    def appendToStreamsList(self, newItem, uniqueKeyCheck="streamID"):
        self.streamsListMutex.acquire()
        try:
            # create list of keys as specified by uniqueKeyCheck
            existingItems = [item[uniqueKeyCheck] for item in self.streamsList]
            # Now check to see if the item with the same streamID (or whatever key uniqueKeyCheck is set to) is already
            # present in existingItems[]
            if newItem[uniqueKeyCheck] in existingItems:
                # A stream Definition with this key value already exists - duplicate detected
                raise Exception(f"duplicate {uniqueKeyCheck} detected: {newItem[uniqueKeyCheck]}")
            else:
                # Otherwise, this stream is new so we can add it
                self.streamsList.append(newItem)
                # Release the mutex
                self.streamsListMutex.release()
        except Exception as e:
            # Release the mutex
            self.streamsListMutex.release()
            raise Exception(f"appendToStreamsList() item[{uniqueKeyCheck}], {e}")


    # Threadsafe method to remove an item from the streamsList
    def removeFromStreamsList(self, item):
        self.streamsListMutex.acquire()
        self.streamsList.remove(item)
        self.streamsListMutex.release()

    # Threadsafe method to get a filtered version of streamsList
    # If all args are 'None' i.e not set, it will return the whole list
    def getStreamByFilter(self, streamID=None, streamType=None, httpPort=None):
        # Get the currentlist of streams (via shallow copy, so that we can safely iterate over it)
        self.streamsListMutex.acquire()
        streamsList = list(self.streamsList)
        self.streamsListMutex.release()

        filteredStreamList = []
        try:
            # Utils.Message.addMessage("getStreamByID() streamID is" + str(requestedStreamID) + \
            #                          ", streamType is " + str(streamType))

            if httpPort is not None:
                # Filter by http port . This *should* only ever return a single result
                filteredStreamList = list(
                    filter(lambda stream: stream["httpPort"] == int(httpPort), streamsList))

            elif streamID is None and streamType is None:
                # No filtering specified, just return the entire list
                filteredStreamList = streamsList

            elif streamID is not None and streamType is None:
                # Filter by streamID
                # Utils.Message.addMessage("requestedStreamID is " + str(requestedStreamID) + ", streamType is None")
                filteredStreamList = list(
                    filter(lambda stream: stream["streamID"] == int(streamID), streamsList))

            elif streamID is None and streamType is not None:
                # Filter by streamType
                filteredStreamList = list(
                    filter(lambda stream: stream["streamType"] == streamType, streamsList))
            else:
                # filter by streamID and streamType
                filteredStreamList = list(
                    filter(lambda stream: stream["streamID"] == int(streamID) and
                                          stream["streamType"] == streamType, streamsList))

            return filteredStreamList
        except Exception as e:
            Utils.Message.addMessage("ERR:ISPTestHTTPServer.HTTPRequestHandler.getStreamtByID() " + str(e))
            return []

    def kill(self):
        # Kill the http server
        try:
            Utils.Message.addMessage("DBUG:ISPTestHTTPServer() Closing http server (on port " + \
                                     str(self.tcpListenPort) + ")")
            # Wrap the call to HTTPServer.shutdown() inside another thread - it can't call itself otherwise it will deadlock
            threading.Thread(target=self.httpd.shutdown, daemon=True).start()
        except Exception as e:
            Utils.Message.addMessage(
                "ERR:ISPTestHTTPServer() Closing http server (on port " + str(self.tcpListenPort) + ") " + str(e))
        # Confirm that the server thread has ended
        try:
            Utils.Message.addMessage("DBUG:ISPTestHTTPServer() Waiting for httpServerThread.join()")
            self.httpServerThread.join()
            Utils.Message.addMessage("DBUG:ISPTestHTTPServer() httpServerThread.join() completed")

        except Exception as e:
            Utils.Message.addMessage(
                "ERR:ISPTestHTTPServer() ISPTestHTTPServer() httpServerThread.join() (on port " + str(self.tcpListenPort) + ") " + str(e))

    # Causes a pop-up user message to be displayed via the UI.renderMessageBox() method
    def displayAlert(self, *args, **kwargs):
        try:
            # Get handle on UI instance
            ui = self.externalResourcesDict["ui"]
            # call the UI.showErrorDialogue() method
            ui.showErrorDialogue(*args, **kwargs)

        except Exception as e:
            raise Exception(f"ISPTestHTTPServer.displayPopupMessage() {e}")


    # Define a custom BaseHTTPRequestHandler class to handle HTTP GET, POST requests
    # Note: A new instance of this class is created with every HTTP request
    class HTTPRequestHandler(BaseHTTPRequestHandler):
        # Http server methods
        # For JSON, use contentType='application/json'
        def _set_response(self, responseCode=200, contentType='text/html'):
            self.send_response(responseCode)
            self.send_header('Content-type', contentType)
            self.end_headers()

        # Override log_message() to return *nothing*, otherwise the HTTP server will continually log all HTTP requests
        # See here: https://stackoverflow.com/a/3389505
        def log_message(self, format, *args):
            # Utils.Message.addMessage(f"ISPTestHTTPServer: {format%args}")
            pass

        # Override log_error(), otherwise the HTTP server will continually log all HTTP errors to stderr
        # See here: https://stackoverflow.com/a/3389505
        def log_error(self, format, *args):
            Utils.Message.addMessage(f"ERR:ISPTestHTTPServer.log_error(): {format % args}")
            # print(f"{format % args}")

        # # Split the url path into its component parts. Ignore the initial '/'
        # Returns a list
        def splitPath(self, completePath):
            pathList = str(completePath).split("/")[1:]
            # Strip off trailing '/' if there is one
            if pathList[-1] == '':
                pathList = pathList[:-1]  # Take all except the last item of the list
            return pathList

        # Re-encodes the incoming string as UTF and terminates with a '/n' character
        def formatResponse(self, input):
            output = (str(input) + "\n").encode('utf-8')
            return output


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
            parsedPostDataDict = Utils.mapURLQueryToFnArgs(post_data_dict)
            # Create list of mandatory args. *This will fail* if not al the keys are present in post_data_dict
            requiredArgsList = [parsedPostDataDict[key] for key in requiredArgKeysList]
            # Now create a sub-dict of the just the optional keys
            optionalArgsDict = Utils.extractWantedKeysFromDict(parsedPostDataDict, optionalArgKeysList)
            # Finally remove the 'expected' keys from parsedPostDataDict to see if any unexpected keys are left over
            Utils.removeMultipleDictKeys(parsedPostDataDict, requiredArgKeysList + optionalArgKeysList)
            if len(parsedPostDataDict) > 0:
                raise Exception(f"convertKeysToMethodArgs() unexpected keys provided {parsedPostDataDict}"\
                            f" Permitted optional keys are: {optionalArgKeysList},"\
                            f"mandatory keys are: {requiredArgKeysList}")
            return requiredArgsList, optionalArgsDict


        def do_GET(self):
            # Split the path into a list
            pathList = self.splitPath(self.path)
            # Get the number of 'steps' in the path
            pathLen = len(pathList)
            # Utils.Message.addMessage("DBUG:ISPTestHTTPServer.do_GET() request: " + ", " + "Path: " + str(self.path) + ", len: " + str(pathLen))
            # Utils.Message.addMessage("pathList:" + str(pathList))
            # Index to iterate over the path steps
            pathIndex = 0
            currentStep = None

            # Previous states to be captured as the path is traversed and parsed
            filterType = None
            filteredList = []
            requestedStream = None
            streamCommand = None

            # Specify default or 'index' page
            response = self.formatResponse("isptest http server")

            # Traverse the steps of the path, parsing each step in sequence
            try:
                if pathLen == 0:  # Was / requested (i.e no path)?
                    self._set_response()

                # Else if there are subfolders in the path
                while pathIndex < pathLen: # Will execute if pathlen > 0
                    currentStep = pathList[pathIndex]   # Get the current step
                    if str(currentStep).startswith("streams"):        # Test the path step
                        if pathIndex == pathLen - 1:    # Is this the last step of the path
                            # /streams
                            # Split of the URL and query (?key=value suffixes)
                            urlDecoded = urlparse(self.path)
                            path = urlDecoded.path
                            query = urlDecoded.query
                            # Parse query to create a list of optional parameters to be passed to targetMethod()
                            # Note: Since this is a GET, we don't specify any requiredArgKeys, just optionalArgKeys
                            # This method will raise an exception if any unexpected query args are present
                            notUsed, optionalArgs = self.convertKeysToMethodArgs(query, [],
                                                            ["streamID", "streamType", "httpPort"])

                            # Return the entire list of streams without any filtering
                            response = (json.dumps(self.server.parentObject.getStreamByFilter(**optionalArgs),
                                                   sort_keys=True, indent=4, default=str) + "\n").encode('utf-8')
                            # Create the headers
                            self._set_response(contentType='application/json')
                            break # Break out of while loop
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif str(currentStep).startswith("log"):
                        # GET /log
                        # Retreive log messages
                        messagesList = Utils.Message.getMessages()
                        # Reverse the list (most recent first)
                        messagesList.reverse()
                        # format messages into an html table
                        messageTable = "<table>"
                        for message in messagesList:
                            # Create an html table row containing timestamp and message columns
                            messageTable += "<tr><td>" + message[0].strftime("%Y:%m:%d-%H:%M:%S ") + "</td><td>" + \
                                        message[1] + "</td></tr>"
                        messageTable += "</table>"
                        # Convert the messageTable to ASCII with /n characters etc...
                        response = Utils.formatHttpResponse(messageTable)
                        # Create the headers
                        self._set_response()

                    # Compare streams
                    elif str(currentStep).startswith("compare"):
                        # GET /compare Optional args: ?listOrder=True&includeSyncSourceID=True
                        try:
                            if pathIndex == pathLen - 1:  # Is this the last step of the path
                                # Split of the URL and query (?key=value suffixes)
                                urlDecoded = urlparse(self.path)
                                path = urlDecoded.path
                                query = urlDecoded.query
                                # Parse query to create a list of optional parameters to be passed to targetMethod()
                                # Note: Since this is a GET, we don't specify any requiredArgKeys, just optionalArgKeys
                                # This method will raise an exception if any unexpected query args are present
                                optionalArgsList = ["listOrder", "includeSyncSourceID"]
                                unexpectedArgs, kwargs = self.convertKeysToMethodArgs(query, [], optionalArgsList)
                                # Create a RtpStreamComparer object. Pass the list of available streams to it
                                rtpStreamComparer = RtpStreamComparer(self.server.parentObject.getStreamByFilter())

                                # Specify the default list of stats keys that will be compared with each other
                                statsKeysToBeCompared = Registry.criteriaListForCompareStreams
                                # Generate a 'stream comparison' report
                                response = rtpStreamComparer.generateReport(statsKeysToBeCompared, **kwargs).encode('utf-8')
                                # Create the headers
                                self._set_response(contentType='text/plain')
                                break  # Break out of while loop
                            else:
                                # More steps yet to be parsed, let the loop continue
                                pass
                        except Exception as e:
                            raise Exception(f"do__GET() /compare err {str(e)}")

                    elif str(currentStep).startswith("whois"):
                        # GET /whois?0=1.2.3.4&2=2.3.4.
                        # Takes an indexed list of ip addresses and queries them with the WhoIs Resolver.
                        # It then returns a json encoded list of tuples containing [ip address, whois_name]
                        if pathIndex == pathLen - 1:  # Is this the last step of the path
                            try:
                                # parse the GET query as a list
                                getQueryList = parse_qsl(urlparse(self.path).query)  # Extract just the query
                                # Utils.Message.postMessage(f"do_GET/whois {get_query}",
                                #                           tcpPort=self.server.parentObject.tcpListenPort)
                                # Iterate over the list of addresses to be looked up
                                if len (getQueryList) > 0:
                                    outputList = [] # A list of tuples containing [ip addr, whois name]
                                    # Now iterate over the list of ip addresses looking up each one in turn
                                    for hopNo in range(len(getQueryList)):
                                        # Extract the ip address
                                        hopAddr=getQueryList[hopNo][1]
                                        whoisNetName = ""
                                        # Get handle on WhoIsResolver instance (if it exists)
                                        if "whoIsResolver" in self.server.parentObject.externalResourcesDict:
                                            whoIsResolver = self.server.parentObject.externalResourcesDict["whoIsResolver"]
                                            # Query the Whois Resolver for that name
                                            whoisResult = whoIsResolver.queryWhoisCache(hopAddr)
                                            if whoisResult is not None:
                                                whoisNetName = " " + whoisResult[0]['asn_description']
                                        else:
                                            Utils.Message.addMessage(f"DBUG:WhoIsResolver unavailable")

                                        outputList.append([hopAddr, whoisNetName])
                                    # Encode the list as json
                                    response = (json.dumps(outputList, sort_keys=True, indent=4,
                                                           default=str) + "\n").encode('utf-8')
                                    # Create the headers
                                    self._set_response(contentType='application/json')

                                else:
                                    response = Utils.formatHttpResponse(f"do_GET/whois -- no data")
                                    # Create the headers
                                    self._set_response()
                                break  # Break out of while loop

                            except Exception as e:
                                raise Exception(f"do__GET() /whois err {str(e)}")
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep in self.server.parentObject.availableStreamTypes:
                        # /streams/RtpGenerator or /streams/RtpReceiveStream or /streams/RtpStreamResults
                        filterType = currentStep # Capture the current streamType
                        if pathIndex == pathLen - 1:    # Is this the last step of the path
                            filteredList = self.server.parentObject.getStreamByFilter(streamType=filterType)
                            # Return a list of streams filtered by type
                            response = (json.dumps(filteredList,
                                                   sort_keys=True, indent=4, default=str) + "\n").encode('utf-8')
                            # Create the headers
                            self._set_response(contentType='application/json')
                            break  # Break out of while loop
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep.isnumeric():  # Check to see if the 3rd step is an integer (streamID specifier)
                        # Filter by streamID and (previously stored) streamType
                        # /streams/[streamType]/[streamID]
                        filteredList = self.server.parentObject.getStreamByFilter(requestedStreamID=currentStep, streamType=filterType)
                        if len(filteredList) > 0:
                            # Requested stream exists
                            if pathIndex == pathLen - 1:  # Is this the last step of the path
                                # Return the streamsList entry for the reqeusted stream
                                response = (json.dumps(filteredList,
                                                       sort_keys=True, indent=4, default=str) + "\n").encode('utf-8')
                                # Create the headers
                                self._set_response(contentType='application/json')
                                break  # Break out of while loop
                            else:
                                # Still more steps to parse, store the stream
                                requestedStream = filteredList[0]
                        else:
                            # Stream couldn't be found (or invalid path)
                            raise Exception

                    # elif currentStep starts with "stats", "events":
                    elif currentStep.startswith(("stats", "events")):
                        # Request the stats/events for the selected stream
                        # /streams/[streamType]/[streamID]/[command]
                        # Requested stream exists
                        if pathIndex == pathLen - 1:  # Is this the last step of the path?
                            if currentStep.startswith("stats"):
                                response = self.formatResponse("stats " + str(currentStep) + " for event: " + str(requestedStream))
                                # Create the headers
                                self._set_response()
                                break  # Break out of while loop
                            elif currentStep.startswith("events"):
                                # Extract any additional query components (if present)
                                query_components = parse_qs(urlparse(self.path).query)
                                response = self.formatResponse("events " + str(currentStep) + "for event: " + \
                                                               str(requestedStream) + ", " + str(query_components))
                                # Create the headers
                                self._set_response()
                                break  # Break out of while loop

                            else:
                                raise Exception
                        else:
                            # Still more steps to parse, store the command addressed to this stream. Might be useful later
                            streamCommand = currentStep

                    else:
                        # Catchall
                        raise Exception
                    # Increment the step counter
                    pathIndex += 1

                # Write the response back to the client
                self.wfile.write(response)
            except Exception as e:
                Utils.Message.addMessage(
                    "ERR:ISPTestHTTPServer.do_GET() request: " + ", " + "Path: " + str(self.path) + ", len: " + str(
                        pathLen) + ", Error:" + str(e))
                try:
                    self.send_error(404, str("path " + str(self.path) + ", current step: " + str(currentStep) + ", " + str(e)))
                except:
                    # Fail silently - otherwise the sending of an error message might actual cause another Exception
                    pass
            

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])  # <--- Gets the size of data
            post_data_raw = self.rfile.read(content_length)  # <--- Gets the data itself as a string ?foo=bar&x=y etc..
            post_data_dict = parse_qs(post_data_raw) # parse the post data and convert to a dict

            # Utils.Message.addMessage("DBUG:do_POST(), Path: " + str(self.path) + ", data: " + str(post_data_dict))

            # Parse the path
            # Split the path into a list
            pathList = self.splitPath(self.path)
            pathLen = len(pathList)
            # Utils.Message.addMessage("pathList:" + str(pathList))

            # Index to iterate over the path steps
            pathIndex = 0
            currentStep = None
            # availableStreamTypesList = ["RtpGenerator", "RtpReceiveStream", "RtpStreamResults"]

            # Previous states to be captured as the path is traversed and parsed
            # filterType = None
            # requestedStream = None

            # Specify default or 'index' page
            response = self.formatResponse("isptest http server")

            # Traverse the steps of the path, parsing each step in sequence
            try:
                while pathIndex < pathLen:
                    currentStep = pathList[pathIndex]  # Get the current step
                    if currentStep == "log":
                        # add a new message to the logger
                        # POST /log {message:"", logToDisk:bool}
                        if pathIndex == pathLen - 1:  # Is this the last step of the path
                            response = Utils.formatHttpResponse(f"{self.path}, {post_data_dict}")
                            try:
                                # Extract message
                                message = str(post_data_dict[b"message"][0].decode('UTF-8'))

                                # Is the logToDisk key present in the POST
                                logToDiskFlag = True # default value if not present
                                if b"logToDisk" in post_data_dict:
                                    logToDiskFlag = str(post_data_dict[b"logToDisk"][0].decode('UTF-8'))
                                    if logToDiskFlag in ["False", "false", "0", "no", "No"]:
                                        logToDiskFlag = False

                                # Add the message
                                Utils.Message.addMessage(message, logToDisk=logToDiskFlag)
                            except Exception as e:
                                raise Exception(f"do__POST() /log {post_data_dict}, err {str(e)}")

                            # Set the headers
                            self._set_response(responseCode=201)
                            break  # Break out of while loop

                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep == "streams":  # Test the path step
                        if pathIndex == pathLen - 1:  # Is this the last step of the path
                            raise Exception("Can't POST to this path")
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep == "add":  # Test the path step
                        # add a new stream to streamsList
                        # /streams/add
                        if pathIndex == pathLen - 1:  # Is this the last step of the path

                            response = self.formatResponse("Add using " + str(post_data_dict))
                            # Check that all the required keys are in the fields dict
                            # requiredKeys = [b"streamID", b"httpPort", b"streamType", b"timeCreated"]

                            for key in self.server.parentObject.streamRequiredKeys:
                                if key not in post_data_dict:
                                    errorText = "ERR:streams/add key " + str(key) + " missing. Cannot add stream"
                                    Utils.Message.addMessage(errorText)
                                    raise Exception(errorText)

                            # Append the new Rtp Stream to the streamsList[]
                            # NOTE: each value of incoming data is a list of strings encoded in UTF-8
                            try:
                                self.server.parentObject.appendToStreamsList({"streamID": int(post_data_dict[b"streamID"][0]),
                                                    "httpPort": int(post_data_dict[b"httpPort"][0]),
                                                    "streamType": str(post_data_dict[b"streamType"][0].decode('UTF-8')),
                                                    "timeCreated": datetime.datetime.now()
                                                })
                            except Exception as e:
                                errorText = "ERR:HTTPRequestHandler.do_POST() Failed to append stream: " + str(e)
                                Utils.Message.addMessage(errorText)
                                raise Exception(errorText)

                            # Set the headers
                            self._set_response(responseCode=201)
                            break  # Break out of while loop
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep == "alert":  # Test the path step
                        # Causes a popup message box to be displayed (via the UI.showErrorDialogue() method)
                        # POST /alert?title=some_title&body=some_message_text
                        try:
                                # # Parse query to create a list of optional parameters to be passed to displayAlert()
                                # # This method will raise an exception if any unexpected query args are present
                                reqArgs, optionalArgs = self.convertKeysToMethodArgs(post_data_raw.decode('UTF-8'), ["title", "body"],[])
                                response = f"do_POST /alert reqArgs:{reqArgs}".encode('utf-8')
                                self.server.parentObject.displayAlert(reqArgs[0], reqArgs[1])
                                # Create the headers
                                self._set_response()

                        except Exception as e:
                                raise Exception(f"do__POST() /alert {str(e)}")
                    else:
                        # Catchall
                        raise Exception("Can't POST to this path")
                    # Increment the step counter
                    pathIndex += 1

                # Write the response back to the client
                self.wfile.write(response)
            except Exception as e:
                Utils.Message.addMessage("ERR:ISPTestHTTPServer.do_ Post():" + \
                                         ", Error:" + str(e))
                try:
                    self.send_error(404,
                            str("do_POST() path " + str(self.path) + ", current step: " + str(currentStep) + ", " +\
                                 str(self.headers) + ", " + str(e)))
                except:
                    # Fail silently - otherwise the sending of an error message might actual cause another Exception
                    pass

        def do_DELETE(self):
            Utils.Message.addMessage("DBUG:ISPTestHTTPServer.do_DELETE() " + str(self.path))
            # Parse the path
            # Split the path into a list
            pathList = self.splitPath(self.path)
            pathLen = len(pathList)
            # Utils.Message.addMessage("pathList:" + str(pathList))

            # Index to iterate over the path steps
            pathIndex = 0
            currentStep = None

            # Previous states to be captured as the path is traversed and parsed
            filterType = None
            requestedStream = None

            # Specify default or 'index' page
            response = self.formatResponse("isptest http server")
            # Traverse the steps of the path, parsing each step in sequence
            try:
                while pathIndex < pathLen:
                    currentStep = pathList[pathIndex]  # Get the current step
                    if currentStep == "streams":  # Test the path step
                        if pathIndex == pathLen - 1:  # Is this the last step of the path
                            raise Exception("do_DELETE()/streams")
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep == "delete":  # Test the path step
                        # Remove an existing stream from  streamsList
                        # /streams/delete
                        if pathIndex == pathLen - 1:  # Is this the last step of the path
                            # Not enough info, we need the streamType and the streamID
                            raise Exception("do_DELETE()/streams/" + str(currentStep))
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep in self.server.parentObject.availableStreamTypes:
                        # /streams/delete/[streamType]
                        # Capture the streamType for future use
                        filterType = currentStep
                        if pathIndex == pathLen - 1:  # Is this the last step of the path
                            # Not enough info, we still need the streamID
                            raise Exception("do_DELETE()/streams/delete/" + str(currentStep))
                        else:
                            # More steps yet to be parsed, let the loop continue
                            pass

                    elif currentStep.isnumeric():  # Check to see if the 4thd step is an integer (streamID specifier)
                        # Filter by streamID and (previously stored) streamType
                        # /streams/delete/[streamType]/[streamID]
                        # Have to ensure that filterType has been specified, otherwise we could delete the wrong Rtp Stream
                        # (if it shares the same id no)
                        if filterType is not None:
                            filteredList = self.server.parentObject.getStreamByFilter(streamID=currentStep,
                                                                                      streamType=filterType)
                        else:
                            raise Exception("do_DELETE()/streams/delete/" + str(filterType) + "/" + str(currentStep) +\
                                            " -- No streamType set")

                        if len(filteredList) > 0:
                            # Requested stream exists so we know we can delete it
                            if pathIndex == pathLen - 1:  # Is this the last step of the path
                                msg = str(filterType) + " " + str(currentStep) + " to be removed from streams directory"
                                try:
                                    # Remove the stream from the list
                                    self.server.parentObject.removeFromStreamsList(filteredList[0])
                                    Utils.Message.addMessage(msg)
                                    response = self.formatResponse(msg)
                                    self._set_response()
                                    break # Break out of while loop
                                except Exception as e:
                                    raise Exception(str(e))
                            else:
                                # Still more steps to parse, store the stream
                                requestedStream = filteredList[0]
                        else:
                            # Stream couldn't be found (or invalid path)
                            raise Exception("do_DELETE()/streams/delete/ no such stream could be found " + str(filterType) + "/" + str(currentStep))

                    else:
                        # Catchall
                        raise Exception ("do_DELETE()/" + str(currentStep))

                    # Increment the step counter
                    pathIndex += 1

                # Write the response back to the client
                self.wfile.write(response)
            except Exception as e:
                Utils.Message.addMessage("ERR:ISPTestHTTPServer.do_DELETE() " + str(self.path) + ", " + str(e))
                try:
                    self.send_error(404,
                                str("do_DELETE() path " + str(self.path) + ", current step: " + str(
                                    currentStep) + ", " + str(e)))
                except:
                    # Fail silently - otherwise the sending of an error message might actual cause another Exception
                    pass


    def __httpServerThread(self):
        # Utils.Message.addMessage("DBUG: start " + str(self.__stats["stream_syncSource"]) + ":httpServerThread")
        try:
            # This call will block
            self.httpd = Utils.CustomHTTPServer((self.tcpListernAddr, self.tcpListenPort), ISPTestHTTPServer.HTTPRequestHandler)
            Utils.Message.addMessage(f"DBUG: Creating ISPTestHTTPServer, listening on TCP port " + str(self.tcpListenPort))
            # Pass this object instance to the server
            self.httpd.setParentObjectInstance(self)
            # Start the http server
            self.httpd.serve_forever()
            Utils.Message.addMessage(f"DBUG:Stream ISPTestHTTPServer serve_forever() returned")

        except Exception as e:
            Utils.Message.addMessage(f"ERR:__httpServerThread() Failed to start ISPTestHTTPServer(port {self.tcpListenPort}), {e}")

        Utils.Message.addMessage(f"DBUG: ISPTestHTTPServer(port {self.tcpListenPort}) ended")


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

def main(argv):
    # Function to test the ProcessCreator class
    def testProcessCreator():
        args = [
            "192.168.3.18",
            2001,
            1024 * 128,
            1300,
            12345,
            -1,
        ]
        kwargs = {
            "controllerTCPPort": None
        }
        # attempt to create a subprocess
        try:
            rtpGeneratorSubProcess = Utils.ProcessCreator(RtpGenerator, *args, processName="subprocess_test", **kwargs)
        except Exception as e:
            print(f"Couldn't create subprocess {e}")
            exit(0)
        while True:
            pid = rtpGeneratorSubProcess.getProcess().pid
            name = rtpGeneratorSubProcess.getProcess().name
            is_Alive = rtpGeneratorSubProcess.getProcess().is_alive()
            print(f"datetime.datetime.now() {pid}, {name}, isAlive:{is_Alive}")
            time.sleep(5)


    def mpTest():
        # Create a multiprocess queue
        x = mp.Queue()
        testObj = Utils.TestClass()
        x.put(testObj)
        while True:
            try:
                print(f"x: {x.get(timeout=2).getValues()}")
            except Empty:
                print("Empty")
                break


    def nestedMPTest():
        # Create TestClass as a child process
        proc = Utils.ProcessCreator(Utils.TestClass, processName="testClass")
        while True:
            print ("main alive")
            time.sleep(1)

    ###### THIS IS IMPORTANT - It works!
    def RxStreamCreatorTest():
        # define mp queue
        newStreamsPending = mp.Queue()
        obj = Utils.ProcessCreator(Utils.RxStreamDetector, newStreamsPending, processName="Utils.MPQueueTest")
        x = 40
        while x > 0:
            try:
                val = newStreamsPending.get(timeout=1)

                print(f"main() Creating new RxStream object with id {val['id']}")
                rxStream = Utils.ProcessCreator(Utils.RxStream, val['id'], val['txQueue'],
                                                val['rxQueue'], val['streamsPendingDeletionQueue'])

            except Empty:
                # print(f"main() newStreamsPending Empty")
                pass
            except Exception as e:
                print(f"ERR:main() {e}")
            x -= 1
            time.sleep(0.5)
        print("main() ending")

    def txRxTransceiverTest():
        # define mp queue
        newStreamsPending = mp.Queue()
        obj = Utils.ProcessCreator(Utils.TransceiverSimulator, newStreamsPending, processName="Utils.TransceiverSimulator")
        x = 40
        while x > 0:
            try:
                val = newStreamsPending.get(timeout=1)

                print(f"main() Creating new RxStream object with id {val['id']}")
                rxStream = Utils.ProcessCreator(Utils.RxStream, val['id'], val['txQueue'],
                                                val['rxQueue'], val['streamsPendingDeletionQueue'])

            except Empty:
                # print(f"main() newStreamsPending Empty")
                pass
            except Exception as e:
                print(f"ERR:main() {e}")
            x -= 1
            time.sleep(0.5)
        print("main() ending")


    # Check if this is running on OSX. If so, need to use 'spawn' as the multiprocessor start method
    if Utils.getOperatingSystem() == "Darwin":
        print("OSX Detected, using 'spawn' multiprocess start method")
        mp.set_start_method('spawn')  # Specifies how the OS creates sub-processes. Safest option for all OSs

    # Enable multiprocessor debugging to stderr
    enableMultiProcessorLoggingToStdERR = False
    if enableMultiProcessorLoggingToStdERR:
        mp.log_to_stderr(logging.DEBUG)

    # RxStreamCreatorTest()
    # txRxTransceiverTest()
    # exit()
    # nestedMPTest()

    # mpTest()


    # testProcessCreator()
    # testObject = Utils.TestObject()
    #
    # saveStatus = Utils.exportObjectToDisk(testObject)
    # if saveStatus is True:
    #     importedObject = Utils.importObjectFromDisk()
    #     try:
    #         print(str(importedObject.getMyDict()))
    #     except Exception as e:
    #         print("import failure: " + str(e))
    # else:
    #     print("export failure " + str(saveStatus))
    # exit()

    # String to specify which operation mode we're in (loopback, tx, rx)
    MODE = ""

    # Additonal Operation Mode flag for 'special features'
    specialFeaturesModeFlag = False
    # Used to automatically add n TX streams (used for load testing)
    autoGenerateStreams = 0

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
        # -z [n] Enable special features (like simulate packet loss, jitter, auto add n streams
        # -o obscure (disguise) the Rtp packets by inserting an offset between the UDP and RTP headers. NOTE: Must be
        # set on both the transmitter and receiver



        address = ""

        # Check for no no option supplied:
        if len (argv) < 1:
            print ("No options supplied. Use -h for help")
            exit()

        opts, args = getopt.getopt(argv, "hxt:r:i:t:b:d:s:u:l:v:z:n:o")

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
                print("-o obscure (disguise) the Rtp packets by inserting an offset between the\r")
                print("UDP and RTP headers. NOTE: Must be set on both the transmitter and receiver\r")
                print("\r")
                print ("-z [n] Enable special features (like simulate packet loss, jitter etc)\r")
                exit()

            elif opt == '-o':
                Registry.rtpHeaderOffsetString = "dfhsdfkjhsbkfsdfegrsb".encode('utf-8')
                print("RTP 'Disguise' mode enabled")

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
                # Specify message verbosity (to hide warning messages)
                try:
                    # Test for an int
                    arg = int(arg) + 1 - 1
                    autoGenerateStreams = int(arg)
                    # assign the value
                    print (f"Auto Generate {arg} streams")
                except:
                    print("Invalid -z autoGenerateStreams value supplied. " + str(arg))
                    exit()

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

    # Create a list to hold the UDP receive addresses and ports
    # This will be a list of dicts [{"addr", "port}, {},...]
    # It will be passed to the UI object to allow the UI to access the port no.s in use
    receiveAddrList = []

    # Register signal handler for SIGINT, SIGTERM and SIGKILL
    signal.signal(signal.SIGINT, requestShutdownSignalHandler) # Ctrl-C
    signal.signal(signal.SIGTERM, shutdownApplicationSignalHandler)    # OS kill signal


    # Create a UI object (which will spawn a renderDisplay and catchKeyboardPresses thread)
    # Create flag that will be used by UI to signal back to main() that a shutdown has been requested
    # shutdownFlag = mp.Event()

    rtpPacketTransceiverShutdownFlag = mp.Event()

    # diskLogger gets its own shutdownFlag because we want it to be the last thread to end (so we can get error messages
    # until the very last moment)
    diskLoggerShutdownFlag = mp.Event()

    # Create dict to hold a list of Object instances that will be shared
    sharedObjects = {}

    # Create a dict to hold a list of child processes spawned (keyed by the pid of the process)
    # This is a dict of dicts {"process", "name"}
    processesCreatedDict = {}
    # Register processesCreatedDict with the sharedObjects dict
    sharedObjects["processesCreatedDict"] = processesCreatedDict

    # # Create new instance of WhoisResolver (which will create a background __whoisLookupThread)
    # whoIsResolver = Utils.WhoisResolver()
    # # Register whoIsResolver with the shared objects dict
    # sharedObjects = {"whoIsResolver": whoIsResolver}
    # Create and start the main HTTP Server
    isptesttHTTPServerPort = None # Default value. Will be specified in Registry
    try:
        # Establish what port the http server should be running on
        # Note, if this port is unavailable, The HTTP server should pick up the next available port
        if MODE == "RECEIVE":
            isptesttHTTPServerPort = Registry.httpServerRtpReceiverTCPPort
        elif MODE == "TRANSMIT":
            isptesttHTTPServerPort = Registry.httpServerRtpTransmitterTCPPort
        else:
            isptesttHTTPServerPort = Utils.TCPListenPortCreator.getNext()

        # Create the server object
        isptesttHTTPServer = ISPTestHTTPServer(operationMode=MODE, tcpListenPort=isptesttHTTPServerPort,
                                               externalResourcesDict=sharedObjects)
        # Get the actual TCP listener port from the ISPTestHTTPServer object itself
        isptesttHTTPServerPort = isptesttHTTPServer.getTCPPort()
        Utils.Message.addMessage(f"isptesttHTTPServer successfully started on port {isptesttHTTPServerPort}")
    except Exception as e:
        Utils.Message.addMessage("ERR:isptesttHTTPServer = ISPTestHTTPServer() " + str(e))
        print(f"ERR:Failed to start HTTP Server on port {isptesttHTTPServerPort}. Perhaps the port is already in use? "
              f"See {Utils.Message.getOutputFileName()} for clues:\n{e}")
        exit(1)

    # # Create a UI flag that will allow the UI thread to be woken up (to force a redraw)
    # wakeUpUI = threading.Event()

    # Create new instance of WhoisResolver (which will create a background __whoisLookupThread)
    whoIsResolver = Utils.WhoisResolver()
    # and add it to the shared objects dict (so that HTTP Server will have access to it)
    sharedObjects["whoIsResolver"] = whoIsResolver

    # Create a UI object (that spawns its own thread)
    # ui = UI(MODE, specialFeaturesModeFlag, receiversAndSendersList, controllerTCPPort=isptesttHTTPServerPort)
    ui = UI(MODE, specialFeaturesModeFlag, receiveAddrList,
            controllerTCPPort=isptesttHTTPServerPort, processesCreatedDict=processesCreatedDict)
    # and add it to the shared objects dict (so that HTTP Server will have access to it)
    sharedObjects["ui"] = ui

    # Create a diskLogging Thread - This thread polls the available streams EventsLists and logs then to a file
    diskLoggerThread = threading.Thread(target=__diskLoggerThread, args=(MODE, diskLoggerShutdownFlag, isptesttHTTPServerPort,))
    diskLoggerThread.daemon = True  # Thread will auto shutdown when the prog ends
    diskLoggerThread.setName("__diskLoggerThread")
    diskLoggerThread.start()

#################### <<<<< Mode override
    # Start traffic generator thread
    if MODE == 'LOOPBACK' or MODE == 'TRANSMIT':
        # Attempt to create an RtpGenerator based on the supplied parameters as a child process
        try:
            rtpGenerator = mp.Process(target=RtpGenerator,
                                      args=(UDP_TX_IP, UDP_TX_PORT, txRate,
                                        payloadLength, SYNC_SOURCE_ID, txStreamTimeToLive_sec),
                                      kwargs={"UDP_SRC_PORT":UDP_TX_SRC_PORT, "friendlyName":RTP_TX_STREAM_FRIENDLY_NAME,
                                        "controllerTCPPort":isptesttHTTPServerPort},
                                      name=f"RtpGenerator({SYNC_SOURCE_ID})",
                                      daemon=False)
            rtpGenerator.start()
            # Add the new RtpGenerator child process to processesCreatedDict so it can be tracked
            try:
                Utils.addToProcessesCreatedDict(processesCreatedDict, rtpGenerator)
            except Exception as e:
                Utils.Message.addMessage(f"ERR:main() add RtpGenerator({SYNC_SOURCE_ID}) process to processesCreatedDict, {e}")
        except Exception as e:
            Utils.Message.addMessage("ERR:main() Create RtpGenerator() " + str(e))

        try:
            # If special features mode is set and a value is specified, automatically add additional streams
            # based on the initial tx stream specifiers
            # Special features mode (-z n where n is the number of streams to be auto generated)
            if specialFeaturesModeFlag and autoGenerateStreams > 0:
                for n in range(autoGenerateStreams):
                    # Increment the SYNC_SOURCE_ID for the next auto-generated stream
                    SYNC_SOURCE_ID += 1
                    friendlyName = f"Auto{n+1}of{autoGenerateStreams}"

                    rtpGenerator = mp.Process(target=RtpGenerator,
                                              args=(UDP_TX_IP, UDP_TX_PORT, txRate,
                                                    payloadLength, SYNC_SOURCE_ID, txStreamTimeToLive_sec),
                                              kwargs={"UDP_SRC_PORT": UDP_TX_SRC_PORT,
                                                      "friendlyName": friendlyName,
                                                      "controllerTCPPort": isptesttHTTPServerPort},
                                              name=f"RtpGenerator({SYNC_SOURCE_ID})",
                                              daemon=False)
                    rtpGenerator.start()
                    # Add the new RtpGenerator child process to processesCreatedDict so it can be tracked
                    try:
                        Utils.addToProcessesCreatedDict(processesCreatedDict, rtpGenerator)
                    except Exception as e:
                        Utils.Message.addMessage(
                            f"ERR:main() add RtpGenerator({SYNC_SOURCE_ID}) process to processesCreatedDict, {e}")

        except Exception as e:
            Utils.Message.addMessage("ERR:main() Auto generate RtpGenerator() " + str(e))


    # Main program execution loops

    # Define a local function that will perform a graceful shutdown of all threads and resources
    def shutdownApplication():
        Utils.Message.addMessage("main.shutdownApplication() called")
        # # Cause RtpPacketReceiver(s) to shut down - this will stop the rxQueues being filled
        # shutdownFlag.set()

        # Special case. If in RECEIVE mode, take a snapshot of all the Events lists and stats[] dictionaries, for
        # saving to disk
        if MODE == 'RECEIVE':
            # Signal RtpPacketTransceiver to shut down
            rtpPacketTransceiverShutdownFlag.set()
            try:
                streamsExportedCounter = Utils.createStreamsSnapshot(Registry.streamsSnapshotFilename,
                                                                     isptesttHTTPServerPort)
                Utils.Message.addMessage(f"Created snapshot for {streamsExportedCounter}"
                                         f" streams to file {Registry.streamsSnapshotFilename}")
            except Exception as e:
                Utils.Message.addMessage(f"ERR:Export streams snapshot failure (on shutdown) {e}")


        # Attempt to remove all rtp stream objects (be they RtpGenerators (which themselves reference RtpStreamresults objects)
        # Get a list of streams and send the delete method to each in turn
        try:
            streamsList = Utils.APIHelper(isptesttHTTPServerPort).getStreamsList()


            # Iterate over streamsList to send an HTTP DELETE via the api
            for stream in streamsList:
                try:
                    # send an HTTP DELETE to each object, to cause it to die
                    Utils.APIHelper(stream["httpPort"]).deleteByURL("/delete")
                except Exception as e:
                    pass
                    # Utils.Message.addMessage(f"main.shutdownApplication() HTTP DELETE streams {e}")
        except Exception as e:
            Utils.Message.addMessage(f"ERR:main.shutdownApplication() HTTP DELETE streams {e}")

        # Allow time for the streams to deregister themselves
        time.sleep(0.5)
        # Now wait for the streamsList to be empty (i.e have all the stream objects de-registered themselves),
        # before continuing with the shutdown process
        prevStreamsRemainingCounter = 0
        stalledStreamsThreshold = 5 # The no of loops to tolerate if streamsRemainingCounter is not decrementing - used as a timeout
        streamsList = []
        while stalledStreamsThreshold > 0:
            # update streamsList
            try:
                streamsList = Utils.APIHelper(isptesttHTTPServerPort).getStreamsList()
            except Exception as e:
                Utils.Message.addMessage(f"main.shutdownApplication() Wait for HTTP DELETE streams to complete {e}")
            streamsRemainingCounter = len(streamsList)
            # If all streams deleted, we can move on
            if streamsRemainingCounter == 0:
                break
            Utils.Message.addMessage(f"DBUG:main.shutdownApplication() Remaining streams {streamsRemainingCounter}")
            # Update the loop counters
            if prevStreamsRemainingCounter == streamsRemainingCounter:
                # No further streams have been deleted since the last check. Assume something is stuck
                # decrement stalledStreamsThreshold
                stalledStreamsThreshold -= 1
                if stalledStreamsThreshold < 1:
                    Utils.Message.addMessage(f"ERR:main()shutdownApplication() stalledStreamsThreshold:{stalledStreamsThreshold}, "\
                                             f"streamsRemaining:{[s['streamID'] for s in streamsList]}")
            else:
                # reset the threshold counter
                stalledStreamsThreshold = 5
            # Update prevStreamsRemainingCounter
            prevStreamsRemainingCounter = streamsRemainingCounter
            time.sleep(1)

        try:
            # Update the processesCreatedDict
            Utils.updateProcessesCreatedDict(processesCreatedDict)
            # Now wait for all the child processes to end (join)
            Utils.Message.addMessage(f"DBUG:main.shutdownApplication() {len(processesCreatedDict)} child processes to join")
            for pid in processesCreatedDict:
                process = processesCreatedDict[pid]
                # Check to see if Process has already exited (in the mean time)
                exitCode = process["process"].exitcode
                if  exitCode is not None:
                    Utils.Message.addMessage(f"Waiting for process {pid}:{process['name']} to end")
                    if process["process"].join(timeout=10) == None:
                        Utils.Message.addMessage(f"Process.join() {pid}:{process['name']} timed out")
                else:
                    Utils.Message.addMessage(f"Process {pid}:{process['name']} has already ended with exit code {exitCode}")
        except Exception as e:
            Utils.Message.addMessage(f"ERR:main.shutdownApplication() joining child processes {e}")

        # Kill the whoIsResolver object
        whoIsResolver.kill()

        time.sleep(0.2)
        # Term.clearScreen()
        # Term.printAt("main.shutdownApplication() in progress", 1, 1)

        # Now kill UI
        ui.kill()

        # Kill the HTTP server
        isptesttHTTPServer.kill()

        time.sleep(0.5)

        ############ Stop DiskLogger as the last item
        diskLoggerShutdownFlag.set()
        try:
            # Wait for diskLogger Thread to end
            Utils.Message.addMessage("DBUG: Attempting to verify diskLoggerThread is dead")
            diskLoggerThread.join()
            Utils.Message.addMessage("DBUG: diskLoggerThread confirmed killed")
            print("diskLoggerThread ended\r")
        except Exception as e:
            Utils.Message.addMessage("ERR: diskLoggerThread.join() " + str(e))
        print("isptest ended\r")
        exit()



    if MODE == 'RECEIVE' or MODE == 'LOOPBACK':

        # Attempt to import a previously saved snapshot
        # ########### NOT IMPLEMENTED If it exists, this will prepopulate rxQueuesDict with a list of previously known
        # receive stream syncSourceIds and receive queues
        importedSnapshotsList = []

        try:
####### Inhibited import
            # importedSnapshotsList = Utils.importObjectFromDisk(Registry.streamsSnapshotFilename)
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
                        if stat in ["stream_friendly_name"]: # 'Exclude' list
                            pass
                        else:
                            x = Utils.convertStringToPythonDataType(stats[stat])
                            if not isinstance(stats[stat], type(x)):
                                # Utils.Message.addMessage(f"DBUG: Recreating stream. converted {stat} from {type(stats[stat])} to {type(x)}")
                                # assign the type-converted value back to the value in the dict
                                stats[stat] = x

                    eventsList = stream[2]
                    # Attempt to validate the keys/Values of the events list by reading the event no
                    for event in eventsList:
                        # This should (hopefully) cause an exception if the Event.eventNo can't be read
                        eventNo = event.eventNo

                    try:
                        # Utils.Message.addMessage("Recovered Events list " + str(eventsList))
                        # Create an RtpReceiveStream based on the info retrieved by setting the restoredStreamFlag
                        # This will preload the RtpReceiveStream._stats{} and eventsList to be preloaded
                        newRtpStream = RtpReceiveStream(stats["stream_syncSource"],
                                                        stats["stream_srcAddress"],
                                                        stats["stream_srcPort"],
                                                        stats["stream_rxAddress"],
                                                        stats["stream_rxPort"],
                                                        stats["glitch_Event_Trigger_Threshold_packets"],
                                                        None,
                                                        None,
                                                        # Specify None as the txMessageQueue, as we don't know what it is yet
                                                        # This will have to be determined by RtpPacketReceiver once the
                                                        # packets start arriving
                                                        restoredStreamFlag=True,
                                                        historicStatsDict=stats,
                                                        historicEventsList=eventsList,
                                                        controllerTCPPort=isptesttHTTPServerPort
                                                        )

                    except Exception as e:
                        raise Exception(
                            ("ERR:Recreate RtpReceiveStream from file: create RtpReceiveStream " + \
                             " ID: " + str(stats["stream_syncSource"]) + ", " + str(e)))

        except Exception as e:
            Utils.Message.addMessage("ERR:Prev streams import failed " + str(e))

        # Create a multiprocessing Event to indicate whether RtpPacketTransceiver has imported a previous
        # streams snapshot file. This must only happen once
        previousStreamsImportedFlag = mp.Event()

        # Create an RtpPacketTransceiver for each of the specified UDP listen addresses/ports
        # This should run as a child process
        for receivePort in receivePortList:
            try:
                rtpPacketTransceiver = mp.Process(target=RtpPacketTransceiver,
                                                  args=(rtpPacketTransceiverShutdownFlag,
                                                        previousStreamsImportedFlag,
                                                        UDP_RX_IP, UDP_RX_PORT, ISPTEST_HEADER_SIZE,
                                                        glitchEventTriggerThreshold,),
                                                  kwargs={"controllerTCPPort":isptesttHTTPServer.getTCPPort()},
                                                  name=f"RtpPacketTransceiver{UDP_RX_PORT}",
                                                  daemon=False)
                rtpPacketTransceiver.start()
                # Now confirm that the process actually started (and remained running)
                # attempt to join() If this blocks, then the Process must be running
                # If it executes immediately, then the server must have failed to start
                rtpPacketTransceiver.join(timeout=1)
                if rtpPacketTransceiver.is_alive():
                    Utils.Message.addMessage(f"RtpPacketTransceiver created with pid:{rtpPacketTransceiver.pid}")
                    # Add the new RtpPacketTransceiver child process to processesCreatedDict so it can be tracked
                    try:
                        Utils.addToProcessesCreatedDict(processesCreatedDict, rtpPacketTransceiver)
                    except Exception as e:
                        Utils.Message.addMessage(
                            f"ERR:main() add RtpPacketTransceiver({UDP_RX_PORT}) process to processesCreatedDict, {e}")

                    # RtpPacketTransceiver creation was successful, so add the receive addr/port to receiveAddrList[]
                    receiveAddrList.append({"addr": UDP_RX_IP, "port": receivePort})
                else:
                    Utils.Message.addMessage(f"{Fore.RED}RtpPacketTransceiver({UDP_RX_IP}) failed to start")
            except Exception as e:
                Utils.Message.addMessage(f"ERR: create RtpPacketTransceiver (port {receivePort}), {e}")



    enable_faulthandler_debugging = True

    faulthandlerLogFile = None
    if enable_faulthandler_debugging:
        # Create a file for the faulthander to dump stacktraces to
        faulthandlerLogFile = open("isptest_faulthandler_stacktrace.txt", mode='w')

    # Store the previous memory usage
    prevPeakMemUsage = 0
    peakMemUsage = None

    ## Dictionary to hold a list of the http server objects for each of the streams (be they Tx, Rx or Results)

    # Endless loop
    while True:
        try:
            loopCounter = 0 # Used as a scheduler
            while True:
                # Term.printAt(str(listCurrentThreads()),1,2)
                time.sleep(1)
                loopCounter += 1

                # # Update/Maintain the list of spawned child processes
                # try:
                #     Utils.updateProcessesCreatedDict(processesCreatedDict)
                #     Utils.Message.addMessage(f"child processes: {[processesCreatedDict[x]['name'] for x in processesCreatedDict]}",
                #                              logToDisk=False)
                # except Exception as e:
                #     Utils.Message.addMessage(f"main()updateProcessesCreatedDict(), {e}")


                # Every 5 seconds, seed the WhoIs resolver with the all know traceroute addresses in use
                if loopCounter % 5 == 0:
                    try:
                        # get the available streams list from the api
                        api = Utils.APIHelper(isptesttHTTPServerPort)
                        availableRtpStreamList = api.getStreamsList()
                        # Iterate over the available streams, querying a current traceroute hopslist
                        tracerouteHopsList = []
                        aggregateHopsList = [] # used to provide a list of all the streams' hopslists concatenated
                        for stream in availableRtpStreamList:
                            # Get the http server port for this stream
                            httpPort = stream["httpPort"]
                            # Get latest stable tracerouteHopsList from selected stream from the api
                            lastUpdated, tracerouteHopsList = Utils.APIHelper(httpPort).getByURL("/traceroute")
                            if len(tracerouteHopsList) > 0:
                                # concatenate this streams' hoplist onto the end of aggregateHopsList
                                aggregateHopsList += tracerouteHopsList

                            # Now we have a list of all the the addresses picked up by all the current stream traceroutes
                            # It will inevitibly contain lots of duplicates so we just want to end up with a list of
                            # unique ip addresses to pass to APIHelper.whoisLookup()
                            # Create list of unique addresses (from here https://stackoverflow.com/a/3724558)
                            unique_addresses = [list(x) for x in set(tuple(x) for x in aggregateHopsList)]

                            # # Pass the unique hops list to the WhoIs resolver so that it can query the addresses WhoIs info
                            # # in advance of it actually being required
                            if len(unique_addresses) > 0:
                                apiResponse = api.whoisLookup(unique_addresses)

                    except Exception as e:
                        Utils.Message.addMessage(f"ERR:main() seed WhoIs resolver cache {e}")

                # If in RECEIVE mode, schedule an auto export of the current streams
                try:
                    if MODE == 'RECEIVE' and (loopCounter % Registry.streamsSnapshotAutoSaveInterval_s == 0):
                        # Create snapshot of current receive streams
                        streamsExportedCounter = Utils.createStreamsSnapshot(Registry.streamsSnapshotFilename,
                                                                             isptesttHTTPServerPort)
                        Utils.Message.addMessage(f"Created auto snapshot for {streamsExportedCounter}"
                                                 f" streams to file {Registry.streamsSnapshotFilename}")
                except Exception as e:
                    Utils.Message.addMessage("ERR:streamsSnapshotAutoSave " + str(e))

                # Debugging code -  This samples the memory usage of the program every 2 seconds
                # If memory usage jumps significantly (by 10%) since the last sample, it will trigger
                # the snapshot of memory usage of all objects listed in objectsToProfile[]
                # Also, the current stack trace will be dumped to a file isptest_faulthandler_stacktrace.txt

                # Additionally, every 60 seconds, regardless of the current memory usage, the
                # snapshot of object memory usage will be triggered <<< Currently disabled

                # For convenience, objectsToProfile[] is actually a list of dictionaries that contain the object to
                # be measured and also a 'friendly name'

                # Clear the flag
                measureObjectMemoryUsageFlag = False
                # Every 2 seconds, measure memory usage and list running threads
                if loopCounter % 2 == 0:
                    try:
                        peakMemUsage = Utils.getPeakMemoryUsage()
                        if peakMemUsage is not None:
                            # Test to see if memory use has increased significantly (by 10%) since the last sample
                            if peakMemUsage > prevPeakMemUsage * 1.1:
                                # If so, set the flag to trigger meaurement of the individual objects memory use
                                measureObjectMemoryUsageFlag = True
                                # Dump a stack trace to disk
                                if enable_faulthandler_debugging and faulthandlerLogFile is not None:
                                    faulthandler.dump_traceback(file=faulthandlerLogFile, all_threads=True)
                                # List all current running threads
                                Utils.Message.addMessage("DBUG:Current threads " + Utils.listCurrentThreads())
                                # Write out peak mem use and object mem use summary
                                Utils.Message.addMessage(f"DBUG:Peak Mem Usage: {Utils.bToMb(peakMemUsage)}b")  # in bytes

                            # Snapshot peak memory usage
                            prevPeakMemUsage = peakMemUsage
                    except Exception as e:
                        Utils.Message.addMessage("ERR: main.getPeakMemoryUsage() " + str(e))

                # Every 60 seconds, and if the measureObjectMemoryUsageFlag is set, record the object memory usage
                if loopCounter % 60 == 0 and measureObjectMemoryUsageFlag:
                    try:
                        # Create list of objects to track memory usage and a friendly name
                        # Each object is contained within its own dict which also contains a friendly name.
                        # this will help genration of a report
                        objectsToProfile = [{"obj":ui, "name":"ui"},
                                            {"obj":whoIsResolver, "name":"whoIsResolver"},
                                            {"obj":isptesttHTTPServer, "name":"isptesttHTTPServer"}]  # These never change
                        # Create a string to store the object sizes
                        summaryString = ""

                        # if MODE == "RECEIVE":
                        #     try:
                        #         objectsToProfile.append({"obj":udpMessageSender, "name":"udpMessageSender"})
                        #         objectsToProfile.append({"obj":rtpPacketReceiver, "name":"rtpPacketReceiver"})
                        #     except Exception as e:
                        #         Utils.Message.addMessage("ERR: MODE==RECEIVE, objectsToProfile.append() " + str(e))

                        # Iterate over all the objects to be tracked, and report on the size
                        for obj in objectsToProfile:
                            objSize = Utils.getObjectSize(obj["obj"])
                            if objSize is not None and objSize > 0:
                                summaryString += "[name: " + str(obj["name"]) + ", type" + \
                                                     str(type(obj["obj"])) + ":" + str(Utils.bToMb(objSize)) + "], "
                        # Write out peak mem use and object mem use summary
                        if peakMemUsage is not None:
                            Utils.Message.addMessage("DBUG:Peak Usage: " + str(Utils.bToMb(peakMemUsage)) + "b")  # in bytes
                        Utils.Message.addMessage("DBUG:object profiler: " + summaryString)
                        # List all current running threads
                        # Utils.Message.addMessage("DBUG:Current threads " + Utils.listCurrentThreads())

                    except Exception as e:
                        Utils.Message.addMessage("ERR:object profiler " + str(e))


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
