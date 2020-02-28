import ast
import importlib
import os
import sys
import types

from pyworkflow import (SCIPION_TESTS_CMD, getTestsScript, SCIPION_HOME_VAR,
                        SCIPION_NOTES_FILE, SCIPION_NOTES_PROGRAM, SCIPION_NOTES_ARGS,
                        SCIPION_DOMAIN, SCIPION_DEBUG, SCIPION_DEBUG_NOCLEAN)


_get = os.environ.get  # shortcut

_scipionHome = os.path.abspath(_get(SCIPION_HOME_VAR, ''))  # Home for scipion

class Config:
    """ Main Config for pyworkflow. It contains the main configuration values
    providing default values or, if present, taking them from the environment.
    It has SCIPION_HOME, SCIPION_USER_DATA ...
    Necessary value is SCIPION_HOME and has to be present in the environment"""

    # SCIPION PATHS
    SCIPION_HOME = _scipionHome

    # This will prepend SCIPION_HOME in case the variable is not absolute
    __prefixHome = lambda path: path if os.path.isabs(path) else os.path.join(_scipionHome, path)

    # Where to install software
    SCIPION_SOFTWARE = __prefixHome(_get('SCIPION_SOFTWARE','software'))

    # Where are the libraries and bindings folder
    SCIPION_LIBS = os.path.join(SCIPION_SOFTWARE, 'lib')
    SCIPION_BINDINGS = os.path.join(SCIPION_SOFTWARE, 'bindings')

    # Where is the input data for tests...also where it will be downloaded
    SCIPION_TESTS = __prefixHome(_get('SCIPION_TESTS',
                          os.path.join('data', 'tests')))

    # User dependent paths
    # Location for scipion projects
    SCIPION_USER_DATA = os.path.expanduser(_get('SCIPION_USER_DATA',
                                                 '~/ScipionUserData'))

    # General purpose scipion tmp folder
    SCIPION_TMP = _get('SCIPION_TMP',
                        os.path.join(SCIPION_USER_DATA, 'tmp'))
    # LOGS PATHS
    # Path for Scipion logs
    SCIPION_LOGS = os.path.expanduser(_get('SCIPION_LOGS', os.path.join(SCIPION_USER_DATA,'logs')))

    # Get general log file path
    LOG_FILE = os.path.join(SCIPION_LOGS, 'scipion.log')

    # Where the output of the tests will be stored
    SCIPION_TESTS_OUTPUT = _get('SCIPION_TESTS_OUTPUT',
                                 os.path.join(SCIPION_USER_DATA, 'Tests'))

    SCIPION_SUPPORT_EMAIL = _get('SCIPION_SUPPORT_EMAIL',
                                  'scipion@cnb.csic.es')
    SCIPION_LOGO = _get('SCIPION_LOGO',
                         'scipion_logo.gif')

    # Config folders
    SCIPION_CONFIG = _get('SCIPION_CONFIG', 'scipion.conf')
    SCIPION_LOCAL_CONFIG = _get('SCIPION_LOCAL_CONFIG', SCIPION_CONFIG)
    SCIPION_HOSTS = _get('SCIPION_HOSTS', 'hosts.conf')
    SCIPION_PROTOCOLS = _get('SCIPION_PROTOCOLS', 'protocols.conf')

    SCIPION_PLUGIN_JSON = _get('SCIPION_PLUGIN_JSON', None)
    SCIPION_PLUGIN_REPO_URL = _get('SCIPION_PLUGIN_REPO_URL',
                                    'http://scipion.i2pc.es/getplugins/')

    # REMOTE Section
    SCIPION_URL = _get('SCIPION_URL' , 'http://scipion.cnb.csic.es/downloads/scipion')
    SCIPION_URL_SOFTWARE = _get('SCIPION_URL_SOFTWARE', SCIPION_URL + '/software')
    SCIPION_URL_TESTDATA = _get('SCIPION_URL_TESTDATA', SCIPION_URL + '/data/tests')

    # Scipion Notes
    SCIPION_NOTES_FILE = _get(SCIPION_NOTES_FILE, 'notes.txt')
    SCIPION_NOTES_PROGRAM = _get(SCIPION_NOTES_PROGRAM, None)
    SCIPION_NOTES_ARGS = _get(SCIPION_NOTES_ARGS, None)

    # Aspect
    SCIPION_FONT_NAME = _get('SCIPION_FONT_NAME', "Helvetica")
    SCIPION_FONT_SIZE = int(_get('SCIPION_FONT_SIZE', 10))

    # Notification
    SCIPION_NOTIFY = _get('SCIPION_NOTIFY', 'True')

    try:
        VIEWERS = ast.literal_eval(_get('VIEWERS', "{}"))
    except Exception as e:
        VIEWERS = {}
        print("ERROR loading preferred viewers, VIEWERS variable will be ignored")
        print(e)

    SCIPION_DOMAIN = _get(SCIPION_DOMAIN, None)
    SCIPION_TESTS_CMD = _get(SCIPION_TESTS_CMD, getTestsScript())

    @classmethod
    def getVariableDict(cls):
        """ fill environment with own values"""
        myDict = dict()
        # For each attribute
        for name, value in vars(cls).items():
            # Skip methods, only str objects
            if isinstance(value, str):
                # Skip starting with __ : __doc__, __module__
                if not name.startswith("__"):
                    # Update environment
                    myDict[name] =value

        return myDict

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
        return os.path.join(get_paths()['data'], "lib")

    @staticmethod
    def debugOn(*args):
        from pyworkflow.utils import envVarOn
        return bool(envVarOn(SCIPION_DEBUG, *args))

    @staticmethod
    def toggleDebug():
        newValue = not Config.debugOn()
        os.environ[SCIPION_DEBUG] = str(newValue)
        os.environ[SCIPION_DEBUG_NOCLEAN] = str(newValue)

    @classmethod
    def getExternalJsonTemplates(cls):
        return os.path.dirname(cls.SCIPION_CONFIG)
