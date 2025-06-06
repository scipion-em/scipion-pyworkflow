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


import re
import collections

from pyworkflow.object import *
from .constants import *

BIN_THREADS_PARAM = 'binThreads'
PARALLELIZATION = 'Parallelization'

class FormElement(Object):
    """Base for any element on the form"""
    ATTRIBUTES = ['label', 'expertLevel', 'condition', 'important', 'help',
                  'default', 'paramClass']
    
    def __init__(self, **args):
        super().__init__(**args)
        self.label = String(args.get('label', None))
        self.expertLevel = Integer(args.get('expertLevel', LEVEL_NORMAL))
        self.condition = String(args.get('condition', None))
        self._isImportant = Boolean(args.get('important', False))
        self.help = String(args.get('help', None))
        # This two list will be filled by the Form
        # which have a global-view of all parameters
        # All param names in which condition appears this param
        self._dependants = []
        # All param names that appears in the condition
        self._conditionParams = []
        
    def isExpert(self):
        return self.expertLevel > LEVEL_NORMAL
    
    def setExpert(self):
        self.expertLevel.set(LEVEL_ADVANCED)
        
    def isImportant(self):
        return self._isImportant.get()
    
    def setImportant(self, value):
        self._isImportant.set(value)
    
    def hasCondition(self):
        return self.condition.hasValue()
    
    def getLabel(self):
        return self.label.get()

    def getHelp(self):
        return self.help.get()
    
    def config(self, **kwargs):
        """ Configure the object and set attributes
        coming in the keyword-arguments, the 
        same as in the __init__
        """
        for key in self.ATTRIBUTES:
            if key in kwargs:
                self.setAttributeValue(key, kwargs.get(key)) 
    
        
class Param(FormElement):
    """Definition of a protocol parameter"""
    def __init__(self, **args):
        FormElement.__init__(self, **args)
        # This should be defined in subclasses
        self.paramClass = args.get('paramClass', None)
        self.default = String(args.get('default', None))

        # Allow pointers (used for scalars)
        self.allowsPointers = args.get('allowsPointers', False)
        self.validators = args.get('validators', [])
        self.readOnly = args.get("readOnly", False)
        
    def __str__(self):
        return "    label: %s" % self.label.get()
    
    def addValidator(self, validator):
        """ Validators should be callables that 
        receive a value and return a list of errors if so.
        If everything is ok, the result should be an empty list.
        """
        self.validators.append(validator)
        
    def validate(self, value):
        errors = []
        for val in self.validators:
            errors += val(value)
        return errors
    
    def getDefault(self):
        return self.default.get()
    
    def setDefault(self, newDefault):
        self.default.set(newDefault)
    
    
class ElementGroup(FormElement):
    """ Class to group some params in the form.
    Such as: Labeled group or params in the same line. 
    """
    def __init__(self, form=None, **args):
        FormElement.__init__(self, **args)
        self._form = form
        self._paramList = []    
    
    def iterParams(self):
        """ Return key and param for every child param. """
        for name in self._paramList:
            yield name, self._form.getParam(name)

    def addParam(self, paramName, ParamClass, **kwargs):
        """Add a new param to the group"""
        param = ParamClass(**kwargs)
        self._paramList.append(paramName)
        self._form.registerParam(paramName, param)
        return param
    
    def addHidden(self, paramName, ParamClass, **kwargs):
        """Add a hidden parameter to be used in conditions. """
        kwargs.update({'label': '', 'condition': 'False'})
        self.addParam(paramName, ParamClass, **kwargs)

    def addLine(self, lineName, **kwargs):
        
        labelName = lineName
        for symbol in ' ()':
            labelName = labelName.replace(symbol, '_')
        
        return self.addParam(labelName, Line, form=self._form, 
                             label=lineName, **kwargs)        
    
    
# ----------- Some type of ElementGroup --------------------------

class Line(ElementGroup):
    """ Group to put some parameters in the same line. """
    pass


class Group(ElementGroup):
    """ Group some parameters with a labeled frame. """
    pass

    
class Section(ElementGroup):
    """Definition of a section to hold other params"""
    def __init__(self, form, **args):
        ElementGroup.__init__(self, form, **args)
        self.questionParam = String(args.get('questionParam', ''))
    
    def hasQuestion(self):
        """Return True if a question param was set"""
        return self.questionParam.get() in self._paramList
    
    def getQuestionName(self):
        """ Return the name of the question param. """
        return self.questionParam.get()
    
    def getQuestion(self):
        """ Return the question param"""
        return self._form.getParam(self.questionParam.get())

    def addGroup(self, groupName, **kwargs):
        labelName = groupName
        for symbol in ' ()':
            labelName = labelName.replace(symbol, '_')
        
        return self.addParam(labelName, Group, form=self._form, 
                             label=groupName, **kwargs)
        

