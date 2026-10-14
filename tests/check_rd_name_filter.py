# Self-check for the Real-Debrid name filter: python3 tests/check_rd_name_filter.py
# Records are Real-Debrid's answers to addMagnet on one account, 2026-10-13/14.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui  # first: importing debrid directly is circular
from debrid.services import realdebrid
import releases

REFUSED_BODY = '{\n\t"error": "infringing_file",\n\t"error_code": 35\n}'
ADDED_BODY = '{\n\t"id": "7SGQ6Z7LGK6NQ",\n\t"uri": "https:\\/\\/api.real-debrid.com\\/rest\\/1.0\\/torrents\\/info\\/7SGQ6Z7LGK6NQ"\n}'
# refused by name in both passes, an hour apart
TAGGED = ('185f8d7ec1063c05a26e5dd13adf631b87b5ead7', 'The.Fantastic.Four.First.Steps.2025.IMAX.1080p.DSNP.WEB-DL.DD+5.1.Atmos.H.264-playWEB', 451)
# added at once
CLEAN = ('bf3f69b7dcfbe376899d5bf4f34710eec31b0001', '【高清影视之家发布 www.BBEBBB.com】美国队长4[HDR+杜比视界双版本][国英多音轨+简繁英字幕].2025.V2.BluRay.2160p.TrueHD7.1.DoVi.HDR.x265.10bit-DreamHD', 201)
# refused in pass 1, added in pass 2: a 451 on a clean name is no verdict beyond the run
BLOCKED = ('b5b3c9d181bedbb40c53e8fb11897f0905ae3f18', 'Captain.America.Brave.New.World.2025.1080p.HDTC.Hindi.Dual.DD.2.0.x264.Full4Movies.mkv', 451)

class response:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content.encode()

class session:
    def __init__(self, record):
        self.record = record
        self.adds = 0
    def post(self, url, headers=None, data=None):
        if url.endswith('/addMagnet'):
            self.adds += 1
            return response(self.record[2], REFUSED_BODY if self.record[2] == 451 else ADDED_BODY)
        return response(204, '')

class element:
    def __init__(self, record):
        hash, title, _ = record
        self.Releases = [releases.release('[test]', 'torrent', title, [], 1, ['magnet:?xt=urn:btih:' + hash + '&dn=' + title])]
        self.Releases[0].cached = ['RD']
    def deviation(self):
        return '.*'
    def files(self):
        return []

def download(record):
    realdebrid.session = session(record)
    added = realdebrid.download(element(record), stream=False)
    return added, realdebrid.session.adds

assert download(TAGGED) == (False, 0), 'a name Real-Debrid refuses must never be sent'
assert download(CLEAN) == (True, 1), 'a clean name must be added'
assert download(BLOCKED) == (False, 1), 'a 451 on a clean name is tried once'
assert download(BLOCKED) == (False, 0), 'a hash that drew a 451 must not be re-added in the same run'
assert [bool(realdebrid.blocked.search(n)) for n in ('A.1080p.BluRay.DTS-HD', 'A.2002.BluRay.DTS-HD', 'A.WEB.DL', 'a.webrip')] == [True, False, False, True]
# Real-Debrid's own answers on 2026-10-14, each name a fresh webseed torrent so only the name decided:
# an add is judged on the root name, an unrestrict on the file's own name.
import json
probe = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rd-name-filter-2026-10-14.json')))
for answer in probe['add'] + probe['unrestrict']:
    assert bool(realdebrid.blocked.search(answer['name'])) == (answer['status'] == 451), answer
print('ok')
