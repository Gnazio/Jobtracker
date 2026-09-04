"""Fonte: Adzuna - annunci del settore privato.

InPA copre solo la pubblica amministrazione. Adzuna e' l'unico aggregatore con
API ufficiale, gratuita e con ricerca per raggio che copra bene l'Italia:
`where=Pisa&distance=150` e' esattamente il criterio del sito.

Serve una chiave gratuita da https://developer.adzuna.com/ (registrazione in un
minuto), da mettere nelle variabili d'ambiente ADZUNA_APP_ID e ADZUNA_APP_KEY.
Su GitHub Actions vanno messe come *secrets* del repository. Senza chiave questa
fonte non fa nulla e il resto del build continua a funzionare.

Nota: gli annunci privati non hanno vincoli di classe di laurea, quindi il
filtro LM-21 non si applica e vengono marcati come tali.
"""

import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geo  # noqa: E402
from http_client import get  # noqa: E402

API = "https://api.adzuna.com/v1/api/jobs/it/search/{pagina}"

# Una query per ciascuna delle competenze spendibili. Adzuna cerca in titolo e
# descrizione, quindi conviene tenerle corte e specifiche: query lunghe non
# restituiscono nulla.
QUERY = [
    "machine learning",
    "deep learning",
    "computer vision",
    "data scientist",
    "intelligenza artificiale",
    "ingegnere biomedico",
    "ingegneria clinica",
    "dispositivi medici",
    "elaborazione immagini",
    "bioingegneria",
    "python ricerca",
    "software sanitario",
]


def _chiavi():
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    return (app_id, app_key) if app_id and app_key else (None, None)


def configurata():
    """True se le chiavi sono presenti nell'ambiente."""
    return bool(_chiavi()[0])


def _cerca(app_id, app_key, cosa, raggio_km, per_pagina=50, giorni=45):
    import json

    parametri = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": per_pagina,
        "what": cosa,
        "where": "Pisa",
        "distance": raggio_km,
        "max_days_old": giorni,
        "content-type": "application/json",
    }
    url = API.format(pagina=1) + "?" + urllib.parse.urlencode(parametri)
    return json.loads(get(url, timeout=40).decode("utf-8"))


def _pulisci(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def scarica(raggio_km, **_):
    app_id, app_key = _chiavi()
    if not app_id:
        print(
            "  Adzuna: nessuna chiave (ADZUNA_APP_ID/ADZUNA_APP_KEY), fonte saltata",
            file=sys.stderr,
        )
        return []

    visti = {}
    for cosa in QUERY:
        try:
            dati = _cerca(app_id, app_key, cosa, raggio_km)
        except Exception as e:
            print(f"  Adzuna: query '{cosa}' fallita ({e})", file=sys.stderr)
            continue
        for r in dati.get("results") or []:
            rid = str(r.get("id") or "")
            if rid and rid not in visti:
                visti[rid] = r

    return [_normalizza(r, raggio_km) for r in visti.values()]


def _normalizza(r, raggio_km):
    luogo = (r.get("location") or {})
    etichetta = luogo.get("display_name") or ""
    aree = luogo.get("area") or []

    # Adzuna restituisce l'area dal generale al particolare: l'ultima voce e'
    # il comune. Provo tutte, dalla piu' specifica.
    provincia, km = None, None
    for nome in reversed(aree + [etichetta]):
        dedotta = geo.citta_da_testo(nome)
        if dedotta:
            provincia = dedotta
            km = geo.distanza_provincia(dedotta)
            break

    # Adzuna ha gia' filtrato per raggio con distance=raggio_km: se non
    # riesco a ricondurre il comune a una provincia nota, l'annuncio resta
    # comunque dentro il raggio. Marcarlo "nazionale" lo farebbe scartare.
    if km is None:
        ambito = "provincia"
    else:
        ambito = "provincia" if km <= raggio_km else "fuori"

    azienda = (r.get("company") or {}).get("display_name") or ""
    return {
        "id": "adzuna:" + str(r.get("id")),
        "media_id": None,
        "fonte": "Adzuna",
        "titolo": (r.get("title") or "").strip(),
        "figura": (r.get("category") or {}).get("label") or "",
        "ente": azienda,
        "descrizione": _pulisci(r.get("description"))[:600],
        "descrizione_completa": "",
        "url": r.get("redirect_url") or "",
        "pubblicazione": r.get("created"),
        "scadenza": None,
        "stato": "Aperto",
        "posti": None,
        "procedura": None,
        "sede": provincia or etichetta or "Sede da verificare",
        "provincia": provincia,
        "km": km,
        "ambito": ambito,
    }
