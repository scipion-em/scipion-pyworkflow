#!/usr/bin/env python
# -*- coding: utf-8 -*-
# **************************************************************************
# *
# * Authors:   Pablo Conesa [1]
# *
# * [1] Biocomputing unit, CNB-CSIC
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
import json
import logging
logger = logging.getLogger(__name__)

from urllib.request import urlopen
from pyworkflow import Config


# Module to have Models for reporting usage data to the scipion.i2pc.es site.
class ProtStat:
    """ Class to store the usage part of a reported ScipionWorkflow"""
    def __init__(self, count=0, nextProtsDict=None):
        self._count = count
        self._nextProts = nextProtsDict or dict()

    def getCount(self):
        return self._count
    def addUsage(self, count=1):
        self._count += count
    def addCountToNextProtocol(self, nextProt, count=1):
        self._nextProts[nextProt] = self._nextProts.get(nextProt, 0) + count

    def toJSON(self):
        jsonStr = "[%s,{%s}]"
        nextProtS = ""

        if len(self._nextProts):
            nextProtA = []
            for protName, count in self._nextProts.items():
                nextProtA.append('"%s":%d' % (protName, count))

            nextProtS= ",".join(nextProtA)

        jsonStr = jsonStr % (self._count, nextProtS)

        return jsonStr

    def __repr__(self):
        return self.toJSON()

class ScipionWorkflow:
    """ Class to serialize and deserialize what is reported from scipion.
    Example: {"ProtA":
                [2, {
                        "ProtB":2,
                        "ProtC":3,
                        ...
                    }
                ], ...
              }
    """

    def __init__(self, jsonStr=None):
        """ Instantiate this class optionally with a JSON string serialized from this class
        (what is sent by Scipion to this web service)."""

        self._prots = dict()
        if jsonStr is not None:
            self.deserialize(jsonStr)

    def getProtStats(self):
        return self._prots

    def deserialize(self, jsonStr):
        """ Deserialize a JSONString serialized by this class with the toJSON method"""
        jsonObj = json.loads(jsonStr)

        if isinstance(jsonObj, dict):
            self.deserializeV2(jsonObj)
        else:
            self.deserializeList(jsonObj)

    def deserializeV2(self, jsonObj):
        """ Deserializes v2 usage stats: something like {"ProtA": [2,{..}],...} """
        for key, value in jsonObj.items():
            # Value should be something like [2,{..}]
            count = value[0]
            nextProtDict = value[1]
            nextProt = ProtStat(count, nextProtDict)
            self._prots[key] = nextProt

    def deserializeList(self, jsonObj):
        """ Deserializes old data: a list of protocol names repeated: ["ProtA","ProtA", "ProtB", ...] """

        for protName in jsonObj:
            self.addCount(protName)

    def addCount(self, protName):
        """ Adds one to the count of a protocol"""

        protStat = self.getProtStat(protName)

        protStat.addUsage()

    def getProtStat(self, protName):

        protStat = self._prots.get(protName, ProtStat())
        if protName not in self._prots:
            self._prots[protName] = protStat

        return protStat

    def addCountToNextProtocol(self, protName, nextProtName):
        protStat = self.getProtStat(protName)
        protStat.addCountToNextProtocol(nextProtName)

    def getCount(self):
        """ Returns the number of protocols in the workflow"""
        count = 0
        for ps in self._prots.values():
            count += ps._count
        return count

    def toJSON(self):
        """ Returns a valid JSON string"""
        if len(self._prots) == 0:
            return "{}"
        else:
            jsonStr="{"
            for protName, protStat in self._prots.items():

                jsonStr += '"%s":%s,' % (protName, protStat.toJSON())

            jsonStr = jsonStr[:-1] + "}"

            return jsonStr

    def __repr__(self):
        return self.toJSON()

def getNextProtocolSuggestions(protocol):
    """ Returns the suggestions from the Scipion website for the next protocols to the protocol passed"""

    try:
        url = Config.SCIPION_STATS_SUGGESTION % protocol  # protocol.getClassName()
        results = json.loads(urlopen(url).read().decode('utf-8'))
        return results
    except Exception as e:
        logger.error("Suggestions system not available", exc_info=e)
        return []