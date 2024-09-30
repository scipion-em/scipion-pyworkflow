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
import logging
logger = logging.getLogger(__name__)
import re
from collections import OrderedDict

from pyworkflow import Config, ID_ATTRIBUTE, ID_COLUMN
from pyworkflow.utils import replaceExt, joinExt, valueToList
from .sqlite_db import SqliteDb, OperationalError
from .mapper import Mapper

ID = ID_COLUMN
CREATION = 'creation'
PARENT_ID = 'parent_id'
CLASSNAME = 'classname'
NAME = 'name'


class SqliteMapper(Mapper):
    """Specific Mapper implementation using Sqlite database"""
    def __init__(self, dbName, dictClasses=None):
        Mapper.__init__(self, dictClasses)
        self.__initObjDict()
        self.__initUpdateDict()
        try:
            self.db = SqliteObjectsDb(dbName)
        except Exception as ex:
            raise Exception('Error creating SqliteMapper, dbName: %s'
                            '\n error: %s' % (dbName, ex))
    
    def close(self):
        self.db.close()
        
    def commit(self):
        self.db.commit()
        
    def __getObjectValue(self, obj):
        """ Get the value of the object to be stored.
        We need to handle the special case of pointer, where we should
        store as value the object id of the pointed object.
        """
        value = obj.getObjValue()

        if obj.isPointer() and obj.hasValue():
            if value.hasObjId():  # Check the object has been stored previously
                value = value.strId()  # For pointers store the id of referenced object
            else:
                self.updatePendingPointers.append(obj)
                value = "Pending update" 
            
        return value
        
    def __insert(self, obj, namePrefix=None):
        if not hasattr(obj, '_objDoStore'):
            logger.info("MAPPER: object '%s' doesn't seem to be an Object subclass,"
                  "       it does not have attribute '_objDoStore'. "
                  "Insert skipped." % obj)
            return
        obj._objId = self.db.insertObject(obj._objName, obj.getClassName(),
                                          self.__getObjectValue(obj),
                                          obj._objParentId,
                                          obj._objLabel, obj._objComment)
        self.updateDict[obj._objId] = obj
        sid = obj.strId()
        if namePrefix is None:
            namePrefix = sid
        else:
            namePrefix = joinExt(namePrefix, sid)
        self.insertChilds(obj, namePrefix)
        
    def insert(self, obj):
        """Insert a new object into the system, the id will be set"""
        self.__insert(obj)
        
    def insertChild(self, obj, key, attr, namePrefix=None):
        if not hasattr(attr, '_objDoStore'):
            logger.info("MAPPER: object '%s' doesn't seem to be an Object subclass,"
                  "       it does not have attribute '_objDoStore'. \n"
                  "Insert skipped." % attr)
            return 

        if namePrefix is None:
            namePrefix = self.__getNamePrefix(obj)
        attr._objName = joinExt(namePrefix, key)
        attr._objParentId = obj._objId
        self.__insert(attr, namePrefix)
        
    def insertChilds(self, obj, namePrefix=None):
        """ Insert childs of an object, if namePrefix is None,
        the it will be deduced from obj. """
        # This is also done in insertChild, but avoid 
        # doing the same for every child element
        if namePrefix is None:
            namePrefix = self.__getNamePrefix(obj)
        for key, attr in obj.getAttributesToStore():
            self.insertChild(obj, key, attr, namePrefix)
        
    def deleteChilds(self, obj):
        namePrefix = self.__getNamePrefix(obj)
        self.db.deleteChildObjects(namePrefix)
        
    def deleteAll(self):
        """ Delete all objects stored """
        self.db.deleteAll()
                
    def delete(self, obj):
        """Delete an object and all its childs"""
        self.deleteChilds(obj)
        self.db.deleteObject(obj.getObjId())
    
    def __getNamePrefix(self, obj):
        if len(obj._objName) > 0 and '.' in obj._objName:
            return replaceExt(obj._objName, obj.strId())
        return obj.strId()
    
    def __printObj(self, obj):
        logger.info("obj._objId: %s" % obj._objId)
        logger.info("obj._objParentId: %s" % obj._objParentId)
        logger.info("obj._objName: %s"% obj._objName)
        logger.info("obj.getObjValue(): %s" % obj.getObjValue())

    def updateTo(self, obj, level=1):
        self.__initUpdateDict()
        self.__updateTo(obj, level)
        # Update pending pointers to objects
        for ptr in self.updatePendingPointers:
            self.db.updateObject(ptr._objId, ptr._objName,
                                 Mapper.getObjectPersistingClassName(ptr),
                                 self.__getObjectValue(obj), ptr._objParentId,
                                 ptr._objLabel, ptr._objComment)

        # Delete any child objects that have not been found.
        # This could be the case if some elements (such as inside List)
        # were stored in the database and were removed from the object
        self.db.deleteMissingObjectsByAncestor(self.__getNamePrefix(obj),
                                               self.updateDict.keys())

    def __updateTo(self, obj, level):
        self.db.updateObject(obj._objId, obj._objName,
                             Mapper.getObjectPersistingClassName(obj),
                             self.__getObjectValue(obj), obj._objParentId, 
                             obj._objLabel, obj._objComment)

        if obj.getObjId() in self.updateDict:
            raise Exception('Circular reference, object: %s found twice'
                            % obj.getName())
        
        self.updateDict[obj._objId] = obj

        for key, attr in obj.getAttributesToStore():
            if attr._objId is None:  # Insert new items from the previous state
                attr._objParentId = obj._objId
                namePrefix = self.__getNamePrefix(obj)
                attr._objName = joinExt(namePrefix, key)
                self.__insert(attr, namePrefix)
            else:  
                self.__updateTo(attr, level + 2)

    def updateFrom(self, obj):
        objRow = self.db.selectObjectById(obj._objId)
        self.fillObject(obj, objRow)
            
    def selectById(self, objId):
        """Build the object which id is objId"""
        if objId in self.objDict:
            obj = self.objDict[objId]
        else:
            objRow = self.db.selectObjectById(objId)
            if objRow is None:
                obj = None
            else:
                obj = self._buildObjectFromClass(objRow['classname'])
                if obj is not None:
                    self.fillObject(obj, objRow)
        return obj

    def exists(self, objId):
        return self.db.doesRowExist(objId)

    def getParent(self, obj):
        """ Retrieve the parent object of another. """
        return self.selectById(obj._objParentId)
        
    def fillObjectWithRow(self, obj, objRow):
        """ Fill the object with row data. """

        rowId = objRow[ID]
        rowName = self._getStrValue(objRow['name'])

        if not hasattr(obj, ID_ATTRIBUTE):
            raise Exception("Entry '%s' (id=%s) in the database, stored as '%s'"
                            ", is being mapped to %s object. " %
                            (rowName, rowId,
                             objRow['classname'], type(obj)))

        obj._objId = rowId

        self.objDict[rowId] = obj
        obj._objName = rowName
        obj._objLabel = self._getStrValue(objRow['label'])
        obj._objComment = self._getStrValue(objRow['comment'])
        obj._objCreation = self._getStrValue(objRow[CREATION])
        objValue = objRow['value']
        obj._objParentId = objRow[PARENT_ID]
        
        if obj.isPointer():
            if objValue is not None:
                objValue = self.selectById(int(objValue))
            # This is necessary in some specific cases. E.g.:
            # CTF consensus creating:
            #   A.- Micrographs
            #   B.- CTFs --> pointing to micrographs in this same protocol(#1)
            # When loading this kind of protocol the sequence is as follows:
            #  1 Loading of protocol consuming consensus CTF output ..
            #    ...
            #    finds inputCtf (DIRECT pointer to B)
            #    2 loads set properties
            #      ...
            #      2.4 pointer to micrographs (Pointer to Consensus + extended)
            #        2.4.1 pointee loads (Consensus protocol)
            #        ...
            #        ...
            #        2.4.n _extended of 2.4 is loaded since is a child of consensus
            #      2.4 obj.set() for 2.4 pointer --> will reset the extended to None.
            obj.set(objValue, cleanExtended=False)
        else:
            try:
                obj.set(objValue)
            except Exception as e:
                # Case for parameter type change. Loading the project tolerates type changes like Float to Int.
                # But when running a protocol loads happens differently (maybe something to look at) and comes here.
                logger.error("Can't set %s to %s. Maybe its type has changed!. Continues with default value %s." %
                             (objValue, rowName, obj.get()))
        
    def fillObject(self, obj, objRow, includeChildren=True):
        """ Fills an already instantiated object the data in a row, including children

        NOTE: This, incase children are included, makes a query to the db with all its children 'like 2.*'.
        At some point it calls selectById triggering the loading of other protocols and ancestors.

        :param obj: Object to fill
        :param objRow: row with the values
        :param includeChildren: (True). If true children are also populated

        """

        self.fillObjectWithRow(obj, objRow)
        namePrefix = self.__getNamePrefix(obj)

        if includeChildren:
            childs = self.db.selectObjectsByAncestor(namePrefix)

            for childRow in childs:

                childParts = childRow[NAME].split('.')
                childName = childParts[-1]
                childId = childRow[ID]
                parentId = int(childParts[-2])
                # Here we are assuming that always the parent have
                # been processed first, so it will be in the dictionary
                parentObj = self.objDict.get(parentId, None)
                if parentObj is None:  # Something went wrong
                    continue

                # If id already in the objDict skip all this
                if childId in self.objDict.keys():
                    setattr(parentObj, childName, self.objDict[childId])
                    continue

                # Try to get the instance from the parent
                childObj = getattr(parentObj, childName, None)

                # If parent does not have that attribute...
                if childObj is None:
                    # Instantiate it based on the class Name
                    childObj = self._buildObjectFromClass(childRow[CLASSNAME])

                    # If we have any problem building the object, just ignore it
                    if childObj is None:
                        # This is the case for deprecated types.
                        continue
                    setattr(parentObj, childName, childObj)

                self.fillObjectWithRow(childObj, childRow)

    def __buildObject(self, row):
        """ Builds and object, either based on the parent attribute, or a new
        one based on the class. """
        parentId = self._getParentIdFromRow(row)
        #  If there is no parent...
        if parentId is None:
            # It must be a Root object, use the class
            return self._buildObjectFromClass(self._getClassFromRow(row))
        else:
            # Try to get the instance from the parent
            name = self._getNameFromRow(row)
            childParts = name.split('.')
            childName = childParts[-1]

            # Get the parent, we should have it cached
            parentObj = self.objDict.get(parentId, None)
            if parentObj is None:  # Something went wrong
                logger.warning("Parent object (id=%d) was not found, "
                      "object: %s. Ignored." % (parentId, name))
                return None

            childObj = getattr(parentObj, childName, None)

            # If parent object does not have that attribute
            if childObj is None:
                childObj = self._buildObjectFromClass(row[CLASSNAME])
                # If we have any problem building the object, just ignore it
                if childObj is None:
                    return None

                setattr(parentObj, childName, childObj)

            return childObj

    def __objFromRow(self, objRow, includeChildren=True):
        objClassName = objRow['classname']
        obj = self._buildObjectFromClass(objClassName)

        if obj is not None:
            self.fillObject(obj, objRow, includeChildren)
        
        return obj
        
    def __iterObjectsFromRows(self, objRows, objectFilter=None):
        for objRow in objRows:
            obj = self.objDict.get(objRow['id'], None) or self.__objFromRow(objRow)

            if (obj is not None and
                    objectFilter is None or objectFilter(obj)):
                yield obj
        
    def __objectsFromRows(self, objRows, iterate=False, objectFilter=None):
        """Create a set of object from a set of rows
        Params:
            objRows: rows result from a db select.
            iterate: if True, iterates over all elements, if False the whole
                list is returned
            objectFilter: function to filter some of the objects of the
                results.
        """
        if not iterate:
            return [obj for obj in self.__iterObjectsFromRows(objRows,
                                                              objectFilter)]
        else:
            return self.__iterObjectsFromRows(objRows, objectFilter)
               
    def __initObjDict(self):
        """ Clear the objDict cache """        
        self.objDict = {}
        
    def __initUpdateDict(self):
        """ Clear the updateDict cache """        
        self.updateDict = {}
        # This is used to store pointers that pointed object are not stored yet
        self.updatePendingPointers = []
         
    def selectBy(self, iterate=False, objectFilter=None, **args):
        """Select object meetings some criteria"""
        self.__initObjDict()
        objRows = self.db.selectObjectsBy(**args)
        return self.__objectsFromRows(objRows, iterate, objectFilter)
    
    def selectByClass(self, className, includeSubclasses=True, iterate=False,
                      objectFilter=None):
        self.__initObjDict()
        
        if includeSubclasses:
            from pyworkflow.utils.reflection import getSubclasses
            whereStr = "classname='%s'" % className
            base = self.dictClasses.get(className)
            subDict = getSubclasses(base, self.dictClasses)
            for k, v in subDict.items():
                if issubclass(v, base):
                    whereStr += " OR classname='%s'" % k
            objRows = self.db.selectObjectsWhere(whereStr)
            return self.__objectsFromRows(objRows, iterate, objectFilter)
        else:
            return self.selectBy(iterate=iterate, classname=className)
            
    def selectAll(self, iterate=False, objectFilter=None):
        self.__initObjDict()
        objRows = self.db.selectObjectsByParent(parent_id=None)
        return self.__objectsFromRows(objRows, iterate, objectFilter)

    def selectAllBatch(self, objectFilter=None):
        """ Select all the row at once for all the project

        Returns:
            all the protocols populated with the data from the DB

        """
        self.__initObjDict()

        # Get all the data from Objects table sorted by Name
        objAll = self.db.selectAllObjects()

        # We should have first the protocol lines
        # then each of the protocol attributes
        # at then there is the creation time

        # Dictionary to store objects
        objs = []

        # For each row
        for row in objAll:
            obj = self._getObjectFromRow(row)

            if obj is not None and objectFilter is None or objectFilter(obj):
                objs.append(obj)

        return objs

    def _getObjectFromRow(self, row):
        """ Creates and fills and object described iin row

        :param row: A row with the Class to instantiate, and value to set."""

        # Get the ID first
        identifier = row[ID]

        # If already in the dictionary we skipp al this
        if identifier in self.objDict.keys():
            return self.objDict[identifier]

        # Build the object without children
        obj = self.__buildObject(row)

        # If an object was created
        if obj is not None:
            try:
                # Fill object attributes with row values
                self.fillObjectWithRow(obj, row)

                # Add it to the obj cache, we might need it later to assign
                # attributes
                self.objDict[obj._objId] = obj

                return obj

            except Exception as e:
                # Tolerate errors when loading attributes.
                # This could happen then a protocol has change a param to a new type not compatible
                # with previous values. Warn properly about it.
                logger.warning("Can't load the row (%s, %s, %s) form the database to memory. This could cause future error." %
                             (identifier, row[NAME], row[PARENT_ID]))

    def _getObjectFromDictionary(self, objId):
        return self.objDict[objId]

    @staticmethod
    def _getIdFromRow(row):
        return SqliteMapper._getFieldFromRow(ID, row)

    @staticmethod
    def _getParentIdFromRow(row):
        return SqliteMapper._getFieldFromRow(PARENT_ID, row)

    @staticmethod
    def _getClassFromRow(row):
        return SqliteMapper._getFieldFromRow(CLASSNAME, row)

    @staticmethod
    def _getNameFromRow(row):
        return SqliteMapper._getFieldFromRow(NAME, row)

    @staticmethod
    def _getFieldFromRow(fieldName, row):
        return row[fieldName]

    def insertRelation(self, relName, creatorObj, parentObj, childObj,
                       parentExt=None, childExt=None):
        """ This function will add a new relation between two objects.
        Params:
            relName: the name of the relation to be added.
            creatorObj: this object will be the one who register the relation.
            parentObj: this is "parent" in the relation
            childObj: this is "child" in the relation
        """
        for o in [creatorObj, parentObj, childObj]:
            if not o.hasObjId():
                raise Exception("Before adding a relation, the object should "
                                "be stored in mapper")
        self.db.insertRelation(relName, creatorObj.getObjId(),
                               parentObj.getObjId(), childObj.getObjId(),
                               parentExt, childExt)
    
    def __objectsFromIds(self, objIds):
        """Return a list of objects, given a list of id's
        """
        return [self.selectById(rowId[ID]) for rowId in objIds]
        
    def getRelationChilds(self, relName, parentObj):
        """ Return all "child" objects for a given relation.
        Params:
            relName: the name of the relation.
            parentObj: this is "parent" in the relation
        Returns: 
            a list of "child" objects.
        """
        childIds = self.db.selectRelationChilds(relName, parentObj.getObjId())
        
        return self.__objectsFromIds(childIds)  
            
    def getRelationParents(self, relName, childObj):
        """ Return all "parent" objects for a given relation.
        Params:
            relName: the name of the relation.
            childObj: this is "child" in the relation
        Returns: 
            a list of "parent" objects.
        """
        parentIds = self.db.selectRelationParents(relName, childObj.getObjId())
        
        return self.__objectsFromIds(parentIds)  

    def getRelationsByCreator(self, creatorObj):
        """ Return all relations created by creatorObj. """
        return self.db.selectRelationsByCreator(creatorObj.getObjId())
    
    def getRelationsByName(self, relationName):
        """ Return all relations stored of a given type. """
        return self.db.selectRelationsByName(relationName)

    def deleteRelations(self, creatorObj):
        """ Delete all relations created by object creatorObj """
        self.db.deleteRelationsByCreator(creatorObj.getObjId())
    
    def insertRelationData(self, relName, creatorId, parentId, childId,
                           parentExtended=None, childExtended=None):
        self.db.insertRelation(relName, creatorId, parentId, childId,
                               parentExtended, childExtended)
    
    
