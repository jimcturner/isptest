#!/usr/bin/env python
####################################################################################
# Define a class to hold constants to be used by the rest of the application
# This will be used as the source of default values
class Registry(object):
    streamReportFilename = "Stream_report_"
    version = "1.5"
    pythonMinimumVersionRequired_Major = 3  # Specfify the minimum version of the Python interpreter required
    pythonMinimumVersionRequired_Minor = 6  # This equates to Python version 3.6

    resultsSubfolder = "results/"        # Specifies the subfolder where exported files will be saved
    receiverLogFilename = "isptest_Receiver_Events_Log"
    transmitterLogFilename= "isptest_Transmitter_Events_Log"
    maximumLogFileSize_bytes = 1024 * 1024 # 1Mb maximum size
    tracerouteMaxHops = 28 # The maximum no of hops traceroute will consider before resetting
    tracerouteFallbackUDPDestPort = 33434 # The 'fallback' port used by the RtpGenerator.traceroute thread if no reply
                                            # is received from a host
