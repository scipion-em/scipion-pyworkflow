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
""" This modules hosts gui code to visualize steps"""
import json
import tkinter as tk

import pyworkflow.protocol as pwprot
import  pyworkflow.gui as pwgui
import pyworkflow.utils as pwutils


from pyworkflow import TK
from pyworkflow.utils import Icon


class StepsTreeProvider(pwgui.tree.TreeProvider):
    """Create the tree elements for a Protocol run"""

    def __init__(self, stepsList):
        for i, s in enumerate(stepsList):
            if not s._index:
                s._index = i + 1

        self._stepsList = stepsList
        self.getColumns = lambda: [('Index', 50), ('Step', 200), ('Status', 150),
                                   ('Time', 150), ('Class', 100)]
        self._parentDict = {}

    def getObjects(self):
        return self._stepsList

    @staticmethod
    def getObjectInfo(obj):
        info = {'key': obj._index,
                'values': (str(obj), obj.getStatus(), pwutils.prettyDelta(obj.getElapsedTime()),
                           obj.getClassName())}
        return info

    @staticmethod
    def getObjectPreview(obj):

        args = json.loads(obj.argsStr.get())
        msg = "*Prerequisites*: %s \n" % str(obj._prerequisites)
        msg += "*Arguments*: " + '\n  '.join([str(a) for a in args])
        if hasattr(obj, 'resultFiles'):
            results = json.loads(obj.resultFiles.get())
            if len(results):
                msg += "\n*Result files:* " + '\n  '.join(results)

        return None, msg

class StepsWindow(pwgui.browser.BrowserWindow):
    def __init__(self, title, parentWindow, protocol, **args):
        self._protocol = protocol
        provider = StepsTreeProvider(protocol.loadSteps())
        pwgui.browser.BrowserWindow.__init__(self, title, parentWindow,
                                             weight=False, **args)
        # Create buttons toolbar
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.fillToolBar()

        # Create and set browser
        browser = pwgui.browser.ObjectBrowser(self.root, provider,
                                              showPreviewTop=False)
        self.setBrowser(browser, row=1, column=0)

    def fillToolBar(self):
        # Tool bar
        toolbar = tk.Frame(self.root)
        toolbar.grid(row=0, column=0, sticky='nw', padx=5, pady=5)

        # Tree button
        btn = tk.Label(toolbar, text="Tree",
                       image=self.getImage(Icon.CODE_BRANCH),
                       compound=tk.LEFT, cursor='hand2')
        btn.bind(TK.LEFT_CLICK, self._showTree)
        btn.grid(row=0, column=0, sticky='nw')

        # Reset status
        btn = tk.Label(toolbar, text="Reset",
                       image=self.getImage(Icon.BROOM),
                       compound=tk.LEFT, cursor='hand2')
        btn.bind('<Button-1>', self._resetStep)
        btn.grid(row=0, column=1, sticky='nw')

    def _resetStep(self, e=None):

        item = self.browser._lastSelected
        if item is not None:
            objId = item.getObjId()
            self._protocol._updateSteps(lambda step: step.setStatus(pwprot.STATUS_NEW), where="id='%s'" % objId)
            item.setStatus(pwprot.STATUS_NEW)
            self.browser.tree.update()
    # noinspection PyUnusedLocal
    def _showTree(self, e=None):
        g = self._protocol.getStepsGraph()
        w = pwgui.Window("Protocol steps", self, minsize=(800, 600))
        root = w.root
        canvas = pwgui.Canvas(root, width=600, height=500,
                              tooltipCallback=self._stepTooltip,)
        canvas.grid(row=0, column=0, sticky='nsew')
        canvas.drawGraph(g, pwgui.LevelTreeLayout())
        w.show()

    def _stepTooltip(self, tw, item):
        """ Create the contents of the tooltip to be displayed
        for the given step.
        Params:
            tw: a tk.TopLevel instance (ToolTipWindow)
            item: the selected step.
        """

        if not hasattr(item.node, 'step'):
            return

        step = item.node.step

        tm = str(step.funcName)

        if not hasattr(tw, 'tooltipText'):
            frame = tk.Frame(tw)
            frame.grid(row=0, column=0)
            tw.tooltipText = pwgui.dialog.createMessageBody(
                frame, tm, None, textPad=0, textBg=pwutils.Color.ALT_COLOR_2)
            tw.tooltipText.config(bd=1, relief=tk.RAISED)
        else:
            pwgui.dialog.fillMessageText(tw.tooltipText, tm)


