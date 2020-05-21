#!/usr/bin/env python
####################################################################################
# Define a class to hold constants to be used by the rest of the application
# This will be used as the source of default values
class Registry(object):
    streamReportFilename = "Stream_report_"
    version = "1.9"
    pythonMinimumVersionRequired_Major = 3  # Specfify the minimum version of the Python interpreter required
    pythonMinimumVersionRequired_Minor = 6  # This equates to Python version 3.6

    resultsSubfolder = "results/"        # Specifies the subfolder where exported files will be saved
    receiverLogFilename = "isptest_Receiver_Events_Log"
    transmitterLogFilename= "isptest_Transmitter_Events_Log"
    maximumLogFileSize_bytes = 1024 * 1024 # 1Mb maximum size

    messageLogFilename = "isptest_log.txt"  # This file is appended to, every time Utils.Message.addMessage() is called
    # Provides content for the help popup
    helpTableContents = [["h","Display/hide this page"],
                         ["Ctrl-C", "Quit the application"],
                         ["d", "Delete the currently selected transmit or receive stream"],
                         ["l","Sets the friendly name of the stream (10 chars max)"],
                         ["r", "Show report for the currently stream"],
                         ["t", "Show traceroute for the currently selected stream"],
                         ["a", "Show 'About' dialogue"]
                         ]

    ######### RtpReceiveStream
    lossOfStreamAlarmThreshold_s = 5 # Specifies how long before a loss of stream Event is triggered by RtpReceiveStream
    streamIsDeadThreshold_s = 30 # Specifies how long to wait with no incoming rtp packets before a stream is presumed dead
    # Getting false positives at the moment (because the CPU can keep up!) so creating lots of unhelpful events
    allowProcessorOverloadEventGeneration = False

    # RtpGenerator
    tracerouteMaxHops = 28  # The maximum no of hops traceroute will consider before resetting
    tracerouteFallbackUDPDestPort = 33434  # The 'fallback' port used by the RtpGenerator.traceroute thread if no reply
    # is received from a host