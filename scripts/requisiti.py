"""Filtro sul titolo di studio: LM-21 Ingegneria biomedica.

Nei concorsi pubblici le classi di laurea ammesse sono tassative: se la tua
classe non e' elencata nel bando sei escluso, per quanto il profilo sia
attinente. Le classi non compaiono quasi mai nella descrizione restituita
dall'API di InPA: stanno nel PDF del bando. Questo modulo scarica il PDF,
ne estrae i codici di classe e li confronta con i titoli posseduti.

Verdetti:
  ammesso  - fra le classi elencate c'e' LM-21 (o un titolo equipollente)
  escluso  - il bando elenca delle classi e LM-21 non e' fra queste
  ignoto   - nel PDF non si trovano codici di classe: requisiti da leggere a mano

Il verdetto 'escluso' non cancella il bando: lo marca. Un PDF puo' elencare
classi per motivi diversi dal requisito d'accesso (allegati, altri profili),
quindi la pagina mostra sempre quali classi ha trovato, cosi' il controllo
finale resta tuo.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_client import get  # noqa: E402

MEDIA = "https://portale.inpa.gov.it/api/media/{}"
CACHE = Path(__file__).resolve().parents[1] / "data" / "requisiti_cache.json"

# --- Titoli posseduti -------------------------------------------------------
# LM-21 Ingegneria biomedica (DM 270/2004).
# 26/S e' la classe specialistica corrispondente del DM 509/1999: le tabelle di
# equiparazione (DM 9 luglio 2009) le rendono equivalenti a ogni effetto.
CLASSI_POSSEDUTE = {"LM-21", "26/S"}

# Alcuni bandi non usano i codici ma il nome del corso.
NOME_TITOLO = re.compile(
    r"ingegneria\s+(?:biomedica|clinica)|biomedical\s+engineering", re.I
)

# Un dottorato non sostituisce la classe di laurea nei concorsi, ma nei bandi
# per assegni, borse e RTT e' spesso il requisito principale e le classi non
# vengono nemmeno elencate.
DOTTORATO = re.compile(
    r"dottorat[oi] di ricerca|titolo di dottore di ricerca|\bph\.?\s?d\b", re.I
)
DOTTORATO_AFFINE = re.compile(
    r"dottorat\w+[^.;]{0,120}(intelligenza artificiale|informatic|ingegneri|"
    r"scienze? dell'informazione|computer science|data science|bioingegner)", re.I
)

# LM-1..LM-92, L-1..L-46, e le vecchie specialistiche NN/S.
#
# Attenzione ai trattini: i PDF dei bandi usano indifferentemente il trattino
# normale, i trattini tipografici e persino il segno meno matematico (U+2212).
# Accettandone uno solo si perde piu' della meta' delle classi.
TRATTINO = "[-‐‑‒–—―−/]"

RX_CLASSE = re.compile(
    rf"\b(LM|LMR|LMG)\s*{TRATTINO}\s*(\d{{1,3}})(?:\s*{TRATTINO}\s*(\d{{2}}))?\b"
    rf"|\bL\s*{TRATTINO}\s*(\d{{1,2}})\b"
    rf"|\b(\d{{1,2}})\s*/\s*S\b",
    re.I,
)


def _normalizza(m):
    if m.group(1):
        base = f"{m.group(1).upper()}-{int(m.group(2))}"
        return f"{base}/{m.group(3)}" if m.group(3) else base
    if m.group(4):
        return f"L-{int(m.group(4))}"
    if m.group(5):
        return f"{int(m.group(5))}/S"
    return None


def estrai_classi(testo):
    """Codici di classe di laurea citati nel testo, normalizzati."""
    trovate = set()
    for m in RX_CLASSE.finditer(testo or ""):
        c = _normalizza(m)
        if c:
            trovate.add(c)
    # Falsi positivi frequenti: 'L-1' dentro sigle, classi oltre il massimo reale.
    pulite = set()
    for c in trovate:
        if c.startswith("LM-"):
            n = int(c.split("-")[1].split("/")[0])
            if 1 <= n <= 92:
                pulite.add(c)
        elif c.startswith("L-"):
            n = int(c[2:])
            if 1 <= n <= 46:
                pulite.add(c)
        else:
            n = int(c.split("/")[0])
            if 1 <= n <= 102:
                pulite.add(c)
    return pulite


# --- Requisiti scritti per esteso ------------------------------------------
# Molti bandi non usano i codici: elencano i corsi per nome, oppure ammettono
# qualunque laurea magistrale. Entrambi i casi vanno riconosciuti, altrimenti
# meta' dei bandi resta "da verificare" e il filtro non serve a niente.

# Da dove cominciano i requisiti: oltre quel punto il PDF parla d'altro
# (allegati, moduli, informativa privacy) e le classi citate non sono requisiti.
RX_INIZIO_REQUISITI = re.compile(
    r"requisiti\s+(?:specifici|di\s+ammissione|di\s+partecipazione|generali)"
    r"|titol[oi]\s+di\s+studio\s+(?:richiest|e\s+profession)"
    r"|per\s+l'ammissione\s+al\s+(?:concorso|la\s+selezione)",
    re.I,
)

# "Laurea magistrale in Ingegneria biomedica", "Diploma di laurea in Biologia"...
RX_NOME_CORSO = re.compile(
    r"(?:diploma\s+di\s+)?laure[ae]"
    r"(?:\s+(?:magistral\w+|specialistic\w+|triennal\w+|di\s+primo\s+livello))?"
    r"\s+in\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\s]{3,58})",
    re.I,
)

# Titoli che valgono come i tuoi.
RX_CORSO_COMPATIBILE = re.compile(
    r"ingegneria\s+(?:biomedica|clinica)|biomedical\s+engineering"
    r"|^ingegneria\s*$|ingegneria\s+(?:tutti|in\s+tutte)",
    re.I,
)

# "Laurea magistrale conseguita ai sensi del D.M. 270/2004" senza altre
# specificazioni: va bene qualunque magistrale.
RX_QUALSIASI = re.compile(
    r"laurea\s+magistrale[^.;]{0,80}(?:D\.?\s?M\.?|decreto)[^.;]{0,40}270"
    r"|laurea\s+(?:magistrale\s+)?in\s+qualsiasi\s+disciplina"
    r"|laurea\s+magistrale\s+in\s+qualunque",
    re.I,
)

RUMORE_NOMI = re.compile(
    r"^(possesso|corso|corsi|una|uno|cui|italia|altri|tale|detta|questione|"
    r"materie|discipline|relazione|conformit|data|essere|oggetto)\b",
    re.I,
)


def _sezione_requisiti(testo, finestra=7000):
    """Ritaglia la parte del bando che contiene i requisiti d'accesso."""
    m = RX_INIZIO_REQUISITI.search(testo or "")
    if not m:
        return testo or ""
    return testo[m.start(): m.start() + finestra]


