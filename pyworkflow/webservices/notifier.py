# **************************************************************************
# *
# * Authors:    Roberto Marabini       (roberto@cnb.csic.es)
#               J.M. De la Rosa Trevin (jmdelarosa@cnb.csic.es)
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


import os
import time
import threading
import uuid
from datetime import timedelta, datetime
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPHandler

import pyworkflow.utils as pwutils
from . import config


class ProjectWorkflowNotifier(object):
    """ Implement different types of notifications about a given
    project. Currently, the protocols in a workflow will be sent.
    """

    def __init__(self, project):
        self.project = project

    def _getUuidFileName(self):
        return self.project.getLogPath("uuid.log")

    def _getDataFileName(self, fileName="data.log"):
        return self.project.getLogPath(fileName)

    def _getUuid(self):
        # Load (or create if not exits) a file
        # in the project Logs folder to store an unique
        # project identifier
        uuidFn = self._getUuidFileName()
        try:
            with open(uuidFn) as f:
                uuidValue = f.readline()
        except IOError:
            uuidValue = str(uuid.uuid4())
            with open(uuidFn, 'w') as f:
                f.write(uuidValue)

        return uuidValue

    def _modifiedBefore(self, seconds):
        """ Return True if the uuid.log file has been modified within a given
        number of seconds. """
        uuidFn = self._getUuidFileName()
        if not os.path.exists(uuidFn):
            return False
        mTime = datetime.fromtimestamp(os.path.getmtime(uuidFn))
        delta = datetime.now() - mTime

        return delta < timedelta(seconds=seconds)

    def _sendData(self, url, dataDict=None):
        try:
            # then connect to webserver a send json
            # set debuglevel=0 for no messages
            opener = build_opener(HTTPHandler(debuglevel=0))
            data = urlencode(dataDict).encode()
            content = opener.open(url, data=data).read()
            now = time.time()
            os.utime(self._getUuidFileName(), (now, now))
        except Exception as e:
            pass
            # print("Could not notify, maybe there is not internet connection.")

    def _dataModified(self, projectWorfklow):
        try:
            with open(self._getDataFileName()) as f:
                projectWorfklow2 = f.readline()
                if projectWorfklow2 == projectWorfklow:
                    return False
        except IOError:
            pass
        return True

    def notifyWorkflow(self):

        try:
            # check if environment exists otherwise abort
            if not pwutils.envVarOn('SCIPION_NOTIFY'):
                return

            # if project specifies not to send stats
            if self._isProjectMuted():
                return
            # Check the seconds range of the notify, by default one day
            seconds = int(os.environ.get('SCIPION_NOTIFY_SECONDS', '86400'))

            if self._modifiedBefore(seconds):  # notify not more than once a day
                return

            # INFO: now we are only sending the protocols names in the project.
            # We could pass namesOnly=False to get the full workflow template
            projectWorfklow = self.project.getProtocolsJson(namesOnly=True)

            # if list with workflow has not been altered do not sent it
            if not self._dataModified(projectWorfklow):
                return
            else:
                # For compatibility with version 1.0 check
                # if Log directory exists. If it does not
                # create it
                # TODO: REMOVE this check in scipion 1.3
                dataFile = self._getDataFileName()
                # create the folder of the file path if not exists
                pwutils.makeFilePath(dataFile)
                with open(dataFile, 'w') as f:
                    f.write(projectWorfklow)
            dataDict = {'project_uuid': self._getUuid(),
                        'project_workflow': projectWorfklow}

            urlName = os.environ.get('SCIPION_NOTIFY_URL',
                                     config.SCIPION_STATS_WORKFLOW_APP).strip()
            urlName += "addOrUpdateWorkflow/"
            t = threading.Thread(name="notifier", target=lambda: self._sendData(urlName, dataDict))
            t.start()  # will execute function in a separate thread
        except Exception as e:
            print("Can't report usage: ", e)

    def _isProjectMuted(self):
        """ Projects are muted if they come from tests, Since there is no flag for it
        we will assume that if the project name starts with Test it will be considered
        a test and therefore no statistics will be sent"""
        return os.path.basename(self.project.name).startswith("Test")

    def getEntryFromWebservice(self, uuid):
        if not pwutils.envVarOn('SCIPION_NOTIFY'):
            return
        urlName = os.environ.get('SCIPION_NOTIFY_URL').strip()
        # remove last directory
        urlName = os.path.split(urlName)[0]
        url = urlName + "/?project_uuid=" + uuid
        resultDict = self._sendData(url)
