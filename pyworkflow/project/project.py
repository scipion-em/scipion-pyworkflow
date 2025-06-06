#!/usr/bin/env python
# **************************************************************************
# *
# * Authors:     J.M. De la Rosa Trevin (delarosatrevin@scilifelab.se) [1]
# *
# * [1] SciLifeLab, Stockholm University
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
import logging

from .usage import ScipionWorkflow
from ..protocol.launch import _checkJobStatus

ROOT_NODE_NAME = "PROJECT"
logger = logging.getLogger(__name__)
from pyworkflow.utils.log import LoggingConfigurator
import datetime as dt
import json
import os
import re
import time
import traceback
from collections import OrderedDict

import pyworkflow as pw
from pyworkflow.constants import PROJECT_DBNAME, PROJECT_SETTINGS
import pyworkflow.object as pwobj
import pyworkflow.protocol as pwprot
import pyworkflow.utils as pwutils
from pyworkflow.mapper import SqliteMapper
from pyworkflow.protocol.constants import (MODE_RESTART, MODE_RESUME,
                                           STATUS_INTERACTIVE, ACTIVE_STATUS,
                                           UNKNOWN_JOBID, INITIAL_SLEEP_TIME, STATUS_FINISHED)
from pyworkflow.protocol.protocol import Protocol, LegacyProtocol

from . import config


OBJECT_PARENT_ID = pwobj.OBJECT_PARENT_ID
PROJECT_LOGS = 'Logs'
PROJECT_RUNS = 'Runs'
PROJECT_TMP = 'Tmp'
PROJECT_UPLOAD = 'Uploads'
PROJECT_CONFIG = '.config'
PROJECT_CREATION_TIME = 'CreationTime'

# Regex to get numbering suffix and automatically propose runName
REGEX_NUMBER_ENDING = re.compile(r'(?P<prefix>.+)(?P<number>\(\d*\))\s*$')
REGEX_NUMBER_ENDING_CP = re.compile(r'(?P<prefix>.+\s\(copy)(?P<number>.*)\)\s*$')


