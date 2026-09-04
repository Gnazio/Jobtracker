"""Fonte: Gazzetta Ufficiale, 4a Serie Speciale - Concorsi ed esami.

Serve da rete di sicurezza rispetto a InPA: le procedure di universita' ed enti
di ricerca compaiono spesso qui con il testo integrale del bando. Il feed RSS
espone pero' solo il fascicolo piu' recente e con titoli troncati, quindi
leggiamo il sommario HTML degli ultimi fascicoli, che riporta il titolo intero.

La sede non e' un campo strutturato: la si ricava dal nome dell'ente quando
possibile, altrimenti il bando resta marcato 'sede da verificare'.
"""

import re
import sys
from datetime import date, timedelta
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geo  # noqa: E402
from http_client import get  # noqa: E402

RSS = "https://www.gazzettaufficiale.it/rss/S4"
SOMMARIO = (
    "https://www.gazzettaufficiale.it/gazzetta/concorsi/caricaDettaglio/home"
    "?dataPubblicazioneGazzetta={data}&numeroGazzetta={numero}"
)

# Solo gli enti che hanno senso per il profilo: la 4a serie contiene migliaia
# di bandi comunali che InPA copre gia' meglio.
ENTI_INTERESSE = re.compile(
    r"consiglio nazionale delle ricerche|universit|scuola (?:normale|superiore|sant)|"
    r"politecnico|istituto (?:italiano di tecnologia|nazionale|superiore di sanit|"
    r"di ricovero|zooprofilattico)|\bI\.?N\.?F\.?N\b|\bE\.?N\.?E\.?A\b|\bI\.?N\.?A\.?F\b|"
    r"\bI\.?N\.?G\.?V\b|\bC\.?R\.?E\.?A\b|\bI\.?S\.?S\b|\bI\.?R\.?C\.?C\.?S\b|"
    r"agenzia (?:spaziale|italiana del farmaco)|area science park|"
    r"stazione zoologica|fondazione (?:bruno kessler|toscana|stella maris)",
    re.I,
)

# Riconoscimento della sede dal nome dell'ente o dal titolo.
_CITTA = re.compile(
    r"\b(" + "|".join(
        re.escape(c) for c in sorted(geo.PROVINCE, key=len, reverse=True)
    ) + r"|pontedera|cascina|navacchio|calambrone|empoli|prato|viareggio|carrara|massa)\b",
    re.I,
)


def _fascicoli_recenti(giorni):
    """Ricava (data, numero) dei fascicoli citati nel feed RSS piu' recente."""
    try:
        xml = get(RSS).decode("utf-8", "replace")
    except Exception:
        return []
    fascicoli = []
    for m in re.finditer(r"/eli/gu/(\d{4})/(\d{2})/(\d{2})/(\d+)/S4", xml):
        anno, mese, giorno, numero = m.groups()
        fascicoli.append((f"{anno}-{mese}-{giorno}", numero))
    # dal link del canale ricavo l'ultimo numero e risalgo a ritroso di N fascicoli
    if not fascicoli:
        return []
    return list(dict.fromkeys(fascicoli))[:max(1, giorni // 3)]


def _voci_sommario(data, numero):
    url = SOMMARIO.format(data=data, numero=numero)
    try:
        html = get(url).decode("utf-8", "replace")
    except Exception:
        return []
    voci = []
    for m in re.finditer(
        r'<a[^>]+href="(/atto/concorsi/caricaDettaglioAtto/originario\?[^"]+)"[^>]*>(.*?)</a>',
        html,
        re.S,
    ):
        href, testo = m.groups()
        testo = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", testo))).strip()
        if len(testo) > 25:
            voci.append(("https://www.gazzettaufficiale.it" + unescape(href), testo))
    return voci


def scarica(raggio_km, giorni=30):
    oggi = date.today()
    limite = oggi - timedelta(days=giorni)
    risultati = []
    visti = set()

    for data, numero in _fascicoli_recenti(giorni):
        try:
            if date.fromisoformat(data) < limite:
                continue
        except ValueError:
            continue
        for url, titolo in _voci_sommario(data, numero):
            if url in visti or not ENTI_INTERESSE.search(titolo):
                continue
            visti.add(url)

            m = _CITTA.search(titolo)
            provincia, km, ambito, sede = None, None, "nazionale", "Sede da verificare"
            if m:
                nome = m.group(1).title()
                nome = {"Pontedera": "Pisa", "Cascina": "Pisa", "Navacchio": "Pisa",
                        "Calambrone": "Pisa", "Empoli": "Firenze", "Viareggio": "Lucca",
                        "Carrara": "Massa-Carrara", "Massa": "Massa-Carrara"}.get(nome, nome)
                km = geo.distanza_provincia(nome)
                if km is not None:
                    provincia, sede = nome, nome
                    ambito = "provincia" if km <= raggio_km else "fuori"

            scad = re.search(r"scad(?:enza)?\.?\s*(\d{1,2}\s+\w+\s+\d{4})", titolo, re.I)

            risultati.append({
                "id": "gu:" + re.sub(r"\W+", "", url)[-40:],
                "fonte": "Gazzetta Ufficiale",
                "titolo": titolo,
                "figura": "",
                "ente": titolo.split(" - ")[0][:120],
                "descrizione": "",
                "descrizione_completa": "",
                "url": url,
                "pubblicazione": data + "T00:00:00Z",
                "scadenza": None,
                "scadenza_testo": scad.group(1) if scad else None,
                "stato": "Aperto",
                "posti": None,
                "procedura": None,
                "sede": sede,
                "provincia": provincia,
                "km": km,
                "ambito": ambito,
            })

    return risultati
