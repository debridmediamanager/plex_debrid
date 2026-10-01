#import modules
from base import *
from ui.ui_print import *
import releases

# (required) Name of the Debrid service
name = "Debrid Link"
short = "DL"

# Authentication
api_key = ""
client_id = "0KLCzpbPTCsWZtQ9Ad0aZA"

session = requests.Session()


def setup(cls, new=False):
    from debrid.services import setup
    setup(cls, new)


def logerror(response):
    if response.status_code != 200:
        ui_print(
            "[debridlink] error "
            + str(response.status_code)
            + ": "
            + str(response.content),
            debug=ui_settings.debug
        )

    if 'error' in str(response.content):
        try:
            response2 = json.loads(
                response.content,
                object_hook=lambda d: SimpleNamespace(**d)
            )

            if response2.error != 'authorization_pending':
                ui_print(
                    "[debridlink] error "
                    + str(response.status_code)
                    + ": "
                    + response2.error
                )
        except:
            if response.status_code != 200:
                ui_print(
                    "[debridlink] error "
                    + str(response.status_code)
                    + ": unknown error"
                )

    if response.status_code == 401:
        ui_print(
            "[debridlink] error 401: debridlink api key does not "
            "seem to work. check your debridlink settings."
        )


def get(url):
    headers = {
        'User-Agent':
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/50.0.2661.102 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Bearer ' + api_key
    }

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=30
        )

        logerror(response)

        return json.loads(
            response.content,
            object_hook=lambda d: SimpleNamespace(**d)
        )

    except Exception as e:
        ui_print(
            "debridlink error: (json exception): " + str(e),
            debug=ui_settings.debug
        )

        return None


def post(url, data):
    headers = {
        'User-Agent':
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/50.0.2661.102 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Bearer ' + api_key
    }

    try:
        response = session.post(
            url,
            headers=headers,
            data=data,
            timeout=30
        )

        logerror(response)

        return json.loads(
            response.content,
            object_hook=lambda d: SimpleNamespace(**d)
        )

    except Exception as e:
        ui_print(
            "debridlink error: (json exception): " + str(e),
            debug=ui_settings.debug
        )

        return None


# OAuth
def oauth(code=""):
    if code == "":
        response = post(
            'https://debrid-link.fr/api/oauth/device/code',
            'client_id=' + client_id
        )

        return response.device_code, response.user_code

    response = None

    while response is None:
        response = post(
            'https://debrid-link.fr/api/oauth/token',
            'client_id='
            + client_id
            + '&code='
            + code
            + '&grant_type=http%3A%2F%2Foauth.net%2F'
              'grant_type%2Fdevice%2F1.0'
        )

        if hasattr(response, 'error'):
            response = None

        time.sleep(1)

    return response.access_token


def download(element, stream=True, query='', force=False):
    """
    Add the selected torrent directly to Debrid-Link.

    Debrid-Link's old /seedbox/cached endpoint is no longer
    available, so cache availability is not checked beforehand.
    """

    if query == '':
        query = element.deviation()

    for release in element.Releases[:]:

        if not (
            regex.match(r'(' + query + ')', release.title, regex.I)
            or force
        ):
            continue

        if len(release.download) == 0:
            continue

        magnet = release.download[0]

        if not isinstance(magnet, str):
            continue

        if not magnet.lower().startswith('magnet:'):
            ui_print(
                '[debridlink] skipping release without valid magnet: '
                + release.title,
                debug=ui_settings.debug
            )
            continue

        try:
            url = 'https://debrid-link.fr/api/v2/seedbox/add'

            response = post(
                url,
                {
                    'url': magnet,
                    'async': 'true'
                }
            )

            if response is not None and getattr(
                response,
                'success',
                False
            ):
                ui_print(
                    '[debridlink] added release: '
                    + release.title
                )

                return True

            if response is not None:
                ui_print(
                    '[debridlink] could not add release: '
                    + release.title
                    + ' - '
                    + str(getattr(response, 'error', 'unknown error'))
                )

        except Exception as e:
            ui_print(
                '[debridlink] error adding release: '
                + release.title
                + ' - '
                + str(e)
            )

    return False


def check(element, force=False):
    """
    Compatibility check for modern Debrid-Link.

    The former /seedbox/cached endpoint has been disabled.

    plex_debrid expects check() to populate release.cached before
    its version rules are applied. We therefore mark releases with
    valid magnets as DL-eligible.

    IMPORTANT:
    "DL" here means Debrid-Link can accept the release. It no longer
    means that Debrid-Link has confirmed the torrent is already cached.
    """

    valid = []

    for release in element.Releases[:]:

        if len(release.download) == 0:
            element.Releases.remove(release)
            continue

        magnet = release.download[0]

        if not (
            isinstance(magnet, str)
            and magnet.lower().startswith('magnet:')
            and len(release.hash) == 40
        ):
            element.Releases.remove(release)
            continue

        release.cached += ['DL']
        valid.append(release)

    ui_print(
        '[debridlink] '
        + str(len(valid))
        + ' valid torrent release(s) available for Debrid-Link',
        debug=ui_settings.debug
    )
