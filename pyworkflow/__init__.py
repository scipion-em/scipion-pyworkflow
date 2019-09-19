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
from __future__ import print_function
from __future__ import absolute_import

import ast
import os
import sys
import importlib
import types


# This variable is useful to determinate the plugins compatibility with the
# current Scipion core release.
# This version does not need to change with future scipion releases
# if plugins are still compatible, so future hot fixes releases or even micros
# or minor release should not change this CORE_VERSION. Only, when a new release
# will break existing plugins, this number needs to be incremented.
CORE_VERSION = '2.0'

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

PYTHON = os.environ.get("SCIPION_PYTHON", 'python')


class Config:
    __get = os.environ.get  # shortcut
    SCIPION_HOME = __get('SCIPION_HOME', '')
    SCIPION_USER_DATA = __get('SCIPION_USER_DATA',
                              os.path.expanduser('~/ScipionUserData'))
    SCIPION_SUPPORT_EMAIL = __get('SCIPION_SUPPORT_EMAIL',
                                  'scipion@cnb.csic.es')
    SCIPION_LOGO = __get('SCIPION_LOGO',
                         'scipion_logo.png')
    # Where is the input data for tests...also where it will be downloaded
    SCIPION_TESTS = __get('SCIPION_TESTS',
                          os.path.join(SCIPION_HOME, 'data', 'tests'))

    SCIPION_EM_ROOT = __get('SCIPION_EM_ROOT',
                            os.path.join(SCIPION_HOME, 'software', 'em'))

    # Where the output of the tests will be stored
    SCIPION_TESTS_OUTPUT = __get('SCIPION_TESTS_OUTPUT',
                                 os.path.join(SCIPION_USER_DATA, 'Tests'))

    SCIPION_CONFIG = __get('SCIPION_CONFIG', 'scipion.conf')
    SCIPION_LOCAL_CONFIG = __get('SCIPION_LOCAL_CONFIG', 'scipion.conf')
    SCIPION_HOSTS = __get('SCIPION_HOSTS', 'hosts.conf')
    SCIPION_PROTOCOLS = __get('SCIPION_PROTOCOLS', 'protocols.conf')

    SCIPION_PLUGIN_JSON = __get('SCIPION_PLUGIN_JSON', None)
    SCIPION_PLUGIN_REPO_URL = __get('SCIPION_PLUGIN_REPO_URL',
                                    'http://scipion.i2pc.es/getplugins/')

    # Get general log file path
    LOG_FILE = os.path.join(__get('SCIPION_LOGS', SCIPION_USER_DATA),
                            'scipion.log')

    SCIPION_URL_SOFTWARE = __get('SCIPION_URL_SOFTWARE')

    try:
        VIEWERS = ast.literal_eval(__get('VIEWERS', "{}"))
    except Exception as e:
        VIEWERS = {}
        print("ERROR loading preferred viewers, VIEWERS variable will be ignored")
        print(e)

    SCIPION_DOMAIN = __get('SCIPION_DOMAIN', None)

    @classmethod
    def getDomain(cls):
        """ Import domain module from path or name defined in SCIPION_DOMAIN. """
        value = cls.SCIPION_DOMAIN

        print('SCIPION_DOMAIN=%s' % value)
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
        os.environ['SCIPION_DOMAIN'] = value


def join(*paths):
    """ join paths from HOME . """
    return os.path.join(HOME, *paths)


__resourcesPath = [join('resources')]


def findResource(filename):
    from .utils.path import findFile

    return findFile(filename, *__resourcesPath)


# Following are a set of functions to centralize the way to get
# files from several scipion folder such as: config or apps

def getScipionPath(*paths):
     return os.path.join(Config.SCIPION_HOME, *paths)


def getScipionScript():
    return getScipionPath('scipion')


def getConfigPath(*paths):
    return getScipionPath('config', *paths)


def getTemplatePath(*paths):
    return join('templates', *paths)
