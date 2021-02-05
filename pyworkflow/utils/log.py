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

FILE_FORMATTER = 'fileFormatter'


def getLogConfiguration():
    if not loadCustomLoggingConfig():
        getDefaultLogConfiguration()

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

def getDefaultLogConfiguration():
    from pyworkflow import Config
    # Log configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s %(levelname)s:  %(message)s'
                # TODO: use formattime to show the time less verbose
            },
            FILE_FORMATTER: {
                'format': '%(asctime)s %(levelname)s:  %(message)s'
            },
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
    logging.getLogger(name)

class ScipionLogger:
    def __init__(self, filePath=''):
        from pyworkflow import Config
        """ If filePath is empty string, the general logger is used. """
        self._filePath = filePath
        makeFilePath(self._filePath)

        self.config = getLogConfiguration()

        if self._filePath not in self.config['loggers']:
            self.config['handlers'][self._filePath] = {
                'level': Config.SCIPION_LOG_LEVEL,
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': FILE_FORMATTER,
                'filename': self._filePath,
                'maxBytes': 100000}

            self.config['loggers'][self._filePath] = {
                'handlers': [self._filePath],
                'level': Config.SCIPION_LOG_LEVEL,
                'propagate': False}
            # Note: if we want to see in the console what we also have in
            # run.log, add 'consoleHandler' to the list of 'handlers'.

            logging.config.dictConfig(self.config)

        self._log = logging.getLogger(self._filePath)

    def getLog(self):
        return self._log  
    
    def getLogString(self):
        return open(self._filePath, 'r').readlines()
        
    def info(self, message, redirectStandard=False, *args, **kwargs):
        if redirectStandard:
            print(message)
            sys.stdout.flush()
        self._log.info(message, *args, **kwargs)

    def warning(self, message, redirectStandard=False, *args, **kwargs):
        if redirectStandard:
            print(message)
            sys.stdout.flush()
        self._log.warning(message, *args, **kwargs)
        
    def error(self, message, redirectStandard=False, *args, **kwargs):
        if redirectStandard:
            sys.stderr.write(message + '\n')
            sys.stderr.flush()
        self._log.error(message, *args, **kwargs)    
        
    def debug(self, message, redirectStandard=False, *args, **kwargs):
        if redirectStandard:
            sys.stderr.write(message + '\n')
            sys.stderr.flush()
        self._log.debug(message, *args, **kwargs)

    def close(self):
        if self._filePath in self.config['loggers']:
            del self.config['handlers'][self._filePath]
            del self.config['loggers'][self._filePath]


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, level):
       self.logger = logger
       self.level = level
       self.linebuf = ''

    def write(self, buf):
       for line in buf.rstrip().splitlines():
          self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass

def setUpGUILogging():
    """Sets up the logging library for the GUI processes: By default all goes to SCIPION_LOG file and console."""
    getLogConfiguration()

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
    sys.stdout = StreamToLogger(rootLogger, logging.INFO)





