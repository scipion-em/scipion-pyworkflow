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
import logging

logger = logging.getLogger(__name__)

import contextlib
import sys
import platform
import os
import re
from datetime import datetime, timezone
import traceback
import sysconfig

import bibtexparser
import numpy as np
import math
from pyworkflow.constants import StrColors, TRUE_YES_ON_
from pyworkflow import Config


def prettyDate(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif type(time) is float:
        diff = now - datetime.fromtimestamp(int(time))
    elif isinstance(time, datetime):
        diff = now - time
    elif not time:
        # Avoid now - now (sonar cloud bug)
        copy = now
        diff = now - copy
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(int(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(int(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(int(day_diff / 7)) + " weeks ago"
    if day_diff < 365:
        return str(int(day_diff / 30)) + " months ago"
    return str(int(day_diff / 365)) + " years ago"


def dateStr(dt=None, time=True, secs=False, dateFormat=None):
    """ Get a normal string representation of datetime. 
    If dt is None, use NOW.
    """
    if dt is None:
        dt = datetime.now()
    elif isinstance(dt, float) or isinstance(dt, int):
        dt = datetime.fromtimestamp(dt)

    if dateFormat is None:
        dateFormat = '%d-%m-%Y'
        if time:
            dateFormat += ' %H:%M'
            if secs:
                dateFormat += ':%S'

    return dt.strftime(dateFormat)


prettyTime = dateStr


def prettyTimestamp(dt=None, format='%Y-%m-%d_%H%M%S'):
    if dt is None:
        dt = datetime.now()

    return dt.strftime(format)


def prettySize(size):
    """ Human friendly file size. """
    unit_list = list(zip(['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
                         [0, 0, 1, 2, 2, 2]))
    if size > 1:
        exponent = min(int(math.log(size, 1024)), len(unit_list) - 1)
        quotient = float(size) / 1024 ** exponent
        unit, num_decimals = unit_list[exponent]
        format_string = '{:.%sf} {}' % num_decimals
        return format_string.format(quotient, unit)
    if size == 0:
        return '0 bytes'
    if size == 1:
        return '1 byte'


def prettyDelta(timedelta):
    """ Remove the milliseconds of the timedelta. """
    return str(timedelta).split('.')[0]


def to_utc(t):
    """ Make date conversions to utc"""
    return datetime.fromtimestamp(t, tz=timezone.utc)


def prettyLog(msg):
    logger.info(cyanStr(msg))


class Timer(object):
    """ Simple Timer base in datetime.now and timedelta. """

    def __init__(self, message=""):
        self._message = message

    def tic(self):
        self._dt = datetime.now()

    def getElapsedTime(self):
        return datetime.now() - self._dt

    def toc(self, message='Elapsed:'):
        logger.info(message + str(self.getElapsedTime()))

    def getToc(self):
        return prettyDelta(self.getElapsedTime())

    def __enter__(self):
        self.tic()

    def __exit__(self, type, value, traceback):
        self.toc(self._message)


def timeit(func):
    """
    Decorator function to have a simple measurement of the execution time of a given function.
    To use it ::

        @timeit
        def func(...)
            ...

    """

    def timedFunc(*args, **kwargs):
        t = Timer()
        t.tic()
        result = func(*args, **kwargs)
        t.toc("Function '%s' took" % func)

        return result

    return timedFunc


def trace(nlevels, separator=' --> ', stream=sys.stdout):
    # Example:
    #   @trace(3)
    #   def doRefresh(...
    # gives as output whenever doRefresh is called lines like:
    #   text.py:486 _addFileTab --> text.py:330 __init__ --> doRefresh

    def realTrace(f):
        """ Decorator function to print stack call in a human-readable way.
        """

        def tracedFunc(*args, **kwargs):
            stack = traceback.extract_stack()[-nlevels - 1:-1]
            fmt = lambda x: '%s:%d %s' % (os.path.basename(x[0]), x[1], x[2])
            stList = list(map(fmt, stack))
            stream.write(separator.join(stList + [f.__name__]) + '\n')
            return f(*args, **kwargs)

        return tracedFunc

    return realTrace


def prettyDict(d):
    print("{")
    for k, v in d.items():
        print("    %s: %s" % (k, v))
    print("}")


def prettyXml(elem, level=0):
    """ Add indentation for XML elements for more human readable text. """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for _elem in elem:
            prettyXml(_elem, level + 1)
        if not _elem.tail or not _elem.tail.strip():
            _elem.tail = i


def getUniqueItems(originalList):
    """ Method to remove repeated items from one list 
    originalList -- Original list with repeated items, or not.
    returns -- New list with the content of original list without repeated items
    """
    auxDict = {}
    resultList = [auxDict.setdefault(x, x) for x in originalList if x not in auxDict]
    return resultList

def sortListByList(inList, priorityList):
    """ Returns a list sorted by some elements in a second priorityList"""
    if priorityList:
        sortedList = priorityList + [item for item in inList
                                                     if item not in priorityList]
        return sortedList
    else:
        return inList


def getLocalUserName():
    """ Recover local machine user name.
    returns: Local machine user name.
    """
    import getpass
    return getpass.getuser()


def getLocalHostName():
    return getHostName()


def getHostName():
    """ Return the name of the local machine. """
    import socket
    return socket.gethostname()


def getHostFullName():
    """ Return the fully-qualified name of the local machine. """
    import socket
    return socket.getfqdn()

def getPython():
    return sys.executable

def getPythonPackagesFolder():
    # This does not work on MAC virtual envs
    # import site
    # return site.getsitepackages()[0]

    return sysconfig.get_path("platlib")


# ******************************File utils *******************************

def isInFile(text, filePath):
    """
    Checks if given text is in the given file.

    :param text: Text to check.
    :param filePath: File path to check.

    :returns True if the given text is in the given file,
        False if it is not in the file.

    """
    return any(text in line for line in open(filePath))


def getLineInFile(text, fileName):
    """ Find the line where the given text is located in the given file.

    :param text: Text to check.
    :param filePath: File path to check.

    :return line number where the text was located.

    """
    with open(fileName) as f:
        for i, line in enumerate(f):
            if text in line:
                return i + 1
    return None

def hasAnyFileChanged(files, time):
    """ Returns true if any of the files in files list has been changed after 'time'"""
    for file in files:
        if hasFileChangedSince(file, time):
            return True

    return False

def hasFileChangedSince(file, time):
    """ Returns true if the file has changed after 'time'"""
    modTime = datetime.fromtimestamp(os.path.getmtime(file))
    return time < modTime


# ------------- Colored message strings -----------------------------


def getColorStr(text, color, bold=False):
    """ Add ANSI color codes to the string if there is a terminal sys.stdout.

    :param text: text to be colored
    :param color: red or green
    :param bold: bold the text
    """
    if not Config.colorsInTerminal():
        return text

    attr = [str(color.value)]

    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), text)


def grayStr(text):
    return getColorStr(text, color=StrColors.gray)


def redStr(text):
    return getColorStr(text, color=StrColors.red)


def greenStr(text):
    return getColorStr(text, color=StrColors.green)


def yellowStr(text):
    return getColorStr(text, color=StrColors.yellow)


def blueStr(text):
    return getColorStr(text, color=StrColors.blue)


def magentaStr(text):
    return getColorStr(text, color=StrColors.magenta)


def cyanStr(text):
    return getColorStr(text, color=StrColors.cyan)


def ansi(n, bold=False):
    """Return function that escapes text with ANSI color n."""
    return lambda txt: '\x1b[%d%sm%s\x1b[0m' % (n, ';1' if bold else '', txt)


black, red, green, yellow, blue, magenta, cyan, white = map(ansi, range(30, 38))
blackB, redB, greenB, yellowB, blueB, magentaB, cyanB, whiteB = [
    ansi(i, bold=True) for i in range(30, 38)]

# -------------- Hyper text highlighting ----------------------------
#
# We use a subset of TWiki hyper text conventions.
# In particular:
#     *some_text* will display some_text in bold
#     _some_text_ will display some_text in italic
#     Links:
#         http://www.link-page.com  -> hyperlink using the url as label
#         [[http://www.link-page.com][Link page]] -> hyperlink using "Link page" as label

# Types of recognized styles
HYPER_BOLD = 'bold'
HYPER_ITALIC = 'italic'
HYPER_LINK1 = 'link1'
HYPER_SCIPION_OPEN = 'sci-open'
HYPER_LINK2 = 'link2'
HYPER_ALL = 'all'

# Associated regular expressions
PATTERN_BOLD = r"(^|[\s])[*](?P<bold>[^\s*][^*]*[^\s*]|[^\s*])[*]"
# PATTERN_BOLD = r"[\s]+[*]([^\s][^*]+[^\s])[*][\s]+"
PATTERN_ITALIC = r"(^|[\s])[_](?P<italic>[^\s_][^_]*[^\s_]|[^\s_])[_]"
# PATTERN_ITALIC = r"[\s]+[_]([^\s][^_]+[^\s])[_][\s]+"
PATTERN_LINK1 = r'(?P<link1>http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)'
PATTERN_LINK2 = r"[\[]{2}(?P<link2>[^\s][^\]]+[^\s])[\]][\[](?P<link2_label>[^\s][^\]]+[^\s])[\]]{2}"
# __PATTERN_LINK2 should be first since it could contain __PATTERN_LINK1
PATTERN_ALL = '|'.join([PATTERN_BOLD, PATTERN_ITALIC, PATTERN_LINK2, PATTERN_LINK1])

# Compiled regex
# Not need now, each pattern compiled separately
# HYPER_REGEX = {
#               HYPER_BOLD: re.compile(PATTERN_BOLD),
#               HYPER_ITALIC: re.compile(PATTERN_ITALIC),
#               HYPER_LINK1: re.compile(PATTERN_LINK1),
#               HYPER_LINK2: re.compile(PATTERN_LINK1),
#               }
HYPER_ALL_RE = re.compile(PATTERN_ALL)


def parseHyperText(text, matchCallback):
    """ Parse the text recognizing Hyper definitions below.

    :param matchCallback: a callback function to processing each matching,
        it should accept the type of match (HYPER_BOLD, ITALIC or LINK)

    :return The input text with the replacements made by matchCallback
    """

    def _match(match):
        """ Call the proper matchCallback with some extra info. """
        m = match.group().strip()
        if m.startswith('*'):
            tag = HYPER_BOLD
        elif m.startswith('_'):
            tag = HYPER_ITALIC
        elif m.startswith('http'):
            tag = HYPER_LINK1
        elif m.startswith('[['):
            tag = HYPER_LINK2
        else:
            raise Exception("Bad prefix for HyperText match")
        return matchCallback(match, tag)

    return HYPER_ALL_RE.sub(_match, text)


#    for hyperMode, hyperRegex in HYPER_REGEX.iteritems():
#        text = hyperRegex.sub(lambda match: matchCallback(match, hyperMode), text)
#
#    return text

class LazyDict(object):
    """ Dictionary to be initialized at the moment it is accessed for the first time.
    Initialization is done by a callback passed at instantiation"""
    def __init__(self, callback=dict):
        """ :param callback: method to initialize the dictionary. Should return a dictionary"""
        self.data = None
        self.callback = callback

    def evaluate_callback(self):
        self.data = self.callback()

    def __getitem__(self, name):
        if self.data is None:
            self.evaluate_callback()
        return self.data.__getitem__(name)

    def __setitem__(self, name, value):
        if self.data is None:
            self.evaluate_callback()
        return self.data.__setitem__(name, value)

    def __getattr__(self, name):
        if self.data is None:
            self.evaluate_callback()
        return getattr(self.data, name)

    def __iter__(self):
        if self.data is None:
            self.evaluate_callback()
        return self.data.__iter__()


def parseBibTex(bibtexStr):
    """ Parse a bibtex file and return a dictionary. """

    return bibtexparser.loads(bibtexStr,
                              parser=bibtexparser.bparser.BibTexParser(common_strings=True)
                              ).entries_dict



def isPower2(num):
    """ Return True if 'num' is a power of 2. """
    return num != 0 and ((num & (num - 1)) == 0)


# ---------------------------------------------------------------------------
# Parsing of arguments
# ---------------------------------------------------------------------------

def getListFromRangeString(rangeStr):
    """ Create a list of integers from a string with range definitions.
    Examples:
    "1,5-8,10" -> [1,5,6,7,8,10]
    "2,6,9-11" -> [2,6,9,10,11]
    "2 5, 6-8" -> [2,5,6,7,8]
    """
    # Split elements by command or space
    elements = re.split(r',|\s', rangeStr)
    values = []
    for e in elements:
        if '-' in e:
            limits = e.split('-')
            values += range(int(limits[0]), int(limits[1]) + 1)
        else:
            # If values are separated by comma also splitted 
            values += map(int, e.split())
    return values


def getRangeStringFromList(list):
    left = None
    right = None
    ranges = []

    def addRange():
        if left == right:  # Single element
            ranges.append("%d" % right)
        else:
            ranges.append("%(left)d-%(right)d" % locals())

    for item in list:
        if right is None:
            left = right = item
        else:
            if item == right + 1:
                right += 1
            else:
                addRange()
                left = right = item
    addRange()
    return ','.join(ranges)


def getListFromValues(valuesStr, length=None, caster=str):
    """ Convert a string representing list items into a list.
    The items should be separated by spaces or commas and a multiplier 'x' can be used.
    If length is not None, then the last element will be repeated
    until the desired length is reached.

    Examples:
    '1 1 2x2 4 4' -> ['1', '1', '2', '2', '4', '4']
    '2x3, 3x4, 1' -> ['3', '3', '4', '4', '4', '1']

    """
    result = []
    valuesStr = valuesStr.replace(","," ")
    for chunk in valuesStr.split():
        if caster != str:
            values = chunk.split('x')
        else:
            values=[chunk]

        n = len(values)
        if n == 1:  # 'x' is not present in the chunk, single value
            result += [caster(values[0])]
        elif n == 2:  # multiple the values by the number after 'x'
            result += [caster(values[1])] * int(values[0])
        else:
            raise Exception("More than one 'x' is not allowed in list string value.")

    # If length is passed, we fill the list with 
    # the last element until length is reached
    if length is not None and length > len(result):
        item = result[-1]
        result += [caster(item)] * (length - len(result))

    return result


def getFloatListFromValues(valuesStr, length=None):
    """ Convert a string to a list of floats"""
    return [v for v in getListFromValues(valuesStr, length, caster=float)]


def getBoolListFromValues(valuesStr, length=None):
    """ Convert a string to a list of booleans"""
    from pyworkflow.object import Boolean
    return [v.get() for v in getListFromValues(valuesStr, length, caster=Boolean)]


def getStringListFromValues(valuesStr, length=None):
    """ Convert a string to a list of booleans"""
    from pyworkflow.object import String
    return [String(value=v).get() for v in getListFromValues(valuesStr, length)]


class Environ(dict):
    """ Some utilities to handle environment settings. """
    REPLACE = 0
    BEGIN = 1
    END = 2

    def getFirst(self, keys, mandatory=False):
        """ Return the value of the first key present in the environment.
        If none is found, returns the 'defaultValue' parameter.
        """
        for k in keys:
            if k in self:
                return self.get(k)

        if mandatory:
            logger.info("None of the variables: %s found in the Environment. "
                  "Please check scipion.conf files." % (str(keys)))

        return None

    def set(self, varName, varValue, position=REPLACE):
        """ Modify the value for some variable.

        :param varName: for example LD_LIBRARY_PATH
        :param varValue: the value to set, prefix or suffix.
        :param position: controls how the value will be changed.
            If REPLACE, it will overwrite the value of
            the var. BEGIN or END will preserve the current value
            and will add, at the beginning or end, the new value.

        """
        if varName in self and position != self.REPLACE:
            if position == self.BEGIN:
                self[varName] = varValue + os.pathsep + self[varName]
            elif position == self.END:
                self[varName] = self[varName] + os.pathsep + varValue
        else:
            self[varName] = varValue

    def update(self, valuesDict, position=REPLACE):
        """ Use set for each key, value pair in valuesDict. """
        for k, v in valuesDict.items():
            self.set(k, v, position)

    def addLibrary(self, libraryPath, position=BEGIN):
        """ Adds a path to LD_LIBRARY_PATH at the requested position
        if the provided paths exist. """

        if libraryPath is None:
            return

        if existsVariablePaths(libraryPath):
            self.update({'LD_LIBRARY_PATH': libraryPath}, position=position)
        else:
            logger.info("Some paths do not exist in: % s" % libraryPath)

    def setPrepend(self, prepend):
        """ Use this method to set a prepend string that will be added at
        the beginning of any command that will be run in this environment.
        This can be useful for example when 'modules' need to be loaded and
        a simple environment variables setup is not enough.
        """
        setattr(self, '__prepend', prepend)

    def getPrepend(self):
        """ Return if there is any prepend value. See setPrepend function. """
        return getattr(self, '__prepend', '')


def existsVariablePaths(variableValue):
    """ Check if the path (or paths) in variableValue exists.
    Multiple paths are allowed if separated by os."""
    return all(os.path.exists(p)
               for p in variableValue.split(os.pathsep) if p.split())


def environAdd(varName, newValue, valueFirst=False):
    """ Add a new value to some environ variable.
    If valueFirst is true, the new value will be at the beginning.
    """
    varList = [os.environ[varName]]
    i = 1
    if valueFirst:
        i = 0
    varList.insert(i, newValue)
    os.environ[varName] = os.pathsep.join(varList)


def envVarOn(varName, env=None):
    """ Is variable set to True in the environment? """
    v = env.get(varName) if env else os.environ.get(varName)
    return strToBoolean(v)

def strToBoolean(string):
    """ Converts a string into a Boolean if the string is on of true, yes, on, 1. Case insensitive."""
    return string is not None and string.lower() in TRUE_YES_ON_

def strToDuration(durationStr):
    """ Converts a string representing an elapsed time to seconds
    E.g.: for "1m 10s" it'll return  70 """

    toEval = durationStr.replace("d", "*3600*24")\
        .replace("h", "*3600")\
        .replace("m", "*60") \
        .replace("s", "") \
        .replace(" ", "+")
    return eval(toEval)

def getMemoryAvailable():
    """ Return the total memory of the system in MB """
    from psutil import virtual_memory
    return virtual_memory().total // 1024 ** 2


def getFreePort(basePort=0, host=''):
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, basePort))
        ipaddr, port = s.getsockname()
        s.close()
    except Exception as e:
        logger.error("Can't get a free port", exc_info=e)
        return 0
    return port


def readProperties(propsFile):
    myprops = {}
    with open(propsFile, 'r') as f:
        for line in f:
            line = line.rstrip()  # removes trailing whitespace and '\n' chars

            if "=" not in line:
                continue  # skips blanks and comments w/o =
            if line.startswith("#"):
                continue  # skips comments which contain =

            k, v = line.split("=", 1)
            myprops[k] = v
    return myprops


# ---------------------Color utils --------------------------
def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))