class SqliteObjectsDb(SqliteDb):
    """Class to handle a Sqlite database.
    It will create connection, execute queries and commands"""
    # Maintain the current version of the DB schema
    # useful for future updates and backward compatibility
    # version should be an integer number
    VERSION = 1
    
    SELECT = ("SELECT id, parent_id, name, classname, value, label, comment, "
              "datetime(creation, 'localtime') as creation FROM Objects")
    DELETE = "DELETE FROM Objects WHERE "
    DELETE_SEQUENCE = "DELETE FROM SQLITE_SEQUENCE WHERE name='Objects'"
    
    SELECT_RELATION = ("SELECT object_%s_id AS id FROM Relations "
                       "WHERE name=? AND object_%s_id=?")
    SELECT_RELATIONS = "SELECT * FROM Relations WHERE "
    EXISTS = "SELECT EXISTS(SELECT 1 FROM Objects WHERE %s=? LIMIT 1)"
    
    def selectCmd(self, whereStr, orderByStr=' ORDER BY id'):

        whereStr = " WHERE " + whereStr if whereStr is not None else ''
        return self.SELECT + whereStr + orderByStr
    
    def __init__(self, dbName, timeout=1000, pragmas=None):
        SqliteDb.__init__(self)
        self._pragmas = pragmas or {}
        self._createConnection(dbName, timeout)
        self._initialize()

    def _initialize(self):
        """ Create the required tables if needed. """
        tables = self.getTables()
        # Check if the tables have been created or not
        if not tables:
            self.__createTables()
        else:
            self.__updateTables()
        
    def __createTables(self):
        """Create required tables if don't exists"""
        # Enable foreign keys
        self.setVersion(self.VERSION)
        self._pragmas['foreing_keys'] = "ON"
        for pragma in self._pragmas.items():
            self.executeCommand("PRAGMA %s=%s" % pragma)
        # Create the Objects table
        self.executeCommand("""CREATE TABLE IF NOT EXISTS Objects
                     (id        INTEGER PRIMARY KEY AUTOINCREMENT,
                      parent_id INTEGER REFERENCES Objects(id),
                      name      TEXT,                -- object name 
                      classname TEXT,                -- object's class name
                      value     TEXT DEFAULT NULL,   -- object value, used for Scalars
                      label     TEXT DEFAULT NULL,   -- object label, text used for display
                      comment   TEXT DEFAULT NULL,   -- object comment, text used for annotations
                      creation  DATE                 -- creation date and time of the object
                      )""")
        # Create the Relations table
        self.executeCommand("""CREATE TABLE IF NOT EXISTS Relations
                     (id        INTEGER PRIMARY KEY AUTOINCREMENT,
                      parent_id INTEGER REFERENCES Objects(id), -- object that created the relation
                      name      TEXT,               -- relation name 
                      classname TEXT DEFAULT NULL,  -- relation's class name
                      value     TEXT DEFAULT NULL,  -- relation value
                      label     TEXT DEFAULT NULL,  -- relation label, text used for display
                      comment   TEXT DEFAULT NULL,  -- relation comment, text used for annotations
                      object_parent_id  INTEGER REFERENCES Objects(id) ON DELETE CASCADE,
                      object_child_id  INTEGER REFERENCES Objects(id) ON DELETE CASCADE,
                      creation  DATE,                 -- creation date and time of the object
                      object_parent_extended TEXT DEFAULT NULL, -- extended property to consider internal objects
                      object_child_extended TEXT DEFAULT NULL
                      )""")
        self.commit()
        
    def __updateTables(self):
        """ This method is intended to update the table schema
        in the case of dealing with old database version.
        """
        if self.getVersion() < self.VERSION:  # This applies for version 1
            # Add the extra column for pointer extended attribute in Relations table
            # from version 1 on, there is not needed since the table will 
            # already contains this column
            columns = [c[1] for c in self.getTableColumns('Relations')]
            if 'object_parent_extended' not in columns:
                self.executeCommand("ALTER TABLE Relations "
                                    "ADD COLUMN object_parent_extended  TEXT DEFAULT NULL")
            if 'object_child_extended' not in columns:
                self.executeCommand("ALTER TABLE Relations "
                                    "ADD COLUMN object_child_extended  TEXT DEFAULT NULL")
            self.setVersion(self.VERSION)

    def insertObject(self, name, classname, value, parent_id, label, comment):
        """Execute command to insert a new object. Return the inserted object id"""
        try:
            self.executeCommand(
                'INSERT INTO Objects (parent_id, name, classname, value, label, comment, creation)' +
                ' VALUES (?, ?, ?, ?, ?, ?, datetime(\'now\'))',
                (parent_id, name, classname, value, label, comment))
            return self.cursor.lastrowid
        except Exception as ex:
            logger.error("insertObject: ERROR")
            logger.error('INSERT INTO Objects (parent_id, name, classname, value, label, comment, creation)' +
                  ' VALUES (?, ?, ?, ?, ?, ?, datetime(\'now\'))')
            logger.error((parent_id, name, classname, value, label, comment))
            raise ex
        
    def insertRelation(self, relName, parent_id, object_parent_id, object_child_id, 
                       object_parent_extended=None, object_child_extended=None, **kwargs):
        """Execute command to insert a new object. Return the inserted object id"""
        self.executeCommand("INSERT INTO Relations "
                            "(parent_id, name, object_parent_id, object_child_id, creation, "
                            "object_parent_extended, object_child_extended) "
                            " VALUES (?, ?, ?, ?, datetime('now'), ?, ?)",
                            (parent_id, relName, object_parent_id, object_child_id,
                             object_parent_extended, object_child_extended))
        return self.cursor.lastrowid
    
    def updateObject(self, objId, name, classname, value, parent_id, label, comment):
        """Update object data """
        self.executeCommand("UPDATE Objects SET parent_id=?, name=?, "
                            "classname=?, value=?, label=?, comment=? WHERE id=?",
                            (parent_id, name, classname, value, label, comment, objId))
        
    def selectObjectById(self, objId):
        """Select an object give its id"""
        self.executeCommand(self.selectCmd(ID + "=?"), (objId,))
        return self.cursor.fetchone()

    def doesRowExist(self, objId):
        """Return True if a row with a given id exists"""
        self.executeCommand(self.EXISTS % ID, (objId,))
        one = self.cursor.fetchone()
        return one[0] == 1

    def selectAllObjects(self):
        """Select all data at once"""
        self.executeCommand(self.selectCmd(ID + ">0", ' ORDER BY parent_id'))
        return self.cursor.fetchall()

    def selectObjectsByParent(self, parent_id=None, iterate=False):
        """Select object with a given parent
        if the parent_id is None, all object with parent_id NULL
        will be returned"""
        if parent_id is None:
            self.executeCommand(self.selectCmd(PARENT_ID + " is NULL"))
        else:
            self.executeCommand(self.selectCmd(PARENT_ID + "=?"), (parent_id,))
        return self._results(iterate)  
    
    def selectObjectsByAncestor(self, ancestor_namePrefix, iterate=False):
        """Select all objects in the hierarchy of ancestor_id"""
        self.executeCommand(self.selectCmd("name LIKE '%s.%%'"
                                           % ancestor_namePrefix))
        return self._results(iterate)

    def selectObjectsBy(self, iterate=False, **args):     
        """More flexible select where the constrains can be passed
        as a dictionary, the concatenation is done by an AND"""

        if len(args) == 0:
            whereStr = '1=?'
            whereTuple = (1,)
        else:
            whereList = ['%s=?' % k for k in args.keys()]
            whereStr = ' AND '.join(whereList)
            whereTuple = tuple(args.values())

        self.executeCommand(self.selectCmd(whereStr), whereTuple)
        return self._results(iterate)
    
    def selectObjectsWhere(self, whereStr, iterate=False):
        self.executeCommand(self.selectCmd(whereStr))
        return self._results(iterate)
    
    def deleteObject(self, objId):
        """Delete an existing object"""
        self.executeCommand(self.DELETE + ID + "=?", (objId,))
        
    def deleteChildObjects(self, ancestor_namePrefix):
        """ Delete from db all objects that are childs 
        of an ancestor, now them will have the same starting prefix"""
        self.executeCommand(self.DELETE + "name LIKE '%s.%%'"
                            % ancestor_namePrefix)

    def selectMissingObjectsByAncestor(self, ancestor_namePrefix,
                                       idList):
        """Select all objects in the hierarchy of ancestor_id"""
        idStr = ','.join(str(i) for i in idList)
        cmd = self.selectCmd("name LIKE '%s.%%' AND id NOT IN (%s) "
                             % (ancestor_namePrefix, idStr))
        self.executeCommand(cmd)
        return self._results(iterate=False)

    def deleteMissingObjectsByAncestor(self, ancestor_namePrefix, idList):
        """Select all objects in the hierarchy of ancestor_id"""
        idStr = ','.join(str(i) for i in idList)
        cmd = "%s name LIKE '%s.%%' AND id NOT IN (%s) " % (self.DELETE, ancestor_namePrefix, idStr)
        self.executeCommand(cmd)

    def deleteAll(self):
        """ Delete all objects from the db. """
        self.executeCommand(self.DELETE + "1")
        self.executeCommand(self.DELETE_SEQUENCE)  # restart the count of ids
        
    def selectRelationChilds(self, relName, object_parent_id):
        self.executeCommand(self.SELECT_RELATION % ('child', 'parent'), 
                            (relName, object_parent_id))
        return self._results()
        
    def selectRelationParents(self, relName, object_child_id):
        self.executeCommand(self.SELECT_RELATION % ('parent', 'child'), 
                            (relName, object_child_id))
        return self._results()
    
    def selectRelationsByCreator(self, parent_id):
        self.executeCommand(self.SELECT_RELATIONS + PARENT_ID + "=?", (parent_id,))
        return self._results()
     
    def selectRelationsByName(self, relationName):
        self.executeCommand(self.SELECT_RELATIONS + "name=?", (relationName,))
        return self._results()
       
    def deleteRelationsByCreator(self, parent_id):
        self.executeCommand("DELETE FROM Relations where parent_id=?", (parent_id,))


