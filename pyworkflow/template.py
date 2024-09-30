""" Module to host templates classes"""
import collections
import glob
import os
import tempfile
from datetime import datetime
from pyworkflow import SCIPION_JSON_TEMPLATES, Config, VarTypes
from pyworkflow.utils import greenStr
import logging
logger = logging.getLogger(__name__)

class Template:
    def __init__(self, source, name, description=""):
        self.source = source
        # Tidy up templates names: removing .json.template and .json (when passed as parameter)
        self.name = name
        self.description = description
        self.content = None
        self.params = None
        self.projectName = None

    def __str__(self):
        return self.name

    def getContent(self):
        """ Returns the content of the template if not present it calls , loadContent"""

        if self.content is None:
            self.content = self.loadContent()

        return self.content

    def loadContent(self):
        """ Method to load into self.content the content of a template"""
        pass

    def getObjId(self):
        return self.source + '-' + self.name

    def genProjectName(self):
        self.projectName = self.getObjId() + '-' + datetime.now().strftime("%y%m%d-%H%M%S")

    def replaceEnvVariables(self):
        self.content = (self.getContent() % os.environ).split('~')

    def parseContent(self):

        content = self.getContent()

        def paramStr2Param(fieldIndex, fieldString):
            fieldLst = fieldString.split('|')

            title = fieldLst[0]
            defaultValue = fieldLst[1] if len(fieldLst) >= 2 else None
            varType = fieldLst[2] if len(fieldLst) >= 3 else None
            alias = fieldLst[3] if len(fieldLst) >= 4 else None

            return TemplateParam(fieldIndex, title, defaultValue, varType, alias)

        # Fill each field in the template in order to prevent spreading in the form
        self.params = collections.OrderedDict()
        for index in range(1, len(content), 2):
            param = paramStr2Param(index, content[index])
            self.params[param.getTitle()] = param

    def createTemplateFile(self):

        # Where to write the json file.
        (fileHandle, path) = tempfile.mkstemp()

        self._replaceFields()

        finalJson = "".join(self.getContent())

        os.write(fileHandle, finalJson.encode())
        os.close(fileHandle)

        print("New workflow saved at " + path)

        return path

    def _replaceFields(self):

        for field in self.params.values():
            self.content[field.getIndex()] = field.getValue()

    def getParams(self):
        return self.params

    def setParamValue(self, alias, newValue):
        paramsSetted = 0
        for field in self.params.values():
            if field.getAlias() == alias:
                oldValue = field.getValue()
                field.setValue(newValue)
                if field.validate() is None:
                    paramsSetted += 1
                    print(greenStr("%s set to %s") %
                          (field.getTitle(), str(newValue)))
                else:
                    field.setValue(oldValue)
                    raise Exception("%s is not compatible with %s(%s) parameter." % (newValue, field.getTitle(), alias))
        if not paramsSetted:
            raise Exception("Alias %s not recognized." % alias)
        return paramsSetted

class LocalTemplate(Template):
    """ Local template representing a json file in the file system"""

    def __init__(self, source, tempPath):
        # Tidy up templates names: removing .json.template and .json (when passed as parameter)
        name = os.path.basename(tempPath).replace(SCIPION_JSON_TEMPLATES, "").replace(".json", "")
        super().__init__(source,name, "")
        self.templatePath = os.path.abspath(tempPath)
        self.description, self.content = self._parseTemplate()

    def _parseTemplate(self):
        with open(self.templatePath, 'r') as myFile:
            allContents = myFile.read().splitlines()
            description, index = LocalTemplate.getDescription(allContents)

        if not description:
            description = 'Not provided'
        content = ''.join(allContents[index:])
        return description, content


    @staticmethod
    def getDescription(strList):
        # Example of json.template file with description:
        # -----------------------------------------------
        # Here goes the description
        # Description
        # Another description line...
        # [
        #    {
        #       "object.className": "ProtImportMovies",
        #       "object.id": "2",...
        # -----------------------------------------------

        contents_start_1 = '['
        contents_start_2 = '{'
        description = []
        counter = 0
        nLines = len(strList)

        while counter + 1 < nLines:
            currentLine = strList[counter]
            nextLine = strList[counter + 1]
            if contents_start_1 not in currentLine:
                description.append(currentLine)
            else:
                if contents_start_2 in nextLine:
                    break
                else:
                    description.append(currentLine)
            counter += 1

        return ''.join(description), counter



