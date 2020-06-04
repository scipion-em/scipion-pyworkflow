# **************************************************************************
# *
# * Authors:     Yaiza Rancel (cyrancel@cnb.csic.es) [1]
# *              Pablo Conesa (pconesa@cnb.csic.es) [1]
# *              J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [2]
# *
# * [1] Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# * [2] SciLifeLab, Stockholm University
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
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
import glob
import os
import importlib
import inspect
import traceback
import types
import pkg_resources
from email import message_from_string
from collections import OrderedDict
from abc import ABCMeta, abstractmethod

import pyworkflow as pw
import pyworkflow.utils as pwutils
import pyworkflow.object as pwobj
from pyworkflow.template import Template

from .constants import *


class Domain:
    """ Class to represent the application domain.
    It will allow to specify new objects, protocols, viewers and wizards
    through the registration of new plugins.
    """

    # The following classes should be defined in subclasses of Domain
    _name = None
    _protocolClass = None
    _objectClass = pwobj.Object
    _viewerClass = None
    _wizardClass = None
    _baseClasses = {}  # Update this with the base classes of the Domain

    # Dictionaries to store different type of objects
    _plugins = {}
    _protocols = {}
    _objects = {}
    _viewers = {}
    _wizards = {}

    @classmethod
    def registerPlugin(cls, name):
        """ Register a new plugin. This function should only be called when
        creating a class with __metaclass__=PluginMeta that will trigger this.
        """
        m = importlib.import_module(name)

        # Define variables
        m.Plugin._defineVariables()
        m.Domain = cls  # Register the domain class for this module
        # TODO avoid loading bibtex here and make a lazy load like the rest.
        # Load bibtex
        m._bibtex = {}
        bib = cls.__getSubmodule(name, 'bibtex')
        if bib is not None:
            try:
                m._bibtex = pwutils.parseBibTex(bib.__doc__)
            except Exception:
                pass
        cls._plugins[name] = m  # Register the name to as a plugin

    @classmethod
    def getPlugins(cls):
        """ Return existing plugins for this Domain. """
        loaded = getattr(cls, '_pluginsLoaded', False)
        if not loaded:  # Load plugin only once
            cls._discoverPlugins()
            cls._pluginsLoaded = True
        return dict(cls._plugins)

    @classmethod
    def _discoverPlugins(cls):
        for entry_point in pkg_resources.iter_entry_points('pyworkflow.plugin'):
            cls.registerPlugin(entry_point.name)

    @classmethod
    def _discoverGUIPlugins(cls):
        for entry_point in pkg_resources.iter_entry_points('pyworkflow.guiplugin'):
            entry_point.load()

    @classmethod
    def getPlugin(cls, name):
        """ Load a given plugin name. """
        m = importlib.import_module(name)

        # if not cls.__isPlugin(m):
        #     raise Exception("Invalid plugin '%s'. "
        #                     "Class Plugin with __metaclass__=PluginMeta "
        #                     "not found" % name)
        return m

    @classmethod
    def refreshPlugin(cls, name):
        """ Refresh a given plugin name. """
        plugin = cls.getPlugin(name)
        if plugin is not None:
            fn = plugin.__file__
            fn_dir = os.path.dirname(fn) + os.sep
            module_visit = {plugin}
            module_visit_path = {fn}
            del fn

            def get_recursive_modules(module):
                """ Get all plugin modules recursively """
                for module_child in vars(module).values():
                    if isinstance(module_child, types.ModuleType):
                        fn_child = getattr(module_child, "__file__", None)
                        if (fn_child is not None) and fn_child.startswith(
                                fn_dir):
                            if fn_child not in module_visit_path:
                                module_visit.add(module_child)
                                module_visit_path.add(fn_child)
                                get_recursive_modules(module_child)

            get_recursive_modules(plugin)
            # reload all plugin modules

            while module_visit:
                for module in module_visit:
                    try:
                        importlib.reload(module)
                        module_visit.remove(module)
                        break
                    except Exception as ex:
                        pass

    @classmethod
    def __getSubclasses(cls, submoduleName, BaseClass,
                        updateBaseClasses=False):
        """ Load all detected subclasses of a given BaseClass.
        Params:
            updateBaseClasses: if True, it will try to load classes from the
                Domain submodule that was not imported as globals()
        """
        subclasses = getattr(cls, '_%s' % submoduleName)

        if not subclasses:  # Only discover subclasses once
            if updateBaseClasses:
                sub = cls.__getSubmodule(cls.getName(), submoduleName)
                if sub is not None:
                    for name in cls.getModuleClasses(sub):
                        attr = getattr(sub, name)
                        if inspect.isclass(attr) and issubclass(attr, BaseClass):
                            cls._baseClasses[name] = attr

            for pluginName, plugin in cls.getPlugins().items():
                sub = cls.__getSubmodule(pluginName, submoduleName)
                if sub is not None:
                    for name in cls.getModuleClasses(sub):
                        attr = getattr(sub, name)
                        if inspect.isclass(attr) and issubclass(attr, BaseClass):

                            # Check if the class already exists (to prevent
                            # naming collisions)
                            if name in subclasses:
                                # Get already added class plugin
                                pluginCollision = subclasses[name]._package.__name__
                                print("ERROR: Name collision (%s) detected "
                                      "while discovering %s.%s.\n"
                                      " It conflicts with %s" %
                                      (name, pluginName, submoduleName,
                                       pluginCollision))
                            else:
                                # Set this special property used by Scipion
                                attr._package = plugin
                                subclasses[name] = attr
            subclasses.update(
                pwutils.getSubclasses(BaseClass, cls._baseClasses))

        return subclasses

    @classmethod
    def getModuleClasses(cls, module):
        # Dir was used before but dir returns all imported elements
        # included those imported to be BaseClasses.
        # return dir(module)

        # Get the module name
        moduleName = module.__name__

        # Get any module class
        for name, declaredClass in inspect.getmembers(module, inspect.isclass):
            if moduleName in declaredClass.__module__:
                yield name

    @classmethod
    def getProtocols(cls):
        """ Return all Protocol subclasses from all plugins for this domain."""
        return cls.__getSubclasses('protocols', cls._protocolClass)

    @classmethod
    def getObjects(cls):
        """ Return all EMObject subclasses from all plugins for this domain."""
        return cls.__getSubclasses('objects', cls._objectClass)

    @classmethod
    def getViewers(cls):
        """ Return all Viewer subclasses from all plugins for this domain."""
        return cls.__getSubclasses('viewers', cls._viewerClass,
                                   updateBaseClasses=True)

    @classmethod
    def getWizards(cls):
        """ Return all Wizard subclasses from all plugins for this domain."""
        return cls.__getSubclasses('wizards', cls._wizardClass)

    @classmethod
    def getMapperDict(cls):
        """ Return a dictionary that can be used with subclasses of Mapper
        to store/retrieve objects (including protocols) defined in this
        Domain. """
        mapperDict = getattr(cls, '__mapperDict', None)

        if mapperDict is None:
            mapperDict = dict(pwobj.OBJECTS_DICT)
            mapperDict.update(cls.getObjects())
            mapperDict.update(cls.getProtocols())
            cls.__mapperDict = mapperDict

        return mapperDict

    @classmethod
    def getName(cls):
        """ Return the name of this Domain. """
        return cls._name

    @staticmethod
    def importFromPlugin(module, objects=None, errorMsg='', doRaise=False):
        """ This method try to import either a list of objects from the
            module/plugin or the whole module/plugin and returns what is
            imported if not fails.
            When the import fails (due to the plugin or the object is not found),
            it prints a common message + optional errorMsg;
            or it raise an error with the same message, if doRaise is True.

         -> Usages:

             # Import the whole plugin 'plugin1' as 'plug1'
             plug1 = importFromPlugin('plugin1')

             # Import a plugin's module
             pl1Cons = importFromPlugin('plug1.constants')

             # Import a single class from a plugin's module
             p1prot1 = importFromPlugin('plug1.protocols', 'prot1')

             # Import some classes from a plugin's module,
             #   the returned tuple has the same length of the second argument
             pt1, pt2, ... = importFromPlugin('plugin1.protocols',
                                              ['pt1', 'pt2', ...])
        """
        def _tryImportFromPlugin(submodule=None):
            try:
                if submodule is None:  # Import only the module
                    output = importlib.import_module(module)
                else:  # Import the class of that module
                    output = getattr(importlib.import_module(module), submodule)
                return output
            except Exception as e:
                plugName = module.split('.')[0]  # The Main module is the plugin
                errMsg = (str(e) if errorMsg == ''
                          else "%s. %s" % (str(e), errorMsg))
                Domain.__pluginNotFound(plugName, errMsg, doRaise)

        if objects is None or isinstance(objects, str):
            output = _tryImportFromPlugin(objects)
        else:
            output = tuple()
            for obj in objects:
                output += (_tryImportFromPlugin(obj), )  # append in tuple
        return output

    @classmethod
    def findClass(cls, className):
        """ Find a class object given its name.
        The search will start with protocols and then with protocols.
        """
        # FIXME: Why not also Viewers, Wizards?
        c = cls.getProtocols().get(className,
                                   cls.getObjects().get(className, None))
        if c is None:
            raise Exception("findClass: class '%s' not found." % className)
        return c

    @classmethod
    def findSubClasses(cls, classDict, className):
        """ Find all subclasses of a give className. """
        clsObj = classDict[className]
        subclasses = {}

        for k, v in classDict.items():
            if issubclass(v, clsObj):
                subclasses[k] = v
        return subclasses

    @classmethod
    def getPreferredViewers(cls, className):
        """ Find and import the preferred viewers for this class. """
        viewerNames = pw.Config.VIEWERS.get(className, [])
        if not isinstance(viewerNames, list):
            viewerNames = [viewerNames]
        viewers = []  # we will try to import them and store here
        for prefViewerStr in viewerNames:
            try:
                viewerModule, viewerClassName = prefViewerStr.rsplit('.', 1)
                prefViewer = cls.importFromPlugin(viewerModule,
                                                  viewerClassName,
                                                  doRaise=True)
                viewers.append(prefViewer)
            except Exception as e:
                print("Couldn't load \"%s\" as preferred viewer.\n"
                      "There might be a typo in your VIEWERS variable "
                      "or an error in the viewer's plugin installation"
                      % prefViewerStr)
                print(e)
        return viewers

    @classmethod
    def findViewers(cls, className, environment):
        """ Find the available viewers in this Domain for this class. """
        viewers = []
        try:
            clazz = cls.findClass(className)
            baseClasses = clazz.mro()
            preferredViewers = cls.getPreferredViewers(className)
            preferedFlag = 0

            for viewer in cls.getViewers().values():
                if environment in viewer._environments:
                    for t in viewer._targets:
                        if t in baseClasses:
                            for prefViewer in preferredViewers:
                                if viewer is prefViewer:
                                    viewers.insert(0, viewer)
                                    preferedFlag = 1
                                    break
                            else:
                                if t == clazz:
                                    viewers.insert(preferedFlag, viewer)
                                else:
                                    viewers.append(viewer)
                                break
        except Exception as e:
            # Catch if there is a missing plugin, we will get Legacy which triggers and Exception
            pass

        return viewers

    @classmethod
    def findWizards(cls, protocol, environment):
        """ Find available wizards for this class, in this Domain.
        Params:
            protocols: Protocol instance for which wizards will be search.
            environment: The environment name for wizards (e.g TKINTER)
        Returns:
            a dict with the paramName and wizards for this class."""
        return cls.__findWizardsFromDict(protocol, environment,
                                         cls.getWizards())

    @classmethod
    def printInfo(cls):
        """ Simple function (mainly for debugging) that prints basic
        information about this Domain. """
        print("Domain: %s" % cls._name)
        print("     objects: %s" % len(cls._objects))
        print("   protocols: %s" % len(cls._protocols))
        print("     viewers: %s" % len(cls._viewers))
        print("     wizards: %s" % len(cls._wizards))

    # ---------- Private methods of Domain class ------------------------------
    @staticmethod
    def __pluginNotFound(plugName, errorMsg='', doRaise=False):
        """ Prints or raise (depending on the doRaise) telling why it is failing
        """
        hint = ("   Check the plugin manager (Configuration->Plugins in "
                "Scipion manager window) \n")
        # the str casting is to work with Exceptions as errorMsg
        if 'No module named %s' % plugName in str(errorMsg):
            msgStr = " > %s plugin not found. %s" % (plugName, errorMsg)
            hint += "   or use 'scipion installp --help' in the command line "
            hint += "to install it."
        else:
            msgStr = " > error when importing from %s: %s" % (plugName, errorMsg)
            if errorMsg != '':  # if empty we know nothing...
                hint += ("   or use 'scipion installp --help --checkUpdates' "
                         "in the command line to check for upgrades,\n   "
                         "it could be a versions compatibility issue.")

        stackList = traceback.extract_stack()
        if len(stackList) > 3:
            callIdx = -3  # We use the most probable index as default
            for idx, stackLine in enumerate(stackList):
                if stackLine[0].endswith('/unittest/loader.py'):
                    callIdx = idx + 1
        else:
            callIdx = 0

        callBy = stackList[callIdx][0]
        if callBy.endswith('pyworkflow/plugin.py'):
            # This special case is to know why is failing and not where is called
            # because we know that we call all plugins.protocols at the beginning
            calling = traceback.format_exc().split('\n')[-4]
        else:
            line = stackList[callIdx][1]
            calling = "  Called by %s, line %s" % (callBy, line)

        raiseMsg = "%s\n %s\n%s\n" % (msgStr, calling, hint)
        if doRaise:
            raise Exception("\n\n" + raiseMsg)
        else:
            print(raiseMsg)

    @staticmethod
    def __getSubmodule(name, subname):
        try:
            completeModuleText = '%s.%s' % (name, subname)
            if pwutils.isModuleAFolder(name):
                return importlib.import_module(completeModuleText)
        except Exception as e:
            msg = str(e)
            # FIXME: The following is a quick and dirty way to filter
            # when the submodule is not present
            if msg != 'No module named \'%s\'' % completeModuleText:
                Domain.__pluginNotFound(completeModuleText, msg)
            return None

    @classmethod
    def __isPlugin(cls, m):
        """ Return True if the module is a Scipion plugin. """
        return m.__name__ in cls._plugins

    @staticmethod
    def __findWizardsFromDict(protocol, environment, wizDict):
        wizards = {}
        baseClasses = [c.__name__ for c in protocol.getClass().mro()]

        for wiz in wizDict.values():
            if environment in wiz._environments:
                for c, params in wiz._targets:
                    if c.__name__ in baseClasses:
                        for p in params:
                            wizards[p] = wiz
        return wizards


