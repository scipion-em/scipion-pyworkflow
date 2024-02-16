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
import tkinter as tk
import tkinter.font as tkFont
import queue
from functools import partial
from tkinter.ttk import Style

import pyworkflow as pw
from pyworkflow.object import Object
from pyworkflow.utils import Message, Icon
from PIL import Image, ImageTk
from .widgets import Button
import numpy as np

DEFAULT_WINDOW_CLASS = "Scipion Framework"

# --------------- GUI CONFIGURATION parameters -----------------------
# TODO: read font size and name from config file
FONT_ITALIC = 'fontItalic'
FONT_NORMAL = 'fontNormal'
FONT_BOLD = 'fontBold'
FONT_BIG = 'fontBig'
cfgFontName = pw.Config.SCIPION_FONT_NAME
cfgFontSize = pw.Config.SCIPION_FONT_SIZE
cfgFontBigSize = cfgFontSize + 8
# TextColor
# cfgCitationTextColor = "dark olive green"
# cfgLabelTextColor = "black"
# cfgSectionTextColor = "blue4"
# Background Color
# cfgBgColor = "light grey"
# cfgLabelBgColor = "white"
# cfgHighlightBgColor = cfgBgColor
cfgButtonFgColor = pw.Config.SCIPION_BG_COLOR
cfgButtonActiveFgColor = pw.Config.SCIPION_BG_COLOR
cfgButtonBgColor = pw.Config.SCIPION_MAIN_COLOR
cfgButtonActiveBgColor = pw.Config.getActiveColor()
cfgEntryBgColor = "lemon chiffon"
# cfgExpertLabelBgColor = "light salmon"
# cfgSectionBgColor = cfgButtonBgColor
# Color
# cfgListSelectColor = "DeepSkyBlue4"
# cfgBooleanSelectColor = "white"
# cfgButtonSelectColor = "DeepSkyBlue2"
# Dimensions limits
# cfgMaxHeight = 650
cfgMaxWidth = 800
# cfgMaxFontSize = 14
# cfgMinFontSize = 6
cfgWrapLenght = cfgMaxWidth - 50

# Style of treeviews where row height is variable based on the font size
LIST_TREEVIEW = 'List.Treeview'

image_cache = dict()

class Config(Object):
    pass


def saveConfig(filename):
    from pyworkflow.mapper import SqliteMapper
    from pyworkflow.object import String, Integer

    mapper = SqliteMapper(filename)
    o = Config()
    for k, v in globals().items():
        if k.startswith('cfg'):
            if type(v) is str:
                value = String(v)
            else:
                value = Integer(v)
            setattr(o, k, value)
    mapper.insert(o)
    mapper.commit()


# --------------- FONT related variables and functions  -----------------------
def setFont(fontKey, update=False, **opts):
    """Register a tkFont and store it in a globals of this module
    this method should be called only after a tk.Tk() windows has been
    created."""
    if not hasFont(fontKey) or update:
        globals()[fontKey] = tkFont.Font(**opts)

    return globals()[fontKey]


def hasFont(fontKey):
    return fontKey in globals()


def aliasFont(fontAlias, fontKey):
    """Set a fontAlias as another alias name of fontKey"""
    g = globals()
    g[fontAlias] = g[fontKey]


def getDefaultFont():
    return tk.font.nametofont("TkDefaultFont")


def getNamedFont(fontName):
    return globals()[fontName]


def getBigFont():
    return getNamedFont(FONT_BIG)


def setCommonFonts(windows=None):
    """Set some predefined common fonts.
    Same conditions of setFont applies here."""
    f = setFont(FONT_NORMAL, family=cfgFontName, size=cfgFontSize)
    aliasFont('fontButton', FONT_NORMAL)

    # Set default font size
    default_font = getDefaultFont()
    default_font.configure(size=cfgFontSize, family=cfgFontName)

    fb = setFont(FONT_BOLD, family=cfgFontName, size=cfgFontSize,
                 weight='bold')
    fi = setFont(FONT_ITALIC, family=cfgFontName, size=cfgFontSize,
                 slant='italic')

    setFont(FONT_BIG, family=cfgFontName, size=cfgFontBigSize)

    # not used?
    # setFont('fontLabel', family=cfgFontName, size=cfgFontSize+1, weight='bold')

    if windows:
        windows.fontBig = tkFont.Font(size=cfgFontSize + 2, family=cfgFontName,
                                      weight='bold')
        windows.font = f
        windows.fontBold = fb
        windows.fontItalic = fi

        # This adds the default value for the listbox inside a combo box
        # Which seems to not react to default font!!
        windows.root.option_add("*TCombobox*Listbox*Font", default_font)
        windows.root.option_add("*TCombobox*Font", default_font)


