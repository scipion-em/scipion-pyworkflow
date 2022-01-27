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

import logging
import os
import sys
logger = logging.getLogger(__name__)
from pyworkflow.exceptions import PyworkflowException
from pyworkflow.utils import STATUS, getExtraLogInfo, Config, getFinalProjId
from sqlalchemy import create_engine

class AlchemyDb:
    """Class to handle alchemy Engines.
    It will create connection, execute queries and commands.
    """

    def __init__(self, dbName):

        self._engine = EnginePool.getEngine(dbName)

        # For server DB the database should match the project name and all the "db" (*.sqlite) inside
        # a project will become prefixed
        self.tablePrefix = self.getPrefixFromDBName(dbName)

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
        forbiddenChars = "/. "
        for char in forbiddenChars:
            path = path.replace(char, "_")

        return path

    @classmethod
    def getPrefixFromDBName(cls, dbname):
        if EnginePool.isServer():
            return cls.slugifyPath(dbname)
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

    def _iterResults(self):
        row = self.cursor.fetchone()
        while row is not None:
            yield row
            row = self.cursor.fetchone()
        
    def _results(self, iterate=False):
        """ Return the results to which cursor, point to. 
        If iterates=True, iterate yielding each result independently"""
        if not iterate:
            return self.cursor.fetchall()
        else:
            return self._iterResults()
        
    def getTables(self):
        """ Return the table names existing in the Database with a prexif.
        If  tablePattern is not None, only tables matching 
        the pattern will be returned.
        """

        self.executeCommand("SELECT * FROM information_schema.tables where table_type = 'BASE TABLE' and table_schema = ''")
        return [str(row['name']) for row in self._iterResults()]
    
    def hasTable(self, tableName):
        return tableName in self.getTables()
    
    def getTableColumns(self, tableName):
        self.executeCommand('PRAGMA table_info(%s)' % tableName)
        return self.cursor.fetchall()
    
    def getVersion(self):
        """ Return the database 'version' that is used.
        Internally it make use of the SQLite PRAGMA database.user_version;
        """
        self.executeCommand('PRAGMA user_version')
        return self.cursor.fetchone()[0]
    
    def setVersion(self, version):
        self.executeCommand('PRAGMA user_version=%d' % version)
        self.commit()


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

class SchemaHandler:
    """ Handles all schema operations: create tables, schema queries,..."""
    def __init__(self, engine, prefix):
        self._engine = engine
        self._prefix = prefix

    def getTables(self):
        """ Return the table names existing in the Database with a prexif.
        If  tablePattern is not None, only tables matching
        the pattern will be returned.
        """
        tables = []
        with self._engine.connect() as conn:

            results = conn.execute("SELECT table_name FROM information_schema.tables where table_type = 'BASE TABLE' and table_schema = '%s'" % self._prefix)
            tables = [str(row['table_name']) for row in results]

        return  tables

    def hasTable(self, tableName):
        return tableName in self.getTables()


    def getTableColumns(self, tableName):
        """ Returns a list of all column names of a table with a prefix (schema)"""
        columns = []
        with self._engine.connect() as conn:
            results = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = '%s' AND table_name   = '%s'" % (self._prefix, tableName))
            columns = [str(row['column_name']) for row in results]

        return columns