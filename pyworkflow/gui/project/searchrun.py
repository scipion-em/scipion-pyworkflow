# -*- coding: utf-8 -*-
# **************************************************************************
# *
# * Authors:     Pablo Conesa [1]
# *
# * [1] Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
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
""" This modules hosts code provider and window to search for a run"""

import tkinter as tk
from pyworkflow import Config
import pyworkflow.protocol as pwprot

from pyworkflow.gui import SearchBaseWindow
from pyworkflow.gui.project.constants import *
from pyworkflow.gui.tree import ProjectRunsTreeProvider

class RunsTreeProvider(ProjectRunsTreeProvider):
    """Provide runs info to populate tree inside viewprotocols. Is more advanced
    than ProjectRunsTreeProvider extended, extended with right click actions."""

    def __init__(self, project, actionFunc):
        super().__init__(project)
        self.actionFunc = actionFunc
        self._selection = project.getSettings().runSelection

    def getActionsFromSelection(self):
        """ Return the list of options available for selection. """
        n = len(self._selection)
        single = n == 1
        if n:
            prot = self.project.getProtocol(self._selection[0])
            status = prot.getStatus()
            nodeInfo = self.project.getSettings().getNodeById(prot.getObjId())
            expanded = nodeInfo.isExpanded() if nodeInfo else True
        else:
            status = None

        stoppable = status in [pwprot.STATUS_RUNNING, pwprot.STATUS_SCHEDULED,
                               pwprot.STATUS_LAUNCHED]

        return [(ACTION_EDIT, single and status and expanded),
                (ACTION_RENAME, single and status and expanded),
                (ACTION_DUPLICATE, status and expanded),
                (ACTION_COPY, status and expanded),
                (ACTION_PASTE, status and expanded),
                (ACTION_DELETE, status != pwprot.STATUS_RUNNING and status and expanded),
                (ACTION_STEPS, single and Config.debugOn() and status and expanded),
                (ACTION_BROWSE, single and status and expanded),
                (ACTION_DB, single and Config.debugOn() and status and expanded),
                (ACTION_STOP, stoppable and single),
                (ACTION_EXPORT, not single),
                (ACTION_EXPORT_UPLOAD, not single),
                (ACTION_COLLAPSE, single and status and expanded),
                (ACTION_EXPAND, single and status and not expanded),
                (ACTION_LABELS, True),
                (ACTION_SELECT_FROM, True),
                (ACTION_SELECT_TO, True),
                (ACTION_RESTART_WORKFLOW, single),
                (ACTION_CONTINUE_WORKFLOW, single),
                (ACTION_STOP_WORKFLOW, single),
                (ACTION_RESET_WORKFLOW, single)
                ]

    def getObjectActions(self, obj):

        def addAction(actionLabel):
            if actionLabel:
                text = actionLabel
                action = actionLabel
                actionLabel = (text, lambda: self.actionFunc(action),
                               ActionIcons.get(action, None),
                               ActionShortCuts.get(action,None))
            return actionLabel

        actions = [addAction(a)
                   for a, cond in self.getActionsFromSelection() if cond]

        if hasattr(obj, 'getActions'):
            for text, action in obj.getActions():
                actions.append((text, action, None))

        return actions


class SearchRunWindow(SearchBaseWindow):

    columnConfig = {
        '#0': (ProjectRunsTreeProvider.ID_COLUMN, {'width': 100, 'stretch': tk.NO}, 10),
        ProjectRunsTreeProvider.RUN_COLUMN: (ProjectRunsTreeProvider.RUN_COLUMN, {'width': 300, 'stretch': tk.TRUE}, 10),
        ProjectRunsTreeProvider.STATE_COLUMN: (ProjectRunsTreeProvider.STATE_COLUMN, {'width': 150, 'stretch': tk.FALSE}, 5),
        ProjectRunsTreeProvider.TIME_COLUMN: (ProjectRunsTreeProvider.TIME_COLUMN, {'width': 200, 'stretch': tk.FALSE}, 5),
        'Comment': ('Comment', {'width': 300, 'stretch': tk.FALSE}, 5),
        'Expanded': ('Expanded', {'width': 150, 'stretch': tk.FALSE}, 5),
    }

    def __init__(self, parentWindow, runsGraph, **kwargs):


        super().__init__(parentWindow,
                         title="Locate a protocol in the graph",
                         **kwargs)
        self.runsGraph = runsGraph

    def _onSearchClick(self, e=None):

        self._resultsTree.clear()
        keyword = self._searchVar.get().lower().strip()

        weightIndex = len(self.columnConfig)
        nodes = self.runsGraph.getNodes()
        protList = []

        for node in nodes:
            if node.run is not None:
                run = node.run
                key = run.getObjId()
                label = run.getRunName()
                status = run.getStatusMessage(),
                time = run.getObjCreation()
                comment = run.getObjComment()
                expanded = "expanded" if getattr(node, 'expanded', False) else "collapsed"
                line = (key, label, status, time, comment, expanded)

                line = self.addSearchWeight(line, keyword)
                # something was found: weight > 0
                if line[weightIndex] != 0:
                    # Add the run
                    protList.append(line)

        # Sort by weight
        protList.sort(reverse=True, key=lambda x: x[weightIndex])

        for line in protList:

            self._resultsTree.insert(
                '', 'end', line[0], text=line[0],
                values=line[1:])



