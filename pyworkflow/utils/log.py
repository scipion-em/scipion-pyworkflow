#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     Antonio Poza (Apr 30, 2013)
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
"""
Module to handle default logging configuration and custom one. Default logging configuration
is defined here but optionally, it can be configured with an external json file
containing a standard python logging configuration content as documented here:
https://docs.python.org/3/howto/logging-cookbook.html#an-example-dictionary-based-configuration
To specify a custom logging config file use SCIPION_LOG_CONFIG variable to a json logging configuration file
If you just want to change the logger devel use SCIPION_LOG_LEVEL variable (defaults to INFO)
See https://docs.python.org/3/howto/logging.html#logging-levels for available levels. Use the literal! not de value.
"""
import os
import sys
import logging
import logging.config
import json
from logging import FileHandler

from pyworkflow.constants import PROJECT_SETTINGS, PROJECT_DBNAME
from pyworkflow.utils import Config

CONSOLE_HANDLER = 'consoleHandler'

SCIPION_PROT_ID = "SCIPION_PROT_ID"
SCIPION_PROJ_ID = "SCIPION_PROJ_ID"


# Constant for extra logging data
class STATUS:
    START = "START"
    STOP = "STOP"
    INTERVAL = "INTERVAL"
    EVENT = "EVENT"


class LevelFilter(object):
    """ Logging handler filter to filter some levels. e.g.: ERROR """
    def __init__(self, level):
        """

        :param level: Level integer value,from which include messages. Value is compared to record.levelno.
        """

        self.level = level

    def filter(self, record):
        return record.levelno <= self.level

