# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
# *              Jose Gutierrez (jose.gutierrez@cnb.csic.es)
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
"""
Module to handling Dialogs
some code was taken from tkSimpleDialog
"""
import os.path
import tkinter as tk
import traceback
from tkcolorpicker import askcolor as _askColor
from pyworkflow import Config
from pyworkflow.exceptions import PyworkflowException
from pyworkflow.utils import Message, Icon, Color
from . import gui, Window, widgets, configureWeigths, LIST_TREEVIEW, defineStyle, ToolTip, getDefaultFont
from .tree import BoundTree, Tree
from .text import Text, TaggedText

# Possible result values for a Dialog
from .. import TK

RESULT_YES = 0
RESULT_NO = 1
RESULT_CANCEL = 2
RESULT_RUN_SINGLE = 3
RESULT_RUN_ALL = 4
RESULT_CLOSE = 5


class Dialog(tk.Toplevel):
    _images = {}  # Images cache
    """Implementation of our own dialog to display messages
    It will have by default a three buttons: YES, NO and CANCEL
    Subclasses can rename the labels of the buttons like: OK, CLOSE or others
    The buttons(and theirs order) can be changed.
    An image name can be passed to display left to the message.
    """

    def __init__(self, parent, title, lockGui=True, **kwargs):
        """Initialize a dialog.
        Arguments:
            parent -- a parent window (the application window)
            title -- the dialog title
        **args accepts:
            buttons -- list of buttons tuples containing which buttons to display
        """

        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
            gui.setCommonFonts()
            # invoke the button on the return key
            parent.bind_class("Button", "<Key-Return>", lambda event: event.widget.invoke())

        tk.Toplevel.__init__(self, parent)

        defineStyle()

        self.withdraw()  # remain invisible for now
        # If the master is not viewable, don't
        # make the child transient, or else it
        # would be opened withdrawn
        if parent.winfo_viewable() and lockGui:
            self.transient(parent)

        if title:
            self.title(title)

        self.parent = parent

        # Default to CANCEL so if window is "Closed" behaves the same.
        self.result = RESULT_CANCEL
        self.initial_focus = None

        bodyFrame = tk.Frame(self)
        # Call subclass method body to create that region
        self.body(bodyFrame)
        bodyFrame.grid(row=0, column=0, sticky='news',
                       padx=5, pady=5)

        # Frame for the info/message label
        infoFrame = tk.Frame(self)
        infoFrame.grid(row=1, column=0, sticky='sew',
                       padx=5, pady=(0, 5))
        self.floatingMessage = tk.Label(infoFrame, text="", fg=Config.SCIPION_MAIN_COLOR)
        self.floatingMessage.grid(row=0, column=0, sticky='news')

        # Create buttons
        self.icons = kwargs.get('icons',
                                {RESULT_YES: Icon.BUTTON_SELECT,
                                 RESULT_NO: Icon.BUTTON_CLOSE,
                                 RESULT_CANCEL: Icon.BUTTON_CANCEL,
                                 RESULT_CLOSE: Icon.BUTTON_CLOSE})

        self.buttons = kwargs.get('buttons', [('OK', RESULT_YES),
                                              ('Cancel', RESULT_CANCEL)])
        self.defaultButton = kwargs.get('default', 'OK')

        # Frame for buttons
        btnFrame = tk.Frame(self)
        self.buttonbox(btnFrame)
        btnFrame.grid(row=2, column=0, sticky='sew',
                      padx=5, pady=(0, 5))

        gui.configureWeigths(self)

        if self.initial_focus is None:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        if self.parent is not None:
            position = kwargs.get('position', (parent.winfo_rootx() + 50,
                                               parent.winfo_rooty() + 50))
            self.geometry("+%d+%d" % position)

        self.deiconify()  # become visible now
        self.initial_focus.focus_set()
        # Pablo: I've commented this when migrating to python3 since I was getting and exception:
        # window ".139897767953072.139897384058440" was deleted before its visibility changed
        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        if lockGui:
            self.grab_set()
        self.wait_window(self)

    def getRoot(self):
        return self

    def destroy(self):
        """Destroy the window"""
        self.initial_focus = None
        tk.Toplevel.destroy(self)

    #
    # construction hooks

    def body(self, master):
        """create dialog body.
        return widget that should have initial focus.
        This method should be overridden, and is called
        by the __init__ method.
        """
        pass

    def _createButton(self, frame, text, result):
        icon = None
        if result in self.icons.keys():
            icon = self.getImage(self.icons[result])
        return tk.Button(frame, text=text, image=icon,
                         compound=tk.LEFT,
                         command=lambda: self._handleResult(result))

    def buttonbox(self, btnFrame):
        frame = tk.Frame(btnFrame)
        btnFrame.columnconfigure(0, weight=1)
        frame.grid(row=0, column=0)
        col = 0
        for btnLabel, btnResult in self.buttons:
            btn = self._createButton(frame, btnLabel, btnResult)
            btn.grid(row=0, column=col, padx=5, pady=5)
            if (btnLabel == self.defaultButton and
                    self.initial_focus is None):
                self.initial_focus = btn
            col += 1
        self.bind("<Return>", self._handleReturn)
        self.bind("<KP_Enter>", self._handleReturn)
        self.bind("<Escape>", lambda e: self._handleResult(RESULT_CANCEL))

    def _handleResult(self, resultValue):
        """This method will be called when any button is pressed.
        It will set the resultValue associated with the button
        and close the Dialog"""
        self.result = resultValue
        noCancel = self.result != RESULT_CANCEL and self.result != RESULT_CLOSE

        callBack = self.validate if noCancel else self.validateClose
        if not callBack():
            self.initial_focus.focus_set()  # put focus back
            return

        self.withdraw()
        self.update_idletasks()

        try:
            if noCancel:
                self.apply()
        finally:
            self.cancel()

    def _handleReturn(self, e=None):
        """Handle press return key"""
        # Check which of the buttons is the default
        for button, result in self.buttons:
            if self.defaultButton == button:
                self._handleResult(result)

    def cancel(self, event=None):
        # put focus back to the parent window
        if self.parent is not None:
            self.parent.focus_set()
        self.destroy()

    #
    # command hooks

    def validate(self):
        """validate the data
        This method is called automatically to validate the data before the
        dialog is destroyed. By default, it always validates OK.
        """
        return 1  # override

    def validateClose(self):
        return True

    def apply(self):
        """process the data
        This method is called automatically to process the data, *after*
        the dialog is destroyed. By default, it does nothing.
        """
        pass  # override

    def getImage(self, imgName):
        """A shortcut to get an image from its name"""
        return gui.getImage(imgName)

    def getResult(self):
        return self.result

    def resultYes(self):
        return self.result == RESULT_YES

    def resultNo(self):
        return self.result == RESULT_NO

    def resultCancel(self):
        return self.result == RESULT_CANCEL

    def info(self, message):
        """ Shows a info message for long running processes to inform the user GUI is not frozen"""
        self.floatingMessage.config(text=message)

    ### Basic GUI helper methods
    def _addButton(self, frame, callback, text="", icon=None, row=0, col=0, tooltip=None, shortcut=""):
        """ Adds a label button"""
        btn = tk.Label(frame, text=text,
                       image=self.getImage(icon),
                       compound=tk.LEFT, cursor='hand2')
        btn.grid(row=row, column=col, sticky='nw', padx=(5, 0), pady=(5, 0))
        btn.bind('<Button-1>', callback)
        if tooltip:
            tooltip = tooltip + ' (%s)' % shortcut if shortcut else tooltip
            ToolTip(btn, tooltip, delay=150)
        if shortcut:
            self.bind(shortcut, callback)


