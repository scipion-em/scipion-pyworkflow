#!/usr/bin/env python
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
"""
Main Project window implementation.
It is composed by three panels:
1. Left: protocol tree.
2. Right upper: VIEWS (Data/Protocols)
3. Summary/Details
"""

import logging
from tkinter import Label

from .. import askString

logger = logging.getLogger(__name__)

import os
import threading
import shlex
import subprocess
import socketserver

import pyworkflow as pw
import pyworkflow.utils as pwutils
from pyworkflow.gui.project.utils import OS
from pyworkflow.project import MenuConfig
from pyworkflow.gui import Message, Icon, getBigFont, ToolTip
from pyworkflow.gui.browser import FileBrowserWindow

from pyworkflow.gui.plotter import Plotter
from pyworkflow.gui.text import _open_cmd, openTextFileEditor
from pyworkflow.webservices import ProjectWorkflowNotifier, WorkflowRepository

from .labels import LabelsDialog
# Import possible Object commands to be handled
from .base import ProjectBaseWindow, VIEW_PROTOCOLS, VIEW_PROJECTS


class ProjectWindow(ProjectBaseWindow):
    """ Main window for working in a Project. """
    _OBJECT_COMMANDS = {}

    def __init__(self, path, master=None):
        # Load global configuration
        self.projPath = path
        self.project = self.loadProject()
        self.projName = self.project.getShortName()

        try:
            projTitle = '%s (%s on %s)' % (self.projName,
                                           pwutils.getLocalUserName(),
                                           pwutils.getLocalHostName())
        except Exception:
            projTitle = self.projName 


        # TODO: put the menu part more nicely. From here:
        menu = MenuConfig()

        projMenu = menu.addSubMenu('Project')
        projMenu.addSubMenu('Browse files', 'browse',
                            icon=Icon.FOLDER_OPEN)
        projMenu.addSubMenu('Remove temporary files', 'delete',
                            icon=Icon.ACTION_DELETE)
        projMenu.addSubMenu('Toggle color mode', 'color_mode',
                            shortCut="Ctrl+t", icon=Icon.ACTION_VISUALIZE)
        projMenu.addSubMenu('Select all protocols', 'select all',
                            shortCut="Ctrl+a", icon=Icon.SELECT_ALL)
        projMenu.addSubMenu('Locate a protocol', 'locate protocol',
                            shortCut="Ctrl+l")
        projMenu.addSubMenu('', '')  # add separator
        projMenu.addSubMenu('Import workflow', 'load_workflow',
                            icon=Icon.DOWNLOAD)
        projMenu.addSubMenu('Search workflow', 'search_workflow',
                            icon=Icon.ACTION_SEARCH)

        projMenu.addSubMenu('Configuration', 'configuration',
                            icon=Icon.SETTINGS)

        projMenu.addSubMenu('', '')  # add separator
        projMenu.addSubMenu('Debug Mode', 'debug mode',
                            shortCut="Ctrl+D", icon=Icon.DEBUG)
        projMenu.addSubMenu('', '')  # add separator
        projMenu.addSubMenu('Notes', 'notes', icon=Icon.ACTION_EDIT)
        projMenu.addSubMenu('', '')  # add separator
        projMenu.addSubMenu('Exit', 'exit', icon=Icon.ACTION_OUT)

        helpMenu = menu.addSubMenu('Help')
        helpMenu.addSubMenu('Online help', 'online_help',
                            icon=Icon.ACTION_EXPORT)
        helpMenu.addSubMenu('About', 'about',
                            icon=Icon.ACTION_HELP)
        helpMenu.addSubMenu('Contact support', 'contact_us',
                            icon=Icon.ACTION_HELP)

        self.menuCfg = menu

        if self.project.openedAsReadOnly():
            self.projName += "<READ ONLY>"

        # Notify about the workflow in this project
        self.selectedProtocol = None
        self.showGraph = False
        self.commentTT = None  # Tooltip to store the project description

        Plotter.setBackend('TkAgg')
        ProjectBaseWindow.__init__(self, projTitle, master,
                                   minsize=(90, 50), icon=Icon.SCIPION_ICON_PROJ, _class=self.projName)

        OS.handler().maximizeWindow(self.root)

        self.switchView(VIEW_PROTOCOLS)

        self.initProjectTCPServer()  # Socket thread to communicate with clients

        ProjectWorkflowNotifier(self.project).notifyWorkflow()


    def createHeaderFrame(self, parent):
        """Create the header and add the view selection frame at the right."""
        header = ProjectBaseWindow.createHeaderFrame(self, parent)
        self.addViewList(header)
        return header

    def customizeheader(self, headerFrame):
        """ Adds the Project name in the header frame"""
        # Create the Project Name label

        projLabel = Label(headerFrame, text=self.projName, font=getBigFont(),
                             borderwidth=0, anchor='nw', bg=pw.Config.SCIPION_BG_COLOR,
                             fg=pw.Color.ALT_COLOR_DARK)
        projLabel.bind("<Button-1>", self.setComment)
        projLabel.grid(row=0, column=2, sticky='sw', padx=(20, 5), pady=10)

        self.commentTT = ToolTip(projLabel, self.project.getComment(), 200)
    def setComment(self, e):

        newComment = askString("Change project description", "Description", self.root, entryWidth=100, defaultValue=self.project.getComment())
        self.commentTT.configure(text=newComment)
        self.project.setComment(newComment)
        self.project._storeCreationTime()  # Comment is stored as creation time comment for now
    def getSettings(self):
        return self.settings
    
    def saveSettings(self):

        try:
            self.settings.write()
        except Exception as ex:
            logger.error(Message.NO_SAVE_SETTINGS, exc_info=ex)

    def _onClosing(self):
        if not self.project.openedAsReadOnly():
            self.saveSettings()

        ProjectBaseWindow._onClosing(self)
     
    def loadProject(self):
        proj = pw.project.Project(pw.Config.getDomain(), self.projPath)
        proj.configureLogging()
        proj.load()

        # Check if we have settings.sqlite, generate if not
        settingsPath = os.path.join(proj.path, proj.settingsPath)
        if os.path.exists(settingsPath):
            self.settings = proj.getSettings()
        else:
            logger.info('Warning: settings.sqlite not found! '
                  'Creating default settings..')
            self.settings = proj.createSettings()

        return proj

    # The next functions are callbacks from the menu options.
    # See how it is done in pyworkflow/gui/gui.py:Window._addMenuChilds()
    #
    def onBrowseFiles(self):
        # Project -> Browse files
        FileBrowserWindow("Browse Project files",
                          self, self.project.getPath(''), 
                          selectButton=None  # we will select nothing
                          ).show()

    def onDebugMode(self):
        pw.Config.toggleDebug()

    def onNotes(self):
        notes_program = pw.Config.SCIPION_NOTES_PROGRAM
        notes_args = pw.Config.SCIPION_NOTES_ARGS
        args = []
        notes_file = self.project.getPath('Logs', pw.Config.SCIPION_NOTES_FILE)

        # If notesFile does not exist, it is created and an explanation/documentation comment is added at the top.
        if not os.path.exists(notes_file):
            f = open(notes_file, 'a')
            f.write(pw.genNotesHeading())
            f.close()

        # Then, it will be opened as specified in the conf
        if notes_program:
            args.append(notes_program)
            # Custom arguments
            if notes_args:
                args.append(notes_args)
            args.append(notes_file)
            subprocess.Popen(args)  # nonblocking
        else:
            # if no program has been selected
            # xdg-open will try to guess but
            # if the file does not exist it
            # will return an error so If the file does
            # not exist I will create an empty one
            # 'a' will avoid accidental truncation
            openTextFileEditor(notes_file)

    def onRemoveTemporaryFiles(self):
        # Project -> Remove temporary files
        tmpPath = os.path.join(self.project.path, self.project.tmpPath)
        n = 0
        try:
            for fname in os.listdir(tmpPath):
                fpath = "%s/%s" % (tmpPath, fname)
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    n += 1
                # TODO: think what to do with directories. Delete? Report?
            self.showInfo("Deleted content of %s -- %d file(s)." % (tmpPath, n))
        except Exception as e:
            self.showError(str(e))
        
    def _loadWorkflow(self, obj):
        try:
            self.getViewWidget().info('Importing workflow %s' % obj.getPath())
            self.project.loadProtocols(obj.getPath())
            self.getViewWidget().updateRunsGraph(True)
            self.getViewWidget().cleanInfo()
        except Exception as ex:
            self.showError(str(ex), exception=ex)
            
    def onImportWorkflow(self):
        FileBrowserWindow("Select workflow .json file",
                          self, self.project.getPath(''),
                          onSelect=self._loadWorkflow,
                          selectButton='Import'
                          ).show()

    def onSearchWorkflow(self):
        WorkflowRepository().search()

    def onToggleColorMode(self):
        self.getViewWidget()._toggleColorScheme(None)

    def onSelectAllProtocols(self):
        self.getViewWidget()._selectAllProtocols(None)

    def onLocateAProtocol(self):
        self.getViewWidget()._locateProtocol(None)

    def manageLabels(self):

        labels = self.project.settings.getLabels()
        dialog = LabelsDialog(self.root,
                            labels,
                            allowSelect=True)

        # Scan for renamed labels to update node info...
        labelsRenamed = dict()
        for label in labels:
            if label.hasOldName():
                oldName = label.getOldName()
                newName = label.getName()
                logger.info("Label %s renamed to %s" % (oldName, newName))
                labelsRenamed[oldName] = newName
                label.clearOldName()

        # If there are labels renamed
        if labelsRenamed:
            logger.info("Updating labels of protocols after renaming.")
            labels.updateDict()

            for node in self.project.settings.getNodes():
                nodeLabels = node.getLabels()
                for index, nodeLabel in enumerate(nodeLabels):

                    newLabel = labelsRenamed.get(nodeLabel, None)
                    if newLabel is not None:
                        logger.info("Label %s found in %s. Updating it to %s" % (nodeLabel,node, newLabel))
                        nodeLabels[index] = newLabel

        return dialog

    def initProjectTCPServer(self):
        server = ProjectTCPServer((self.project.address, self.project.port),
                                  ProjectTCPRequestHandler)
        server.project = self.project
        server.window = self
        server_thread = threading.Thread(name="projectTCPserver", target=server.serve_forever)
        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()

    # Seems it is not used and should be in scipion-em
    # Not within scipion but used from ShowJ
    def schedulePlot(self, path, *args):
        # FIXME: This import should not be here
        from pwem.viewers import EmPlotter
        self.enqueue(lambda: EmPlotter.createFromFile(path, *args).show())

    @classmethod
    def registerObjectCommand(cls, cmd, func):
        """ Register an object command to be handled when receiving the
        action from showj. """
        cls._OBJECT_COMMANDS[cmd] = func

    def runObjectCommand(self, cmd, inputStrId, objStrId):
        try:
            objId = int(objStrId)
            project = self.project

            if os.path.isfile(inputStrId) and os.path.exists(inputStrId):
                from pwem.utils import loadSetFromDb
                inputObj = loadSetFromDb(inputStrId)
            else:
                inputId = int(inputStrId)
                inputObj = project.mapper.selectById(inputId)

            func = self._OBJECT_COMMANDS.get(cmd, None)

            if func is None:
                logger.info("Error, command '%s' not found. " % cmd)
            else:
                def myfunc():
                    func(inputObj, objId)
                    inputObj.close()
                self.enqueue(myfunc)

        except Exception as ex:
            logger.error("There was an error executing object command !!!:", exc_info=ex)

