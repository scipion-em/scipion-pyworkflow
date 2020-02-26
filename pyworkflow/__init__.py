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
import os
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

def getPyworkflowPath():
    """ Returns the path where pyworkflow is"""
    return dirname(__file__)

def getModuleFolder(moduleName):
    """ Returns the path of a module without importing it"""

    spec = importlib.util.find_spec(moduleName)
    return dirname(spec.origin)

def join(*paths):
    """ join paths from HOME . """
    return os.path.join(HOME, *paths)

__resourcesPath = [join('resources')]

def findResource(filename):
    from .utils.path import findFile

    return findFile(filename, *__resourcesPath)

def genNotesHeading():
    return SCIPION_NOTES_HEADING_MSG

from .config import Config