class TemplateParam(object):
    def __init__(self, index, title, value=None, varType=None, alias=None):
        self._index = index
        self._title = title
        self._value = value
        self._type = int(varType)
        self._alias = alias

    def getTitle(self):
        return self._title

    def getIndex(self):
        return self._index

    def getType(self):
        return self._type

    def getValue(self):
        return self._value

    def setValue(self, value):
        self._value = value

    def getAlias(self):
        return self._alias

    def validate(self):
        return Validations.check(self._value, self._type)


class Validations:

    """ FIELDS VALIDATION """
    """ FIELDS TYPES"""
    @classmethod
    def check(cls, value, fieldType):
        if fieldType == VarTypes.BOOLEAN.value:
            return cls.validBoolean(value)
        elif fieldType == VarTypes.DECIMAL.value:
            return cls.validDecimal(value)
        elif fieldType == VarTypes.INTEGER.value:
            return cls.validInteger(value)
        elif fieldType in (VarTypes.PATH.value, VarTypes.FOLDER.value):
            return cls.validPath(value)
        elif fieldType == VarTypes.STRING.value:
            return cls.validString(value)

        else:
            return "Type %s for %s not recognized. Review the template." % (fieldType, value)

    @staticmethod
    def validString(value):
        if value is None:
            return "String does not accept None/empty values."

    @staticmethod
    def validInteger(value):
        if not value.isdigit():
            return "Value does not seem to be an integer number."

    @staticmethod
    def validPath(value):
        if not os.path.exists(value):
            return "Path does not exists."

    @staticmethod
    def validDecimal(value):

        try:
            float(value)
            return None
        except Exception as e:
            return "Value can't be converted to a float (%s)" % str(e)

    @staticmethod
    def validBoolean(value):
        validValues = ["true", "1", "false", "0"]

        valueL = value.lower()

        if valueL not in validValues:
            return "Only valid values for a boolean type are: %s" % validValues


class TemplateList:
    def __init__(self, templates=None):
        self.templates = templates if templates else []

    def addTemplate(self, t):
        self.templates.append(t)

    def genFromStrList(self, templateList):
        for t in templateList:
            parsedPath = t.split(os.path.sep)
            pluginName = parsedPath[parsedPath.index('templates') - 1]
            self.addTemplate(LocalTemplate(pluginName, t))

    def sortListByPluginName(self):
        # Create a identifier with both plugin and template names to sort by both
        self.templates = sorted(self.templates, key=lambda template: '.' + template.getObjId()
                                if template.getObjId().startswith('local') else template.getObjId())

        return self

    def addScipionTemplates(self, tempId=None):
        """ Adds scipion templates from local file system or from workflow hub.
        :param tempId: identifier of the template to look up for. If fount only this template is chosen
        """

        self.addLocalTemplates(tempId)

        if tempId is None or len(self.templates) == 0:
            self.addWHTemplates(tempId)


    def addLocalTemplates(self, tempId=None):
        # Check if there is any .json.template in the template folder
        # get the template folder (we only want it to be included once)
        templateFolder = Config.getExternalJsonTemplates()
        for templateName in glob.glob1(templateFolder,
                                       "*" + SCIPION_JSON_TEMPLATES):
            t = LocalTemplate("local", os.path.join(templateFolder, templateName))
            if tempId is not None:
                if t.getObjId() == tempId:
                    self.addTemplate(t)
                    break
            else:
                self.addTemplate(t)

    def addWHTemplates(self, tempId=None):

        try:

            from pyworkflow.webservices.workflowhub import get_wh_templates

            templates = get_wh_templates(tempId)

            self.templates.extend(templates)
        except Exception as e:
            logger.warning("Can't get templates from workflow hub: %s" % e)

    def addPluginTemplates(self, tempId=None):
        """
        Get the templates provided by all plugins.
        :return: a list of templates
        """
        # Check if other plugins have json.templates
        domain = Config.getDomain()
        # Check if there is any .json.template in the template folder
        # get the template folder (we only want it to be included once)
        for pluginName, pluginModule in domain.getPlugins().items():
            tempListPlugin = pluginModule._pluginInstance.getTemplates()
            for t in tempListPlugin:
                if tempId is not None:
                    if t.getObjId() == tempId:
                        self.addTemplate(t)
                        break
                else:
                    self.addTemplate(t)

