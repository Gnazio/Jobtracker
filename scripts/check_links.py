"""Verifica i link della lista curata.

Le pagine "lavora con noi" cambiano indirizzo spesso e un link morto sul sito e'
peggio di un link assente. Il build marca ogni URL con l'esito del controllo e la
pagina mostra il pulsante solo se il link risponde.

Uso autonomo, per sapere quali voci di data/curated.json vanno sistemate:

    python scripts/check_links.py
"""

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_client import UA, _ctx  # noqa: E402

# 404 e 410 sono verdetti definitivi. 403 e 429 di solito significano solo che
# il sito blocca i client non-browser: quei link restano visibili.
ROTTI = {404, 410}


def stato(url, timeout=20):
    if not url:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0  # rete o TLS: non e' colpa dell'URL, non lo marco rotto


def verifica(voci, timeout=20):
    """Aggiunge sito_ok / carriere_ok a ogni voce. Modifica la lista sul posto."""
    lavori = []
    for v in voci:
        for campo in ("sito", "carriere"):
            if v.get(campo):
                lavori.append((v, campo, v[campo]))

    if not lavori:
        return voci

    with ThreadPoolExecutor(max_workers=8) as pool:
        esiti = list(pool.map(lambda t: stato(t[2], timeout), lavori))

    for (v, campo, _), code in zip(lavori, esiti):
        v[campo + "_ok"] = code not in ROTTI
    return voci


def main():
    percorso = Path(__file__).resolve().parents[1] / "data" / "curated.json"
    voci = json.loads(percorso.read_text(encoding="utf-8"))
    verifica(voci)

    problemi = 0
    for v in voci:
        for campo in ("sito", "carriere"):
            if v.get(campo) and not v.get(campo + "_ok"):
                print(f"  ROTTO  {v['nome'][:44]:<46} {campo}: {v[campo]}")
                problemi += 1
        if not v.get("carriere"):
            print(f"  manca  {v['nome'][:44]:<46} carriere: nessun link diretto")

    print(f"\n{problemi} link rotti su {len(voci)} voci.")
    return 1 if problemi else 0


if __name__ == "__main__":
    sys.exit(main())
