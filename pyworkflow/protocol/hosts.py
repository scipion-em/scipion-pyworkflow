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
This modules contains classes to store information about
execution hosts.
"""


import os
import sys
import json
from configparser import RawConfigParser
from collections import OrderedDict

import pyworkflow as pw
from pyworkflow import PARALLEL_COMMAND_VAR
from pyworkflow.object import Object, String, Integer


class HostConfig(Object):
    """ Main store the configuration for execution hosts. """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.label = String(kwargs.get('label', None))
        self.hostName = String(kwargs.get('hostName', None))
        self.userName = String()
        self.password = String()
        self.hostPath = String()
        self.mpiCommand = String()
        self.scipionHome = String()
        self.scipionConfig = String()
        self.address = String()
        self.queueSystem = QueueSystemConfig()

    def getLabel(self):
        return self.label.get()

    def getHostName(self):
        return self.hostName.get()

    def getUserName(self):
        return self.userName.get()

    def getPassword(self):
        return self.password.get()

    def getHostPath(self):
        return self.hostPath.get()

    def getSubmitCommand(self):
        return self.queueSystem.submitCommand.get()

    def getSubmitPrefix(self):
        return self.queueSystem.submitPrefix.get()

    def getCheckCommand(self):
        return self.queueSystem.checkCommand.get()

    def getCancelCommand(self):
        return self.queueSystem.cancelCommand.get()

    def isQueueMandatory(self):
        return self.queueSystem.mandatory.get()

    def getSubmitTemplate(self):
        return self.queueSystem.getSubmitTemplate()

    def getQueuesDefault(self):
        return self.queueSystem.queuesDefault

    def getMpiCommand(self):
        return self.mpiCommand.get()

    def getQueueSystem(self):
        return self.queueSystem

    def getJobDoneRegex(self):
        return self.queueSystem.jobDoneRegex.get()

    def setLabel(self, label):
        self.label.set(label)

    def setHostName(self, hostName):
        self.hostName.set(hostName)

    def setUserName(self, userName):
        self.userName.set(userName)

    def setPassword(self, password):
        self.password.set(password)

    def setHostPath(self, hostPath):
        self.hostPath.set(hostPath)

    def setMpiCommand(self, mpiCommand):
        self.mpiCommand.set(mpiCommand)

    def setQueueSystem(self, queueSystem):
        self.queueSystem = queueSystem

    def getScipionHome(self):
        """ Return the path where Scipion is installed in
        the host.
        """
        return self.scipionHome.get()

    def setScipionHome(self, newScipionHome):
        self.scipionHome.set(newScipionHome)

    def getScipionConfig(self):
        """ From which file to read the configuration file in
        this hosts.
        """
        return self.scipionConfig.get()

    def setScipionConfig(self, newConfig):
        self.scipionConfig.set(newConfig)

    def getAddress(self):
        return self.address.get()

    def setAddress(self, newAddress):
        return self.address.set(newAddress)

    @classmethod
    def writeBasic(cls, configFn):
        """ Write a very basic Host configuration for testing purposes. """
        with open(configFn, 'w') as f:
            f.write('[localhost]\nPARALLEL_COMMAND = '
                    'mpirun -np %_(JOB_NODES)d --map-by node %_(COMMAND)s\n')

    @classmethod
    def load(cls, hostsConf):
        """ Load several hosts from a configuration file.
        Return an dictionary with hostName -> hostConfig pairs.
        """
        # Read from users' config file. Raw to avoid interpolation of %: we expect %_
        cp = RawConfigParser(comment_prefixes=";")
        cp.optionxform = str  # keep case (stackoverflow.com/questions/1611799)
        hosts = OrderedDict()

        try:
            assert cp.read(hostsConf) != [], 'Missing file %s' % hostsConf

            for hostName in cp.sections():
                host = HostConfig(label=hostName, hostName=hostName)
                host.setHostPath(pw.Config.SCIPION_USER_DATA)

                # Helper functions (to write less)
                def get(var, default=None):
                    if cp.has_option(hostName, var):

                        value = cp.get(hostName, var)
                        # Rescue python2.7 behaviour: ## at the beginning of a line, means a single #.
                        # https://github.com/scipion-em/scipion-pyworkflow/issues/70
                        value = value.replace("\n##", "\n#")

                        # Keep compatibility: %_ --> %%
                        value = value.replace('%_(', '%(')

                        return value
                    else:
                        return default

                def getDict(var):
                    try:
                        od = OrderedDict()

                        if cp.has_option(hostName, var):
                            for key, value in json.loads(get(var)).items():
                                od[key] = value

                        return od
                    except Exception as e:
                        raise AttributeError("There is a parsing error in the '%s' variable: %s" % (var, str(e)))

                host.setScipionHome(get(pw.SCIPION_HOME_VAR, pw.Config.SCIPION_HOME))
                host.setScipionConfig(pw.Config.SCIPION_CONFIG)
                # Read the address of the remote hosts,
                # using 'localhost' as default for backward compatibility
                host.setAddress(get('ADDRESS', 'localhost'))
                host.mpiCommand.set(get(PARALLEL_COMMAND_VAR))
                host.queueSystem = QueueSystemConfig()
                hostQueue = host.queueSystem  # shortcut
                hostQueue.name.set(get('NAME'))

                # If the NAME is not provided or empty
                # do no try to parse the rest of Queue parameters
                hostQueue.submitPrefix.set(get('SUBMIT_PREFIX', ''))
                if hostQueue.hasName():
                    hostQueue.setMandatory(get('MANDATORY', 0))
                    hostQueue.submitCommand.set(get('SUBMIT_COMMAND'))
                    hostQueue.submitTemplate.set(get('SUBMIT_TEMPLATE'))
                    hostQueue.cancelCommand.set(get('CANCEL_COMMAND'))
                    hostQueue.checkCommand.set(get('CHECK_COMMAND'))
                    hostQueue.jobDoneRegex.set(get('JOB_DONE_REGEX'))
                    hostQueue.queues = getDict('QUEUES')
                    hostQueue.queuesDefault = getDict('QUEUES_DEFAULT')

                hosts[hostName] = host

            return hosts
        except Exception as e:
            sys.exit('Failed to read settings. The reported error was:\n  %s\n'
                     'Review %s and run again.'
                     % (e, os.path.abspath(hostsConf)))


class QueueSystemConfig(Object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = String()
        # Number of cores from which the queue is mandatory
        # 0 means no mandatory at all
        # 1 will force to launch all jobs through the queue
        self.mandatory = Integer()
        self.queues = None  # List for queue configurations
        self.submitCommand = String()
        # Allow to change the prefix of submission scripts
        # we used by default the ID.job, but in some clusters
        # the job script should start by a letter
        self.submitPrefix = String()
        self.checkCommand = String()
        self.cancelCommand = String()
        self.submitTemplate = String()
        self.jobDoneRegex = String()

    def hasName(self):
        return self.name.hasValue()

    def hasValue(self):
        return self.hasName() and len(self.queues)

    def getName(self):
        return self.name.get()

    def getMandatory(self):
        return self.mandatory.get()

    def getSubmitTemplate(self):
        return self.submitTemplate.get()

    def getSubmitCommand(self):
        return self.submitCommand.get()

    def getCheckCommand(self):
        return self.checkCommand.get()

    def getCancelCommand(self):
        return self.cancelCommand.get()

    def getQueues(self):
        return self.queues

    def setName(self, name):
        self.name.set(name)

    def setMandatory(self, mandatory):
        # This condition is to be backward compatible
        # when mandatory was a boolean
        # now it should use the number of CPU
        # that should force to use the queue
        if mandatory in ['False', 'false']:
            mandatory = 0
        elif mandatory in ['True', 'true']:
            mandatory = 1

        self.mandatory.set(mandatory)

    def setSubmitTemplate(self, submitTemplate):
        self.submitTemplate.set(submitTemplate)

    def setSubmitCommand(self, submitCommand):
        self.submitCommand.set(submitCommand)

    def setCheckCommand(self, checkCommand):
        self.checkCommand.set(checkCommand)

    def setCancelCommand(self, cancelCommand):
        self.cancelCommand.set(cancelCommand)

    def setJobDoneRegex(self, jobDoneRegex):
        self.jobDoneRegex.set(jobDoneRegex)

    def setQueues(self, queues):
        self.queues = queues

    def getQueueConfig(self, objId):
        if objId is not None and self.queues is not None:
            for queueConfig in self.queues:
                if objId == queueConfig.getObjId():
                    return queueConfig
        return None
