""" Module to host templates classes"""
import collections
import glob
import os
import tempfile
from datetime import datetime
from pyworkflow import SCIPION_JSON_TEMPLATES, Config
from pyworkflow.utils import greenStr


class Template:
    def __init__(self, pluginName, tempPath):
        self.pluginName = pluginName
        # Tidy up templates names: removing .json.template and .json (when passed as parameter)
        self.templateName = os.path.basename(tempPath).replace(SCIPION_JSON_TEMPLATES, "").replace(".json", "")
        self.templatePath = os.path.abspath(tempPath)
        self.description, self.content = self._parseTemplate()
        self.params = None
        self.projectName = None

    def __str__(self):
        return self.templatePath

    def getObjId(self):
        return self.pluginName + '-' + self.templateName

    def genProjectName(self):
        self.projectName = self.getObjId() + '-' + datetime.now().strftime("%y%m%d-%H%M%S")

    def replaceEnvVariables(self):
        self.content = (self.content % os.environ).split('~')

    def _parseTemplate(self):
        with open(self.templatePath, 'r') as myFile:
            allContents = myFile.read().splitlines()
            description, index = Template.getDescription(allContents)

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

    def parseContent(self):

        def paramStr2Param(fieldIndex, fieldString):
            fieldLst = fieldString.split('|')

            title = fieldLst[0]
            defaultValue = fieldLst[1] if len(fieldLst) >= 2 else None
            varType = fieldLst[2] if len(fieldLst) >= 3 else None
            alias = fieldLst[3] if len(fieldLst) >= 4 else None

            return TemplateParam(fieldIndex, title, defaultValue, varType, alias)

        # Fill each field in the template in order to prevent spreading in the form
        self.params = collections.OrderedDict()
        for index in range(1, len(self.content), 2):
            param = paramStr2Param(index, self.content[index])
            self.params[param.getTitle()] = param

    def createTemplateFile(self):

        # Where to write the json file.
        (fileHandle, path) = tempfile.mkstemp()

        self._replaceFields()

        finalJson = "".join(self.content)

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
                if field.validate():
                    paramsSetted += 1
                    print(greenStr("%s set to %s") %
                          (field.getTitle(), str(newValue)))
                else:
                    field.setValue(oldValue)
                    raise Exception("%s is not compatible with %s(%s) parameter." % (newValue, field.getTitle(), alias))
        if not paramsSetted:
            raise Exception("Alias %s not recognized." % alias)
        return paramsSetted


class TemplateParam(object):
    def __init__(self, index, title, value=None, varType=None, alias=None):
        self._index = index
        self._title = title
        self._value = value
        self._type = varType
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
    FIELD_TYPE_STR = "0"
    FIELD_TYPE_BOOLEAN = "1"
    FIELD_TYPE_PATH = "2"
    FIELD_TYPE_INTEGER = "3"
    FIELD_TYPE_DECIMAL = "4"

    @classmethod
    def check(cls, value, fieldType):
        if fieldType == cls.FIELD_TYPE_BOOLEAN:
            return cls.validBoolean(value)
        elif fieldType == cls.FIELD_TYPE_DECIMAL:
            return cls.validDecimal(value)
        elif fieldType == cls.FIELD_TYPE_INTEGER:
            return cls.validInteger(value)
        elif fieldType == cls.FIELD_TYPE_PATH:
            return cls.validPath(value)
        elif fieldType == cls.FIELD_TYPE_STR:
            return cls.validString(value)

        else:
            print("Type %s for %s not recognized. Review the template."
                  % (type, value))
            return

    @staticmethod
    def validString(value):
        return value is not None

    @staticmethod
    def validInteger(value):
        return value.isdigit()

    @staticmethod
    def validPath(value):
        return os.path.exists(value)

    @staticmethod
    def validDecimal(value):

        try:
            float(value)
            return True
        except Exception as e:
            return False

    @staticmethod
    def validBoolean(value):
        return value is True or value is False


class TemplateList:
    def __init__(self, templates=None):
        self.templates = templates if templates else []

    def addTemplate(self, t):
        self.templates.append(t)

    def genFromStrList(self, templateList):
        for t in templateList:
            parsedPath = t.split(os.path.sep)
            pluginName = parsedPath[parsedPath.index('templates') - 1]
            self.addTemplate(Template(pluginName, t))

    def sortListByPluginName(self):
        # Create a identifier with both plugin and template names to sort by both
        self.templates = sorted(self.templates, key=lambda template: '.' + template.getObjId()
                                if template.getObjId().startswith('local') else template.getObjId())

        return self

    def addScipionTemplates(self, tempId=None):
        # Check if there is any .json.template in the template folder
        # get the template folder (we only want it to be included once)
        templateFolder = Config.getExternalJsonTemplates()
        for templateName in glob.glob1(templateFolder,
                                       "*" + SCIPION_JSON_TEMPLATES):
            t = Template("local", os.path.join(templateFolder, templateName))
            if tempId is not None:
                if t.getObjId() == tempId:
                    self.addTemplate(t)
                    break
            else:
                self.addTemplate(t)

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
            tempListPlugin = pluginModule.Plugin.getTemplates()
            for t in tempListPlugin:
                if tempId is not None:
                    if t.getObjId() == tempId:
                        self.addTemplate(t)
                        break
                else:
                    self.addTemplate(t)

