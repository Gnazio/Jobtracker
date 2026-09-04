"""Fonte: InPA - Portale del reclutamento (portale.inpa.gov.it).

Dal 2022 tutte le procedure di reclutamento della PA - compresi enti di ricerca,
universita' e aziende sanitarie - devono essere pubblicate qui. E' la fonte
principale del tracker.

L'endpoint e' quello usato dal sito pubblico: accetta un POST JSON e ignora i
campi che non conosce. I filtri utili sono `regioneId` e `status`.
"""

import re
import sys
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geo  # noqa: E402
from http_client import post_json  # noqa: E402

API = "https://portale.inpa.gov.it/concorsi-smart/api/concorso-public-area/search-better"
REGIONI = "https://portale.inpa.gov.it/concorsi-smart/api/indirizzo/regioni/find-all"
DETTAGLIO = "https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={}"

HEADERS = {"Origin": "https://www.inpa.gov.it", "Referer": "https://www.inpa.gov.it/"}

# id di regione usati dall'API (stabili, ricavati da /indirizzo/regioni/find-all)
REGIONE_ID = {
    "Abruzzo": "1", "Basilicata": "2", "Calabria": "3", "Campania": "4",
    "Emilia Romagna": "5", "Friuli Venezia Giulia": "6", "Lazio": "7",
    "Liguria": "8", "Lombardia": "9", "Marche": "10", "Molise": "11",
    "Piemonte": "12", "Puglia": "13", "Sardegna": "14", "Sicilia": "15",
    "Toscana": "16", "Trentino Alto Adige": "17", "Umbria": "18",
    "Valle d'Aosta": "19", "Veneto": "20",
}


def _testo(html):
    """Toglie i tag dalla descrizione HTML restituita dall'API."""
    if not html:
        return ""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _pagina(regione_id, stati, page, size=200):
    body = {"regioneId": regione_id, "status": stati}
    return post_json(f"{API}?page={page}&size={size}", body, headers=HEADERS)


def scarica(raggio_km, stati=("OPEN", "VISIBLE"), max_pagine=12):
    """Scarica i bandi delle regioni che hanno almeno una provincia nel raggio."""
    stati = list(stati)
    visti = set()
    grezzi = []

    for regione in geo.regioni_entro(raggio_km):
        rid = REGIONE_ID.get(regione)
        if not rid:
            continue
        pagina = 0
        while pagina < max_pagine:
            dati = _pagina(rid, stati, pagina)
            contenuto = dati.get("content") or []
            if not contenuto:
                break
            for c in contenuto:
                if c.get("id") and c["id"] not in visti:
                    visti.add(c["id"])
                    grezzi.append(c)
            if dati.get("last") or pagina + 1 >= (dati.get("totalPages") or 1):
                break
            pagina += 1

    return [_normalizza(c, raggio_km) for c in grezzi]


def _normalizza(c, raggio_km):
    etichetta, provincia, km, ambito = geo.risolvi_sedi(c.get("sedi"), raggio_km)
    enti = c.get("entiRiferimento") or []
    ente = c.get("ente")
    if isinstance(ente, dict):
        ente = ente.get("denominazione")
    if not enti and ente:
        enti = [ente]

    # Se il bando dichiara solo la regione, il nome dell'ente di solito
    # basta a individuare il comune ("Comune di Ravenna", "Universita' di Pisa").
    if ambito == "regione":
        dedotta = geo.citta_da_testo(", ".join(enti), c.get("titolo"))
        if dedotta:
            km_ded = geo.distanza_provincia(dedotta)
            if km_ded is not None:
                provincia, km = dedotta, km_ded
                etichetta = dedotta
                ambito = "provincia" if km_ded <= raggio_km else "fuori"

    return {
        "id": "inpa:" + c["id"],
        "fonte": "InPA",
        "titolo": (c.get("titolo") or "").strip(),
        "figura": (c.get("figuraRicercata") or "").strip(),
        "ente": ", ".join(enti) if enti else "",
        "descrizione": _testo(c.get("descrizioneBreve") or c.get("descrizione"))[:600],
        "descrizione_completa": _testo(c.get("descrizione"))[:4000],
        "url": DETTAGLIO.format(c["id"]),
        "pubblicazione": c.get("dataPubblicazione"),
        "scadenza": c.get("dataScadenza"),
        "stato": c.get("statusLabel") or c.get("calculatedStatus"),
        "posti": c.get("numPosti"),
        "procedura": c.get("tipoProcedura"),
        "sede": etichetta,
        "provincia": provincia,
        "km": km,
        "ambito": ambito,
    }
