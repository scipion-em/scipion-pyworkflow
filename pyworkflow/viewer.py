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

import pyworkflow.protocol as pwprot
from pyworkflow.utils import KEYSYM
from subprocess import call

DESKTOP_TKINTER = 'tkinter'
WEB_DJANGO = 'django'


class View(object):
    """ Represents a visualization result for some object or file.
    Views can be plots, table views, chimera scripts, commands or messages.
    """
    def show(self):
        """ This method should be overwritten to implement how
        this particular view will be displayed in desktop.
        """
        pass
    
    def toUrl(self):
        """ If the view have web implementation, this method
        should be implemented to build the url with parameters
        that will be used to respond.
        """
        pass
    
    
class CommandView(View):
    """ View for calling an external command. """
    def __init__(self, cmd, **kwargs):
        View.__init__(self)
        self._cmd = cmd
        self._env = kwargs.get('env', None)
        self._cwd = kwargs.get('cwd', None)
        
    def show(self):
        call(self._cmd, shell=True, env=self._env, cwd=self._cwd)
        

MSG_INFO = 0
MSG_WARN = 1
MSG_ERROR = 2

MSG_DICT = {MSG_INFO: 'showInfo',
            MSG_WARN: 'showWarning',
            MSG_ERROR: 'showError'}


class MessageView(View):
    """ View for some message. """
    def __init__(self, msg, title='', msgType=MSG_INFO, tkParent=None,
                 **kwargs):
        View.__init__(self)
        self._msg = msg
        self._title = title
        self._msgType = msgType
        self._tkParent = tkParent
        
    def show(self):
        import pyworkflow.gui.dialog as dialog
        func = getattr(dialog, MSG_DICT[self._msgType])
        func(self._title, self._msg, self._tkParent)
        
    def getMessage(self):
        return self._msg


class TextView(View):
    """ View for display some text file. """
    def __init__(self, filelist, title='', tkParent=None, **kwargs):
        View.__init__(self)
        self._filelist = filelist
        if title:
            self._title = title
        else:
            self._title = filelist[0]
        self._tkParent = tkParent
        
    def getFileList(self):
        return self._filelist
        
    def show(self):
        from pyworkflow.gui.text import showTextFileViewer
        showTextFileViewer(self._title, self._filelist, self._tkParent)


# ---------------- Viewers ----------------------------------------
class Viewer(object):
    """ A Viewer will provide several Views to visualize
    the data associated to data objects or protocol.
    
    The _targets class property should contain a list of string
    with the class names that this viewer is able to visualize.
    For example: _targets = ['Image', 'SetOfImages']
    """
    _targets = []
    _environments = [DESKTOP_TKINTER]
    _name = None
    
    def __init__(self, tmpPath='./Tmp', **args):
        self._tmpPath = tmpPath
        self._project = args.get('project')
        if self._project is None:
            raise Exception('Can not initialize a Viewer with None project.')
        self.protocol = args.get('protocol', None)
        self.formWindow = args.get('parent', None)
        self._keyPressed = args.get('keyPressed', None)
        self._tkRoot = self.formWindow.root if self.formWindow else None

    @classmethod
    def can_handle_this(cls, classHierarchy, instance=None):
        """ Returns none if it cannot handle the instance, otherwise returns which of the
        classes of the hierarchy it targets (used for establishing priority"""

        for t in cls._targets:
            if t in classHierarchy:

                if instance is not None and not cls.can_handle_this_instance(instance):
                    return None
                else:
                    return t

    @classmethod
    def can_handle_this_instance(cls, instance):
        return True
    def getKeyPressed(self):
        return self._keyPressed

    def shiftPressed(self):
        return self._keyPressed==KEYSYM.SHIFT

    def controlPressed(self):
        return self._keyPressed == KEYSYM.CONTROL

    def getTkRoot(self):
        return self._tkRoot

    def _getTmpPath(self, *paths):
        return os.path.join(self._tmpPath, *paths)
    
    def visualize(self, obj, **kwargs):
        """ Display each of the views, by default
        the implementation is for desktop.
        """
        for view in self._visualize(obj, **kwargs):
            view.show()
            
    def _visualize(self, obj, **kwargs):
        """ This method should make the necessary conversions
        and return the list of Views that will be used to 
        visualize the object
        """
        return []
    
    # FIXME: REMOVE THIS METHOD AFTER RE-FACTORING
    def getView(self):
        """ This method should return the string value of the view in web
        that will respond to this viewer. This method only should be implemented
        in those viewers that have WEB_DJANGO environment defined. 
        """
        return None
    
    def getProject(self):
        return self._project
    
    def setProject(self, project):
        self._project = project
        
    def getParent(self):
        """ Get the Tk parent widget. """
        return self.formWindow
        
    def infoMessage(self, msg, title='',):
        """ Build a message View of type INFO. """
        return MessageView(msg, title, msgType=MSG_INFO, tkParent=self._tkRoot)
    
    def errorMessage(self, msg, title=''):
        """ Build a message View of type INFO. """
        return MessageView(msg, title, msgType=MSG_ERROR, tkParent=self._tkRoot)  
    
    def errorList(self, errors, views, title='Visualization errors'):
        """ Convert an error list in a single Error message. """
        if errors:
            views.append(self.errorMessage('\n'.join(errors), title))
    
    def warnMessage(self, msg, title=''):
        """ Build a message View of type INFO. """
        return MessageView(msg, title, msgType=MSG_WARN, tkParent=self._tkRoot)

    def textView(self, filelist, title=''):
        return TextView(filelist, title, tkParent=self.formWindow)  
    
    def tkWindow(self, windowClass, **kwargs):
        kwargs['masterWindow'] = self.formWindow
        return windowClass(**kwargs)  

    def getProtocolId(self):
        if not hasattr(self, 'protocol'):
            raise Exception("self.protocol is not defined for this Viewer.")
        return self.protocol.strId()

    @classmethod
    def getName(cls):
        if cls._name is None:
            return cls.__name__
        return cls._name


