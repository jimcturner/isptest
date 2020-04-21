#!/usr/bin/env python
####################################################################################
# Define a class to hold constants to be used by the rest of the application
# This will be used as the source of default values
class Registry(object):
    streamReportFilename = "Stream_report_"
    version = "V1.4"
    resultsSubfolder = "results/"        # Specifies the subfolder where exported files will be saved
    receiverLogFilenamePrefix = "receiver_"
    pythonMinimumVersionRequired_Major = 3  # Specfify the minimum version of the Python interpreter required
    pythonMinimumVersionRequired_Minor = 6  # This equiates to Python version 3.6