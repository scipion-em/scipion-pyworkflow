# **************************************************************************
# *
# * Authors:     Pablo Conesa (pconesa@cnb.csic.es)
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
This module contains some sqlite basic tools to handle Databases.
"""
import datetime
import logging
import os
import sys
logger = logging.getLogger(__name__)
from pyworkflow.exceptions import PyworkflowException
from pyworkflow.utils import STATUS, getExtraLogInfo, Config, getFinalProjId
from sqlalchemy import create_engine, insert, MetaData, Integer, Table, Column, String, ForeignKey, Unicode, DateTime, \
    Text


class AlchemyDb:
    """Class to handle alchemy Engines.
    It will create connection, execute queries and commands.
    """

    def __init__(self, dbName):

        self._engine = EnginePool.getEngine(dbName)

        # For server DB the database should match the project name and all the "db" (*.sqlite) inside
        # a project will become prefixed
        self.tablePrefix = self.getPrefixFromDBName(dbName)
        self.queryProvider = ObjectsQueryProvider(self.tablePrefix)

        # # Check database exists, if not we should create it
        # self._createDatabase()

    def _createDatabase(self, database=None):
        """ Creates a database in case it does not exists"""
        # For sqlite mode do not create the file
        if not EnginePool.isServer():
            return
        with self._engine.connect() as conn:

            try:
                conn.execute("commit")
                # Do not substitute user-supplied database names here.
                database = getFinalProjId(database)
                conn.execute("CREATE DATABASE " + database)
                conn.execute("SET search_path TO " + database)
            except Exception as e:

                # Database exists or not priviledges
                # Clear the previous exceptions
                raise PyworkflowException.raiseFromException(e, "Database %s couldn't be created. DB user should be allowed to create databases"
                                                                 "on the server." % database)

    @classmethod
    def slugifyPath(cls, path):
        """ Replaces any invalid server DB char in dbName by _. Based on this doc:
        https://www.postgresql.org/docs/9.2/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
        mostly letters, then numbers are valid"""

        # Let's assume path only come with / . or spaces. Finger cross.
        forbiddenChars = "/. -"
        for char in forbiddenChars:
            path = path.replace(char, "_")

        return path

    @classmethod
    def getPrefixFromDBName(cls, dbname):
        if EnginePool.isServer():
            dbname = dbname.replace(".sqlite", "").replace(".db","")
            return cls.slugifyPath(dbname) + "_"
        else:
            # No prefix for file base DB (sqlite)
            return ''
    @classmethod
    def closeConnection(cls, dbName):
        pass
        #TODO: this might not be nedded if other operations can be done as a context connection
        # if dbName in cls.OPEN_CONNECTIONS:
        #     connection = cls.OPEN_CONNECTIONS[dbName]
        #     del cls.OPEN_CONNECTIONS[dbName]
        #     connection.close()
        #     logger.debug("Connection closed for %s" % dbName,
        #                  extra=getExtraLogInfo('CONNECTIONS', STATUS.STOP, dbfilename=dbName))

    def getDbName(self):
        return self._dbName
    
    def close(self):
        pass
        # self.connection.close()
        # logger.debug("Connection closed for %s" % self._dbName,
        #              extra=getExtraLogInfo(
        #                                 "CONNECTIONS",
        #                                 STATUS.STOP,
        #                                 dbfilename=self._dbName))
        # if self._dbName in self.OPEN_CONNECTIONS:
        #     del self.OPEN_CONNECTIONS[self._dbName]
    # TODO differently: logging?
    # def _debugExecute(self, *args):
    #     try:
    #         logger.debug("COMMAND: %s; %s" %(args[0] , self._dbName),
    #             extra=getExtraLogInfo("QUERY", STATUS.EVENT, dbfilename=self._dbName)
    #         )
    #         logger.debug("ARGUMENTS: " + str(args[1:]))
    #         return self.cursor.execute(*args)
    #     except Exception as ex:
    #         print(">>>> FAILED cursor.execute on db: '%s'" % self._dbName)
    #         raise ex
    def executeCommand(self, *args):
        """ Executes any SQL Command"""
        with self._engine.connect() as conn:
            result = conn.execute(*args)
            return result

    def _iterResults(self, cursor):
        row = cursor.fetchone()
        while row is not None:
            yield row
            row = cursor.fetchone()
        
    def _results(self, cursor, iterate=False):
        """ Return the results to which cursor, point to. 
        If iterates=True, iterate yielding each result independently"""
        if not iterate:
            return cursor.fetchall()
        else:
            return self._iterResults(cursor)
    
    def getVersion(self):
        """ Return the database 'version' that is used.
        Internally it make use of the SQLite PRAGMA database.user_version;
        """
        #TODO: handle version properly when running on a server
        # self.executeCommand('PRAGMA user_version')
        # return self.cursor.fetchone()[0]
    
    def setVersion(self, version):
        self.executeCommand('PRAGMA user_version=%d' % version)
        self.commit()

    def getTables(self):
        """ Return the table names existing in the Database with a prexif.
        If  tablePattern is not None, only tables matching
        the pattern will be returned.
        """
        tables = []
        with self._engine.connect() as conn:

            results = conn.execute(self.queryProvider.getTablesQuery())
            tables = [str(row['table_name']) for row in results]

        return  tables

    def hasTable(self, tableName):
        return tableName in self.getTables()


    def getTableColumns(self, tableName):
        """ Returns a list of all column names of a table with a prefix (schema)"""
        columns = []
        with self._engine.connect() as conn:
            results = conn.execute(self.queryProvider.getTableColumnsQuery(tableName))
            columns = [str(row['column_name']) for row in results]

        return columns


class EnginePool:
    """ Class to host a pool SQLAlchemy engines bases on the database connection configuration.
     Depending on the persistence DB selected (default to sqlite) there can be one engine (case for
     server based DB or one per sqlite
     """

    # Dictionary for engines. Key would be the database path as used from consumers
    # For historical reasons, it all started with sqlite,  so key is a path to Å
    # sqlite db that has to be "translated" into server based schemas or prefixes
    _enginePool = dict()

    @classmethod
    def clear(cls):
        """ Clears te pool

        :return: None
        """
        # For now let's do a dicttionary clear. We may need to "clear" the engines?
        for engine in cls._enginePool.values():
            engine.dispose()
        cls._enginePool.clear()

    @classmethod
    def getEngine(cls, dbName):
        """ Returns the engine associated to the dbName or creates one"""

        if dbName in cls._enginePool:
            return cls._enginePool[dbName]
        else:
            return cls.createEngine(dbName)

    @classmethod
    def getDBConnectionString(cls, dbName):
        """ Composes a connection string to a specific database in a SERVER"""
        return Config.SCIPION_CONNECTION_STRING + "/" + dbName

    @classmethod
    def createGenericEngine(cls, connectionString=None):
        """ A Generic engine a and engine that will connect JUST to a server and not to a specific database.
         It will be used to handle databases: CREATE, DROP them

         :param connectionString: Optional, if absent Config.SCIPION_CONNECTION_STRING will br used
         :returns the new or already existing generic engine"""

        key = Config.SCIPION_CONNECTION_STRING if connectionString is None else connectionString
        if key not in cls._enginePool.keys():
            newGenericEngine = create_engine(key)
            cls._enginePool[key] = newGenericEngine

        return cls._enginePool[key]

    @classmethod
    def createEngine(cls, dbName):
        """ Creates an engine based on the dbName and persistence DB configured"""

        # For now we do not expect multiple DB connections.
        # This could be the case when importing into the server some sqlite sets.
        # In this case we should bring the context here and not us isSever that relies 100%
        # in the enviroment
        if cls.isServer():

            # We do not care about dbName: we are assuming this is in the context of
            # a Project, therefore there should be a single engine for all "dbs"
            # in the same project.
            projId = getFinalProjId(None)

            if projId not in cls._enginePool.keys():
                newEngine = create_engine(cls.getDBConnectionString(projId))
                cls._enginePool[projId] = newEngine

                # Creates the database matching the project name
                cls.createDatabase(projId)
            else:
                newEngine = cls._enginePool[projId]

            if dbName not in cls._enginePool.keys():
                cls._enginePool[dbName] = newEngine

            return cls._enginePool[projId]
        # Sqlite mode
        else:
            newEngine = create_engine("sqlite://"+ dbName)
            cls._enginePool[dbName] = newEngine
            return newEngine

    @classmethod
    def createDatabase(cls, database):
        """ Creates a database in a server based SQL server if it does not exists"""
        with cls.createGenericEngine().connect() as conn:

            try:
                conn.execute("commit")
                # Do not substitute user-supplied database names here.
                database = getFinalProjId(database)
                conn.execute("CREATE DATABASE " + database)
                conn.execute("SET search_path TO " + database)
            except Exception as e:

                # Database exists or not priviledges
                # Clear the previous exceptions
                raise PyworkflowException.raiseFromException(e,
                                                             "Database %s couldn't be created. DB user should be allowed to create databases"
                                                             "on the server." % database)
    @classmethod
    def deleteDatabase(cls, database):
        """ Deletes a database using the generic engine"""
        # For sqlite mode do not create the file
        if not EnginePool.isServer():
            os.remove(database)
            return
        with cls.createGenericEngine().connect() as conn:

            try:
                conn.execute("commit")
                # Do not substitute user-supplied database names here.
                database = getFinalProjId(database)
                conn.execute("DROP DATABASE " + database)
            except Exception as e:

                # Database exists or not priviledges
                # Clear the previous exceptions
                raise PyworkflowException.raiseFromException(e, "Database %s couldn't be dropped. DB user should be allowed to DROP databases "
                                                                 "on the server." % database)

    @classmethod
    def isServer(cls):
        """ Returns true if persistence is to a server based SQL database.
        if SCIPION_CONNECTION_STRING has something has to be, for now a SQL server option:
        Any compatible one with SQLAlchemy: postgresql, MariaDB, MySQL, ORACLE, SQLServer
        """
        return Config.SCIPION_CONNECTION_STRING is not None


class ObjectsQueryProvider:
    """ Defines al needed queries and prefixes the tables with a prefix"""

    TABLES = "SELECT table_name FROM information_schema.tables where table_type = 'BASE TABLE' and table_name IN ('Relations', 'Objects')"
    COLUMNS = "SELECT column_name FROM information_schema.columns WHERE table_name = '%s'"
    SELECT = 'SELECT id, parent_id, name, classname, value, label, comment, creation FROM public."Objects"'
    DELETE = "DELETE FROM Objects WHERE "
    EXISTS = 'SELECT EXISTS(SELECT 1 FROM public."Objects" WHERE %s=%%s LIMIT 1)'

    # OBJECTS table Queries
    # CREATE_OBJECTS_TABLE = """CREATE TABLE IF NOT EXISTS Objects
    #                  (id        SERIAL PRIMARY KEY,
    #                   parent_id INTEGER REFERENCES Objects(id),
    #                   name      TEXT,                -- object name
    #                   classname TEXT,                -- object's class name
    #                   value     TEXT DEFAULT NULL,   -- object value, used for Scalars
    #                   label     TEXT DEFAULT NULL,   -- object label, text used for display
    #                   comment   TEXT DEFAULT NULL,   -- object comment, text used for annotations
    #                   creation  DATE                 -- creation date and time of the object
    #                   )"""

    # Use alchqemy STYLE
    #INSERT_OBJECT = 'INSERT INTO Objects (parent_id, name, classname, value, label, comment, creation) VALUES (%s, %s, %s, %s, %s, %s, NOW())'
    UPDATE_OBJECT = 'UPDATE public."Objects" SET parent_id=%s, name=%s, classname=%s, value=%s, label=%s, comment=%s WHERE id=%s'

    # RELATIONS table queries
    # CREATE_RELATIONS_TABLE = """CREATE TABLE IF NOT EXISTS Relations
    #                  (id        SERIAL PRIMARY KEY,
    #                   parent_id INTEGER REFERENCES Objects(id), -- object that created the relation
    #                   name      TEXT,               -- relation name
    #                   classname TEXT DEFAULT NULL,  -- relation's class name
    #                   value     TEXT DEFAULT NULL,  -- relation value
    #                   label     TEXT DEFAULT NULL,  -- relation label, text used for display
    #                   comment   TEXT DEFAULT NULL,  -- relation comment, text used for annotations
    #                   object_parent_id  INTEGER REFERENCES Objects(id) ON DELETE CASCADE,
    #                   object_child_id  INTEGER REFERENCES Objects(id) ON DELETE CASCADE,
    #                   creation  DATE,                 -- creation date and time of the object
    #                   object_parent_extended TEXT DEFAULT NULL, -- extended property to consider internal objects
    #                   object_child_extended TEXT DEFAULT NULL
    #                   )"""
    # INSERT_RELATION ="INSERT INTO Relations " \
    #                  "(parent_id, name, object_parent_id, object_child_id, creation, object_parent_extended, object_child_extended)" \
    #                  " VALUES (?, ?, ?, ?, datetime('now'), ?, ?)"

    SELECT_RELATION = "SELECT object_%s_id AS id FROM Relations WHERE name=? AND object_%s_id=?"
    SELECT_RELATIONS = "SELECT * FROM Relations WHERE "

    ##??? SQLITE
    # DELETE_SEQUENCE = "DELETE FROM SQLITE_SEQUENCE WHERE name='Objects'"


    def __init__(self, prefix):
        self._prefix = prefix
        self.objects = None
        self.relations = None
        self.metadata = MetaData()

    def getRelationsTable(self):
        """ Returns the Relations table equivalent to:

        CREATE_RELATIONS_TABLE = CREATE TABLE IF NOT EXISTS Relations
            (id        SERIAL PRIMARY KEY,
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
            object_child_extended TEXT DEFAULT NULL)
        """

        if self.relations is None:
            self.relations = Table("Relations", self.metadata,
                Column('id', Integer, primary_key=True),
                Column("parent_id", Integer, ForeignKey("Objects.id"),nullable=True),
                Column("name", Text),
                Column("classname", Unicode, nullable=True),
                Column("value", Unicode, nullable=True),
                Column("label", Unicode, nullable=True),
                Column("comment", Unicode, nullable=True),
                Column("creation", DateTime, nullable=False),
                Column("object_parent_id", Integer, ForeignKey("Objects.id", ondelete="CASCADE"),nullable=True),
                Column("object_child_id", Integer, ForeignKey("Objects.id", ondelete="CASCADE"), nullable=True),
                Column("object_parent_extended", Unicode, nullable=True),
                Column("object_child_extended", Unicode, nullable=True)
           )
        return self.relations

    def getObjectsTable(self):
        """ returns the Objects table equivalent to:

        CREATE TABLE IF NOT EXISTS Objects
            (id        SERIAL PRIMARY KEY,
            parent_id INTEGER REFERENCES Objects(id),
            name      TEXT,                -- object name
            classname TEXT,                -- object's class name
            value     TEXT DEFAULT NULL,   -- object value, used for Scalars
            label     TEXT DEFAULT NULL,   -- object label, text used for display
            comment   TEXT DEFAULT NULL,   -- object comment, text used for annotations
            creation  DATE                 -- creation date and time of the object
            )

        """
        if self.objects is None:
            self.objects = Table('Objects', self.metadata,
                Column('id', Integer, primary_key=True),
                Column('parent_id', Integer, ForeignKey("Objects.id"),nullable=True),
                Column('name', Unicode,nullable=False),
                Column('classname', Unicode),
                Column('value', Unicode, nullable=True),
                Column('label', Unicode, nullable=True),
                Column('comment', Unicode, nullable=True),
                Column('creation', DateTime, nullable=False)
            )

        return  self.objects

    def getExistsQuery(self, where):
        """ Returns a query which tells if a ROW matching a where param EXISTS query with a prefix if apply"""
        return "SELECT EXISTS(SELECT 1 FROM Objects WHERE %s=? LIMIT 1)" %  where

    def getRelationQuery(self, selectColumn, whereColumn):
        """ Returns the RELATION query with a prefix if apply"""
        return self.SELECT_RELATION % (selectColumn, whereColumn)

    def getRelationsQuery(self):
        """ Returns the RELEATIONS query with a prefix if apply"""
        return self.SELECT_RELATIONS

    def getDeleteQuery(self):
        """ Returns the DELETE query with a prefix if apply"""
        return self.DELETE
    def getSelectQuery(self):
        """ Returns the SELECT query with a prefix if apply"""
        return self.SELECT

    def getTablesQuery(self):
        """ Query to return the tables in a database having a prefix"""
        return self.TABLES

    def getTableColumnsQuery(self, tableName):
        """ Returns a query with all columns of a table applying the prefix"""
        return self.COLUMNS % tableName

    def getInsertRelationQuery(self, parent_id, name, object_parent_id, object_child_id, object_parent_extended, object_child_extended):
        """
        return the equivalent of:
            INSERT INTO Relations
                (parent_id, name, object_parent_id, object_child_id, creation, object_parent_extended, object_child_extended)
            VALUES (?, ?, ?, ?, datetime('now'), ?, ?)

        :return: Insert query object
        """
        return insert(self.getRelationsTable()).values(
            parent_id=parent_id,
            name=name,
            object_parent_id=object_parent_id,
            object_child_id=object_child_id,
            creation=datetime.datetime.now(),
            object_parent_extended=object_parent_extended,
            object_child_extended=object_child_id)


    def getInsertObjectQuery(self, name, classname, value, parent_id, label, comment):
        """
        return the equivalent of:
        INSERT INTO Objects (parent_id, name, classname, value, label, comment, creation) VALUES (?, ?, ?, ?, ?, ?, now())'
        :param name: 
        :param classname: 
        :param value: 
        :param parent_id: 
        :param label: 
        :param comment: 
        :return: 
        """
        return insert(self.getObjectsTable()).values(
            name=name,
            classname=classname,
            value=value,
            parent_id=parent_id,
            label=label,
            comment=comment,
            creation=datetime.datetime.now())