class Form(object):
    """Store all sections and parameters"""
    def __init__(self, protocol):
        """ Build a Form from a given protocol. """
        object.__init__(self)
        self._sectionList = []  # Store list of sections
        # Dictionary to store all params, grouped by sections
        self._paramsDict = collections.OrderedDict()
        self._lastSection = None
        self._protocol = protocol
        self.addGeneralSection()
        
    def getClass(self):
        return type(self)
        
    def addSection(self, label='', updateSection=True, **kwargs):
        """Add a new section"""
        newSection = Section(self, label=label, **kwargs)
        if updateSection:
            self.lastSection = newSection
        self._sectionList.append(newSection)
        return newSection

    def getSection(self, label):
        """ get section by label from _sectionList"""
        for s in self._sectionList:
            if s.label == label:
                return s
        return

    def hasSection(self, label):
        return self.getSection(label) is not None

    def addGroup(self, *args, **kwargs):
        return self.lastSection.addGroup(*args, **kwargs)
    
    def addLine(self, *args, **kwargs):
        return self.lastSection.addLine(*args, **kwargs)      

    def registerParam(self, paramName, param):
        """ Register a given param in the form. """
        self._paramsDict[paramName] = param        
        self._analizeCondition(paramName, param)
        
    def addParam(self, *args, **kwargs):
        """Add a new param to last section"""
        if args[0] == BIN_THREADS_PARAM:
            section = self.getParallelSection(updateSection=False)
        else:
            section = self.lastSection
        return section.addParam(*args, **kwargs)

    # Adhoc method for specific params
    def addBooleanParam(self, name, label, help, default=True, **kwargs):
        return self.addParam(name, BooleanParam, label=label, help=help, default=default, **kwargs)

    def addHidden(self, *args, **kwargs):
        return self.lastSection.addHidden(*args, **kwargs)
    
    def _analizeCondition(self, paramName, param):
        if param.hasCondition():
            param._conditionParams = []
            tokens = re.split(r'\W+', param.condition.get())
            for t in tokens:
                if self.hasParam(t):
                    self.getParam(t)._dependants.append(paramName)
                    param._conditionParams.append(t)
                if self._protocol.hasAttribute(t):
                    param._conditionParams.append(t)
                    
    def evalParamCondition(self, paramName):
        """Evaluate if a condition is True for a give param
        with the values of a particular Protocol"""
        param = self.getParam(paramName)

        if not param.hasCondition():
            return True
        condStr = param.condition.get()
        localDict = {}
        globalDict = dict(globals())
        # FIXME: Check why this import is here
        from pyworkflow import Config
        globalDict.update(Config.getDomain().getObjects())

        for t in param._conditionParams:
            if self.hasParam(t) or self._protocol.hasAttribute(t):
                localDict[t] = self._protocol.getAttributeValue(t)

        return eval(condStr, globalDict, localDict)
    
    def validateParams(self, protocol):
        """ Check that all validations of the params in the form
        are met for the protocol param values.
        It will return a list with errors, just in the same
        way of the Protocol.validate function
        """
        errors = []
        
        for name, param in self.iterParams():
            value = protocol.getAttributeValue(name)
            errors += param.validate(value)
        
        return errors
        
    def getParam(self, paramName):
        """Retrieve a param given a the param name
        None is returned if not found
        """        
        return self._paramsDict.get(paramName, None)
    
    def hasParam(self, paramName):
        return paramName in self._paramsDict
        
    def __str__(self):
        s = "Form: \n"
        for section in self.iterSections():
            s += str(section)
        return s
    
    def iterSections(self):
        return self._sectionList
    
    def iterAllParams(self):
        """ Iter all parameters, including ElementGroups. """
        return self._paramsDict.items()
    
    def iterParams(self):
        """ Iter parameters disregarding the ElementGroups. """
        for k, v in self._paramsDict.items():
            if not isinstance(v, ElementGroup):
                yield k, v
        
    def iterPointerParams(self):
        for paramName, param in self._paramsDict.items():
            if isinstance(param, PointerParam):
                yield paramName, param

    def addGeneralSection(self):
        self.addSection(label='General')
        self.addParam('runName', StringParam, label="Run name:", important=True, 
                      help='Select run name label to identify this run.')
        self.addParam('runMode', EnumParam, choices=['resume', 'restart'],
                      label="Run mode", display=EnumParam.DISPLAY_COMBO, default=0,
                      help='The <resume> mode will try to start the execution'
                           'from the last successfully finished step if possible.'
                           'On the contrary, <restart> will delete all previous results'
                           'of this particular run and start from the beginning. This option'
                           'should be used carefully.'
                      )

    def getParallelSection(self, updateSection=True):
        section = self.getSection(PARALLELIZATION)
        return section if section else self.addSection(label=PARALLELIZATION, updateSection=updateSection)
  
    def addParallelSection(self, threads=1, mpi=8, binThreads=0, binThreadsHelp=None):

        """ Adds the parallelization section to the form
            pass threads=0 to disable threads parameter and mpi=0 to disable mpi params

        :param threads: default value for of threads, defaults to 1
        :param mpi: default value for mpi, defaults to 8
        :param binThreads: Threads to pass as an argument to the program
        """
        self.addSection(label=PARALLELIZATION)
        self.addParam('hostName', StringParam, default="localhost",
                      label='Execution host',
                      help='Select in which of the available do you want to launch this protocol.')

        # WARNING. THis is confusing but is described here. For legacy reasons it is not obvious how to disentangle this
        # threads ahs 2 meanings:
        # 1.- threads for the binary when execution mode is serial
        # 2.- threads for Scipion when execution mode is parallel
        # In this case (#2), there could be a binThreads which are the binary threads as in #1 case

        binLabel = "Threads"
        binHelpMsg = ("*Threads*:\nThis refers to different execution threads in the same process that "
                   "can share memory. They run in the same computer. This value is an argument"
                   " passed to the program integrated")
        binHelpMsg = binThreadsHelp if binThreadsHelp else binHelpMsg

        if threads > 0:

            label= "Scipion threads"
            helpMsg= ("*Scipion threads*:\n threads created by Scipion to run the steps."
                            " 1 thread is always used by the master/main process. Then extra threads will allow"
                            " this protocol to run several steps at the same time, taking always into account "
                            "restrictions to previous steps and 'theoretical GPU availability'")

            if self._protocol.modeSerial():
                label = binLabel
                helpMsg = binHelpMsg


            self.addParam('numberOfThreads', IntParam, default=threads,
                          label=label, help=helpMsg)
        if mpi > 0:
            mpiHelp=("*MPI*:\nThis is a number of independent processes"
                         " that communicate through message passing "
                         "over the network (or the same computer).\n")
            self.addParam('numberOfMpi', IntParam, default=mpi,
                          label='MPIs', help=mpiHelp)
        if binThreads:
            if self._protocol.modeParallel():
                self.addParam(BIN_THREADS_PARAM, IntParam, default=binThreads,
                              label=binLabel, help=binHelpMsg)
            else:
                logger.warning("binThreads can't be used when stepsExecutionMode is not STEPS_PARALLEL. Use threads instead.")