def changeFontSizeByDeltha(font, deltha, minSize=-999, maxSize=999):
    size = font['size']
    new_size = size + deltha
    if minSize <= new_size <= maxSize:
        font.configure(size=new_size)


def changeFontSize(font, event, minSize=-999, maxSize=999):
    deltha = 2
    if event.char == '-':
        deltha = -2
    changeFontSizeByDeltha(font, deltha, minSize, maxSize)


# --------------- IMAGE related variables and functions -----------------------
def getImage(imageName, imgDict=None, tkImage=True, percent=100,
             maxheight=None):
    """ Search for the image in the RESOURCES path list. """

    global image_cache

    if imageName is None:
        return None

    # Rename .gif by .png. In Linux with pillow 9.2.0 gif transparency is broken so
    # we need to go for png. But in the past, in Macs png didn't work and made us go from png to gif
    # We are now providing the 2 formats, prioritising pngs. If png work in MAC and windows then gif
    # could be deleted. Otherwise, we may need to do this replacement based on the OS.
    # NOTE: "convert  my-image.gif PNG32:my-image.png" has converted gifs to pngs RGBA (32 bits) it seems pillow
    # needs RGBA format to deal with transparencies.

    if not os.path.isabs(imageName) and imageName not in [Icon.WAITING]:
        imageName = imageName.replace(".gif", ".png")

    if imageName in image_cache:
        return image_cache[imageName]

    if not os.path.isabs(imageName):
        imagePath = pw.findResource(imageName)
    else:
        imagePath = imageName
    image = None
    if imagePath:
        image = Image.open(imagePath)
        # For a future dark mode we might need to invert the image but it requires some extra work to make it look nice:
        # image = invertImage(image)
        w, h = image.size
        newSize = None
        if percent != 100:  # Display image with other dimensions
            fp = float(percent) / 100.0
            newSize = int(fp * w), int(fp * h)
        elif maxheight and h > maxheight:
            newSize = int(w * float(maxheight) / h), maxheight
        if newSize:
            image.thumbnail(newSize, Image.ANTIALIAS)
        if tkImage:
            image = ImageTk.PhotoImage(image)

        image_cache[imageName] = image
    return image

def invertImage(img):
    # Creating a numpy array out of the image object
    img_arry = np.array(img)

    # Maximum intensity value of the color mode
    I_max = 255

    # Subtracting 255 (max value possible in a given image
    # channel) from each pixel values and storing the result
    img_arry = I_max - img_arry

    # Creating an image object from the resultant numpy array
    return Image.fromarray(img_arry)
# ---------------- Windows geometry utilities -----------------------
def getGeometry(win):
    """ Return the geometry information of the windows
    It will be a tuple (width, height, x, y)
    """
    return (win.winfo_reqwidth(), win.winfo_reqheight(),
            win.winfo_x(), win.winfo_y())


def centerWindows(root, dim=None, refWindows=None):
    """Center a windows in the middle of the screen 
    or in the middle of other windows(refWindows param)"""
    root.update_idletasks()
    if dim is None:
        gw, gh, _, _ = getGeometry(root)
    else:
        gw, gh = dim
    if refWindows:
        rw, rh, rx, ry = getGeometry(refWindows)
        x = rx + (rw - gw) / 2
        y = ry + (rh - gh) / 2
    else:
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        x = (w - gw) / 2
        y = (h - gh) / 2

    root.geometry("%dx%d+%d+%d" % (gw, gh, x, y))


def configureWeigths(widget, row=0, column=0):
    """This function is a shortcut to a common
    used pair of calls: rowconfigure and columnconfigure
    for making childs widgets take the space available"""
    widget.columnconfigure(column, weight=1)
    widget.rowconfigure(row, weight=1)