def fillMessageText(text, message):
    # Insert lines of text
    if isinstance(message, list):
        lines = message
    else:
        lines = message.splitlines()
    text.setReadOnly(False)
    text.clear()
    w = 0
    for l in lines:
        w = max(w, len(l))
        text.addLine(l)
    w = min(w + 5, 80)
    h = min(len(lines) + 3, 30)
    text.config(height=h, width=w)
    text.addNewline()
    text.setReadOnly(True)


def createMessageBody(bodyFrame, message, image,
                      frameBg=Config.SCIPION_BG_COLOR,
                      textBg=Config.SCIPION_BG_COLOR,
                      textPad=5):
    """ Create a Text containing the message.
    Params:
        bodyFrame: tk.Frame to be filled.
        msg: a str or list with the lines.
    """
    bodyFrame.config(bg=frameBg, bd=0)
    text = TaggedText(bodyFrame, bg=textBg, bd=0, highlightthickness=0)
    # Insert image
    if image:
        label = tk.Label(bodyFrame, image=image, bg=textBg, bd=0)
        label.grid(row=0, column=0, sticky='nw')

    text.frame.grid(row=0, column=1, sticky='news',
                    padx=textPad, pady=textPad)
    fillMessageText(text, message)
    bodyFrame.rowconfigure(0, weight=1)
    bodyFrame.columnconfigure(1, weight=1)

    return text