class StringParam(Param):
    """Param with underlying String value"""
    def __init__(self, **args):
        Param.__init__(self, paramClass=String, **args)


class TextParam(StringParam):
    """Long string params"""
    def __init__(self, **args):
        StringParam.__init__(self, **args)
        self.height = args.get('height', 5)
        self.width = args.get('width', 30)        
        

class RegexParam(StringParam):
    """Regex based string param"""
    pass


class PathParam(StringParam):
    """Param for path strings"""
    pass


# TODO: Handle filter pattern
class FileParam(PathParam):
    """Filename path"""
    pass


class FolderParam(PathParam):
    """Folder path"""
    pass


class LabelParam(StringParam):
    """ Just the same as StringParam, but to be rendered
    as a label and can not be directly edited by the user
    in the Protocol Form.
    """
    pass

        
class IntParam(Param):
    def __init__(self, **args):
        Param.__init__(self, paramClass=Integer, **args)
        self.addValidator(Format(int, error="should be an integer",
                                 allowsNull=args.get('allowsNull', False)))
        
        
class EnumParam(IntParam):
    """Select from a list of values, separated by comma"""
    # Possible values for display
    DISPLAY_LIST = 0
    DISPLAY_COMBO = 1
    DISPLAY_HLIST = 2  # horizontal list, save space
    
    def __init__(self, **args):
        IntParam.__init__(self, **args)
        self.choices = args.get('choices', [])
        self.display = Integer(args.get('display', EnumParam.DISPLAY_COMBO))
    
    
class FloatParam(Param):
    def __init__(self, **args):
        Param.__init__(self, paramClass=Float, **args)
        self.addValidator(Format(float, error="should be a float",
                                 allowsNull=args.get('allowsNull', False)))

        
