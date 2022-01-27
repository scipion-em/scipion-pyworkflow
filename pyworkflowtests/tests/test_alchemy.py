
from unittest import TestCase
from pyworkflow.config import Config
from pyworkflow.mapper.alchemy_db import EnginePool, AlchemyDb,SchemaHandler
from pyworkflow.tests import setupTestOutput, BaseTest
from pyworkflow.utils.log import setFinalProjId
import logging
logger = logging.getLogger(__name__)

""" Tests core functionality engine pool """
class TestEnginePool(BaseTest):

    PROJ_ID = "scipion_db_test"

    @classmethod
    def setUpClass(cls):
        setupTestOutput(cls)
        # Setup the project name
        setFinalProjId(cls.PROJ_ID)

    @classmethod
    def dropDatabase(cls):
        # Try to drop the database in case of an unfinished test
        try:
            EnginePool.deleteDatabase(cls.PROJ_ID)
            print("Database existed before test??")
        except Exception as e:
            print(e)

    def test_sqlite_mode(self):

        #Clean the pool
        EnginePool.clear()
        tmpConnectionString =Config.SCIPION_CONNECTION_STRING

        # Force sqlite mode
        Config.SCIPION_CONNECTION_STRING = None

        self.assertFalse(EnginePool.isServer(), "SQLITE mode detected as server mode")

        newEngine = EnginePool.getEngine("/tmp/scipion-test.sqlite")

        self.assertIsNotNone(newEngine, "New engine not created")
        self.assertEqual(1, len(EnginePool._enginePool), "Sqlite engine not stored in pool")

        # Ask for the same engine:
        secondTime = EnginePool.getEngine("/tmp/scipion-test.sqlite")
        self.assertEqual(id(newEngine), id(secondTime), "Engines for the same sqlite is not the same")

        # Ask for a second database
        secondEngine = EnginePool.getEngine("/tmp/scipion_test2.sqlite")
        self.assertIsNotNone(secondEngine, "Second engine not created")
        self.assertEqual(2, len(EnginePool._enginePool), "Second Sqlite engine not stored in pool")
        self.assertNotEqual(id(newEngine), id(secondEngine), "Engines for different sqlite is the same")

        # Restore configuration for future tests
        Config.SCIPION_CONNECTION_STRING = tmpConnectionString


    def test_server_mode(self):

        EnginePool.clear()

        if Config.SCIPION_CONNECTION_STRING is None:
            print("SCIPION_CONNECTION_STRING not found in the environemnt. Cannot test this persistence mode")
            return

        self.assertTrue(EnginePool.isServer(), "Server mode not detected by EnginePool")

        self.dropDatabase()

        newEngine = EnginePool.getEngine("/tmp/scipion-test.sqlite")

        self.assertIsNotNone(newEngine, "New engine not created")
        self.assertEqual(3, len(EnginePool._enginePool), "Generic engine, db engine and 'schema' engine not stored in pool")

        # Ask for the same engine:
        secondTime = EnginePool.getEngine("/tmp/scipion-test.sqlite")
        self.assertEqual(id(newEngine), id(secondTime), "Engines for the same sqlite is not the same")

        # Ask for a second database
        secondEngine = EnginePool.getEngine("/tmp/scipion_test2.sqlite")
        self.assertIsNotNone(secondEngine, "Second engine not created")
        self.assertEqual(4, len(EnginePool._enginePool), "Second engine must be same as first but added")
        self.assertEqual(id(newEngine), id(secondEngine), "Engines for different dnNamea are not the same")

    def test_alchemyDb_server_mode(self):

        EnginePool.clear()

        # If server configuration available
        if Config.SCIPION_CONNECTION_STRING is None:
            print("SCIPION_CONNECTION_STRING not found in the environment. Cannot test this persistence mode")
            return

        self.dropDatabase()
        # Get an Alchemy DB instance
        alchemyDB = AlchemyDb("myset.sqlite")
        # Get the tables, shoulb be 0
        schemaHanlder = SchemaHandler(alchemyDB._engine, "myschema")
        self.assertEqual(len(schemaHanlder.getTables()), 0, "getTables returns tables??")

        # Let's create a table
        with alchemyDB._engine.connect() as conn:
            conn.execute("CREATE SCHEMA myschema")
            conn.execute("CREATE TABLE myschema.films (code char(5) CONSTRAINT firstkey PRIMARY KEY, title varchar(40) NOT NULL)")

        tables = schemaHanlder.getTables()
        self.assertEqual(len(tables), 1, "getTables does not return right tables")
        self.assertEqual(len(schemaHanlder.getTableColumns("films")),2, "getTableColumns does not return right amount fo fields")

        self.dropDatabase()


