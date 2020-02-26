# -*- coding: utf-8 -*-
# **************************************************************************
# *
# * Authors:     Scipion team
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
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
SCIPION_HOME = 'SCIPION_HOME'
SCIPION_USER_DATA = 'SCIPION_USER_DATA'
SCIPION_USER_DATA_DEFAULT = '~/ScipionUserData'
SCIPION_SUPPORT_EMAIL = 'SCIPION_SUPPORT_EMAIL'
SCIPION_SUPPORT_EMAIL_DEFAULT = 'scipion@cnb.csic.es'
SCIPION_LOGO = 'SCIPION_LOGO'
SCIPION_LOGO_DEFAULT = 'scipion_logo.gif'
SCIPION_TESTS = 'SCIPION_TESTS'
SCIPION_TESTS_OUTPUT = 'SCIPION_TESTS_OUTPUT'
SCIPION_CONFIG = 'SCIPION_CONFIG'
SCIPION_CONFIG_DEFAULT = 'scipion.conf'
SCIPION_LOCAL_CONFIG = 'SCIPION_LOCAL_CONFIG'
SCIPION_HOSTS = 'SCIPION_HOSTS'
SCIPION_HOSTS_DEFAULT = 'hosts.conf'
SCIPION_PROTOCOLS = 'SCIPION_PROTOCOLS'
SCIPION_PROTOCOLS_DEFAULT = 'protocols.conf'
SCIPION_PLUGIN_JSON = 'SCIPION_PLUGIN_JSON'
SCIPION_PLUGIN_REPO_URL = 'SCIPION_PLUGIN_REPO_URL'
SCIPION_PLUGIN_REPO_URL_DEFAULT = 'http://scipion.i2pc.es/getplugins/'
SCIPION_LOGS = 'SCIPION_LOGS'
SCIPION_LOGS_DEFAULT = 'scipion.log'
SCIPION_URL_SOFTWARE = 'SCIPION_URL_SOFTWARE'
SCIPION_NOTES_FILE = 'SCIPION_NOTES_FILE'
SCIPION_NOTES_FILE_DEFAULT = 'notes.txt'
SCIPION_NOTES_PROGRAM = 'SCIPION_NOTES_PROGRAM'
SCIPION_NOTES_ARGS = 'SCIPION_NOTES_ARGS'
SCIPION_NOTES_HEADING_MSG = \
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
SCIPION_DOMAIN = 'SCIPION_DOMAIN'
SCIPION_DEBUG = 'SCIPION_DEBUG'
SCIPION_JSON_TEMPLATES = '.json.template'

# Color and appearance contants
TK_GRAY_DEFAULT = '#d9d9d9'

# Other
PW_ALT_TESTS_CMD = 'PW_ALT_TESTS_CMD'
VIEWERS = 'VIEWERS'