class BooleanParam(Param):
    """ Param to store boolean values. By default it will be displayed as 2 radio buttons with Yes/no labels.
    Alternatively, if you pass checkbox it will be displayed as a checkbox.

    :param display: (Optional) default DISPLAY_YES_NO.  (Yes /no)
                    Alternatively use BooleanParam.DISPLAY_CHECKBOX to use checkboxes """
    DISPLAY_YES_NO = 1
    DISPLAY_CHECKBOX = 2

    def __init__(self, display=DISPLAY_YES_NO, **args):
        Param.__init__(self, paramClass=Boolean, **args)
        self.display = display
        self.addValidator(NonEmptyBool)


class HiddenBooleanParam(BooleanParam):
    def __init__(self, **args):
        Param.__init__(self, paramClass=Boolean, **args)

        
class PointerParam(Param):
    """ This type of Param will serve to select existing objects
    in the database that will be input for some protocol.
    """
    def __init__(self,  paramClass=Pointer, **args):
        Param.__init__(self, paramClass=paramClass, **args)
        # This will be the class to be pointed
        self.setPointerClass(args['pointerClass'])
        # Some conditions on the pointed candidates
        self.pointerCondition = String(args.get('pointerCondition', None))
        self.allowsNull = Boolean(args.get('allowsNull', False))
        
    def setPointerClass(self, newPointerClass):

        # Tolerate passing classes instead of their names
        if isinstance(newPointerClass, list):
            self.pointerClass = CsvList()
            self.pointerClass.set(",". join([clazz.__name__ for clazz in newPointerClass]))

        elif(isinstance(newPointerClass, str)):
            if ',' in newPointerClass:
                self.pointerClass = CsvList()
                self.pointerClass.set(newPointerClass)
            else:
                self.pointerClass = String(newPointerClass)

        # Single class item, not the string
        else:
            self.pointerClass = String(newPointerClass.__name__)


class MultiPointerParam(PointerParam):
    """ This type of Param will serve to select objects
    with DIFFERENT types from the database to be input for some protocol.
    """
    def __init__(self, **args):
        PointerParam.__init__(self, paramClass=PointerList, **args)
        self.maxNumObjects = Integer(args.get('maxNumObjects', 100))
        self.minNumObjects = Integer(args.get('minNumObjects', 2))

        
class RelationParam(Param):
    """ This type of Param is very similar to PointerParam, since it will
    hold a pointer to another object. But, in the PointerParam, we search
    for objects of some Class (maybe with some conditions).
    Here, we search for objects related to a given attribute of a protocol
    by a given relation.
    """
    def __init__(self, **args):
        Param.__init__(self, paramClass=Pointer, **args)
        # This will be the name of the relation
        self._relationName = String(args.get('relationName'))
        # We will store the attribute name in the protocol to be 
        # used as the object for which relations will be search
        self._attributeName = String(args.get('attributeName'))
        # This specify if we want to search for childs or parents
        # of the given attribute of the protocol
        self._direction = Integer(args.get('direction', RELATION_CHILDS))
        self.allowsNull = Boolean(args.get('allowsNull', False))
        
    def getName(self):
        return self._relationName.get()
    
    def getAttributeName(self):
        return self._attributeName.get()
    
    def getDirection(self):
        return self._direction.get()       
        
        
class ProtocolClassParam(StringParam):
    def __init__(self, **args):
        StringParam.__init__(self, **args)
        self.protocolClassName = String(args.get('protocolClassName'))
        self.allowSubclasses = Boolean(args.get('allowSubclasses', False))
        
        
class DigFreqParam(FloatParam):
    """ Digital frequency param. """
    def __init__(self, **args):
        FloatParam.__init__(self, **args)
        self.addValidator(FreqValidator)
        
        
class NumericListParam(StringParam):
    """ This class will serve to have list representations as strings.
     Possible notation are:
     1000 10 1 1 -> to define a list with 4 values [1000, 10, 1, 1], or
     10x2 5x3    -> to define a list with 5 values [10, 10, 5, 5, 5]
     If you ask for more elements than in the list, the last one is repeated
    """
    def __init__(self, **args):
        StringParam.__init__(self, **args)
        self.addValidator(NumericListValidator())
        
        
class NumericRangeParam(StringParam):
    """ This class will serve to specify range of numbers with a string representation.
     Possible notation are::

        "1,5-8,10" -> [1,5,6,7,8,10]
        "2,6,9-11" -> [2,6,9,10,11]
        "2 5, 6-8" -> [2,5,6,7,8]

    """
    def __init__(self, **args):
        StringParam.__init__(self, **args)
        self.addValidator(NumericRangeValidator())
        
        
