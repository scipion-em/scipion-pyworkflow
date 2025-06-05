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
""" This module contains the provider and dialog to search for a protocol"""
import tkinter as tk
from pyworkflow import Config
import pyworkflow.gui as pwgui
import pyworkflow.object as pwobj
from pyworkflow.gui.dialog import SearchBaseWindow

from pyworkflow.gui.project.utils import isAFinalProtocol
from pyworkflow.gui.project.viewprotocols_extra import ProtocolTreeConfig
from pyworkflow.project.usage import getNextProtocolSuggestions
from pyworkflow.utils import Icon

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
        'score': ('Score/Freq.', {'width': 50, 'stretch': tk.FALSE}, 5, int),
        'streaming': ('Streamified', {'width': 100, 'stretch': tk.FALSE}, 5),
        'installed': ('Installation', {'width': 110, 'stretch': tk.FALSE}, 5),
        'help': ('Help', {'minwidth': 300, 'stretch': tk.YES}, 5),
    }

    def __init__(self, parentWindow, position=None, selectionGetter=None):

        posStr = "" if position is None else " at (%s,%s)" % position
        self.position = position
        self.selectionGetter = selectionGetter
        self.selectedProtocol = None
        self._infoLbl = None  # Label to show information
        super().__init__(parentWindow,
                         title="Add a protocol" + posStr)

        self.root.bind("<FocusIn>", self._onWindowFocusIn)

    def _onWindowFocusIn(self, event):
        """
        To refresh the selected protocol in the graph upon window activation.
        :param event: event information
        :return: Nothing
        """
        if event.widget == self.root and self.selectionGetter:
            self.selectedProtocol = self.selectionGetter()
            if self._isSuggestionActive():
                self._onSearchClick()
    def _isSuggestionActive(self):
        """
        :return: Returns true if current mode is suggestion mode.
        """
        return self._searchVar.get().lower().strip() ==""

    def _createSearchBox(self, content):
        frame = super()._createSearchBox(content)

        btn = pwgui.widgets.IconButton(frame, "Suggest",
                                 tooltip="Suggestions for active protocol based on usage.",
                                 imagePath=Icon.LIGHTBULB,
                                 command=self.showSuggestions)
        btn.grid(row=0, column=3, sticky='nw')

        self.lbl = tk.StringVar()
        lbl = tk.Label(frame, text="", bg=Config.SCIPION_BG_COLOR, textvariable=self.lbl, font=self.font)
        lbl.grid(row=0, column=4, sticky='news')

    def _createResultsTree(self, frame, show, columns):
        # This code is where the callback (on double click) is defined.
        return self.master.getViewWidget()._createProtocolsTree(frame, show=show, columns=columns, position=self.position)

    def showSuggestions(self, e=None):
        self._searchVar.set("")
        self._onSearchClick()
    def _onSearchClick(self, e=None):

        self._resultsTree.clear()

        protList = self.scoreProtocols()

        # Sort by weight
        protList.sort(reverse=True, key=lambda x: x[8])

        self._addProtocolToTree(protList)

    def scoreProtocols(self):

        if self._isSuggestionActive():
            return self.addSuggestions()

        keyword = self._searchVar.get().lower().strip()
        self.lbl.set('Showing text search matches for "%s"' % keyword)

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

    def addSuggestions(self):

        if self.selectedProtocol is None:
            self.lbl.set("Showing suggestions for a first protocol")
            protName =str(None)
        else:
            protName = self.selectedProtocol.getClassName()
            self.lbl.set("Usage suggestions for selected protocol: %s" % self.selectedProtocol.getClassLabel())

        protList = []
        suggestions = getNextProtocolSuggestions(protName)
        for suggestion in suggestions:
            #Fields comming from the site:
            # https://scipion.i2pc.es/report_protocols/api/v2/nextprotocol/suggestion/None/
            # 'next_protocol__name', 'count', 'next_protocol__friendlyName', 'next_protocol__package', 'next_protocol__description'
            nextProtName, count, name, package, descr = suggestion
            streamstate = "unknown"
            installed = "Missing. Available in %s plugin." % package
            protClass = Config.getDomain().getProtocols().get(nextProtName, None)

            # Get accurate values from existing installations
            if protClass is not None:
                name = protClass.getClassLabel().lower()
                descr = protClass.getHelpText().strip().replace('\r', '').replace('\n', '').lower()
                streamstate = "streamified" if protClass.worksInStreaming() else "static"
                installed = "installed" if protClass.isInstalled() else "missing installation"

            line = (nextProtName, name,
                    installed,
                    descr,
                    streamstate,
                    "",
                    "",
                    "",
                    count)

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

        :param protList: List of tuples with all the values/columns used in search and shown in the tree"""

        for key, label, installed, help, streamified, beta, new, updated, weight in protList:
            tag = ProtocolTreeConfig.getProtocolTag(installed == 'installed',
                                                    beta == BETA,
                                                    new == NEW,
                                                    updated == UPDATED)

            self._resultsTree.insert(
                '', 'end', key, text="", tags=tag,
                values=(label, weight, streamified, installed, help))