def _nomi_corsi(sezione):
    nomi = []
    for m in RX_NOME_CORSO.finditer(sezione):
        nome = re.sub(r"\s+", " ", m.group(1)).strip(" ,;.")
        # taglio le code discorsive: "Biologia conseguita ai sensi..."
        nome = re.split(
            r"\b(?:conseguit|equipollent|equiparat|ai sensi|oppure|ovvero|nonch)",
            nome, flags=re.I,
        )[0].strip()
        if 4 <= len(nome) <= 58 and not RUMORE_NOMI.match(nome):
            nomi.append(nome)
    # tolgo i duplicati mantenendo l'ordine
    return list(dict.fromkeys(nomi))[:20]


def analizza_testo(testo):
    """Estrae dal testo del bando tutto cio' che serve a dare un verdetto.

    Le classi si cercano prima nella sezione dei requisiti, che e' la piu'
    affidabile. Molti bandi pero' le mettono altrove - in una tabella dei
    profili, in un allegato in coda - quindi se li' non si trova nulla si
    ripiega sul documento intero: meglio un elenco da controllare a occhio
    che un "da verificare" che non dice niente.
    """
    sezione = _sezione_requisiti(testo)
    classi = estrai_classi(sezione) or estrai_classi(testo)
    nomi = _nomi_corsi(sezione) or _nomi_corsi(testo or "")
    return {
        "classi": sorted(classi),
        "nomi": nomi,
        "qualsiasi_magistrale": bool(RX_QUALSIASI.search(sezione)),
        "nome_titolo": bool(NOME_TITOLO.search(sezione)),
        "dottorato": bool(DOTTORATO.search(sezione)),
        "dottorato_affine": bool(DOTTORATO_AFFINE.search(testo or "")),
    }


def _testo_pdf(dati):
    """Estrae il testo da un PDF. Usa pypdf, con pymupdf come alternativa."""
    import io

    try:
        from pypdf import PdfReader

        lettore = PdfReader(io.BytesIO(dati))
        return "\n".join((p.extract_text() or "") for p in lettore.pages)
    except ImportError:
        pass
    try:
        import fitz

        with fitz.open(stream=dati, filetype="pdf") as d:
            return "\n".join(p.get_text() for p in d)
    except ImportError:
        raise RuntimeError(
            "Serve pypdf per leggere i bandi: pip install -r requirements.txt"
        )