class ProjectManagerWindow(ProjectBaseWindow):
    """ Windows to manage all projects. """
    # To allow plugins to add their own menus
    _pluginMenus = dict()

    def __init__(self, **kwargs):

        # TODO: put the menu part more nicely. From here:
        menu = MenuConfig()

        fileMenu = menu.addSubMenu('File')
        fileMenu.addSubMenu('Browse files', 'browse', icon=Icon.FOLDER_OPEN)
        fileMenu.addSubMenu('Exit', 'exit', icon=Icon.ACTION_OUT)

        confMenu = menu.addSubMenu('Configuration')
        if os.path.exists(pw.Config.SCIPION_CONFIG):
            confMenu.addSubMenu('General', 'general')
        confMenu.addSubMenu('Hosts', 'hosts')
        if os.path.exists(pw.Config.SCIPION_PROTOCOLS):
            confMenu.addSubMenu('Protocols', 'protocols')
        if os.path.exists(pw.Config.SCIPION_LOCAL_CONFIG):
            confMenu.addSubMenu('User', 'user')

        helpMenu = menu.addSubMenu('Help')
        helpMenu.addSubMenu('Online help', 'online_help', icon=Icon.ACTION_EXPORT)
        helpMenu.addSubMenu('About', 'about', icon=Icon.ACTION_HELP)

        self.menuCfg = menu

        try:
            title = '%s (%s on %s)' % (Message.LABEL_PROJECTS, 
                                       pwutils.getLocalUserName(),
                                       pwutils.getLocalHostName())
        except Exception:
            title = Message.LABEL_PROJECTS
        
        ProjectBaseWindow.__init__(self, title, minsize=(750, 500),
                                   icon=Icon.SCIPION_ICON_PROJS, **kwargs)
        self.manager = pw.project.Manager()
        self.switchView(VIEW_PROJECTS)

    #
    # The next functions are callbacks from the menu options.
    # See how it is done in pyworkflow/gui/gui.py:Window._addMenuChilds()
    #
    def onBrowseFiles(self):
        # File -> Browse files
        FileBrowserWindow("Browse files", self,
                          pw.Config.SCIPION_USER_DATA,
                          selectButton=None).show()

    def onGeneral(self):
        # Config -> General
        self._openConfigFile(pw.Config.SCIPION_CONFIG)

    @staticmethod
    def _openConfigFile(configFile):
        """ Open an Scipion configuration file, if the user have one defined,
        also open that one with the defined text editor.
        """
        _open_cmd(configFile)

    @staticmethod
    def onHosts():
        # Config -> Hosts
        ProjectManagerWindow._openConfigFile(pw.Config.SCIPION_HOSTS)

    @staticmethod
    def onProtocols():
        ProjectManagerWindow._openConfigFile(pw.Config.SCIPION_PROTOCOLS)

    @staticmethod
    def onUser():
        ProjectManagerWindow._openConfigFile(pw.Config.SCIPION_LOCAL_CONFIG)


class ProjectTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class ProjectTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        try:
            project = self.server.project
            window = self.server.window
            msg = self.request.recv(1024)
            msg = msg.decode()
            tokens = shlex.split(msg)
            if msg.startswith('run protocol'):
                
                logger.debug("run protocol messaged arrived: %s" % msg)
                protocolName = tokens[2]
                protocolClass = pw.Config.getDomain().getProtocols()[protocolName]
                # Create the new protocol instance and set the input values
                protocol = project.newProtocol(protocolClass)

                for token in tokens[3:]:
                    param, value = token.split('=')
                    attr = getattr(protocol, param, None)
                    if param == 'label':
                        protocol.setObjLabel(value)
                    elif attr.isPointer():
                        obj = project.getObject(int(value))
                        attr.set(obj)
                    elif value:
                        attr.set(value)

                if protocol.useQueue():
                    # Do not use the queue in this case otherwise we need to ask for queue parameters.
                    # Maybe something to do in the future. But now this logic is in form.py.
                    logger.warning('Cancelling launching protocol "%s" to the queue.' % protocol)
                    protocol._useQueue.set(False)

                # project.launchProtocol(protocol)
                # We need to enqueue the action of execute a new protocol
                # to be run in the same GUI thread and avoid concurrent
                # access to the project sqlite database
                window.getViewWidget().executeProtocol(protocol)
            elif msg.startswith('run function'):
                functionName = tokens[2]
                functionPointer = getattr(window, functionName)
                functionPointer(*tokens[3:])
            else:
                answer = b'no answer available\n'
                self.request.sendall(answer)
        except Exception as e:
            print(e)
            import traceback
            traceback.print_stack()
