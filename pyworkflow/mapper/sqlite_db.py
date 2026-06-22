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
logger = logging.getLogger(__name__)
import os
import shutil
import hashlib
import tempfile
import threading
import time
from sqlite3 import dbapi2 as sqlite
from pyworkflow.utils import STATUS, getExtraLogInfo, Config


class SqliteDb:
    """Class to handle a Sqlite database.
    It will create connection, execute queries and commands.
    """
    OPEN_CONNECTIONS = {}  # Store all connections made

    # --- Node-local SQLite (opt-in via Config.SQLITE_NODE_LOCAL, default OFF) ---
    # Maps a shared-storage DB path to its node-local working copy, plus an open
    # reference count so the local copy is published back to shared storage (and
    # cleaned up) only when the last opener closes. Targets the common case of
    # single-writer, non-reused connections (the default mode).
    NODE_LOCAL_MAP = {}
    NODE_LOCAL_REFS = {}
    # Shared-storage DB paths that have received committed writes from THIS process
    # since their last publish. Only DBs this process actually wrote are published,
    # so a GUI/viewer that merely reads a DB never clobbers the producing protocol's
    # snapshot on shared storage.
    NODE_LOCAL_DIRTY = set()
    # Re-entrant lock guarding the maps above (touched by the publisher thread too).
    NODE_LOCAL_LOCK = threading.RLock()
    # Background daemon that periodically publishes live snapshots (see
    # _startNodeLocalPublisher); started lazily on the first node-local open.
    _NODE_LOCAL_PUBLISHER = None

    def __init__(self):
        self._reuseConnections = False

    @classmethod
    def _nodeLocalPath(cls, dbName):
        localDir = Config.SQLITE_NODE_LOCAL_DIR or tempfile.gettempdir()
        localDir = os.path.join(localDir, 'scipion_sqlite_nodelocal')
        os.makedirs(localDir, exist_ok=True)
        digest = hashlib.md5(os.path.abspath(dbName).encode('utf-8')).hexdigest()
        return os.path.join(localDir, '%s.sqlite' % digest)

    @classmethod
    def _setupNodeLocal(cls, dbName):
        """Map a shared DB path to a node-local working copy and return the local
        path to actually open. On the first opener the existing shared DB (if any)
        is copied across so reads/continues see prior state."""
        with cls.NODE_LOCAL_LOCK:
            localPath = cls._nodeLocalPath(dbName)
            cls.NODE_LOCAL_MAP[dbName] = localPath
            if cls.NODE_LOCAL_REFS.get(dbName, 0) == 0:
                if os.path.exists(dbName):
                    shutil.copy2(dbName, localPath)
                elif os.path.exists(localPath):
                    os.remove(localPath)  # discard a stale leftover copy
            cls.NODE_LOCAL_REFS[dbName] = cls.NODE_LOCAL_REFS.get(dbName, 0) + 1
        # Ensure the periodic publisher is running so the GUI can live-monitor.
        cls._startNodeLocalPublisher()
        return localPath

    @classmethod
    def _markNodeLocalDirty(cls, dbName):
        """Flag that this process committed writes to a node-local DB, so the
        publisher will refresh its shared-storage snapshot on the next cycle."""
        with cls.NODE_LOCAL_LOCK:
            if dbName in cls.NODE_LOCAL_MAP:
                cls.NODE_LOCAL_DIRTY.add(dbName)

    @classmethod
    def _syncNodeLocal(cls, dbName):
        """Publish the node-local working copy back to shared storage atomically
        (temp file + os.replace) once the last opener closes, then clean up. Only
        the main DB file needs syncing: WAL is prohibited and the DELETE-mode
        rollback journal is transient (removed on commit)."""
        with cls.NODE_LOCAL_LOCK:
            localPath = cls.NODE_LOCAL_MAP.get(dbName)
            if localPath is None:
                return
            refs = cls.NODE_LOCAL_REFS.get(dbName, 1) - 1
            if refs > 0:
                cls.NODE_LOCAL_REFS[dbName] = refs
                return
            cls.NODE_LOCAL_REFS.pop(dbName, None)
            cls.NODE_LOCAL_MAP.pop(dbName, None)
            cls.NODE_LOCAL_DIRTY.discard(dbName)
        try:
            if os.path.exists(localPath):
                tmp = '%s.nodelocal.tmp' % dbName
                shutil.copy2(localPath, tmp)
                os.replace(tmp, dbName)  # atomic publish to shared storage
                os.remove(localPath)
        except OSError as e:
            logger.error("Failed to sync node-local SQLite DB %s -> %s: %s"
                         % (localPath, dbName, e))

    # ---- Periodic live-snapshot publishing (restores GUI live monitoring) ----
    @classmethod
    def _startNodeLocalPublisher(cls):
        """Start (once) a daemon thread that periodically publishes read-only
        snapshots of the dirty node-local DBs to their shared-storage paths, so
        the GUI can live-monitor status and viewers can show intermediate results
        while the protocol keeps writing node-local. Disabled if the interval is
        non-positive (only the final sync-on-close happens then)."""
        if Config.SQLITE_NODE_LOCAL_SYNC_SEC <= 0:
            return
        with cls.NODE_LOCAL_LOCK:
            if cls._NODE_LOCAL_PUBLISHER is not None:
                return
            t = threading.Thread(target=cls._nodeLocalPublishLoop,
                                 args=(Config.SQLITE_NODE_LOCAL_SYNC_SEC,),
                                 name='sqlite-nodelocal-publisher', daemon=True)
            cls._NODE_LOCAL_PUBLISHER = t
            t.start()

    @classmethod
    def _nodeLocalPublishLoop(cls, interval):
        while True:
            time.sleep(interval)
            try:
                cls._publishDirtyNodeLocal()
            except Exception as e:
                logger.error("Node-local publisher cycle failed: %s" % e)

    @classmethod
    def _publishDirtyNodeLocal(cls):
        """Publish a fresh snapshot of every DB written since the last cycle."""
        with cls.NODE_LOCAL_LOCK:
            pairs = [(d, cls.NODE_LOCAL_MAP.get(d)) for d in cls.NODE_LOCAL_DIRTY]
            cls.NODE_LOCAL_DIRTY.clear()
        for shared, local in pairs:
            if local is None:
                continue
            try:
                cls._publishSnapshot(shared, local)
            except Exception as e:
                # Re-mark dirty so we retry next cycle; never disrupt the writer.
                cls._markNodeLocalDirty(shared)
                logger.warning("Could not publish node-local snapshot %s -> %s: %s"
                               % (local, shared, e))

    @classmethod
    def _publishSnapshot(cls, shared, local):
        """Publish a consistent, read-only snapshot of a node-local DB to its
        shared path WITHOUT disturbing the live writer.

        Uses SQLite's online backup API from a separate read connection: it reads
        a transactionally-consistent copy while the protocol keeps writing (the
        two connections coordinate via locking on the *local* filesystem, where
        locking is reliable). The snapshot is built locally and then published to
        shared storage with a single-writer temp file + atomic os.replace, so a
        GUI/viewer reading the shared path only ever sees a complete DB and never
        locks the node-local writer."""
        if not os.path.exists(local):
            return
        snapLocal = '%s.snapshot' % local
        # 1) Transactionally-consistent snapshot on the reliable local filesystem.
        src = sqlite.Connection(local, 5, check_same_thread=False)
        try:
            src.execute("PRAGMA busy_timeout = %d" % Config.SQLITE_BUSY_TIMEOUT)
            dst = sqlite.Connection(snapLocal, 5, check_same_thread=False)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        # 2) Atomic publish to shared storage. The temp file lives on the shared
        #    filesystem (same dir as the target) so os.replace is atomic there.
        sharedTmp = '%s.publish.tmp' % shared
        try:
            shutil.copyfile(snapLocal, sharedTmp)
            os.replace(sharedTmp, shared)
        finally:
            if os.path.exists(snapLocal):
                os.remove(snapLocal)

    def _createConnection(self, dbName, timeout):
        """Establish db connection"""
        self._dbName = dbName
        if self._reuseConnections and dbName in self.OPEN_CONNECTIONS:
            self.connection = self.OPEN_CONNECTIONS[dbName]
        else:
            # self.closeConnection(dbName)  # Close the connect if exists for this db
            # When node-local mode is enabled, open the connection on a node-local
            # working copy; it is synced back to shared storage on close.
            connectionPath = (self._setupNodeLocal(dbName)
                              if Config.SQLITE_NODE_LOCAL else dbName)
            self.connection = sqlite.Connection(connectionPath, timeout, check_same_thread=False)
            self.connection.row_factory = sqlite.Row
            self.connection.execute("PRAGMA busy_timeout = %d" % Config.SQLITE_BUSY_TIMEOUT)
            self.OPEN_CONNECTIONS[dbName] = self.connection
            logger.debug("Connection open for %s" % dbName, extra=getExtraLogInfo(
                "CONNECTIONS",
                STATUS.START,
                dbfilename=dbName))

        self.cursor = self.connection.cursor()
        # Define some shortcuts functions
        if Config.debugSQLOn():
            self.executeCommand = self._debugExecute
        else:
            self.executeCommand = self.cursor.execute
        # In node-local mode, route commits through a wrapper that flags the DB as
        # dirty so the publisher refreshes its shared-storage snapshot. A reader
        # (GUI/viewer) never commits, so it never triggers a publish.
        if Config.SQLITE_NODE_LOCAL:
            self.commit = self._nodeLocalCommit
        else:
            self.commit = self.connection.commit

    def _nodeLocalCommit(self):
        self.connection.commit()
        SqliteDb._markNodeLocalDirty(self._dbName)

    @classmethod
    def closeConnection(cls, dbName):
        if dbName in cls.OPEN_CONNECTIONS:
            connection = cls.OPEN_CONNECTIONS[dbName]
            del cls.OPEN_CONNECTIONS[dbName]
            connection.close()
            if Config.SQLITE_NODE_LOCAL:
                cls._syncNodeLocal(dbName)
            logger.debug("Connection closed for %s" % dbName,
                         extra=getExtraLogInfo('CONNECTIONS', STATUS.STOP, dbfilename=dbName))

    def getDbName(self):
        return self._dbName
    
    def close(self):
        self.connection.close()
        if Config.SQLITE_NODE_LOCAL:
            self._syncNodeLocal(self._dbName)
        logger.debug("Connection closed for %s" % self._dbName,
                     extra=getExtraLogInfo(
                                        "CONNECTIONS",
                                        STATUS.STOP,
                                        dbfilename=self._dbName))
        if self._dbName in self.OPEN_CONNECTIONS:
            del self.OPEN_CONNECTIONS[self._dbName]
        
    def _debugExecute(self, *args):
        try:
            logger.debug("COMMAND: %s; %s" %(args[0] , self._dbName),
                extra=getExtraLogInfo("QUERY", STATUS.EVENT, dbfilename=self._dbName)
            )
            logger.debug("ARGUMENTS: " + str(args[1:]))
            return self.cursor.execute(*args)
        except Exception as ex:
            print(">>>> FAILED cursor.execute on db: '%s'" % self._dbName)
            raise ex

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
        
    def getTables(self, tablePattern=None):
        """ Return the table names existing in the Database.
        If  tablePattern is not None, only tables matching 
        the pattern will be returned.
        """
        self.executeCommand("SELECT name FROM sqlite_master "
                            "WHERE type='table' "
                            "AND name NOT LIKE 'sqlite_%';")
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

