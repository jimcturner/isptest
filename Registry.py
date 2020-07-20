#!/usr/bin/env python
####################################################################################
# Define a class to hold constants to be used by the rest of the application
# This will be used as the source of default values
class Registry(object):
    streamReportFilename = "Stream_report_"
    version = "2.1"
    pythonMinimumVersionRequired_Major = 3  # Specfify the minimum version of the Python interpreter required
    pythonMinimumVersionRequired_Minor = 7  # This equates to Python version 3.7

    resultsSubfolder = "results/"        # Specifies the subfolder where exported files will be saved
    receiverLogFilename = "isptest_Receiver_Events_Log"
    transmitterLogFilename= "isptest_Transmitter_Events_Log"
    maximumLogFileSize_bytes = 1024 * 1024 # 1Mb maximum size

    messageLogFilenameTx = "isptest_log_tx.txt"  # This file is appended to, every time Utils.Message.addMessage() is called
    messageLogFilenameRx = "isptest_log_rx.txt"  # This file is appended to, every time Utils.Message.addMessage() is called

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
    receiveStreamAcceptThreshold = 15 # The minimum no of rtp packets for particular sync source ID to be received
                                    # before the stream is accepted as a valid incoming stream
    nonExistentStreamTimout_seconds = 5 # How long to wait before deciding that a received packet isn't part of any stream

    lossOfStreamAlarmThreshold_s = 10 # Specifies how long before a loss of stream Event is triggered by RtpReceiveStream
    streamIsDeadThreshold_s = 90 # Specifies how long to wait with no incoming rtp packets before a stream is presumed dead
    autoRemoveDeadRxStreamsEnable = True # Determines whether dead streams should automaticaslly be removed from the
                                            # list of received streams

    # No of historic events to keep in memory (before events are purged)
    rtpReceiveStreamHistoricEventsLimit = 250
    # rtpReceiveStreamJitterExcessiveAlarmThresholdPercent = 100 # **REDUNDANT ** The amount of jitter in the
    # received packet arrival time before an excessive jitter event is registered
    # The jitter events are a bit annoying as they clog the log. Therefore disable them by default
    rtpReceiveStreamEnableExcessiveJitterEventGeneration = False

    # The threshold before an Excessive Jitter Event is generated
    # NOTE: This is a whole number in multiples of the 'mean receive period' for the incoming stream. Therefore the
    # 'lateness' threshold time depends upon the incoming bitrate.
    # A value of '2' means that if the packet jitter >= 2x receivePeriod (uS) (or rather, the packet is late by the
    # two receive periods worth of time) an Event will be created
    # then an Event will be generated
    rtpReceiveStreamJitterExcessiveAlarmThreshold = 2
    rtpReceiveStreamGlitchThreshold = 4 # The default no of packets that have to be lost before a Glitch Event is generated


    # RtpGenerator
    rtpGeneratorUDPTxTTL = 128  # Sets the TTL value of the transmitted udp packets
    rtpGeneratorEnableTraceroute = True # Enables/inhbits the traceroute thread from starting
    tracerouteMaxHops = 28  # The maximum no of hops traceroute will consider before resetting
    tracerouteFallbackUDPDestPort = 33434  # The 'fallback' port used by the RtpGenerator.traceroute thread if no reply
    # is received from a host
    simulatedJitterPercent = 50 # The amount of 'simulated jitter' to add to the tx packets, if the feature is enabled
    # Specify min/max/default RtpGenerator tx parameters
    minimumPermittedTXRate_bps = 10240 # Specifies the minimum RtpGenerator tx rate as 10kbps
    defaultTXRate_bps = 1 * 1024 * 1024 # Specifies the default RtpGenerator tx rate as 1Mbps
    defaultPayloadLength_bytes = 1300
    defaultTxStreamTimeToLive_sec = 3600

    # RtpStreamResults
    # No of historic events to keep in memory (before events are purged)
    rtpStreamResultsHistoricEventsLimit = 250

    # Utils
    historicMessagesToKeepInMemory = 50