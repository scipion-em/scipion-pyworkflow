import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from pyworkflow.template import Template

logger = logging.getLogger(__name__)


class WHTemplate(Template):
    def __init__(self, source, name, description, url):
        super().__init__(source, name, description)
        self.url = url

    def loadContent(self):
        """Download the remote template file content and return it as text."""
        data = makeRequest(self.url, asJson=False)

        # Some endpoints may return extra text before the actual JSON starts
        stripped = data.lstrip()
        if not stripped:
            return data

        if stripped[0] in ("{", "["):
            return stripped

        firstObj = data.find("{")
        firstArr = data.find("[")
        candidates = [pos for pos in (firstObj, firstArr) if pos != -1]
        if not candidates:
            return data

        return data[min(candidates):]


def makeRequest(url, asJson=True, timeout=10, extraHeaders=None):
    """Fetch JSON or text content from a URL."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json" if asJson else "text/plain,*/*;q=0.8",
    }
    if extraHeaders:
        headers.update(extraHeaders)

    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=timeout) as response:
            encoding = response.headers.get_content_charset("utf-8")
            rawText = response.read().decode(encoding, errors="replace")
            return json.loads(rawText) if asJson else rawText

    except HTTPError as e:
        errorBody = e.read().decode("utf-8", errors="replace")
        logger.error(
            "workflowHubHttpError url=%s statusCode=%s reason=%s bodyPreview=%s",
            url,
            getattr(e, "code", None),
            getattr(e, "reason", None),
            errorBody[:500],
        )
        raise

    except URLError as e:
        logger.error("workflowHubUrlError url=%s error=%s", url, str(e))
        raise

    except Exception as e:
        logger.error("workflowHubRequestError url=%s error=%s", url, str(e))
        raise


def extractBlobPathsFromTreeHtml(treeHtml, rootUrl):
    """Extract file paths from /blob/ links on a WorkflowHub tree HTML page."""
    hrefs = re.findall(r'href="([^"]+)"', treeHtml)
    blobPaths = []

    for href in hrefs:
        if "/blob/" not in href:
            continue

        fullUrl = urljoin(rootUrl, href)
        blobPath = fullUrl.split("/blob/", 1)[1]
        blobPaths.append(blobPath)

    # Deduplicate while preserving order
    seen = set()
    uniquePaths = []
    for p in blobPaths:
        if p in seen:
            continue
        seen.add(p)
        uniquePaths.append(p)

    return uniquePaths


def selectWorkflowJsonPath(paths):
    """Pick the most likely workflow JSON file from a list of repository paths."""
    jsonPaths = [p for p in paths if p.lower().endswith(".json")]

    if not jsonPaths:
        return None

    # Avoid common metadata files if present
    filtered = [
        p for p in jsonPaths
        if not p.lower().endswith("ro-crate-metadata.json")
    ]
    if not filtered:
        filtered = jsonPaths

    # Prefer a canonical filename if it exists
    preferredNames = {"workflow.json", "workflowhub.json", "template.json"}
    for p in filtered:
        if p.split("/")[-1].lower() in preferredNames:
            return p

    return filtered[0]


def getWorkflowFileUrl(workflowId, versionId):
    rootUrl = f"https://workflowhub.eu/workflows/{workflowId}/git/{versionId}/"
    treeUrl = rootUrl + "tree"

    # The tree endpoint is HTML, not JSON
    treeHtml = makeRequest(
        treeUrl,
        asJson=False,
        timeout=10,
        extraHeaders={"Accept": "text/html,*/*;q=0.8"},
    )

    paths = extractBlobPathsFromTreeHtml(treeHtml, rootUrl)
    chosenPath = selectWorkflowJsonPath(paths)

    if not chosenPath:
        raise Exception(f"Couldn't find any .json file in tree page: {treeUrl}")

    return rootUrl + "raw/" + chosenPath


def selectLatestVersion(workflow):
    """Select a reasonable 'latest' version from TRS workflow metadata."""
    versions = workflow.get("versions") or []
    if not versions:
        return None

    # Try numeric sort on version id if possible, otherwise fall back to last item
    def versionKey(v):
        vid = str(v.get("id", ""))
        if vid.isdigit():
            return int(vid)
        return vid

    try:
        return sorted(versions, key=versionKey)[-1]
    except Exception:
        return versions[-1]


def getWhTemplates(templateId=None, organization="Scipion CNB"):
    """Return a list of Scipion templates available in WorkflowHub (TRS)."""
    orgEncoded = quote(organization, safe="")
    url = f"https://workflowhub.eu/ga4gh/trs/v2/tools?organization={orgEncoded}"

    response = makeRequest(url, asJson=True, timeout=10)

    templateList = []

    for workflow in response:
        name = workflow.get("name", "<unknown>")
        try:
            workflowId = workflow["id"]
            description = workflow.get("description", "")

            version = selectLatestVersion(workflow)
            if not version:
                raise Exception("No versions available")

            versionId = version["id"]
            templateUrl = getWorkflowFileUrl(workflowId, versionId)

            newTemplate = WHTemplate("WH", name, description, templateUrl)
            if templateId is None or newTemplate.getObjId() == templateId:
                templateList.append(newTemplate)

        except Exception as e:
            logger.warning(
                "workflowHubTemplateSkip name=%s workflowId=%s error=%s",
                name,
                workflow.get("id", None),
                str(e),
            )

    return templateList


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    templates = getWhTemplates()
    for t in templates:
        print(t)
