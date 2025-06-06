# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es) [1]
# *              Jose Gutierrez (jose.gutierrez@cnb.csic.es) [2]
# *
# * [1] SciLifeLab, Stockholm University
# * [2] Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
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
In this module a simple ObjectBrowser is implemented.
This class can be subclasses to extend its functionality.
A concrete use of ObjectBrowser is FileBrowser, where the
elements to inspect and preview are files.
"""
import os.path
import stat
import tkinter as tk
import time
import logging

logger = logging.getLogger(__name__)

import pyworkflow.utils as pwutils
from . import gui, LIST_TREEVIEW
from .tree import BoundTree, TreeProvider
from .text import TaggedText, openTextFileEditor
from .widgets import Button, HotButton
from .. import Config

PARENT_FOLDER = ".."


class ObjectBrowser(tk.Frame):
    """ This class will implement a simple object browser.
    Basically, it will display a list of elements at the left
    panel and can display a preview and description on the
    right panel for the selected element.
    An ObjectView will be used to grab information for
    each element such as: icon, preview and description.
    A TreeProvider will be used to populate the list (Tree).
    """

    def __init__(self, parent, treeProvider,
                 showPreview=True, showPreviewTop=True,
                 **args):
        tk.Frame.__init__(self, parent, **args)
        self.treeProvider = treeProvider
        self._lastSelected = None
        gui.configureWeigths(self)
        self.showPreviewTop = showPreviewTop
        # The main layout will be two panes, 
        # At the left containing the elements list
        # and the right containing the preview and description
        p = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        p.grid(row=0, column=0, sticky='news')

        leftPanel = tk.Frame(p)
        self._fillLeftPanel(leftPanel)
        p.add(leftPanel, padx=5, pady=5)
        p.paneconfig(leftPanel, minsize=300)

        if showPreview:
            rightPanel = tk.Frame(p)
            self._fillRightPanel(rightPanel)
            p.add(rightPanel, padx=5, pady=5)
            p.paneconfig(rightPanel, minsize=200)

            # Register a callback when the item is clicked
            self.tree.itemClick = self._itemClicked

    def _fillLeftPanel(self, frame):
        gui.configureWeigths(frame)
        self.tree = BoundTree(frame, self.treeProvider, style=LIST_TREEVIEW)
        self.tree.grid(row=0, column=0, sticky='news')
        self.itemConfig = self.tree.itemConfig
        self.getImage = self.tree.getImage

    def _fillRightPanel(self, frame):
        frame.columnconfigure(0, weight=1)

        if self.showPreviewTop:
            top = tk.Frame(frame)
            top.grid(row=0, column=0, sticky='news')
            frame.rowconfigure(0, weight=3)
            gui.configureWeigths(top)
            top.rowconfigure(0, minsize=200)
            self._fillRightTop(top)

        bottom = tk.Frame(frame)
        bottom.grid(row=1, column=0, sticky='news')
        frame.rowconfigure(1, weight=1)
        gui.configureWeigths(bottom)
        bottom.rowconfigure(1, weight=1)
        self._fillRightBottom(bottom)

    def _fillRightTop(self, top):
        self.noImage = self.getImage(pwutils.Icon.NO_IMAGE_128)
        self.label = tk.Label(top, image=self.noImage)
        self.label.grid(row=0, column=0, sticky='news')

    def _fillRightBottom(self, bottom):
        self.text = TaggedText(bottom, width=40, height=15, bg=Config.SCIPION_BG_COLOR,
                               takefocus=0)
        self.text.grid(row=0, column=0, sticky='news')

    def _itemClicked(self, obj):
        self._lastSelected = obj
        img, desc = self.treeProvider.getObjectPreview(obj)
        # Update image preview
        if self.showPreviewTop:
            if isinstance(img, (str, pwutils.SpriteImage)):
                img = self.getImage(img)
            if img is None:
                img = self.noImage
            self.label.config(image=img)

        # Update text preview
        self.text.setReadOnly(False)
        self.text.clear()

        if desc is not None:
            self.text.addText(desc)
        self.text.setReadOnly(True)
        if hasattr(self, 'entryLabel') and not self._lastSelected.isDir():
            self.entryVar.set(self._lastSelected.getFileName())

    def getSelected(self):
        """ Return the selected object. """
        return self._lastSelected


# ------------ Classes and Functions related to File browsing --------------

class FileInfo(object):
    """ This class will store some information about a file.
    It will serve to display files items in the Tree.
    """

    def __init__(self, path, filename):
        self._fullpath = os.path.join(path, filename)
        self._filename = filename
        if os.path.exists(self._fullpath):
            self._stat = os.stat(self._fullpath)
        else:
            self._stat = None

    def isDir(self):
        return stat.S_ISDIR(self._stat.st_mode) if self._stat else False

    def getFileName(self):
        return self._filename

    def getPath(self):
        return self._fullpath

    def getSize(self):
        return self._stat.st_size if self._stat else 0

    def getSizeStr(self):
        """ Return a human readable string of the file size."""
        return pwutils.prettySize(self.getSize()) if self._stat else '0'

    def getDateStr(self):
        return pwutils.dateStr(self.getDate()) if self._stat else '0'

    def getDate(self):
        return self._stat.st_mtime if self._stat else 0

    def isLink(self):
        return os.path.islink(self._fullpath)


class FileHandler(object):
    """ This class will be used to get the icon, preview and info
    from the different types of objects.
    It should be used with FileTreeProvider, where different
    types of handlers can be registered.
    """

    def getFileIcon(self, objFile):
        """ Return the icon name for a given file. """
        if objFile.isDir():
            icon = pwutils.Icon.FOLDER if not objFile.isLink() else pwutils.Icon.FOLDER_LINK
        else:
            icon = pwutils.Icon.FILE if not objFile.isLink() else pwutils.Icon.FILE_LINK

        return icon

    def getFilePreview(self, objFile):
        """ Return the preview image and description for the specific object."""
        if objFile.isDir():
            return pwutils.Icon.FOLDER_OPEN, None
        return None, None

    def getFileActions(self, objFile):
        """ Return actions that can be done with this object.
        Actions will be displayed in the context menu 
        and the first one will be the default when double-click.
        """
        return []


class FSFileHandler(FileHandler):

    def __init__(self):
        self._refresh_callback = None

    def setRefresh(self, refresh_callback):
        self._refresh_callback = refresh_callback

    def copyToClipboard(self, file):
        import pyperclip
        pyperclip.copy(file)
        logger.info(f'{file} copy to clipboard')

    def deleteFile(self, file):
        pwutils.cleanPath(file)

        if self._refresh_callback:
            self._refresh_callback(None)
    def getFileActions(self, objFile):
        """ Return basic os actions like delete or copy to clipboard
        """
        fn = objFile.getPath()
        return [('Copy path', lambda: self.copyToClipboard(fn), pwutils.Icon.ACTION_COPY),
                ('Delete', lambda: self.deleteFile(fn), pwutils.Icon.DELETE_OPERATION)
                ]


class TextFileHandler(FileHandler):
    def __init__(self, textIcon):
        FileHandler.__init__(self)
        self._icon = textIcon

    def getFileIcon(self, objFile):
        return self._icon


class SqlFileHandler(FileHandler):
    def getFileIcon(self, objFile):
        return pwutils.Icon.DB


class FileTreeProvider(TreeProvider):
    """ Populate a tree with files and folders of a given path """

    _FILE_HANDLERS = {}
    _FS_HANDLER = FSFileHandler()
    FILE_COLUMN = 'File'
    SIZE_COLUMN = 'Size'

    @classmethod
    def registerFileHandler(cls, fileHandler, *extensions):
        """ Register a FileHandler for a given file extension. 
        Params:
            fileHandler: the FileHandler that will take care of extensions.
            *extensions: the extensions list that will be associated to this
                FileHandler.
        """
        for fileExt in extensions:
            handlersList = cls._FILE_HANDLERS.get(fileExt, [])
            handlersList.append(fileHandler)
            cls._FILE_HANDLERS[fileExt] = handlersList

    def __init__(self, currentDir, showHidden, onlyFolders, browser):
        TreeProvider.__init__(self, sortingColumnName=self.FILE_COLUMN)
        self._currentDir = os.path.abspath(currentDir)
        self._showHidden = showHidden
        self._onlyFolders = onlyFolders
        self._browser = browser
        self.getColumns = lambda: [(self.FILE_COLUMN, 300),
                                   (self.SIZE_COLUMN, 70), ('Time', 150)]

    def getFileHandlers(self, obj):
        filename = obj.getFileName()
        fileExt = pwutils.getExt(filename)
        fhs = self._FILE_HANDLERS.get(fileExt,[])
        # add basic options: delete, copy. They do not depend on the extension.
        if self._FS_HANDLER not in fhs:
            fhs.append(self._FS_HANDLER)
        return fhs

    def getObjectInfo(self, obj):
        filename = obj.getFileName()
        fileHandlers = self.getFileHandlers(obj)
        icon = fileHandlers[0].getFileIcon(obj)

        info = {'key': filename, 'text': filename,
                'values': (obj.getSizeStr(), obj.getDateStr()), 'image': icon
                }

        return info

    def getObjectPreview(self, obj):

        try:
            # Look for any preview available
            fileHandlers = self.getFileHandlers(obj)

            for fileHandler in fileHandlers:
                preview = fileHandler.getFilePreview(obj)
                if preview:
                    img, desc = preview
                    if obj.isLink():
                        desc = "Is a link" if desc is None else desc + "\nIs a link."
                    return img, desc

        except Exception as e:
            msg = "Couldn't get preview for %s" % obj
            logger.error(msg, exc_info=e)
            return None, msg + " See scipion GUI log window for more details."

    def getObjectActions(self, obj):
        fileHandlers = self.getFileHandlers(obj)
        actions = []
        for fileHandler in fileHandlers:
            if fileHandler == self._FS_HANDLER:
                fileHandler.setRefresh(self._browser._actionRefresh)
            actions += fileHandler.getFileActions(obj)
        # Always allow the option to open as text
        # specially useful for unknown formats
        fn = obj.getPath()
        actions.append(("Open external program",
                        lambda: openTextFileEditor(fn), pwutils.Icon.ACTION_REFERENCES))

        return actions

    def getObjects(self):

        fileInfoList = []
        if not self._currentDir == pwutils.ROOT:
            fileInfoList.append(FileInfo(self._currentDir, PARENT_FOLDER))

        try:
            # This might fail if there is not granted
            files = os.listdir(self._currentDir)

            for f in files:

                fullPath = os.path.join(self._currentDir, f)
                # If f is a file and only need folders
                if self._onlyFolders and not os.path.isdir(fullPath):
                    continue

                # Do not add hidden files if not requested
                if not self._showHidden and f.startswith('.'):
                    continue

                # All ok...add item.
                fileInfoList.append(FileInfo(self._currentDir, f))
        except Exception as e:
            logger.info("Can't list files at " + self._currentDir, e)

        # Sort objects
        fileInfoList.sort(key=self.fileKey, reverse=not self.isSortingAscending())

        return fileInfoList

    def fileKey(self, f):
        sortDict = {self.FILE_COLUMN: 'getFileName',
                    self.SIZE_COLUMN: 'getSize'}
        return getattr(f, sortDict.get(self._sortingColumnName, 'getDate'))()

    def getDir(self):
        return self._currentDir

    def setDir(self, newPath):
        self._currentDir = newPath


# Some constants for the type of selection
# when the file browser is opened

SELECT_NONE = 0  # No selection, just browse files
SELECT_FILE = 1
SELECT_FOLDER = 2
SELECT_PATH = 3  # Can be either file or folder


class FileBrowser(ObjectBrowser):
    """ The FileBrowser is a particular class of ObjectBrowser (Tk.Frame)
    where the "objects" are just files and directories.
    """

    _lastSelectedFile = None
    "Class scope attribute to keep the lastSelected file"

    _fileSelectedAtLoading = None
    "Class scope attribute to offer *Recent* shortcut"

    def __init__(self, parent, initialDir='.',
                 selectionType=SELECT_FILE,
                 selectionSingle=True,
                 allowFilter=True,
                 filterFunction=None,
                 previewDim=144,
                 showHidden=False,  # Show hidden files or not?
                 selectButton='Select',  # Change the Select button text
                 entryLabel=None,  # Display an entry for some input
                 entryValue='',  # Display a value in the entry field
                 showInfo=None,  # Used to notify errors or messages
                 shortCuts=None,  # Shortcuts to common locations/paths
                 onlyFolders=False
                 ):
        """

        :param parent: Parent tkinter window.
        :param initialDir: Folder to show when loading the dialog.
        :param selectionType: Any of SELECT_NONE, SELECT_FILE, SELECT_FOLDER, SELECT_PATH.
        :param showHidden: Pass True to show hidden files.
        :param selectButton: text for the select button. Defaults to *Select*.
        :param entryLabel: text for the entry widget. Default None. There will be no entry.
        :param entryValue: default value for the entry. Needs entryLabel.
        :param showInfo: callback to show a string message, otherwise _showInfo will be used.
        :param shortCuts: list of extra :class:`ShortCut`
        :param onlyFolders: Pass True to show only folders.
        """
        self.pathVar = tk.StringVar()
        self.pathVar.set(os.path.abspath(initialDir))
        self.pathEntry = None
        self.previousSearch = None
        self.previousSearchTS = None
        self.shortCuts = shortCuts
        self._provider = FileTreeProvider(initialDir, showHidden, onlyFolders, self)
        self.selectButton = selectButton
        self.entryLabel = entryLabel
        self.entryVar = tk.StringVar()
        self.entryVar.set(entryValue)

        self.showInfo = showInfo or self._showInfo

        ObjectBrowser.__init__(self, parent, self._provider)

        # focuses on the browser in order to allow to move with the keyboard
        self._goDir(os.path.abspath(initialDir))

        buttonsFrame = tk.Frame(self)
        self._fillButtonsFrame(buttonsFrame)
        buttonsFrame.grid(row=1, column=0)

        # Callback to be called "on Select" button key press
        self.onSelect=None

    def _showInfo(self, msg):
        """ Default way (logger.info to console) to show a message with a given info.
        """
        logger.info(msg)

    def _fillLeftPanel(self, frame):
        """ Redefine this method to include a buttons toolbar and
        also include a filter bar at the bottom of the Tree.
        """
        # Tree with files
        frame.columnconfigure(0, weight=1)

        treeFrame = tk.Frame(frame)
        ObjectBrowser._fillLeftPanel(self, treeFrame)
        # Register the double-click event
        self.tree.itemDoubleClick = self._itemDoubleClick
        # Register keypress event
        self.tree.itemKeyPressed = self._itemKeyPressed

        treeRow = 3
        treeFrame.grid(row=treeRow, column=0, sticky='news')
        # Toolbar frame
        toolbarFrame = tk.Frame(frame)
        self._fillToolbar(toolbarFrame)
        toolbarFrame.grid(row=0, column=0, sticky='new')

        pathFrame = tk.Frame(frame)
        pathLabel = tk.Label(pathFrame, text='Path')
        pathLabel.grid(row=0, column=0, padx=0, pady=3)
        pathEntry = tk.Entry(pathFrame, bg='white', width=65,
                             textvariable=self.pathVar, font=gui.getDefaultFont())
        pathEntry.grid(row=0, column=1, sticky='new', pady=3)
        pathEntry.bind("<Return>", self._onEnterPath)
        pathEntry.bind("<KP_Enter>", self._onEnterPath)
        self.pathEntry = pathEntry
        pathFrame.grid(row=1, column=0, sticky='new')

        # Entry frame, could be used for filter
        if self.entryLabel:
            entryFrame = tk.Frame(frame)
            entryFrame.grid(row=2, column=0, sticky='new')
            tk.Label(entryFrame, text=self.entryLabel).grid(row=0, column=0,
                                                            sticky='nw', pady=3)
            tk.Entry(entryFrame,
                     textvariable=self.entryVar,
                     bg=Config.SCIPION_BG_COLOR,
                     width=65,
                     font=gui.getDefaultFont()).grid(row=0, column=1, sticky='nw', pady=3)

        frame.rowconfigure(treeRow, weight=1)

    def _addButton(self, frame, text, image, command):
        btn = tk.Label(frame, text=text, image=self.getImage(image),
                       compound=tk.LEFT, cursor='hand2')
        btn.bind('<Button-1>', command)
        btn.grid(row=0, column=self._col, sticky='nw',
                 padx=(0, 5), pady=5)
        self._col += 1

    def _fillToolbar(self, frame):
        """ Fill the toolbar frame with some buttons. """
        self._col = 0

        self._addButton(frame, 'Refresh', pwutils.Icon.ACTION_REFRESH,
                        self._actionRefresh)
        self._addButton(frame, 'Home', pwutils.Icon.HOME, self._actionHome)
        self._addButton(frame, 'Launch folder', pwutils.Icon.ROCKET,
                        self._actionLaunchFolder)
        self._addButton(frame, 'Working dir', pwutils.Icon.ACTION_BROWSE,
                        self._actionWorkingDir)
        self._addButton(frame, 'Up', pwutils.Icon.ARROW_UP, self._actionUp)

        self._fileSelectedAtLoading = FileBrowser._lastSelectedFile

        if self._fileSelectedAtLoading is not None:
            self._addButton(frame, 'Recent', None, self._actionRecent)

        # Add shortcuts
        self._addShortCuts(frame)

    def _addShortCuts(self, frame):
        """ Add shortcuts if available"""
        if self.shortCuts:
            for shortCut in self.shortCuts:
                self._addButton(frame,
                                shortCut.name,
                                shortCut.icon,
                                lambda e: self._goDir(shortCut.path))

    def _fillButtonsFrame(self, frame):
        """ Add button to the bottom frame if the selectMode
        is distinct from SELECT_NONE.
        """
        Button(frame, "Close", pwutils.Icon.BUTTON_CLOSE,
               command=self._close).grid(row=0, column=0, padx=(0, 5))
        if self.selectButton:
            HotButton(frame, self.selectButton, pwutils.Icon.BUTTON_SELECT,
                      command=self._select).grid(row=0, column=1)

    def _actionRefresh(self, e=None):
        self.tree.update()

    def _goDir(self, newDir):

        newDir = os.path.abspath(newDir)

        # Add a final "/" to the path: abspath is removing it except for "/"
        if not newDir.endswith(os.path.sep):
            newDir += os.path.sep

        self.pathVar.set(newDir)
        self.pathEntry.icursor(len(newDir))
        self.treeProvider.setDir(newDir)
        self.tree.update()
        self.tree.focus_set()

        itemKeyToFocus = PARENT_FOLDER
        if PARENT_FOLDER not in self.tree._objDict:
            itemKeyToFocus = self.tree.get_children()[0]

        # Focusing on a item, but nothing is selected 
        # Current dir remains in _lastSelected
        self._lastSelected = FileInfo(os.path.dirname(newDir),
                                      os.path.basename(newDir))

        FileBrowser._lastSelectedFile = self._lastSelected

        self.tree.focus(itemKeyToFocus)

    def _actionUp(self, e=None):
        parentFolder = pwutils.getParentFolder(self.treeProvider.getDir())
        self._goDir(parentFolder)

    def _actionRecent(self, e=None):
        self._goDir(self._fileSelectedAtLoading.getPath())

    def _actionHome(self, e=None):
        self._goDir(pwutils.getHomePath())

    def _actionRoot(self, e=None):
        self._goDir("/")

    def _actionLaunchFolder(self, e=None):
        self._goDir(Config.SCIPION_CWD)

    def _actionWorkingDir(self, e=None):
        self._goDir(os.getcwd())

    def _itemDoubleClick(self, obj):
        if obj.isDir():
            self._goDir(obj.getPath())
        else:
            actions = self._provider.getObjectActions(obj)
            if actions:
                # actions[0] = first Action, [1] = the action callback
                actions[0][1]()

    def _itemKeyPressed(self, obj, e=None):

        if e.keysym in [pwutils.KEYSYM.RETURN]:
            self._itemDoubleClick(obj)
            return

        textToSearch = self._composeTextToSearch(e.char)

        # locate an item in starting with that letter.
        self._searchItem(textToSearch)

    def _composeTextToSearch(self, newChar):

        currentMiliseconds = time.time()

        if (self.previousSearchTS is not None) and \
                ((currentMiliseconds - self.previousSearchTS) < 0.3):
            newChar = self.previousSearch + newChar

        self.previousSearch = newChar
        self.previousSearchTS = currentMiliseconds

        return newChar

    def _searchItem(self, char):
        """ locate an item in starting with that letter."""
        try:
            self.tree.search(char)
        except Exception as e:
            # seems to raise an exception but selects things right.
            pass

    def _onEnterPath(self, e=None):
        path = os.path.abspath(self.pathVar.get())
        if os.path.exists(path):
            self._goDir(path)

        else:
            self.showInfo("Path '%s' does not exists. " % path)
            self.pathEntry.focus()

    def onClose(self):
        """ This onClose is replaced at init time in the FileBrowserWindow with its own callback"""
        pass

    def _close(self, e=None):
        """ This _close is bound to the close button"""
        self.onClose()

    def _select(self, e=None):

        self._lastSelected = self.getSelected()

        if self._lastSelected is not None:
            if self.onSelect:
                self.onSelect(self._lastSelected)
            else:
                self.onClose()
        else:
            self.showInfo('Select a valid file/folder')

    def getEntryValue(self):
        return self.entryVar.get()

    def getCurrentDir(self):
        return self.treeProvider.getDir()


class ShortCut:
    """ Shortcuts to paths to be displayed in the file browser"""

    @staticmethod
    def factory(path, name, icon=None, toolTip=""):
        """ Factory method to create shortcuts"""
        return ShortCut(path, name, icon, toolTip)

    def __init__(self, path, name, icon=None, toolTip=""):
        self.path = path
        self.name = name
        self.icon = icon
        self.toolTip = toolTip


class BrowserWindow(gui.Window):
    """ Windows to hold a browser frame inside. """

    def __init__(self, title, master=None, **kwargs):
        if 'minsize' not in kwargs:
            kwargs['minsize'] = (800, 400)
        gui.Window.__init__(self, title, master, **kwargs)

    def setBrowser(self, browser, row=0, column=0):
        self.browser = browser
        browser.grid(row=row, column=column, sticky='news')
        self.itemConfig = browser.tree.itemConfig


STANDARD_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg']


def isStandardImage(filename):
    """ Check if a filename have an standard image extension. """
    fnLower = filename.lower()
    return any(fnLower.endswith(ext) for ext in STANDARD_IMAGE_EXTENSIONS)


class FileBrowserWindow(BrowserWindow):
    """ Windows to hold a file browser frame inside. """

    lastValue=None
    def __init__(self, title, master=None, path=None,
                 onSelect=None, shortCuts=None, **kwargs):
        BrowserWindow.__init__(self, title, master, **kwargs)
        self.registerHandlers()
        browser = FileBrowser(self.root, path,
                              showInfo=lambda msg: self.showInfo(msg, "Info"),
                              shortCuts=shortCuts,
                              **kwargs)
        if onSelect:
            def selected(obj):
                self.close()
                onSelect(obj)

            browser.onSelect = selected
        browser.onClose = self.close
        self.setBrowser(browser)

    def getEntryValue(self):
        return self.browser.getEntryValue()

    def getLastSelection(self):
        return self.browser._lastSelected.getPath()
    def getCurrentDir(self):
        return self.browser.getCurrentDir()

    def registerHandlers(self):
        register = FileTreeProvider.registerFileHandler  # shortcut

        register(TextFileHandler(pwutils.Icon.TXT_FILE),
                 '.txt', '.log', '.out', '.err', '.stdout', '.stderr', '.emx',
                 '.json', '.xml', '.pam')
        register(TextFileHandler(pwutils.Icon.PYTHON_FILE), '.py')
        register(SqlFileHandler(), '.sqlite', '.db')