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


import os
import webbrowser
import tkinter as tk

import pyworkflow as pw
from pyworkflow.gui import Window, Message, Color, getBigFont, defineStyle
from pyworkflow.gui.widgets import GradientFrame
from pyworkflow.utils.properties import Icon

from .viewprojects import ProjectsView
from .viewprotocols import ProtocolsView
from .viewdata import ProjectDataView

VIEW_PROJECTS = Message.VIEW_PROJECTS
VIEW_PROTOCOLS = Message.VIEW_PROTOCOLS
VIEW_DATA = Message.VIEW_DATA
VIEW_LIST = [VIEW_PROTOCOLS, VIEW_DATA]


class ProjectBaseWindow(Window):
    """ Base windows for Project and Manager GUIs.
    It extends from Window and add some layout functions (header and footer)
    """
    def __init__(self, title, masterWindow=None, weight=True,
                 minsize=(900, 500), icon=Icon.SCIPION_ICON, **kwargs):
        Window.__init__(self, title, masterWindow, weight=weight, 
                        icon=icon, minsize=minsize, enableQueue=True, **kwargs)
        
        content = tk.Frame(self.root)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        content.grid(row=0, column=0, sticky='news')
        self.content = content

        defineStyle()

        if getattr(self, 'menuCfg', None):
            Window.createMainMenu(self, self.menuCfg)
        
        self.header = self.createHeaderFrame(content)
        self.header.grid(row=0, column=0, sticky='new')
        
        self.footer = tk.Frame(content, bg=pw.Config.SCIPION_BG_COLOR)
        self.footer.grid(row=1, column=0, sticky='news') 
        
        self.view, self.viewWidget = None, None
        
        self.viewFuncs = {VIEW_PROJECTS: ProjectsView,
                          VIEW_PROTOCOLS: ProtocolsView,
                          VIEW_DATA: ProjectDataView,
                          }
        
    def createHeaderFrame(self, parent):
        
        """ Create the Header frame at the top of the windows.
        It has (from left to right):
            - Main application Logo
            - Project Name
            - View selection combobox
        """
        header = tk.Frame(parent, bg=pw.Config.SCIPION_BG_COLOR)
        header.columnconfigure(1, weight=1)
        header.columnconfigure(2, weight=1)
        # Create the SCIPION logo label
        logoImg = self.getImage(self.generalCfg.logo.get())
        logoLabel = tk.Label(header, image=logoImg, 
                             borderwidth=0, anchor='nw', bg=pw.Config.SCIPION_BG_COLOR)
        logoLabel.grid(row=0, column=0, sticky='nw', padx=(5, 0), pady=5)
        version = "%s - %s (core)" % (os.environ.get('SCIPION_VERSION', ""), pw.LAST_VERSION)

        versionLabel = tk.Label(header, text=version,
                                bg=pw.Config.SCIPION_BG_COLOR)
        versionLabel.grid(row=0, column=1, sticky='sw', pady=20)
        
        # Create the Project Name label
        projName = getattr(self, 'projName', '')
        projLabel = tk.Label(header, text=projName, font=getBigFont(),
                             borderwidth=0, anchor='nw', bg=pw.Config.SCIPION_BG_COLOR,
                             fg=Color.ALT_COLOR_DARK)
        projLabel.grid(row=0, column=2, sticky='sw', padx=(20, 5), pady=10)
        # Create gradient
        GradientFrame(header, height=8, borderwidth=0).grid(row=1, column=0,
                                                            columnspan=3,
                                                            sticky='new')
        return header

    def addViewList(self, header):
        """Create the view selection frame (Protocols|Data) in the header.
        """
        # This function is called from createHeaderFrame() in ProjectWindow
        viewFrame = tk.Frame(header, bg=pw.Config.SCIPION_BG_COLOR)
        viewFrame.grid(row=0, column=2, sticky='se', padx=5, pady=10)

        def addLink(elementText):
            btn = tk.Label(viewFrame, text=elementText, cursor='hand2',
                           fg=pw.Config.SCIPION_MAIN_COLOR, bg=pw.Config.SCIPION_BG_COLOR)
            btn.bind('<Button-1>', lambda e: self._viewComboSelected(elementText))
            return btn
        
        def addTube():        
            return tk.Label(viewFrame, text="|", fg=pw.Config.SCIPION_MAIN_COLOR, bg=pw.Config.SCIPION_BG_COLOR, padx=5)

        for i, elementText in enumerate(VIEW_LIST):
            btn = addLink(elementText)
            btn.grid(row=0, column=i*2)
            
            if i < len(VIEW_LIST)-1:
                tube = addTube()
                tube.grid(row=0, column=(i*2)+1)
    
    def _viewComboSelected(self, elementText):
        if elementText != self.view:
            self.switchView(elementText)

    def switchView(self, newView):
        # Destroy the previous view if exists:
        if self.viewWidget:
            self.viewWidget.grid_forget()
            self.viewWidget.destroy()
        # Create the new view
        self.viewWidget = self.viewFuncs[newView](self.footer, self)
        # Grid in the second row (1)
        self.viewWidget.grid(row=0, column=0, columnspan=10, sticky='news')
        self.footer.rowconfigure(0, weight=1)
        self.footer.columnconfigure(0, weight=1)
        self.view = newView
        
    def getViewWidget(self):
        return self.viewWidget
    #
    # The next functions are callbacks from the menu options.
    # See how it is done in pyworkflow/gui/gui.py:Window._addMenuChilds()

    def onExit(self):
        # Project -> Exit
        self._onClosing()

    def onOnlineHelp(self):
        # Help -> Online help
        webbrowser.open_new("https://scipion-em.github.io/docs/")

    def onAbout(self):
        # Help -> About
        self.showInfo(
            "[[http://scipion.i2pc.es/][Scipion]] is an image processing "
            "framework to obtain 3D models of macromolecular complexes using "
            "Electron Microscopy.\n\n"
            "It integrates several software packages with a unified interface. "
            "This way you can combine them in a single workflow, while all the "
            "formats and conversions are taken care of automatically.\n\n"
            "*Scipion* is developed by a multidisciplinary group of engineers, "
            "physicists, mathematicians, biologists and computer scientists. "
            "It is produced mainly by people at the "
            "[[http://biocomputingunit.es//][CNB Biocomputing Unit]], "
            "[[https://www.scilifelab.se/][SciLifeLab]] and "
            "[[https://www2.mrc-lmb.cam.ac.uk/][MRC LMB]], "
            "but with many contributions across the globe.")

    def onContactSupport(self):
        # Help -> Contact support
        email = pw.Config.SCIPION_SUPPORT_EMAIL
        self.showInfo("Please, do contact us at [[mailto:%s][%s]] for any "
                      "feedback, bug, idea, anything that will make Scipion "
                      "better.""" % (email, email))
