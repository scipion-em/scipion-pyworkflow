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
""" This modules hosts most of the accessory code that is used in view protocols"""
import json
import os
from configparser import ConfigParser

from pyworkflow import Config
import  pyworkflow.gui as pwgui
import pyworkflow.object as pwobj
import pyworkflow.utils as pwutils
from pyworkflow.gui.project.utils import isAFinalProtocol
from pyworkflow.project import MenuConfig
from pyworkflow.utils import Message, Icon
from pyworkflow.viewer import DESKTOP_TKINTER



class RunIOTreeProvider(pwgui.tree.TreeProvider):
    """Create the tree elements from a Protocol Run input/output children"""

    def __init__(self, parent, protocol, mapper, loggerCallback):
        """

        :param parent:
        :param protocol:
        :param mapper:
        :param loggerCallback: method to call to log events in the gui.
        """

        self.parent = parent
        self.protocol = protocol
        self.mapper = mapper
        self._loggerCallback = loggerCallback

    @staticmethod
    def getColumns():
        return [('Attribute', 200), ('Info', 100)]

    def getObjects(self):
        objs = []
        if self.protocol is not None:
            # Store a dict with input parents (input, PointerList)
            self.inputParentDict = pwobj.OrderedDict()
            inputs = []
            inputObj = pwobj.String(Message.LABEL_INPUT)
            inputObj._icon = Icon.ACTION_IN
            self.inputParentDict['_input'] = inputObj
            inputParents = [inputObj]

            for key, attr in self.protocol.iterInputAttributes():
                attr._parentKey = key
                # Repeated keys means there are inside a pointerList
                # since the same key is yielded for all items inside
                # so update the parent dict with a new object
                if key in self.inputParentDict:
                    if self.inputParentDict[key] == inputObj:
                        parentObj = pwobj.String(key)
                        parentObj._icon = Icon.ACTION_IN
                        parentObj._parentKey = '_input'
                        inputParents.append(parentObj)
                        self.inputParentDict[key] = parentObj
                else:
                    self.inputParentDict[key] = inputObj
                inputs.append(attr)

            outputs = [attr for _, attr in
                       self.protocol.iterOutputAttributes()]
            self.outputStr = pwobj.String(Message.LABEL_OUTPUT)
            objs = inputParents + inputs + [self.outputStr] + outputs
        return objs

    def _visualizeObject(self, ViewerClass, obj):
        viewer = ViewerClass(project=self.protocol.getProject(),
                             protocol=self.protocol,
                             parent=self.parent.windows)
        viewer.visualize(obj, windows=self.parent.windows)

    def _editObject(self, obj):
        """Open the Edit GUI Form given an instance"""
        pwgui.dialog.EditObjectDialog(self.parent, Message.TITLE_EDIT_OBJECT,
                                      obj, self.mapper)

    def _deleteObject(self, obj):
        """ Remove unnecessary output, specially for Coordinates. """
        prot = self.protocol
        try:
            objLabel = self.getObjectLabel(obj, prot)
            if self.parent.windows.askYesNo("Delete object",
                                            "Are you sure to delete *%s* object?"
                                            % objLabel):
                prot.getProject().deleteProtocolOutput(prot, obj)
                self.parent._fillSummary()
                self.parent.windows.showInfo("Object *%s* successfully deleted."
                                             % objLabel)
        except Exception as ex:
            self.parent.windows.showError(str(ex))

    @staticmethod
    def getObjectPreview(obj):
        desc = "<name>: " + obj.getName()
        return None, desc

    def getObjectActions(self, obj):
        if isinstance(obj, pwobj.Pointer):
            obj = obj.get()
            isPointer = True
        else:
            isPointer = False
        actions = []

        # If viewers not loaded yet (firstime)
        domain = Config.getDomain()

        if not domain.viewersLoaded():
            self._loggerCallback("Discovering viewers for the first time across all the plugins.")


        viewers = Config.getDomain().findViewers(obj.getClassName(), DESKTOP_TKINTER)

        def viewerCallback(viewer):
            return lambda: self._visualizeObject(viewer, obj)

        for v in viewers:
            actions.append(('Open with %s' % v.__name__ if v._name is None else v._name,
                            viewerCallback(v),
                            Icon.ACTION_VISUALIZE))
        # EDIT
        actions.append((Message.LABEL_EDIT,
                        lambda: self._editObject(obj),
                        Icon.ACTION_EDIT))
        # DELETE
        # Special case to allow delete outputCoordinates
        # since we can end up with several outputs and
        # we may want to clean up
        if self.protocol.allowsDelete(obj) and not isPointer:
            actions.append((Message.LABEL_DELETE,
                            lambda: self._deleteObject(obj),
                            Icon.ACTION_DELETE))
        return actions

    @staticmethod
    def getObjectLabel(obj, parent):
        """ We will try to show in the list the string representation
        that is more readable for the user to pick the desired object.
        """
        label = 'None'
        if obj:
            label = obj.getObjLabel()
            if not len(label.strip()):
                parentLabel = parent.getObjLabel() if parent else 'None'
                label = "%s -> %s" % (parentLabel, obj.getLastName())
        return label

    def getObjectInfo(self, obj):

        def stringToInfo():
            """ String objects converted to info dictionary for the tree"""

            value = obj.get()
            infoStr = {'key': value, 'text': value, 'values': '', 'open': True}
            if hasattr(obj, '_parentKey'):
                infoStr['parent'] = self.inputParentDict[obj._parentKey]
            return infoStr

        def labelToValue(label, key, name):
            """ To tolerate str(labelObj) in case xmippLib is missing, but
            still being able to open a project."""
            try:
                value = str(label)
            except Exception as e:
                print("Can not convert object %s - %s to string." % (key, name))
                value = str(e)

            return value

        def pointerToInfo():
            """ Converts a Pointer into an info dictionary for the tree"""

            namePtr = obj.getLastName()
            # Remove ugly item notations inside lists
            namePtr = namePtr.replace('__item__000', '')
            # Consider Pointer as inputs
            imagePtr = getattr(obj, '_icon', '')
            parentPtr = self.inputParentDict[obj._parentKey]

            suffix = ''
            if obj.hasExtended():
                # getExtended method remove old attributes conventions.
                extendedValue = obj.getExtended()
                if obj.hasExtended():
                    suffix = '[%s]' % extendedValue
                # else:
                #     suffix = '[Item %s]' % extendedValue

                # Tolerate loading projects:
                # When having only the project sqlite..an obj.get() will
                # the load of the set...and if it is missing this whole
                # "thread" fails.
                try:
                    labelObjPtr = obj.get()
                    if labelObjPtr is None:
                        labelObjPtr = obj.getObjValue()
                        suffix = ''

                except Exception:
                    return {'parent': parentPtr, 'image': imagePtr, 'text': namePtr,
                            'values': ("Couldn't read object attributes.",)}
            else:
                labelObjPtr = obj.get()

            objKeyPtr = obj._parentKey + str(labelObjPtr.getObjId())
            labelPtr = self.getObjectLabel(labelObjPtr,
                                        self.mapper.getParent(labelObjPtr))
            namePtr += '   (from %s %s)' % (labelPtr, suffix)
            valuePtr = labelToValue(labelObjPtr, objKeyPtr, namePtr)
            infoPtr = {'key': objKeyPtr, 'parent': parentPtr, 'image': imagePtr,
                    'text': namePtr, 'values': (valuePtr,)}

            return infoPtr


        if obj is None or not obj.hasValue():
            return None

        if isinstance(obj, pwobj.String):
            info = stringToInfo()
        else:
            # All attributes are considered output, unless they are pointers
            image = Icon.ACTION_OUT
            parent = self.outputStr

            if isinstance(obj, pwobj.Pointer):
                info = pointerToInfo()
            else:
                name = self.getObjectLabel(obj, self.protocol)
                objKey = str(obj.getObjId())
                labelObj = obj
                value = labelToValue(labelObj, objKey, name)
                info = {'key': objKey, 'parent': parent, 'image': image,
                        'text': name, 'values': (value,)}
        return info

