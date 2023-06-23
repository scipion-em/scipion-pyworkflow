# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
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


from pyworkflow.protocol import (STATUS_SAVED, STATUS_LAUNCHED, STATUS_RUNNING,
                                 STATUS_FINISHED, STATUS_FAILED,
                                 STATUS_INTERACTIVE, STATUS_ABORTED,
                                 STATUS_SCHEDULED)

from pyworkflow.utils.properties import Message, Icon, KEYSYM

STATUS_COLORS = {
               STATUS_SAVED: '#D9F1FA',
               STATUS_LAUNCHED: '#D9F1FA',
               STATUS_RUNNING: '#FCCE62',
               STATUS_FINISHED: '#D2F5CB',
               STATUS_FAILED: '#F5CCCB',
               STATUS_INTERACTIVE: '#F3F5CB',
               STATUS_ABORTED: '#F5CCCB',
               STATUS_SCHEDULED: '#F3F5CB'
               }

# For protocols with warnings
WARNING_COLOR = '#848484'


ACTION_EDIT = Message.LABEL_EDIT
ACTION_RENAME = Message.LABEL_RENAME
ACTION_SELECT_FROM = Message.LABEL_SELECT_FROM
ACTION_SELECT_TO = Message.LABEL_SELECT_TO
ACTION_COPY = Message.LABEL_COPY
ACTION_PASTE = Message.LABEL_PASTE
ACTION_DUPLICATE = Message.LABEL_DUPLICATE
ACTION_DELETE = Message.LABEL_DELETE
ACTION_REFRESH = Message.LABEL_REFRESH
ACTION_STEPS = Message.LABEL_STEPS
ACTION_BROWSE = Message.LABEL_BROWSE
ACTION_DB = Message.LABEL_DB
ACTION_TREE = Message.LABEL_TREE
ACTION_STOP = Message.LABEL_STOP
ACTION_DEFAULT = Message.LABEL_DEFAULT
ACTION_CONTINUE = Message.LABEL_CONTINUE
ACTION_RESULTS = Message.LABEL_ANALYZE
ACTION_EXPORT = Message.LABEL_EXPORT
ACTION_EXPORT_UPLOAD = Message.LABEL_EXPORT_UPLOAD
ACTION_SWITCH_VIEW = 'Switch_View'
ACTION_COLLAPSE = 'Collapse'
ACTION_EXPAND = 'Expand'
ACTION_LABELS = 'Labels'
ACTION_RESTART_WORKFLOW = Message.LABEL_RESTART_WORKFLOW
ACTION_CONTINUE_WORKFLOW = Message.LABEL_CONTINUE_WORKFLOW
ACTION_STOP_WORKFLOW = Message.LABEL_STOP_WORKFLOW
ACTION_RESET_WORKFLOW = Message.LABEL_RESET_WORKFLOW
ACTION_SEARCH = 'Search'

ActionIcons = {
    ACTION_EDIT: Icon.ACTION_EDIT,
    ACTION_SELECT_FROM: Icon.ACTION_SELECT_FROM,
    ACTION_SELECT_TO: Icon.ACTION_SELECT_TO,
    ACTION_DUPLICATE: Icon.ACTION_DUPLICATE,
    ACTION_COPY: Icon.ACTION_COPY,
    ACTION_PASTE:Icon.ACTION_PASTE,
    ACTION_DELETE: Icon.ACTION_DELETE,
    ACTION_REFRESH: Icon.ACTION_REFRESH,
    ACTION_RENAME: Icon.ACTION_RENAME,
    ACTION_STEPS: Icon.CODE_BRANCH,
    ACTION_BROWSE: Icon.ACTION_BROWSE,
    ACTION_DB: Icon.ACTION_DB,
    ACTION_TREE: None,  # should be set
    ACTION_STOP: Icon.ACTION_STOP,
    ACTION_CONTINUE: Icon.ACTION_CONTINUE,
    ACTION_RESULTS: Icon.ACTION_RESULTS,
    ACTION_EXPORT: Icon.ACTION_EXPORT,
    ACTION_EXPORT_UPLOAD: Icon.ACTION_EXPORT_UPLOAD,
    ACTION_COLLAPSE: Icon.ACTION_COLLAPSE,
    ACTION_EXPAND: Icon.ACTION_EXPAND,
    ACTION_LABELS: Icon.TAGS,
    ACTION_RESTART_WORKFLOW: Icon.BACKWARD,
    ACTION_CONTINUE_WORKFLOW: Icon.ACTION_CONTINUE,
    ACTION_STOP_WORKFLOW: Icon.ACTION_STOP_WORKFLOW,
    ACTION_RESET_WORKFLOW: Icon.BROOM,
    ACTION_SEARCH: Icon.ACTION_SEARCH,
}

# TODO: Centralize this and the 2 above collections
ActionShortCuts = {
    # F keys
    ACTION_RENAME: "<F2>",
    ACTION_REFRESH: "<F5>",
    # Letter keys, uppercase first, sorted
    ACTION_COLLAPSE: "-",
    ACTION_EXPAND: "+",
    ACTION_RESULTS: "a",
    ACTION_BROWSE: "b",
    ACTION_CONTINUE_WORKFLOW:"c",
    ACTION_DB: "d",
    ACTION_EDIT: "e",
    ACTION_SELECT_FROM: "f",
    ACTION_LABELS: "l",
    ACTION_TREE: "o",
    ACTION_RESTART_WORKFLOW: "R",
    ACTION_RESET_WORKFLOW:"r",
    ACTION_STEPS: "S",
    ACTION_STOP: "s",
    ACTION_SELECT_TO: "t",
    # Control +, sorted
    ACTION_COPY: "<Control-c>",
    ACTION_DUPLICATE: "<Control-d>",
    ACTION_PASTE: "<Control-v>",
    ACTION_STOP_WORKFLOW: "<Control-s>",
    ACTION_DELETE: "<Delete>",


}
