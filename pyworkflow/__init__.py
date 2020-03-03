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

from .constants import *
from .config import *

# Define pyworkflow version in a standard way, as proposed by:
# https://www.python.org/dev/peps/pep-0396/
__version__ = LAST_VERSION + 'a1'

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

