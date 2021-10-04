#!/usr/bin/env python
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


import os
import json
import datetime as dt
from collections import OrderedDict
from configparser import ConfigParser

import pyworkflow.object as pwobj
from pyworkflow.mapper import SqliteMapper


class ProjectSettings(pwobj.Object):
    """ Store settings related to a project. """

    COLOR_MODE_STATUS = 0
    COLOR_MODE_LABELS = 1
    COLOR_MODE_AGE = 2
    COLOR_MODES = (COLOR_MODE_STATUS, COLOR_MODE_LABELS, COLOR_MODE_AGE)

    def __init__(self, confs={}, **kwargs):
        super().__init__(**kwargs)
        self.config = ProjectConfig()
        # Store the current view selected by the user
        self.currentProtocolsView = pwobj.String()
        # Store the color mode: 0= Status, 1=Labels, ...
        self.colorMode = pwobj.Integer(ProjectSettings.COLOR_MODE_STATUS)
        # Store graph nodes positions and other info
        self.nodeList = NodeConfigList()
        self.labelsList = LabelsList()  # Label list
        self.mapper = None  # This should be set when load, or write
        self.runsView = pwobj.Integer(1)  # by default the graph view
        self.readOnly = pwobj.Boolean(False)
        self.runSelection = pwobj.CsvList(int)  # Store selected runs
        self.dataSelection = pwobj.CsvList(int)  # Store selected runs
        # Some extra settings stored, now mainly used
        # from the webtools
        # Time when the project was created
        self.creationTime = pwobj.String(dt.datetime.now())
        # Number of days that this project is active
        # if None, the project will not expire
        # This is used in webtools where a limited time
        # is allowed for each project
        self.lifeTime = pwobj.Integer()
        # Set a disk quota for the project (in Gb)
        # if None, quota is unlimited
        self.diskQuota = pwobj.Integer()

    def commit(self):
        """ Commit changes made. """
        self.mapper.commit()

    def getRunsView(self):
        return self.runsView.get()

    def setRunsView(self, value):
        self.runsView.set(value)

    def getReadOnly(self):
        return self.readOnly.get()

    def setReadOnly(self, value):
        self.readOnly.set(value)

    def getCreationTime(self):
        return self.creationTime.datetime()

    def setCreationTime(self, value):
        self.creationTime.set(value)

    def getLifeTime(self):
        return self.lifeTime.get()

    def setLifeTime(self, value):
        self.lifeTime.set(value)

    def getConfig(self):
        return self.config

    def getProtocolView(self):
        return self.currentProtocolsView.get()

    def setProtocolView(self, protocolView):
        """ Set the new protocol Menu given its index.
        The new ProtocolMenu will be returned.
        """
        self.currentProtocolsView.set(protocolView)

    def getColorMode(self):
        return self.colorMode.get()

    def setColorMode(self, colorMode):
        """ Set the color mode to use when drawing the graph.
        """
        self.colorMode.set(colorMode)

    def statusColorMode(self):
        return self.getColorMode() == self.COLOR_MODE_STATUS

    def labelsColorMode(self):
        return self.getColorMode() == self.COLOR_MODE_LABELS

    def ageColorMode(self):
        return self.getColorMode() == self.COLOR_MODE_AGE

    def write(self, dbPath=None):
        self.setName('ProjectSettings')
        if dbPath is not None:
            self.mapper = SqliteMapper(dbPath, globals())
        else:
            if self.mapper is None:
                raise Exception("Can't write ProjectSettings without "
                                "mapper or dbPath")

        self.mapper.deleteAll()
        self.mapper.insert(self)
        self.mapper.commit()

    def getNodes(self):
        return self.nodeList

    def getNodeById(self, nodeId):
        return self.nodeList.getNode(nodeId)

    def addNode(self, nodeId, **kwargs):
        return self.nodeList.addNode(nodeId, **kwargs)

    def getLabels(self):
        return self.labelsList

    @classmethod
    def load(cls, dbPath):
        """ Load a ProjectSettings from dbPath. """
        classDict = dict(globals())
        classDict.update(pwobj.__dict__)
        mapper = SqliteMapper(dbPath, classDict)
        settingList = mapper.selectByClass('ProjectSettings')
        n = len(settingList)

        if n == 0:
            raise Exception("Can't load ProjectSettings from %s" % dbPath)
        elif n > 1:
            raise Exception("Only one ProjectSettings is expected in db, "
                            "found %d in %s" % (n, dbPath))

        settings = settingList[0]
        settings.mapper = mapper

        return settings


class ProjectConfig(pwobj.Object):
    """A simple base class to store ordered parameters"""

    def __init__(self, **args):
        super().__init__(**args)
        self.logo = pwobj.String('scipion_logo_small.gif')
        # Do not store this object, unless we implement some kind of
        # icon customization
        self._objDoStore = False


