#import modules
from base import *
from ui.ui_print import *
import releases

base_url = "http://127.0.0.1:9696"
api_key = ""
name = "prowlarr"
session = requests.Session()


def setup(cls, new=False):
    from scraper.services import setup
    setup(cls, new)


def make_release(result, download):
    """Build a plex_debrid release from a resolved magnet."""
    if getattr(result, 'indexer', None) is not None:
        source = '[prowlarr: ' + str(result.indexer) + ']'
    else:
        source = '[prowlarr: unnamed]'

    if getattr(result, 'size', None) is not None:
        size = float(result.size) / 1000000000
    else:
        size = 1

    seeders = getattr(result, 'seeders', 0)
    if seeders is None:
        seeders = 0

    return releases.release(
        source,
        'torrent',
        result.title,
        [],
        size,
        [download],
        seeders=seeders
    )


def scrape(query, altquery):
    from scraper.services import active

    scraped_releases = []

    if 'prowlarr' not in active:
        return scraped_releases

    url = (
        base_url
        + '/api/v1/search?query='
        + query
        + '&type=search&limit=1000&offset=0'
    )

    headers = {'X-Api-Key': api_key}

    try:
        response = session.get(url, headers=headers, timeout=60)

    except requests.exceptions.Timeout:
        ui_print(
            '[prowlarr] error: prowlarr request timed out. '
            'Reduce the number of prowlarr indexers or make sure they are healthy.'
        )
        return []

    except Exception as e:
        ui_print(
            '[prowlarr] error: prowlarr couldnt be reached. '
            'Make sure your prowlarr base url is correctly formatted '
            '(default: http://localhost:9696).'
        )
        print("[PROWLARR] search error:", repr(e), flush=True)
        return []

    if response.status_code != 200:
        print(
            "[PROWLARR] search returned HTTP",
            response.status_code,
            flush=True
        )
        return []

    try:
        results = json.loads(
            response.content,
            object_hook=lambda d: SimpleNamespace(**d)
        )

    except Exception as e:
        ui_print('[prowlarr] error: prowlarr didnt return any data.')
        print("[PROWLARR] JSON error:", repr(e), flush=True)
        return []

    to_resolve = []

    for result in results:
        try:
            result.title = result.title.replace(' ', '.')
            result.title = result.title.replace(':', '').replace("'", '')
            result.title = regex.sub(r'\.+', ".", result.title)

            title_matches = regex.match(
                r'('
                + altquery.replace('.', r'\.').replace(r'\.*', '.*')
                + ')',
                result.title,
                regex.I
            )

            if not title_matches:
                continue

            if getattr(result, 'protocol', None) != 'torrent':
                continue

            magnet_url = getattr(result, 'magnetUrl', None)
            download_url = getattr(result, 'downloadUrl', None)

            # A genuine magnet can be used immediately.
            if (
                isinstance(magnet_url, str)
                and magnet_url.lower().startswith('magnet:')
            ):
                scraped_releases.append(
                    make_release(result, magnet_url)
                )
                continue

            # Newer Prowlarr/indexer responses may put an HTTP proxy/download
            # endpoint in magnetUrl instead of an actual magnet URI.
            if (
                isinstance(magnet_url, str)
                and magnet_url.lower().startswith(('http://', 'https://'))
            ):
                to_resolve.append((result, magnet_url))
                continue

            # Traditional Prowlarr download URL.
            if (
                isinstance(download_url, str)
                and download_url.lower().startswith(('http://', 'https://'))
            ):
                to_resolve.append((result, download_url))
                continue

        except Exception as e:
            print(
                "[PROWLARR] result processing error:",
                getattr(result, 'title', '<unknown>'),
                repr(e),
                flush=True
            )

    # Resolve proxy/download URLs concurrently.
    resolved_results = [None] * len(to_resolve)
    threads = []

    for index, item in enumerate(to_resolve):
        result, resolve_url = item

        t = Thread(
            target=multi_init,
            args=(resolve, (result, resolve_url), resolved_results, index)
        )

        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    for result in resolved_results:
        if result:
            scraped_releases += result

    return scraped_releases


def resolve(item):
    """
    Resolve a Prowlarr HTTP proxy/download endpoint into either:
      - a magnet redirect, or
      - a .torrent payload converted to a magnet.
    """
    scraped_releases = []

    result, resolve_url = item

    try:
        link = session.get(
            resolve_url,
            allow_redirects=False,
            timeout=15
        )

        # Some indexers/Prowlarr endpoints redirect directly to a magnet.
        location = link.headers.get('Location')

        if location:
            if str(location).lower().startswith('magnet:'):
                scraped_releases.append(
                    make_release(result, location)
                )
                return scraped_releases

            # Occasionally a redirect may lead to another HTTP endpoint.
            if str(location).lower().startswith(('http://', 'https://')):
                second = session.get(
                    location,
                    allow_redirects=False,
                    timeout=15
                )

                second_location = second.headers.get('Location')

                if (
                    second_location
                    and str(second_location).lower().startswith('magnet:')
                ):
                    scraped_releases.append(
                        make_release(result, second_location)
                    )
                    return scraped_releases

                second_type = second.headers.get('Content-Type', '')

                if 'application/x-bittorrent' in second_type.lower():
                    magnet = releases.torrent2magnet(second.content)

                    if magnet:
                        scraped_releases.append(
                            make_release(result, magnet)
                        )

                    return scraped_releases

        # Prowlarr may return the .torrent directly.
        content_type = link.headers.get('Content-Type', '')

        if 'application/x-bittorrent' in content_type.lower():
            magnet = releases.torrent2magnet(link.content)

            if magnet:
                scraped_releases.append(
                    make_release(result, magnet)
                )

            return scraped_releases

        print(
            "[PROWLARR] unable to resolve torrent:",
            result.title,
            "HTTP",
            link.status_code,
            "type=",
            repr(content_type),
            flush=True
        )

    except Exception as e:
        print(
            "[PROWLARR] resolver error:",
            result.title,
            repr(e),
            flush=True
        )

    return scraped_releases


# Multiprocessing watchlist method
def multi_init(cls, obj, result, index):
    result[index] = cls(obj)
