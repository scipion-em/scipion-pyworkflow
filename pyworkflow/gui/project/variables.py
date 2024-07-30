# **************************************************************************
# *
# * Authors:     Pablo Conesa (scipion@cnb.csic.es)
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
Module for editing variables
"""
        
import tkinter as tk

from pyworkflow import Config, Variable, VariablesRegistry, VarTypes
from pyworkflow.gui import Icon, configureWeigths, getDefaultFont, askPath
from pyworkflow.gui.tree import TreeProvider
import pyworkflow.gui.dialog as dialog


class VariablesTreeProvider(TreeProvider):
    """ Populate Tree from Labels. """
    def __init__(self):
        TreeProvider.__init__(self)
        self._parentDict = {}

    def getColumns(self):
        return [('Name', 300), ('Value', 500), ('Default?', 60), ('DefaultV',200),('Description', 400), ('Source', 150)]

    def getObjectInfo(self, variable: Variable):

        return {'key': variable.name, 'parent': None,
                'text': variable.name, 'values': (variable.value, "is default" if variable.isDefault else "Declared",
                                                  variable.default, variable.description, variable.source),
                }


    def getObjects(self):
        return VariablesRegistry.__iter__()


class VariablesDialog(dialog.ToolbarListDialog):
    """
    This dialog will allow editing variables coming either from pyworkflow or the plugins
    """
    def __init__(self, parent, **kwargs):
        """ From kwargs:
                message: message tooltip to show when browsing.
                selected: the item that should be selected.
                validateSelectionCallback:
                    a callback function to validate selected items.
                allowSelect: if set to False, the 'Select' button will not
                    be shown.
        """
        toolbarButtons = [
            # dialog.ToolbarButton('Add', self._addLabel, Icon.ACTION_NEW),
            dialog.ToolbarButton('Edit', self._editVariable, Icon.ACTION_EDIT),
            dialog.ToolbarButton('Set to default', self._setToDefault, Icon.ACTION_DELETE)
        ]

        helpMsg =("Use this form to change core and plugin's variables. If \"Default\" is true, it currently is the default value and is not present in the config file. All changes here "
                  "will be persisted in the general %s config file. \"Source\" field tells you where the variable is defined."% Config.SCIPION_CONFIG)

        dialog.ToolbarListDialog.__init__(self, parent,
                                          "Edit config variables",
                                          VariablesTreeProvider(),
                                          helpMsg,
                                          toolbarButtons,
                                          allowsEmptySelection=True,
                                          itemDoubleClick=self._editVariable,
                                          cancelButton=False,
                                          buttons=[('Save', dialog.RESULT_YES),
                                           ('Cancel', dialog.RESULT_CANCEL)],
                                          **kwargs)


    def apply(self):
        VariablesRegistry.save(Config.SCIPION_CONFIG)
    def _editVariable(self, e=None):
        selection = self.tree.getSelectedObjects()
        if selection:
            variable = selection[0]
            dlg = EditVariableDialog(self, "Edit variable", variable)
            if dlg.resultYes():
                self.refresh()

    def _setToDefault(self, e=None):
        selection = self.tree.getSelectedObjects()
        if selection:
            varsStr = '\n'.join('- %s' % v.name for v in selection)
            if dialog.askYesNo(" The variables will be set it to its default value.",
                               "Are you sure to reset the %s"
                               "value?\n" % varsStr, self):
                for variable in selection:
                    variable.setToDefault()
                self.tree.update()


class EditVariableDialog(dialog.Dialog):
    """ Dialog to edit a variable """
    def __init__(self, parent, title, variable:Variable, **kwargs):
        self.variable = variable
        dialog.Dialog.__init__(self, parent, title)

    def body(self, bodyFrame):
        bodyFrame.config(bg=Config.SCIPION_BG_COLOR)
        configureWeigths(bodyFrame, 1, 1)

        # Name
        label_text = tk.Label(bodyFrame, text=self.variable.name, bg=Config.SCIPION_BG_COLOR, bd=0)
        label_text.grid(row=0, column=0, sticky='nw', padx=(15, 10), pady=15)

        # Description
        label_text = tk.Label(bodyFrame, text=self.variable.description, bg=Config.SCIPION_BG_COLOR, bd=0)
        label_text.grid(row=0, column=1, sticky='nw', padx=(15, 10), pady=15)

        # Value
        label_text = tk.Label(bodyFrame, text="Value", bg=Config.SCIPION_BG_COLOR, bd=0)
        label_text.grid(row=2, column=0, sticky='nw', padx=(15, 10), pady=15)

        # Value Entry
        if self.variable.var_type == VarTypes.INTEGER:
            var=tk.IntVar()
        else:
            var = tk.StringVar()

        var.set(self.variable.value)
        self.valueVar = var
        self.valueLabel = tk.Entry(bodyFrame, width=30, textvariable=var, font=getDefaultFont())
        self.valueLabel.grid(row=2, column=1, sticky='news', padx=5, pady=5)

        if self.variable.var_type in [VarTypes.PATH, VarTypes.FOLDER, VarTypes.FILENAME]:
            self._addButton(bodyFrame, self.buttonClicked, icon=Icon.ACTION_BROWSE, row=2, col=2,tooltip="Click to browse file system for a file or folder")

    def buttonClicked(self, e):
        """ Callback for when the wizard button has been clicked"""

        var_type = self.variable.var_type

        if var_type in [VarTypes.PATH, VarTypes.FOLDER, VarTypes.FILENAME]:

            onlyFolders = (var_type == VarTypes.FOLDER)
            returnBaseName = (var_type ==var_type.FILENAME)
            path = self.valueVar.get() if not returnBaseName else "."

            value =askPath(path=path, master=self, onlyFolders=onlyFolders, returnBaseName=returnBaseName)
            self.valueVar.set(value)
    def apply(self):
        self.variable.setValue(self.valueVar.get())

    def validate(self):

        validationMsg = None

        if len(self.valueVar.get().strip()) == 0:
            validationMsg = "Value name can't be empty.\n"

        if validationMsg is not None:
            dialog.showError("Validation error", validationMsg, self)
            return False

        return True
