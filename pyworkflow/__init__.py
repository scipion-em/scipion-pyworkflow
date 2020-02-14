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
# This variable is useful to determinate the plugins compatibility with the
# current Scipion core release.
# This version does not need to change with future scipion releases
# if plugins are still compatible, so future hot fixes releases or even micros
# or minor release should not change this CORE_VERSION. Only, when a new release
# will break existing plugins, this number needs to be incremented.
CORE_VERSION = '3.0.0'

# Versions
VERSION_1 = '1.0.0'
VERSION_1_1 = '1.1.0'
VERSION_1_2 = '1.2.0'
VERSION_2_0 = '2.0.0'
VERSION_3_0 = '3.0.0'

# For a new release, define a new constant and assign it to LAST_VERSION
# The existing one has to be added to OLD_VERSIONS list.
LAST_VERSION = VERSION_3_0
OLD_VERSIONS = (VERSION_1, VERSION_1_1, VERSION_1_2, VERSION_2_0)

# Define pyworkflow version in a standard way, as proposed by:
# https://www.python.org/dev/peps/pep-0396/
__version__ = LAST_VERSION + 'a1'

HOME = os.path.abspath(os.path.dirname(__file__))
PYTHON = os.environ.get("SCIPION_PYTHON", 'python3')

# Variable constants, probably we can have a constants module
SCIPION_TESTS_CMD = 'SCIPION_TESTS_CMD'
NOTES_HEADING_MSG = \
     '############################################  SCIPION NOTES  ##############################################' + \
     '\n\nThis document can be used to store your notes within your project from Scipion framework.\n\n' + \
     'Scipion notes behaviour can be managed in the Scipion config file by creating or editing, if they\n' + \
     'already exist, the following variables:\n\n' + \
     '\t-SCIPION_NOTES_FILE is used to store the file name (default is {})\n' + \
     '\t-SCIPION_NOTES_PROGRAM is used to select the program which will be used to open the notes file. If \n' + \
     '\t empty, it will use the default program used by your OS to open that type of file.\n' + \
     '\t-SCIPION_NOTES_ARGS is used to add input arguments that will be used in the calling of the program\n' + \
     '\t specified in SCIPION_NOTES_PROGRAM.\n\n' + \
     'These lines can be removed if desired.\n\n' + \
     '###########################################################################################################' + \
     '\n\nPROJECT NOTES:'

# Following are a set of functions to centralize the way to get
# files from several scipion folder such as: config or apps
def getPWPath(*paths):
    return os.path.join(os.path.dirname(__file__), *paths)


def getAppsPath():
    return os.path.join(getPWPath(), 'apps')


def getSyncDataScript():
    return os.path.join(getAppsPath(), 'pw_sync_data.py')


def getScheduleScript():
    return os.path.join(getAppsPath(), 'pw_schedule_run.py')


def getPwProtMpiRunScript():
    return os.path.join(getAppsPath(), 'pw_protocol_mpirun.py')


def getTestsScript():
    return os.path.join(getAppsPath(), 'pw_run_tests.py')


def getViewerScript():
    return os.path.join(getAppsPath(), 'pw_viewer.py')


def join(*paths):
    """ join paths from HOME . """
    return os.path.join(HOME, *paths)


__resourcesPath = [join('resources')]


def findResource(filename):
    from .utils.path import findFile

    return findFile(filename, *__resourcesPath)

def genNotesHeading():
    return NOTES_HEADING_MSG.format(Config.SCIPION_NOTES_FILE)


from .config import Config