class MessageDialog(Dialog):
    """Dialog subclasses to show message info, questions or errors.
    It can display an icon with the message"""

    def __init__(self, parent, title, msg, iconPath, **args):
        self.msg = msg
        self.iconPath = iconPath
        if 'buttons' not in args:
            args['buttons'] = [('OK', RESULT_YES)]
            args['default'] = 'OK'
        Dialog.__init__(self, parent, title, **args)

    def body(self, bodyFrame):
        self.image = gui.getImage(self.iconPath)
        createMessageBody(bodyFrame, self.msg, self.image)


class ExceptionDialog(MessageDialog):
    def __init__(self, *args, **kwargs):
        self._exception = None if "exception" not in kwargs else kwargs['exception']
        super().__init__(*args, **kwargs)

    def body(self, bodyFrame):
        super().body(bodyFrame)

        def addTraceback(event):
            detailsText = TaggedText(bodyFrame, bg=Config.SCIPION_BG_COLOR, bd=0, highlightthickness=0)
            traceStr = traceback.format_exc()
            fillMessageText(detailsText, traceStr)
            detailsText.frame.grid(row=row + 1, column=0, columnspan=2, sticky='news', padx=5, pady=5)
            event.widget.grid_forget()

        row = 1
        if self._exception:

            if isinstance(self._exception, PyworkflowException):
                helpUrl = self._exception.getUrl()
                labelUrl = TaggedText(bodyFrame, bg=Config.SCIPION_BG_COLOR, bd=0, highlightthickness=0)
                fillMessageText(labelUrl, "Please go here for more details: %s" % helpUrl)
                labelUrl.grid(row=row, column=0, columnspan=2, sticky='news')
                row += 1

            label = tk.Label(bodyFrame, text="Show details...", bg=Config.SCIPION_BG_COLOR, bd=0)
            label.grid(row=row, column=0, columnspan=2, sticky='news')
            label.bind("<Button-1>", addTraceback)


class YesNoDialog(MessageDialog):
    """Ask a question with YES/NO answer"""

    def __init__(self, master, title, msg, **kwargs):
        buttonList = [('Yes', RESULT_YES), ('No', RESULT_NO)]

        if kwargs.get('showCancel', False):
            buttonList.append(('Cancel', RESULT_CANCEL))

        MessageDialog.__init__(self, master, title, msg,
                               Icon.ALERT, default='No',
                               buttons=buttonList)


class GenericDialog(Dialog):
    """
    Create a dialog with many buttons
    Arguments:
            parent -- a parent window (the application window)
            title -- the dialog title
            msg  -- message to display into the dialog
            iconPath -- path of the image to show into the dialog

        **args accepts:
            buttons -- list of buttons tuples containing which buttons to display and theirs values
            icons -- list of icons for all buttons
            default -- button default

            Example:
                buttons=[('Single', RESULT_RUN_SINGLE),
                         ('All', RESULT_RUN_ALL),
                         ('Cancel', RESULT_CANCEL)],
                default='Cancel',
                icons={RESULT_CANCEL: Icon.BUTTON_CANCEL,
                       RESULT_RUN_SINGLE: Icon.BUTTON_SELECT,
                       RESULT_RUN_ALL: Icon.ACTION_EXECUTE})
    """

    def __init__(self, master, title, msg, iconPath, **kwargs):
        self.msg = msg
        self.iconPath = iconPath
        Dialog.__init__(self, master, title, **kwargs)

    def body(self, bodyFrame):
        self.image = gui.getImage(self.iconPath)
        createMessageBody(bodyFrame, self.msg, self.image)


