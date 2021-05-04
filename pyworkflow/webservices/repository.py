import webbrowser
import json
import requests

from pyworkflow import CORE_VERSION
from . import config


class WorkflowRepository(object):
    """ Manager to communicate with the workflow repository services.
    It will provide functions to:
    - Search workflows (open the url in a browser).
    - Upload a given workflow json file.
    """
    def __init__(self,
                 repositoryUrl=config.WORKFLOW_REPOSITORY_SERVER,
                 uploadFileSuffix=config.WORKFLOW_PROG_STEP1,
                 uploadMdSuffix=config.WORKFLOW_PROG_STEP2):
        self._url = repositoryUrl
        self._uploadFileUrl = repositoryUrl + uploadFileSuffix
        self._uploadMdUrl = repositoryUrl + uploadMdSuffix

    def search(self):
        """ Open the repository URL in a web browser. """
        webbrowser.open(self._url)

    def upload(self, jsonFileName):
        """ Upload a given workflow providing the path ot the json file.

        First the file is uploaded, then the metadata is uploaded.
        The script uploads the file and then opens a browser for the metadata
        Note that the two steps are needed since no initial value can be passed
        to a file field. poster3 module is needed. Poster3 is pure python
        so it may be added to the directory rather than installed if needed.

        The server is django a uses filefield and csrf_exempt.
        csrf_exempt disable csrf checking. filefield
        """

        # we are going to upload a file so this is a multipart
        # connection
        with open(jsonFileName, "rb") as workflowFile:
            file_dict = {"json": workflowFile}
            response = requests.post(self._uploadFileUrl, files=file_dict)

        # server returns  a json stored as text at response.text
        _dict = json.loads(response.text)

        version = CORE_VERSION
        # version hack end

        fnUrl = "?jsonFileName=%s&versionInit=%s" % (_dict['jsonFileName'],
                                                     version)  # use GET
        # open browser to fill metadata, fileName will be saved as session
        # variable. Note that I cannot save the file never in the
        # session in the first connection because the browser changes
        # from urlib2 to an actual browser
        # so sessions are different
        webbrowser.open(self._uploadMdUrl + fnUrl)