class SqliteFlatMapper(Mapper):
    """Specific Flat Mapper implementation using Sqlite database"""
    def __init__(self, dbName, dictClasses=None, tablePrefix='',
                 indexes=None):
        Mapper.__init__(self, dictClasses)
        self._objTemplate = None
        self._attributesToStore = None
        try:
            # We (ROB and JMRT) are playing with different
            # PRAGMAS (see https://www.sqlite.org/pragma.html)
            # for the SqliteFlatMapper instances
            # We have been playing with the following
            # pragmas: {synchronous, journal_mode, temp_store and
            #  cache_size} and inside scipion no improvement
            # has been observed. Outside scipion a careful
            #  choosing of pragmas may duplicate the speed but
            # inside scipion, I think that the overhead due
            # to the manipulation of python classes is more
            # important that the data access.

            # uncommenting these pragmas increase the speed
            # by a factor of two if NO python object is manipulated.
            # Unfortunately, any interesting operation involve
            # creation and manipulation of python objects that take
            # longer than the access time to the database
            pragmas = {
                # 0 | OFF | 1 | NORMAL | 2 | FULL | 3 | EXTRA;
                # #'synchronous': 'OFF', # ON
                # DELETE | TRUNCATE | PERSIST | MEMORY | WAL | OFF
                # #'journal_mode': 'OFF', # DELETE
                # FILE 0 | DEFAULT | 1 | FILE | 2 | MEMORY;
                # #'temp_store': 'MEMORY',
                # PRAGMA schema.cache_size = pages;
                # #'cache_size': '5000' # versus -2000
                # "temp_store_directory": "'.'",
            }
            self.db = SqliteFlatDb(dbName, tablePrefix,
                                   pragmas=pragmas, indexes=indexes)
            self.doCreateTables = self.db.missingTables()
            
            if not self.doCreateTables:
                self.__loadObjDict()
        except Exception as ex:
            raise SqliteFlatMapperException('Error creating SqliteFlatMapper, '
                                            'dbName: %s, tablePrefix: %s\n error: %s' %
                                            (dbName, tablePrefix, ex))
    
    def commit(self):
        self.db.commit()
        
    def close(self):
        self.db.close()
        
    def insert(self, obj):
        if self.doCreateTables:
            self.db.createTables(obj.getObjDict(includeClass=True))
            self.doCreateTables = False
        """Insert a new object into the system, the id will be set"""
        self.db.insertObject(obj.getObjId(), obj.isEnabled(), obj.getObjLabel(), obj.getObjComment(), 
                             *self._getValuesFromObject(obj).values())

    def getAttributes2Store(self, item):

        if self._attributesToStore is None:
            self._attributesToStore = [key for key, value in item.getAttributesToStore()]

        return self._attributesToStore

    def _getValuesFromObject(self, item):

        valuesDict = OrderedDict()

        for attr in self.getAttributes2Store(item):
            item.fillObjDict('', valuesDict, False, attr, getattr(item, attr))

        return valuesDict

    def enableAppend(self):
        """ This will allow to append items to existing db. 
        This is by default not allow, since most sets are not 
        modified after creation.
        """
        if not self.doCreateTables:
            obj = self.selectFirst()
            if obj is not None:
                self.db.setupCommands(obj.getObjDict(includeClass=True))
        
    def clear(self):
        self.db.clear()
        self.doCreateTables = True
    
    def deleteAll(self):
        """ Delete all objects stored """
        self.db.deleteAll()
                
    def delete(self, obj):
        """Delete an object and all its childs"""
        self.db.deleteObject(obj.getObjId())
    
    def updateTo(self, obj, level=1):
        """ Update database entry with new object values. """ 
        if self.db.INSERT_OBJECT is None:
            self.db.setupCommands(obj.getObjDict(includeClass=True))
        args = list(obj.getObjDict().values())
        args.append(obj.getObjId())
        self.db.updateObject(obj.isEnabled(), obj.getObjLabel(), obj.getObjComment(), *args)

    def exists(self, objId):
        return self.db.doesRowExist(objId)

    def selectById(self, objId):
        """Build the object which id is objId"""
        objRow = self.db.selectObjectById(objId)
        if objRow is None:
            obj = None
        else:
            obj = self.__objFromRow(objRow)
        return obj

    def __loadObjDict(self):
        """ Load object properties and classes from db.
        Stores the _objTemplate for future reuse"""
        # Create a template object for retrieving stored ones
        columnList = []
        rows = self.db.getClassRows()

        # Adds common fields to the mapping
        # Schema definition in classes table
        self.db.addCommonFieldsToMap()

        attrClasses = {}
        self._objBuildList = []

        # For each row lin classes table (_samplinRate --> c01, Integer)
        for r in rows:

            # Something like: _acquisition._doseInitial
            label = r['label_property']

            # If the actual item class:  "Particle" in a SetOfParticles
            # First loop.
            if label == SELF:
                objClassName = r['class_name']

                # Store the template to reuse it during iterations and avoid instantiation
                self._objTemplate = self._buildObjectFromClass(objClassName)
                self._objClass = self._objTemplate.__class__
            else:
                # Update the database column mapping: c01 <-> _samplingRate
                self.db._columnsMapping[label] = r['column_name']

                # List for the latter _objColumns [(5,"_smplingRate"), ...]
                # This latter will be used to take the value from the cursor's row using the index (row[5] => obj._samplingRate)
                columnList.append(label)

                # Annotate the class
                attrClasses[label] = r['class_name']

                # Split the label: _acquisition._doseInitial -> ["_acquisition", "_doseInitial"]
                # For the loop
                attrParts = label.split('.')

                # Like a breadcrumb in websites... partial path to the attribute
                attrJoin = ''

                # Start from the template (root)
                o = self._objTemplate

                # for each part: ["_acquisition", "_doseInitial"]
                for a in attrParts:
                    attrJoin += a

                    # Try to get the attribute. Case of attributes defined in the model (init)
                    attr = getattr(o, a, None)

                    # If the object does not have the attribute, then it might be an extra parameter or an optional like Transform.p+ç1
                    if attr is None:
                        className = attrClasses[attrJoin]

                        # Instantiate the class.
                        attr = self._buildObjectFromClass(className)

                        # Get the class form the attr: it could come as a LegacyClass in case "className" is not found.
                        self._objBuildList.append((attr.__class__, attrJoin.split('.')))
                        setattr(o, a, attr)
                    o = attr
                    attrJoin += '.'
        basicRows = 5
        n = len(rows) + basicRows - 1
        self._objColumns = list(zip(range(basicRows, n), columnList))
         
    def __buildAndFillObj(self):
        """ Instantiates the set item base on the _objBuildList.
        _objBuildList has been populated when loading the classDictionary"""

        obj = self._objClass()
        
        for clazz, attrParts in self._objBuildList:
            o = obj
            for a in attrParts:
                attr = getattr(o, a, None)
                if not attr:
                    setattr(o, a, clazz())
                    break
                o = attr
        return obj

    def getInstance(self):

        if self._objTemplate is None:
            self.__loadObjDict()

        # Difference in performance using scipion3 tests pwperformance.tests.test_set_performance.TestSetPerformanceSteps.testSuperExtendedCoordinatesSet
        # A test that creates a 10**6 set of extended coordinates (coordinates with 20 extra attributes)
        # With the template iteration takes 10 secs
        # Building the object each time take 25 secs (15 seconds more)
        if Config.SCIPION_MAPPER_USE_TEMPLATE:
            return self._objTemplate
        else:
            return  self.__buildAndFillObj()

    def __objFromRow(self, objRow):

            
        obj = self.getInstance()
        obj.setObjId(objRow[ID])
        obj.setObjLabel(self._getStrValue(objRow['label']))
        obj.setObjComment(self._getStrValue(objRow['comment']))
        
        try:
            obj.setEnabled(objRow['enabled'])
            obj.setObjCreation(self._getStrValue(objRow[CREATION]))
        except Exception:
            # THIS SHOULD NOT HAPPEN
            logger.warning("'creation' column not found in object: %s" % obj.getObjId())
            logger.warning("         db: %s" % self.db.getDbName())
            logger.warning("         objRow: %s." % dict(objRow))

        for c, attrName in self._objColumns:
            obj.setAttributeValue(attrName, objRow[c])

        return obj
        
    def __iterObjectsFromRows(self, objRows, objectFilter=None):
        for objRow in objRows:
            obj = self.__objFromRow(objRow)
            if objectFilter is None or objectFilter(obj):
                yield obj
        
    def __objectsFromRows(self, objRows, iterate=False, objectFilter=None):
        """Create a set of object from a set of rows
        Params:
            objRows: rows result from a db select.
            iterate: if True, iterates over all elements, if False the whole
                list is returned
            objectFilter: function to filter some of the objects of the results. 
        """
        if not iterate:
            return [obj.clone()
                    for obj in self.__iterObjectsFromRows(objRows, objectFilter)]
        else:
            return self.__iterObjectsFromRows(objRows, objectFilter)
         
    def selectBy(self, iterate=False, objectFilter=None, **args):
        """Select object meetings some criteria"""
        objRows = self.db.selectObjectsBy(**args)
        return self.__objectsFromRows(objRows, iterate, objectFilter)
    
    def selectAll(self, iterate=True, objectFilter=None, orderBy=ID,
                  direction='ASC', where='1', limit=None):
        # Just a sanity check for emtpy sets, that doesn't contains
        # 'Properties' table
        if not self.db.hasTable('Properties'):
            return iter([]) if iterate else []

        # Initialize the instance
        self.getInstance()

        try:
            objRows = self.db.selectAll(orderBy=orderBy,
                                        direction=direction,
                                        where=where,
                                        limit=limit)
        except OperationalError as e:
            msg="""Error executing selectAll command: %s.
You may want to change the directory used by sqlite to create temporary files
to one that has enough free space. By default this directory is /tmp
You may achieve this goal by defining the SQLITE_TMPDIR environment variable
and restarting scipion. Export command:
    export SQLITE_TMPDIR=. """ % str(e)
            raise OperationalError(msg)
        
        return self.__objectsFromRows(objRows, iterate, objectFilter) 

    def unique(self, labels, where=None):
        """ Returns a list (for a single label) or a dictionary with unique values for the passed labels.
        If more than one label is passed it will be unique rows similar ti SQL unique clause.

        :param labels (string or list) item attribute/s to retrieve unique row values
        :param where (string) condition to filter the results"""

        if isinstance(labels, str):
            labels = [labels]

        rows = self.db.unique(labels, where)
        result = {label: [] for label in labels}  # Initialize the results dictionary
        for row in rows:
            for label in labels:
                result[label].append(row[label])

        # If there is only one label,
        if len(labels) == 1:
            return result[labels[0]]
        else:
            return result

    def aggregate(self, operations, operationLabel, groupByLabels=None):

        operations = valueToList(operations)
        groupByLabels = valueToList(groupByLabels)

        rows = self.db.aggregate(operations, operationLabel, groupByLabels)

        # Transform the sql row into a disconnected list of dictionaries
        results = []
        for row in rows:
            values = {}
            for key in row.keys():
                values[key] = row[key]
            results.append(values)

        return results

    def count(self):
        return 0 if self.doCreateTables else self.db.count()

    def maxId(self):
        return 0 if self.doCreateTables else self.db.maxId()

    def __objectsFromIds(self, objIds):
        """Return a list of objects, given a list of id's
        """
        return [self.selectById(rowId[ID]) for rowId in objIds]
    
    def hasProperty(self, key):
        return self.db.hasProperty(key)
        
    def getProperty(self, key, defaultValue=None):
        return self.db.getProperty(key, defaultValue)
        
    def setProperty(self, key, value):
        return self.db.setProperty(key, value)
    
    def deleteProperty(self, key):
        return self.db.deleteProperty(key)
    
    def getPropertyKeys(self):
        return self.db.getPropertyKeys()

    @staticmethod
    def fmtDate(date):
        """ Formats a python date into a valid string to be used in a where term
        Currently creation files is stored in utc time and is has no microseconds.

        :param date: python date un utc. use datetime.datetime.utcnow() instead of now()"""
        return "datetime('%s')" % date.replace(microsecond=0)