class EntryDialog(Dialog):
    """Dialog to ask some entry"""

    def __init__(self, parent, title, entryLabel, entryWidth=20,
                 defaultValue='', headerLabel=None):
        self.entryLabel = entryLabel
        self.entryWidth = entryWidth
        self.headerLabel = headerLabel
        self.tkvalue = tk.StringVar()
        self.tkvalue.set(defaultValue)
        self.value = None
        Dialog.__init__(self, parent, title)

    def body(self, bodyFrame):
        bodyFrame.config(bg=Config.SCIPION_BG_COLOR)
        frame = tk.Frame(bodyFrame, bg=Config.SCIPION_BG_COLOR)
        frame.grid(row=0, column=0, padx=20, pady=20)
        row = 0
        if self.headerLabel:
            label = tk.Label(bodyFrame, text=self.headerLabel, bg=Config.SCIPION_BG_COLOR, bd=0)
            label.grid(row=row, column=0, columnspan=2, sticky='nw', padx=(15, 10), pady=15)
            row += 1
        label = tk.Label(bodyFrame, text=self.entryLabel, bg=Config.SCIPION_BG_COLOR, bd=0)
        label.grid(row=row, column=0, sticky='nw', padx=(15, 10), pady=15)
        self.entry = tk.Entry(bodyFrame, bg=gui.cfgEntryBgColor,
                              width=self.entryWidth, textvariable=self.tkvalue,
                              font=getDefaultFont())
        self.entry.grid(row=row, column=1, sticky='new', padx=(0, 15), pady=15)
        self.initial_focus = self.entry

    def apply(self):
        self.value = self.entry.get()

    def validate(self):
        if len(self.entry.get().strip()) == 0:
            showError("Validation error", "Value is empty", self)
            return False
        return True


class EditObjectDialog(Dialog):
    """Dialog to edit some text"""

    def __init__(self, parent, title, obj, mapper, **kwargs):
        self.obj = obj
        self.mapper = mapper

        self.textWidth = 5
        self.textHeight = 1
        self.labelText = kwargs.get('labelText', Message.TITLE_LABEL)
        self.valueText = self.obj.getObjLabel()

        self.commentLabel = Message.TITLE_COMMENT
        self.commentWidth = 50
        self.commentHeight = 15
        self.valueComment = self.obj.getObjComment()

        Dialog.__init__(self, parent, title, **kwargs)

    def body(self, bodyFrame):
        bodyFrame.config(bg=Config.SCIPION_BG_COLOR)
        frame = tk.Frame(bodyFrame, bg=Config.SCIPION_BG_COLOR)
        frame.grid(row=0, column=0, padx=20, pady=20)

        # Label
        label_text = tk.Label(bodyFrame, text=self.labelText, bg=Config.SCIPION_BG_COLOR, bd=0)
        label_text.grid(row=0, column=0, sticky='nw', padx=(15, 10), pady=15)
        # Label box
        var = tk.StringVar()
        var.set(self.valueText)
        self.textLabel = tk.Entry(bodyFrame, width=self.textWidth, textvariable=var, font=gui.getDefaultFont())
        self.textLabel.grid(row=0, column=1, sticky='news', padx=5, pady=5)

        # Comment
        label_comment = tk.Label(bodyFrame, text=self.commentLabel, bg=Config.SCIPION_BG_COLOR, bd=0)
        label_comment.grid(row=1, column=0, sticky='nw', padx=(15, 10), pady=15)
        # Comment box
        self.textComment = Text(bodyFrame, height=self.commentHeight,
                                width=self.commentWidth)
        self.textComment.setReadOnly(False)
        self.textComment.setText(self.valueComment)
        self.textComment.grid(row=1, column=1, sticky='news', padx=5, pady=5)
        self.initial_focus = self.textLabel

    def getLabel(self):
        return self.textLabel.get()

    def getComment(self):
        return self.textComment.getText()

    def apply(self):
        self.obj.setObjLabel(self.getLabel())
        self.obj.setObjComment(self.getComment())

        if self.obj.hasObjId():
            self.mapper.store(self.obj)
            self.mapper.commit()

    def buttonbox(self, btnFrame):
        # Cancel the binding of <Return> key
        Dialog.buttonbox(self, btnFrame)
        # self.bind("<Return>", self._noReturn)
        self.unbind("<Return>")

    def _noReturn(self, e):
        pass


