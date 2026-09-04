"""Client HTTP minimale basato sulla libreria standard.

Nessuna dipendenza esterna: il workflow di GitHub Actions gira senza pip install.

Se sulla tua macchina un antivirus o un proxy aziendale intercetta il TLS,
Python rifiuta il certificato. In quel caso lancia con:

    JOBTRACKER_INSECURE=1 python scripts/build.py

La verifica resta attiva su GitHub Actions, dove il problema non si presenta.
"""

import gzip
import json
import os
import ssl
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

_ctx = None
if os.environ.get("JOBTRACKER_INSECURE") == "1":
    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE


def _apri(req, timeout):
    ultimo = None
    for tentativo in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
                dati = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    dati = gzip.decompress(dati)
                return dati
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            ultimo = e
            time.sleep(2 * (tentativo + 1))
    raise ultimo


def get(url, timeout=45, headers=None):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    h.update(headers or {})
    return _apri(urllib.request.Request(url, headers=h), timeout)


def post_json(url, payload, timeout=60, headers=None):
    h = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    h.update(headers or {})
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=h, method="POST"
    )
    return json.loads(_apri(req, timeout).decode("utf-8"))