class MenuConfig(object):
    """Menu configuration in a tree fashion.
    Each menu can contains submenus.
    Leaf elements can contain actions"""

    def __init__(self, text=None, value=None,
                 icon=None, tag=None, **kwargs):
        """Constructor for the Menu config item.
        Arguments:
          text: text to be displayed
          value: internal value associated with the item.
          icon: display an icon with the item
          tag: put some tags to items
        **args: pass other options to base class.
        """
        self.text = text
        self.value = value
        self.icon = icon
        self.tag = tag
        self.shortCut = kwargs.get('shortCut', None)
        self.childs = pwobj.List()
        self.openItem = kwargs.get('openItem', False)

    def addSubMenu(self, text, value=None, **args):
        subMenu = type(self)(text, value, **args)
        self.childs.append(subMenu)
        return subMenu

    def __iter__(self):
        for v in self.childs:
            yield v

    def __len__(self):
        return len(self.childs)

    def isEmpty(self):
        return len(self.childs) == 0


class NodeConfig(pwobj.Scalar):
    """ Store Graph node information such as x, y. """

    def __init__(self, nodeId=0, x=None, y=None, selected=False, expanded=True,
                 visible=True):
        pwobj.Scalar.__init__(self)
        # Special node id 0 for project node
        self._values = {'id': nodeId,
                        'x': pwobj.Integer(x).get(0),
                        'y': pwobj.Integer(y).get(0),
                        'selected': selected,
                        'expanded': expanded,
                        'visible': pwobj.Boolean(visible).get(0),
                        'labels': []}

    def _convertValue(self, value):
        """Value should be a str with comma separated values
        or a list.
        """
        self._values = json.loads(value)

    def getObjValue(self):
        self._objValue = json.dumps(self._values)
        return self._objValue

    def get(self):
        return self.getObjValue()

    def getId(self):
        return self._values['id']

    def setX(self, x):
        self._values['x'] = x

    def getX(self):
        return self._values['x']

    def setY(self, y):
        self._values['y'] = y

    def getY(self):
        return self._values['y']

    def setPosition(self, x, y):
        self.setX(x)
        self.setY(y)

    def getPosition(self):
        return self.getX(), self.getY()

    def setSelected(self, selected):
        self._values['selected'] = selected

    def isSelected(self):
        return self._values['selected']

    def setExpanded(self, expanded):
        self._values['expanded'] = expanded

    def isExpanded(self):
        return self._values['expanded']

    def setVisible(self, visible):
        self._values['visible'] = visible

    def isVisible(self):
        if self._values.get('visible') is None:
            self._values['visible'] = True
        return self._values['visible']

    def setLabels(self, labels):
        self._values['labels'] = labels

    def getLabels(self):
        return self._values.get('labels', None)

    def __str__(self):
        return 'NodeConfig: %s' % self._values


class NodeConfigList(pwobj.List):
    """ Store all nodes information items and 
    also store a dictionary for quick access
    to nodes query.
    """

    def __init__(self):
        self._nodesDict = {}
        pwobj.List.__init__(self)

    def getNode(self, nodeId):
        return self._nodesDict.get(nodeId, None)

    def addNode(self, nodeId, **kwargs):
        node = NodeConfig(nodeId, **kwargs)
        self._nodesDict[node.getId()] = node
        self.append(node)
        return node

    def updateDict(self):
        self._nodesDict.clear()
        for node in self:
            self._nodesDict[node.getId()] = node

    def clear(self):
        pwobj.List.clear(self)
        self._nodesDict.clear()


class Label(pwobj.Scalar):
    """ Store Label information """

    def __init__(self, labelId=None, name='', color=None):
        pwobj.Scalar.__init__(self)
        # Special node id 0 for project node
        self._values = {'id': labelId,
                        'name': name,
                        'color': color}

    def _convertValue(self, value):
        """Value should be a str with comma separated values
        or a list.
        """
        self._values = json.loads(value)

    def getObjValue(self):
        self._objValue = json.dumps(self._values)
        return self._objValue

    def get(self):
        return self.getObjValue()

    def getId(self):
        return self._values['id']

    def getName(self):
        return self._values['name']

    def setName(self, newName):
        self._values['name'] = newName

    def setColor(self, color):
        self._values['color'] = color

    def getColor(self):
        return self._values.get('color', None)

    def __str__(self):
        return 'Label: %s' % self._values

    def __eq__(self, other):
        return self.getName() == other.getName()


class LabelsList(pwobj.List):
    """ Store all labels information"""

    def __init__(self):
        self._labelsDict = {}
        pwobj.List.__init__(self)

    def getLabel(self, name):
        return self._labelsDict.get(name, None)

    def addLabel(self, label):
        self._labelsDict[label.getName()] = label
        self.append(label)
        return label

    def updateDict(self):
        self._labelsDict.clear()
        for label in self:
            self._labelsDict[label.getName()] = label

    def deleteLabel(self, label):
        self._labelsDict.pop(label.getName())
        self.remove(label)

    def clear(self):
        pwobj.List.clear(self)
        self._labelDict.clear()