""" Functions to display dialogs """


def askYesNo(title, msg, parent):
    d = YesNoDialog(parent, title, msg)
    return d.resultYes()


def askYesNoCancel(title, msg, parent):
    d = YesNoDialog(parent, title, msg, showCancel=True)
    return d.result


def askSingleAllCancel(title, msg, parent):
    d = GenericDialog(parent, title, msg,
                      Icon.ALERT,
                      buttons=[('Single', RESULT_RUN_SINGLE),
                               ('All', RESULT_RUN_ALL),
                               ('Cancel', RESULT_CANCEL)],
                      default='Single',
                      icons={RESULT_CANCEL: Icon.BUTTON_CANCEL,
                             RESULT_RUN_SINGLE: Icon.BUTTON_SELECT,
                             RESULT_RUN_ALL: Icon.ACTION_EXECUTE})

    return d.result


def showInfo(title, msg, parent):
    MessageDialog(parent, title, msg, Icon.INFO)


def showWarning(title, msg, parent):
    MessageDialog(parent, title, msg, Icon.ALERT)


def showError(title, msg, parent, exception=None):
    ExceptionDialog(parent, title, msg, Icon.ERROR, exception=exception)


def askString(title, label, parent, entryWidth=20, defaultValue='', headerLabel=None):
    d = EntryDialog(parent, title, label, entryWidth, defaultValue, headerLabel)
    return d.value


def askColor(parent, defaultColor='black'):
    (rgbcolor, hexcolor) = _askColor(defaultColor, parent=parent)
    return hexcolor


def askPath(title=None, msg="Select a file of a folder", path=".", onlyFolders=False, master=None, returnBaseName=False):
    from pyworkflow.gui.browser import FileBrowserWindow

    if title is None:
        title = "Select a folder" if onlyFolders else "Select a file"
    browserW = FileBrowserWindow(title, master=master, path=path, onlyFolders=onlyFolders)
    browserW.show(modal=True)

    result = browserW.getLastSelection()
    if returnBaseName:
        result=os.path.basename(result)

    return result