class ProtocolViewer(Viewer, pwprot.Protocol):
    """ Special kind of viewer that have a Form to organize better
    complex visualization associated with protocol results.
    If should provide a mapping between form params and the corresponding
    functions that will return the corresponding Views.
    """

    _label ="Protocol viewer"
    def __init__(self, **kwargs):
        # Here we are going to intercept the original _defineParams function
        # and replace by an empty one, this is to postpone the definition of 
        # params until the protocol is set and then self.protocol can be used
        # for a more dynamic definition
        object.__setattr__(self, '_defineParamsBackup', self._defineParams)
        object.__setattr__(self, '_defineParams', self._defineParamsEmpty)
    
        pwprot.Protocol.__init__(self, **kwargs)
        Viewer.__init__(self, **kwargs)
        self.allowHeader.set(False)
        # This flag will be used to display a plot or return the plotter
        self.showPlot = True
        self._tkRoot = None
        self.formWindow = None
        self.setWorkingDir(self.getProject().getTmpPath())
        
    def getWindow(self):
        return self.formWindow

    @classmethod
    def getName(cls):
        return cls._label

    def getTkRoot(self):
        return self._tkRoot
    
    def _defineParamsEmpty(self, form):
        """ Just do nothing and postpone the real definition. """
        pass
    
    def setProtocol(self, protocol):
        """ Set the protocol instance to the viewer and
        call the definition of the parameters.
        """
        self.protocol = protocol
        self._defineParamsBackup(self._definition)
        self._createVarsFromDefinition()
    
    def visualize(self, obj, **args):
        """Open the Protocol GUI Form given a Protocol instance"""
        from pyworkflow.gui.form import FormWindow
        self.setProtocol(obj)
        self.windows = args.get('windows', None)
        self.formWindow = FormWindow("Protocol Viewer: " + self.getClassName(),
                                     self, self._viewAll, self.windows,
                                     visualizeDict=self.__getVisualizeWrapperDict(),
                                     visualizeMode=True)
        self.formWindow.visualizeMode = True
        self.showInfo = self.formWindow.showInfo
        self.showError = self.formWindow.showError
        self._tkRoot = self.formWindow.root
        self.formWindow.show(center=True)     
    
    def _visualizeParam(self, paramName=None):
        """ Call handler to get viewers and visualize each one. """
        errors = self.validate()
        if errors:
            errorMsg = '\n'.join(errors)
            self.showError(errorMsg, "Validation errors")
        else:
            views = self._getVisualizeDict()[paramName](paramName)
            if views:
                for v in views:
                    v.show()
            
    def __getVisualizeWrapperDict(self):
        """ Replace the True attributes handler by the generic one. """
        d = {}
        for k in self._getVisualizeDict():
            d[k] = self._visualizeParam
            
        return d        
        
    def _getVisualizeDict(self):
        """ Create the visualization dict for view individual params. """
        return {}
    
    def _viewAll(self, *args):
        """ Visualize all data give the parameters. """
        for k, v in self._getVisualizeDict().items():
            if self.getAttributeValue(k, False):
                v(k)
                
    def _citations(self):
        return self.protocol._citations()

    def validateInstallation(self):
        return

    # TODO deprecate this method, it's duplicate of one from pwutils.utils
    def _getListFromRangeString(self, rangeStr):
        """ Create a list of integer from a string with range definitions
        Examples:
        "1,5-8,10" -> [1,5,6,7,8,10]
        "2,6,9-11" -> [2,6,9,10,11]
        "2 5, 6-8" -> [2,5,6,7,8]
        """
        elements = rangeStr.split(',')
        values = []
        for e in elements:
            if '-' in e:
                limits = e.split('-')
                values += range(int(limits[0]), int(limits[1])+1)
            else:
                # If values are separated by comma also split
                values += map(int, e.split())
        return values
