# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *
# * [1] SciLifeLab, Stockholm University
# *
# * This program is free software: you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation, either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program.  If not, see <https://www.gnu.org/licenses/>.
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
import ast
import os
import sys
import importlib
import types
from .constants import *

# For a new release, define a new constant and assign it to LAST_VERSION
# The existing one has to be added to OLD_VERSIONS list.
LAST_VERSION = VERSION_3_0
OLD_VERSIONS = (VERSION_1, VERSION_1_1, VERSION_1_2, VERSION_2_0)

# Define pyworkflow version in a standard way, as proposed by:
# https://www.python.org/dev/peps/pep-0396/
__version__ = LAST_VERSION + 'a1'

HOME = os.path.abspath(os.path.dirname(__file__))
PYTHON = os.environ.get(SCIPION_PYTHON, SCIPION_PYTHON_DEFAULT)

# Variable constants, probably we can have a constants module


# Following are a set of functions to centralize the way to get
# files from several scipion folder such as: config or apps
def getPWPath(*paths):
    return os.path.join(os.path.dirname(__file__), *paths)


def getAppsPath():
    return os.path.join(getPWPath(), APPS)


def getSyncDataScript():
    return os.path.join(getAppsPath(), PW_SYNC_DATA)


def getScheduleScript():
    return os.path.join(getAppsPath(), PW_SCHEDULE_RUN)


def getPwProtMpiRunScript():
    return os.path.join(getAppsPath(), PW_PROTOCOL_MPIRUN)


def getTestsScript():
    return os.path.join(getAppsPath(), PW_RUN_TESTS)


def getViewerScript():
    return os.path.join(getAppsPath(), PW_VIEWER)


class Config:
    __get = os.environ.get  # shortcut
    SCIPION_HOME = __get(SCIPION_HOME, '')
    SCIPION_USER_DATA = __get(SCIPION_USER_DATA,
                              os.path.expanduser(SCIPION_USER_DATA_DEFAULT))
    SCIPION_SUPPORT_EMAIL = __get(SCIPION_SUPPORT_EMAIL,
                                  SCIPION_SUPPORT_EMAIL_DEFAULT)
    SCIPION_LOGO = __get(SCIPION_LOGO,
                         SCIPION_LOGO_DEFAULT)
    # Where is the input data for tests...also where it will be downloaded
    SCIPION_TESTS = __get(SCIPION_TESTS,
                          os.path.join(SCIPION_HOME, 'data', 'tests'))

    # Where the output of the tests will be stored
    SCIPION_TESTS_OUTPUT = __get(SCIPION_TESTS_OUTPUT,
                                 os.path.join(SCIPION_USER_DATA, 'tests'))

    SCIPION_CONFIG = __get(SCIPION_CONFIG, SCIPION_CONFIG_DEFAULT)
    SCIPION_LOCAL_CONFIG = __get(SCIPION_LOCAL_CONFIG, SCIPION_CONFIG_DEFAULT)
    SCIPION_HOSTS = __get(SCIPION_HOSTS, SCIPION_HOSTS_DEFAULT)
    SCIPION_PROTOCOLS = __get(SCIPION_PROTOCOLS, SCIPION_PROTOCOLS_DEFAULT)

    SCIPION_PLUGIN_JSON = __get(SCIPION_PLUGIN_JSON, None)
    SCIPION_PLUGIN_REPO_URL = __get(SCIPION_PLUGIN_REPO_URL, SCIPION_PLUGIN_REPO_URL_DEFAULT)

    # Get general log file path
    LOG_FILE = os.path.join(__get(SCIPION_LOGS, SCIPION_USER_DATA), SCIPION_LOGS_DEFAULT)

    SCIPION_URL_SOFTWARE = __get(SCIPION_URL_SOFTWARE)

    # Scipion Notes
    SCIPION_NOTES_FILE = __get(SCIPION_NOTES_FILE, SCIPION_NOTES_FILE_DEFAULT)
    SCIPION_NOTES_PROGRAM = __get(SCIPION_NOTES_PROGRAM, None)
    SCIPION_NOTES_ARGS = __get(SCIPION_NOTES_ARGS, None)

    try:
        VIEWERS = ast.literal_eval(__get(VIEWERS, "{}"))
    except Exception as e:
        VIEWERS = {}
        print("ERROR loading preferred viewers, {} variable will be ignored".format(VIEWERS))
        print(e)

    SCIPION_DOMAIN = __get(SCIPION_DOMAIN, None)
    PW_ALT_TESTS_CMD = __get(PW_ALT_TESTS_CMD, getTestsScript())

    @classmethod
    def getDomain(cls):
        """ Import domain module from path or name defined in SCIPION_DOMAIN. """
        value = cls.SCIPION_DOMAIN

        if not value:
            return None

        if os.path.isdir(value):
            dirname, value = os.path.split(value)
            sys.path.append(dirname)

        return importlib.import_module(value).Domain

    @classmethod
    def setDomain(cls, moduleOrNameOrPath):
        if isinstance(moduleOrNameOrPath, types.ModuleType):
            value = os.path.abspath(moduleOrNameOrPath.__path__[0])
        else:
            value = moduleOrNameOrPath
        cls.SCIPION_DOMAIN = value
        os.environ[SCIPION_DOMAIN] = value

    @staticmethod
    def getPythonLibFolder():
        from sysconfig import get_paths
        return join(get_paths()['data'], 'lib')

    @staticmethod
    def debugOn(*args):
        from pyworkflow.utils import envVarOn
        return bool(envVarOn(SCIPION_DEBUG, *args))

    @staticmethod
    def toggleDebug():

        newValue = not Config.debugOn()

        os.environ[SCIPION_DEBUG] = str(newValue)

    @classmethod
    def getExternalJsonTemplates(cls):
        return os.path.dirname(cls.SCIPION_CONFIG)


def join(*paths):
    """ join paths from HOME . """
    return os.path.join(HOME, *paths)


__resourcesPath = [join('resources')]


def findResource(filename):
    from .utils.path import findFile

    return findFile(filename, *__resourcesPath)

def genNotesHeading():
    return SCIPION_NOTES_HEADING_MSG.format(Config.SCIPION_NOTES_FILE)
