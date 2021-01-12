#!/usr/bin/env python
####################################################################################
# Define a class to hold constants to be used by the rest of the application
# This will be used as the source of default values
class Registry(object):
    streamReportFilename = "Stream_report_"
    version = "2.7"
    pythonMinimumVersionRequired_Major = 3  # Specfify the minimum version of the Python interpreter required
    pythonMinimumVersionRequired_Minor = 7  # This equates to Python version 3.7

    resultsSubfolder = "results/"        # Specifies the subfolder where exported files will be saved
    receiverLogFilename = "isptest_Receiver_Events_Log"
    enableJsonEventsLog = False  # Enables saving events as json objects
    transmitterLogFilename= "isptest_Transmitter_Events_Log"
    maximumLogFileSize_bytes = 1024 * 1024 # 1Mb maximum size

    messageLogFilenameTx = "isptest_log_tx.txt"  # This file is appended to, every time Utils.Message.addMessage() is called
    messageLogFilenameRx = "isptest_log_rx.txt"  # This file is appended to, every time Utils.Message.addMessage() is called
    streamsSnapshotFilename = "ispTestSnapshot.isp" # This file is created when the isptest Receiver app ends, and is reloaded
                                                    # on startup
    streamsSnapshotAutoSaveInterval_s = 30       # The frequency of stream snapshot auto saves (when in RECEIVE mode)

    httpRequestTimeout = 0.1 # The default timeout for all HTTP requests (GET, POST etc)
    # This string will be added between the UDP header
    # and Rtp header of the geenrated RTp traffic. It's purpose is to obscure the generated
    # packets to stop them looking like RTP (to aid investigation of ISPs that
    # block RTP. Note: it is overwritten in main() if the program is started with the '-o' option
    rtpHeaderOffsetString = None # None is the default value

    # Provides content for the help popup
    helpTableContents = [["h","Display/hide this page"],
                         ["Ctrl-C", "Quit the application"],
                         ["d", "Delete the currently selected transmit or receive stream"],
                         ["l","Sets the friendly name of the stream (10 chars max)"],
                         ["r", "Show report for the currently stream"],
                         ["t", "Show traceroute for the currently selected stream"],
                         ["a", "Show 'About' dialogue"],
                         ["p", "Compare stream performance"],
                         ["b", "Burst mode - temporary (5s) doubling of Tx bitrate"]
                         ]


    ######### RtpCommon
    rtpCommonHistoricTracerouteEventsToKeep = 10 # No of previous traceroute results to hold in memory
    # TCP listen ports for the embedded HTTP servers
    httpServerRtpReceiverTCPPort = 10000
    httpServerRtpTransmitterTCPPort = 10001
    # httpServerRtpResultsTCPPort = 10002

    httpServerStartingTCPPort = 10010 # The starting tcp http server port no for adhoc server creation

    ######### RtpStreamComparer
    # A list of the available criteria by which a stream can be compared (and a display friendly name)
    # These criteria map to stats{} dictionary keys within RtpReceiveStream and RtpStreamresults objects
    criteriaListForCompareStreams = [
        {"keyToCompare": "glitch_packets_lost_total_percent", "friendlyTitle": "Packet loss %"},
        {"keyToCompare": "glitch_packets_lost_total_count", "friendlyTitle": "Total packets lost"},
        {"keyToCompare": "glitch_counter_total_glitches", "friendlyTitle": "Total no of glitches"},
        {"keyToCompare": "glitch_most_recent_timestamp", "friendlyTitle": "Most recent glitch"},
        {"keyToCompare": "glitch_mean_time_between_glitches", "friendlyTitle": "Glitch period(how often)"},
        {"keyToCompare": "glitch_packets_lost_per_glitch_max", "friendlyTitle": "Worst loss (packets)"},
        {"keyToCompare": "glitch_max_glitch_duration", "friendlyTitle": "Worst glitch (duration)"},
        {"keyToCompare": "glitch_packets_lost_per_glitch_mean", "friendlyTitle": "Mean glitch packet loss"},
        {"keyToCompare": "glitch_mean_glitch_duration", "friendlyTitle": "Mean glitch duration"}
    ]

    ######### RtpReceiveStream
    receiveStreamAcceptThreshold = 15 # The minimum no of rtp packets for particular sync source ID to be received
                                    # before the stream is accepted as a valid incoming stream
    nonExistentStreamTimout_seconds = 5 # How long to wait before deciding that a received packet isn't part of any stream

    lossOfStreamAlarmThreshold_s = 5 # Specifies how long before a loss of stream Event is triggered by RtpReceiveStream
    streamIsDeadThreshold_s = 30 # Specifies how long to wait with no incoming rtp packets before a stream is presumed dead (12 hrs)
                                    # At this point, the timing clocks used in the stats calculations will pause
                                    # At this point, the Receiver will auto-save a Stream report
    autoRemoveDeadRxStreamsThreshold_s = 60 * 60 * 12 # 12 hours
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
    rtpReceiveStreamCompressResultsBeforeSending = False # If True, uses bz2 compression. Experimental

    ### RtpPacketReciever
    # buffer size is 65535 bytes. This is the maximum possible size for UDP We need to set it
    # to this size for Windows (which is running in promiscuous mode). Otherwise packets received
    # larger we can accept would kill the socket
    rtpPacketRecieverRecvFromBufferSize = 65535

    ### RtpGenerator
    rtpGeneratorRtpParams = 0b10000000 # Was 0b01000000 Perhaps try 0b10000000 to match NTT?
    rtpGeneratorRtpPayloadType = 0x33 # 0x33 identifies as MPEG video Was 0b00000000

    rtpGeneratorUDPTxTTL = 128  # Sets the TTL value of the transmitted udp packets
    rtpGeneratorEnableTraceroute = True # Enables/inhbits the traceroute thread from starting
    tracerouteMaxHops = 20  # The maximum no of hops traceroute will consider before resetting
    tracerouteStartingTTL = 1   # The starting TTL for the traceroute
    tracerouteFallbackUDPDestPort = None  # 33434 The 'fallback' port used by the RtpGenerator.traceroute thread if no reply
    # is received from a host. If this is set, traceroute will firstly send to thje udp port specified by the tx stream.
    # if it gets no response it will use the fallback. It will continue to alternate between the two dest ports
    # until it runs out of attempts. this feature exists because some routers will only reply with ICMP messages
    # if traceroute (ie ttl=1) messages are sent to port 33434. Otherwise they may silently drop them, which isn't
    # much use if you're trying to derive a list of hops taken by the transmitted packets
    tracerouteStartDelay = 2
    simulatedJitterPercent = 50 # The amount of 'simulated jitter' to add to the tx packets, if the feature is enabled
    # Specify min/max/default RtpGenerator tx parameters
    minimumPermittedTXRate_bps = 10240 # Specifies the minimum RtpGenerator tx rate as 10kbps
    defaultTXRate_bps = 1 * 1024 * 1024 # Specifies the default RtpGenerator tx rate as 1Mbps
    defaultPayloadLength_bytes = 1300
    defaultTxStreamTimeToLive_sec = 3600
    maximumPayloadSize_bytes = 1500 - 12 # Maximum Ethernet frame size is 1500 bytes (minus 12 bytes for the RTP header)
    enableExcessTxSpeedWarnings = True   # Inhibits excessive tx speed warnings

    # RtpStreamResults
    # No of historic events to keep in memory (before events are purged)
    rtpStreamResultsHistoricEventsLimit = 250

    # Utils
    historicMessagesToKeepInMemory = 50
    pastebinApiDeveloperkey = '78c625162b816673e6b3ecc2750ee741'