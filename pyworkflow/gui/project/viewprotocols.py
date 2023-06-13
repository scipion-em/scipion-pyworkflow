# -*- coding: utf-8 -*-
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
import logging
import threading

from pyworkflow import Config
from pyworkflow.gui import TextFileViewer, getDefaultFont, LIST_TREEVIEW, \
    ShortCut, ToolTip, RESULT_RUN_ALL, RESULT_RUN_SINGLE, RESULT_CANCEL
from pyworkflow.gui.project.constants import *
from pyworkflow.protocol import SIZE_1MB, SIZE_1GB, SIZE_1TB

INIT_REFRESH_SECONDS = Config.SCIPION_GUI_REFRESH_INITIAL_WAIT

"""
View with the protocols inside the main project window.
"""

import os
import json
import re
import tempfile
from collections import OrderedDict
import tkinter as tk
import tkinter.ttk as ttk
import datetime as dt

from pyworkflow import Config, TK
import pyworkflow.utils as pwutils
import pyworkflow.protocol as pwprot
from pyworkflow.viewer import DESKTOP_TKINTER, ProtocolViewer
from pyworkflow.utils.properties import Color, KEYSYM, Icon, Message
from pyworkflow.webservices import WorkflowRepository

import pyworkflow.gui as pwgui
from pyworkflow.gui.form import FormWindow
from pyworkflow.gui.project.utils import getStatusColorFromNode, inspectObj
from pyworkflow.gui.project.searchprotocol import SearchProtocolWindow, ProtocolTreeProvider
from pyworkflow.gui.project.steps import StepsWindow
from pyworkflow.gui.project.viewprotocols_extra import RunIOTreeProvider, ProtocolTreeConfig
from pyworkflow.gui.project.searchrun import RunsTreeProvider, SearchRunWindow

logger = logging.getLogger(__name__)

DEFAULT_BOX_COLOR = '#f8f8f8'


RUNS_TREE = Icon.RUNS_TREE

VIEW_LIST = 0
VIEW_TREE = 1
VIEW_TREE_SMALL = 2


class ScipionLogWindow(pwgui.Window):
    """Class that create a windows where the system log is display """
    def __init__(self, parentWindow, **kwargs):
        pwgui.Window.__init__(self, title="Scipion log",
                              masterWindow=parentWindow,
                              minsize=(1000, 400))
        content = tk.Frame(self.root)
        content.grid(row=0, column=0, sticky='news')
        pwgui.configureWeigths(content)
        self.showScipionLog = threading.Thread(name="scipion_log",
                                              target=self._showScipionLog,
                                              args=(content,))
        self.showScipionLog.start()

    def _showScipionLog(self, content):
        """
        Create a content of the system log window
        """

        # Fill the Output Log
        terminal = tk.Frame(content)
        terminal.grid(row=0, column=0, sticky='news')
        pwgui.configureWeigths(terminal)

        self.textLog = TextFileViewer(terminal, font=getDefaultFont(),
                                      height=30, width=100)
        self.textLog.grid(row=0, column=0, sticky='news')

        fileLogPath = Config.SCIPION_LOG
        self.fileLog = open(fileLogPath, 'r')
        # Create a tab where the log will appear
        self.textLog.createWidgets([fileLogPath])
        self.textLog.refreshAll(goEnd=True)
        # Refreshing the log every 3 seconds
        self.threadRefresh = threading.Thread(name="refresh_log",
                                              target=self._refreshLogComponent,
                                              args=(3,))
        self.threadRefresh.start()

    def _refreshLogComponent(self, wait=3):
        """ Refresh the Plugin Manager log """
        import time
        while True:
            time.sleep(wait)
            # Taking the vertical scroll position. If this action fail, assume
            # that the log window was closed and finalized the refresh thread
            try:
                vsPos = self.textLog.taList[0].getVScroll()
                if vsPos[1] == 1.0:
                    self.textLog.refreshAll(goEnd=True)
                else:
                    self.textLog.refreshAll(goEnd=False)
            except Exception:
                break