def defineStyle():
    """
    Defines some specific behaviour of the style.
    """

    # To specify the height of the rows based on the font size.
    # Should be centralized somewhere.
    style = Style()
    defaultFont = getDefaultFont()
    rowheight = defaultFont.metrics()['linespace']

    style.configure(LIST_TREEVIEW, rowheight=rowheight,
                    background=pw.Config.SCIPION_BG_COLOR,
                    fieldbackground=pw.Config.SCIPION_BG_COLOR)
    style.configure(LIST_TREEVIEW+".Heading", font=(defaultFont["family"],defaultFont["size"]))


class Window:
    """Class to manage a Tk windows.
    It will encapsulate some basic creation and
    setup functions. """
    # To allow plugins to add their own menus
    _pluginMenus = dict()

    def __init__(self, title='', masterWindow=None, weight=True,
                 minsize=(500, 300), icon=Icon.SCIPION_ICON, **kwargs):
        """Create a Tk window.
        title: string to use as title for the windows.
        master: if not provided, the windows create will be the principal one
        weight: if true, the first col and row will be configured with weight=1
        minsize: a minimum size for height and width
        icon: if not None, set the windows icon
        """
        # Init gui plugins
        pw.Config.getDomain()._discoverGUIPlugins()

        if masterWindow is None:
            Window._root = self
            self._images = {}
            # If a window which isn't the main Scipion window is generated from another main window, e. g. with Scipion
            # template after the refactoring of the kickoff, in which a dialog is launched and then a form, being it
            # called from the command line, so there's no Scipion main window. In that case, a tk.Tk() exists because if
            # a tk.TopLevel(), as the dialog, is directly launched, it automatically generates a main tk.Tk(). Thus,
            # after that first auto-tk.Tk(), another tk.Tk() was created here, and so the previous information was lost.
            # Solution proposed is to generate the root as an invisible window if it doesn't exist previously, and make
            # he first window generated a tk.Toplevel. After that, all steps executed later will go through the else
            # statement, being that way each new tk.Toplevel() correctly referenced.
            root = tk.Tk()
            root.withdraw()  # Main window, invisible
            # invoke the button on the return key
            root.bind_class("Button", "<Key-Return>", lambda event: event.widget.invoke())

            self._class = kwargs.get("_class", DEFAULT_WINDOW_CLASS)
            self.root = tk.Toplevel(class_=self._class)  # Toplevel of main window
        else:
            class_ = masterWindow._class if hasattr(masterWindow, "_class") else DEFAULT_WINDOW_CLASS
            self.root = tk.Toplevel(masterWindow.root, class_=class_)
            self.root.group(masterWindow.root)
            self._images = masterWindow._images

        self.root.withdraw()
        self.root.title(title)

        if weight:
            configureWeigths(self.root)
        if minsize is not None:
            self.root.minsize(minsize[0], minsize[1])

        # Set the icon
        self._setIcon(icon)

        self.root.protocol("WM_DELETE_WINDOW", self._onClosing)
        self._w, self._h, self._x, self._y = 0, 0, 0, 0
        self.root.bind("<Configure>", self._configure)
        self.master = masterWindow
        setCommonFonts(self)

        if kwargs.get('enableQueue', False):
            self.queue = queue.Queue(maxsize=0)
        else:
            self.queue = None

    def _setIcon(self, icon):

        if icon is not None:
            try:
                path = pw.findResource(icon)
                # If path is None --> Icon not found
                if path is None:
                    # By default, if icon is not found use default scipion one.
                    path = pw.findResource(Icon.SCIPION_ICON)

                abspath = os.path.abspath(path)

                img = tk.Image("photo", file=abspath)
                self.root.tk.call('wm', 'iconphoto', self.root._w, img)
            except Exception as e:
                # Do nothing if icon could not be loaded
                pass

    def __processQueue(self):  # called from main frame
        if not self.queue.empty():
            func = self.queue.get(block=False)
            # executes graphic interface function
            func()
        self._queueTimer = self.root.after(500, self.__processQueue)

    def enqueue(self, func):
        """ Put some function to be executed in the GUI main thread. """
        self.queue.put(func)

    def getRoot(self):
        return self.root

    def desiredDimensions(self):
        """Override this method to calculate desired dimensions."""
        return None

    def _configure(self, e):
        """ Filter event and call appropriate handler. """
        if self.root != e.widget:
            return

        _, _, x, y = getGeometry(self.root)
        w, h = e.width, e.height

        if w != self._w or h != self._h:
            self._w, self._h = w, h
            self.handleResize()

        if x != self._x or y != self._y:
            self._x, self._y = x, y
            self.handleMove()

    def handleResize(self):
        """Override this method to respond to resize events."""
        pass

    def handleMove(self):
        """Override this method to respond to move events."""
        pass

    def show(self, center=True):
        """This function will enter in the Tk mainloop"""
        if center:
            if self.master is None:
                refw = None
            else:
                refw = self.master.root
            centerWindows(self.root, dim=self.desiredDimensions(),
                          refWindows=refw)
        self.root.deiconify()
        self.root.focus_set()
        if self.queue is not None:
            self._queueTimer = self.root.after(1000, self.__processQueue)
        self.root.mainloop()

    def close(self, e=None):
        self.root.destroy()
        # JMRT: For some reason when Tkinter has an exception
        # it does not exit the application as expected and
        # remains in the mainloop, so here we are forcing
        # to exit the whole system (only applies for the main window)
        if self.master is None:
            import sys
            sys.exit()

    def _onClosing(self):
        """Do some cleaning before closing."""
        if self.master is None:
            pass
        else:
            self.master.root.focus_set()
        if self.queue is not None:
            self.root.after_cancel(self._queueTimer)
        self.close()

    def getImage(self, imgName, percent=100, maxheight=None):
        return getImage(imgName, self._images, percent=percent,
                        maxheight=maxheight)

    def createMainMenu(self, menuConfig):
        """Create Main menu from the given MenuConfig object."""
        menu = tk.Menu(self.root, font=self.font)
        self._addMenuChilds(menu, menuConfig)
        self._addPluginMenus(menu)
        self.root.config(menu=menu)
        return menu

    def _addMenuChilds(self, menu, menuConfig):
        """Add entries of menuConfig in menu
        (using add_cascade or add_command for sub-menus and final options)."""
        # Helper function to create the main menu.
        for sub in menuConfig:
            menuLabel = sub.text
            if not menuLabel:  # empty or None label means a separator
                menu.add_separator()
            elif len(sub) > 0:  # sub-menu
                submenu = tk.Menu(self.root, tearoff=0, font=self.font)
                menu.add_cascade(label=menuLabel, menu=submenu)
                self._addMenuChilds(submenu, sub)  # recursive filling
            else:  # menu option
                # If there is an entry called "Browse files", when clicked it
                # will call the method onBrowseFiles() (it has to be defined!)
                def callback(name):
                    """Return a callback function named "on<Name>"."""
                    f = "on%s" % "".join(x.capitalize() for x in name.split())
                    return lambda: getattr(self, f)()

                if sub.shortCut is not None:
                    menuLabel += ' (' + sub.shortCut + ')'

                menu.add_command(label=menuLabel, compound=tk.LEFT,
                                 image=self.getImage(sub.icon),
                                 command=callback(name=sub.text))

    def _addPluginMenus(self, menu):

        if self._pluginMenus:
            submenu = tk.Menu(self.root, tearoff=0, font=self.font)
            menu.add_cascade(label="Others", menu=submenu)

            # For each plugin menu
            for label in self._pluginMenus:
                submenu.add_command(label=label, compound=tk.LEFT,
                                    image=self.getImage(self._pluginMenus.get(label)[1]),
                                    command=partial(self.plugin_callback, label))

    def plugin_callback(self, label):
        return self._pluginMenus.get(label)[0](self)

    @classmethod
    def registerPluginMenu(cls, label, callback, icon=None):
        # TODO: have a proper model instead of a tuple?
        cls._pluginMenus[label] = (callback, icon)

    def showError(self, msg, header="Error", exception=None):
        """Pops up a dialog with the error message
        :param msg Message to display
        :param header Title of the dialog
        :param exception: Optional. exception associated"""
        from .dialog import showError
        showError(header, msg, self.root, exception=exception)

    def showInfo(self, msg, header="Info"):
        from .dialog import showInfo
        showInfo(header, msg, self.root)

    def showWarning(self, msg, header='Warning'):
        from .dialog import showWarning
        showWarning(header, msg, self.root)

    def askYesNo(self, title, msg):
        from .dialog import askYesNo
        return askYesNo(title, msg, self.root)

    def createCloseButton(self, parent):
        """ Create a button for closing the window, setting
        the proper label and icon. 
        """
        return Button(parent, Message.LABEL_BUTTON_CLOSE, Icon.ACTION_CLOSE,
                      command=self.close)

    def configureWeights(self, row=0, column=0):
        configureWeigths(self.root, row, column)
