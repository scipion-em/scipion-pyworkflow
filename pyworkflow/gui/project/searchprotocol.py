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
""" This modules hosts code provider and window to search for a protocol"""
import tkinter as tk

from pyworkflow import Config
import  pyworkflow.gui as pwgui
import pyworkflow.object as pwobj
from pyworkflow.gui.dialog import SearchBaseWindow

from pyworkflow.gui.project.utils import isAFinalProtocol
from pyworkflow.gui.project.viewprotocols_extra import ProtocolTreeConfig

UPDATED = "updated"

NEW = "new"

BETA = "beta"


class ProtocolTreeProvider(pwgui.tree.ObjectTreeProvider):
    """Create the tree elements for a Protocol run"""

    def __init__(self, protocol):
        self.protocol = protocol
        # This list is create to group the protocol parameters
        # in the tree display
        self.status = pwobj.List(objName='_status')
        self.params = pwobj.List(objName='_params')
        self.statusList = ['status', 'initTime', 'endTime', 'error',
                           'interactive', 'mode']

        objList = [] if protocol is None else [protocol]
        pwgui.tree.ObjectTreeProvider.__init__(self, objList)



class SearchProtocolWindow(SearchBaseWindow):

    columnConfig = {
        '#0': ('Status', {'width': 50, 'minwidth': 50, 'stretch': tk.NO}, 5),
        # Heading, tree column kwargs, casting for sorting
        'protocol': ('Protocol', {'width': 300, 'stretch': tk.FALSE}, 10),
        'streaming': ('Streamified', {'width': 100, 'stretch': tk.FALSE}, 5),
        'installed': ('Installation', {'width': 110, 'stretch': tk.FALSE}, 5),
        'help': ('Help', {'minwidth': 300, 'stretch': tk.YES}, 5),
        'score': ('Score', {'width': 50, 'stretch': tk.FALSE}, 5, int)
    }

    def __init__(self, parentWindow, **kwargs):

        super().__init__(parentWindow,
                         title="Add a protocol",
                         **kwargs)

    def _createResultsTree(self, frame, show, columns):
        return self.master.getViewWidget()._createProtocolsTree(frame, show=show, columns=columns)

    def _onSearchClick(self, e=None):

        self._resultsTree.clear()

        protList = self.scoreProtocols()

        # Sort by weight
        protList.sort(reverse=True, key=lambda x: x[8])

        self._addProtocolToTree(protList)

    def scoreProtocols(self):

        keyword = self._searchVar.get().lower().strip()
        emProtocolsDict = Config.getDomain().getProtocols()
        protList = []

        for key, prot in emProtocolsDict.items():
            if isAFinalProtocol(prot, key):
                label = prot.getClassLabel().lower()
                line = (key, label,
                        "installed" if prot.isInstalled() else "missing installation",
                        prot.getHelpText().strip().replace('\r', '').replace('\n', '').lower(),
                        "streamified" if prot.worksInStreaming() else "static",
                        BETA if prot.isBeta() else "",
                        NEW if prot.isNewDev() else "",
                        UPDATED if prot.isUpdated() else "")

                line = self._addSearchWeight(line, keyword)
                # something was found: weight > 0
                if line[8] != 0:
                    protList.append(line)

        return protList

    @staticmethod
    def _addSearchWeight(line2Search, searchtext):
        # Adds a weight value for the search
        weight = 0

        # prioritize findings in label
        if searchtext in line2Search[1]:
            weight += 10

        for value in line2Search[2:]:
            weight += 5 if searchtext in value else 0

        if " " in searchtext:
            for word in searchtext.split():
                if word in line2Search[1]:
                    weight += 3

                for value in line2Search[2:]:
                    weight += 1 if word in value else 0

        return line2Search + (weight,)

    def _addProtocolToTree(self, protList):
        """ Adds the items in protList to the tree

        :param protList: List of tuples with all the values/colunms used in search ans shown in the tree"""

        for key, label, installed, help, streamified, beta, new, updated, weight in protList:
            tag = ProtocolTreeConfig.getProtocolTag(installed == 'installed',
                                                    beta == BETA,
                                                    new == NEW,
                                                    updated == UPDATED)

            self._resultsTree.insert(
                '', 'end', key, text="", tags=tag,
                values=(label, streamified, installed, help, weight))


