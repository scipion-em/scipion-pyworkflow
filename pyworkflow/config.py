
import logging

logger = logging.getLogger(__file__)
import ast
import importlib
import inspect
import json
import os
import shutil
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
    """ Main Config for pyworkflow. It contains the main Scipion configuration variables
    providing default values or, if present, taking them from the environment.
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
    "Path where Scipion is installed. Other paths are based on this like SCIPION_SOFTWARE, SCIPION_TESTS,... unless specified"

    # Actual SCIPION_HOME
    SCIPION_HOME_DEFINED = _get(SCIPION_HOME_VAR, False)
    "False if SCIPION_HOME is found in the environment"

    _root = Root(SCIPION_HOME)
    _join = _root.join

    # Internal cached variables, use __ so they are not returned in getVars
    __activeColor = None

    CONDA_ACTIVATION_CMD = _get(CONDA_ACTIVATION_CMD_VAR,'')
    "Command to activate/initialize conda itself. Do not confuse it with 'conda activate'. It should be defined at installation time. It looks like this: eval \"$(/extra/miniconda3/bin/conda shell.bash hook)\""

    # SCIPION PATHS
    SCIPION_SOFTWARE = _join(_get('SCIPION_SOFTWARE', 'software'))
    "Path where Scipion will install the software. Defaults to SCIPION_HOME/software."

    SCIPION_TESTS = _join(_get('SCIPION_TESTS', os.path.join('data', 'tests')))
    "Path where to find/download test data. Defaults to SCIPION_HOME/data/tests."

    # User dependent paths
    SCIPION_USER_DATA = _get('SCIPION_USER_DATA', '~/ScipionUserData')
    "Path where Scipion projects are or will be created. Defaults to ~/ScipionUserData"

    SCIPION_TMP = _get('SCIPION_TMP', _join(SCIPION_USER_DATA, 'tmp'))
    "General purpose scipion tmp folder. Defaults to SCIPION_USER_DATA/tmp"

    # LOGGING variables
    SCIPION_LOGS = _get('SCIPION_LOGS', _join(SCIPION_USER_DATA, 'logs'))
    "Path for Scipion logs folder used by the GUI. Defaults to SCIPION_USER_DATA/logs."

    SCIPION_LOG_CONFIG = _get('SCIPION_LOG_CONFIG', None)
    "Optional. Path to a python logging configuration file fine tune the logging."

    SCIPION_LOG = _join(SCIPION_LOGS, 'scipion.log')
    "Path to the file where scipion will write GUI logging messages. Defaults to SCIPION_LOGS/scipion.log"

    SCIPION_LOG_FORMAT = _get('SCIPION_LOG_FORMAT', "%(message)s")
    "Format for all the log lines, defaults to %(message)s. To compose the format see https://docs.python.org/3/library/logging.html#logrecord-attributes"

    SCIPION_LOG_LEVEL = _get(SCIPION_LOG_LEVEL, 'INFO')
    "Default logging level. String among CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET. Default value is INFO."

    NO_COLOR = _get('NO_COLOR', '')
    "Comply with https://no-color.org/ initiative. Set it to something different than '' to deactivate colors in the output."

    SCIPION_SCRATCH = _get(SCIPION_SCRATCH, None)
    "Optional. Path to a location mounted in a scratch drive (SSD,...)"

    SCIPION_TESTS_OUTPUT = _get('SCIPION_TESTS_OUTPUT', _join(SCIPION_USER_DATA, 'Tests'))
    "Path to a folder Where the output of the tests will be written. Defaults to SCIPION_USER_DATA/Tests."

    SCIPION_TEST_NOSYNC = _get('SCIPION_TEST_NOSYNC', "False")
    "Set it to 1, True, Yes or y to cancel test dataset synchronization. Needed when updating files in a dataset."

    SCIPION_SUPPORT_EMAIL = _get('SCIPION_SUPPORT_EMAIL', 'scipion@cnb.csic.es')

    SCIPION_LOGO = _get('SCIPION_LOGO', 'scipion_logo.gif')

    # Config variables
    SCIPION_CONFIG = _get('SCIPION_CONFIG', 'scipion.conf')
    "Path to the scipion configuration file where all this variables could be defined."

    SCIPION_LOCAL_CONFIG = _get('SCIPION_LOCAL_CONFIG', SCIPION_CONFIG)
    "Path to an optional/extra/user configuration file meant to overwrite default variables."

    SCIPION_HOSTS = _get('SCIPION_HOSTS', 'hosts.conf')
    "Path to the host.cof file to allow scipion to use queue engines and run in HPC environments."

    SCIPION_PROTOCOLS = _get('SCIPION_PROTOCOLS', 'protocols.conf')
    ""

    SCIPION_PLUGIN_JSON = _get('SCIPION_PLUGIN_JSON', None)
    "Optional. Path to get the json file with all the plugins available for Scipion."

    SCIPION_PLUGIN_REPO_URL = _get('SCIPION_PLUGIN_REPO_URL',
                                   'http://scipion.i2pc.es/getplugins/')
    "Url from where to get the list of plugins."

    # REMOTE Section
    SCIPION_URL = _get('SCIPION_URL', 'http://scipion.cnb.csic.es/downloads/scipion')
    SCIPION_URL_SOFTWARE = _get('SCIPION_URL_SOFTWARE', SCIPION_URL + '/software')
    SCIPION_URL_TESTDATA = _get('SCIPION_URL_TESTDATA', SCIPION_URL + '/data/tests')

    # Scipion Notes
    SCIPION_NOTES_FILE = _get(SCIPION_NOTES_FILE, 'notes.txt')
    "Name of the file where to write per project notes."

    SCIPION_NOTES_PROGRAM = _get(SCIPION_NOTES_PROGRAM, None)
    "Command or program to use to open the notes file. Otherwise system will extension association will take place."

    SCIPION_NOTES_ARGS = _get(SCIPION_NOTES_ARGS, None)

    # Aspect
    SCIPION_FONT_NAME = _get('SCIPION_FONT_NAME', "Helvetica")
    "Name of the font to use in Scipion GUI. Defaults to Helvetica."

    SCIPION_FONT_SIZE = int(_get('SCIPION_FONT_SIZE', SCIPION_DEFAULT_FONT_SIZE))
    "Size of the 'normal' font to be used in Scipion GUI. Defaults to 10."

    SCIPION_MAIN_COLOR = _get('SCIPION_MAIN_COLOR', Color.MAIN_COLOR)
    "Main color of the GUI. Background will be white, so for better contrast choose a dark color. Probably any name here will work: https://matplotlib.org/stable/gallery/color/named_colors.html"
    SCIPION_BG_COLOR = _get('SCIPION_BG_COLOR', Color.BG_COLOR)
    "Main background color of the GUI. Default is white, chose a light one. Probably any name here will work: https://matplotlib.org/stable/gallery/color/named_colors.html"


    WIZARD_MASK_COLOR = _get('WIZARD_MASK_COLOR', '[0.125, 0.909, 0.972]')
    "Color to use in some wizards."

    # Notification
    SCIPION_NOTIFY = _get('SCIPION_NOTIFY', 'True')
    "If set to False, Scipion developers will know almost nothing about Scipion usage and will have less information to improve it."

    SCIPION_CWD = _get('SCIPION_CWD', os.path.abspath(os.getcwd()))
    "Directory when scipion was launched"

    SCIPION_GUI_REFRESH_IN_THREAD = _get('SCIPION_GUI_REFRESH_IN_THREAD', 'False')
    "True to refresh the runs graph with a thread. Unstable."

    SCIPION_GUI_REFRESH_INITIAL_WAIT = int(_get("SCIPION_GUI_REFRESH_INITIAL_WAIT", 5))
    "Seconds to wait after a manual refresh"

    SCIPION_GUI_CANCEL_AUTO_REFRESH = _get("SCIPION_GUI_CANCEL_AUTO_REFRESH","False")
    "Set it to True to cancel automatic refresh of the runs."

    # Cancel shutil fast copy. In GPFS, shutil.copy does fail when trying a fastcopy and does not fallback on the slow copy.
    SCIPION_CANCEL_FASTCOPY = _get('SCIPION_CANCEL_FASTCOPY', None)
    "Cancel fast copy done by shutil (copying files) when it fails. Has happened in GPFS environments."

    # Priority package list: This variable is used in the view protocols in
    # order to load first the plugins that contains the main protocols.conf
    # sections, so other plugins can define only their sections avoiding
    # duplicating all the sections in all plugins
    SCIPION_PRIORITY_PACKAGE_LIST = _get('SCIPION_PRIORITY_PACKAGE_LIST', None)

    SCIPION_STEPS_CHECK_SEC = int(_get('SCIPION_STEPS_CHECK_SEC', 5))
    "Number of seconds to wait before checking if new input is available in streamified protocols."

    SCIPION_UPDATE_SET_ATTEMPTS = int(_get('SCIPION_UPDATE_SET_ATTEMPTS', 3))
    "Number of attempts to modify the protocol output before failing. The default value is 3"

    SCIPION_UPDATE_SET_ATTEMPT_WAIT = int(_get('SCIPION_UPDATE_SET_ATTEMPT_WAIT', 2))
    "Time in seconds to wait until the next attempt when checking new outputs. The default value is 2 seconds"

    try:
        VIEWERS = ast.literal_eval(_get('VIEWERS', "{}"))
    except Exception as e:
        VIEWERS = {}
        logger.error("ERROR loading preferred viewers, VIEWERS variable will be ignored", exc_info=e)

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
                if (isinstance(value, str) or isinstance(value, int)) and not name.startswith('__'):
                    configVars[name] = str(value)
        return configVars

    @classmethod
    def printVars(cls):
        """ Print the variables' dict, mostly for debugging. """
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
    def debugOn():
        """ Returns a True if debug mode (SCIPION_DEBUG variable) is active """
        from .utils import envVarOn
        return bool(envVarOn(SCIPION_DEBUG))

    @staticmethod
    def toggleDebug():
        debugOn = not Config.debugOn()
        os.environ[SCIPION_DEBUG] = str(debugOn)
        os.environ[SCIPION_DEBUG_NOCLEAN] = str(debugOn)
        os.environ[SCIPION_LOG_LEVEL] = "INFO" if not debugOn else "DEBUG"

    @staticmethod
    def debugSQLOn():
        from .utils import envVarOn
        return bool(envVarOn(SCIPION_DEBUG_SQLITE))

    @staticmethod
    def toggleDebugSQL():
        newValue = not Config.debugSQLOn()
        os.environ[SCIPION_DEBUG_SQLITE] = str(newValue)

    @classmethod
    def refreshInThreads(cls):
        from .utils import strToBoolean
        return strToBoolean(cls.SCIPION_GUI_REFRESH_IN_THREAD)

    @classmethod
    def getExternalJsonTemplates(cls):
        return os.path.dirname(cls.SCIPION_CONFIG)

    @classmethod
    def getWizardMaskColor(cls):
        return json.loads(cls.WIZARD_MASK_COLOR)

    @classmethod
    def getPriorityPackageList(cls):
        if cls.SCIPION_PRIORITY_PACKAGE_LIST is not None:
            return cls.SCIPION_PRIORITY_PACKAGE_LIST.split(" ")
        else:
            return []

    @classmethod
    def getStepsCheckSeconds(cls):
        return cls.SCIPION_STEPS_CHECK_SEC

    @classmethod
    def getUpdateSetAttempts(cls):
        return cls.SCIPION_UPDATE_SET_ATTEMPTS

    @classmethod
    def getUpdateSetAttemptsWait(cls):
        return cls.SCIPION_UPDATE_SET_ATTEMPT_WAIT

    @classmethod
    def colorsInTerminal(cls):
        """ Returns true if colors are allowed. Based on NO_COLOR variable. Undefined or '' colors are enabled"""
        return cls.NO_COLOR == ''


    @classmethod
    def getActiveColor(cls):
        """ Returns a color lighter than the SCIPION_MAIN_COLOR"""

        if cls.__activeColor is None:
            import matplotlib.colors
            from pyworkflow.utils import lighter, rgb_to_hex

            rgb_main = matplotlib.colors.to_rgb(cls.SCIPION_MAIN_COLOR)
            rgb_main = (rgb_main[0] * 255, rgb_main[1] * 255, rgb_main[2] * 255)
            rgb_active = lighter(rgb_main, 0.3)
            cls.__activeColor = rgb_to_hex(rgb_active)

        return cls.__activeColor

    @classmethod
    def isScipionRunning(cls):
        """ Returns true if this execution is understood to be running Scipion.
        In some case, documentation inspection by sphynx or when packaging a plugin using setup.py
        this code could be reached but is not an actual execution. This is useful for cancelling some actions
        like registering FileHandlers or other stuff not needed when just importing modules."""
        return cls.SCIPION_HOME_DEFINED != False

# Add bindings folder to sys.path
sys.path.append(Config.getBindingsFolder())

# Cancel fast copy
if Config.SCIPION_CANCEL_FASTCOPY:
    shutil._USE_CP_SENDFILE = False