class ListDialog(Dialog):
    """
    Dialog to select an element from a list.
    It is implemented using the Tree widget.
    """

    def __init__(self, parent, title, provider, message=None, **kwargs):
        """ From kwargs:

        :param message: message tooltip to show when browsing.
        :param validateSelectionCallback: a callback function to validate selected items.
        :param previewCallback: method to be called on item click to fill the callback frame.
        :param selectmode: 'extended' by default. Selection mode of the tk.Tree
        :param selectOnDoubleClick: (False). If True, double click will trigger "Select" button click
        :param allowsEmptySelection: (False). Allows empty selection
        :param allowSelect: if set to False, the 'Select' button will not be shown.
        :param allowsEmptySelection: if set to True, it will not validate that at least one element was selected.
        """
        self.values = []
        self.provider = provider
        self.message = message
        self.validateSelectionCallback = kwargs.get('validateSelectionCallback', None)
        self.previewCallBack = kwargs.get('previewCallback', None)

        self._selectmode = kwargs.get('selectmode', 'extended')
        self._selectOnDoubleClick = kwargs.get('selectOnDoubleClick', False)
        self._allowsEmptySelection = kwargs.get('allowsEmptySelection', False)

        if "buttons" not in kwargs:
            buttons=[]
            if kwargs.get('allowSelect', True):
                buttons.append(('Select', RESULT_YES))
            if kwargs.get('cancelButton', False):
                buttons.append(('Close', RESULT_CLOSE))
            else:
                buttons.append(('Cancel', RESULT_CANCEL))
            kwargs['buttons'] = buttons
        Dialog.__init__(self, parent, title, **kwargs)

    def body(self, bodyFrame):
        bodyFrame.config()
        gui.configureWeigths(bodyFrame)
        dialogFrame = tk.Frame(bodyFrame)
        dialogFrame.grid(row=0, column=0, sticky='news', padx=5, pady=5)
        dialogFrame.config()
        gui.configureWeigths(dialogFrame, row=1)
        self._createFilterBox(dialogFrame)
        self._createTree(dialogFrame)
        if self.previewCallBack:
            self._createPreviewPanel(dialogFrame)

        if self.message:
            label = tk.Label(bodyFrame, text=self.message, compound=tk.LEFT,
                             image=self.getImage(Icon.LIGHTBULB))
            label.grid(row=2, column=0, sticky='nw', padx=5, pady=5)
        self.initial_focus = self.tree

    def _createTree(self, parent):
        self.tree = BoundTree(parent, self.provider, selectmode=self._selectmode, style=LIST_TREEVIEW)
        if self._selectOnDoubleClick:
            self.tree.itemDoubleClick = lambda obj: self._handleResult(RESULT_YES)

        if self.previewCallBack:
            self.tree.itemClick = self._itemClick

        self.tree.grid(row=1, column=0)

    def _itemClick(self, obj):
        self.previewCallBack(obj, self.previewFrame)

    def _createPreviewPanel(self, parent):
        self.previewFrame = tk.Frame(parent)
        self.previewFrame.grid(row=1, column=1)

    def _createFilterBox(self, content):
        """ Create the Frame with Filter widgets """

        self.searchBoxframe = tk.Frame(content)
        label = tk.Label(self.searchBoxframe, text="Filter")
        label.grid(row=0, column=0, sticky='nw')
        self._searchVar = tk.StringVar(value='')
        self.entry = tk.Entry(self.searchBoxframe, bg=Config.SCIPION_BG_COLOR,
                              textvariable=self._searchVar, width=40,
                              font=gui.getDefaultFont())

        self.entry.bind('<KeyRelease>', self._onSearch)
        self.entry.focus_set()
        self.entry.grid(row=0, column=1, sticky='news')
        self.searchBoxframe.grid(row=0, column=0, sticky='news', padx=5,
                                 pady=(10, 5))

    def refresh(self):
        """ Refreshes the list taking into account the filter"""
        self._onSearch()

    def _onSearch(self, e=None):

        def comparison():
            pattern = self._searchVar.get().lower()
            return [w[0] for w in self.lista.items()
                    if pattern in self.lista.get(w[0]).lower()]

        self.tree.update()
        self.lista = {}

        for item in self.tree.get_children():

            itemStr = self.tree.item(item)['text']
            for value in self.tree.item(item)['values']:
                if isinstance(value, int):
                    itemStr = itemStr + ' ' + str(value)
                else:
                    itemStr = itemStr + ' ' + value

            self.lista[item] = itemStr

        if self._searchVar.get() != '':
            matchs = comparison()
            if matchs:
                for item in self.tree.get_children():
                    if item not in matchs:
                        self.tree.delete(item)
            else:
                self.tree.delete(*self.tree.get_children())

    def apply(self):
        self.values = self.tree.getSelectedObjects()

    def validate(self):
        self.apply()  # load self.values with selected items
        err = ''

        if self.values:
            if self.validateSelectionCallback:
                err = self.validateSelectionCallback(self.values)
        else:
            if not self._allowsEmptySelection:
                err = "Please select an element"

        if err:
            showError("Validation error", err, self)
            return False

        return True


class ToolbarButton:
    """
    Store information about the buttons that will be added to the toolbar.
    """

    def __init__(self, text, command, icon=None, tooltip=None, shortcut=None):
        self.text = text
        self.command = command
        self.icon = icon
        self.tooltip = tooltip
        self.shortcut = shortcut


