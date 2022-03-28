
from unittest import TestCase
from pyworkflow.config import Config
from pyworkflow.mapper.alchemy_db import EnginePool, AlchemyDb,ObjectsQueryProvider
from pyworkflow.mapper.alchemysql import ObjectsDb
from pyworkflow.tests import setupTestOutput, BaseTest
from pyworkflow.utils.log import setFinalProjId
from pyworkflow.object import String
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

        self.assertEqual(len(alchemyDB.getTables()), 0, "getTables returns tables??")

        # Let's create a table
        with alchemyDB._engine.connect() as conn:
            conn.execute("CREATE TABLE myset_films (code char(5) CONSTRAINT firstkey PRIMARY KEY, title varchar(40) NOT NULL)")
        tables = alchemyDB.getTables()
        self.assertEqual(len(tables), 1, "getTables does not return right tables")
        self.assertEqual(len(alchemyDB.getTableColumns("films")),2, "getTableColumns does not return right amount fo fields")

        EnginePool.clear()
        self.dropDatabase()

    def test_query_provider(self):

        prefix = "myprefix"
        # qp = ObjectsQueryProvider(prefix)
        #
        # # Test queries are prefixed
        # self.assertTrue(prefix in qp.getSelectQuery(), "SELECT query not prefixed")
        # self.assertTrue(prefix in qp.getDeleteQuery(), "DELETE query not prefixed")
        # self.assertTrue(prefix in qp.getRelationQuery("column", "where"), "RELATION query not prefixed")
        # self.assertTrue(prefix in qp.getRelationsQuery(), "RELATIONS query not prefixed")
        # self.assertTrue(prefix in qp.getExistsQuery("where"), "EXISTS query not prefixed")

    def test_AlchemyObjectsDb(self):

        EnginePool.clear()

        # If server configuration available
        if Config.SCIPION_CONNECTION_STRING is None:
            print("SCIPION_CONNECTION_STRING not found in the environment. Cannot test this persistence mode")
            return

        self.dropDatabase()

        # Instantiate object db
        odb = ObjectsDb("project.sqlite")

        tables = odb.getTables()
        self.assertEqual(len(tables), 2, "ObjectsDb does not create 2 tables.")
        self.assertTrue(odb.hasTable("Relations"), "Relations table not created")
        self.assertTrue(odb.hasTable("Objects"), "Objects table not created")

        # Persist a String
        id = odb.insertObject("name丌", "class", "value", None, "label", "comment")
        self.assertEqual(id, 1, "last row id is not returned")
        row = odb.selectObjectById(id)
        self.assertEqual("name丌", row["name"], "name not stored or retrieved.")
        self.assertEqual("class", row["classname"], "class not stored or retrieved.")
        self.assertEqual(None, row["parent_id"], "Name not stored or retrieved.")
        self.assertEqual("value", row["value"], "label not stored or retrieved.")
        self.assertEqual("label", row["label"], "name not stored or retrieved.")
        self.assertEqual("comment", row["comment"], "comment not stored or retrieved.")

        # Update an object
        odb.updateObject(id, "newName", "newClass","newValue", None, "newLabel", "newComment")
        row = odb.selectObjectById(id)
        self.assertEqual("newName", row["name"], "name not stored or retrieved.")
        self.assertEqual("newClass", row["classname"], "class not stored or retrieved.")
        self.assertEqual("newValue", row["value"], "label not stored or retrieved.")
        self.assertEqual("newLabel", row["label"], "name not stored or retrieved.")
        self.assertEqual("newComment", row["comment"], "comment not stored or retrieved.")

        # Rox existence
        self.assertTrue(odb.doesRowExist(1), "row should exist")
        self.assertFalse(odb.doesRowExist(2), "row shouldn't exist")
        self.assertTrue(odb.doesRowExist("newClass", field="classname"), "row should exist using other field than ID")

        # Insert a second element
        id = odb.insertObject("1.name", "class2", "value2", id, "label2", "newComment")
        self.assertEqual(id, 2, "last row id is not returned for the second item")
        results= odb.selectAllObjects()

        # test cursor is iterable
        self.assertEqual(len(results), 2, "selectAllObjects does not return the 2 items")

        # Select by parent
        results = odb.selectObjectsByParent(1)
        self.assertEqual(len(results), 1, "selectObjectsByParent does not return the single existing child")

        results= odb.selectObjectsByAncestor("1")
        self.assertEqual(len(results), 1, "selectObjectsByAncestor does not return the single existing child")

        # Select object by "nothing" = all
        results= odb.selectObjectsBy()
        self.assertEqual(len(results), 2, "selectObjectsBy empty does not return all items.")

        # Select object by 1 field
        results = odb.selectObjectsBy(classname="class2")
        self.assertEqual(len(results), 1, "selectObjectsBy classname does not work.")

        # This should return 2 rows
        results = odb.selectObjectsBy(comment="newComment")
        self.assertEqual(len(results), 2, "selectObjectsBy comment does not work.")

        # Loop results
        for row in results:
            print(row)

        # This should return 2 rows, but using iterate
        results = odb.selectObjectsBy(iterate=True, comment="newComment")
        self.assertEqual(len(results), 2, "selectObjectsBy comment does not work.")

        # Loop results
        for row in results:
            print(row)

        # Relations
        id = odb.insertRelation( "relation name", id, id, id, "object_parent_extended", "object_child_extended")