class ProtocolTreeConfig:
    """ Handler class that groups functions and constants
    related to the protocols tree configuration.
    """
    ALL_PROTOCOLS = "All"
    TAG_PROTOCOL_DISABLED = 'protocol-disabled'
    TAG_PROTOCOL = 'protocol'
    TAG_SECTION = 'section'
    TAG_PROTOCOL_GROUP = 'protocol_group'
    TAG_PROTOCOL_BETA = 'protocol_beta'
    TAG_PROTOCOL_NEW = 'protocol_new'
    TAG_PROTOCOL_UPDATED = 'protocol_updated'
    PLUGIN_CONFIG_PROTOCOLS = 'protocols.conf'

    @classmethod
    def getProtocolTag(cls, isInstalled, isBeta=False, isNew=False, isUpdated=False):
        """ Return the proper tag depending if the protocol is installed or not.
        """
        if isInstalled:
            if isBeta:
                return cls.TAG_PROTOCOL_BETA
            elif isNew:
                return cls.TAG_PROTOCOL_NEW
            elif isUpdated:
                return cls.TAG_PROTOCOL_UPDATED
            return cls.TAG_PROTOCOL
        else:
            return cls.TAG_PROTOCOL_DISABLED

    @classmethod
    def __addToTree(cls, menu, item, checkFunction=None):
        """ Helper function to recursively add items to a menu.
        Add item (a dictionary that can contain more dictionaries) to menu
        If check function is added will use it to check if the value must be added.
        """
        children = item.pop('children', [])

        if checkFunction is not None:
            add = checkFunction(item)
            if not add:
                return
        subMenu = menu.addSubMenu(**item)  # we expect item={'text': ...}
        for child in children:
            cls.__addToTree(subMenu, child, checkFunction)  # add recursively to sub-menu

        return subMenu

    @classmethod
    def __inSubMenu(cls, child, subMenu):
        """
        Return True if child belongs to subMenu
        """
        for ch in subMenu:
            if cls.__isProtocol(child):
                if ch.value is not None and ch.value == child['value']:
                    return ch
            elif ch.text == child['text']:
                return ch
        return None

    @classmethod
    def _orderSubMenu(cls, session):
        """
        Sort all children of a given section:
        The protocols first, then the sections (the 'more' section at the end)
        """

        def sortWhenLastIsAProtocol():
            """ Sorts children when the last is a protocol"""
            for i in range(lastChildPos - 1, -1, -1):
                if childs[i].tag == cls.TAG_PROTOCOL:
                    break
                else:
                    tmp = childs[i + 1]
                    childs[i + 1] = childs[i]
                    childs[i] = tmp

        def sortWhenLastIsNotAProtocol():
            """ Sorts children when the last is NOT a protocol"""
            for i in range(lastChildPos - 1, -1, -1):
                if childs[i].tag == cls.TAG_PROTOCOL:
                    break
                elif 'more' in str(childs[i].text).lower():
                    tmp = childs[i + 1]
                    childs[i + 1] = childs[i]
                    childs[i] = tmp

        lengthSession = len(session.childs)
        if lengthSession > 1:
            childs = session.childs
            lastChildPos = lengthSession - 1
            if childs[lastChildPos].tag == cls.TAG_PROTOCOL:
                sortWhenLastIsAProtocol()
            else:
                sortWhenLastIsNotAProtocol()

    @classmethod
    def __findTreeLocation(cls, subMenu, children, parent):
        """
        Locate the protocol position in the given view
        """
        for child in children:
            sm = cls.__inSubMenu(child, subMenu)
            if sm is None:
                cls.__addToTree(parent, child, cls.__checkItem)
                cls._orderSubMenu(parent)
            elif child['tag'] == cls.TAG_PROTOCOL_GROUP or child['tag'] == cls.TAG_SECTION:
                cls.__findTreeLocation(sm.childs, child['children'], sm)
    @classmethod
    def __isProtocol(cls, dict):
        """ True inf the item has a key named tag with protocol as value"""
        return dict["tag"] == cls.TAG_PROTOCOL

    @classmethod
    def __isProtocolNode(cls, node):
        """ True if tag attribute is protocol"""
        return node.tag == cls.TAG_PROTOCOL


    @classmethod
    def __checkItem(cls, item):
        """ Function to check if the protocol has to be added or not.
        Params:
            item: {"tag": "protocol", "value": "ProtImportMovies",
                   "text": "import movies"}
        """
        if not cls.__isProtocol(item):
            return True

        # It is a protocol as this point, get the class name and
        # check if it is disabled
        protClassName = item["value"]
        protClass = Config.getDomain().getProtocols().get(protClassName)
        icon = Icon.PRODUCTION
        if protClass is not None:
            if protClass.isBeta():
                icon = Icon.BETA
            elif protClass.isNewDev():
                icon = Icon.NEW
            elif protClass.isUpdated():
                icon = Icon.UPDATED
        item['icon'] = icon
        return False if protClass is None else not protClass.isDisabled()

    @classmethod
    def __addAllProtocols(cls, domain, protocols):
        # Add all protocols
        allProts = domain.getProtocols()

        # Sort the list
        allProtsSorted = sorted(allProts.items(), key=lambda e: e[1].getClassLabel())

        allProtMenu = ProtocolConfig(cls.ALL_PROTOCOLS)
        packages = {}

        # Group protocols by package name
        for k, v in allProtsSorted:
            if isAFinalProtocol(v, k):
                packageName = v.getPlugin().getName()

                # Get the package submenu
                packageMenu = packages.get(packageName)

                # If no package menu available
                if packageMenu is None:
                    # Add it to the menu ...
                    packageLine = {"tag": "package", "value": packageName,
                                   "text": packageName}
                    packageMenu = cls.__addToTree(allProtMenu, packageLine)

                    # Store it in the dict
                    packages[packageName] = packageMenu

                # Add the protocol
                tag = cls.getProtocolTag(v.isInstalled(), v.isBeta(), v.isNewDev(), v.isUpdated())

                protLine = {"tag": tag, "value": k,
                            "text": v.getClassLabel(prependPackageName=False)}

                cls.__addToTree(packageMenu, protLine)

        protocols[cls.ALL_PROTOCOLS] = allProtMenu

    @classmethod
    def __addProtocolsFromConf(cls, protocols, protocolsConfPath):
        """
        Load the protocols in the tree from a given protocols.conf file,
        either the global one in Scipion or defined in a plugin.
        """

        def addProtocols():
            """ Adds protocols defined in the "PROTOCOLS" section of the config file. """
            for menuName in cp.options('PROTOCOLS'):
                if menuName not in protocols:  # The view has not been inserted
                    menu = ProtocolConfig(menuName)
                    children = json.loads(cp.get('PROTOCOLS', menuName))
                    for child in children:
                        cls.__addToTree(menu, child, cls.__checkItem)
                    protocols[menuName] = menu
                else:  # The view has been inserted
                    menu = protocols.get(menuName)
                    children = json.loads(cp.get('PROTOCOLS',
                                                 menuName))
                    cls.__findTreeLocation(menu.childs, children, menu)

        # Populate the protocols menu from the plugin config file.
        if os.path.exists(protocolsConfPath):
            cp = ConfigParser()
            cp.optionxform = str  # keep case
            cp.read(protocolsConfPath)
            #  Ensure that the protocols section exists
            if cp.has_section('PROTOCOLS'):
                addProtocols()

    @classmethod
    def load(cls, domain, protocolsConf):
        """ Read the protocol configuration from a .conf file similar to the
        one in scipion/config/protocols.conf,
        which is the default one when no file is passed.
        """
        protocols = dict()
        # Read the protocols.conf from Scipion (base) and create an initial
        # tree view
        cls.__addProtocolsFromConf(protocols, protocolsConf)

        # Read the protocols.conf of any installed plugin
        pluginDict = domain.getPlugins()

        for pluginName in pluginDict.keys():
            try:

                # if the plugin has a path
                if pwutils.isModuleLoaded(pluginName) and pwutils.isModuleAFolder(pluginName):
                    # Locate the plugin protocols.conf file
                    protocolsConfPath = os.path.join(
                        pluginDict[pluginName].__path__[0],
                        cls.PLUGIN_CONFIG_PROTOCOLS)
                    cls.__addProtocolsFromConf(protocols, protocolsConfPath)

            except Exception as e:
                print('Failed to read settings. The reported error was:\n  %s\n'
                      'To solve it, fix %s and run again.' % (
                          e, os.path.abspath(protocolsConfPath)))

        # Clean empty sections
        cls._hideEmptySections(protocols)

        # Add all protocols to All view
        cls.__addAllProtocols(domain, protocols)

        return protocols

    @classmethod
    def _hideEmptySections(cls, protocols):
        """ Cleans all empty sections in the tree"""

        for protConf in protocols.values():
            cls._setVisibility(protConf)

    @classmethod
    def _setVisibility(cls, node):
        """ Sets the visibility of a node based on the presence of a leaf hanging form it"""
        if cls.__isProtocolNode(node):
            # Default visibility value is true. No need to set it again
            return True

        anyLeaf = False

        for child in node.childs:
            # NOTE: since python short circuits this, _setVisibility must be called always. So not swap!!
            anyLeaf = cls._setVisibility(child) or anyLeaf

        node.visible = anyLeaf

        return anyLeaf


class ProtocolConfig(MenuConfig):
    """Store protocols configuration """

    def __init__(self, text=None, value=None, **args):
        MenuConfig.__init__(self, text, value, **args)
        if 'openItem' not in args:
            self.openItem = self.tag != 'protocol_base'

    def addSubMenu(self, text, value=None, shortCut=None, **args):
        if 'icon' not in args:
            tag = args.get('tag', None)
            if tag == 'protocol_base':
                args['icon'] = Icon.GROUP

        args['shortCut'] = shortCut
        return MenuConfig.addSubMenu(self, text, value, **args)

    def __str__(self):
        return self.text