class TupleParam(Param):
    """ This class will condense a tuple of several
    other params of the same type and related concept.
    For example: min and max, low and high.
    """
    def __init__(self, **args):
        Param.__init__(self, **args)


class DeprecatedParam:
    """ Deprecated param. To be used when you want to rename an existing param
    and still be able to recover old param value. It acts like a redirector, passing the
    value received when its value is set to the new renamed parameter

    usage: In defineParams method, before the renamed param definition line add the following:

    self.oldName = DeprecatedParam("newName", self)
    form.addParam('newName', ...)

    """
    def __init__(self, newParamName, prot):
        """

        :param newParamName: Name of the renamed param
        :param prot: Protocol hosting this and the renamed param

        """
        self._newParamName = newParamName
        self.prot = prot
        # Need to fake being a Object at loading time
        self._objId = None
        self._objIsPointer = False

    def set(self, value, cleanExtended=False):
        if hasattr(self.prot, self._newParamName):
            newParam = self._getNewParam()
            if newParam.isPointer():
                newParam.set(value, cleanExtended)
                self._extended = newParam._extended
            else:
                newParam.set(value)

    def isPointer(self):
        return self._getNewParam().isPointer()

    def getObjValue(self):
        return None

    def _getNewParam(self):
        return getattr(self.prot, self._newParamName)

# -----------------------------------------------------------------------------
#         Validators
# -----------------------------------------------------------------------------
class Validator(object):
    pass


class Conditional(Validator):
    """ Simple validation based on a condition. 
    If the value doesn't meet the condition,
    the error will be returned.
    """
    def __init__(self, error, allowsNull=False):
        self.error = error
        self._allowsNull = allowsNull
        
    def __call__(self, value):
        errors = []
        if value is not None or not self._allowsNull:
            if not self._condition(value):
                errors.append(self.error)
        return errors   
    
    
class Format(Conditional):
    """ Check if the format is right. """
    def __init__(self, valueType, error='Value have not a correct format',
                 allowsNull=False):
        Conditional.__init__(self, error, allowsNull)
        self.valueType = valueType
        
    def _condition(self, value):
        try:
            self.valueType(value)
            return True
        except Exception:
            return False


class NonEmptyCondition(Conditional):
    def __init__(self, error='Value cannot be empty'):
        Conditional.__init__(self, error)
        self._condition = lambda value: len(value) > 0
        
        
class LT(Conditional):
    def __init__(self, threshold,
                 error='Value should be less than the threshold'):
        Conditional.__init__(self, error)
        self._condition = lambda value: value < threshold
        
        
class LE(Conditional):
    def __init__(self, threshold,
                 error='Value should be less or equal than the threshold'):
        Conditional.__init__(self, error)
        self._condition = lambda value: value <= threshold
        
        
class GT(Conditional):
    def __init__(self, threshold,
                 error='Value should be greater than the threshold'):
        Conditional.__init__(self, error)
        self._condition = lambda value: value > threshold


class GE(Conditional):
    def __init__(self, thresold, error='Value should be greater or equal than the threshold'):
        Conditional.__init__(self, error)
        self._condition = lambda value: value is not None and value >= thresold


class Range(Conditional):
    def __init__(self, minValue, maxValue, error='Value is outside range'):
        Conditional.__init__(self, error)
        self._condition = lambda value: minValue <= value <= maxValue
        
        
class NumericListValidator(Conditional):
    """ Validator for ListParam. See ListParam. """
    def __init__(self, error='Incorrect format for numeric list param'):
        Conditional.__init__(self, error)
        
    def _condition(self, value):
        try:
            parts = re.split(r"[x\s]", value)
            parts = list(filter(None, parts))
            for p in parts:
                float(p)
            return True
        except Exception:
            return False


class NumericRangeValidator(Conditional):
    """ Validator for RangeParam. See RangeParam. """

    def __init__(self, error='Incorrect format for numeric range param'):
        Conditional.__init__(self, error)

    def _condition(self, value):
        try:
            parts = re.split(r"[-,\s]", value)
            parts = list(filter(None, parts))
            for p in parts:
                float(p)
            return True
        except Exception:
            return False


class NonEmptyBoolCondition(Conditional):
    def __init__(self, error='Boolean param needs to be set.'):
        Conditional.__init__(self, error)
        self._condition = lambda value: value is not None


# --------- Some constants validators ---------------------

Positive = GT(0.0, error='Value should be greater than zero')

FreqValidator = Range(0.001, 0.5,
                      error="Digital frequencies should be between 0.001 and 0.5")

NonEmpty = NonEmptyCondition()
NonEmptyBool = NonEmptyBoolCondition()