def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def lighter(color, percent):
    """assumes color is rgb between (0, 0, 0) and (255, 255, 255)"""
    color = np.array(color)
    white = np.array([255, 255, 255])
    vector = white - color
    return tuple(np.around(color + vector * percent))


def formatExceptionInfo(level=6):
    error_type, error_value, trbk = sys.exc_info()
    tb_list = traceback.format_tb(trbk, level)
    s = "Error: %s \nDescription: %s \nTraceback:" % (error_type.__name__,
                                                      error_value)
    for i in tb_list:
        s += "\n" + i
    return s


def printTraceBack():
    traceback.print_stack()


def getEnvVariable(variableName, default=None, exceptionMsg=None):
    """ Returns the value of an environment variable or raise an exception message.
    Useful when adding variable to the config file and report accurate messages"""
    value = os.getenv(variableName)

    if exceptionMsg is None:
        exceptionMsg = ("Environment variable %s not found. "
                        "Please check scipion configuration. "
                        "Try running : scipion config." % variableName)

    if value is None:
        if default is None:
            raise Exception(exceptionMsg)
        else:
            return default
    else:
        return value


@contextlib.contextmanager
def weakImport(package, msg=None):
    """
    This method can be used to tolerate imports that may fail.

    e.g::

        from .protocol_ctffind import CistemProtCTFFind
        with weakImport('tomo'):
            from .protocol_ts_ctffind import CistemProtTsCtffind

    In this case CistemProtTsCtffind should fail if tomo package is missing,
    but exception is captured and all the imports above should be available

    :param package: name of the package that is expected to fail

    """
    try:
        yield
    except ImportError as e:
        if "'%s'" % package not in str(e):
            raise e
        elif msg is not None:
            logger.warning(msg)
# To be removed once developers have installed distro. 20-Nov-2023.
with weakImport("distro", msg='You are missing distro package. '
            'Did you "git pulled"?. Please run "scipion3 pip install distro==1.8".'):
    import distro

class OS:
    @staticmethod
    def getPlatform():
        return platform.system()

    @classmethod
    def getDistro(cls):
        return distro

    @classmethod
    def isWSL(cls):

        # For now lets assume that if WSL_DISTRO_NAME exists is a WLS
        return cls.getWLSNAME() is not None

    @classmethod
    def getWLSNAME(cls):
        return os.environ.get("WSL_DISTRO_NAME", None)

    @classmethod
    def isUbuntu(cls):
        return distro.id() == "ubuntu"

    @classmethod
    def isCentos(cls):
        return distro.id() == "centos"

    @classmethod
    def WLSfile2Windows(cls, file):
        # Links in WSL are not valid in windows
        file = os.path.realpath(file).replace("/", "\\")
        file = ("\\\\wsl.localhost\\" + cls.getWLSNAME() + file)
        return file


def valueToList(value):
    """ Returns a list containing value, unless value is already a list. If value is None returns an empty list"""
    if value is None:
        return []
    elif isinstance(value, list):
        return value
    else:
        return [value]