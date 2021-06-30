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

import os
import sys
import time
import argparse

from pyworkflow.protocol import (getProtocolFromDb,
                                 STATUS_FINISHED, STATUS_ABORTED, STATUS_FAILED,
                                 STATUS_RUNNING, STATUS_SCHEDULED, STATUS_SAVED,
                                 STATUS_LAUNCHED, Set, Protocol, MAX_SLEEP_TIME)
from pyworkflow.constants import PROTOCOL_UPDATED

# Add callback for remote debugging if available.
from pyworkflow.utils import prettyTimestamp

try:
    from rpdb2 import start_embedded_debugger
    from signal import signal, SIGUSR2

    signal(SIGUSR2, lambda sig, frame: start_embedded_debugger('a'))
except ImportError:
    pass

stopStatuses = [STATUS_FINISHED, STATUS_ABORTED, STATUS_FAILED]


class RunScheduler:
    """ Check that all dependencies are met before launching a run. """

    def __init__(self):
        self._parseArgs()
        # Enter to the project directory and load protocol from db
        self.protocol = self._loadProtocol()
        self.project = self.protocol.getProject()
        self.log = open(self.protocol.getScheduleLog(), 'w')
        self.protPid = os.getpid()
        self.protocol.setPid(self.protPid)
        self.protocol._store(self.protocol._pid)
        self.prerequisites = list(map(int, self.protocol.getPrerequisites()))
        # Keep track of the last time the protocol was checked and
        # its modification date to avoid unnecessary db opening
        self.updatedProtocols = dict()
        self.initial_sleep = self._args.initial_sleep

    def getSleepTime(self):
        return self._args.sleepTime

    def getInitialSleepTime(self):
        return self.initial_sleep

    def _parseArgs(self):
        parser = argparse.ArgumentParser()
        _addArg = parser.add_argument  # short notation

        _addArg("projPath", metavar='PROJECT_NAME',
                help="Project database path.")

        _addArg("dbPath", metavar='DATABASE_PATH',
                help="Protocol database path.")

        _addArg("protId", type=int, metavar='PROTOCOL_ID',
                help="Protocol ID.")

        _addArg("--initial_sleep", type=int, default=0,
                dest='initial_sleep', metavar='SECONDS',
                help="Initial sleeping time (in seconds)")

        _addArg("--sleep_time", type=int, default=15,
                dest='sleepTime', metavar='SECONDS',
                help="Sleeping time (in seconds) between updates.")

        _addArg("--wait_for", nargs='*', type=int, default=[],
                dest='waitProtIds', metavar='PROTOCOL_ID',
                help="List of protocol ids that should be not running "
                     "(i.e, finished, aborted or failed) before this "
                     "run will be executed.")

        self._args = parser.parse_args()

    def _loadProtocol(self):
        return getProtocolFromDb(self._args.projPath,
                                 self._args.dbPath,
                                 self._args.protId, chdir=True)

    def _log(self, msg):
        self.log.write("%s: %s\n" % (prettyTimestamp(), msg))
        self.log.flush()

    def _updateProtocol(self, protocol):

        protId = protocol.getObjId()

        if protId in self.updatedProtocols:
            return self.updatedProtocols[protId]

        protDb = protocol.getDbPath()

        if os.path.exists(protDb):
            updateResult = self.project._updateProtocol(protocol)
            if updateResult == PROTOCOL_UPDATED:
                self._log("Updated protocol: %s (%s)" % (protId, protocol))
            self.updatedProtocols[protId] = protocol

        return protocol

    def _getProtocolFromPointer(self, pointer):
        """
        The function return a protocol from an attribute

           A) When the pointer points to a protocol

           B) When the pointer points to another object (INDIRECTLY).
              - The pointer has an _extended value (new parameters
                configuration in the protocol)

           C) When the pointer points to another object (DIRECTLY).
              - The pointer has not an _extended value (old parameters
                configuration in the protocol)
        """
        output = pointer.get()
        if isinstance(output, Protocol):  # case A
            protocol = output
        else:
            if pointer.hasExtended():  # case B
                protocol = pointer.getObjValue()
            else:  # case C
                protocol = self.project.getNode(str(output.getObjParentId())).run
        return protocol

    def _getSecondsToWait(self, inProt):
        """
        Assigns a timeout penalty or reward depending on the status of the
        input protocol (inProt)
        If inProt status is stopped we assign a reward i.o.c a penalty
        """
        protStatus = inProt.getStatus()
        inStreaming = inProt.worksInStreaming()
        meStreaming = self.protocol.worksInStreaming()

        penaltyRewardValues = {
            STATUS_LAUNCHED: 5 if inStreaming else 10,
            STATUS_RUNNING: -2 if inStreaming else 3,
            STATUS_SCHEDULED: int(self.getSleepTime()/2),
            STATUS_SAVED: self.getSleepTime(),
        }

        secondToWait = penaltyRewardValues.get(protStatus, -3)

        if not meStreaming:
            secondToWait += 3 * self.getSleepTime()

        return secondToWait

    def _checkPrerequisites(self, prerequisites, project):
        # Check if we need to wait for required protocols
        wait = False
        # For each protocol that is a prerequisite that has not finished,
        # we'll penalize with 3 more seconds of waiting
        penalize = 0
        self._log("Checking prerequisites... %s" % prerequisites)
        for protId in prerequisites:
            # Check if prerequisites exist. In the case of metaprotocols, it
            # may be necessary to load them from the project database.
            node = project.getRunsGraph().getNode(str(protId))

            if node is None:
                self._log("Updating runs graph. Missing protocol ... %s" % protId)
                project.getRunsGraph(refresh=True)

            node = project.getRunsGraph().getNode(str(protId))
            # Check if the protocol is within our workflow
            if node is None:
                self._log("Protocol can't wait for %s. Missing prerequisite " % protId)
                break

            prot = project.getRunsGraph().getNode(str(protId)).run
            if prot is not None:
                prot = self._updateProtocol(prot)
                penalize += self._getSecondsToWait(prot)
                if prot.getStatus() not in stopStatuses:
                    wait = True
                    self._log("   ...waiting for %s" % prot)
        return wait, penalize

    def _checkMissingInput(self):
        """
         Check if there are missing inputs
         In case of having them, check if protocol is in streaming
        """
        inputMissing = False
        # For each input that is not ready we'll penalize with 3 more
        # seconds of waiting
        penalize = 0

        self._log("Checking input data...")
        # Updating input protocols
        for key, attr in self.protocol.iterInputAttributes():
            inputProt = self._getProtocolFromPointer(attr)
            inputProt = self._updateProtocol(inputProt)
            penalize += self._getSecondsToWait(inputProt)

        validation = self.protocol.validate()
        if len(validation) > 0:
            inputMissing = True
            self._log("%s doesn't validate:\n\t- %s" % (self.protocol.getObjLabel(),
                                                        '\n\t- '.join(
                                                            validation)))
        elif not self.protocol.worksInStreaming():
            for key, attr in self.protocol.iterInputAttributes():
                inSet = attr.get()
                if isinstance(inSet, Set) and inSet.isStreamOpen():
                    inputMissing = True
                    self._log("Waiting for closing %s... (%s does not work in "
                              "streaming)" % (inSet, self.protocol))
                    break

        if not inputMissing:
            inputProtocolDict = self.protocol.inputProtocolDict()
            for prot in inputProtocolDict.values():
                self._updateProtocol(prot)

        return inputMissing, penalize

    def schedule(self):
        self._log("Scheduling protocol %s, PID: %s,prerequisites: %s" %
                  (self.protocol.getObjId(), self.protPid, self.prerequisites))

        initialSleepTime = runScheduler.getInitialSleepTime()
        self._log("Waiting %s seconds before start checking inputs " % initialSleepTime)
        time.sleep(initialSleepTime)

        while True:
            # Clear the list of protocols updated in the previous loop
            self.updatedProtocols.clear()
            sleepTime = self.getSleepTime()
            # FIXME: This does not cover all the cases:
            # When the user registers new coordinates after clicking the
            # "Analyze result" button, this action is registered in the project.sqlite
            # and not in it's own run.db and never gets updated. It is not critical and
            # will only affect a combination of json import with extended that will
            # appear after clicking on the "Analyze result" button.

            # Check if there are missing inputs
            missing, penalize = self._checkMissingInput()
            sleepTime += penalize

            # Check the prerequisites
            wait, penalize = self._checkPrerequisites(self.prerequisites,
                                                      self.project)
            sleepTime += penalize

            if not missing and not wait:
                break

            sleepTime = max(min(sleepTime, MAX_SLEEP_TIME), self.getSleepTime())

            self._log("Still not ready, sleeping %s seconds...\n" % sleepTime)
            time.sleep(sleepTime)

        self._log("Launching the protocol >>>>")
        self.log.close()
        self.project.launchProtocol(self.protocol, scheduled=True, force=True)


if __name__ == '__main__':

    # Create a child process
    # using os.fork() method
    pid = os.fork()

    # pid greater than 0 represents
    # the parent process
    if pid > 0:
        sys.exit(0)
    else:
        try:
            runScheduler = RunScheduler()
            runScheduler.schedule()
        except Exception as ex:
            print(ex)
            print("Schedule fail with this parameters: ", sys.argv)