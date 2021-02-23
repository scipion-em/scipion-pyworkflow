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
from logging.handlers import RotatingFileHandler

from pyworkflow.utils import makeFilePath, Config

class STATUS:
    START="START"
    STOP="STOP"
    INTERVAL="INTERVAL"

def setupLogging():
    if not loadCustomLoggingConfig():
        setupDefaultLogging()
    return logging

def loadCustomLoggingConfig():
    """ Loads the custom logging configuration file"""
    from pyworkflow import Config

    if Config.SCIPION_LOG_CONFIG:
        if os.path.exists(Config.SCIPION_LOG_CONFIG):
            with open(Config.SCIPION_LOG_CONFIG, 'r') as stream:
                config = json.load(stream)

            logging.config.dictConfig(config)
            return True
        else:
            print("SCIPION_LOG_CONFIG variable points to a non existing file: %s." % Config.SCIPION_LOG_CONFIG)
    return False

def setupDefaultLogging():
    from pyworkflow import Config
    # Log configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s %(name)s %(levelname)s:  %(message)s'
                # TODO: use formattime to show the time less verbose
            }
        },
        'handlers': {
            'fileHandler': {
                'level': Config.SCIPION_LOG_LEVEL,
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'standard',
                'filename': Config.SCIPION_LOG,
                'maxBytes': 100000,
            },
            'consoleHandler': {
                'level': Config.SCIPION_LOG_LEVEL,
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
        },
        'loggers': {
            '': {
                'handlers': ['consoleHandler', 'fileHandler'],
                'level': Config.SCIPION_LOG_LEVEL,
                'propagate': False,
                'qualname': 'pyworkflow',
            },
        }
    }

    # Create the log folder
    os.makedirs(Config.SCIPION_LOGS, exist_ok=True)

    logging.config.dictConfig(config)

def getRotatingFileLogger(name, path):
    logger = logging.getLogger(name)
    makeFilePath(path)
    handler = RotatingFileHandler(filename=path, maxBytes=100000)
    handler.setLevel(Config.SCIPION_LOG_LEVEL)
    return logger

class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, level):
       self.logger = logger
       self.level = logging._checkLevel(level)
       self.linebuf = ''

    def write(self, buf):
       for line in buf.rstrip().splitlines():
          self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass
    def fileno(self):
        # Mimic filehandle, this is used by subprocess.
        return 1

def setUpGUILogging():
    """Sets up the logging library for the GUI processes: By default all goes to SCIPION_LOG file and console."""
    setupLogging()

def setUpProtocolRunLogging(stdoutLogFile, stderrLogFile):
    """ Sets up the logging library for the protocols run processes, loads the custom configuration plus
    2 FileHandlers for stdout and stderr"""
    loadCustomLoggingConfig()

    stdoutHandler = RotatingFileHandler(stdoutLogFile, maxBytes=100000)
    stderrHandler = RotatingFileHandler(stderrLogFile, maxBytes=100000)
    stderrHandler.setLevel(logging.ERROR)

    # Add the 3 handlers
    rootLogger = logging.getLogger()
    rootLogger.addHandler(stderrHandler)
    rootLogger.addHandler(stdoutHandler)
    rootLogger.setLevel(Config.SCIPION_LOG_LEVEL)

    # Capture std out and std err and send it to the root logger
    sys.stderr = StreamToLogger(rootLogger,logging.ERROR)
    sys.stdout = StreamToLogger(rootLogger, Config.SCIPION_LOG_LEVEL)

    return rootLogger

def restoreStdoutAndErr():
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

def getExtraLogInfo(project_name, status, prot_id=None, prot_name=None, step_id=None , duration=None):
    # Add TS!! optionally
    return {"project_name": project_name,
            "status": status,
            "prot_id": prot_id,
            "prot_name": prot_name,
            "step_id": step_id,
            "duration": duration
    }