# noinspection PyAttributeOutsideInit
class ProtocolsView(tk.Frame):
    """ What you see when the "Protocols" tab is selected.

    In the main project window there are three tabs: "Protocols | Data | Hosts".
    This extended tk.Frame is what will appear when Protocols is on.
    """

    RUNS_CANVAS_NAME = "runs_canvas"

    SIZE_COLORS = {SIZE_1MB: "green",
                    SIZE_1GB: "orange",
                    SIZE_1TB: "red"}

    _protocolViews = None

    def __init__(self, parent, windows, **args):
        tk.Frame.__init__(self, parent, **args)
        # Load global configuration
        self.windows = windows
        self.project = windows.project
        self.domain = self.project.getDomain()
        self.root = windows.root
        self.getImage = windows.getImage
        self.protCfg = self.getCurrentProtocolView()
        self.settings = windows.getSettings()
        self.runsView = self.settings.getRunsView()
        self._loadSelection()
        self._items = {}
        self._lastSelectedProtId = None
        self._lastStatus = None
        self.selectingArea = False
        self._lastRightClickPos = None  # Keep last right-clicked position

        self.style = ttk.Style()
        self.root.bind("<Control-f>", self._findProtocol)
        self.root.bind("<Control-a>", self._selectAllProtocols)
        self.root.bind("<Control-t>", self._toggleColorScheme)
        self.root.bind("<Control-D>", self._toggleDebug)
        self.root.bind("<Control-l>", self._locateProtocol)

        if Config.debugOn():
            self.root.bind("<Control-i>", self._inspectProtocols)


        self.__autoRefresh = None
        self.__autoRefreshCounter = INIT_REFRESH_SECONDS  # start by 3 secs

        self.refreshSemaphore = True
        self.repeatRefresh = False

        c = self.createContent()
        pwgui.configureWeigths(self)
        c.grid(row=0, column=0, sticky='news')


    def createContent(self):
        """ Create the Protocols View for the Project.
        It has two panes:
            Left: containing the Protocol classes tree
            Right: containing the Runs list
        """
        p = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=Config.SCIPION_BG_COLOR)
        bgColor = Color.ALT_COLOR
        # Left pane, contains Protocols Pane
        leftFrame = tk.Frame(p, bg=bgColor)
        leftFrame.columnconfigure(0, weight=1)
        leftFrame.rowconfigure(1, weight=1)

        # Protocols Tree Pane
        protFrame = tk.Frame(leftFrame, width=300, height=500, bg=bgColor)
        protFrame.grid(row=1, column=0, sticky='news', padx=5, pady=5)
        protFrame.columnconfigure(0, weight=1)
        protFrame.rowconfigure(1, weight=1)
        self._createProtocolsPanel(protFrame, bgColor)
        self.updateProtocolsTree(self.protCfg)
        # Create the right Pane that will be composed by:
        # a Action Buttons TOOLBAR in the top
        # and another vertical Pane with:
        # Runs History (at Top)

        # Selected run info (at Bottom)
        rightFrame = tk.Frame(p, bg=Config.SCIPION_BG_COLOR)
        rightFrame.columnconfigure(0, weight=1)
        rightFrame.rowconfigure(1, weight=1)
        # rightFrame.rowconfigure(0, minsize=label.winfo_reqheight())

        # Create the Action Buttons TOOLBAR
        toolbar = tk.Frame(rightFrame, bg=Config.SCIPION_BG_COLOR)
        toolbar.grid(row=0, column=0, sticky='news')
        pwgui.configureWeigths(toolbar)
        # toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(1, weight=1)

        self.runsToolbar = tk.Frame(toolbar, bg=Config.SCIPION_BG_COLOR)
        self.runsToolbar.grid(row=0, column=0, sticky='sw')
        # On the left of the toolbar will be other
        # actions that can be applied to all runs (refresh, graph view...)
        self.allToolbar = tk.Frame(toolbar, bg=Config.SCIPION_BG_COLOR)
        self.allToolbar.grid(row=0, column=10, sticky='se')
        self.createActionToolbar()

        # Create the Run History tree
        v = ttk.PanedWindow(rightFrame, orient=tk.VERTICAL)
        # runsFrame = ttk.Labelframe(v, text=' History ', width=500, height=500)
        runsFrame = tk.Frame(v, bg=Config.SCIPION_BG_COLOR)
        # runsFrame.grid(row=1, column=0, sticky='news', pady=5)
        self.runsTree = self.createRunsTree(runsFrame)
        pwgui.configureWeigths(runsFrame)

        self.createRunsGraph(runsFrame)

        if self.runsView == VIEW_LIST:
            treeWidget = self.runsTree
        else:
            treeWidget = self.runsGraphCanvas

        treeWidget.grid(row=0, column=0, sticky='news')

        # Create the Selected Run Info
        infoFrame = tk.Frame(v)
        infoFrame.columnconfigure(0, weight=1)
        infoFrame.rowconfigure(1, weight=1)
        # Create the info label
        self.infoLabel = tk.Label(infoFrame)
        self.infoLabel.grid(row=0, column=0, sticky='w', padx=3)
        # Create the Analyze results button
        self.btnAnalyze = pwgui.Button(infoFrame, text=Message.LABEL_ANALYZE,
                                       fg='white', bg=Config.SCIPION_MAIN_COLOR,
                                       image=self.getImage(Icon.ACTION_VISUALIZE),
                                       compound=tk.LEFT,
                                       activeforeground='white',
                                       activebackground=Config.getActiveColor(),
                                       command=self._analyzeResultsClicked)
        self.btnAnalyze.grid(row=0, column=0, sticky='ne', padx=15)
        # self.style.configure("W.TNotebook")#, background='white')
        tab = ttk.Notebook(infoFrame)  # , style='W.TNotebook')

        # Summary tab
        dframe = tk.Frame(tab, bg=Config.SCIPION_BG_COLOR)
        pwgui.configureWeigths(dframe, row=0)
        pwgui.configureWeigths(dframe, row=2)
        # Just configure the provider, later below, in updateSelection, it will be
        # provided with the protocols.
        provider = RunIOTreeProvider(self, None,
                                     self.project.mapper, self.info)

        rowheight = pwgui.getDefaultFont().metrics()['linespace']
        self.style.configure("NoBorder.Treeview", background=Config.SCIPION_BG_COLOR,
                             borderwidth=0, font=self.windows.font,
                             rowheight=rowheight, fieldbackground=Config.SCIPION_BG_COLOR)
        self.infoTree = pwgui.browser.BoundTree(dframe, provider, height=6,
                                                show='tree',
                                                style="NoBorder.Treeview")
        self.infoTree.grid(row=0, column=0, sticky='news')
        label = tk.Label(dframe, text='SUMMARY', bg=Config.SCIPION_BG_COLOR,
                         font=self.windows.fontBold)
        label.grid(row=1, column=0, sticky='nw', padx=(15, 0))

        hView = {'sci-open': self._viewObject,
                 'sci-bib': self._bibExportClicked}

        self.summaryText = pwgui.text.TaggedText(dframe, width=40, height=5,
                                                 bg=Config.SCIPION_BG_COLOR, bd=0,
                                                 font=self.windows.font,
                                                 handlers=hView)
        self.summaryText.grid(row=2, column=0, sticky='news', padx=(30, 0))

        # Method tab
        mframe = tk.Frame(tab)
        pwgui.configureWeigths(mframe)
        # Methods text box
        self.methodText = pwgui.text.TaggedText(mframe, width=40, height=15,
                                                bg=Config.SCIPION_BG_COLOR, handlers=hView)
        self.methodText.grid(row=0, column=0, sticky='news')
        # Reference export button
        # btnExportBib = pwgui.Button(mframe, text=Message.LABEL_BIB_BTN,
        #                             fg='white', bg=Color.MAIN_COLOR,
        #                             image=self.getImage(Icon.ACTION_BROWSE),
        #                             compound=tk.LEFT,
        #                             activeforeground='white',
        #                             activebackground='#A60C0C',
        #                             command=self._bibExportClicked)
        # btnExportBib.grid(row=2, column=0, sticky='w', padx=0)

        # Logs
        ologframe = tk.Frame(tab)
        pwgui.configureWeigths(ologframe)
        self.outputViewer = pwgui.text.TextFileViewer(ologframe, allowOpen=True,
                                                      font=self.windows.font)
        self.outputViewer.grid(row=0, column=0, sticky='news')
        self.outputViewer.windows = self.windows

        self._updateSelection()

        # Move to the selected protocol
        if self._isSingleSelection():
            prot = self.getSelectedProtocol()
            node = self.runsGraph.getNode(str(prot.getObjId()))
            self._selectNode(node)


        # Add all tabs

        tab.add(dframe, text=Message.LABEL_SUMMARY)
        tab.add(mframe, text=Message.LABEL_METHODS)
        tab.add(ologframe, text=Message.LABEL_LOGS_OUTPUT)
        #         tab.add(elogframe, text=Message.LABEL_LOGS_ERROR)
        #         tab.add(slogframe, text=Message.LABEL_LOGS_SCIPION)
        tab.grid(row=1, column=0, sticky='news')

        v.add(runsFrame, weight=1)
        v.add(infoFrame, weight=20)
        v.grid(row=1, column=0, sticky='news')

        # Add sub-windows to PanedWindows
        p.add(leftFrame, padx=0, pady=0, sticky='news')
        p.add(rightFrame, padx=0, pady=0)
        p.paneconfig(leftFrame, minsize=5)
        leftFrame.config(width=235)
        p.paneconfig(rightFrame, minsize=10)

        return p

    def _viewObject(self, objId):
        """ Call appropriate viewer for objId. """
        proj = self.project
        obj = proj.getObject(int(objId))
        viewerClasses = self.domain.findViewers(obj.getClassName(), DESKTOP_TKINTER)
        if not viewerClasses:
            return  # TODO: protest nicely
        viewer = viewerClasses[0](project=proj, parent=self.windows)
        viewer.visualize(obj)

    def _loadSelection(self):
        """ Load selected items, remove if some do not exists. """
        self._selection = self.settings.runSelection
        for protId in list(self._selection):

            if not self.project.doesProtocolExists(protId):
                self._selection.remove(protId)

    def _isMultipleSelection(self):
        return len(self._selection) > 1

    def _isSingleSelection(self):
        return len(self._selection) == 1

    def _noSelection(self):
        return len(self._selection) == 0

    def info(self, message):
        self.infoLabel.config(text=message)
        self.infoLabel.update_idletasks()

    def cleanInfo(self):
        self.info("")

    def refreshRuns(self, e=None, initRefreshCounter=True, checkPids=False):
        """
        Refresh the protocol runs workflow. If the variable REFRESH_WITH_THREADS
        exits, then use a threads to refresh, i.o.c use normal behavior
        """
        useThreads = Config.refreshInThreads()
        if useThreads:
            import threading
            # Refresh the status of displayed runs.
            if self.refreshSemaphore:
                # print("Launching a thread to refresh the runs...")
                threadRefreshRuns = threading.Thread(name="Refreshing runs",
                                                     target=self.refreshDisplayedRuns,
                                                     args=(e, initRefreshCounter,
                                                           checkPids))
                threadRefreshRuns.start()
            else:
                self.repeatRefresh = True
        else:
            self.refreshDisplayedRuns(e, initRefreshCounter, checkPids)

    # noinspection PyUnusedLocal
    def refreshDisplayedRuns(self, e=None, initRefreshCounter=True, checkPids=False):
        """ Refresh the status of displayed runs.
         Params:
            e: Tk event input
            initRefreshCounter: if True the refresh counter will be set to 3 secs
             then only case when False is from _automaticRefreshRuns where the
             refresh time is doubled each time to avoid refreshing too often.
        """
        self.viewButtons[ACTION_REFRESH]['state'] = tk.DISABLED
        self.info('Refreshing...')
        self.refreshSemaphore = False
        if Config.debugOn():
            import psutil
            proc = psutil.Process(os.getpid())
            mem = psutil.virtual_memory()
            logger.debug("------------- refreshing ---------- ")
            files = proc.open_files()
            logger.debug("  open files: %s" % len(files))
            for f in files:
                logger.debug("    - %s, %s" % (f.path, f.fd))
            logger.debug("  memory percent: %s" % proc.memory_percent())

        if self.runsView == VIEW_LIST:
            self.updateRunsTree(True)
        else:
            self.updateRunsGraph(True, checkPids=checkPids)
            self._updateSelection()

        if initRefreshCounter:

            self.__autoRefreshCounter = INIT_REFRESH_SECONDS  # start by 3 secs
            if self.__autoRefresh:
                self.runsTree.after_cancel(self.__autoRefresh)
                self.__autoRefresh = self.runsTree.after(
                    self.__autoRefreshCounter * 1000,
                    self._automaticRefreshRuns)
        self.refreshSemaphore = True
        if self.repeatRefresh:
            self.repeatRefresh = False
            self.refreshRuns()
        self.cleanInfo()
        self.viewButtons[ACTION_REFRESH]['state'] = tk.NORMAL

    # noinspection PyUnusedLocal
    def _automaticRefreshRuns(self, e=None):
        """ Schedule automatic refresh increasing the time between refreshes. """
        if pwutils.envVarOn(Config.SCIPION_GUI_CANCEL_AUTO_REFRESH):
            return

        self.refreshRuns(initRefreshCounter=False, checkPids=True)
        secs = self.__autoRefreshCounter
        # double the number of seconds up to 30 min
        self.__autoRefreshCounter = min(2 * secs, 1800)
        self.__autoRefresh = self.runsTree.after(secs * 1000,
                                                 self._automaticRefreshRuns)

    # noinspection PyUnusedLocal
    def _findProtocol(self, e=None):
        """ Find a desired protocol by typing some keyword. """
        window = SearchProtocolWindow(self.windows)
        window.show()

    def _locateProtocol(self, e=None):

        window = SearchRunWindow(self.windows, self.runsGraph, onDoubleClick=self._onRunClick)
        window.show()
        # self._moveCanvas(0,1)

    def _onRunClick(self, e=None):
        """ Callback to be called when a click happens o a run in the SearchRunWindow.tree"""
        tree = e.widget
        protId = tree.getFirst()
        node = self.runsGraph.getNode(protId)
        self._selectNode(node)

    def _selectNode(self, node):

        x = node.x
        y = node.y
        self._moveCanvas(x,y)

        # Select the protocol
        self._selectItemProtocol(node.run)
        self.refreshDisplayedRuns()

    def _moveCanvas(self, X, Y):

        self.runsGraphCanvas.moveTo(X, Y)

    def _scipionLog(self, e=None):
        windows = ScipionLogWindow(self.windows)
        windows.show()

    def createActionToolbar(self):
        """ Prepare the buttons that will be available for protocol actions. """

        self.actionButtons = {}
        actionList = [
            ACTION_EDIT, ACTION_RENAME, ACTION_DUPLICATE, ACTION_COPY, ACTION_PASTE,  ACTION_DELETE,
            ACTION_BROWSE,
            ACTION_STOP, ACTION_STOP_WORKFLOW, ACTION_CONTINUE, ACTION_CONTINUE_WORKFLOW, ACTION_RESTART_WORKFLOW, ACTION_RESET_WORKFLOW,
            ACTION_RESULTS,
            ACTION_EXPORT, ACTION_EXPORT_UPLOAD,
            ACTION_COLLAPSE, ACTION_EXPAND,
            ACTION_LABELS, ACTION_SEARCH,
            ACTION_SELECT_FROM, ACTION_SELECT_TO,
            ACTION_STEPS, ACTION_DB
        ]

        def addButton(action, text, toolbar):
            btn = tk.Label(toolbar, text="",
                           image=self.getImage(ActionIcons.get(action, None)),
                           compound=tk.LEFT, cursor='hand2', bg=Config.SCIPION_BG_COLOR)

            callback = lambda e: self._runActionClicked(action, event=e)
            btn.bind(TK.LEFT_CLICK, callback)

            # Shortcuts:
            shortCut = ActionShortCuts.get(action, None)
            if shortCut:
                text += " (%s)" % shortCut
                self.root.bind(shortCut, callback)

            ToolTip(btn,text , 500)

            return btn

        for action in actionList:
            self.actionButtons[action] = addButton(action, action,
                                                   self.runsToolbar)

        ActionIcons[ACTION_TREE] = RUNS_TREE

        self.viewButtons = {}

        # Add combo for switch between views
        viewFrame = tk.Frame(self.allToolbar)
        viewFrame.grid(row=0, column=0)
        self._createViewCombo(viewFrame)

        # Add refresh Tree button
        btn = addButton(ACTION_TREE, "  ", self.allToolbar)
        pwgui.tooltip.ToolTip(btn, "Re-organize the node positions.", 1500)
        self.viewButtons[ACTION_TREE] = btn
        if self.runsView != VIEW_LIST:
            btn.grid(row=0, column=1)

        # Add refresh button
        btn = addButton(ACTION_REFRESH, ACTION_REFRESH, self.allToolbar)
        btn.grid(row=0, column=2)
        self.viewButtons[ACTION_REFRESH] = btn

    def _createViewCombo(self, parent):
        """ Create the select-view combobox. """
        label = tk.Label(parent, text='View:', bg=Config.SCIPION_BG_COLOR)
        label.grid(row=0, column=0)
        viewChoices = ['List', 'Tree', 'Tree - small']
        self.switchCombo = pwgui.widgets.ComboBox(parent, width=10,
                                                  choices=viewChoices,
                                                  values=[VIEW_LIST, VIEW_TREE, VIEW_TREE_SMALL],
                                                  initial=viewChoices[self.runsView],
                                                  onChange=lambda e: self._runActionClicked(
                                                      ACTION_SWITCH_VIEW))
        self.switchCombo.grid(row=0, column=1)

    def _updateActionToolbar(self):
        """ Update which action buttons should be visible. """

        def displayAction(actionToDisplay, column, condition=True):

            """ Show/hide the action button if the condition is met. """

            # If action present (set color is not in the toolbar but in the
            # context menu)
            action = self.actionButtons.get(actionToDisplay, None)
            if action is not None:
                if condition:
                    action.grid(row=0, column=column, sticky='sw',
                                padx=(0, 5), ipadx=0)
                else:
                    action.grid_remove()

        for i, actionTuple in enumerate(self.provider.getActionsFromSelection()):
            action, cond = actionTuple
            displayAction(action, i, cond)

    def _createProtocolsTree(self, parent,
                             show='tree', columns=None):

        t = pwgui.tree.Tree(parent, show=show, style=LIST_TREEVIEW,
                            columns=columns)
        t.column('#0', minwidth=300)

        def configureTag(tag, img):
            # Protocol nodes
            t.tag_configure(tag, image=self.getImage(img))
            t.tag_bind(tag, TK.LEFT_DOUBLE_CLICK, self._protocolItemClick)
            t.tag_bind(tag, TK.RETURN, self._protocolItemClick)
            t.tag_bind(tag, TK.ENTER, self._protocolItemClick)

        # Protocol nodes
        configureTag(ProtocolTreeConfig.TAG_PROTOCOL, Icon.PRODUCTION)
        # New protocols
        configureTag(ProtocolTreeConfig.TAG_PROTOCOL_NEW, Icon.NEW)
        # Beta protocols
        configureTag(ProtocolTreeConfig.TAG_PROTOCOL_BETA, Icon.BETA)
        # Disable protocols (not installed) are allowed to be added.
        configureTag(ProtocolTreeConfig.TAG_PROTOCOL_DISABLED,
                     Icon.PROT_DISABLED)
        # Updates protocols
        configureTag(ProtocolTreeConfig.TAG_PROTOCOL_UPDATED,
                     Icon.UPDATED)
        t.tag_configure('protocol_base', image=self.getImage(Icon.GROUP))
        t.tag_configure('protocol_group', image=self.getImage(Icon.GROUP))
        t.tag_configure('section', font=self.windows.fontBold)
        return t

    def _createProtocolsPanel(self, parent, bgColor):
        """Create the protocols Tree displayed in left panel"""
        comboFrame = tk.Frame(parent, bg=bgColor)
        tk.Label(comboFrame, text='View', bg=bgColor).grid(row=0, column=0,
                                                           padx=(0, 5), pady=5)
        choices = self.getProtocolViews()
        initialChoice = self.settings.getProtocolView()
        combo = pwgui.widgets.ComboBox(comboFrame, choices=choices,
                                       initial=initialChoice)
        combo.setChangeCallback(self._onSelectProtocols)
        combo.grid(row=0, column=1)
        comboFrame.grid(row=0, column=0, padx=5, pady=5, sticky='nw')

        t = self._createProtocolsTree(parent)
        t.grid(row=1, column=0, sticky='news')
        # Program automatic refresh
        t.after(3000, self._automaticRefreshRuns)
        self.protTree = t

    def getProtocolViews(self):

        if self._protocolViews is None:
            self._loadProtocols()

        return list(self._protocolViews.keys())

    def getCurrentProtocolView(self):
        """ Select the view that is currently selected.
        Read from the settings the last selected view
        and get the information from the self._protocolViews dict.
        """
        currentView = self.project.getProtocolView()
        if currentView in self.getProtocolViews():
            viewKey = currentView
        else:
            viewKey = self.getProtocolViews()[0]
            self.project.settings.setProtocolView(viewKey)
            if currentView is not None:
                print("PROJECT: Warning, protocol view '%s' not found." % currentView)
                print("         Using '%s' instead." % viewKey)

        return self._protocolViews[viewKey]

    def _loadProtocols(self):
        """ Load protocol configuration from a .conf file. """
        # If the host file is not passed as argument...
        configProtocols = Config.SCIPION_PROTOCOLS

        localDir = Config.SCIPION_LOCAL_CONFIG
        protConf = os.path.join(localDir, configProtocols)
        self._protocolViews = ProtocolTreeConfig.load(self.project.getDomain(),
                                                      protConf)

    def _onSelectProtocols(self, combo):
        """ This function will be called when a protocol menu
        is selected. The index of the new menu is passed. 
        """
        protView = combo.getText()
        self.settings.setProtocolView(protView)
        self.protCfg = self.getCurrentProtocolView()
        self.updateProtocolsTree(self.protCfg)

    def populateTree(self, tree, treeItems, prefix, obj, subclassedDict, level=0):

        # If node does not have leaves (protocols) do not add it
        if not obj.visible:
            return

        text = obj.text
        if text:
            value = obj.value if obj.value is not None else text
            key = '%s.%s' % (prefix, value)
            img = obj.icon if obj.icon is not None else ''
            tag = obj.tag if obj.tag is not None else ''

            if len(img):
                img = self.getImage(img)
                # If image is none
                img = img if img is not None else ''

            protClassName = value.split('.')[-1]  # Take last part
            emProtocolsDict = self.domain.getProtocols()
            prot = emProtocolsDict.get(protClassName, None)

            if tag == 'protocol' and text == 'default':
                if prot is None:
                    print("Protocol className '%s' not found!!!. \n"
                          "Fix your config/protocols.conf configuration."
                          % protClassName)
                    return

                text = prot.getClassLabel()

            item = tree.insert(prefix, 'end', key, text=text, image=img, tags=tag)
            treeItems[item] = obj
            # Check if the attribute should be open or close
            openItem = getattr(obj, 'openItem', level < 2)
            if openItem:
                tree.item(item, open=openItem)

            # I think this mode is deprecated
            if obj.value is not None and tag == 'protocol_base':
                logger.warning('protocol_base tags are deprecated')
        else:
            key = prefix

        for sub in obj:
            self.populateTree(tree, treeItems, key, sub, subclassedDict,
                              level + 1)

    def updateProtocolsTree(self, protCfg):

        try:
            self.protCfg = protCfg
            self.protTree.clear()
            self.protTree.unbind(TK.TREEVIEW_OPEN)
            self.protTree.unbind(TK.TREEVIEW_CLOSE)
            self.protTreeItems = {}
            subclassedDict = {}  # Check which classes serve as base to not show them
            emProtocolsDict = self.domain.getProtocols()
            for _, v1 in emProtocolsDict.items():
                for k2, v2 in emProtocolsDict.items():
                    if v1 is not v2 and issubclass(v1, v2):
                        subclassedDict[k2] = True
            self.populateTree(self.protTree, self.protTreeItems, '', self.protCfg,
                              subclassedDict)
            self.protTree.bind(TK.TREEVIEW_OPEN,
                               lambda e: self._treeViewItemChange(True))
            self.protTree.bind(TK.TREEVIEW_CLOSE,
                               lambda e: self._treeViewItemChange(False))
        except Exception as e:
            # Tree can't be loaded report back, but continue
            print("Protocols tree couldn't be loaded: %s" % e)

    def _treeViewItemChange(self, openItem):
        item = self.protTree.focus()
        if item in self.protTreeItems:
            self.protTreeItems[item].openItem = openItem

    def createRunsTree(self, parent):
        self.provider = RunsTreeProvider(self.project, self._runActionClicked)

        # This line triggers the getRuns for the first time.
        # Ne need to force the check pids here, temporary
        self.provider._checkPids = True

        t = pwgui.tree.BoundTree(parent, self.provider, style=LIST_TREEVIEW)
        self.provider._checkPids = False

        t.itemDoubleClick = self._runItemDoubleClick
        t.itemClick = self._runTreeItemClick

        return t

    def updateRunsTree(self, refresh=False):
        self.provider.setRefresh(refresh)
        self.runsTree.update()
        self.updateRunsTreeSelection()

    def updateRunsTreeSelection(self):
        for prot in self._iterSelectedProtocols():
            treeId = self.provider.getObjectFromId(prot.getObjId())._treeId
            self.runsTree.selection_add(treeId)

    def createRunsGraph(self, parent):
        self.runsGraphCanvas = pwgui.Canvas(parent, width=400, height=400,
                                            tooltipCallback=self._runItemTooltip,
                                            tooltipDelay=1000,
                                            name=ProtocolsView.RUNS_CANVAS_NAME,
                                            takefocus=True,
                                            highlightthickness=0)

        self.runsGraphCanvas.onClickCallback = self._runItemClick
        self.runsGraphCanvas.onDoubleClickCallback = self._runItemDoubleClick
        self.runsGraphCanvas.onRightClickCallback = self._runItemRightClick
        self.runsGraphCanvas.onControlClickCallback = self._runItemControlClick
        self.runsGraphCanvas.onAreaSelected = self._selectItemsWithinArea
        self.runsGraphCanvas.onMiddleMouseClickCallback = self._runItemMiddleClick

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self.settings.getNodes().updateDict()
        self.settings.getLabels().updateDict()

        self.updateRunsGraph()

    def updateRunsGraph(self, refresh=False, checkPids=False):

        self.runsGraph = self.project.getRunsGraph(refresh=refresh,
                                                   checkPids=checkPids)
        self.drawRunsGraph()

    def drawRunsGraph(self, reorganize=False):

        # Check if there are positions stored
        if reorganize:
            # Create layout to arrange nodes as a level tree
            layout = pwgui.LevelTreeLayout()
            self.runsGraphCanvas.reorganizeGraph(self.runsGraph, layout)
        else:
            self.runsGraphCanvas.clear()
            layout = pwgui.LevelTreeLayout(partial=True)

            # Create empty nodeInfo for new runs
            for node in self.runsGraph.getNodes():
                nodeId = node.run.getObjId() if node.run else 0
                nodeInfo = self.settings.getNodeById(nodeId)
                if nodeInfo is None:
                    self.settings.addNode(nodeId, x=0, y=0, expanded=True,
                                          visible=True)

            self.runsGraphCanvas.drawGraph(self.runsGraph, layout,
                                           drawNode=self.createRunItem,
                                           nodeList=self.settings.nodeList)

            projectSize = len(self.runsGraph.getNodes())
            settingsNodeSize = len(self.settings.getNodes())
            if projectSize < settingsNodeSize -1:
                logger.info("Settings nodes list (%s) is bigger than current project nodes (%s). "
                            "Clean up needed?" % (settingsNodeSize, projectSize) )
                self.settings.cleanUpNodes(self.runsGraph.getNodeNames(), toRemove=False)

    def createRunItem(self, canvas, node):

        nodeId = node.run.getObjId() if node.run else 0
        nodeInfo = self.settings.getNodeById(nodeId)

        # Extend attributes: use some from nodeInfo
        node.expanded = nodeInfo.isExpanded()
        node.x, node.y = nodeInfo.getPosition()
        node.visible = nodeInfo.isVisible()
        nodeText = self._getNodeText(node)

        # Get status color
        statusColor = getStatusColorFromNode(node)

        # Get the box color (depends on color mode: label or status)
        boxColor = self._getBoxColor(nodeInfo, statusColor, node)

        # Draw the box
        item = RunBox(nodeInfo, self.runsGraphCanvas,
                      nodeText, node.x, node.y,
                      bgColor=boxColor, textColor='black')
        # No border
        item.margin = 0

        # Paint the oval..if apply.
        self._paintOval(item, statusColor)

        # Paint the bottom line (for now only labels are painted there).
        self._paintBottomLine(item)

        item.setSelected(nodeId in self._selection)
        return item

    def _getBoxColor(self, nodeInfo, statusColor, node):

        try:

            # If the color has to go to the box
            if self.settings.statusColorMode():
                boxColor = statusColor

            elif self.settings.ageColorMode():

                if node.run:

                    # Project elapsed time
                    elapsedTime = node.run.getProject().getElapsedTime()
                    creationTime = node.run.getProject().getCreationTime()

                    # Get the latest activity timestamp
                    ts = node.run.endTime.datetime()

                    if elapsedTime is None or creationTime is None or ts is None:
                        boxColor = DEFAULT_BOX_COLOR

                    else:

                        # tc closer to the end are younger
                        protAge = ts - creationTime

                        boxColor = self._ageColor('#6666ff', elapsedTime,
                                                  protAge)
                else:
                    boxColor = DEFAULT_BOX_COLOR

            elif self.settings.sizeColorMode():

                # Get the protocol size
                protSize = self._getRunSize(node)

                boxColor = self._sizeColor(protSize)

            # ... box is for the labels.
            elif self.settings.labelsColorMode():
                # If there is only one label use the box for the color.
                if self._getLabelsCount(nodeInfo) == 1:

                    labelId = nodeInfo.getLabels()[0]
                    label = self.settings.getLabels().getLabel(labelId)

                    # If there is no label (it has been deleted)
                    if label is None:
                        nodeInfo.getLabels().remove(labelId)
                        boxColor = DEFAULT_BOX_COLOR
                    else:
                        boxColor = label.getColor()

                else:
                    boxColor = DEFAULT_BOX_COLOR
            else:
                boxColor = DEFAULT_BOX_COLOR

            return boxColor
        except Exception as e:
            logger.debug("Can't get color for %s. %s" % (node, e))
            return DEFAULT_BOX_COLOR

    @staticmethod
    def _getRunSize(node):
        """
        Returns the size "recursively" of a run

        :param node: node of the graph.
        :return: size in bytes

        """

        if not node.run:
            return 0
        else:
            return node.run.getSize()

    @classmethod
    def _sizeColor(cls, size):
        """
        Returns the color that corresponds to the size
        :param size:
        :return:
        """

        for threshold, color in cls.SIZE_COLORS.items():
            if size <= threshold:
                return color

        return "#000000"
    @staticmethod
    def _ageColor(rgbColorStr, projectAge, protocolAge):

        #  Get the ratio
        ratio = protocolAge.seconds / float(projectAge.seconds)

        # Invert direction: older = white = 100%, newest = rgbColor = 0%
        ratio = 1 - ratio

        # There are cases coming with protocols older than the project.
        ratio = 0 if ratio < 0 else ratio

        hexTuple = pwutils.hex_to_rgb(rgbColorStr)
        lighterTuple = pwutils.lighter(hexTuple, ratio)
        return pwutils.rgb_to_hex(lighterTuple)

    @staticmethod
    def _getLabelsCount(nodeInfo):

        return 0 if nodeInfo.getLabels() is None else len(nodeInfo.getLabels())

    def _paintBottomLine(self, item):

        if self.settings.labelsColorMode():
            self._addLabels(item)

    def _paintOval(self, item, statusColor):
        # Show the status as a circle in the top right corner
        if not self.settings.statusColorMode():
            # Option: Status item.
            (topLeftX, topLeftY, bottomRightX,
             bottomRightY) = self.runsGraphCanvas.bbox(item.id)
            statusSize = 10
            statusX = bottomRightX - (statusSize + 3)
            statusY = topLeftY + 3

            pwgui.Oval(self.runsGraphCanvas, statusX, statusY, statusSize,
                       color=statusColor, anchor=item)

        # in statusColorMode
        else:
            # Show a black circle if there is any label
            if self._getLabelsCount(item.nodeInfo) > 0:
                (topLeftX, topLeftY, bottomRightX,
                 bottomRightY) = self.runsGraphCanvas.bbox(item.id)
                statusSize = 10
                statusX = bottomRightX - (statusSize + 3)
                statusY = topLeftY + 3

                pwgui.Oval(self.runsGraphCanvas, statusX, statusY, statusSize,
                           color='black', anchor=item)

    def _getNodeText(self, node):
        nodeText = node.getLabel()
        # Truncate text to prevent overflow
        if len(nodeText) > 40:
            nodeText = nodeText[:37] + "..."

        if node.run:
            expandedStr = '' if node.expanded else '\n ➕ %s more' % str(node.countChilds({}))
            if self.runsView == VIEW_TREE_SMALL:
                nodeText = node.getName() + expandedStr
            else:
                nodeText += expandedStr + '\n' + node.run.getStatusMessage() if not expandedStr else expandedStr
                if node.run.summaryWarnings:
                    nodeText += u' \u26a0'
        return nodeText

    def _addLabels(self, item):
        # If there is only one label it should be already used in the box color.
        if self._getLabelsCount(item.nodeInfo) < 2:
            return
        # Get the positions of the box
        (topLeftX, topLeftY, bottomRightX,
         bottomRightY) = self.runsGraphCanvas.bbox(item.id)

        # Get the width of the box
        boxWidth = bottomRightX - topLeftX

        # Set the size
        marginV = 3
        marginH = 2
        labelWidth = (boxWidth - (2 * marginH)) / len(item.nodeInfo.getLabels())
        labelHeight = 6

        # Leave some margin on the right and bottom
        labelX = bottomRightX - marginH
        labelY = bottomRightY - (labelHeight + marginV)

        for index, labelId in enumerate(item.nodeInfo.getLabels()):

            # Get the label
            label = self.settings.getLabels().getLabel(labelId)

            # If not none
            if label is not None:
                # Move X one label to the left
                if index == len(item.nodeInfo.getLabels()) - 1:
                    labelX = topLeftX + marginH
                else:
                    labelX -= labelWidth

                pwgui.Rectangle(self.runsGraphCanvas, labelX, labelY,
                                labelWidth, labelHeight, color=label.getColor(),
                                anchor=item)
            else:

                item.nodeInfo.getLabels().remove(labelId)

    def switchRunsView(self):
        viewValue = self.switchCombo.getValue()
        self.runsView = viewValue
        self.settings.setRunsView(viewValue)

        if viewValue == VIEW_LIST:
            self.runsTree.grid(row=0, column=0, sticky='news')
            self.runsGraphCanvas.frame.grid_remove()
            self.updateRunsTree()
            self.viewButtons[ACTION_TREE].grid_remove()
            self._lastRightClickPos = None
        else:
            self.runsTree.grid_remove()
            self.updateRunsGraph()
            self.runsGraphCanvas.frame.grid(row=0, column=0, sticky='news')
            self.viewButtons[ACTION_TREE].grid(row=0, column=1)

    def _protocolItemClick(self, e=None):
        # Get the tree widget that originated the event
        # it could be the left panel protocols tree or just
        # the search protocol dialog tree
        tree = e.widget
        protClassName = tree.getFirst().split('.')[-1]
        protClass = self.domain.getProtocols().get(protClassName)
        prot = self.project.newProtocol(protClass)
        self._openProtocolForm(prot, disableRunMode=True)

    def _toggleColorScheme(self, e=None):

        currentMode = self.settings.getColorMode()

        if currentMode >= len(self.settings.COLOR_MODES) - 1:
            currentMode = -1

        nextColorMode = currentMode + 1

        self.settings.setColorMode(nextColorMode)
        self._updateActionToolbar()
        # self.updateRunsGraph()
        self.drawRunsGraph()
        self._infoAboutColorScheme()

    def _infoAboutColorScheme(self):
        """ Writes in the info widget a brief description abot the color scheme."""

        colorScheme = self.settings.getColorMode()

        msg = "Color mode changed to %s. %s"
        if colorScheme == self.settings.COLOR_MODE_AGE:
            msg = msg % ("AGE", "Young boxes will have an darker color.")
        elif colorScheme == self.settings.COLOR_MODE_SIZE:
            keys = list(self.SIZE_COLORS.keys())
            msg = msg % ("SIZE", "Semaphore color scheme. Green <= %s, Orange <=%s, Red <=%s, Dark quite big." %
                         (pwutils.prettySize(keys[0]),
                          pwutils.prettySize(keys[1]),
                          pwutils.prettySize(keys[2]))
                         )
        elif colorScheme == self.settings.COLOR_MODE_STATUS:
            msg = msg % ("STATUS", "Color based on the status. A black circle indicates it has labels")
        elif colorScheme == self.settings.COLOR_MODE_LABELS:
            msg = msg % ("LABELS", "Color based on custom labels you've assigned. Small circles reflect the protocol status")

        self.info(msg)
    def _toggleDebug(self, e=None):
        Config.toggleDebug()

    def _selectAllProtocols(self, e=None):
        self._selection.clear()

        # WHY GOING TO THE db?
        #  Let's try using in memory data.
        # for prot in self.project.getRuns():
        for prot in self.project.runs:
            self._selection.append(prot.getObjId())
        self._updateSelection()

        # self.updateRunsGraph()
        self.drawRunsGraph()

    def _inspectProtocols(self, e=None):
        objs = self._getSelectedProtocols()
        # We will inspect the selected objects or
        #   the whole project is no protocol is selected
        if len(objs) > 0:
            objs.sort(key=lambda obj: obj._objId, reverse=True)
            filePath = objs[0]._getLogsPath('inspector.csv')
            doInspect = True
        else:
            proj = self.project
            filePath = proj.getLogPath('inspector.csv')
            objs = [proj]
            doInspect = pwgui.dialog.askYesNo(Message.TITLE_INSPECTOR,
                                              Message.LABEL_INSPECTOR, self.root)

        if doInspect:
            inspectObj(objs, filePath)
            # we open the resulting CSV file with the OS default software
            pwgui.text.openTextFileEditor(filePath)

    # NOt used!: pconesa 02/11/2016.
    # def _deleteSelectedProtocols(self, e=None):
    #
    #     for selection in self._selection:
    #         self.project.getProtocol(self._selection[0])
    #
    #
    #     self._updateSelection()
    #     self.updateRunsGraph()

    def _updateSelection(self):
        self._fillSummary()
        self._fillMethod()
        self._fillLogs()
        self._showHideAnalyzeResult()

        if self._isSingleSelection():
            last = self.getSelectedProtocol()
            self._lastSelectedProtId = last.getObjId() if last else None

        self._updateActionToolbar()

    def _runTreeItemClick(self, item=None):
        self._selection.clear()
        for prot in self.runsTree.iterSelectedObjects():
            self._selection.append(prot.getObjId())
        self._updateSelection()

    def _selectItemProtocol(self, prot):
        """ Call this function when a new box (item) of a protocol
        is selected. It should be called either from itemClick
        or itemRightClick
        """
        self._selection.clear()
        self.settings.dataSelection.clear()
        self._selection.append(prot.getObjId())

        # Select output data too
        self.toggleDataSelection(prot, True)

        self._updateSelection()
        self.runsGraphCanvas.update_idletasks()

    def _deselectItems(self, item):
        """ Deselect all items except the item one
        """
        g = self.project.getRunsGraph()

        for node in g.getNodes():
            if node.run and node.run.getObjId() in self._selection:
                # This option is only for compatibility with all projects
                if hasattr(node, 'item'):
                    node.item.setSelected(False)
        item.setSelected(True)

    def _runItemClick(self, item=None):

        # If click is in a empty area....start panning
        if item is None:
            print("Click on empty area")
            return

        self.runsGraphCanvas.focus_set()

        # Get last selected item for tree or graph
        if self.runsView == VIEW_LIST:
            prot = self.project.mapper.selectById(int(self.runsTree.getFirst()))
        else:
            prot = item.node.run
            if prot is None:  # in case it is the main "Project" node
                return
            self._deselectItems(item)
        self._selectItemProtocol(prot)

    def _runItemDoubleClick(self, e=None):
        if e.nodeInfo.isExpanded():
            self._runActionClicked(ACTION_EDIT)

    def _runItemMiddleClick(self, e=None):
        self._runActionClicked(ACTION_SELECT_TO)

    def _runItemRightClick(self, item=None):
        prot = item.node.run
        if prot is None:  # in case it is the main "Project" node
            return
        n = len(self._selection)
        # Only select item with right-click if there is a single
        # item selection, not for multiple selection
        if n <= 1:
            self._deselectItems(item)
            self._selectItemProtocol(prot)
            self._lastRightClickPos = self.runsGraphCanvas.eventPos

        return self.provider.getObjectActions(prot)

    def _runItemControlClick(self, item=None):
        # Get last selected item for tree or graph
        if self.runsView == VIEW_LIST:
            # TODO: Prot is not used!!
            prot = self.project.mapper.selectById(int(self.runsTree.getFirst()))
        else:
            prot = item.node.run
            protId = prot.getObjId()
            if protId in self._selection:
                item.setSelected(False)
                self._selection.remove(protId)

                # Remove data selected
                self.toggleDataSelection(prot, False)
            else:

                item.setSelected(True)
                if len(self._selection) == 1:  # repaint first selected item
                    firstSelectedNode = self.runsGraph.getNode(str(self._selection[0]))
                    if hasattr(firstSelectedNode, 'item'):
                        firstSelectedNode.item.setSelected(False)
                        firstSelectedNode.item.setSelected(True)
                self._selection.append(prot.getObjId())

                # Select output data too
                self.toggleDataSelection(prot, True)

        self._updateSelection()

    def toggleDataSelection(self, prot, append):

        # Go through the data selection
        for paramName, output in prot.iterOutputAttributes():
            if append:
                self.settings.dataSelection.append(output.getObjId())
            else:
                self.settings.dataSelection.remove(output.getObjId())

    def _runItemTooltip(self, tw, item):
        """ Create the contents of the tooltip to be displayed
        for the given item.
        Params:
            tw: a tk.TopLevel instance (ToolTipWindow)
            item: the selected item.
        """
        prot = item.node.run

        if prot:
            tm = '*%s*\n' % prot.getRunName()
            tm += 'Identifier :%s\n' % prot.getObjId()
            tm += 'Status: %s\n' % prot.getStatusMessage()
            tm += 'Wall time: %s\n' % pwutils.prettyDelta(prot.getElapsedTime())
            tm += 'CPU time: %s\n' % pwutils.prettyDelta(dt.timedelta(seconds=prot.cpuTime))
            tm += 'Folder size: %s\n' % pwutils.prettySize(prot.getSize())

            if not hasattr(tw, 'tooltipText'):
                frame = tk.Frame(tw)
                frame.grid(row=0, column=0)
                tw.tooltipText = pwgui.dialog.createMessageBody(frame, tm, None,
                                                                textPad=0,
                                                                textBg=Color.ALT_COLOR_2)
                tw.tooltipText.config(bd=1, relief=tk.RAISED)
            else:
                pwgui.dialog.fillMessageText(tw.tooltipText, tm)

    @staticmethod
    def _selectItemsWithinArea(x1, y1, x2, y2, enclosed=False):
        """
        Parameters
        ----------
        x1: x coordinate of first corner of the area
        y1: y coordinate of first corner of the area
        x2: x coordinate of second corner of the area
        y2: y coordinate of second corner of the area
        enclosed: Default True. Returns enclosed items,
                  overlapping items otherwise.
        Returns
        -------
        Nothing

        """

        return
        # NOT working properly: Commented for the moment.
        # if enclosed:
        #     items = self.runsGraphCanvas.find_enclosed(x1, y1, x2, y2)
        # else:
        #     items = self.runsGraphCanvas.find_overlapping(x1, y1, x2, y2)
        #
        # update = False
        #
        # for itemId in items:
        #     if itemId in self.runsGraphCanvas.items:
        #
        #         item = self.runsGraphCanvas.items[itemId]
        #         if not item.node.isRoot():
        #             item.setSelected(True)
        #             self._selection.append(itemId)
        #             update = True
        #
        # if update is not None: self._updateSelection()

    def _openProtocolForm(self, prot, disableRunMode=False):
        """Open the Protocol GUI Form given a Protocol instance"""

        w = FormWindow(Message.TITLE_NAME_RUN + prot.getClassName(),
                       prot, self._executeSaveProtocol, self.windows,
                       hostList=self.project.getHostNames(),
                       updateProtocolCallback=self._updateProtocol,
                       disableRunMode=disableRunMode)
        w.adjustSize()
        w.show(center=True)

    def _browseSteps(self):
        """ Open a new window with the steps list. """
        window = StepsWindow(Message.TITLE_BROWSE_DATA, self.windows,
                             self.getSelectedProtocol())
        window.show()

    def _browseRunData(self):
        provider = ProtocolTreeProvider(self.getSelectedProtocol())
        window = pwgui.browser.BrowserWindow(Message.TITLE_BROWSE_DATA,
                                             self.windows)
        window.setBrowser(pwgui.browser.ObjectBrowser(window.root, provider))
        window.itemConfig(self.getSelectedProtocol(), open=True)
        window.show()

    def _browseRunDirectory(self):
        """ Open a file browser to inspect the files generated by the run. """
        protocol = self.getSelectedProtocol()
        workingDir = protocol.getWorkingDir()
        if os.path.exists(workingDir):

            protFolderShortCut = ShortCut.factory(workingDir,name="Protocol folder", icon=None ,toolTip="Protocol directory")
            window = pwgui.browser.FileBrowserWindow("Browsing: " + workingDir,
                                                     master=self.windows,
                                                     path=workingDir,
                                                     shortCuts=[protFolderShortCut])
            window.show()
        else:
            self.windows.showInfo("Protocol working dir does not exists: \n %s"
                                  % workingDir)

    def _iterSelectedProtocols(self):
        for protId in sorted(self._selection):
            prot = self.project.getRunsGraph().getNode(str(protId)).run
            if prot:
                yield prot

    def _getSelectedProtocols(self):
        return [prot for prot in self._iterSelectedProtocols()]

    def _iterSelectedNodes(self):

        for protId in sorted(self._selection):
            node = self.settings.getNodeById(protId)

            yield node

    def _getSelectedNodes(self):
        return [node for node in self._iterSelectedNodes()]

    def getSelectedProtocol(self):
        if self._selection:
            return self.project.getProtocol(self._selection[0])
        return None

    def _showHideAnalyzeResult(self):

        if self._selection:
            self.btnAnalyze.grid()
        else:
            self.btnAnalyze.grid_remove()

    def _fillSummary(self):
        self.summaryText.setReadOnly(False)
        self.summaryText.clear()
        self.infoTree.clear()
        n = len(self._selection)

        if n == 1:
            prot = self.getSelectedProtocol()

            if prot:
                provider = RunIOTreeProvider(self, prot, self.project.mapper, self.info)
                self.infoTree.setProvider(provider)
                self.infoTree.grid(row=0, column=0, sticky='news')
                self.infoTree.update_idletasks()
                # Update summary
                self.summaryText.addText(prot.summary())
            else:
                self.infoTree.clear()

        elif n > 1:
            self.infoTree.clear()
            for prot in self._iterSelectedProtocols():
                self.summaryText.addLine('> _%s_' % prot.getRunName())
                for line in prot.summary():
                    self.summaryText.addLine(line)
                self.summaryText.addLine('')
        self.summaryText.setReadOnly(True)

    def _fillMethod(self):

        try:
            self.methodText.setReadOnly(False)
            self.methodText.clear()
            self.methodText.addLine("*METHODS:*")
            cites = OrderedDict()

            for prot in self._iterSelectedProtocols():
                self.methodText.addLine('> _%s_' % prot.getRunName())
                for line in prot.getParsedMethods():
                    self.methodText.addLine(line)
                cites.update(prot.getCitations())
                cites.update(prot.getPackageCitations())
                self.methodText.addLine('')

            if cites:
                self.methodText.addLine('*REFERENCES:*   '
                                        ' [[sci-bib:][<<< Open as bibtex >>>]]')
                for cite in cites.values():
                    self.methodText.addLine(cite)

            self.methodText.setReadOnly(True)
        except Exception as e:
            self.methodText.addLine('Could not load all methods:' + str(e))

    def _fillLogs(self):
        try:
            prot = self.getSelectedProtocol()

            if not self._isSingleSelection() or not prot:
                self.outputViewer.clear()
                self._lastStatus = None
            elif prot.getObjId() != self._lastSelectedProtId:
                self._lastStatus = prot.getStatus()
                i = self.outputViewer.getIndex()
                self.outputViewer.clear()
                # Right now skip the err tab since we are redirecting
                # stderr to stdout
                out, err, schedule = prot.getLogPaths()
                self.outputViewer.addFile(out)
                self.outputViewer.addFile(err)
                if os.path.exists(schedule):
                    self.outputViewer.addFile(schedule)
                elif i == 2:
                    i = 0
                self.outputViewer.setIndex(i)  # Preserve the last selected tab
                self.outputViewer.selectedText().goEnd()
                # when there are not logs, force re-load next time
                if (not os.path.exists(out) or
                        not os.path.exists(err)):
                    self._lastStatus = None

            elif prot.isActive() or prot.getStatus() != self._lastStatus:
                doClear = self._lastStatus is None
                self._lastStatus = prot.getStatus()
                self.outputViewer.refreshAll(clear=doClear, goEnd=doClear)
        except Exception as e:
            self.info("Something went wrong filling %s's logs: %s. Check terminal for details" % (prot, e))
            import traceback
            traceback.print_exc()

    def _scheduleRunsUpdate(self, secs=1):
        # self.runsTree.after(secs*1000, self.refreshRuns)
        self.windows.enqueue(self.refreshRuns)

    def executeProtocol(self, prot):
        """ Function to execute a protocol called not
        directly from the Form "Execute" button.
        """
        # We need to equeue the execute action
        # to be executed in the same thread
        self.windows.enqueue(lambda: self._executeSaveProtocol(prot))

    def _executeSaveProtocol(self, prot, onlySave=False, doSchedule=False):
        if onlySave:
            self.project.saveProtocol(prot)
            msg = Message.LABEL_SAVED_FORM
            # msg = "Protocol successfully saved."

        else:
            if doSchedule:
                self.project.scheduleProtocol(prot)
            else:
                self.project.launchProtocol(prot)
            # Select the launched protocol to display its summary, methods..etc
            self._selection.clear()
            self._selection.append(prot.getObjId())
            self._updateSelection()
            self._lastStatus = None  # clear lastStatus to force re-load the logs
            msg = ""

        # Update runs list display, even in save we
        # need to get the updated copy of the protocol
        self._scheduleRunsUpdate()
        self._selectItemProtocol(prot)

        return msg

    def _updateProtocol(self, prot):
        """ Callback to notify about the change of a protocol
        label or comment. 
        """
        self._scheduleRunsUpdate()

    def _continueProtocol(self, prot):
        self.project.continueProtocol(prot)
        self._scheduleRunsUpdate()

    def _onDelPressed(self):
        # This function will be connected to the key 'Del' press event
        # We need to check if the canvas have the focus and then
        # proceed with the delete action

        # get the widget with the focus
        widget = self.focus_get()

        # Call the delete action only if the widget is the canvas
        if str(widget).endswith(ProtocolsView.RUNS_CANVAS_NAME):
            try:
                self._deleteProtocol()
            except Exception as ex:
                self.windows.showError(str(ex))

    def _deleteProtocol(self):
        protocols = self._getSelectedProtocols()

        if len(protocols) == 0:
            return

        protStr = '\n  - '.join(['*%s*' % p.getRunName() for p in protocols])

        if pwgui.dialog.askYesNo(Message.TITLE_DELETE_FORM,
                                 Message.LABEL_DELETE_FORM % protStr,
                                 self.root):
            self.info('Deleting protocols...')
            self.project.deleteProtocol(*protocols)
            self.settings.cleanUpNodes([str(prot.getObjId()) for prot in protocols])
            self._selection.clear()
            self._updateSelection()
            self._scheduleRunsUpdate()
            self.cleanInfo()


    def _editProtocol(self, protocol):
        disableRunMode = False
        if protocol.isSaved():
            disableRunMode = True
        self._openProtocolForm(protocol, disableRunMode=disableRunMode)

    def _pasteProtocolsFromClipboard(self, e=None):
        """ Pastes the content of the clipboard providing is a json workflow"""

        try:

            self.project.loadProtocols(jsonStr=self.clipboard_get())
            self.info("Clipboard content pasted successfully.")
        except Exception as e:
            self.info("Paste failed, maybe clipboard content is not valid content? See GUI log for details.")
            logger.error("Clipboard content couldn't be pasted." , exc_info=e)

    def _copyProtocolsToClipboard(self, e=None):

        protocols = self._getSelectedProtocols()

        jsonStr = self.project.getProtocolsJson(protocols)

        self.clipboard_clear()
        self.clipboard_append(jsonStr)
        self.info("Protocols copied to the clipboard. Now you can paste them here, another project or in a template or ... anywhere!.")

    def _copyProtocols(self, e=None):
        protocols = self._getSelectedProtocols()
        if len(protocols) == 1:
            newProt = self.project.copyProtocol(protocols[0])
            if newProt is None:
                self.windows.showError("Error copying protocol.!!!")
            else:
                self._openProtocolForm(newProt, disableRunMode=True)
        else:
            self.info('Copying the protocols...')
            self.project.copyProtocol(protocols)
            self.refreshRuns()
            self.cleanInfo()

    def _stopWorkFlow(self, action):

        protocols = self._getSelectedProtocols()

        # TODO: use filterCallback param and we may not need to return 2 elements
        workflowProtocolList, activeProtList = self.project._getSubworkflow(protocols[0],
                                                                            fixProtParam=False,
                                                                            getStopped=False)
        if activeProtList:
            errorProtList = []
            if pwgui.dialog.askYesNo(Message.TITLE_STOP_WORKFLOW_FORM,
                                     Message.TITLE_STOP_WORKFLOW, self.root):
                self.info('Stopping the workflow...')
                errorProtList = self.project.stopWorkFlow(activeProtList)
                self.cleanInfo()
                self.refreshRuns()
            if errorProtList:
                msg = '\n'
                for prot in errorProtList:
                    msg += str(prot.getObjLabel()) + '\n'
                pwgui.dialog.MessageDialog(
                    self, Message.TITLE_STOPPED_WORKFLOW_FAILED,
                    Message.TITLE_STOPPED_WORKFLOW_FAILED + ' with: ' + msg,
                    Icon.ERROR)

    def _resetWorkFlow(self, action):

        protocols = self._getSelectedProtocols()
        errorProtList = []
        if pwgui.dialog.askYesNo(Message.TITLE_RESET_WORKFLOW_FORM,
                                 Message.TITLE_RESET_WORKFLOW, self.root):
            self.info('Resetting the workflow...')
            workflowProtocolList, activeProtList = self.project._getSubworkflow(protocols[0])
            errorProtList = self.project.resetWorkFlow(workflowProtocolList)
            self.cleanInfo()
            self.refreshRuns()
        if errorProtList:
            msg = '\n'
            for prot in errorProtList:
                msg += str(prot.getObjLabel()) + '\n'
            pwgui.dialog.MessageDialog(
                self, Message.TITLE_RESETED_WORKFLOW_FAILED,
                Message.TITLE_RESETED_WORKFLOW_FAILED + ' with: ' + msg,
                Icon.ERROR)

    def _launchWorkFlow(self, action):
        """
        This function can launch a workflow from a selected protocol in two
        modes depending on the 'action' value (RESTART, CONTINUE)
        """
        protocols = self._getSelectedProtocols()
        mode = pwprot.MODE_RESTART if action == ACTION_RESTART_WORKFLOW else pwprot.MODE_RESUME
        errorList, _ = self._launchSubWorkflow(protocols[0], mode,  self.root)

        if errorList:
            msg = ''
            for errorProt in errorList:
                msg += str(errorProt) + '\n'
            pwgui.dialog.MessageDialog(
                self, Message.TITLE_LAUNCHED_WORKFLOW_FAILED_FORM,
                Message.TITLE_LAUNCHED_WORKFLOW_FAILED + "\n" + msg,
                Icon.ERROR)
        self.refreshRuns()

    @staticmethod
    def _launchSubWorkflow(protocol, mode, root, askSingleAll=False):
        """
        Method to launch a subworkflow
        mode: mode value (RESTART, CONTINUE)
        askSingleAll: specify if this method was launched from the form or from the menu
        """
        project = protocol.getProject()
        workflowProtocolList, activeProtList = project._getSubworkflow(protocol)

        # Check if exists active protocols
        activeProtocols = ""
        if activeProtList:
            for protId, activeProt in activeProtList.items():
                activeProtocols += ("\n* " + activeProt.getRunName())

        # by default, we assume RESTART workflow option
        title = Message.TITLE_RESTART_WORKFLOW_FORM
        message = Message.MESSAGE_RESTART_WORKFLOW_WITH_RESULTS % ('%s\n' % activeProtocols) if len(activeProtList) else Message.MESSAGE_RESTART_WORKFLOW

        if mode == pwprot.MODE_RESUME:
             message = Message.MESSAGE_CONTINUE_WORKFLOW_WITH_RESULTS % ('%s\n' % activeProtocols) if len(activeProtList) else Message.MESSAGE_CONTINUE_WORKFLOW
             title = Message.TITLE_CONTINUE_WORKFLOW_FORM

        if not askSingleAll:
            if pwgui.dialog.askYesNo(title,  message, root):
                project.launchWorkflow(workflowProtocolList, mode)
                return [], RESULT_RUN_ALL
            return [], RESULT_CANCEL
        else:  # launching from a form
            if len(workflowProtocolList) > 1:
                title = Message.TITLE_RESTART_FORM if mode == pwprot.MODE_RESTART else Message.TITLE_CONTINUE_FORM
                message += Message.MESSAGE_ASK_SINGLE_ALL
                result = pwgui.dialog.askSingleAllCancel(title, message,
                                                         root)
                if result == RESULT_RUN_ALL:
                    if mode == pwprot.MODE_RESTART:
                        project._restartWorkflow(workflowProtocolList)
                    else:
                        project._continueWorkflow(workflowProtocolList)

                    return [], RESULT_RUN_ALL

                elif result == RESULT_RUN_SINGLE:
                    errorList = project.resetWorkFlow(workflowProtocolList)
                    return errorList, RESULT_RUN_SINGLE

                elif result == RESULT_CANCEL:
                    return [], RESULT_CANCEL

            else:  # is a single protocol
                if not protocol.isSaved():
                    title = Message.TITLE_RESTART_FORM
                    message = Message.MESSAGE_RESTART_FORM % ('%s\n' % protocol.getRunName())
                    if mode == pwprot.MODE_RESUME:
                        title = Message.TITLE_CONTINUE_FORM
                        message = Message.MESSAGE_CONTINUE_FORM % ('%s\n' % protocol.getRunName())

                    result = pwgui.dialog.askYesNo(title,  message,  root)
                    resultRun = RESULT_RUN_SINGLE if result else RESULT_CANCEL
                    return [], resultRun

                return [], RESULT_RUN_SINGLE

    def _selectLabels(self):
        selectedNodes = self._getSelectedNodes()

        if selectedNodes:
            dlg = self.windows.manageLabels()

            if dlg.resultYes():
                for node in selectedNodes:
                    node.setLabels([label.getName() for label in dlg.values])

                # self.updateRunsGraph()
                self.drawRunsGraph()

    def _selectAncestors(self):
        self._selectNodes(down=False)

    def _selectDescendants(self):
        self._selectNodes(down=True)

    def _selectNodes(self, down=True, fromRun=None):
        """ Selects all nodes in the specified direction, defaults to down."""
        nodesToSelect = []
        # If parent param not passed...
        if fromRun is None:
            # ..use selection, must be first call
            for protId in self._selection:
                run = self.runsGraph.getNode(str(protId))
                nodesToSelect.append(run)
        else:
            name = fromRun.getName()

            if not name.isdigit():
                return
            else:
                name = int(name)

            # If already selected (may be this should be centralized)
            if name not in self._selection:
                nodesToSelect = (fromRun,)
                self._selection.append(name)

        # Go in the direction .
        for run in nodesToSelect:
            # Choose the direction: down or up.
            direction = run.getChilds if down else run.getParents

            # Select himself plus ancestors
            for parent in direction():
                self._selectNodes(down, parent)

        # Only update selection at the end, avoid recursion
        if fromRun is None:
            self._lastSelectedProtId = None
            self._updateSelection()
            self.drawRunsGraph()


    def _exportProtocols(self, defaultPath=None, defaultBasename=None):
        protocols = self._getSelectedProtocols()

        def _export(obj):
            filename = os.path.join(browser.getCurrentDir(),
                                    browser.getEntryValue())
            try:
                if (not os.path.exists(filename) or
                    self.windows.askYesNo("File already exists",
                                          "*%s* already exists, do you want "
                                          "to overwrite it?" % filename)):
                    self.project.exportProtocols(protocols, filename)
                    logger.info("Workflow successfully saved to '%s' "
                                          % filename)
                else:  # try again
                    self._exportProtocols(defaultPath=browser.getCurrentDir(),
                                          defaultBasename=browser.getEntryValue())
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self.windows.showError(str(ex))

        browser = pwgui.browser.FileBrowserWindow(
            "Choose .json file to save workflow",
            master=self.windows,
            path=defaultPath or self.project.getPath(''),
            onSelect=_export,
            entryLabel='File  ', entryValue=defaultBasename or 'workflow.json')
        browser.show()

    def _exportUploadProtocols(self):
        try:
            jsonFn = os.path.join(tempfile.mkdtemp(), 'workflow.json')
            self.project.exportProtocols(self._getSelectedProtocols(), jsonFn)
            WorkflowRepository().upload(jsonFn)
            pwutils.cleanPath(jsonFn)
        except Exception as ex:
            self.windows.showError("Error connecting to workflow repository:\n"
                                   + str(ex))

    def _stopProtocol(self, prot):
        if pwgui.dialog.askYesNo(Message.TITLE_STOP_FORM,
                                 Message.LABEL_STOP_FORM, self.root):
            self.project.stopProtocol(prot)
            self._lastStatus = None  # force logs to re-load
            self._scheduleRunsUpdate()

    def _analyzeResults(self, prot):
        viewers = self.domain.findViewers(prot.getClassName(), DESKTOP_TKINTER)
        if len(viewers):
            # Instantiate the first available viewer
            # TODO: If there are more than one viewer we should display
            # TODO: a selection menu
            firstViewer = viewers[0](project=self.project, protocol=prot,
                                     parent=self.windows)

            if isinstance(firstViewer, ProtocolViewer):
                firstViewer.visualize(prot, windows=self.windows)
            else:
                firstViewer.visualize(prot)
        else:
            outputList = []
            for _, output in prot.iterOutputAttributes():
                outputList.append(output)

            for output in outputList:
                viewers = self.domain.findViewers(output.getClassName(), DESKTOP_TKINTER)
                if len(viewers):
                    # Instantiate the first available viewer
                    # TODO: If there are more than one viewer we should display
                    # TODO: a selection menu
                    viewerclass = viewers[0]
                    firstViewer = viewerclass(project=self.project,
                                              protocol=prot,
                                              parent=self.windows)
                    # FIXME:Probably o longer needed protocol on args, already provided on init
                    firstViewer.visualize(output, windows=self.windows,
                                          protocol=prot)

    def _analyzeResultsClicked(self, e=None):
        """ Function called when button "Analyze results" is called. """
        prot = self.getSelectedProtocol()

        # Nothing selected
        if prot is None:
            return

        if os.path.exists(prot._getPath()):
            self._analyzeResults(prot)
        else:
            self.windows.showInfo("Selected protocol hasn't been run yet.")

    def _bibExportClicked(self, e=None):
        try:
            bibTexCites = OrderedDict()
            for prot in self._iterSelectedProtocols():
                bibTexCites.update(prot.getCitations(bibTexOutput=True))
                bibTexCites.update(prot.getPackageCitations(bibTexOutput=True))

            if bibTexCites:
                with tempfile.NamedTemporaryFile(suffix='.bib') as bibFile:
                    for refId, refDict in bibTexCites.items():
                        # getCitations does not always return a dictionary
                        # if the citation is not found in the bibtex file it adds just
                        # the refId: like "Ramirez-Aportela-2019"
                        # we need to exclude this
                        if isinstance(refDict, dict):
                            refType = refDict['ENTRYTYPE']
                            # remove 'type' and 'id' keys
                            refDict = {k: v for k, v in refDict.items()
                                       if k not in ['ENTRYTYPE', 'ID']}
                            jsonStr = json.dumps(refDict, indent=4,
                                                 ensure_ascii=False)[1:]
                            jsonStr = jsonStr.replace('": "', '"= "')
                            jsonStr = re.sub('(?<!= )"(\S*?)"', '\\1', jsonStr)
                            jsonStr = jsonStr.replace('= "', ' = "')
                            refStr = '@%s{%s,%s\n\n' % (refType, refId, jsonStr)
                            bibFile.write(refStr.encode('utf-8'))
                        else:
                            print("WARNING: reference %s not properly defined or unpublished." % refId)
                    # flush so we can see content when opening
                    bibFile.flush()
                    pwgui.text.openTextFileEditor(bibFile.name)

        except Exception as ex:
            self.windows.showError(str(ex))

        return

    def _renameProtocol(self, prot):
        """ Open the EditObject dialog to edit the protocol name. """
        kwargs = {}
        if self._lastRightClickPos:
            kwargs['position'] = self._lastRightClickPos

        dlg = pwgui.dialog.EditObjectDialog(self.runsGraphCanvas, Message.TITLE_EDIT_OBJECT,
                                            prot, self.project.mapper, **kwargs)
        if dlg.resultYes():
            self._updateProtocol(prot)

    def _runActionClicked(self, action, event=None):

        if event is not None:
            # log Search box events are reaching here
            # Since this method is bound to the window events
            if event.widget.widgetName == 'entry':
                return

        # Following actions do not need a select run
        if action == ACTION_TREE:
            self.drawRunsGraph(reorganize=True)
        elif action == ACTION_REFRESH:
            self.refreshRuns(checkPids=True)
        elif action == ACTION_PASTE:
            self._pasteProtocolsFromClipboard()

        elif action == ACTION_SWITCH_VIEW:
            self.switchRunsView()
        else:
            prot = self.getSelectedProtocol()
            if prot:
                try:
                    if action == ACTION_DEFAULT:
                        pass
                    elif action == ACTION_EDIT:
                        self._editProtocol(prot)
                    elif action == ACTION_RENAME:
                        self._renameProtocol(prot)
                    elif action == ACTION_DUPLICATE:
                        self._copyProtocols()
                    elif action == ACTION_COPY:
                        self._copyProtocolsToClipboard()
                    elif action == ACTION_DELETE:
                        self._deleteProtocol()
                    elif action == ACTION_STEPS:
                        self._browseSteps()
                    elif action == ACTION_BROWSE:
                        self._browseRunDirectory()
                    elif action == ACTION_DB:
                        self._browseRunData()
                    elif action == ACTION_STOP:
                        self._stopProtocol(prot)
                    elif action == ACTION_CONTINUE:
                        self._continueProtocol(prot)
                    elif action == ACTION_RESULTS:
                        self._analyzeResults(prot)
                    elif action == ACTION_EXPORT:
                        self._exportProtocols(defaultPath=pwutils.getHomePath())
                    elif action == ACTION_EXPORT_UPLOAD:
                        self._exportUploadProtocols()
                    elif action == ACTION_COLLAPSE:
                        node = self.runsGraph.getNode(str(prot.getObjId()))
                        nodeInfo = self.settings.getNodeById(prot.getObjId())
                        nodeInfo.setExpanded(False)
                        self.setVisibleNodes(node, visible=False)
                        self.updateRunsGraph(True)
                        self._updateActionToolbar()
                    elif action == ACTION_EXPAND:
                        node = self.runsGraph.getNode(str(prot.getObjId()))
                        nodeInfo = self.settings.getNodeById(prot.getObjId())
                        nodeInfo.setExpanded(True)
                        self.setVisibleNodes(node, visible=True)
                        self.updateRunsGraph(True)
                        self._updateActionToolbar()
                    elif action == ACTION_LABELS:
                        self._selectLabels()
                    elif action == ACTION_SELECT_FROM:
                        self._selectDescendants()
                    elif action == ACTION_SELECT_TO:
                        self._selectAncestors()
                    elif action == ACTION_RESTART_WORKFLOW:
                        self._launchWorkFlow(action)
                    elif action == ACTION_CONTINUE_WORKFLOW:
                        self._launchWorkFlow(action)
                    elif action == ACTION_STOP_WORKFLOW:
                        self._stopWorkFlow(action)
                    elif action == ACTION_RESET_WORKFLOW:
                        self._resetWorkFlow(action)
                    elif action == ACTION_SEARCH:
                        self._searchProtocol()

                except Exception as ex:
                    self.windows.showError(str(ex))
                    if Config.debugOn():
                        import traceback
                        traceback.print_exc()
            else:
                self.info("Action '%s' not implemented." % action)

    def setVisibleNodes(self, node, visible=True):
        hasParentHidden = False
        for child in node.getChilds():
            prot = child.run
            nodeInfo = self.settings.getNodeById(prot.getObjId())
            if visible:
                hasParentHidden = self.hasParentHidden(child)
            if not hasParentHidden:
                nodeInfo.setVisible(visible)
                self.setVisibleNodes(child, visible)

    def hasParentHidden(self, node):
        for parent in node.getParents():
            prot = parent.run
            nodeInfo = self.settings.getNodeById(prot.getObjId())
            if not nodeInfo.isVisible() or not nodeInfo.isExpanded():
                return True
        return False


class RunBox(pwgui.TextBox):
    """ Just override TextBox move method to keep track of 
    position changes in the graph.
    """

    def __init__(self, nodeInfo, canvas, text, x, y, bgColor, textColor):
        pwgui.TextBox.__init__(self, canvas, text, x, y, bgColor, textColor)
        self.nodeInfo = nodeInfo
        canvas.addItem(self)

    def move(self, dx, dy):
        pwgui.TextBox.move(self, dx, dy)
        self.nodeInfo.setPosition(self.x, self.y)

    def moveTo(self, x, y):
        pwgui.TextBox.moveTo(self, x, y)
        self.nodeInfo.setPosition(self.x, self.y)


