# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
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
# * MERCHANTABIlITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
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
This modules holds the base classes for the ORM implementation.
The Object class is the root in the hierarchy and some other
basic classes.
"""
import logging
logger = logging.getLogger(__name__)

from collections import OrderedDict
import datetime as dt
from os.path import getmtime

from pyworkflow.utils import getListFromValues, getListFromRangeString, strToDuration
from pyworkflow.utils.reflection import getSubclasses


# Binary relations always involve two objects, we 
# call them parent-child objects, the following
# constants reflect which direction of the relation we refer
RELATION_CHILDS = 0
RELATION_PARENTS = 1

# There are other relations related to data provenance,
# which object were used to produce a result (source of it)
RELATION_SOURCE = 'relation_datasource'
RELATION_TRANSFORM = 'relation_transform'


# Then column name of the parent id relation
OBJECT_PARENT_ID = 'object_parent_id'


class Object(object):
    """ All objects in our Domain should inherit from this class
    that will contain all base properties"""

    def __init__(self, value=None, **kwargs):
        object.__init__(self)
        if len(kwargs) == 0:
            self._objIsPointer =  False  # True if will be treated as a reference for storage
            self._objId =  None  # Unique identifier of this object in some context
            self._objParentId =  None  # identifier of the parent object
            self._objName = ''  # The name of the object will contains the whole path of ancestors
            self._objLabel = ''  # This will serve to label the objects
            self._objComment = ''
            # Performance: self._objTag =  None  # This attribute serve to make some annotation on the object.
            self._objDoStore = True
        else:

            self._objIsPointer = kwargs.get('objIsPointer', False)  # True if will be treated as a reference for storage
            self._objId = kwargs.get('objId', None)  # Unique identifier of this object in some context
            self._objParentId = kwargs.get('objParentId', None)  # identifier of the parent object
            self._objName = kwargs.get('objName', '')  # The name of the object will contains the whole path of ancestors
            self._objLabel = kwargs.get('objLabel', '')  # This will serve to label the objects
            self._objComment = kwargs.get('objComment', '')
            #Performance: self._objTag = kwargs.get('objTag', None)  # This attribute serve to make some annotation on the object.
            self._objDoStore = kwargs.get('objDoStore', True)  # True if this object will be stored from his parent

        self._objCreation = None
        self._objParent = None  # Reference to parent object
        self._objEnabled = True
        self.set(value)

    @classmethod
    def getClassName(cls):
        return cls.__name__
    
    def getClass(self):
        return type(self)
    
    @classmethod
    def getDoc(cls):
        return cls.__doc__ or ''

    # FIXME: This function should be renamed to hasAttribute when we address that issue
    def hasAttributeExt(self, attrName):
        attrList = attrName.split('.')
        obj = self
        for partName in attrList:
            obj = getattr(obj, partName, None)
            if obj is None:
                return False
        return True

    # FIXME: This function is not symmetric with setAttributeValue
    def hasAttribute(self, attrName):
        return hasattr(self, attrName)

    # FIXME: This function is not symmetric with setAttributeValue
    def getAttributeValue(self, attrName, defaultValue=None):
        """ Get the attribute value given its name.
        Equivalent to getattr(self, name).get() 
        """
        attr = getattr(self, attrName, None)
        if attr is None:
            value = defaultValue
        elif callable(attr):
            value = attr()
        elif isinstance(attr, Object):
            value = attr.get()
        else:
            value = attr  # behave well for non-Object attributes
        return value
    
    def setAttributeValue(self, attrName, value, ignoreMissing=True):
        """ Set the attribute value given its name.
        Equivalent to setattr(self, name).set(value) 
        If the attrName contains dot: x.y
        it will be equivalent to getattr(getattr(self, 'x'), 'y').set(value)
        If ignoreMissing is True, non-existing attrName will not raise an
        exception.
        """
        attrList = attrName.split('.')
        obj = self
        for partName in attrList:
            obj = getattr(obj, partName, None)
            if obj is None:
                if ignoreMissing:
                    return
                raise Exception("Object.setAttributeValue: %s has no attribute %s."
                                % (self.__class__.__name__, attrName))
        obj.set(value)
        
    def getAttributes(self):
        """Return the list of attributes that are
        subclasses of Object"""
        for name in vars(self):
            value = getattr(self, name)
            if isinstance(value, Object):
                yield name, value
                
    def getAttributesToStore(self):
        """Return the list of attributes than are
        subclasses of Object and will be stored"""
        for key, attr in self.getAttributes():
            try:
                if attr is not None and attr._objDoStore:
                    yield key, attr
            except Exception as e:
                logger.info("Object.getAttributesToStore: attribute '%s' (%s) seems to "
                      "be overwritten, since '_objDoStore' was not found. Ignoring attribute." % (key, type(attr)))
                logger.debug("Exception: %s" % e)

    def isPointer(self):
        """If this is true, the value field is a pointer 
        to another object"""
        return self._objIsPointer
        
    def _convertValue(self, value):
        """Convert a value to desired scalar type"""
        return value
    
    def set(self, value):
        """Set the internal value, if it is different from None
        call the convert function in subclasses"""
        if value is not None:
            value = self._convertValue(value)            
        self._objValue = value
    
    def get(self):
        """Return internal value"""
        return self._objValue
    
    def trace(self, callback):
        """ Add an observer when the set method is called. """
        if self.set == self.__setTrace:
            pass
        else:
            self.__set = self.set 
            self.set = self.__setTrace
        self.__setCallback = callback 
        
    def __setTrace(self, value):
        self.__set(value)
        self.__setCallback()
    
    def getObjValue(self):
        """Return the internal value for storage.
        This is a good place to do some update of the
        internal value before been stored"""
        return self._objValue
    
    def getObjId(self):
        """Return object id"""
        return self._objId
    
    def setObjId(self, newId):
        """Set the object id"""
        self._objId = newId
        
    def copyObjId(self, other):
        """ Copy the object id form other to self. """
        self.setObjId(other.getObjId())
        
    def hasObjId(self):
        return self._objId is not None
    
    def cleanObjId(self):
        """ This function will set to None this object id
        and the id of all its children attributes.
        This function should be used when retrieving
        an object from a mapper and storing in a different one.
        """
        self.setObjId(None)
        for _, attr in self.getAttributesToStore():
            attr.cleanObjId()
            
    def getObjParentId(self):
        return self._objParentId
    
    def hasObjParentId(self):
        return self._objParentId is not None
            
    def getObjLabel(self):
        """ Return the label associated with this object"""
        return self._objLabel
    
    def setObjLabel(self, label):
        """ Set the label to better identify this object"""
        self._objLabel = label
             
    def getObjComment(self):
        """ Return the comment associated with this object"""
        return self._objComment
    
    def setObjComment(self, comment):
        """ Set the comment to better identify this object"""
        self._objComment = comment       
        
    def setObjCreation(self, creation):
        """ Set the creation time of the object. """
        self._objCreation = creation
        
    def getObjCreation(self):
        """ Return the stored creation time of the object. """
        return self._objCreation

    def getObjCreationAsDate(self):
        """ Return the stored creation time of the object as date """
        return String.getDatetime(self._objCreation)

    def strId(self):
        """String representation of id"""
        return str(self._objId)
    
    def getName(self):
        # TODO: REMOVE THIS FUNCTION, SINCE IT DOES NOT COMPLAIN WITH _objX naming
        return self._objName
    
    def getObjName(self):
        return self._objName
    
    def setEnabled(self, enabled):
        self._objEnabled = bool(enabled)
        
    def isEnabled(self):
        """Return if object is enabled"""
        return self._objEnabled
    
    def getNameId(self):
        """ Return an unique and readable id that identifies this object. """
        label = self.getObjLabel()
        if len(label) > 0:
            return label
        elif self.hasObjId():
            return '%s.%s' % (self.getName(), self.strId())
        return ''
    
    def getLastName(self):
        """ If the name contains parent path, remove it
        and only return the attribute name in its parent. 
        """
        if '.' in self._objName:
            return self._objName.split('.')[-1]
        return self._objName 
    
    def setName(self, name):
        self._objName = name
        
    def hasValue(self):        
        return True
    
    def getStore(self):
        """Return True if the object will be stored by the mapper"""
        return self._objDoStore
    
    def setStore(self, value):
        """set the store flag"""
        self._objDoStore = value

    def __hash__(self):
        # Issue found in scipion-em-xmipp/xmipp3/protocols/protocol_extract_particles_pairs.py (_setupBasicProperties)
        # TypeError: unhashable type: 'Micrograph'
        # Solution: Hashability makes an object usable as a dictionary key and a set member, because these data
        # structures use the hash value internally. All of Python’s immutable built_in objects are hashable, while no
        # mutable containers (such as lists or dictionaries) are. Objects which are instances of user-defined classes
        # are hashable by default; they all compare unequal, and their hash value is their id().
        # https://docs.python.org/3.1/glossary.html
        return id(self)

    def __eq__(self, other):
        """Comparison for scalars should be by value
        and for other objects by reference"""
        if self._objValue is None:
            return object.__eq__(self, other)
        return self._objValue == other._objValue
    
    def equalAttributes(self, other, ignore=[], verbose=False):
        """Compare that all attributes are equal"""
        for k, v1 in self.getAttributes():
            # v1 = getattr(self, k) # This is necessary because of FakedObject simulation of getattr
            # Skip comparison of attribute names in 'ignore' list
            if k in ignore:
                continue
            v2 = getattr(other, k)
            if issubclass(type(v1), Object):
                comp = v1.equalAttributes(v2, ignore=ignore, verbose=verbose)
            else:
                comp = v1 == v2
            if not comp:
                if verbose:
                    logger.info("Different attributes: self.%s = %s, other.%s = %s" % (k, v1, k, v2))
                return False
        return True
            
    def copyAttributes(self, other, *attrNames):
        """ Copy attributes in attrNames from other to self. 
        If the name X is in attrNames, it would be equivalent to:
        self.X.set(other.X.get())
        This method is more useful for Scalar attributes.
        There are two paths for Pointer and PointerList.
        """
        for name in attrNames:
            attr = getattr(self, name, None)
            otherAttr = getattr(other, name)

            if attr is None:
                setattr(self, name, otherAttr.clone())
            elif isinstance(attr, Pointer):
                attr.copy(otherAttr)
            elif isinstance(attr, PointerList):
                for pointer in otherAttr:
                    attr.append(pointer)
            elif isinstance(attr, Scalar):
                if otherAttr.hasPointer():
                    attr.copy(otherAttr)
                else:
                    attr.set(otherAttr.get())
            else:
                # Necessary for the correct storage of complex attributes (such as Acquisition or Transform) in
                # heterogeneous sets of sets, like the sets of tilt-series. Those sets imply append to the intermediate
                # level + append to the upper level + update the upper level, passing in the previous method version
                # through the line attr.set(otherAttr.get()), resulting in a None and copying the acquisition of the
                # set to all the elements of the set and losing the transformation info
                setattr(self, name, otherAttr.clone())
            
    def __getObjDict(self, prefix, objDict, includeClass, includePointers=True):
        if prefix:
            prefix += '.'
        for k, v in self.getAttributesToStore():
            self.fillObjDict(prefix, objDict, includeClass, k, v, includePointers=includePointers)

    @staticmethod
    def fillObjDict(prefix, objDict, includeClass, k, v, includePointers=False):

        if not v.isPointer():
            kPrefix = prefix + k
            if includeClass:
                objDict[kPrefix] = (v.getClassName(), v.getObjValue())
            else:
                objDict[kPrefix] = v.getObjValue()
            if not isinstance(v, Scalar):
                v.__getObjDict(kPrefix, objDict, includeClass)
        # Is a pointer ...
        elif includePointers and not v.pointsNone():
            # Should we take into account the prefix??
            objDict[k]=v.getUniqueId()


    def getObjDict(self, includeClass=False, includeBasic=False, includePointers=False):
        """
        Return all attributes and values in a dictionary.
        Nested attributes will be separated with a dot in the dict key.

        :param includeClass: if True, the values will be a tuple (ClassName, value)
            otherwise only the values of the attributes
        :param includeBasic: if True include the id, label and comment.
        :param includePointers: If true pointer are also added using Pointer.getUniqueId --> "2.outputTomograms"

        :return a dictionary

        includeBasic example::

            object.id: objId
            object.label: objLabel
            object.comment: objComment

        """
        d = OrderedDict()

        if includeClass:
            d['self'] = (self.getClassName(),)

        if includeBasic:
            d['object.id'] = self.getObjId()
            d['object.label'] = self.getObjLabel()
            d['object.comment'] = self.getObjComment()

        self.__getObjDict('', d, includeClass, includePointers=includePointers )

        return d

    def setAttributesFromDict(self, attrDict, setBasic=True,
                              ignoreMissing=False):
        """ Set object attributes from the dict obtained from getObjDict.
         WARNING: this function is yet experimental and not fully tested.
        """
        if setBasic:
            self.setObjId(attrDict.get('object.id', None))
            self.setObjLabel(attrDict.get('object.label', ''))
            self.setObjComment(attrDict.get('object.comment', ''))

        for attrName, value in attrDict.items():
            if not attrName.startswith('object.'):
                self.setAttributeValue(attrName, value, ignoreMissing)
            
    def __getMappedDict(self, prefix, objDict):
        if prefix:
            prefix += '.'
        for k, v in self.getAttributesToStore():
            if not v.isPointer():
                kPrefix = prefix + k
                objDict[kPrefix] = v
                if not isinstance(v, Scalar):
                    v.__getMappedDict(kPrefix, objDict)
                        
    def getMappedDict(self):
        d = OrderedDict()
        self.__getMappedDict('', d)
        return d        
    
    def getNestedValue(self, key):
        """ Retrieve the value of nested attributes like: _ctfModel.defocusU. """
        attr = self
        for p in key.split('.'):
            attr = getattr(attr, p)
        return attr.get()
    
    def getValuesFromDict(self, objDict):
        """ Retrieve the values of the attributes
        for each of the keys that comes in the objDict.
        """
        return [self.getNestedValue(k) for k in objDict if k != 'self']
    
    def getValuesFromMappedDict(self, mappedDict):
        return [v.getObjValue() for v in mappedDict.values()]
    
    def copy(self, other, copyId=True, ignoreAttrs=[], copyEnable=False):
        """
        Copy all attributes values from one object to the other.
        The attributes will be created if needed with the corresponding type.

        :param other: the other object from which to make the copy.
        :param copyId: if true, the _objId will be also copied.
        :param ignoreAttrs: pass a list with attributes names to ignore.
        :param copyEnable: Pass true if you want enabled flag to be copied

        """
        copyDict = {'internalPointers': []} 
        self._copy(other, copyDict, copyId, ignoreAttrs=ignoreAttrs, copyEnable=copyEnable)
        self._updatePointers(copyDict)
        return copyDict
        
    def _updatePointers(self, copyDict):
        """ Update the internal pointers after a copy. 
        If there are pointers to other object in the copy 
        the references should be updated.
        """
        for ptr in copyDict['internalPointers']:
            pointedId = ptr.getObjValue().getObjId()
            if pointedId in copyDict:
                ptr.set(copyDict[pointedId])
        
    def _copy(self, other, copyDict, copyId, level=1, ignoreAttrs=[], copyEnable=False):
        """ Recursively clone all attributes from one object to the other.
        (Currently, we are not deleting attributes missing in the 'other' object.)
        Params:

        :param copyDict: this dict is used to store the ids map between 'other' and
            'self' attributes. It is used for update pointers and relations
            later on. This will only work if the ids of 'other' attributes
            has been properly set.
        :param copyId: Pass true to copy the id
        :param level: (1), depth to the copy
        :param ignoreAttrs: List with attributes to ignore
        :param copyEnable: (False) pass true to copy the enable flag
        """
        # Copy basic object data
        # self._objName = other._objName
        if copyId:
            self._objId = other._objId
        self._objValue = other._objValue
        self._objLabel = other._objLabel
        self._objComment = other._objComment

        if copyEnable:
            self._objEnabled = other._objEnabled

        # Copy attributes recursively
        for name, attr in other.getAttributes():
            if name not in ignoreAttrs:
                myAttr = getattr(self, name, None)
    
                if myAttr is None:
                    myAttr = attr.getClass()()
                    setattr(self, name, myAttr)
                    
                myAttr._copy(attr, copyDict, copyId, level+2)
                # Store the attr in the copyDict
                if attr.hasObjId():
                    # storing in copyDict with id=", attr.getObjId()
                    copyDict[attr.getObjId()] = myAttr
                # Use the copyDict to fix the reference in the copying object
                # if the pointed one is inside the same object
                if myAttr.isPointer() and myAttr.hasValue():
                    copyDict['internalPointers'].append(myAttr)
    
    def clone(self, copyEnable=False):
        """ Clones the object

        :param copyEnable (False): clone also the enable flag"""

        #NOTE: Maybe be, as default, we should be cloning the enable, but we found it is not doing so.
        # So for now it is not cloned, probably to void carying out the enable which may be a decision by one method that should not be
        # tranferred to the next method. Only Subsetting protocols should respect this.
        clone = self.getClass()()
        clone.copy(self, copyEnable=copyEnable)
        return clone    
    
    def evalCondition(self, condition):
        """
        Check if condition is meet.

        Examples of condition::

            "hasCTF"
            "hasCTF and not hasAlignment"

        :param condition: the condition string, it can contain variables
            or methods without arguments to be evaluated.

        :return The value of the condition evaluated with values

        """
        # Split in possible tokens
        import re
        tokens = re.split(r'\W+', condition)
        condStr = condition
        
        for t in tokens:
            if self.hasAttribute(t):
                condStr = condStr.replace(t, str(self.getAttributeValue(t)))
        return eval(condStr)
    
    def printAll(self, name=None, level=0):
        """Print object and all its attributes.
        Mainly for debugging"""
        tab = ' ' * (level*3)
        idStr = ''  # ' (id = %s, pid = %s)' % (self.getObjId(), self._objParentId)
        if name is None:
            logger.info(f"{tab} {self.getClassName()} {idStr}")
        else:
            if name == 'submitTemplate':  # Skip this because very large value
                value = '...'
            else:
                value = self.getObjValue()
                
            logger.info(f"{tab} {name} = {value} {idStr}")
        for k, v in self.getAttributes():
            v.printAll(k, level + 1)
            
    def printObjDict(self, includeClasses=False):
        """Print object dictionary. Mainly for debugging"""
        import pprint
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(dict(self.getObjDict(includeClasses)))        

class OrderedObject(Object):
    """Legacy class, to be removed. Object should give same functionality and is faster"""
    pass
                
class Scalar(Object):
    """Base class for basic types"""
    def hasValue(self):        
        return self._objValue is not None
    
    def equalAttributes(self, other, ignore=[], verbose=False):
        """Compare that all attributes are equal"""
        return self._objValue == other._objValue
    
    def __str__(self):
        """String representation of the scalar value"""
        return str(self.get())

    def __cmp(self, other):
        """ Comparison implementation for scalars. """
        a = self.get()
        b = other.get() if isinstance(other, Object) else other
        # cmp does not longer exist in Python3, so we will follow
        # the recommend replacement: (a > b) - (a < b)
        # https://docs.python.org/3.0/whatsnew/3.0.html#ordering-comparisons

        # Consider None values
        if a is None and b is None:
            return True
        elif a is None or b is None:
            return False
        else:
            return (a > b) - (a < b)

    def __eq__(self, other):
        """ Comparison for scalars should be by value while
         for other objects by reference. """
        return self.__cmp(other) == 0

    def __ne__(self, other):
        return self.__cmp(other) != 0

    def __lt__(self, other):
        return self.__cmp(other) < 0

    def __le__(self, other):
        return self.__cmp(other) <= 0

    def __gt__(self, other):
        return self.__cmp(other) > 0

    def __ge__(self, other):
        return self.__cmp(other) >= 0

    def get(self, default=None):
        """Get the value, if internal value is None
        the default argument passed is returned. """
        if self.hasPointer():
            # Get pointed value
            pointedValue = self._pointer.get()

            return default if pointedValue is None else pointedValue.get(default)

        if self.hasValue():
            return self._objValue
        return default
    
    def _copy(self, other, *args, **kwargs):
        if other.hasPointer():
            self.setPointer(other.getPointer())
        else:
            self.set(other.get())
        
    def swap(self, other):
        """ Swap the contained value between
        self and other objects.
        """
        tmp = self._objValue
        self._objValue = other._objValue
        other._objValue = tmp

    def sum(self, value):
        self._objValue += self._convertValue(value)
        
    def multiply(self, value):
        self._objValue *= value

    def setPointer(self, pointer):
        """ Set an internal pointer from this Scalar.
        Then, the value (retrieved with get) will be obtained
        from the pointed object.
        """
        if pointer is None:
            if self.hasPointer():
                delattr(self, "_pointer")
        else:
            self._pointer = pointer

    def hasPointer(self):
        """ Return True if this Scalar has an internal pointer
        from where the value will be retrieved with the get() method.
        """
        return hasattr(self, '_pointer')

    def getPointer(self):
        """ Return the internal pointer of this Scalar or None. """
        return getattr(self, '_pointer', None)

    
class Integer(Scalar):
    """Integer object"""
    def _convertValue(self, value):
        return int(value)
    
    def increment(self):
        """ Add 1 to the current value. """
        self._objValue += 1
        
    def __float__(self):
        return float(self.get())
    
    def __int__(self):
        return self.get()
    
    def __long__(self):
        return int(self.get())
    
        
class String(Scalar):
    """String object. """
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    FS = ".%f"  # Femto seconds

    @classmethod
    def getDatetime(cls, strValue, formatStr=None, fs=True):
        """
        Converts the given string value to a datetime object.

        :param strValue: string representation of the date
        :param formatStr: if None, uses the default cls:String.DATETIME_FORMAT.
        :param fs: Use femto seconds or not, only when format=None

        """
        if formatStr is None:
            try:
                formatStr = cls.DATETIME_FORMAT
                if fs:
                    formatStr += cls.FS
                datetime = dt.datetime.strptime(strValue, formatStr)
            except Exception as ex:
                # Maybe the %f (femtoseconds) is not working
                # let's try to format without it
                datetime = dt.datetime.strptime(strValue, cls.DATETIME_FORMAT)
        else:
            datetime = dt.datetime.strptime(strValue, formatStr)

        return datetime

    def _convertValue(self, value):
        return str(value)
    
    def empty(self):
        """ Return true if None or len == 0 """
        if not self.hasValue():
            return True
        return len(self.get().strip()) == 0

    def datetime(self, formatStr=None, fs=True):
        """ Get the datetime from this object string value. """
        return String.getDatetime(self._objValue, formatStr, fs)

    def getListFromValues(self, length=None, caster=int):
        """ Returns a list from a string with values as described at getListFromValues. Useful for """
        return getListFromValues(self._objValue, length, caster)

    def getListFromRange(self):
        """ Returns a list from a string with values as described at getListFromRangeString.
         Useful for NumericRangeParam params"""
        return getListFromRangeString(self._objValue)

    def toSeconds(self):

        return strToDuration(self.get())


class Float(Scalar):
    """Float object"""
    EQUAL_PRECISION = 0.001
    
    @classmethod
    def setPrecision(cls, newPrecision):
        """ Set the precision to compare float values.
        Mainly used for testing purposes.
        """
        cls.EQUAL_PRECISION = newPrecision
        
    def _convertValue(self, value):
        return float(value)
    
    def equalAttributes(self, other, ignore=[], verbose=False):
        """Compare that all attributes are equal"""
        # If both float has some value distinct of None
        # then we should compare the absolute value of difference 
        # against the EQUAL_PRECISION to say equal or not
        if self.hasValue() and other.hasValue():
            return abs(self._objValue - other._objValue) < self.EQUAL_PRECISION
        # If one has None as value, then both should have None
        # to have equal attributes
        if not self.hasValue() and not other.hasValue():
            return True
        
        return False
    
    def __float__(self):
        return self.get()
        
        
class Boolean(Scalar):
    """Boolean object"""
    
    def _convertValue(self, value):
        t = type(value)
        if t is bool:
            return value
        if t is str:
            v = value.strip().lower()
            return v == 'true' or v == '1'
        return bool(value) 
    
    def __nonzero__(self):
        if not self.hasValue():
            return False
        return self.get() 
    
    def __bool__(self):
        return self.get()


class Pointer(Object):
    """Reference object to other one"""
    EXTENDED_ATTR = '__attribute__'
    EXTENDED_ITEMID = '__itemid__'
    _ERRORS = {}
    
    def __init__(self, value=None, **kwargs):
        Object.__init__(self, value, objIsPointer=True, **kwargs)
        # The _extended attribute will be used to point to attributes of a
        # pointed object or the id of an item inside a set
        self._extended = String()
        
        if 'extended' in kwargs:
            self.setExtended(kwargs.get('extended')) 
               
    def __str__(self):
        """String representation of a pointer"""
        if self.hasValue():
            className = self.getObjValue().getClassName()
            strId = self.getObjValue().strId()
            return '-> %s (%s)' % (className, strId)
        return '-> None'
    
    def __clean(self, extended):
        """ Remove old attributes conventions. """
        # TODO: This replacements are needed now by backward compatibility
        # reasons, when we used __attribute__ and __item__ to mark both cases
        # in a future the following two lines can be removed.
        ext = extended.replace(self.EXTENDED_ATTR, '')
        ext = ext.replace(self.EXTENDED_ITEMID, '')
        return ext
        
    def hasValue(self):
        return self._objValue is not None
    
    def get(self, default=None):
        """ Get the pointed object. 
        By default, all pointers store a "pointed object" value.
        The _extended attribute allows to also point to internal
        attributes or items (in case of sets) of the pointed object.
        """
        extended = self._extended.get()
        if extended:
            ext = self.__clean(extended)
            parts = ext.split('.')
            value = self._objValue
            for p in parts:
                if hasattr(value, "__getitem__") and p.isdigit():
                    value = value[int(p)]  # item case
                else:
                    value = getattr(value, p, None)
                if value is None:
                    break
        else:
            value = self._objValue
            
        return value
    
    def set(self, other, cleanExtended=True):
        """ Set the pointer value but cleaning the extended property. """
        Object.set(self, other)
        # This check is needed because set is call from the Object constructor
        # when this attribute is not setup yet (a dirty patch, I know)
        if cleanExtended and hasattr(self, '_extended'):
            self._extended.set(None)
        
    def hasExtended(self):
        return bool(self._extended.get())  # consider empty string as false
    
    def getExtended(self):
        return self.__clean(self._extended.get(''))
        
    def setExtended(self, attribute):
        """ Set the attribute name of the "pointed object"
        that will be the result of the get() action. 
        """
        self._extended.set(attribute)
    
    def getExtendedParts(self):
        """ Return the extended components as a list. """
        if self.hasExtended():
            return self.getExtended().split('.')
        else:
            return []
    
    def setExtendedParts(self, parts):
        """ Set the extended attribute but using
        a list as input. 
        """
        self.setExtended('.'.join(parts))
        
    def addExtended(self, attribute):
        """ Similar to setExtended, but concatenating more extensions
        instead of replacing the previous value.
        """
        if self.hasExtended():
            self._extended.set('%s.%s' % (self._extended.get(), attribute))
        else:
            self.setExtended(attribute)
            
    def removeExtended(self):
        """ Remove the last part of the extended attribute. """
        if self.hasExtended():
            parts = self.getExtendedParts()
            self.setExtendedParts(parts[:-1])
        
    def getAttributes(self):
        yield '_extended', getattr(self, '_extended')
        
    def pointsNone(self):
        return self.get() is None
    
    def getUniqueId(self):
        """ Return the unique id concatenating the id
        of the direct pointed object plus the extended 
        attribute.
        """
        uniqueId = self.getObjValue().strId()
        if self.hasExtended():
            uniqueId += '.%s' % self.getExtended()
        
        return uniqueId
    

class List(Object, list):
    ITEM_PREFIX = '__item__'
    
    """Class to store a list of objects"""
    def __init__(self, value=None, **kwargs):
        list.__init__(self)
        Object.__init__(self, value, **kwargs)
        
    def __getattr__(self, name):
        if name.startswith(self.ITEM_PREFIX):
            i = self._stringToIndex(name)
            if i < len(self):
                return self[i]
        raise AttributeError("List object has not attribute: " + name)
            
    def __setattr__(self, name, value):
        if name.startswith('__item__') or len(name) == 0:
            self.append(value)
        else:
            object.__setattr__(self, name, value)

    def getAttributes(self):
        # First yield all attributes not contained in the list
        for name, attr in Object.getAttributes(self):
            yield name, attr
        # Now yield elements contained in the list
        for i, item in enumerate(self):
            yield self._indexToString(i), item
            
    def _indexToString(self, i):
        """Return the way the string index is generated.
        String indexes will start in 1, that's why i+1
        """
        return "%s%06d" % (self.ITEM_PREFIX, i+1)
    
    def _stringToIndex(self, strIndex):
        """ From the string index representation obtain the index.
        For symmetry the number in the index string will be
        decreased in 1.
        """
        return int(strIndex.split(self.ITEM_PREFIX)[1]) - 1
            
    def __len__(self):
        return list.__len__(self)

    def getSize(self):  # Just to have similar API than Set
        return len(self)
    
    def isEmpty(self):
        return len(self) == 0
    
    def clear(self):
        del self[:]
        
    def _convertValue(self, value):
        """Value should be a list."""
        if not (isinstance(value,  list)):
            raise Exception("List.set: value should be a list.")
        self.clear()
        for item in value:
            self.append(item)
        return None
    
        
class PointerList(List):
    def __init__(self, value=None, **kwargs):
        List.__init__(self, value, **kwargs)
        
    def append(self, value):
        """ Append Pointer of objects to the list.
         If value is a Pointer, just add it to the list.
         If is another subclass of Object, create
         a Pointer first and append the pointer.
        """
        if isinstance(value, Pointer):
            pointer = value
        elif isinstance(value, Object):
            pointer = Pointer()
            pointer.set(value)
        else:
            raise Exception("Only subclasses of Object can be added to PointerList\n"
                            " Passing value: %s, type: %s" % (value, type(value)))

        List.append(self, pointer)

            
class CsvList(Scalar, list):
    """This class will store a list of objects
    in a single DB row separated by comma.
    pType: the type of the list elements, int, bool, str"""
    def __init__(self, pType=str, **kwargs):
        Scalar.__init__(self, **kwargs)
        list.__init__(self)
        self._pType = pType
        
    def _convertValue(self, value):
        """ Value should be a str with comma separated values or a list.
        """
        self.clear()
        if value:
            if isinstance(value, str):
                for s in value.split(','):
                    self.append(self._pType(s))
            elif isinstance(value, list) or isinstance(value, tuple):
                for s in value:
                    self.append(self._pType(s))
            else:
                raise Exception("CsvList.set: Invalid value type: ",
                                type(value))

    def equalAttributes(self, other, ignore=[], verbose=False):
        """Compare that all attributes are equal"""

        return self == other

    def getObjValue(self):
        self._objValue = ','.join(map(str, self))
        return self._objValue
    
    def get(self):
        return self.getObjValue()
    
    def __str__(self):
        return list.__str__(self)
     
    def isEmpty(self):
        return len(self) == 0
    
    def clear(self):
        del self[:]

    def __eq__(self, other):
        """ Comparison for scalars should be by value
        and for other objects by reference.
        """
        return all(a == b for a, b in zip(self, other))


class Set(Object):
    """ This class will be a container implementation for elements.
    It will use an extra sqlite file to store the elements.
    All items will have a unique id that identifies each element in the set.
    """
    ITEM_TYPE = None  # This property should be defined to know the item type
    
    # This will be used for stream Set where data is populated on the fly
    STREAM_OPEN = 1
    STREAM_CLOSED = 2

    indexes = ['_index']
    # Dict that contains the attributes to be checked for compatibility in operations involving multiple sets,
    # such us the union of sets. Example: {'sampling rates': 'getSamplingRate', 'dimensions': 'getDimensions'}
    _compatibilityDict = {}
    
    def __init__(self, filename=None, prefix='', 
                 mapperClass=None, classesDict=None, **kwargs):
        # Use the object value to store the filename
        super().__init__(**kwargs)
        self._mapper = None
        self._idCount = 0
        self._size = Integer(0)  # cached value of the number of images
        # It is a bit contradictory that initially a set is Closed
        # but this is the default behaviour of the Set before Streaming extension
        self._streamState = Integer(self.STREAM_CLOSED)  
        self.setMapperClass(mapperClass)
        self._mapperPath = CsvList()  # sqlite filename
        self._representative = None
        self._classesDict = classesDict
        self._indexes = kwargs.get('indexes', [])
        # If filename is passed in the constructor, it means that
        # we want to create a new object, so we need to delete it if
        # the file exists
        if filename:
            self._mapperPath.set('%s, %s' % (filename, prefix))
            self.load()

    @classmethod
    def getCompatibilityDict(cls):
        return cls._compatibilityDict

    def copy(self, other, copyId=True, ignoreAttrs=['_mapperPath', '_size', '_streamState']):
        """ Copies the attributes of the set

        :param other: Set to copy attributes from
        :param copyId: True. Copies the objId.
        :param ignoreAttrs: Attributes list to ignore while copying. _mapperPath, _size and _streamState
        are ignored by default.
        
        """
        
        # Note: By default this behaves properly for cloning non identical objects. 
        # This is to clone a set from another new set that is based on "other".
        # For exact clone, we need to pass empty ignoreAttrs. This case happens in Protocol.__tryUpdateOutputSet
        super().copy(other, copyId, ignoreAttrs)

    def _getMapper(self):
        """ This method will open the connection to the items
        database on demand. That's why this method should 
        be used instead of accessing directly _mapper.
        """
        if self._mapper is None:
            self.load()
        return self._mapper
            
    def aggregate(self, operations, operationLabel, groupByLabels=None):
        """
         This method operate on sets of values. They are used with a
         GROUP BY clause to group values into subsets
        :param operations: list of aggregate function such as COUNT, MAX, MIN,...
        :param operationLabel: label to use by the aggregate function
        :param groupByLabels: list of labels to group by
        :return: the aggregated value of each group
        """
        return self._getMapper().aggregate(operations, operationLabel, groupByLabels)

    def setMapperClass(self, MapperClass):
        """ Set the mapper to be used for storage. """
        if MapperClass is None:
            from pyworkflow.mapper.sqlite import SqliteFlatMapper
            MapperClass = SqliteFlatMapper
        Object.__setattr__(self, '_MapperClass', MapperClass)
        
    def getItem(self, field, value):
        """ Alternative to [] to get a single item form the set.

        :param field: attribute of the item to look up for. Should be a unique identifier
        :param value: value to look for"""

        return self.__getitem__({field:value})

    def __getitem__(self, itemId):
        """ Get the image with the given id.

        NOTE: Performance warning: this method is expensive in terms of performance use of
        iterItems is preferred. Use this one only for a single item retrieval.

        :param itemId: the objId (integer) of the item. Alternatively itemId could be a dictionary like

            {_alternative_identifier: 'RG-1234'}

            where '_alternative_identifier' is an attribute of the item and 'RG-1234' the value to look for
            only the first matching item is returned in case there are more

        """
        closedMapper = self._mapper is None

        if isinstance(itemId, dict):
            for obj in self._getMapper().selectBy(**itemId):
                item = obj
                break
        else:
            item = self._getMapper().selectById(itemId)

        if closedMapper:
            self.close()
        return item

    def __contains__(self, itemId):
        """ element in Set """
        return self._getMapper().exists(itemId)

    def iterItems(self, orderBy='id', direction='ASC', where=None,
                  limit=None, iterate=True, rowFilter=None):
        return self._getMapper().selectAll(orderBy=orderBy,
                                           direction=direction,
                                           where=where,
                                           limit=limit,
                                           iterate=iterate,
                                           rowFilter=rowFilter)  # has flat mapper, iterate is true

    def getFirstItem(self):
        """ Return the first item in the Set. """
        # This function is used in many contexts where the mapper can be
        # left open and could be problematic locking the db for other processes
        # So, we look if the mapper was closed before, in which case
        # we will close it after that
        closedMapper = self._mapper is None
        firstItem = self._getMapper().selectFirst()
        if closedMapper:
            self.close()
        return firstItem
    
    def __iter__(self):
        """ Iterate over the set of images. """
        return self.iterItems()
       
    def __len__(self):
        return self._size.get()
    
    def getSize(self):
        """Return the number of images"""
        return self._size.get()

    def isEmpty(self):
        return self.getSize() == 0
    
    def getFileName(self):
        if len(self._mapperPath):
            return self._mapperPath[0]
        return None
    
    def getPrefix(self):
        if len(self._mapperPath) > 1:
            return self._mapperPath[1]
        return None
    
    def write(self, properties=True):
        """
        Commit the changes made to the Set underlying database.

        :param properties: this flag controls when to write Set attributes to
            special table 'Properties' in the database. False value is
            use for example in SetOfClasses for not writing each Class2D
            properties.

        """
        if properties:
            self._getMapper().setProperty('self', self.getClassName())
            objDict = self.getObjDict()
            for key, value in objDict.items():
                self._getMapper().setProperty(key, value)
        self._getMapper().commit()
    
    def _loadClassesDict(self):
        return self._classesDict or globals()
    
    def setClassesDict(self, classesDict):
        """ Set the dictionary with classes where to look for classes names. """
        self._classesDict = classesDict
    
    def load(self):
        """ Load extra data from files. """
        if self._mapperPath.isEmpty():
            raise Exception("Set.load:  mapper path and prefix not set.")
        fn, prefix = self._mapperPath
        self._mapper = self._MapperClass(fn, self._loadClassesDict(), prefix, self._indexes)
        self._size.set(self._mapper.count())
        self._idCount = self._mapper.maxId()
           
    def __del__(self):
        # Close connections to db when destroy this object
        if self._mapper is not None:
            self.close()
        
    def close(self):
        if self._mapper is not None:
            self._mapper.close()
            self._mapper = None
        
    def clear(self):
        self._mapper.clear()
        self._idCount = 0
        self._size.set(0)
         
    def append(self, item):
        """ Add an item to the set.
        If the item has already an id, use it.
        If not, keep a counter with the max id
        and assign the next one.
        """
        # The _idCount and _size properties work fine
        # under the assumption that once a Set is stored,
        # then it is read-only (no more appends).
        #
        # Anyway, this can be easily changed by updating
        # both from the underlying sqlite when reading a set.

        if not item.hasObjId():
            self._idCount += 1
            item.setObjId(self._idCount)
        else:
            self._idCount = max(self._idCount, item.getObjId())
        self._insertItem(item)
        self._size.increment()

    def _insertItem(self, item):
        self._getMapper().insert(item)
        
    def update(self, item):
        """ Update an existing item. """
        self._getMapper().update(item)
                
    def __str__(self):
        return "%-20s (%d items%s)" % (self.getClassName(), self.getSize(),
                                       self._appendStreamState())

    def _appendStreamState(self):
        return "" if self.isStreamClosed() else ", open set"

    def getSubset(self, n):
        """ Return a subset of n element, making a clone of each. """
        subset = []
        for i, item in enumerate(self):
            subset.append(item.clone())
            if i == n:
                break
        return subset
    
    def setRepresentative(self, representative):
        self._representative = representative
    
    def getRepresentative(self):       
        return self._representative
    
    def hasRepresentative(self):
        """ Return true if have a representative image. """
        return self._representative is not None

    def equalItemAttributes(self, other, ignore=[], verbose=False):
        """Compare that all items in self and other
        return True for equalAttributes.
        """
        return all(x.getObjId() == y.getObjId() and
                   x.equalAttributes(y, ignore=ignore, verbose=verbose)
                   for x, y in zip(self, other))
        
    def hasProperty(self, key):
        return self._getMapper().hasProperty(key)
        
    def getProperty(self, key, defaultValue=None):
        return self._getMapper().getProperty(key, defaultValue)
    
    def loadProperty(self, propertyName, defaultValue=None):
        """ Get the value of a property and
        set its value as an object attribute.
        """
        try:
            self.setAttributeValue(propertyName, self.getProperty(propertyName, defaultValue))
        except Exception as e:
            # There could be an exception with "extra" set properties. We tolerate it but warn the developers
            # This happens in streaming scenarios where properties are only coming from the set sqlite.
            logger.warning("DEVELOPERS: %s property could not be loaded from the disk. "
                           "Is the property an extended property?. It is lost from now on." % propertyName)
    def loadAllProperties(self):
        """ Retrieve all properties stored by the mapper. """
        for key in self._getMapper().getPropertyKeys():
            if key != 'self':
                self.loadProperty(key)
        
    def getIdSet(self):
        """ Return a Python set object containing all ids. """
        return set(self.getUniqueValues('id'))
    
    def getFiles(self):
        files = set()
        if self.getFileName():
            files.add(self.getFileName())
        return files
    
    def getStreamState(self):
        return self._streamState.get()
    
    def setStreamState(self, newState):
        self._streamState.set(newState)
    
    def isStreamOpen(self):
        return self.getStreamState() == self.STREAM_OPEN
    
    def isStreamClosed(self):
        return self.getStreamState() == self.STREAM_CLOSED 
    
    def enableAppend(self):
        """ By default, when a Set is loaded, it is opened
        in read-only mode, so no new insertions are allowed.
        This function will allow to append more items
        to an existing set.
        """
        self._getMapper().enableAppend()




    # ******* Streaming helpers to deal with sets **********
    def hasChangedSince(self, time):
        """ Returns if the set has changed since the timestamp passed as parameter. It will check
                the last modified time of the file this set uses to persists.

        :parameter time: timestamp to compare to the last modification time  """

        if time is None:
            return True

        # Get the file name
        localFile = self.getFileName()

        #self.lastCheck = getattr(self, 'lastCheck', now)
        # Get the last time it was modified
        modTime = dt.datetime.fromtimestamp(getmtime(localFile))
        return time < modTime

    def getUniqueValues(self, attributes, where=None):
        """ Returns a list (for a single label) or a dictionary with unique values for the passed labels.
        If more than one label is passed it will be unique rows similar ti SQL unique clause.

        :param attributes (string or list) item attribute/s to retrieve unique row values
        :param where (string) condition to filter the results"""

        return self._getMapper().unique(attributes, where)

    def fmtDate(self, date):
        """ Formats a python date to a valid string for the mapper"""
        return self._getMapper().fmtDate(date)

    @staticmethod
    def isItemEnabled(item):
        """ Returns if the item is enabled...to be used as a callback. In some other cases (new user subsets)
         this method will be replaced"""

        return item.isEnabled()

def ObjectWrap(value):
    """This function will act as a simple Factory
    to create objects from Python basic types"""
    t = type(value)
    if issubclass(t, Object):
        return value
    if t is int:
        return Integer(value)
    if t is bool:
        return Boolean(value)
    if t is float:
        return Float(value)
    if t is list:
        o = CsvList()
        o.set(value)
        return o
    if t is None:
        return None
    # If it is str, unicode or unknown type, convert to string
    return String(value)
         

class Dict(dict):
    """ Simple wrapper around dict class to have a default value. """
    def __init__(self, default=None):
        self._default = default
        dict.__init__(self)

    def __getitem__(self, key):
        """ Get the image with the given id. """
        return self.get(key, self._default)

    def __contains__(self, item):
        return True


# Define a global dict with all basic defined objects
OBJECTS_DICT = getSubclasses(Object, globals())