def _carica_cache():
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _salva_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def analizza_pdf(media_id, cache, timeout=45):
    """Scarica e analizza il bando. Il risultato resta in cache per id."""
    if media_id in cache:
        return cache[media_id]

    esito = {"classi": [], "nomi": [], "errore": None}
    try:
        dati = get(MEDIA.format(media_id), timeout=timeout)
        testo = _testo_pdf(dati)
        esito.update(analizza_testo(testo))
        esito["caratteri"] = len(testo)
    except Exception as e:
        esito["errore"] = f"{type(e).__name__}: {e}"

    esito["letto_il"] = date.today().isoformat()
    cache[media_id] = esito
    return esito


def verdetto(esito):
    """Restituisce (verdetto, spiegazione) a partire dall'analisi del PDF."""
    if not esito or esito.get("errore"):
        return "ignoto", "Non sono riuscito a leggere il PDF del bando."

    if esito.get("caratteri", 1) < 400:
        return "ignoto", "Il PDF non contiene testo leggibile (scansione): da verificare a mano."

    classi = set(esito.get("classi") or [])
    magistrali = {c for c in classi if c.startswith("LM") or c.endswith("/S")}
    nomi = esito.get("nomi") or []
    compatibile = [n for n in nomi if RX_CORSO_COMPATIBILE.search(n)]

    # 1) Riscontro esplicito, per codice o per nome del corso.
    if CLASSI_POSSEDUTE & classi:
        return "ammesso", "Il bando elenca LM-21 fra le classi ammesse."
    if compatibile or esito.get("nome_titolo"):
        return "ammesso", f"Il bando ammette {compatibile[0] if compatibile else 'Ingegneria biomedica'}."

    # 2) Nessun vincolo di classe: va bene qualunque laurea magistrale.
    if not magistrali and not nomi and esito.get("qualsiasi_magistrale"):
        return "ammesso", "Nessuna classe richiesta: ammessa qualunque laurea magistrale."
    if not magistrali and not nomi and esito.get("dottorato_affine"):
        return "ammesso", "Nessuna classe elencata: il requisito e' il dottorato di ricerca."

    # 3) Il bando elenca dei titoli e i tuoi non ci sono.
    if magistrali:
        return "escluso", f"Classi ammesse: {', '.join(sorted(magistrali)[:8])}. LM-21 non e' compresa."
    if len(nomi) >= 2:
        return "escluso", f"Titoli richiesti: {'; '.join(nomi[:4])}. Ingegneria biomedica non c'e'."

    # 4) Un solo nome letto, o niente: troppo poco per decidere.
    if nomi:
        return "ignoto", f"Il bando sembra chiedere: {nomi[0]}. Da verificare nel PDF."
    if esito.get("dottorato"):
        return "ignoto", "Nessuna classe elencata; il bando parla di dottorato di ricerca."
    return "ignoto", "Nel PDF non ho trovato i titoli richiesti: da verificare a mano."


def valuta(annunci, max_nuovi=80):
    """Assegna titolo_verdetto / titolo_nota / titolo_classi agli annunci InPA.

    Scarica solo i PDF non ancora in cache, al massimo `max_nuovi` per giro,
    per non allungare troppo il workflow.
    """
    cache = _carica_cache()
    nuovi = 0

    for a in annunci:
        # Il vincolo di classe di laurea esiste solo nei concorsi pubblici.
        if a.get("fonte") not in ("InPA", "Gazzetta Ufficiale"):
            a["titolo_verdetto"] = "privato"
            a["titolo_nota"] = "Datore privato: nessun vincolo di classe di laurea."
            a["titolo_classi"] = []
            continue

        mid = a.get("media_id")
        if not mid:
            a["titolo_verdetto"] = "ignoto"
            a["titolo_nota"] = "Bando senza PDF allegato: requisiti da verificare."
            a["titolo_classi"] = []
            continue

        if mid not in cache:
            if nuovi >= max_nuovi:
                a["titolo_verdetto"] = "ignoto"
                a["titolo_nota"] = "Non ancora analizzato: sara' letto al prossimo giro."
                a["titolo_classi"] = []
                continue
            nuovi += 1

        esito = analizza_pdf(mid, cache)
        v, nota = verdetto(esito)
        a["titolo_verdetto"] = v
        a["titolo_nota"] = nota
        a["titolo_classi"] = esito.get("classi") or []
        a["titolo_nomi"] = esito.get("nomi") or []

    _salva_cache(cache)
    if nuovi:
        print(f"  Requisiti: analizzati {nuovi} nuovi PDF", file=sys.stderr)
    return annunci
