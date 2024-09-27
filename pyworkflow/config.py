import logging

logger = logging.getLogger(__file__)
import ast
import importlib
import inspect
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


__resourcesPath = join('resources')

def getResourcesPath(file=None):

    return __resourcesPath if file is None else os.path.join(__resourcesPath, file)

def findResource(filename):
    from .utils.path import findFile
    return findFile(filename, *[__resourcesPath])


def genNotesHeading():
    return SCIPION_NOTES_HEADING_MSG


def getAppsPath(*paths):
    return join(APPS, *paths)


def getSyncDataScript():
    return getAppsPath(PW_SYNC_DATA)


def getScheduleScript():
    return getAppsPath(PW_SCHEDULE_RUN)


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


def validColor(colorname):
    """ If it can be converted to rgb is a valid color"""
    from matplotlib.colors import to_rgb
    to_rgb(colorname)
    return colorname

class VarTypes(Enum):
    STRING = 0
    BOOLEAN = 1
    PATH = 2  # Any Path: Folder or file
    INTEGER = 3
    DECIMAL = 4
    FILENAME = 5  # Just the base name of a file
    FOLDER = 6  # A folder

class Variable:
    def __init__(self, name, description, source, value, default, var_type: VarTypes = VarTypes.STRING, isDefault=None):
        self.name = name
        self.description = description
        self.source = source
        self.value = value
        self.default = default
        self.isDefault = isDefault if isDefault is not None else self._isValueDefault()
        self.var_type = var_type
    def setToDefault(self):
        self.isDefault=True
        self.value=self.default

    def setValue(self, new_value):
        self.value = new_value
        self.isDefault= self._isValueDefault()
    def _isValueDefault(self):
        return self.value==self.default
class VariablesRegistry:
    _variables={}

    def __init__(self):
        raise RuntimeError("Variables class doesn't need to be instantiated.")
    @classmethod
    def register(cls, variable: Variable):
        cls._variables[variable.name] = variable

    @classmethod
    def variables(cls):
        return cls._variables

    @classmethod
    def __iter__(cls):
        """ Iterate alphabetically"""
        for key in sorted(cls._variables):
            yield cls._variables[key]

    @classmethod
    def save(cls, path):
        """ Saves the variables in the path specified """
        from pyworkflow.utils import backup
        backup(path)

        with open(path,"w") as fh:
            # Save the section as in any python config file format.
            fh.write("[PYWORKFLOW]\n")
            for var in cls.__iter__():
                if var.source == "pyworkflow" and not var.isDefault:
                    fh.write("%s=%s\n" % (var.name, var.value))

            fh.write("\n[PLUGINS]\n")
            for var in cls._variables.values():
                if var.source != "pyworkflow" and not var.isDefault:
                    fh.write("%s=%s\n" % (var.name, var.value))