class ToolbarListDialog(ListDialog):
    """
    This class extend from ListDialog to allow an
    extra toolbar to handle operations over the elements
    in the list (e.g. Edit, New, Delete).
    """

    def __init__(self, parent, title, provider,
                 message=None, toolbarButtons=None, **kwargs):
        """ From kwargs:
                message: message tooltip to show when browsing.
                selected: the item that should be selected.
                validateSelectionCallback:
                    a callback function to validate selected items.
                allowSelect: if set to False, the 'Select' button will not
                    be shown.
        """
        self.toolbarButtons = toolbarButtons
        self._itemDoubleClick = kwargs.get('itemDoubleClick', None)
        self._itemOnClick = kwargs.get('itemOnClick', None)
        ListDialog.__init__(self, parent, title, provider, message, **kwargs)

    def body(self, bodyFrame):
        gui.configureWeigths(bodyFrame, 1, 0)

        # Add an extra frame to insert the Toolbar
        # and another one for the ListDialog's body
        self.toolbarFrame = tk.Frame(bodyFrame)
        self.toolbarFrame.grid(row=0, column=0, sticky='new')

        subBody = tk.Frame(bodyFrame)
        subBody.grid(row=1, column=0, sticky='news', padx=5, pady=5)
        ListDialog.body(self, subBody)

        if self.toolbarButtons:
            for i, b in enumerate(self.toolbarButtons):
                self.addButton(b, i)

        if self._itemDoubleClick:
            self.tree.itemDoubleClick = self._itemDoubleClick

        if self._itemOnClick:
            self.tree.itemOnClick = self._itemOnClick

    def addButton(self, button, col):

        self._addButton(self.toolbarFrame, button.command, text=button.text, icon=button.icon, col=col, tooltip=button.tooltip, shortcut=button.shortcut)


class FlashMessage:
    def __init__(self, master, msg, delay=5, relief='solid', func=None):
        self.root = tk.Toplevel(master=master)
        # hides until know geometry
        self.root.withdraw()
        self.root.wm_overrideredirect(1)
        tk.Label(self.root, text="   %s   " % msg,
                 bd=1, bg='DodgerBlue4', fg='white').pack()
        gui.centerWindows(self.root, refWindows=master)
        self.root.deiconify()
        self.root.grab_set()
        self.msg = msg

        if func:
            self.root.update_idletasks()
            self.root.after(10, self.process, func)
        else:
            self.root.after(int(delay * 1000), self.close)
        self.root.wait_window(self.root)

    def process(self, func):
        func()
        self.root.destroy()

    def close(self):
        self.root.destroy()


class FloatingMessage:
    def __init__(self, master, msg, xPos=None, yPos=None, textWidth=280,
                 font='Helvetica', size=12, bd=1, bg=Config.SCIPION_MAIN_COLOR, fg='white'):
        if xPos is None:
            xPos = (master.winfo_width() - textWidth) / 2
            yPos = master.winfo_height() / 2

        self.floatingMessage = tk.Label(master, text="   %s   " % msg,
                                        bd=bd, bg=bg, fg=fg)
        self.floatingMessage.place(x=xPos, y=yPos, width=textWidth)
        self.floatingMessage.config(font=(font, size))

    def setMessage(self, msg):
        self.floatingMessage.config(text=msg)

    def show(self):
        self.floatingMessage.update_idletasks()

    def close(self):
        self.floatingMessage.destroy()