class SqliteFlatMapperException(Exception):
    pass


SELF = 'self'


class SqliteFlatDb(SqliteDb):
    """Class to handle a Sqlite database.
    It will create connection, execute queries and commands"""
    # Maintain the current version of the DB schema
    # useful for future updates and backward compatibility
    # version should be an integer number
    VERSION = 1
    
    CLASS_MAP = {'Integer': 'INTEGER',
                 'Float': 'REAL',
                 'Boolean': 'INTEGER'
                 }

    def __init__(self, dbName, tablePrefix='', timeout=1000,
                 pragmas=None, indexes=None):
        SqliteDb.__init__(self)
        self._pragmas = pragmas or {}
        self._indexes = indexes or []
        tablePrefix = tablePrefix.strip()
        # Avoid having _ for empty prefix
        if tablePrefix and not tablePrefix.endswith('_'):
            tablePrefix += '_'
        # NOTE (Jose Miguel, 2014/01/02
        # Reusing connections is a bit dangerous, since it have lead to
        # unexpected and hard to trace errors due to using an out-of-date
        # reused connection. That's why we are changing now the default to False
        # and only setting to True when the tablePrefix is non-empty, which is
        # the case for classes that are different tables in the same db and it
        # logical to reuse the connection.
        self._reuseConnections = bool(tablePrefix)

        self.CHECK_TABLES = ("SELECT name FROM sqlite_master WHERE type='table'"
                             " AND name='%sObjects';" % tablePrefix)
        self.SELECT = "SELECT * FROM %sObjects" % tablePrefix
        self.FROM = "FROM %sObjects" % tablePrefix
        self.DELETE = "DELETE FROM %sObjects WHERE " % tablePrefix
        self.INSERT_CLASS = ("INSERT INTO %sClasses (label_property, "
                             "column_name, class_name) VALUES (?, ?, ?)"
                             % tablePrefix)
        self.SELECT_CLASS = "SELECT * FROM %sClasses;" % tablePrefix
        self.EXISTS = "SELECT EXISTS(SELECT 1 FROM Objects WHERE %s=? LIMIT 1)"
        self.tablePrefix = tablePrefix
        self._createConnection(dbName, timeout)
        self.INSERT_OBJECT = None
        self.UPDATE_OBJECT = None
        self._columnsMapping = {}

        self.INSERT_PROPERTY = "INSERT INTO Properties (key, value) VALUES (?, ?)"
        self.DELETE_PROPERTY = "DELETE FROM Properties WHERE key=?"
        self.UPDATE_PROPERTY = "UPDATE Properties SET value=? WHERE key=?"
        self.SELECT_PROPERTY = "SELECT value FROM Properties WHERE key=?"
        self.SELECT_PROPERTY_KEYS = "SELECT key FROM Properties"

    def hasProperty(self, key):
        """ Return true if a property with this value is registered. """
        # The database not will not have the 'Properties' table when
        # there is not item inserted (ie an empty set)
        if not self.hasTable('Properties'):
            return False
        self.executeCommand(self.SELECT_PROPERTY, (key,))
        result = self.cursor.fetchone()
        return result is not None

    def getProperty(self, key, defaultValue=None):
        """ Return the value of a given property with this key.
        If not found, the defaultValue will be returned.
        """
        # The database not will not have the 'Properties' table when
        # there is not item inserted (ie an empty set)
        if not self.hasTable('Properties'):
            return defaultValue
        
        self.executeCommand(self.SELECT_PROPERTY, (key,))
        result = self.cursor.fetchone()

        if result:
            return result['value']
        else:
            return defaultValue

    def setProperty(self, key, value):
        """ Insert or update the property with a value. """
        # Just ignore the set property for empty sets
        if not self.hasTable('Properties'):
            return

        # All properties are stored as string, except for None type
        value = str(value) if value is not None else None

        if self.hasProperty(key):
            self.executeCommand(self.UPDATE_PROPERTY, (value, key))
        else:
            self.executeCommand(self.INSERT_PROPERTY, (key, value))
            
    def getPropertyKeys(self):
        """ Return all properties stored of this object. """
        self.executeCommand(self.SELECT_PROPERTY_KEYS)
        keys = [r[0] for r in self.cursor.fetchall()]
        return keys        

    def deleteProperty(self, key):
        self.executeCommand(self.DELETE_PROPERTY, (key,))

    def selectCmd(self, whereStr, orderByStr=' ORDER BY ' + ID):

        whereStr = "" if whereStr is None else " WHERE " + whereStr
        return self.SELECT + whereStr + orderByStr

    def missingTables(self):
        """ Return True is the needed Objects and Classes table are not
        created yet. """
        self.executeCommand(self.CHECK_TABLES)
        result = self.cursor.fetchone()

        return result is None

    def clear(self):
        self.executeCommand("DROP TABLE IF EXISTS Properties;")
        self.executeCommand("DROP TABLE IF EXISTS %sClasses;"
                            % self.tablePrefix)
        self.executeCommand("DROP TABLE IF EXISTS %sObjects;"
                            % self.tablePrefix)

    def createTables(self, objDict):
        """Create the Classes and Object table to store items of a Set.
        Each object will be stored in a single row.
        Each nested property of the object will be stored as a column value.
        """
        self.setVersion(self.VERSION)
        for pragma in self._pragmas.items():
            logger.debug("Executing pragma: %s" % pragma)
            self.executeCommand("PRAGMA %s = %s;" % pragma)
        # Create a general Properties table to store some needed values
        self.executeCommand("""CREATE TABLE IF NOT EXISTS Properties
                     (key       TEXT UNIQUE, -- property key                 
                      value     TEXT  DEFAULT NULL -- property value
                      )""")
        # Create the Classes table to store each column name and type
        self.executeCommand("""CREATE TABLE IF NOT EXISTS %sClasses
                     (id        INTEGER PRIMARY KEY AUTOINCREMENT,
                      label_property      TEXT UNIQUE, --object label                 
                      column_name TEXT UNIQUE,
                      class_name TEXT DEFAULT NULL  -- relation's class name
                      )""" % self.tablePrefix)
        CREATE_OBJECT_TABLE = """CREATE TABLE IF NOT EXISTS %sObjects
                     (id        INTEGER PRIMARY KEY,
                      enabled   INTEGER DEFAULT 1,   -- used to selected/deselect items from a set
                      label     TEXT DEFAULT NULL,   -- object label, text used for display
                      comment   TEXT DEFAULT NULL,   -- object comment, text used for annotations
                      creation  DATE                 -- creation date and time of the object
                      """ % self.tablePrefix

        c = 0
        colMap = {}
        for k, v in objDict.items():
            colName = 'c%02d' % c
            className = v[0]
            colMap[k] = colName
            c += 1
            self.executeCommand(self.INSERT_CLASS, (k, colName, className))
            if k != SELF:
                CREATE_OBJECT_TABLE += ',%s  %s DEFAULT NULL' % (colName, self.CLASS_MAP.get(className, 'TEXT'))

        CREATE_OBJECT_TABLE += ')'
        # Create the Objects table
        self.executeCommand(CREATE_OBJECT_TABLE)

        for idx in self._indexes:
            # first check if the attribute to be indexed exists
            if idx in colMap:
                self.executeCommand("CREATE INDEX index_%s ON Objects (%s);"
                                    % (idx.replace('.', '_'), colMap[idx]))

        self.commit()
        # Prepare the INSERT and UPDATE commands
        self.setupCommands(objDict)

    def setupCommands(self, objDict):
        """ Setup the INSERT and UPDATE commands base on the object dictionary. """
        self.INSERT_OBJECT = "INSERT INTO %sObjects (id, enabled, label, comment, creation" % self.tablePrefix
        self.UPDATE_OBJECT = "UPDATE %sObjects SET enabled=?, label=?, comment=?" % self.tablePrefix
        c = 0
        for k in objDict:
            colName = 'c%02d' % c
            self._columnsMapping[k] = colName
            c += 1
            if k != SELF:
                self.INSERT_OBJECT += ',%s' % colName
                self.UPDATE_OBJECT += ', %s=?' % colName

        self.addCommonFieldsToMap()

        self.INSERT_OBJECT += ") VALUES (?,?,?,?, datetime('now')" + ',?' * (c-1) + ')'
        self.UPDATE_OBJECT += ' WHERE id=?'

    def addCommonFieldsToMap(self):

        # Add common fields to the mapping
        self._columnsMapping[ID_COLUMN] = ID_COLUMN
        self._columnsMapping[ID_ATTRIBUTE] = ID_COLUMN

    def getClassRows(self):
        """ Create a dictionary with names of the attributes
        of the columns. """
        self.executeCommand(self.SELECT_CLASS)
        return self._results(iterate=False)

    def getSelfClassName(self):
        """ Return the class name of the attribute named 'self'.
        This is the class of the items stored in a Set.
        """
        self.executeCommand(self.SELECT_CLASS)

        for classRow in self._iterResults():
            if classRow['label_property'] == SELF:
                return classRow['class_name']
        raise Exception("Row '%s' was not found in Classes table. " % SELF)

    def insertObject(self, *args):
        """Insert a new object as a row.
        *args: id, label, comment, ...
        where ... is the values of the objDict from which the tables
        where created."""
        self.executeCommand(self.INSERT_OBJECT, args)

    def updateObject(self, *args):
        """Update object data """
        self.executeCommand(self.UPDATE_OBJECT, args)

    def selectObjectById(self, objId):
        """Select an object give its id"""
        self.executeCommand(self.selectCmd(ID + "=?"), (objId,))
        return self.cursor.fetchone()

    def doesRowExist(self, objId):
        """Return True if a row with a given id exists"""
        self.executeCommand(self.EXISTS % ID, (objId,))
        one = self.cursor.fetchone()
        return one[0] == 1

    def _getRealCol(self, colName):
        """ Transform the column name taking into account
         special columns such as: id or RANDOM(), and
         getting the mapping translation otherwise.
        """
        if colName in [ID, 'RANDOM()', CREATION]:
            return colName
        elif colName in self._columnsMapping:
            return self._columnsMapping[colName]
        else:
            return None
    def selectAll(self, iterate=True, orderBy=ID, direction='ASC',
                  where=None, limit=None):
        # Handle the specials orderBy values of 'id' and 'RANDOM()'
        # other columns names should be mapped to table column
        # such as: _micId -> c04

        if isinstance(orderBy, str):
            orderByCol = self._getRealCol(orderBy)
        elif isinstance(orderBy, list):
            orderByCol = ','.join([self._getRealCol(c) for c in orderBy])
        else:
            raise Exception('Invalid type for orderBy: %s' % type(orderBy))

        whereStr = self._whereToWhereStr(where)

        cmd = self.selectCmd(whereStr,
                             orderByStr=' ORDER BY %s %s'
                                        % (orderByCol, direction))
        # If there is a limit
        if limit:
            # if it is a tuple
            if isinstance(limit, tuple):
                limit, skipRows = limit  # Extract values from tuple
            else:
                skipRows = None
            # If we need to skip rows
            skipPart = "%s," % skipRows if skipRows else ""
            cmd += " LIMIT %s %s" % (skipPart, limit)

        self.executeCommand(cmd)
        return self._results(iterate)

    def _whereToWhereStr(self, where):
        """ Parse the where string to replace the column name with
        the real table column name ( for example: _micId -> c01 )
        Right now we are assuming a simple where string in the form
        colName=VALUE

        :param where string with pair of terms separated by "=" where left
        element is an attribute of the item

        >>> Example:
        >>> _micId=3 OR _micId=4
        """
        if where is None:
            return

        whereStr = where
        # Split by valid where operators: =, <, >
        result = re.split('<=|>=|=|<|>|AND|OR', where)
        # For each item
        for term in result:
            # trim it
            term = term.strip()
            whereRealCol = self._getRealCol(term)
            if whereRealCol is not  None:
                whereStr = whereStr.replace(term, whereRealCol)

        return whereStr

    def unique(self, labels, where=None):
        """ Returns the results of the execution of a UNIQUE query

        :param labels: list of attributes which you want unique values from
        :param where: condition to match in the form: attrName=value
        :return:
        """
        # let us count for testing
        selectStr = 'SELECT DISTINCT '
        separator = ' '
        # This cannot be like the following line should be expressed in terms
        # of c01, c02 etc (actual fields)....
        for label in labels:
            selectStr += "%s %s AS %s " % (separator, self._getRealCol(label), label)
            separator = ', '

        sqlCommand = selectStr + self.FROM

        whereStr = self._whereToWhereStr(where)
        if whereStr is not None:
            sqlCommand += " WHERE " + whereStr

        self.executeCommand(sqlCommand)
        return self._results(iterate=False)

    def aggregate(self, operations, operationLabel, groupByLabels=None):
        """

        :param operations: string or LIST of operations: MIN, MAX, AVG, COUNT, SUM, TOTAL, GROUP_CONCAT. Any single argument function
        defined for sqlite at https://www.sqlite.org/lang_aggfunc.html
        :param operationLabel: string or LIST of attributes to apply the functions on
        :param groupByLabels: (Optional) attribute or list of attributes to group by the data
        :return:
        """
        # let us count for testing
        selectStr = 'SELECT '
        separator = ' '

        operations = valueToList(operations)
        operationLabel = valueToList(operationLabel)
        groupByLabels = valueToList(groupByLabels)

        # This cannot be like the following line should be expressed in terms
        # of C1, C2 etc....
        for index,label in enumerate(operationLabel):
            for operation in operations:

                if index==0:
                    alias = operation
                else:
                    alias = operation + label

                selectStr += "%s %s(%s) AS %s" % (separator, operation,
                                                  self._columnsMapping[label],
                                                  alias)
                separator = ', '
        if groupByLabels:
            groupByStr = 'GROUP BY '
            separator = ' '
            for groupByLabel in groupByLabels:
                groupByCol = self._columnsMapping[groupByLabel]
                selectStr += ', %(groupByCol)s as "%(groupByLabel)s"' % locals()
                groupByStr += "%s %s" % (separator, groupByCol)
                separator = ', '
        else:
            groupByStr = ' '
        sqlCommand = selectStr + "\n" + self.FROM + "\n" + groupByStr
        self.executeCommand(sqlCommand)
        return self._results(iterate=False)

    def count(self):
        """ Return the number of element in the table. """
        self.executeCommand(self.selectCmd('1').replace('*', 'COUNT(id)'))
        return self.cursor.fetchone()[0]

    def maxId(self):
        """ Return the maximum id from the Objects table. """
        self.executeCommand(self.selectCmd('1').replace('*', 'MAX(id)'))
        return self.cursor.fetchone()[0]

    # FIXME: Seems to be duplicated and a subset of selectAll
    def selectObjectsBy(self, iterate=False, **args):
        """More flexible select where the constrains can be passed
        as a dictionary, the concatenation is done by an AND"""
        whereList = ['%s=?' % k for k in args.keys()]
        whereStr = ' AND '.join(whereList)
        whereTuple = tuple(args.values())
        whereStr = self._whereToWhereStr(whereStr)
        self.executeCommand(self.selectCmd(whereStr), whereTuple)
        return self._results(iterate)

    # FIXME: Seems to be duplicated and a subset of selectAll
    # Moreover, it does not translate between "user columns" and
    # "internal" Objects table columns
    def selectObjectsWhere(self, whereStr, iterate=False):
        self.executeCommand(self.selectCmd(whereStr))
        return self._results(iterate)

    def deleteObject(self, objId):
        """Delete an existing object"""
        self.executeCommand(self.DELETE + "id=?", (objId,))

    def deleteAll(self):
        """ Delete all objects from the db. """
        if not self.missingTables():
            self.executeCommand(self.DELETE + "1")

