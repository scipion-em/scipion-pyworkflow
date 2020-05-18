import ast
import importlib
import inspect
import os
import sys
import types

from .constants import *

HOME = os.path.abspath(os.path.dirname(__file__))
PYTHON = os.environ.get(SCIPION_PYTHON, SCIPION_PYTHON_DEFAULT)


def join(*paths):
    """ join paths from HOME . """
    return os.path.join(HOME, *paths)


__resourcesPath = [join('resources')]


def findResource(filename):
    from .utils.path import findFile
    return findFile(filename, *__resourcesPath)


def genNotesHeading():
    return SCIPION_NOTES_HEADING_MSG


def getAppsPath(*paths):
    return join(APPS, *paths)


def getSyncDataScript():
    return getAppsPath(PW_SYNC_DATA)


def getScheduleScript():
    return getAppsPath(PW_SCHEDULE_RUN)


def getPwProtMpiRunScript():
    return getAppsPath(PW_PROTOCOL_MPIRUN)


def getTestsScript():
    return getAppsPath(PW_RUN_TESTS)


def getViewerScript():
    return getAppsPath(PW_VIEWER)


def getPyworkflowPath():
    """ Returns the path where pyworkflow is"""
    return os.path.dirname(__file__)


def getModuleFolder(moduleName):
    """ Returns the path of a module without importing it"""
    spec = importlib.util.find_spec(moduleName)
    return os.path.dirname(spec.origin)


class Config:
    """ Main Config for pyworkflow. It contains the main configuration values
    providing default values or, if present, taking them from the environment.
    It has SCIPION_HOME, SCIPION_USER_DATA ...
    Necessary value is SCIPION_HOME and has to be present in the environment"""

    @staticmethod
    def __get(key, default):
        value = os.environ.get(key, default)
        # Expand user and variables if string value
        if isinstance(value, str):
            value = os.path.expandvars(os.path.expanduser(value))

        return value

    class Root:
        """ Simple helper to return path from a root. """
        def __init__(self, root):
            self._root = root

        def join(self, *path):
            # We need to consider variable in the config with ~
            expanded = os.path.expanduser(os.path.join(*path))

            # join will not join if expanded is absolute
            return os.path.join(self._root, expanded)

    # Home for scipion
    _get = __get.__func__
    SCIPION_HOME = os.path.abspath(_get(SCIPION_HOME_VAR, ''))
    _root = Root(SCIPION_HOME)
    _join = _root.join

    # SCIPION PATHS
    # Where to install software
    SCIPION_SOFTWARE = _join(_get('SCIPION_SOFTWARE', 'software'))

    # Where is the input data for tests...also where it will be downloaded
    SCIPION_TESTS = _join(_get('SCIPION_TESTS', os.path.join('data', 'tests')))

    # User dependent paths
    # Location for scipion projects
    SCIPION_USER_DATA = _get('SCIPION_USER_DATA', '~/ScipionUserData')

    # General purpose scipion tmp folder
    SCIPION_TMP = _get('SCIPION_TMP', _join(SCIPION_USER_DATA, 'tmp'))
    # LOGS PATHS
    # Path for Scipion logs
    SCIPION_LOGS = _get('SCIPION_LOGS', _join(SCIPION_USER_DATA,'logs'))

    # Get general log file path
    SCIPION_LOG = _join(SCIPION_LOGS, 'scipion.log')

    # Where the output of the tests will be stored
    SCIPION_TESTS_OUTPUT = _get('SCIPION_TESTS_OUTPUT', _join(SCIPION_USER_DATA, 'Tests'))

    SCIPION_SUPPORT_EMAIL = _get('SCIPION_SUPPORT_EMAIL', 'scipion@cnb.csic.es')

    SCIPION_LOGO = _get('SCIPION_LOGO', 'scipion_logo.gif')

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

    SCIPION_CWD = _get('SCIPION_CWD', os.path.abspath(os.getcwd()))

    try:
        VIEWERS = ast.literal_eval(_get('VIEWERS', "{}"))
    except Exception as e:
        VIEWERS = {}
        print("ERROR loading preferred viewers, VIEWERS variable will be ignored")
        print(e)

    SCIPION_DOMAIN = _get(SCIPION_DOMAIN, None)
    SCIPION_TESTS_CMD = _get(SCIPION_TESTS_CMD, getTestsScript())

    # ---- Getters ---- #
    # Getters are alternatives to offer a variable, but preventing it to be stored in the config
    @classmethod
    def getLibFolder(cls):
        """
        :return: Folder where libraries must be placed in case a binding needs them
        """
        lib = cls._join(cls.SCIPION_SOFTWARE, 'lib')
        os.makedirs(lib, exist_ok=True)
        return lib

    @classmethod
    def getBindingsFolder(cls):
        """
        Folder where bindings must be placed. This folder is added to sys.path at launching time.
        If the binding depends on a dynamic libraries, those must be placed at cls.getLibFolder()
        :return:   The bindings folder
        """
        bindings = cls._join(cls.SCIPION_SOFTWARE, 'bindings')
        os.makedirs(bindings, exist_ok=True)
        return bindings

    @classmethod
    def getLogsFolder(cls):
        """
        Folder where scipion logs must be placed. The folder is created         
        """
        logsFolder = cls.SCIPION_LOGS
        os.makedirs(logsFolder, exist_ok=True)
        return logsFolder

    @classmethod
    def getVars(cls):
        """ Return a dictionary with all variables defined
        in this Config.
        """
        configVars = dict()
        # For each variable, also in base classes
        for baseCls in inspect.getmro(cls):
            for name, value in vars(baseCls).items():
                # Skip methods and internal attributes starting with __
                # (e.g __doc__, __module__, etc)
                if isinstance(value, str) and not name.startswith('__'):
                    configVars[name] = value
        return configVars

    @classmethod
    def printVars(cls):
        """ Print the variables dict, mostly for debugging. """
        from .utils import prettyDict
        prettyDict(cls.getVars())

    @classmethod
    def getDomain(cls):
        """ Import domain module from path or name defined in SCIPION_DOMAIN.
        """
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
        from .utils import envVarOn
        return bool(envVarOn(SCIPION_DEBUG, *args))

    @staticmethod
    def toggleDebug():
        newValue = not Config.debugOn()
        os.environ[SCIPION_DEBUG] = str(newValue)
        os.environ[SCIPION_DEBUG_NOCLEAN] = str(newValue)

    @classmethod
    def getExternalJsonTemplates(cls):
        return os.path.dirname(cls.SCIPION_CONFIG)


# Add bindings folder to sys.path
sys.path.append(Config.getBindingsFolder())