class SearchBaseWindow(Window):
    """ Base window for searching in a list
    You are going to implement several elements:

        columnsConfig: a dictionary with elements with this structure:
            <column-key>: (<title>,{kwargs for tree.column method}, weight, <casting_method>(optional, otherwise str))

        Example:

        columnConfig = {
            '#0': ('Status', {'width': 50, 'minwidth': 50, 'stretch': tk.NO}, 3),
            'protocol': ('Protocol', {'width': 300, 'stretch': tk.FALSE}), 5,
            'streaming': ('Streamified', {'width': 100, 'stretch': tk.FALSE}, 3),
            'installed': ('Installation', {'width': 110, 'stretch': tk.FALSE}, 3),
            'help': ('Help', {'minwidth': 300, 'stretch': tk.YES}, 3),
            'score': ('Score', {'width': 50, 'stretch': tk.FALSE}, 3, int),
        }

        _createResultsTree method
        _onSearchClick method

        See SearchProtocolWindow as an example

    """
    COLUMN_TEXT_INDEX = 0
    COLUMN_KWARGS_INDEX = 1
    WEIGHT_INDEX = 2
    CASTING_INDEX = 3
    columnConfig = {}  # Columns configuration

    def __init__(self, parentWindow, title="Search element", onClick=None, onDoubleClick=None, **kwargs):
        super().__init__(title=title,
                         masterWindow=parentWindow)

        self.onClick = self._click if onClick is None else onClick
        self.onDoubleClick = self._double_click if onDoubleClick is None else onDoubleClick

        content = tk.Frame(self.root, bg=Config.SCIPION_BG_COLOR)
        self._createContent(content)
        content.grid(row=0, column=0, sticky='news')
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

    def getColumnKeys(self):
        return self.columnConfig.keys()

    def _createContent(self, content):
        self._createSearchBox(content)
        self._createResultsBox(content)

    def _createSearchBox(self, content):
        """ Create the Frame with Search widgets """
        frame = tk.Frame(content, bg=Config.SCIPION_BG_COLOR)

        label = tk.Label(frame, text="Search", bg=Config.SCIPION_BG_COLOR)
        label.grid(row=0, column=0, sticky='nw')
        self._searchVar = tk.StringVar()
        entry = tk.Entry(frame, bg='white', textvariable=self._searchVar, font=gui.getDefaultFont())
        entry.bind(TK.RETURN, self._onSearchClick)
        entry.bind(TK.ENTER, self._onSearchClick)
        entry.focus_set()
        entry.grid(row=0, column=1, sticky='nw')
        btn = widgets.IconButton(frame, "Search",
                                 imagePath=Icon.ACTION_SEARCH,
                                 command=self._onSearchClick)
        btn.grid(row=0, column=2, sticky='nw')

        frame.grid(row=0, column=0, sticky='new', padx=5, pady=(10, 5))

        return frame

    def _createResultsBox(self, content):
        frame = tk.Frame(content, bg=Color.ALT_COLOR, padx=5, pady=5)
        configureWeigths(frame)
        self._resultsTree = self._createResultsTree(frame,
                                                    show=None,
                                                    columns=list(self.getColumnKeys())[1:])
        self._configureTreeColumns()
        self._resultsTree.grid(row=0, column=0, sticky='news')
        frame.grid(row=1, column=0, sticky='news', padx=5, pady=5)

    def _createResultsTree(self, frame, show, columns):

        t = Tree(frame, show=show, columns=columns, style=LIST_TREEVIEW)
        t.column('#0', minwidth=100)
        t.bind("<Button-1>", self.onClick)
        t.bind("<Double-1>", self.onDoubleClick)
        return t

    def _click(self, event):
        """ To be implemented, triggered on tree-view click """
        pass

    def _double_click(self, event):
        """ To be implemented, triggered on tree-view double click """
        pass

    def addSearchWeight(self, line2Search, searchtext):
        # Adds a weight value for the search
        weight = 0

        linelower = [str(v).lower() for v in line2Search]

        for index, column in enumerate(self.columnConfig.values()):

            if searchtext in linelower[index]:
                # prioritize findings in label
                weight += column[self.WEIGHT_INDEX] * 2

            elif " " in searchtext:
                for word in searchtext.split():
                    if word in linelower[index]:
                        weight += column[self.WEIGHT_INDEX]

        return line2Search + (weight,)

    def _configureTreeColumns(self):

        for key, columnConf in self.columnConfig.items():
            casting = str if len(columnConf) <= self.CASTING_INDEX else columnConf[self.CASTING_INDEX]
            self._resultsTree.column(key, **columnConf[self.COLUMN_KWARGS_INDEX])
            self._resultsTree.heading(key,
                                      text=columnConf[self.COLUMN_TEXT_INDEX],
                                      command=lambda bound_key=key, bound_casting=casting:
                                      self._resultsTree.sortByColumn(bound_key, False, casting=bound_casting))

    def _onSearchClick(self, e=None):
        """ To be implemented, triggered on search button click"""
        pass
