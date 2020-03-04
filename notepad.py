#!/usr/bin/env python

import signal
import time
import threading
import sys
from Utils import listCurrentThreads
import platform


# A class that will be responsible for rendering the display and catching keyboard output
class UI(object):
    # def __init__(self,operationMode, specialFeaturesModeFlag, keyPressed, rtpTxStreamsDict, rtpTxStreamsDictMutex,
    #                 rtpRxStreamsDict, rtpRxStreamsDictMutex,
    #                 rtpTxStreamResultsDict, rtpTxStreamResultsDictMutex, UDP_RX_IP, UDP_RX_PORT):

    def __init__(self):

        self.keysPressedThreadActive = True
        self.renderDisplayThreadActive = True
        # Stores the last pressed keystroke
        self.keyPressed = None

        self.enableGetch = threading.Event()
        self.wakeUpUI = threading.Event()

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


    # This method will check to see that the rednerDisplay and keysPressed threads are running,
    # And if they are, signal them to end
    def kill(self):
        print ("UI.kill() method called\r")
        # Signal the __keysPressedThread to end
        if self.keysPressedThread.is_alive():
            self.keysPressedThreadActive = False
            # Block until the thread ends
            print("UI.kill() Waiting for __keysPressedThread to end")
            self.keysPressedThread.join()
        else:
            print("UI.kill() keysPressedThread.is_alive() didn't return True")

        if self.renderDisplayThread.is_alive():
            # End the __renderDisplayThread
            self.renderDisplayThreadActive = False
            # Block until the thread ends
            print("UI.kill() Waiting for renderDisplayThread to end")
            self.renderDisplayThread.join()
        else:
            print("UI.kill() renderDisplayThread.is_alive() didn't return True")

        # A cross-platform method to catch keypresses (and not echo them to the screen)
    def __getch(self):
        # Define a getch() function to catch keystrokes (for control of the RTP Generator thread)
        # This code has been lifted from https://gist.github.com/jfktrey/8928865
        if platform.system() == "Windows":
            import msvcrt
            time.sleep(0.2)  # 0.2sec timeout
            if msvcrt.kbhit():
                return ord(msvcrt.getch())
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

    # Autonomous thread to render the screen and parse keyboard presses
    def __renderDisplayThread(self):
        secs = 0
        while self.renderDisplayThreadActive == True:
            self.wakeUpUI.wait(timeout=2)
            # Has the timeout been exceeded with no key pressed
            # print ("__renderDisplayThread() " + str(self.keyPressed)+"\r")
            if self.keyPressed == None:
                # print ("UI " + str(secs) + " Timeout exceeded\r")
                pass
            elif self.keyPressed == 3:
                self.keyPressed = None
                print ("UI: you pressed Ctrl-C. Shutting down key __keysPressedThread\r")
                self.keysPressedThreadActive = False
                print ("UI: renderDisplayThread: keysPressedThread join successful, signalling renderDisplayThread to end ")
                self.renderDisplayThreadActive = False


            else:
                print ("UI: key pressed not known: " + str(self.keyPressed))
            # Now clear the 'wakeupUI event' flag (because we've processed this key press)
            self.wakeUpUI.clear()
            # Now re-arm the getch thread
            self.enableGetch.set()
            secs += 2
        print ("__renderDisplapThread ended")

# Autonomous thread to monitor key presses
    def __keysPressedThread(self):
        self.getchCounter = 0
        while self.keysPressedThreadActive == True:
            # Wait for getch to be enabled
            self.enableGetch.wait()
            # Capture keyboard presses via the getch method (with a 1 second timeout)
            self.keyPressed = None  #clear the keyboard buffer
            ch = self.__getch()
            # Check to see if a key has been pressed
            if ch != None:
                # If a key has been pressed, store it
                self.keyPressed = ch
                # Signal that a key has been pressed
                self.wakeUpUI.set()
                # Now disarm key checking (until it is re-enabled elsewhere)
                self.enableGetch.clear()
            self.getchCounter += 1
        print("__keysPressedThread ending\r")

class ServiceExit(Exception):
  """
  Custom exception which is used to trigger the clean exit
  of all running threads and the main program.

  """
  # It might not look important, but it is!
  pass

def service_shutdown(signum, frame):
    print('Caught signal ' + str(signum) + "\r")
    raise ServiceExit

def main(argv):
    # Register the signal handlers
    signal.signal(signal.SIGTERM, service_shutdown)
    signal.signal(signal.SIGINT, service_shutdown)

    print('Starting main program\r')
    # Start the job threads
    try:

        ui = UI()

        # Keep the main thread running, otherwise signals are ignored.
        while True:
            print (str(listCurrentThreads()) + ", ui.keysPressedThreadActive: " +
                   str(ui.keysPressedThreadActive) +\
                ", ui.renderDisplayThreadActive: " + str(ui.renderDisplayThreadActive) +
                ",  ui.getchCounter: " + str(ui.getchCounter) + "\r")
            # print ("xxxxxxx\r")
            # Determine that both the UI.renderDisplay and UI.keysPressed threads are still running. If not,
            # gracefully exit the program.
            if not ui.renderDisplayThread.is_alive() and not ui.keysPressedThread.is_alive():
                print("main() renderDisplayThread and keysPressedThread not running. Shutting down")
                # Raise an exception to cause main() to break
                raise ServiceExit

            time.sleep(1)

    except ServiceExit:
        # Gracefully Terminate the running threads if a SIGTERM ot SIGINT signal received (from the OS, not the keyboard).
        # This code will execute if a 'ServiceExit' exception is raised
        # See here: https://www.g-loaded.eu/2016/11/24/how-to-terminate-running-python-threads-using-signals/

        print ("main() called UI.kill()\r")
        ui.kill()

    print ("exiting\r")


if __name__ == '__main__':
    # Call main and pass command line args to it (but ignore the first argument)
    main(sys.argv[1:])