class Project(object):
    """This class will handle all information 
    related with a Project"""

    @classmethod
    def getDbName(cls):
        """ Return the name of the database file of projects. """
        return PROJECT_DBNAME

    def __init__(self, domain, path):
        """
        Create a new Project instance.
        :param domain: The application domain from where to get objects and
            protocols.
        :param path: Path where the project will be created/loaded
        """
        self._domain = domain
        self.name = path
        self.shortName = os.path.basename(path)
        self.path = os.path.abspath(path)
        self._isLink = os.path.islink(path)
        self._isInReadOnlyFolder = False
        self.pathList = []  # Store all related paths
        self.dbPath = self.__addPath(PROJECT_DBNAME)
        self.logsPath = self.__addPath(PROJECT_LOGS)
        self.runsPath = self.__addPath(PROJECT_RUNS)
        self.tmpPath = self.__addPath(PROJECT_TMP)
        self.uploadPath = self.__addPath(PROJECT_UPLOAD)
        self.settingsPath = self.__addPath(PROJECT_SETTINGS)
        self.configPath = self.__addPath(PROJECT_CONFIG)
        self.runs = None
        self._runsGraph = None
        self._transformGraph = None
        self._sourceGraph = None
        self.address = ''
        self.port = pwutils.getFreePort()
        self.mapper = None
        self.settings:config.ProjectSettings = None
        # Host configuration
        self._hosts = None

        #  Creation time should be stored in project.sqlite when the project
        # is created and then loaded with other properties from the database
        self._creationTime = None

        # Time stamp with the last run has been updated
        self._lastRunTime = None

    def getObjId(self):
        """ Return the unique id assigned to this project. """
        return os.path.basename(self.path)

    def __addPath(self, *paths):
        """Store a path needed for the project"""
        p = self.getPath(*paths)
        self.pathList.append(p)
        return p

    def getPath(self, *paths):
        """Return path from the project root"""
        if paths:
            return os.path.join(*paths) # Why this is relative!!
        else:
            return self.path

    def isLink(self):
        """Returns if the project path is a link to another folder."""
        return self._isLink

    def getDbPath(self):
        """ Return the path to the sqlite db. """
        return self.dbPath

    def getDbLastModificationDate(self):
        """ Return the last modification date of the database """
        pwutils.getFileLastModificationDate(self.getDbPath())

    def getCreationTime(self):
        """ Return the time when the project was created. """
        # In project.create method, the first object inserted
        # in the mapper should be the creation time
        return self._creationTime.datetime()


    def getComment(self):
        """ Returns the project comment. Stored as CreationTime comment."""
        return self._creationTime.getObjComment()

    def setComment(self, newComment):
        """ Sets the project comment """
        self._creationTime.setObjComment(newComment)

    def getSettingsCreationTime(self):
        return self.settings.getCreationTime()

    def getElapsedTime(self):
        """ Returns the time elapsed from the creation to the last
        execution time. """
        if self._creationTime and self._lastRunTime:
            creationTs = self.getCreationTime()
            lastRunTs = self._lastRunTime.datetime()
            return lastRunTs - creationTs
        return None

    def getLeftTime(self):
        lifeTime = self.settings.getLifeTime()
        if lifeTime:
            td = dt.timedelta(hours=lifeTime)
            return td - self.getElapsedTime()
        else:
            return None

    def setDbPath(self, dbPath):
        """ Set the project db path.
        This function is used when running a protocol where
        a project is loaded but using the protocol own sqlite file.
        """
        # First remove from pathList the old dbPath
        self.pathList.remove(self.dbPath)
        self.dbPath = os.path.abspath(dbPath)
        self.pathList.append(self.dbPath)

    def getName(self):
        return self.name

    def getDomain(self):
        return self._domain

    # TODO: maybe it has more sense to use this behaviour
    # for just getName function...
    def getShortName(self):
        return self.shortName

    def getTmpPath(self, *paths):
        return self.getPath(PROJECT_TMP, *paths)

    def getLogPath(self, *paths):
        return self.getPath(PROJECT_LOGS, *paths)

    def getProjectLog(self):
        return os.path.join(self.path,self.getLogPath("project.log")) # For some reason getLogsPath is relative!

    def getSettings(self):
        return self.settings

    def saveSettings(self):
        # Read only mode
        if not self.openedAsReadOnly():
            self.settings.write()

    def createSettings(self, runsView=1, readOnly=False):
        self.settings = config.ProjectSettings()
        self.settings.setRunsView(runsView)
        self.settings.setReadOnly(readOnly)
        self.settings.write(self.settingsPath)
        return self.settings

    def createMapper(self, sqliteFn):
        """ Create a new SqliteMapper object and pass as classes dict
        all globals and update with data and protocols from em.
        """
        classesDict = pwobj.Dict(default=pwprot.LegacyProtocol)
        classesDict.update(self._domain.getMapperDict())
        classesDict.update(config.__dict__)
        return SqliteMapper(sqliteFn, classesDict)

    def load(self, dbPath=None, hostsConf=None, protocolsConf=None, chdir=True,
             loadAllConfig=True):
        """
        Load project data, configuration and settings.

        :param dbPath: the path to the project database.
            If None, use the project.sqlite in the project folder.
        :param hostsConf: where to read the host configuration.
            If None, check if exists in .config/hosts.conf
            or read from ~/.config/scipion/hosts.conf
        :param protocolsConf: Not used
        :param chdir: If True, os.cwd will be set to project's path.
        :param loadAllConfig: If True, settings from settings.sqlite will also be loaded

        """

        if not os.path.exists(self.path):
            raise Exception("Cannot load project, path doesn't exist: %s"
                            % self.path)

        # If folder is read only, flag it and warn about it.
        if not os.access(self.path, os.W_OK):
            self._isInReadOnlyFolder = True
            logger.warning("Project \"%s\": you don't have write permissions "
                  "for project folder. Loading asd READ-ONLY." % self.shortName)

        if chdir:
            os.chdir(self.path)  # Before doing nothing go to project dir

        try:
            self._loadDb(dbPath)
            self._loadHosts(hostsConf)

            if loadAllConfig:

                # FIXME: Handle settings argument here

                # It is possible that settings does not exists if
                # we are loading a project after a Project.setDbName,
                # used when running protocols
                settingsPath = os.path.join(self.path, self.settingsPath)

                logger.debug("settingsPath: %s" % settingsPath)

                if os.path.exists(settingsPath):
                    self.settings = config.ProjectSettings.load(settingsPath)
                else:
                    logger.info("settings is None")
                    self.settings = None

            self._loadCreationTime()

        # Catch DB not found exception (when loading a project from a folder
        #  without project.sqlite
        except MissingProjectDbException as noDBe:
            # Raise it at before: This is a critical error and should be raised
            raise noDBe

        # Catch any less severe exception..to allow at least open the project.
        # except Exception as e:
        #     logger.info("ERROR: Project %s load failed.\n"
        #           "       Message: %s\n" % (self.path, e))

    def configureLogging(self):
        LoggingConfigurator.setUpGUILogging(self.getProjectLog())
    def _loadCreationTime(self):
        # Load creation time, it should be in project.sqlite or
        # in some old projects it is found in settings.sqlite

        creationTime = self.mapper.selectBy(name=PROJECT_CREATION_TIME)

        if creationTime:  # CreationTime was found in project.sqlite
            ctStr = creationTime[0] # This is our String type instance

            # We store it in mem as datetime
            self._creationTime = ctStr

        else:

            # If connected to project.sqlite and not any or the run.db
            if self.path.endswith(PROJECT_DBNAME):
                # We should read the creation time from settings.sqlite and
                # update the CreationTime in the project.sqlite
                self._creationTime = pwobj.String(self.getSettingsCreationTime())
                self._storeCreationTime()

    # ---- Helper functions to load different pieces of a project
    def _loadDb(self, dbPath):
        """ Load the mapper from the sqlite file in dbPath. """
        if dbPath is not None:
            self.setDbPath(dbPath)

        absDbPath = os.path.join(self.path, self.dbPath)
        if not os.path.exists(absDbPath):
            raise MissingProjectDbException(
                "Project database not found at '%s'" % absDbPath)
        self.mapper = self.createMapper(absDbPath)

    def closeMapper(self):
        if self.mapper is not None:
            self.mapper.close()
            self.mapper = None

    def getLocalConfigHosts(self):
        """ Return the local file where the project will try to
        read the hosts configuration. """
        return self.getPath(PROJECT_CONFIG, pw.Config.SCIPION_HOSTS)

    def _loadHosts(self, hosts):
        """ Loads hosts configuration from hosts file. """
        # If the host file is not passed as argument...
        configHosts = pw.Config.SCIPION_HOSTS
        projHosts = self.getLocalConfigHosts()

        if hosts is None:
            # Try first to read it from the project file .config./hosts.conf
            if os.path.exists(projHosts):
                hostsFile = projHosts
            else:
                localDir = os.path.dirname(pw.Config.SCIPION_LOCAL_CONFIG)
                hostsFile = os.path.join(localDir, configHosts)
        else:
            pwutils.copyFile(hosts, projHosts)
            hostsFile = hosts

        self._hosts = pwprot.HostConfig.load(hostsFile)

    def getHostNames(self):
        """ Return the list of host name in the project. """
        return list(self._hosts.keys())

    def getHostConfig(self, hostName):
        if hostName in self._hosts:
            hostKey = hostName
        else:
            hostKey = self.getHostNames()[0]
            logger.warning("Protocol host '%s' not found." % hostName)
            logger.warning("         Using '%s' instead." % hostKey)

        return self._hosts[hostKey]

    def getProtocolView(self):
        """ Returns de view selected in the tree when it was persisted"""
        return self.settings.getProtocolView()

    def create(self, runsView=1, readOnly=False, hostsConf=None,
               protocolsConf=None, comment=None):
        """Prepare all required paths and files to create a new project.

        :param runsView: default view to associate the project with
        :param readOnly: If True, project will be loaded as read only.
        :param hostsConf: Path to the host.conf to be used when executing protocols
        :param protocolsConf: Not used.
        """
        # Create project path if not exists
        pwutils.path.makePath(self.path)
        os.chdir(self.path)  # Before doing nothing go to project dir
        self._cleanData()
        logger.info("Creating project at %s" % os.path.abspath(self.dbPath))
        # Create db through the mapper
        self.mapper = self.createMapper(self.dbPath)
        # Store creation time
        self._creationTime = pwobj.String(dt.datetime.now())
        self.setComment(comment)
        self._storeCreationTime()
        # Load settings from .conf files and write .sqlite
        self.settings = self.createSettings(runsView=runsView,
                                            readOnly=readOnly)
        # Create other paths inside project
        for p in self.pathList:
            pwutils.path.makePath(p)

        self._loadHosts(hostsConf)

    def _storeCreationTime(self, new=True):
        """ Store the creation time in the project db. """
        # Store creation time
        self._creationTime.setName(PROJECT_CREATION_TIME)
        self.mapper.store(self._creationTime)
        self.mapper.commit()

    def _cleanData(self):
        """Clean all project data"""
        pwutils.path.cleanPath(*self.pathList)

    def _continueWorkflow(self, errorsList, continuedProtList=None):
        """
        This function continue a workflow from a selected protocol.
        The previous results are preserved.
        Actions done here are:
        1. if the protocol list exists (for each protocol)
            1.1  if the protocol is not an interactive protocol
            1.1.1. If the protocol is in streaming (CONTINUE ACTION):
                       - 'dataStreaming' parameter if the protocol is an import
                          protocol
                       -  check if the __stepsCheck function exist and it's not
                          the same implementation of the base class
                          (worksInStreaming function)
                        1.1.1.1 Open the protocol sets, store and save them in
                                the  database
                       1.1.1.2 Change the protocol status (SAVED)
                       1.1.1.3 Schedule the protocol
                   Else Restart the workflow from that point (RESTART ACTION) if
                   at least one protocol in streaming has been launched
        """
        if continuedProtList is not None:
            for protocol, level in continuedProtList.values():
                if not protocol.isInteractive():
                    if protocol.isScheduled():
                        continue

                    # streaming ...
                    if protocol.worksInStreaming() and not protocol.isSaved():
                        attrSet = [attr for name, attr in
                                   protocol.iterOutputAttributes(pwprot.Set)]
                        try:
                            if attrSet:
                                # Open output sets..
                                for attr in attrSet:
                                    attr.setStreamState(attr.STREAM_OPEN)
                                    attr.write()
                                    attr.close()
                            protocol.setStatus(pwprot.STATUS_SAVED)
                            protocol._updateSteps(lambda step: step.setStatus(pwprot.STATUS_SAVED))
                            protocol.setMapper(self.createMapper(protocol.getDbPath()))
                            protocol._store()
                            self._storeProtocol(protocol)
                            self.scheduleProtocol(protocol,
                                                  initialSleepTime=level*INITIAL_SLEEP_TIME)
                        except Exception as ex:
                            errorsList.append("Error trying to launch the "
                                              "protocol: %s\nERROR: %s\n" %
                                              (protocol.getObjLabel(), ex))
                            break
                    else:
                        if level != 0:
                            # Not in streaming and not the first protocol.
                            if protocol.isActive():
                                self.stopProtocol(protocol)
                            self._restartWorkflow(errorsList,{protocol.getObjId(): (protocol, level)})

                        else: # First protocol not in streaming
                            if not protocol.isActive():
                               self.scheduleProtocol(protocol)



    def _restartWorkflow(self, errorsList, restartedProtList=None):
        """
        This function restart a workflow from a selected protocol.
        All previous results will be deleted
        Actions done here are:
        1. Set the protocol run mode (RESTART). All previous results will be
           deleted
        2. Schedule the protocol if not is an interactive protocol
        3. For each of the dependents protocols, repeat from step 1
        """
        if restartedProtList is not None:
            for protocol, level in restartedProtList.values():
                if not protocol.isInteractive():
                    try:
                        if protocol.isScheduled():
                            continue
                        elif protocol.isActive():
                            self.stopProtocol(protocol)
                        protocol.runMode.set(MODE_RESTART)
                        self.scheduleProtocol(protocol,
                                              initialSleepTime=level*INITIAL_SLEEP_TIME)
                    except Exception as ex:
                        errorsList.append("Error trying to restart a protocol: %s"
                                          "\nERROR: %s\n" % (protocol.getObjLabel(),
                                                             ex))
                        break
                else:
                    protocol.setStatus(pwprot.STATUS_SAVED)
                    self._storeProtocol(protocol)
                    protocol.runMode.set(MODE_RESTART)
                    self._setupProtocol(protocol)
                    protocol.makePathsAndClean()  # Create working dir if necessary
                    # Delete the relations created by this protocol
                    self.mapper.deleteRelations(self)
                    self.mapper.commit()
                    self.mapper.store(protocol)
                    self.mapper.commit()

    def _fixProtParamsConfiguration(self, protocol=None):
        """
        This function fix:
        1. The old parameters configuration in the protocols.
           Now, dependent protocols have a pointer to the parent protocol, and
           the extended parameter has a parent output value
        """
        # Take the old configuration attributes and fix the pointer
        oldStylePointerList = [item for key, item in
                               protocol.iterInputAttributes()
                               if not isinstance(item.getObjValue(),
                                                 pwprot.Protocol)]
        if oldStylePointerList:
            # Fix the protocol parameters
            for pointer in oldStylePointerList:
                auxPointer = pointer.getObjValue()
                pointer.set(self.getRunsGraph().getNode(str(pointer.get().getObjParentId())).run)
                pointer.setExtended(auxPointer.getLastName())
                protocol._store()
                self._storeProtocol(protocol)
                self._updateProtocol(protocol)
                self.mapper.commit()

    def stopWorkFlow(self, activeProtList):
        """
        This function can stop a workflow from a selected protocol
        :param initialProtocol: selected protocol
        """
        errorProtList = []
        for protocol in activeProtList.values():
            try:
                self.stopProtocol(protocol)
            except Exception:
                errorProtList.append(protocol)
        return errorProtList

    def resetWorkFlow(self, workflowProtocolList):
        """
        This function can reset a workflow from a selected protocol
        :param initialProtocol: selected protocol
        """
        errorProtList = []
        if workflowProtocolList:
            for protocol, level in workflowProtocolList.values():
                if protocol.getStatus() != pwprot.STATUS_SAVED:
                    try:
                        self.resetProtocol(protocol)
                    except Exception:
                        errorProtList.append(protocol)
        return errorProtList

    def launchWorkflow(self, workflowProtocolList, mode=MODE_RESUME):
        """
        This function can launch a workflow from a selected protocol in two
        modes depending on the 'mode' value (RESTART, CONTINUE)
        Actions done here are:

        1. Check if the workflow has active protocols.
        2. Fix the workflow if is not properly configured
        3. Restart or Continue a workflow starting from the protocol depending
            on the 'mode' value

        """
        errorsList = []
        if mode == MODE_RESTART:
            self._restartWorkflow(errorsList, workflowProtocolList)
        else:
            self._continueWorkflow(errorsList,workflowProtocolList)
        return errorsList

    def launchProtocol(self, protocol:Protocol, wait=False, scheduled=False,
                       force=False):
        """ In this function the action of launching a protocol
        will be initiated. Actions done here are:

        1. Store the protocol and assign name and working dir
        2. Create the working dir and also the protocol independent db
        3. Call the launch method in protocol.job to handle submission:
            mpi, thread, queue.

        If the protocol has some prerequisites (other protocols that
        needs to be finished first), it will be scheduled.

        :param protocol: Protocol instance to launch
        :param wait: Optional. If true, this method
            will wait until execution is finished. Used in tests.
        :param scheduled: Optional. If true, run.db and paths
            already exist and are preserved.
        :param force: Optional. If true, launch is forced, regardless
            latter dependent executions. Used when restarting many protocols a once.

        """
        if protocol.getPrerequisites() and not scheduled:
            return self.scheduleProtocol(protocol)

        isRestart = protocol.getRunMode() == MODE_RESTART

        if not force:
            if (not protocol.isInteractive() and not protocol.isInStreaming()) or isRestart:
                self._checkModificationAllowed([protocol],
                                               'Cannot RE-LAUNCH protocol')

        protocol.setStatus(pwprot.STATUS_LAUNCHED)
        self._setupProtocol(protocol)

        # Prepare a separate db for this run if not from schedule jobs
        # Scheduled protocols will load the project db from the run.db file,
        # so there is no need to copy the database

        if not scheduled:
            protocol.makePathsAndClean()  # Create working dir if necessary
            # Delete the relations created by this protocol
            if isRestart:
                self.mapper.deleteRelations(self)
                # Clean and persist execution attributes; otherwise, this would retain old job IDs and PIDs.
                protocol.cleanExecutionAttributes()
                protocol._store(protocol._jobId, protocol._pid)

            self.mapper.commit()

            # NOTE: now we are simply copying the entire project db, this can be
            # changed later to only create a subset of the db need for the run
            pwutils.path.copyFile(self.dbPath, protocol.getDbPath())
            # Update the lastUpdateTimeStamp so later PID obtained in launch is not "remove" with run.db data.
            protocol.lastUpdateTimeStamp.set(pwutils.getFileLastModificationDate(protocol.getDbPath()))

        # Launch the protocol; depending on the case, either the pId or the jobId will be set in this call
        pwprot.launch(protocol, wait)

        # Commit changes
        if wait:  # This is only useful for launching tests...
            self._updateProtocol(protocol)
        else:
            self.mapper.store(protocol)
        self.mapper.commit()

    def scheduleProtocol(self, protocol, prerequisites=[], initialSleepTime=0):
        """ Schedule a new protocol that will run when the input data
        is available and the prerequisites are finished.

        :param protocol: the protocol that will be scheduled.
        :param prerequisites: a list with protocols ids that the scheduled
            protocol will wait for.
        :param initialSleepTime: number of seconds to wait before
            checking input's availability

        """
        isRestart = protocol.getRunMode() == MODE_RESTART

        protocol.setStatus(pwprot.STATUS_SCHEDULED)
        protocol.addPrerequisites(*prerequisites)

        self._setupProtocol(protocol)
        protocol.makePathsAndClean()  # Create working dir if necessary
        # Delete the relations created by this protocol if any
        if isRestart:
            self.mapper.deleteRelations(self)
        self.mapper.commit()

        # Prepare a separate db for this run
        # NOTE: now we are simply copying the entire project db, this can be
        # changed later to only create a subset of the db need for the run
        pwutils.path.copyFile(self.dbPath, protocol.getDbPath())
        # Launch the protocol, the jobId should be set after this call
        pwprot.schedule(protocol, initialSleepTime=initialSleepTime)
        self.mapper.store(protocol)
        self.mapper.commit()

    def _updateProtocol(self, protocol: Protocol, tries=0, checkPid=False):
        """ Update the protocol passed taking the data from its run.db.
        It also checks if the protocol is alive base on its PID of JOBIDS """
        # NOTE: when this method fails recurrently....we are setting the protocol to failed and
        # therefore closing its outputs. This, in streaming scenarios triggers a false closing to protocols
        # while actual protocol is still alive but

        updated = pw.NOT_UPDATED_UNNECESSARY

        # If this is read only exit
        if self.openedAsReadOnly():
            return pw.NOT_UPDATED_READ_ONLY

        try:

            # IMPORTANT: the protocol after some iterations of this ends up without the project!
            # This is a problem if we want tu use protocol.useQueueForJobs that uses project info!
            # print("PROJECT: %s" % protocol.getProject())

            # If the protocol database has changes ....
            if not pwprot.isProtocolUpToDate(protocol):

                logger.debug("Protocol %s outdated. Updating it now." % protocol.getRunName())

                updated = pw.PROTOCOL_UPDATED

                # Backup the values of 'jobId', 'label' and 'comment'
                # to be restored after the .copy
                jobId = protocol.getJobIds().clone()  # Use clone to prevent this variable from being overwritten or cleared in the latter .copy() call
                label = protocol.getObjLabel()
                comment = protocol.getObjComment()
                project = protocol.getProject() # The later protocol.copy(prot2, copyId=False, excludeInputs=True) cleans the project!!

                if project is None:
                    logger.warning("Protocol %s hasn't the project associated when updating it." % label)

                #  Comparing date will not work unless we have a reliable
                # lastModificationDate of a protocol in the project.sqlite
                prot2 = pwprot.getProtocolFromDb(self.path,
                                                 protocol.getDbPath(),
                                                 protocol.getObjId())

                # Capture the db timestamp before loading.
                lastUpdateTime = pwutils.getFileLastModificationDate(protocol.getDbPath())

                # Copy is only working for db restored objects
                protocol.setMapper(self.mapper)

                localOutputs = list(protocol._outputs)
                protocol.copy(prot2, copyId=False, excludeInputs=True) # This cleans protocol._project cause getProtocolFromDb does not bring the project
                protocol.setProject(project)

                # merge outputs: This is necessary when outputs are added from the GUI
                # e.g.: adding coordinates from analyze result and protocol is active (interactive).
                for attr in localOutputs:
                    if attr not in protocol._outputs:
                        protocol._outputs.append(attr)

                # Restore backup values
                if protocol.useQueueForProtocol() and jobId:  # If jobId not empty then restore value as the db is empty
                    # Case for direct protocol launch from the GUI. Without passing through a scheduling process.
                    # In this case the jobid is obtained by the GUI and the job id should be preserved.
                    protocol.setJobIds(jobId)

                # In case of scheduling a protocol, the jobid is obtained during the "scheduling job"
                # and it is written in the rub.db. Therefore, it should be taken from there.

                # Restore values edited in the GUI
                protocol.setObjLabel(label)
                protocol.setObjComment(comment)
                # Use the run.db timestamp instead of the system TS to prevent
                # possible inconsistencies.
                protocol.lastUpdateTimeStamp.set(lastUpdateTime)

                # # Check pid at the end, once updated. It may have brought new pids? Job ids? or process died and pid
                # # pid and job ids were reset and status set to failed, so it does not make sense to check pids
                # if checkPid and protocol.isActive():
                #     self.checkIsAlive(protocol)

                # Close DB connections to rundb
                prot2.getProject().closeMapper()
                prot2.closeMappers()


            # If protocol is still active
            if protocol.isActive():
                # If it is still alive, and hasn't been updated from run db
                # NOTE: checkIsAlive may have changed the protocol status,in case the process ware killed
                # So we need to persist those changes.
                if not self.checkIsAlive(protocol):

                     updated = pw.PROTOCOL_UPDATED


            if updated == pw.PROTOCOL_UPDATED:
                # We store changes, either after updating the protocol with data from run-db or because it died
                self.mapper.store(protocol)

        except Exception as ex:
            if tries == 3:  # 3 tries have been failed
                traceback.print_exc()
                # If any problem happens, the protocol will be marked
                # with a FAILED status
                try:
                    protocol.setFailed(str(ex))
                    self.mapper.store(protocol)
                except Exception:
                    pass
                return pw.NOT_UPDATED_ERROR
            else:
                logger.warning("Couldn't update protocol %s from it's own database. ERROR: %s, attempt=%d"
                             % (protocol.getRunName(), ex, tries))
                time.sleep(0.5)
                return self._updateProtocol(protocol, tries + 1)

        return updated

    def checkIsAlive(self, protocol):
        """ Check if a protocol is alive based on its jobid (queue engines) or pid
        :param protocol: protocol to check its status
        :returns True if it is alive
        """
        # For some reason pid ends up with a None...
        pid = protocol.getPid()

        if pid is None:
            logger.info("Protocol's %s pid is None and is active... this should not happen. Checking its job id: %s" % (protocol.getRunName(), protocol.getJobIds()))
            pid = 0

        alive = False
        if pid == 0:
            alive = self.checkJobId(protocol)
        else:
            alive = self.checkPid(protocol)

        if alive:
            logger.debug("Protocol %s is alive." % protocol.getRunName())
        return alive

    def stopProtocol(self, protocol):
        """ Stop a running protocol """
        try:
            if protocol.getStatus() in ACTIVE_STATUS:
                self._updateProtocol(protocol) # update protocol to have the latest rub.db values
                pwprot.stop(protocol)
        except Exception as e:
            logger.error("Couldn't stop the protocol: %s" % e)
            raise
        finally:
            protocol.setAborted()
            protocol.setMapper(self.createMapper(protocol.getDbPath()))
            protocol._store()
            self._storeProtocol(protocol)
            protocol.getMapper().close()

    def resetProtocol(self, protocol):
        """ Stop a running protocol """
        try:
            if protocol.getStatus() in ACTIVE_STATUS:
                pwprot.stop(protocol)
        except Exception:
            raise
        finally:
            protocol.setSaved()
            protocol.runMode.set(MODE_RESTART)
            protocol.makePathsAndClean()  # Create working dir if necessary
            # Clean jobIds, Pid and StepsDone;
            protocol.cleanExecutionAttributes()  # otherwise, this would retain old executions info
            protocol._store()

    def continueProtocol(self, protocol):
        """ This function should be called 
        to mark a protocol that have an interactive step
        waiting for approval that can continue
        """
        protocol.continueFromInteractive()
        self.launchProtocol(protocol)

    def __protocolInList(self, prot, protocols):
        """ Check if a protocol is in a list comparing the ids. """
        for p in protocols:
            if p.getObjId() == prot.getObjId():
                return True
        return False

    def __validDependency(self, prot, child, protocols):
        """ Check if the given child is a true dependency of the protocol
        in order to avoid any modification.
        """
        return (not self.__protocolInList(child, protocols) and
                not child.isSaved() and not child.isScheduled())

    def _getProtocolsDependencies(self, protocols):
        error = ''
        runsGraph = self.getRunsGraph()
        for prot in protocols:
            node = runsGraph.getNode(prot.strId())
            if node:
                childs = [node.run for node in node.getChildren() if
                          self.__validDependency(prot, node.run, protocols)]
                if childs:
                    deps = [' ' + c.getRunName() for c in childs]
                    error += '\n *%s* is referenced from:\n   - ' % prot.getRunName()
                    error += '\n   - '.join(deps)
        return error

    def _getProtocolDescendents(self, protocol):
        """Getting the descendents protocols from a given one"""
        runsGraph = self.getRunsGraph()
        visitedNodes = dict()
        node = runsGraph.getNode(protocol.strId())
        if node is None:
            return visitedNodes

        visitedNodes[int(node.getName())] = node

        def getDescendents(rootNode):
            for child in rootNode.getChildren():
                if int(child.getName()) not in visitedNodes:
                    visitedNodes[int(child.getName())] = child
                    getDescendents(child)

        getDescendents(node)
        return visitedNodes

    def getProtocolCompatibleOutputs(self, protocol, classes, condition):
        """Getting the outputs compatible with an object type. The outputs of the child protocols are excluded. """
        objects = []
        maxNum = 200
        protocolDescendents = self._getProtocolDescendents(protocol)
        runs = self.getRuns(refresh=False)

        for prot in runs:
            # Make sure we don't include previous output of the same
            # and other descendent protocols
            if prot.getObjId() not in protocolDescendents:
                # Check if the protocol itself is one of the desired classes
                if any(issubclass(prot.getClass(), c) for c in classes):
                    p = pwobj.Pointer(prot)
                    objects.append(p)

                try:
                    # paramName and attr must be set to None
                    # Otherwise, if a protocol has failed and the corresponding output object of type XX does not exist
                    # any other protocol that uses objects of type XX as input will not be able to choose then using
                    # the magnifier glass (object selector of type XX)
                    paramName = None
                    attr = None
                    for paramName, attr in prot.iterOutputAttributes(includePossible=True):
                        def _checkParam(paramName, attr):
                            # If attr is a subclasses of any desired one, add it to the list
                            # we should also check if there is a condition, the object
                            # must comply with the condition
                            p = None

                            match = False
                            cancelConditionEval = False
                            possibleOutput = isinstance(attr, type)

                            # Go through all compatible Classes coming from in pointerClass string
                            for c in classes:
                                # If attr is an instance
                                if isinstance(attr, c):
                                    match = True
                                    break
                                # If it is a class already: "possibleOutput" case. In this case attr is the class and not
                                # an instance of c. In this special case
                                elif possibleOutput and issubclass(attr, c):
                                    match = True
                                    cancelConditionEval = True

                            # If attr matches the class
                            if match:
                                if cancelConditionEval or not condition or attr.evalCondition(condition):
                                    p = pwobj.Pointer(prot, extended=paramName)
                                    p._allowsSelection = True
                                    objects.append(p)
                                    return

                            # JMRT: For all sets, we don't want to include the
                            # subitems here for performance reasons (e.g. SetOfParticles)
                            # Thus, a Set class can define EXPOSE_ITEMS = True
                            # to enable the inclusion of its items here
                            if getattr(attr, 'EXPOSE_ITEMS', False) and not possibleOutput:
                                # If the ITEM type match any of the desired classes
                                # we will add some elements from the set
                                if (attr.ITEM_TYPE is not None and
                                        any(issubclass(attr.ITEM_TYPE, c) for c in classes)):
                                    if p is None:  # This means the set have not be added
                                        p = pwobj.Pointer(prot, extended=paramName)
                                        p._allowsSelection = False
                                        objects.append(p)
                                    # Add each item on the set to the list of objects
                                    try:
                                        for i, item in enumerate(attr):
                                            if i == maxNum:  # Only load up to NUM particles
                                                break
                                            pi = pwobj.Pointer(prot, extended=paramName)
                                            pi.addExtended(item.getObjId())
                                            pi._parentObject = p
                                            objects.append(pi)
                                    except Exception as ex:
                                        print("Error loading items from:")
                                        print("  protocol: %s, attribute: %s" % (prot.getRunName(), paramName))
                                        print("  dbfile: ", os.path.join(self.getPath(), attr.getFileName()))
                                        print(ex)

                        _checkParam(paramName, attr)
                        # The following is a dirty fix for the RCT case where there
                        # are inner output, maybe we should consider extend this for
                        # in a more general manner
                        for subParam in ['_untilted', '_tilted']:
                            if hasattr(attr, subParam):
                                _checkParam('%s.%s' % (paramName, subParam),
                                            getattr(attr, subParam))
                except Exception as e:
                    print("Cannot read attributes for %s (%s)" % (prot.getClass(), e))

        return objects

    def _checkProtocolsDependencies(self, protocols, msg):
        """ Check if the protocols have dependencies.
        This method is used before delete or save protocols to be sure
        it is not referenced from other runs. (an Exception is raised)
        Params:
             protocols: protocol list to be analyzed.
             msg: String message to be prefixed to Exception error.
        """
        # Check if the protocol have any dependencies
        error = self._getProtocolsDependencies(protocols)
        if error:
            raise ModificationNotAllowedException(msg + error)

    def _checkModificationAllowed(self, protocols, msg):
        """ Check if any modification operation is allowed for
        this group of protocols. 
        """
        if self.openedAsReadOnly():
            raise Exception(msg + " Running in READ-ONLY mode.")

        self._checkProtocolsDependencies(protocols, msg)

    def _getSubworkflow(self, protocol, fixProtParam=True, getStopped=True):
        """
        This function get the workflow from "protocol" and determine the
        protocol level into the graph. Also, checks if there are active
        protocols excluding interactive protocols.
        :param protocol from where to start the subworkflow (included)
        :param fixProtParam fix the old parameters configuration in the protocols
        :param getStopped takes into account protocols that aren't stopped
        """
        affectedProtocols = {}
        affectedProtocolsActive = {}
        auxProtList = []
        # store the protocol and your level into the workflow
        affectedProtocols[protocol.getObjId()] = [protocol, 0]
        auxProtList.append([protocol.getObjId(), 0])
        runGraph = self.getRunsGraph()

        while auxProtList:
            protId, level = auxProtList.pop(0)
            protocol = runGraph.getNode(str(protId)).run

            # Increase the level for the children
            level = level + 1

            if fixProtParam:
                self._fixProtParamsConfiguration(protocol)

            if not getStopped and protocol.isActive():
                affectedProtocolsActive[protocol.getObjId()] = protocol
            elif not protocol.getObjId() in affectedProtocolsActive.keys() and getStopped and \
                    not protocol.isSaved() and protocol.getStatus() != STATUS_INTERACTIVE:
                affectedProtocolsActive[protocol.getObjId()] = protocol

            node = runGraph.getNode(protocol.strId())
            dependencies = [node.run for node in node.getChildren()]
            for dep in dependencies:
                if not dep.getObjId() in auxProtList:
                    auxProtList.append([dep.getObjId(), level])

                if not dep.getObjId() in affectedProtocols.keys():
                    affectedProtocols[dep.getObjId()] = [dep, level]
                elif level > affectedProtocols[dep.getObjId()][1]:
                    affectedProtocols[dep.getObjId()][1] = level

        return affectedProtocols, affectedProtocolsActive

    def deleteProtocol(self, *protocols):
        self._checkModificationAllowed(protocols, 'Cannot DELETE protocols')

        for prot in protocols:
            # Delete the relations created by this protocol
            self.mapper.deleteRelations(prot)
            # Delete from protocol from database
            self.mapper.delete(prot)
            wd = prot.workingDir.get()

            if wd.startswith(PROJECT_RUNS):
                prot.cleanWorkingDir()
            else:
                logger.info("Can't delete protocol %s. Its workingDir %s does not starts with %s " % (prot, wd, PROJECT_RUNS))

        self.mapper.commit()

    def deleteProtocolOutput(self, protocol, output):
        """ Delete a given object from the project.
        Usually to clean up some outputs.
        """
        node = self.getRunsGraph().getNode(protocol.strId())
        deps = []

        for node in node.getChildren():
            for _, inputObj in node.run.iterInputAttributes():
                value = inputObj.get()
                if (value is not None and
                        value.getObjId() == output.getObjId() and
                        not node.run.isSaved()):
                    deps.append(node.run)

        if deps:
            error = 'Cannot DELETE Object, it is referenced from:'
            for d in deps:
                error += '\n - %s' % d.getRunName()
            raise Exception(error)
        else:
            protocol.deleteOutput(output)
            pwutils.path.copyFile(self.dbPath, protocol.getDbPath())

    def __setProtocolLabel(self, newProt):
        """ Set a readable label to a newly created protocol.
        We will try to find another existing protocol with the default label
        and then use an incremental labeling in parenthesis (<number>++)
        """
        defaultLabel = newProt.getClassLabel()
        maxSuffix = 0

        for prot in self.getRuns(iterate=True, refresh=False):
            otherProtLabel = prot.getObjLabel()
            m = REGEX_NUMBER_ENDING.match(otherProtLabel)
            if m and m.groupdict()['prefix'].strip() == defaultLabel:
                stringSuffix = m.groupdict()['number'].strip('(').strip(')')
                try:
                    maxSuffix = max(int(stringSuffix), maxSuffix)
                except:
                    logger.error("Couldn't set protocol's label. %s" % stringSuffix)
            elif otherProtLabel == defaultLabel:  # When only we have the prefix,
                maxSuffix = max(1, maxSuffix)     # this REGEX don't match.

        if maxSuffix:
            protLabel = '%s (%d)' % (defaultLabel, maxSuffix+1)
        else:
            protLabel = defaultLabel

        newProt.setObjLabel(protLabel)

    def newProtocol(self, protocolClass, **kwargs):
        """ Create a new protocol from a given class. """
        newProt = protocolClass(project=self, **kwargs)
        # Only set a default label to the protocol if is was not
        # set through the kwargs
        if not newProt.getObjLabel():
            self.__setProtocolLabel(newProt)

        newProt.setMapper(self.mapper)
        newProt.setProject(self)

        return newProt

    def __getIOMatches(self, node, childNode):
        """ Check if some output of node is used as input in childNode.
        Return the list of attribute names that matches.
        Used from self.copyProtocol
        """
        matches = []
        for iKey, iAttr in childNode.run.iterInputAttributes():
            # As this point iAttr should be always a Pointer that 
            # points to the output of other protocol
            if iAttr.getObjValue() is node.run:
                oKey = iAttr.getExtended()
                matches.append((oKey, iKey))
            else:
                for oKey, oAttr in node.run.iterOutputAttributes():
                    # If node output is "real" and iAttr is still just a pointer
                    # the iAttr.get() will return None
                    pointed = iAttr.get()
                    if pointed is not None and oAttr.getObjId() == pointed.getObjId():
                        matches.append((oKey, iKey))

        return matches

    def __cloneProtocol(self, protocol):
        """ Make a copy of the protocol parameters, not outputs. 
            We will label the new protocol with the same name adding the 
            parenthesis as follow -> (copy) -> (copy 2) -> (copy 3)
        """
        newProt = self.newProtocol(protocol.getClass())
        oldProtName = protocol.getRunName()
        maxSuffix = 0

        # if '(copy...' suffix is not in the old name, we add it in the new name
        # and setting the newnumber
        mOld = REGEX_NUMBER_ENDING_CP.match(oldProtName)
        if mOld:
            newProtPrefix = mOld.groupdict()['prefix']
            if mOld.groupdict()['number'] == '':
                oldNumber = 1
            else:
                oldNumber = int(mOld.groupdict()['number'])
        else:
            newProtPrefix = oldProtName + ' (copy'
            oldNumber = 0
        newNumber = oldNumber + 1

        # looking for "<old name> (copy" prefixes in the project and
        # setting the newNumber as the maximum+1
        for prot in self.getRuns(iterate=True, refresh=False):
            otherProtLabel = prot.getObjLabel()
            mOther = REGEX_NUMBER_ENDING_CP.match(otherProtLabel)
            if mOther and mOther.groupdict()['prefix'] == newProtPrefix:
                stringSuffix = mOther.groupdict()['number']
                if stringSuffix == '':
                    stringSuffix = 1
                maxSuffix = max(maxSuffix, int(stringSuffix))
                if newNumber <= maxSuffix:
                    newNumber = maxSuffix + 1

        # building the new name
        if newNumber == 1:
            newProtLabel = newProtPrefix + ')'
        else:
            newProtLabel = '%s %d)' % (newProtPrefix, newNumber)

        newProt.setObjLabel(newProtLabel)
        newProt.copyDefinitionAttributes(protocol)
        newProt.copyAttributes(protocol, 'hostName', '_useQueue', '_queueParams')
        newProt.runMode.set(MODE_RESTART)
        newProt.cleanExecutionAttributes() # Clean jobIds and Pid; otherwise, this would retain old job IDs and PIDs.

        return newProt

    def copyProtocol(self, protocol):
        """ Make a copy of the protocol,
        Return a new instance with copied values. """
        result = None

        if isinstance(protocol, pwprot.Protocol):
            result = self.__cloneProtocol(protocol)

        elif isinstance(protocol, list):
            # Handle the copy of a list of protocols
            # for this case we need to update the references of input/outputs
            newDict = {}

            for prot in protocol:
                newProt = self.__cloneProtocol(prot)
                newDict[prot.getObjId()] = newProt
                self.saveProtocol(newProt)

            g = self.getRunsGraph()

            for prot in protocol:
                node = g.getNode(prot.strId())
                newProt = newDict[prot.getObjId()]

                for childNode in node.getChildren():
                    newChildProt = newDict.get(childNode.run.getObjId(), None)

                    if newChildProt:
                        # Get the matches between outputs/inputs of
                        # node and childNode
                        matches = self.__getIOMatches(node, childNode)
                        # For each match, set the pointer and the extend
                        # attribute to reproduce the dependencies in the
                        # new workflow
                        for oKey, iKey in matches:
                            childPointer = getattr(newChildProt, iKey)

                            # Scalar with pointer case: If is a scalar with a pointer
                            if isinstance(childPointer, pwobj.Scalar) and childPointer.hasPointer():
                              # In this case childPointer becomes the contained Pointer
                              childPointer = childPointer.getPointer()

                            elif isinstance(childPointer, pwobj.PointerList):
                                for p in childPointer:
                                    if p.getObjValue().getObjId() == prot.getObjId():
                                        childPointer = p
                            childPointer.set(newProt)
                            childPointer.setExtended(oKey)
                        self.mapper.store(newChildProt)

            self.mapper.commit()
        else:
            raise Exception("Project.copyProtocol: invalid input protocol ' "
                            "'type '%s'." % type(protocol))

        return result

    def getProjectUsage(self) -> ScipionWorkflow:
        """ returns usage class ScipionWorkflow populated with project data
        """
        protocols = self.getRuns()

        # Handle the copy of a list of protocols
        # for this case we need to update the references of input/outputs
        sw = ScipionWorkflow()
        g = self.getRunsGraph()

        for prot in protocols:

            if not isinstance(prot, LegacyProtocol):
                # Add a count for the protocol
                protName = prot.getClassName()
                sw.addCount(protName)

                # Add next protocols count
                node = g.getNode(prot.strId())

                for childNode in node.getChildren():
                    prot = childNode.run
                    if not isinstance(prot, LegacyProtocol):
                        nextProtName = prot.getClassName()
                        sw.addCountToNextProtocol(protName, nextProtName)

                # Special case: First protocols, those without parent. Import protocols mainly.
                # All protocols, even the firs ones have a parent. For the fisrt ones the parent is "PROJECT" node that is the only root one.
                if node.getParent().isRoot():
                    sw.addCountToNextProtocol(str(None), protName)

        return sw

    def getProtocolsDict(self, protocols=None, namesOnly=False):
        """ Creates a dict with the information of the given protocols.

        :param protocols: list of protocols or None to include all.
        :param namesOnly: the output list will contain only the protocol names.

        """
        protocols = protocols or self.getRuns()

        # If the nameOnly, we will simply return a json list with their names
        if namesOnly:
            return {i: prot.getClassName() for i, prot in enumerate(protocols)}

        # Handle the copy of a list of protocols
        # for this case we need to update the references of input/outputs
        newDict = OrderedDict()

        for prot in protocols:
            newDict[prot.getObjId()] = prot.getDefinitionDict()

        g = self.getRunsGraph()

        for prot in protocols:
            protId = prot.getObjId()
            node = g.getNode(prot.strId())

            for childNode in node.getChildren():
                childId = childNode.run.getObjId()
                childProt = childNode.run
                if childId in newDict:
                    childDict = newDict[childId]
                    # Get the matches between outputs/inputs of
                    # node and childNode
                    matches = self.__getIOMatches(node, childNode)
                    for oKey, iKey in matches:
                        inputAttr = getattr(childProt, iKey)
                        if isinstance(inputAttr, pwobj.PointerList):
                            childDict[iKey] = [p.getUniqueId() for p in
                                               inputAttr]
                        else:
                            childDict[iKey] = '%s.%s' % (
                                protId, oKey)  # equivalent to pointer.getUniqueId

        return newDict

    def getProtocolsJson(self, protocols=None, namesOnly=False):
        """
        Wraps getProtocolsDict to get a json string

        :param protocols: list of protocols or None to include all.
        :param namesOnly: the output list will contain only the protocol names.

        """
        newDict = self.getProtocolsDict(protocols=protocols, namesOnly=namesOnly)
        return json.dumps(list(newDict.values()),
                          indent=4, separators=(',', ': '))

    def exportProtocols(self, protocols, filename):
        """ Create a text json file with the info
        to import the workflow into another project.
        This method is very similar to copyProtocol

        :param protocols: a list of protocols to export.
        :param filename: the filename where to write the workflow.

        """
        jsonStr = self.getProtocolsJson(protocols)
        f = open(filename, 'w')
        f.write(jsonStr)
        f.close()

    def loadProtocols(self, filename=None, jsonStr=None):
        """ Load protocols generated in the same format as self.exportProtocols.

        :param filename: the path of the file where to read the workflow.
        :param jsonStr:

        Note: either filename or jsonStr should be not None.

        """
        importDir = None
        if filename:
            with open(filename) as f:
                importDir = os.path.dirname(filename)
                protocolsList = json.load(f)

        elif jsonStr:
            protocolsList = json.loads(jsonStr)
        else:
            logger.error("Invalid call to loadProtocols. Either filename or jsonStr has to be passed.")
            return

        emProtocols = self._domain.getProtocols()
        newDict = OrderedDict()

        # First iteration: create all protocols and setup parameters
        for i, protDict in enumerate(protocolsList):
            protClassName = protDict['object.className']
            protId = protDict['object.id']
            protClass = emProtocols.get(protClassName, None)

            if protClass is None:
                logger.error("Protocol with class name '%s' not found. Are you missing its plugin?." % protClassName)
            else:
                protLabel = protDict.get('object.label', None)
                prot = self.newProtocol(protClass,
                                        objLabel=protLabel,
                                        objComment=protDict.get('object.comment', None))
                protocolsList[i] = prot.processImportDict(protDict, importDir) if importDir else protDict

                prot._useQueue.set(protDict.get('_useQueue', pw.Config.SCIPION_USE_QUEUE))
                prot._queueParams.set(protDict.get('_queueParams', None))
                prot._prerequisites.set(protDict.get('_prerequisites', None))
                prot.forceSchedule.set(protDict.get('forceSchedule', False))
                newDict[protId] = prot
                # This saves the protocol JUST with the common attributes. Is it necessary?
                # Actually, if after this the is an error, the protocol appears.
                self.saveProtocol(prot)

        # Second iteration: update pointers values
        def _setPointer(pointer, value):
            # Properly setup the pointer value checking if the 
            # id is already present in the dictionary
            # Value to pointers could be None: Partial workflows
            if value:
                parts = value.split('.')

                protId = parts[0]
                # Try to get the protocol holding the input form the dictionary
                target = newDict.get(protId, None)

                if target is None:
                    # Try to use existing protocol in the project
                    logger.info("Protocol identifier (%s) not self contained. Looking for it in the project." % protId)

                    try:
                        target = self.getProtocol(int(protId), fromRuns=True)
                    except:
                        # Not a protocol..
                        logger.info("%s is not a protocol identifier. Probably a direct pointer created by tests. This case is not considered." % protId)

                    if target:
                        logger.info("Linking %s to existing protocol in the project: %s" % (prot, target))

                pointer.set(target)
                if not pointer.pointsNone():
                    pointer.setExtendedParts(parts[1:])

        def _setPrerequisites(prot):
            prerequisites = prot.getPrerequisites()
            if prerequisites:
                newPrerequisites = []
                for prerequisite in prerequisites:
                    if prerequisite in newDict:
                        newProtId = newDict[prerequisite].getObjId()
                        newPrerequisites.append(newProtId)
                    else:
                        logger.info('"Wait for" id %s missing: ignored.' % prerequisite)
                prot._prerequisites.set(newPrerequisites)

        for protDict in protocolsList:
            protId = protDict['object.id']

            if protId in newDict:
                prot = newDict[protId]
                _setPrerequisites(prot)
                for paramName, attr in prot.iterDefinitionAttributes():
                    if paramName in protDict:
                        # If the attribute is a pointer, we should look
                        # if the id is already in the dictionary and 
                        # set the extended property
                        if attr.isPointer():
                            _setPointer(attr, protDict[paramName])
                        # This case is similar to Pointer, but the values
                        # is a list and we will setup a pointer for each value
                        elif isinstance(attr, pwobj.PointerList):
                            attribute = protDict[paramName]
                            if attribute is None:
                                continue
                            for value in attribute:
                                p = pwobj.Pointer()
                                _setPointer(p, value)
                                attr.append(p)
                        # For "normal" parameters we just set the string value
                        else:
                            try:
                                attr.set(protDict[paramName])
                            # Case for Scalars with pointers. So far this will work for Numbers. With Strings (still there are no current examples)
                            # We will need something different to test if the value look like a pointer: regex? ####.text
                            except ValueError as e:
                                newPointer = pwobj.Pointer()
                                _setPointer(newPointer, protDict[paramName])
                                attr.setPointer(newPointer)

                self.mapper.store(prot)

        self.mapper.commit()

        return newDict

    def saveProtocol(self, protocol):
        self._checkModificationAllowed([protocol], 'Cannot SAVE protocol')

        if (protocol.isRunning() or protocol.isFinished()
                or protocol.isLaunched()):
            raise ModificationNotAllowedException('Cannot SAVE a protocol that is %s. '
                            'Copy it instead.' % protocol.getStatus())

        protocol.setStatus(pwprot.STATUS_SAVED)
        if protocol.hasObjId():
            self._storeProtocol(protocol)
        else:
            self._setupProtocol(protocol)

    def getProtocolFromRuns(self, protId):
        """ Returns the protocol with the id=protId from the runs list (memory) or None"""
        if self.runs:
            for run in self.runs:
                if run.getObjId() == protId:
                    return run

        return None

    def getProtocol(self, protId, fromRuns=False):
        """ Returns the protocol with the id=protId or raises an Exception

        :param protId: integer with an existing protocol identifier
        :param fromRuns: If true, it tries to get it from the runs list (memory) avoiding querying the db."""

        protocol = self.getProtocolFromRuns(protId) if fromRuns else None

        if protocol is None:
            protocol = self.mapper.selectById(protId)

        if not isinstance(protocol, pwprot.Protocol):
            raise Exception('>>> ERROR: Invalid protocol id: %d' % protId)

        self._setProtocolMapper(protocol)

        return protocol

    # FIXME: this function just return if a given object exists, not
    # if it is a protocol, so it is incorrect judging by the name
    # Moreover, a more consistent name (comparing to similar methods)
    # would be: hasProtocol
    def doesProtocolExists(self, protId):
        return self.mapper.exists(protId)

    def getProtocolsByClass(self, className):
        return self.mapper.selectByClass(className)

    def getObject(self, objId):
        """ Retrieve an object from the db given its id. """
        return self.mapper.selectById(objId)

    def _setHostConfig(self, protocol):
        """ Set the appropriate host config to the protocol
        give its value of 'hostname'
        """
        hostName = protocol.getHostName()
        hostConfig = self.getHostConfig(hostName)
        protocol.setHostConfig(hostConfig)

    def _storeProtocol(self, protocol):
        # Read only mode
        if not self.openedAsReadOnly():
            self.mapper.store(protocol)
            self.mapper.commit()

    def _setProtocolMapper(self, protocol):
        """ Set the project and mapper to the protocol. """

        # Tolerate loading errors. For support.
        # When only having the sqlite, sometime there are exceptions here
        # due to the absence of a set.
        from pyworkflow.mapper.sqlite import SqliteFlatMapperException
        try:

            protocol.setProject(self)
            protocol.setMapper(self.mapper)
            self._setHostConfig(protocol)

        except SqliteFlatMapperException:
            protocol.addSummaryWarning(
                "*Protocol loading problem*: A set related to this "
                "protocol couldn't be loaded.")

    def _setupProtocol(self, protocol):
        """Insert a new protocol instance in the database"""

        # Read only mode
        if not self.openedAsReadOnly():
            self._storeProtocol(protocol)  # Store first to get a proper id
            # Set important properties of the protocol
            workingDir = self.getProtWorkingDir(protocol)
            self._setProtocolMapper(protocol)

            protocol.setWorkingDir(self.getPath(PROJECT_RUNS, workingDir))
            # Update with changes
            self._storeProtocol(protocol)

    @staticmethod
    def getProtWorkingDir(protocol):
        """
        Return the protocol working directory
        """
        return "%06d_%s" % (protocol.getObjId(), protocol.getClassName())

    def getRuns(self, iterate=False, refresh=True, checkPids=False):
        """ Return the existing protocol runs in the project. 
        """
        if self.runs is None or refresh:
            # Close db open connections to db files
            if self.runs is not None:
                for r in self.runs:
                    r.closeMappers()

            # Use new selectAll Batch
            # self.runs = self.mapper.selectAll(iterate=False,
            #               objectFilter=lambda o: isinstance(o, pwprot.Protocol))
            self.runs = self.mapper.selectAllBatch(objectFilter=lambda o: isinstance(o, pwprot.Protocol))

            # Invalidate _runsGraph because the runs are updated
            self._runsGraph = None

            for r in self.runs:

                self._setProtocolMapper(r)
                r.setProject(self)

                # Check for run warnings
                r.checkSummaryWarnings()

                # Update nodes that are running and were not invoked
                # by other protocols
                if r.isActive():
                    if not r.isChild():
                        self._updateProtocol(r, checkPid=checkPids)

                self._annotateLastRunTime(r.endTime)

            self.mapper.commit()

        return self.runs

    def _annotateLastRunTime(self, protLastTS):
        """ Sets _lastRunTime for the project if it is after current _lastRunTime"""
        try:
            if protLastTS is None:
                return

            if self._lastRunTime is None:
                self._lastRunTime = protLastTS
            elif self._lastRunTime.datetime() < protLastTS.datetime():
                self._lastRunTime = protLastTS
        except Exception as e:
            return

    def needRefresh(self):
        """ True if any run is active and its timestamp is older than its
        corresponding runs.db
        NOTE: If an external script changes the DB this will fail. It uses
        only in memory objects."""
        for run in self.runs:
            if run.isActive():
                if not pwprot.isProtocolUpToDate(run):
                    return True
        return False

    def checkPid(self, protocol):
        """ Check if a running protocol is still alive or not.
        The check will only be done for protocols that have not been sent
        to a queue system.

        :returns True if pid is alive or irrelevant
        """
        from pyworkflow.protocol.launch import _runsLocally
        pid = protocol.getPid()

        if pid == 0:
            return True

        # Include running and scheduling ones
        # Exclude interactive protocols
        # NOTE: This may be happening even with successfully finished protocols
        # which PID is gone.
        if (protocol.isActive() and not protocol.isInteractive()
                and not pwutils.isProcessAlive(pid)):
            protocol.setFailed("Process %s not found running on the machine. "
                               "It probably has died or been killed without "
                               "reporting the status to Scipion. Logs might "
                               "have information about what happened to this "
                               "process." % pid)
            return False

        return True

    def checkJobId(self, protocol):
        """ Check if a running protocol is still alive or not.
        The check will only be done for protocols that have been sent
        to a queue system.

        :returns True if job is still alive or irrelevant
        """
        if len(protocol.getJobIds()) == 0:
            logger.warning("Checking if protocol alive in the queue but JOB ID is empty. Considering it dead.")
            return False
        jobid = protocol.getJobIds()[0]
        hostConfig = protocol.getHostConfig()

        if jobid == UNKNOWN_JOBID:
            return True

        # Include running and scheduling ones
        # Exclude interactive protocols
        # NOTE: This may be happening even with successfully finished protocols
        # which PID is gone.
        if protocol.isActive() and not protocol.isInteractive():

            jobStatus = _checkJobStatus(hostConfig, jobid)

            if jobStatus == STATUS_FINISHED:
                protocol.setFailed("JOB ID %s not found running on the queue engine. "
                                   "It probably has timeout, died or been killed without "
                                   "reporting the status to Scipion. Logs might "
                                   "have information about what happened to this "
                                   "JOB ID." % jobid)

                return False

        return True
    def iterSubclasses(self, classesName, objectFilter=None):
        """ Retrieve all objects from the project that are instances
            of any of the classes in classesName list.
        Params: 
            classesName: String with commas separated values of classes name. 
            objectFilter: a filter function to discard some of the retrieved
            objects."""
        for objClass in classesName.split(","):
            for obj in self.mapper.selectByClass(objClass.strip(), iterate=True,
                                                 objectFilter=objectFilter):
                yield obj

    def getRunsGraph(self, refresh=False, checkPids=False):
        """ Build a graph taking into account the dependencies between
        different runs, ie. which outputs serves as inputs of other protocols. 
        """

        if refresh or self._runsGraph is None:
            runs = [r for r in self.getRuns(refresh=refresh, checkPids=checkPids)
                    if not r.isChild()]
            self._runsGraph = self.getGraphFromRuns(runs)

        return self._runsGraph

    def getGraphFromRuns(self, runs):
        """
        This function will build a dependencies graph from a set
        of given runs.

        :param runs: The input runs to build the graph
        :return: The graph taking into account run dependencies

        """
        outputDict = {}  # Store the output dict
        g = pwutils.Graph(rootName=ROOT_NODE_NAME)

        for r in runs:
            n = g.createNode(r.strId())
            n.run = r

            # Legacy protocols do not have a plugin!!
            develTxt = ''
            plugin = r.getPlugin()
            if plugin and plugin.inDevelMode():
                develTxt = '* '

            n.setLabel('%s%s' % (develTxt, r.getRunName()))
            outputDict[r.getObjId()] = n
            for _, attr in r.iterOutputAttributes():
                # mark this output as produced by r
                if attr is None:
                    logger.warning("Output attribute %s of %s is None" % (_, r))
                else:
                    outputDict[attr.getObjId()] = n

        def _checkInputAttr(node, pointed):
            """ Check if an attr is registered as output"""
            if pointed is not None:
                pointedId = pointed.getObjId()

                if pointedId in outputDict:
                    parentNode = outputDict[pointedId]
                    if parentNode is node:
                        logger.warning("WARNING: Found a cyclic dependence from node %s to itself, probably a bug. " % pointedId)
                    else:
                        parentNode.addChild(node)
                        if os.environ.get('CHECK_CYCLIC_REDUNDANCY') and self._checkCyclicRedundancy(parentNode, node):
                            conflictiveNodes = set()
                            for child in node.getChildren():
                                if node in child._parents:
                                    child._parents.remove(node)
                                    conflictiveNodes.add(child)
                                    logger.warning("WARNING: Found a cyclic dependence from node %s to %s, probably a bug. "
                                                   % (node.getLabel() + '(' + node.getName() + ')',
                                                      child.getLabel() + '(' + child.getName() + ')'))

                            for conflictNode in conflictiveNodes:
                                node._children.remove(conflictNode)

                            return False
                        return True
            return False

        for r in runs:
            node = g.getNode(r.strId())
            for _, attr in r.iterInputAttributes():
                if attr.hasValue():
                    pointed = attr.getObjValue()
                    # Only checking pointed object and its parent, if more
                    # levels we need to go up to get the correct dependencies
                    if not _checkInputAttr(node, pointed):
                        parent = self.mapper.getParent(pointed)
                        _checkInputAttr(node, parent)
        rootNode = g.getRoot()
        rootNode.run = None
        rootNode.label = ROOT_NODE_NAME

        for n in g.getNodes():
            if n.isRoot() and n is not rootNode:
                rootNode.addChild(n)
        return g

    @staticmethod
    def _checkCyclicRedundancy(parent, child):
        visitedNodes = set()
        recursionStack = set()

        def depthFirstSearch(node):
            visitedNodes.add(node)
            recursionStack.add(node)
            for child in node.getChildren():
                if child not in visitedNodes:
                    if depthFirstSearch(child):
                        return True
                elif child in recursionStack and child != parent:
                    return True

            recursionStack.remove(node)
            return False

        return depthFirstSearch(child)


    def _getRelationGraph(self, relation=pwobj.RELATION_SOURCE, refresh=False):
        """ Retrieve objects produced as outputs and
        make a graph taking into account the SOURCE relation. """
        relations = self.mapper.getRelationsByName(relation)
        g = pwutils.Graph(rootName=ROOT_NODE_NAME)
        root = g.getRoot()
        root.pointer = None
        runs = self.getRuns(refresh=refresh)

        for r in runs:
            for paramName, attr in r.iterOutputAttributes():
                p = pwobj.Pointer(r, extended=paramName)
                node = g.createNode(p.getUniqueId(), attr.getNameId())
                node.pointer = p
                # The following alias if for backward compatibility
                p2 = pwobj.Pointer(attr)
                g.aliasNode(node, p2.getUniqueId())

        for rel in relations:
            pObj = self.getObject(rel[OBJECT_PARENT_ID])

            # Duplicated ...
            if pObj is None:
                logger.warning("Relation seems to point to a deleted object. "
                      "%s: %s" % (OBJECT_PARENT_ID, rel[OBJECT_PARENT_ID]))
                continue

            pExt = rel['object_parent_extended']
            pp = pwobj.Pointer(pObj, extended=pExt)

            if pObj is None or pp.get() is None:
                logger.error("project._getRelationGraph: pointer to parent is "
                      "None. IGNORING IT.\n")
                for key in rel.keys():
                    logger.info("%s: %s" % (key, rel[key]))

                continue

            pid = pp.getUniqueId()
            parent = g.getNode(pid)

            while not parent and pp.hasExtended():
                pp.removeExtended()
                parent = g.getNode(pp.getUniqueId())

            if not parent:
                logger.error("project._getRelationGraph: parent Node "
                      "is None: %s" % pid)
            else:
                cObj = self.getObject(rel['object_child_id'])
                cExt = rel['object_child_extended']

                if cObj is not None:
                    if cObj.isPointer():
                        cp = cObj
                        if cExt:
                            cp.setExtended(cExt)
                    else:
                        cp = pwobj.Pointer(cObj, extended=cExt)
                    child = g.getNode(cp.getUniqueId())

                    if not child:
                        logger.error("project._getRelationGraph: child Node "
                              "is None: %s." % cp.getUniqueId())
                        logger.error("   parent: %s" % pid)
                    else:
                        parent.addChild(child)
                else:
                    logger.error("project._getRelationGraph: child Obj "
                          "is None, id: %s " %  rel['object_child_id'])
                    logger.error("   parent: %s" % pid)

        for n in g.getNodes():
            if n.isRoot() and n is not root:
                root.addChild(n)

        return g

    def getSourceChilds(self, obj):
        """ Return all the objects have used obj
        as a source.
        """
        return self.mapper.getRelationChilds(pwobj.RELATION_SOURCE, obj)

    def getSourceParents(self, obj):
        """ Return all the objects that are SOURCE of this object.
        """
        return self.mapper.getRelationParents(pwobj.RELATION_SOURCE, obj)

    def getTransformGraph(self, refresh=False):
        """ Get the graph from the TRANSFORM relation. """
        if refresh or not self._transformGraph:
            self._transformGraph = self._getRelationGraph(pwobj.RELATION_TRANSFORM,
                                                          refresh)

        return self._transformGraph

    def getSourceGraph(self, refresh=False):
        """ Get the graph from the SOURCE relation. """
        if refresh or not self._sourceGraph:
            self._sourceGraph = self._getRelationGraph(pwobj.RELATION_SOURCE,
                                                       refresh)

        return self._sourceGraph

    def getRelatedObjects(self, relation, obj, direction=pwobj.RELATION_CHILDS,
                          refresh=False):
        """ Get all objects related to obj by a give relation.

        :param relation: the relation name to search for.
        :param obj: object from which the relation will be search,
            actually not only this, but all other objects connected
            to this one by the pwobj.RELATION_TRANSFORM.
        :parameter direction: Not used
        :param refresh: If True, cached objects will be refreshed

        """

        graph = self.getTransformGraph(refresh)
        relations = self.mapper.getRelationsByName(relation)
        connection = self._getConnectedObjects(obj, graph)

        objects = []
        objectsDict = {}

        for rel in relations:
            pObj = self.getObject(rel[OBJECT_PARENT_ID])

            if pObj is None:
                logger.warning("Relation seems to point to a deleted object. "
                      "%s: %s" % (OBJECT_PARENT_ID, rel[OBJECT_PARENT_ID]))
                continue
            pExt = rel['object_parent_extended']
            pp = pwobj.Pointer(pObj, extended=pExt)

            if pp.getUniqueId() in connection:
                cObj = self.getObject(rel['object_child_id'])
                cExt = rel['object_child_extended']
                cp = pwobj.Pointer(cObj, extended=cExt)
                if cp.hasValue() and cp.getUniqueId() not in objectsDict:
                    objects.append(cp)
                    objectsDict[cp.getUniqueId()] = True

        return objects

    def _getConnectedObjects(self, obj, graph):
        """ Given a TRANSFORM graph, return the elements that
        are connected to an object, either children, ancestors or siblings.
        """
        n = graph.getNode(obj.strId())
        # Get the oldest ancestor of a node, before reaching the root node
        while n is not None and not n.getParent().isRoot():
            n = n.getParent()

        connection = {}

        if n is not None:
            # Iterate recursively all descendants
            for node in n.iterChildren():
                connection[node.pointer.getUniqueId()] = True
                # Add also 
                connection[node.pointer.get().strId()] = True

        return connection

    def isReadOnly(self):
        if getattr(self, 'settings', None) is None:
            return False

        return self.settings.getReadOnly()

    def isInReadOnlyFolder(self):
        return self._isInReadOnlyFolder

    def openedAsReadOnly(self):
        return self.isReadOnly() or self.isInReadOnlyFolder()

    def setReadOnly(self, value):
        self.settings.setReadOnly(value)

    def fixLinks(self, searchDir):
        logger.info(f"Fixing links for project {self.getShortName()}. Searching in: {searchDir}")
        runs = self.getRuns()

        counter = 0
        for prot in runs:
            if prot.getClassName().startswith("ProtImport"):
                runName = prot.getRunName()
                logger.info(f"Found protocol {runName}")
                for f in prot.getOutputFiles():
                    if ':' in f:
                        f = f.split(':')[0]

                    if not os.path.exists(f):
                        logger.info(f"\tMissing link: {f}")

                        if os.path.islink(f):
                            sourceFile = os.path.realpath(f)
                            newFile = pwutils.findFileRecursive(os.path.basename(sourceFile),
                                                                searchDir)
                            if newFile:
                                counter += 1
                                logger.info(f"\t\tCreating link: {f} -> {newFile}")
                                pwutils.createAbsLink(newFile, f)

        logger.info(f"Fixed {counter} broken links")

    @staticmethod
    def cleanProjectName(projectName):
        """ Cleans a project name to avoid common errors
        Use it whenever you want to get the final project name pyworkflow will end up.
        Spaces will be replaced by _ """

        return re.sub(r"[^\w\d\-\_]", "-", projectName)


class MissingProjectDbException(Exception):
    pass


class ModificationNotAllowedException(Exception):
    pass
