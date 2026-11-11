"""Product name and external links shown in the user interface."""

APP_NAME = "OpenDofusData"
# Placeholder until the online price server exists; the only place the URL is defined.
SAAS_URL = "https://opendofusdata.example"
# The public repository; the only place the URL is defined.
REPOSITORY_URL = "https://github.com/NathanRodet/OpenDofusData"
RELEASES_PAGE_URL = REPOSITORY_URL + "/releases"
# The one request the tool makes on its own (update check): the latest published release.
RELEASES_API_URL = "https://api.github.com/repos/NathanRodet/OpenDofusData/releases/latest"
