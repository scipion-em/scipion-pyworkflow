import json
from urllib.request import Request, urlopen
from pyworkflow.template import Template


class WHTemplate(Template):

    def __init__(self, source, name, description, url):
        super().__init__(source, name, description)
        self.url = url

    def loadContent(self):
        """ Download the file pointer by url and read the content"""

        return make_request(self.url, asJson=False)


def make_request(url, asJson=True):
    """ Makes a request to the url and returns the json as a dictionary"""

    req = Request(url)
    req.add_header("accept", "application/json")

    with urlopen(req, timeout=1) as response:
        if asJson:
            data = json.load(response)
        else:
            html_response = response.read()
            encoding = response.headers.get_content_charset('utf-8')
            data = html_response.decode(encoding)
        return data


def get_workflow_file_url(workflow_id, version):
    root_url = "https://workflowhub.eu/workflows/%s/git/%s/" % (workflow_id, version)
    url = root_url + 'tree'

    result = make_request(url)

    for file in result["tree"]:
        path = (file["path"])
        if path.endswith(".json.template"):
            return root_url + 'raw/' + path


def get_wh_templates(template_id=None, organization="Scipion%20CNB"):
    """ Returns a list of scipion templates available in workflow hub"""

    url = "https://workflowhub.eu/ga4gh/trs/v2/tools?organization=%s" % organization

    response = make_request(url)

    template_list = []

    for workflow in response:
        workflow_id = workflow["id"]
        name = workflow["name"]
        description = workflow['description']
        version = workflow["versions"][-1]
        version_id = version["id"]
        template_url = get_workflow_file_url(workflow_id, version_id)

        new_template = WHTemplate("Workflow hub", name, description, template_url)
        if template_id is None or new_template.getObjId() == template_id:
            template_list.append(new_template)

    return template_list


if __name__ == "__main__":

    templates = get_wh_templates()
    for template in templates:
        print(template)