class LoggingConfigurator:
    """ Class to configure logging scenarios:

    1.- GUI logging

    2.- Protocol run logging

    3.- Other loggings: tests, sync data"""

    customLoggingActive = False  # Holds if a custom logging configuration has taken place.

    @classmethod
    def setupLogging(cls, logFile=None, console=True):
        if not cls.loadCustomLoggingConfig():
            cls.setupDefaultLogging(logFile=logFile, console=console)

    @classmethod
    def loadCustomLoggingConfig(cls):
        """ Loads the custom logging configuration file"""
        from pyworkflow import Config

        if Config.SCIPION_LOG_CONFIG:
            if os.path.exists(Config.SCIPION_LOG_CONFIG):
                with open(Config.SCIPION_LOG_CONFIG, 'r') as stream:
                    config = json.load(stream)

                logging.config.dictConfig(config)
                cls.customLoggingActive = True
                return True
            else:
                print("SCIPION_LOG_CONFIG variable points to a non existing file: %s." % Config.SCIPION_LOG_CONFIG)
        return False

    @staticmethod
    def setupDefaultLogging(logFile=None, console=True):
        """ Configures logging in a default way that is to file (rotating) and console

        :param logFile: Optional, path to the log file. Defaults to SCIPION_LOG variable value. If folder
            does not exists it will be created.
        :param console: Optional, defaults to True, so log messages are sent to the terminal as well

        """
        from pyworkflow import Config

        logFile = logFile or Config.SCIPION_LOG

        # Log configuration
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': Config.SCIPION_LOG_FORMAT
                }
            },
            'handlers': {
                'fileHandler': {
                    'level': Config.SCIPION_LOG_LEVEL,
                    'class': 'logging.handlers.RotatingFileHandler',
                    'formatter': 'standard',
                    'filename': logFile,
                    'maxBytes': 1000000,
                    'backupCount': 10
                },
            },
            'loggers': {
                '': {
                    'handlers': ['fileHandler'],
                    'level': Config.SCIPION_LOG_LEVEL,
                    'propagate': False,
                    'qualname': 'pyworkflow',
                },
            }
        }

        if console:
            config["handlers"][CONSOLE_HANDLER] = {
                        'level': 'ERROR', #Config.SCIPION_LOG_LEVEL,
                        'class': 'logging.StreamHandler',
                        'formatter': 'standard',
                        }

            config['loggers']['']['handlers'].append(CONSOLE_HANDLER)

        # Create the log folder
        os.makedirs(os.path.dirname(os.path.abspath(logFile)), exist_ok=True)

        logging.config.dictConfig(config)

    @classmethod
    def setUpGUILogging(cls):
        """Sets up the logging library for the GUI processes: By default all goes to SCIPION_LOG file and console."""
        cls.setupLogging()

    @classmethod
    def setUpProtocolSchedulingLog(cls, scheduleLogFile):
        """ Sets up the logging for the scheduling process"""

        # Load custom logging
        cls.loadCustomLoggingConfig()

        # File handler to the scheduling log file
        scheduleHandler = FileHandler(scheduleLogFile)

        # Get the root logger
        rootLogger = logging.getLogger()

        # If there wasn't any custom logging
        if not cls.customLoggingActive:
            # Remove the default handler that goes to the terminal
            rootLogger.handlers.clear()

        # Add the handler
        rootLogger.addHandler(scheduleHandler)
        rootLogger.setLevel(Config.SCIPION_LOG_LEVEL)

        # create formatter and add it to the handlers
        formatter = logging.Formatter(Config.SCIPION_LOG_FORMAT)
        scheduleHandler.setFormatter(formatter)


    @classmethod
    def setUpProtocolRunLogging(cls, stdoutLogFile, stderrLogFile):
        """ Sets up the logging library for the protocols run processes, loads the custom configuration plus
        2 FileHandlers for stdout and stderr"""

        cls.loadCustomLoggingConfig()

        # std out: Only warning, info and debug. Error and critical should go exclusively to stderr handler
        stdoutHandler = FileHandler(stdoutLogFile)
        stdoutHandler.addFilter(LevelFilter(logging.WARNING))

        # std err: just errors and critical
        stderrHandler = FileHandler(stderrLogFile)
        stderrHandler.setLevel(logging.ERROR)

        # Get the root logger
        rootLogger = logging.getLogger()

        # If there wasn't any custom logging
        if not cls.customLoggingActive:
            # Remove the default handler that goes to the terminal
            rootLogger.handlers.clear()

        # Add the 2 handlers, remove the
        rootLogger.addHandler(stderrHandler)
        rootLogger.addHandler(stdoutHandler)
        rootLogger.setLevel(Config.SCIPION_LOG_LEVEL)

        # create formatter and add it to the handlers
        formatter = logging.Formatter(Config.SCIPION_LOG_FORMAT)
        stdoutHandler.setFormatter(formatter)
        stderrHandler.setFormatter(formatter)

        # Capture std out and std err and send it to the file handlers
        rootLogger.info("Logging configured. STDOUT --> %s , STDERR --> %s" % (stdoutLogFile, stderrLogFile))

        # TO IMPROVE: This redirects the std out and stderr to the stream contained by the FileHandlers.
        # The problem with this is that output stderr and stdout from subprocesses  is written directly to the file
        # and therefore not being formatted or propagated to other loggers in case of a custom logging configuration.
        # I've (Pablo) have attempted what is described here: https://stackoverflow.com/questions/19425736/how-to-redirect-stdout-and-stderr-to-logger-in-python
        # but didn't work--> check_call(command, shell=True, stdout=sys.stdout, stderr=sys.stderr ) . This leads to an error cause deep in the code python does this: c2pwrite = stdout.fileno()
        sys.stderr = stderrHandler.stream
        sys.stdout = stdoutHandler.stream

        return rootLogger


def restoreStdoutAndErr():
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__


# ******** Extra code to send some log lines to an external performance analysis tool ***********
def setDefaultLoggingContext(protId, projId):
    os.environ[SCIPION_PROT_ID] = str(protId)
    os.environ[SCIPION_PROJ_ID] = projId


def getFinalProtId(protId):
    return protId if protId is not None else int(os.environ.get(SCIPION_PROT_ID, "-1"))


def getFinalProjId(projId):
    return projId if projId is not None else os.environ.get(SCIPION_PROJ_ID, "unknown")


def getExtraLogInfo(measurement, status, project_name=None, prot_id=None, prot_name=None, step_id=None, duration=None,
                    dbfilename=None):
    try:
        # Add TS!! optionally
        if dbfilename:
            splitDb = dbfilename.split("/")
            dbName = splitDb[-1]
            runName = ""
            # project.sqlite and settings.sqlite may not have elements
            if dbName not in [PROJECT_SETTINGS, PROJECT_DBNAME, ":memory:"]:
                runName = splitDb[1]
            dbfilename = os.path.join(runName, dbName)

        return {"measurement": measurement,
                "status": status,
                "project_name": getFinalProjId(project_name),
                "prot_id": getFinalProtId(prot_id),
                "prot_name": prot_name,
                "step_id": step_id,
                "duration": duration,
                "dbfilename": dbfilename
                }

    except Exception as e:
        print("getExtraLogInfo failed: %s.Params were: dbFilename %s" % (e, dbfilename))