class Plugin:
    __metaclass__ = ABCMeta

    _vars = {}
    _homeVar = ''  # Change in subclasses to define the "home" variable
    _pathVars = []
    _supportedVersions = []
    _name = ""
    _url = ""  # For the plugin
    _condaActivationCmd = None

    @classmethod
    def _defineVar(cls, varName, defaultValue):
        """ Internal method to define variables trying to get it from the environment first. """
        cls._addVar(varName, os.environ.get(varName, defaultValue))

    @classmethod
    def _addVar(cls, varName, value):
        """ Adds a variable to the local variable dictionary directly. Avoiding the environment"""
        cls._vars[varName] = value

    @classmethod
    @abstractmethod
    def getEnviron(cls):
        """ Setup the environment variables needed to launch programs. """
        pass

    @classmethod
    def getCondaActivationCmd(cls):

        if cls._condaActivationCmd is None:
            condaActivationCmd = os.environ.get(CONDA_ACTIVATION_CMD_VAR, "")
            correctCondaActivationCmd = condaActivationCmd.replace(pw.Config.SCIPION_HOME + "/", "")
            if not correctCondaActivationCmd:
                print("WARNING!!: %s variable not defined. "
                      "Relying on conda being in the PATH" % CONDA_ACTIVATION_CMD_VAR)
            elif correctCondaActivationCmd[-1] not in [";", "&"]:
                correctCondaActivationCmd += "&&"

            cls._condaActivationCmd = correctCondaActivationCmd

        return cls._condaActivationCmd

    @classmethod
    @abstractmethod
    def _defineVariables(cls):
        """ Method to define variables and their default values.
        It will use the method _defineVar that will take a variable value
        from the environment or from an optional default value.

        This method is not supposed to be called from client code,
        except from the Domain class when registering a Plugin.
        """
        pass

    @classmethod
    @abstractmethod
    def defineBinaries(cls, env):
        """ Define required binaries in the given Environment. """
        pass

    @classmethod
    def getVar(cls, varName, defaultValue=None):
        """ Return the value of a given variable. """
        return cls._vars.get(varName, defaultValue)

    @classmethod
    def getVars(cls):
        """ Return the value of a given variable. """
        return cls._vars

    @classmethod
    def getHome(cls, *paths):
        """ Return a path from the "home" of the package
         if the _homeVar is defined in the plugin. """
        home = cls.getVar(cls._homeVar)
        return os.path.join(home, *paths) if home else ''

    @classmethod
    def getSupportedVersions(cls):
        """ Return the list of supported binary versions. """
        return cls._supportedVersions

    @classmethod
    def getActiveVersion(cls, home=None, versions=None):
        """ Return the version of the binaries that are currently active.
        In the current implementation it will be inferred from the *_HOME
        variable, so it should contain the version number in it. """
        # FIXME: (JMRT) Use the basename might aleviate the issue with matching
        # the binaries version, but we might consider to find a better solution
        home = os.path.basename(home or cls.getHome())
        versions = versions or cls.getSupportedVersions()

        for v in versions:
            if v in home:
                return v

        return ''

    @classmethod
    def getName(cls):
        return cls.__module__

    @classmethod
    def validateInstallation(cls):
        """
        Check if the binaries are properly installed and if not, return
        a list with the error messages.

        The default implementation will check if the _pathVars exists.
        """
        missing = ["%s: %s" % (var, cls.getVar(var))
                   for var in cls._pathVars if not os.path.exists(cls.getVar(var))]

        return (["Missing variables:"] + missing) if missing else []

    @classmethod
    def getPluginTemplateDir(cls):
        return os.path.join(pw.getModuleFolder(cls.getName()), 'templates')

    @classmethod
    def getTemplates(cls):
        """ Get the plugin templates from the templates directory.
            If more than one template is found or passed, a dialog is raised
            to choose one.
        """
        tempList = []
        pluginName = cls.getName()
        tDir = cls.getPluginTemplateDir()
        if os.path.exists(tDir):
            for file in glob.glob1(tDir, "*" + SCIPION_JSON_TEMPLATES):
                t = Template(pluginName, os.path.join(tDir, file))
                tempList.append(t)

        return tempList

    @classmethod
    def getUrl(cls, protClass=None):
        """ Url for the plugin to point users to it"""
        return cls._url


class PluginInfo:
    """
    Information related to a given plugin when it is installed via PIP
    """
    def __init__(self, name):
        try:
            dist = pkg_resources.get_distribution(name)
            lines = [l for l in dist._get_metadata(dist.PKG_INFO)]
            tuples = message_from_string('\n'.join(lines))

        except Exception:
            print("Plugin %s seems is not a pip module yet. "
                  "No metadata found" % name)
            tuples = message_from_string('Author: plugin in development mode?')

        self._name = name
        self._metadata = OrderedDict()

        for v in tuples.items():
            if v[0] == 'Keywords':
                break
            self._metadata[v[0]] = v[1]

    def getAuthor(self):
        return self._metadata.get('Author', "")

    def getAuthorEmail(self):
        return self._metadata.get('Author-email', '')

    def getHomePage(self):
        return self._metadata.get('Home-page', '')

    def getKeywords(self):
        return self._metadata.get('Keywords', '')