class Config:
    """ Main Config for pyworkflow. It contains the main Scipion configuration variables
    providing default values or, if present, taking them from the environment.
    Necessary value is SCIPION_HOME and has to be present in the environment"""

    @staticmethod
    def __get(key, default, description=None, caster=None, var_type:VarTypes=VarTypes.STRING, source="pyworkflow"):

        if key in os.environ:
            value = os.environ.get(key)
            isDefault = (value==default)
        else:
            isDefault = True
            value = default

        # If the caster is passed do the casting, if fails go back to default
        if caster:
            try:
                value=caster(value)
            except:
                logger.warning("Variable %s has this value %s that can't be casted to the right type (%s). Using %s (default value)" %
                               (key,value, caster, default))
                value = default
        # If empty use default value
        if value == "" != default:
            logger.warning("%s variable is empty, falling back to default value (%s)" % (key, default))
            value = default

        # Expand user and variables if string value
        if isinstance(value, str):
            value = os.path.expandvars(os.path.expanduser(value))

        # Register the variable
        VariablesRegistry.register(Variable(key,description, source, value, default, var_type=var_type, isDefault=isDefault))
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
    SCIPION_HOME = os.path.abspath(_get(SCIPION_HOME_VAR, '',
    "Path where Scipion is installed. Other paths are based on this like SCIPION_SOFTWARE, SCIPION_TESTS,... unless specified"))

    # False if SCIPION_HOME is not found in the environment. To distinguish API documentation generation execution.
    SCIPION_HOME_DEFINED = SCIPION_HOME != ''

    _root = Root(str(SCIPION_HOME))
    _join = _root.join

    # Internal cached variables, use __ so they are not returned in getVars
    __activeColor = None
    __defaultSpritesFile = _join(getResourcesPath(),'sprites.png')

    CONDA_ACTIVATION_CMD = _get(CONDA_ACTIVATION_CMD_VAR,'',
    "str: Command to activate/initialize conda itself. Do not confuse it with 'conda activate'. It should be defined at installation time. It looks like this: eval \"$(/extra/miniconda3/bin/conda shell.bash hook)\"")

    # SCIPION PATHS
    SCIPION_SOFTWARE = _get('SCIPION_SOFTWARE', _join('software'),
    "Path where Scipion will install the software. Defaults to SCIPION_HOME/software.", var_type=VarTypes.FOLDER)

    SCIPION_TESTS = _get('SCIPION_TESTS', _join('data', 'tests'),
    "Path where to find/download test data. Defaults to SCIPION_HOME/data/tests.", var_type=VarTypes.FOLDER)

    # User dependent paths
    SCIPION_USER_DATA = _get('SCIPION_USER_DATA', '~/ScipionUserData',
    "Path where Scipion projects are or will be created. Defaults to ~/ScipionUserData", var_type=VarTypes.FOLDER)

    # LOGGING variables
    SCIPION_LOGS = _get('SCIPION_LOGS', _join(SCIPION_USER_DATA, 'logs'),
    "Folder for Scipion logs used by the GUI. Defaults to SCIPION_USER_DATA/logs.", var_type=VarTypes.FOLDER)

    SCIPION_LOG_CONFIG = _get('SCIPION_LOG_CONFIG', None,
    "Optional. Path to a python logging configuration file to fine tune the logging.", var_type=VarTypes.PATH)

    SCIPION_LOG = _get('SCIPION_LOG', _join(SCIPION_LOGS, 'scipion.log'),
    "Path to the file where scipion will write GUI logging messages. Defaults to SCIPION_LOGS/scipion.log", var_type=VarTypes.PATH)

    SCIPION_LOG_FORMAT = _get('SCIPION_LOG_FORMAT', "%(message)s",
    "str: Format for all the log lines, defaults to %(message)s. To compose the format see https://docs.python.org/3/library/logging.html#logrecord-attributes")

    SCIPION_LOG_LEVEL = _get(SCIPION_LOG_LEVEL, 'INFO',
    "Default logging level. String among CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET. Default value is INFO.")

    NO_COLOR = _get('NO_COLOR', '',
    "str: Comply with https://no-color.org/ initiative. Set it to something different than '' to deactivate colors in the output.")

    SCIPION_SCRATCH = _get(SCIPION_SCRATCH, None,
    "Optional. Path to a location mounted in a scratch drive (SSD,...)")

    SCIPION_TESTS_OUTPUT = _get('SCIPION_TESTS_OUTPUT', _join(SCIPION_USER_DATA, 'Tests'),
    "Path to a folder where the output of the tests will be written. Defaults to SCIPION_USER_DATA/Tests.", var_type=VarTypes.FOLDER)

    SCIPION_TEST_NOSYNC = _get('SCIPION_TEST_NOSYNC', FALSE_STR,
    "Set it to 1, True, Yes or y to cancel test dataset synchronization. Needed when updating files in a dataset.") != FALSE_STR

    SCIPION_SUPPORT_EMAIL = 'scipion@cnb.csic.es'

    # Config variables
    SCIPION_CONFIG = _get('SCIPION_CONFIG', _join('config','scipion.conf'),
    "Path to the scipion configuration file where all this variables could be defined.", var_type=VarTypes.PATH)

    SCIPION_LOCAL_CONFIG = _get('SCIPION_LOCAL_CONFIG', SCIPION_CONFIG,
    "Path to an optional/extra/user configuration file meant to overwrite default variables.", var_type=VarTypes.PATH)

    SCIPION_HOSTS = _get('SCIPION_HOSTS', _join('config','hosts.conf'),
    "Path to the host.cof file to allow scipion to use queue engines and run in HPC environments.")

    SCIPION_PROTOCOLS = _get('SCIPION_PROTOCOLS', _join('config','protocols.conf'),
    "Custom conf file to extend the protocols tree view panel (panel on the left)")

    SCIPION_PLUGIN_JSON = _get('SCIPION_PLUGIN_JSON', None,
    "Optional. Path to get the json file with all the plugins available for Scipion.")

    SCIPION_PLUGIN_REPO_URL = _get('SCIPION_PLUGIN_REPO_URL',
                                   'https://scipion.i2pc.es/getplugins/',
    "Url from where to get the list of plugins.")

    # REMOTE Section
    SCIPION_URL = 'https://scipion.cnb.csic.es/downloads/scipion'
    SCIPION_URL_SOFTWARE = SCIPION_URL + '/software'
    SCIPION_URL_TESTDATA = SCIPION_URL + '/data/tests'

    # Scipion Notes
    SCIPION_NOTES_FILE = _get(SCIPION_NOTES_FILE, 'notes.txt',
    "Name of the file where to write per project notes.")

    SCIPION_NOTES_PROGRAM = _get(SCIPION_NOTES_PROGRAM, None,
    "Command or program to use to open the notes file. Otherwise system will extension association will take place.")

    SCIPION_NOTES_ARGS = _get(SCIPION_NOTES_ARGS, None)

    # External text editor:
    SCIPION_TEXT_EDITOR = _get(SCIPION_TEXT_EDITOR, '',
    "Preferred text editor executable.", caster=str)

    # Aspect
    SCIPION_FONT_NAME = _get('SCIPION_FONT_NAME', "Helvetica",
    "Name of the font to use in Scipion GUI. Defaults to Helvetica.")

    SCIPION_FONT_SIZE = _get('SCIPION_FONT_SIZE', SCIPION_DEFAULT_FONT_SIZE,
    "Size of the 'normal' font to be used in Scipion GUI. Defaults to 10.", caster=int)

    SCIPION_MAIN_COLOR = _get('SCIPION_MAIN_COLOR', Color.MAIN_COLOR,
    "str: Main color of the GUI. Background will be white, so for better contrast choose a dark color. Probably any name here will work: https://matplotlib.org/stable/gallery/color/named_colors.html",
                              caster=validColor)

    SCIPION_BG_COLOR = _get('SCIPION_BG_COLOR', Color.BG_COLOR,
    "str: Main background color of the GUI. Default is white, chose a light one. Probably any name here will work: https://matplotlib.org/stable/gallery/color/named_colors.html",
                            validColor)

    SCIPION_CONTRAST_COLOR = _get('SCIPION_CONTRAST_COLOR', 'cyan',
    "Color used to highlight features over grayscaled images.", caster=validColor)

    SCIPION_SPRITES_FILE = _get('SCIPION_SPRITES_FILE', __defaultSpritesFile,
    "File (png) with the icons in a collage. Default is found at pyworkflow/resources/sprites.png. And a GIMP file could be found at the same folder in the github repo.")

    SCIPION_SHOW_TEXT_IN_TOOLBAR = _get('SCIPION_SHOW_TEXT_IN_TOOLBAR', TRUE_STR,
    "Define it to anything else except False to show the label of the icons. It will take more space.") == TRUE_STR

    SCIPION_ICON_ZOOM = _get('SCIPION_ICON_ZOOM', 50,
    "Define it to anything else except False to show the label of the icons. It will take more space.", var_type=VarTypes.INTEGER, caster=int)

    # Notification
    SCIPION_NOTIFY = _get('SCIPION_NOTIFY', TRUE_STR,
    "If set to False, Scipion developers will know almost nothing about Scipion usage and will have less information to improve it.") == TRUE_STR

    # *** Execution variables ***
    SCIPION_CWD = _get('SCIPION_CWD', os.path.abspath(os.getcwd()),
    "Directory when scipion was launched")

    SCIPION_GUI_REFRESH_IN_THREAD = _get('SCIPION_GUI_REFRESH_IN_THREAD', FALSE_STR,
    "True to refresh the runs graph with a thread. Unstable.") != FALSE_STR

    SCIPION_GUI_REFRESH_INITIAL_WAIT = _get("SCIPION_GUI_REFRESH_INITIAL_WAIT", 5,
    "Seconds to wait after a manual refresh", caster=int)

    SCIPION_GUI_CANCEL_AUTO_REFRESH = _get("SCIPION_GUI_CANCEL_AUTO_REFRESH",FALSE_STR,
    "Set it to True to cancel automatic refresh of the runs.") != FALSE_STR

    # Cancel shutil fast copy. In GPFS, shutil.copy does fail when trying a fastcopy and does not
    # fall back on the slow copy. For legacy reasons None is also False.
    SCIPION_CANCEL_FASTCOPY = _get('SCIPION_CANCEL_FASTCOPY', FALSE_STR,
    "Cancel fast copy done by shutil (copying files) when it fails. Has happened in GPFS environments. Defaults to False. None is also False otherwise fastcopy is cancelled."
                                   ) not in [NONE_STR, FALSE_STR]

    # Priority package list: This variable is used in the view protocols in
    # order to load first the plugins that contains the main protocols.conf
    # sections, so other plugins can define only their sections avoiding
    # duplicating all the sections in all plugins. Scipion app is currently defining it for em tomo and chem
    SCIPION_PRIORITY_PACKAGE_LIST = _get('SCIPION_PRIORITY_PACKAGE_LIST', EMPTY_STR)

    SCIPION_STEPS_CHECK_SEC = _get('SCIPION_STEPS_CHECK_SEC', 5,
    "Number of seconds to wait before checking if new input is available in streamified protocols.", caster=int)

    SCIPION_UPDATE_SET_ATTEMPTS = _get('SCIPION_UPDATE_SET_ATTEMPTS', 3,
    "Number of attempts to modify the protocol output before failing. The default value is 3", caster=int)

    SCIPION_UPDATE_SET_ATTEMPT_WAIT = _get('SCIPION_UPDATE_SET_ATTEMPT_WAIT', 2,
    "Time in seconds to wait until the next attempt when checking new outputs. The default value is 2 seconds", caster=int)

    SCIPION_USE_QUEUE = _get("SCIPION_USE_QUEUE", FALSE_STR,
    "Default value for using the queue. By default is False. ANY value will be True except and empty value. \"False\" or \"0\" will be True too.")!= FALSE_STR

    SCIPION_DEFAULT_EXECUTION_ACTION = _get('SCIPION_DEFAULT_EXECUTION_ACTION', DEFAULT_EXECUTION_ACTION_ASK,
    """Ask if you want to launch a single protocol or a sub-workflow. The default value is 1
       1: Scipion always ask
       2: Run a single protocol
       3: Run a sub-workflow """, caster=int)

    SCIPION_MAPPER_USE_TEMPLATE = _get('SCIPION_MAPPER_USE_TEMPLATE', TRUE_STR,
    "Set it to False to force instantiation for each item during sets iterations. Experimental. This penalize the iteration but avoids"
    "the use of .clone() ot the items.") == TRUE_STR

    try:
        VIEWERS = ast.literal_eval(_get('VIEWERS', "{}", "Json string to define which viewer are the default ones per output type."))
    except Exception as e:
        VIEWERS = {}
        logger.error("ERROR loading preferred viewers, VIEWERS variable will be ignored", exc_info=e)

    SCIPION_DOMAIN = _get(SCIPION_DOMAIN, None, "Domain base class. Ignore.")
    SCIPION_TESTS_CMD = _get(SCIPION_TESTS_CMD, getTestsScript(), "Command to run tests")

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
                if isinstance(value, (str, int)) and not name.startswith('__'):
                    configVars[name] = str(value)
        return configVars

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
        return cls.SCIPION_GUI_REFRESH_IN_THREAD

    @classmethod
    def getExternalJsonTemplates(cls):
        return os.path.dirname(cls.SCIPION_CONFIG)

    @classmethod
    def getWizardMaskColor(cls):
        """ Color is a name"""
        from matplotlib.colors import to_rgb
        return list(to_rgb(cls.SCIPION_CONTRAST_COLOR))

    @classmethod
    def getPriorityPackageList(cls):
        if cls.SCIPION_PRIORITY_PACKAGE_LIST != EMPTY_STR:
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
            from pyworkflow.utils import lighter, rgb_to_hex
            from matplotlib.colors import to_rgb
            rgb_main = to_rgb(cls.SCIPION_MAIN_COLOR)
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

    @classmethod
    def isCondaInstallation(cls):
        """ Returns true if the scipion installation is done using conda"""

        # Get the CONDA_PYTHON_EXE
        # NOTE: This will not work when calling scipion python directly! But should works using the launcher.
        envFolder = os.environ.get("CONDA_PREFIX", None)

        # No conda variable... virtualenv installation!!
        if envFolder is None:
            return False
        else:
            from pyworkflow.utils import getPython
            # Conda available.... let's check if it is active the same scipion env
            condaExe = os.path.join(envFolder, "bin", "python")
            return condaExe == getPython()

    @classmethod
    def getSpritesFile(cls):
        if not os.path.exists(Config.SCIPION_SPRITES_FILE):
            return cls.__defaultSpritesFile
        else:
            return Config.SCIPION_SPRITES_FILE


# Add bindings folder to sys.path
sys.path.append(Config.getBindingsFolder())

# Cancel fast copy
if Config.SCIPION_CANCEL_FASTCOPY:
    shutil._USE_CP_SENDFILE = False
