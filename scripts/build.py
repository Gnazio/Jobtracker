"""Genera docs/data/jobs.json a partire dalle fonti automatiche + lista curata.

Uso:
    python scripts/build.py                # aggiorna docs/data/jobs.json
    JOBTRACKER_INSECURE=1 python scripts/build.py    # se il TLS locale e' intercettato

Il file prodotto e' l'unico input del sito: docs/ e' interamente statico.
"""

import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "scripts"))

import profile as prof  # noqa: E402
import check_links  # noqa: E402
from sources import gazzetta, inpa  # noqa: E402

RAGGIO_KM = 150
USCITA = RADICE / "docs" / "data" / "jobs.json"
CURATI = RADICE / "data" / "curated.json"


def _scaduto(iso):
    if not iso:
        return False
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return False
    return d < datetime.now(timezone.utc)


def _giorni_rimasti(iso):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d - datetime.now(timezone.utc)).days


def raccogli():
    annunci, errori = [], []

    for nome, fn in (("InPA", lambda: inpa.scarica(RAGGIO_KM)),
                     ("Gazzetta Ufficiale", lambda: gazzetta.scarica(RAGGIO_KM))):
        try:
            trovati = fn()
            annunci.extend(trovati)
            print(f"  {nome}: {len(trovati)} annunci grezzi", file=sys.stderr)
        except Exception as e:
            errori.append(f"{nome}: {type(e).__name__}: {e}")
            print(f"  {nome} FALLITA: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    return annunci, errori


def unisci_storico(nuovi, giorni=45):
    """Riporta dentro gli annunci di Gazzetta gia' visti nei giri precedenti.

    Il feed RSS della GU espone solo il fascicolo piu' recente: senza questo
    innesto ogni bando sparirebbe dal sito il giorno dopo essere apparso.
    InPA invece e' completa a ogni giro e non va innestata, altrimenti i bandi
    chiusi resterebbero in pagina per sempre.
    """
    if not USCITA.exists():
        return nuovi
    try:
        vecchi = json.loads(USCITA.read_text(encoding="utf-8")).get("annunci", [])
    except (json.JSONDecodeError, OSError):
        return nuovi

    presenti = {a["id"] for a in nuovi}
    limite = datetime.now(timezone.utc) - timedelta(days=giorni)
    recuperati = 0

    for v in vecchi:
        if not v.get("id", "").startswith("gu:") or v["id"] in presenti:
            continue
        try:
            pub = datetime.fromisoformat((v.get("pubblicazione") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if pub >= limite and not _scaduto(v.get("scadenza")):
            nuovi.append(v)
            recuperati += 1

    if recuperati:
        print(f"  Gazzetta: {recuperati} annunci recuperati dai giri precedenti", file=sys.stderr)
    return nuovi


def filtra_e_valuta(annunci):
    tenuti, scartati_geo, scartati_score = [], 0, 0

    for a in annunci:
        if a.get("ambito") == "fuori":
            scartati_geo += 1
            continue
        if _scaduto(a.get("scadenza")):
            continue

        punteggio, tag, motivi = prof.valuta(
            a.get("titolo"), a.get("figura"), a.get("ente"),
            a.get("descrizione"), a.get("descrizione_completa"),
        )
        if punteggio < prof.MIN_SCORE:
            scartati_score += 1
            continue

        # Un bando nazionale vale solo se il contenuto e' molto pertinente:
        # la sede va comunque verificata a mano nel testo.
        if a.get("ambito") == "nazionale" and punteggio < prof.SOGLIA_BUONA:
            scartati_geo += 1
            continue

        a = dict(a)
        a.pop("descrizione_completa", None)
        a["punteggio"] = punteggio
        a["tag"] = [t for t in tag if t not in ("non-accessibile", "fuori-profilo")]
        a["motivi"] = motivi
        a["fascia"] = prof.fascia(punteggio)
        a["giorni_rimasti"] = _giorni_rimasti(a.get("scadenza"))
        tenuti.append(a)

    tenuti.sort(key=lambda x: (-x["punteggio"], x.get("km") if x.get("km") is not None else 999))
    return tenuti, scartati_geo, scartati_score


def carica_curati():
    if not CURATI.exists():
        return []
    voci = json.loads(CURATI.read_text(encoding="utf-8"))
    try:
        check_links.verifica(voci)
    except Exception as e:   # il controllo link non deve mai bloccare il build
        print(f"  Controllo link saltato: {e}", file=sys.stderr)
    for v in voci:
        v.setdefault("fonte", "Lista curata")
        v["km"] = v.get("km", None)
        if v.get("provincia") and v["km"] is None:
            import geo
            v["km"] = geo.distanza_provincia(v["provincia"])
    return voci


def main():
    print("Raccolta annunci...", file=sys.stderr)
    grezzi, errori = raccogli()
    # Se nessuna fonte ha risposto non sovrascrivo il file buono con uno vuoto.
    if not grezzi:
        sys.exit("Nessuna fonte ha risposto: jobs.json lasciato invariato.")

    grezzi = unisci_storico(grezzi)
    annunci, geo_out, score_out = filtra_e_valuta(grezzi)
    curati = carica_curati()

    conteggi = {}
    for a in annunci:
        conteggi[a["fascia"]] = conteggi.get(a["fascia"], 0) + 1

    dati = {
        "aggiornato": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raggio_km": RAGGIO_KM,
        "origine": "Pisa",
        "statistiche": {
            "grezzi": len(grezzi),
            "pubblicati": len(annunci),
            "scartati_distanza": geo_out,
            "scartati_profilo": score_out,
            "per_fascia": conteggi,
        },
        "errori_fonti": errori,
        "annunci": annunci,
        "curati": curati,
    }

    USCITA.parent.mkdir(parents=True, exist_ok=True)
    USCITA.write_text(
        json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        f"\nScritto {USCITA.relative_to(RADICE)}: {len(annunci)} annunci "
        f"({conteggi}) + {len(curati)} voci curate",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
