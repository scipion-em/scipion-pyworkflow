# -*- coding: utf-8 -*-
# **************************************************************************
# *
# * Authors:     Scipion team
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
"""
This modules contains constants related to Pyworkflow
"""
from enum import Enum

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
VERSION_3_0 = '3.1.0'

# For a new release, define a new constant and assign it to LAST_VERSION
# The existing one has to be added to OLD_VERSIONS list.
LAST_VERSION = VERSION_3_0
OLD_VERSIONS = (VERSION_1, VERSION_1_1, VERSION_1_2, VERSION_2_0)

# STATUS
PROD = 0
BETA = 1
NEW = 2
UPDATED = 3

# Dir names
APPS = 'apps'
DATA_TAG = 'data'

# Scripts
PW_SYNC_DATA = 'pw_sync_data.py'
PW_SCHEDULE_RUN = 'pw_schedule_run.py'
PW_PROTOCOL_MPIRUN = 'pw_protocol_mpirun.py'
PW_RUN_TESTS = 'pw_run_tests.py'
PW_VIEWER = 'pw_viewer.py'

# PW Config
SCIPION_PYTHON = 'SCIPION_PYTHON'
SCIPION_PYTHON_DEFAULT = 'python3'
SCIPION_HOME_VAR = 'SCIPION_HOME'
SCIPION_TESTS = 'SCIPION_TESTS'
SCIPION_SCRATCH = 'SCIPION_SCRATCH'

# FONT
SCIPION_DEFAULT_FONT_SIZE = 10

# NOTES CONSTANTS
SCIPION_NOTES_FILE = 'SCIPION_NOTES_FILE'
SCIPION_NOTES_FILE_DEFAULT = 'notes.txt'
SCIPION_NOTES_PROGRAM = 'SCIPION_NOTES_PROGRAM'
SCIPION_NOTES_ARGS = 'SCIPION_NOTES_ARGS'
SCIPION_NOTES_HEADING_MSG = \
    '############################################  SCIPION NOTES  ##############################################' \
    '\n\nThis document can be used to store your notes within your project from Scipion framework.\n\n' \
    'Scipion notes behaviour can be managed in the Scipion config file by creating or editing, if they\n' \
    'already exist, the following variables:\n\n' \
    '\t-%s is used to store the file name (default is %s)\n' \
    '\t-%s is used to select the program which will be used to open the notes file. If \n' \
    '\t empty, it will use the default program used by your OS to open that type of file.\n' \
    '\t-%s is used to add input arguments that will be used in the calling of the program\n' \
    '\t specified in %s.\n\n' \
    'These lines can be removed if desired.\n\n' \
    '###########################################################################################################' \
    '\n\nPROJECT NOTES:' % (SCIPION_NOTES_FILE, SCIPION_NOTES_FILE_DEFAULT,
                            SCIPION_NOTES_PROGRAM, SCIPION_NOTES_ARGS,
                            SCIPION_NOTES_PROGRAM)

SCIPION_DOMAIN = 'SCIPION_DOMAIN'

# Debug constants
SCIPION_DEBUG = 'SCIPION_DEBUG'
SCIPION_JSON_TEMPLATES = '.json.template'
SCIPION_DEBUG_NOCLEAN = 'SCIPION_DEBUG_NOCLEAN'
SCIPION_DEBUG_SQLITE = 'SCIPION_DEBUG_SQLITE'
SCIPION_LOG_LEVEL = 'SCIPION_LOG_LEVEL'

# Color and appearance constants
TK_GRAY_DEFAULT = '#d9d9d9'

# Other
SCIPION_TESTS_CMD = 'SCIPION_TESTS_CMD'
CONDA_ACTIVATION_CMD_VAR = 'CONDA_ACTIVATION_CMD'
VIEWERS = 'VIEWERS'

# Results when updating a protocol
NOT_UPDATED_READ_ONLY = 0
NOT_UPDATED_UNNECESSARY = 1
NOT_UPDATED_ERROR = 2
PROTOCOL_UPDATED = 3

# Db names
PROJECT_DBNAME = 'project.sqlite'
PROJECT_SETTINGS = 'settings.sqlite'

# GUI colors
class Color:
    RED_COLOR = 'Firebrick'  # REMOVE when not used. Red color for background label  = #B22222

    # Color agnostic constants
    MAIN_COLOR = RED_COLOR
    ALT_COLOR = '#EAEBEC'  # Light grey for background color in form, protocol, table header and west container
    ALT_COLOR_2 = '#F2F2F2'  # Very light grey for odd rows, input background, etc
    ALT_COLOR_DARK= '#6E6E6E'  # Very dark grey for project title, tubes, etc
    BG_COLOR = 'white'

    STATUS_SAVED = '#D9F1FA',
    STATUS_LAUNCHED = '#D9F1FA',
    STATUS_RUNNING = '#FCCE62',
    STATUS_FINISHED = '#D2F5CB',
    STATUS_FAILED = '#F5CCCB',
    STATUS_INTERACTIVE = '#F3F5CB',
    STATUS_ABORTED = '#F5CCCB',



# Terminal ASCII colors and tkinter map
# Enum with ascii code colors based on -->https://stackoverflow.com/questions/4842424/list-of-ansi-color-escape-sequences
class StrColors(Enum):
    gray = '30'
    red = '31'
    green = '32'
    yellow = '33'
    blue = '34'
    magenta = '35'
    cyan = '36'
    white = '37'
    lightgreen = '92'

# Console (and XMIPP) escaped colors, and the related tags that we create
# with Text.tag_config(). This dict is used in OutputText:addLine()
ASCII_COLOR_2_TKINTER =\
    {StrColors.gray.value: 'gray',
     StrColors.red.value: 'red',
     StrColors.green.value: 'yellowgreen',
     StrColors.lightgreen.value: 'yellowgreen',
     StrColors.yellow.value: 'yellow',
     StrColors.blue.value: 'blue',
     StrColors.magenta.value: 'magenta',
     StrColors.cyan.value: 'cyan',
     StrColors.white.value: 'white'}

class DOCSITEURLS:
    """Documentation site URL useful when exceptions happens and you want to point to some pages"""
    HOME = 'https://scipion-em.github.io/docs/release-3.0.0/'
    DOCS = HOME + 'docs/'
    CONFIG = DOCS + 'scipion-modes/scipion-configuration.html'
    CONFIG_SECTION = CONFIG + '#%s'
    CONTACTUS = 'http://scipion.i2pc.es/contact'
    USER = DOCS + 'user/'
    GUI = USER + 'scipion-gui.html'
    WAIT_FOR = GUI + '#waiting-for-other-protocols'
    PLUGIN_MANAGER = USER + 'plugin-manager.html'
    HOST_CONFIG = DOCS + "scipion-modes/host-configuration.html"


# tkinter bind constants
class TK:
    LEFT_CLICK = '<Button-1>'
    RETURN = '<Return>'
    ENTER = '<KP_Enter>'
    LEFT_DOUBLE_CLICK = '<Double-1>'
    TREEVIEW_OPEN = '<<TreeviewOpen>>'
    TREEVIEW_CLOSE = '<<TreeviewClose>>'
