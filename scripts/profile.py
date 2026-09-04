"""Profilo di matching derivato dal CV di Giacomo Ignesti.

Ogni regola e' (regex, punteggio, tag). Il punteggio di un bando e' la somma
delle regole che scattano su titolo + figura ricercata + ente + descrizione.
I punteggi negativi servono a scartare i bandi strutturalmente inaccessibili
(mobilita' interna, stabilizzazioni, profili non attinenti).

Per tarare il sito basta modificare questo file: e' l'unico posto dove e'
codificato "cosa e' adatto a me".
"""

import re

# ---------------------------------------------------------------------------
# Regole positive
# ---------------------------------------------------------------------------
POSITIVE = [
    # --- Ricerca: il canale principale --------------------------------------
    (r"\bricercator", 34, "ricerca"),
    (r"\bassegn\w* di ricerca|\bassegnist", 34, "ricerca"),
    (r"\btecnolog[oi]\b", 26, "ricerca"),
    (r"\bborsa di (studio|ricerca)|\bborsist", 20, "ricerca"),
    (r"\bpost[- ]?doc", 26, "ricerca"),
    (r"\bR\.?T\.?[DT]\b|\bricercatore a tempo determinato|\btenure track", 30, "ricerca"),
    (r"\bprofessore (associato|ordinario)|\bprofessor[ei] di II fascia", 18, "ricerca"),
    (r"\bIII livello|\bII livello professionale|\bprimo ricercator", 22, "ricerca"),
    (r"\bcollaborator\w+ tecnic\w+ (?:enti di ricerca|E\.?R\.?)|\bC\.?T\.?E\.?R\b", 18, "ricerca"),
    (r"\bdottorat|\bPhD\b", 14, "ricerca"),
    (r"\bricerca sanitaria\b", 26, "ricerca"),

    # --- Enti di ricerca e atenei nel raggio --------------------------------
    (r"consiglio nazionale delle ricerche|\bC\.?N\.?R\.?\b", 22, "ente-ricerca"),
    (r"scuola superiore sant'?anna|scuola normale superiore|\bIMT\b.*lucca", 22, "ente-ricerca"),
    (r"universit[aà] di pisa|universit[aà] degli studi di (pisa|firenze|siena|bologna|genova|parma|modena)", 18, "ente-ricerca"),
    (r"\bI\.?N\.?F\.?N\.?\b|\bE\.?N\.?E\.?A\.?\b|istituto italiano di tecnologia|\bI\.?I\.?T\.?\b", 18, "ente-ricerca"),
    (r"\bI\.?R\.?C\.?C\.?S\.?\b|stella maris|monasterio|istituto di fisiologia clinica", 18, "ente-ricerca"),
    (r"\bC\.?I\.?N\.?E\.?C\.?A\.?\b|\bC\.?N\.?I\.?T\.?\b", 16, "ente-ricerca"),

    # --- Intelligenza artificiale, dati, visione ----------------------------
    (r"intelligenza artificiale|\bA\.?I\.?\b(?! *sensi)|artificial intelligence", 30, "ai-ml"),
    (r"machine learning|apprendimento automatico|deep learning|apprendimento profondo", 32, "ai-ml"),
    (r"computer vision|visione artificiale|elaborazione (?:di )?immagin|image processing", 32, "ai-ml"),
    (r"data scien|scienza dei dati|\bbig data\b|data analy|analisi dei dati", 24, "ai-ml"),
    (r"elaborazione (?:di |dei )?segnal|signal processing", 26, "ai-ml"),
    (r"\bstatistic|biostatistic", 16, "ai-ml"),
    (r"reti neural|neural network|modelli predittiv", 24, "ai-ml"),
    (r"\bH\.?P\.?C\.?\b|calcolo ad alte prestazioni|supercalcolo|\bG\.?P\.?U\.?\b", 18, "ai-ml"),
    (r"geospazial|telerilevamento|remote sensing|\bG\.?I\.?S\.?\b|satellitar", 16, "ai-ml"),

    # --- Biomedico e ingegneria clinica -------------------------------------
    (r"bioingegner|ingegneria biomedic|ingegner\w* clinic|biomedical engineer", 32, "biomedico"),
    (r"dispositiv\w+ medic|tecnologie biomedich|elettromedical", 24, "biomedico"),
    (r"imaging (?:medic|diagnostic|biomedic)|diagnostica per immagini|ecograf|ultrasound|risonanza magnetica", 30, "biomedico"),
    (r"telemedicina|teleassistenza|telemonitoraggio|\be[- ]?health\b|sanit[aà] digitale", 28, "biomedico"),
    (r"informatica medica|health informatics|fascicolo sanitario", 22, "biomedico"),
    (r"fisica sanitaria|fisic[oa] medic", 14, "biomedico"),
    (r"segnali (?:bio|fisiolog)|\bE\.?C\.?G\.?\b|\bE\.?E\.?G\.?\b|variabilit[aà] della frequenza cardiaca", 24, "biomedico"),

    # --- Sanita' pubblica ---------------------------------------------------
    (r"\bE\.?S\.?T\.?A\.?R\.?\b|azienda ospedalier|azienda usl|\bA\.?O\.?U\.?\b|usl toscana", 14, "sanita"),
    (r"collaborator\w+ professional\w+ (?:sanitari|di ricerca)", 18, "sanita"),
    (r"dirigente (?:ingegnere|fisico|analista|informatic)", 22, "sanita"),

    # --- Informatica e sviluppo --------------------------------------------
    (r"ingegner\w* (?:informatic|elettronic|dell'informazione)", 24, "ict"),
    (r"\bpython\b|\bpytorch\b|tensorflow|\breact\b|\bangular\b|\bflutter\b", 22, "ict"),
    (r"sviluppator|software (?:engineer|developer)|programmator|full[- ]?stack", 20, "ict"),
    (r"funzionar\w+ (?:tecnic|informatic)|area dei funzionari.*(?:tecnic|informatic|scientific)", 18, "ict"),
    (r"transizione digitale|sistemi informativ|\bI\.?C\.?T\.?\b", 14, "ict"),
    (r"settore scientifico[- ]tecnologico", 18, "ict"),

    # --- Segnali di livello coerente col titolo di studio -------------------
    (r"laurea magistrale|laurea specialistica|titolo di dottore di ricerca", 10, "requisiti"),
]

# ---------------------------------------------------------------------------
# Regole negative
# ---------------------------------------------------------------------------
# Soglia: sotto MIN_SCORE il bando non entra nel sito.
NEGATIVE = [
    # Procedure a cui non puoi accedere: riservate a chi e' gia' dipendente
    # pubblico a tempo indeterminato o precario storico di quell'ente.
    (r"mobilit[aà] (?:volontaria|esterna|interna|compartimentale)|\bart\.? ?30 del d\.?lgs", -200, "non-accessibile"),
    (r"stabilizzazion|\bart\.? ?20 del d\.?lgs 75|personale precari", -200, "non-accessibile"),
    (r"\binterpello\b|progressione (?:verticale|fra le aree)|passaggio diretto", -200, "non-accessibile"),
    (r"riservat[oa] (?:esclusivamente )?(?:ai|al|alle|agli) (?:dipendenti|personale)", -200, "non-accessibile"),
    (r"categorie protette|\bL\.? ?68/99|art\.? ?18 legge 68", -200, "non-accessibile"),
    (r"scorrimento (?:di )?graduatori", -60, "non-accessibile"),

    # Profili fuori perimetro
    (r"\boperai[oe]\b|esecutor|\bautist|necrofor|cantonier|giardinier|cuoc[oh]|addett[oa] alle pulizie", -200, "fuori-profilo"),
    (r"assistente social|educator\w* professional|insegnant|maestr[oa]|docente (?:di scuola|AFAM)|\bA\.?F\.?A\.?M\.?\b", -200, "fuori-profilo"),
    # Concorsi per la scuola: enormi per numero, mai pertinenti. Non dicono
    # "insegnante", si riconoscono dalla classe di concorso e dal MIM/USR.
    (r"classe di concorso|concorso (?:ordinario )?(?:per la )?secondaria|scuola (?:secondaria|primaria|dell'infanzia)|"
     r"personale (?:docente|A\.?T\.?A\.?)|ufficio scolastico|\bU\.?S\.?R\.?\b per (?:il|la|l')|"
     r"graduatorie provinciali di supplenza|\bD\.?D\.?G\.?\s*\d+/\d{4}|\bD\.?M\.?\s*20[56]/2023", -200, "fuori-profilo"),
    (r"infermier|ostetric|fisioterapist|logopedist|tecnico di radiologia|\bO\.?S\.?S\.?\b|operatore socio[- ]sanitario", -200, "fuori-profilo"),
    (r"\bmedic[oi] (?:chirurgo|specialista|veterinari)|dirigente medico|farmacist|biolog[oa] (?:sanitari|nutrizionist)", -160, "fuori-profilo"),
    (r"avvocat|magistrat|notai|procurator|contabil|ragionier|economo|tributar", -200, "fuori-profilo"),
    (r"\bgeometr|architett|agronom|forestal|geolog|archeolog|bibliotecari|archivist|restaurator", -160, "fuori-profilo"),
    (r"agente di polizia|polizia (?:locale|municipale|penitenziaria)|vigil[ei] (?:urbano|del fuoco)|carabinier|guardia di finanza|esercito|aeronautica|marina militar|allievi? (?:ufficial|marescial)", -200, "fuori-profilo"),
    (r"\bcappellan|\bsacerdot|\bconsigliere di parit", -200, "fuori-profilo"),

    # Livello di studio troppo basso -> stipendio e mansioni non coerenti
    (r"diploma di (?:istruzione secondaria di primo grado|scuola media)|licenza media|scuola dell'obbligo", -120, "fuori-profilo"),
    (r"area degli operator(?:i|e) esperti\b", -120, "fuori-profilo"),

    # Incarichi apicali politici/amministrativi
    (r"direttore general|segretario (?:comunale|general)|direttore amministrativ|nucleo di valutazione|revisore dei conti|organismo indipendente", -140, "fuori-profilo"),
]

MIN_SCORE = 24
SOGLIA_ALTA = 70
SOGLIA_BUONA = 40

_POS = [(re.compile(p, re.I), s, t) for p, s, t in POSITIVE]
_NEG = [(re.compile(p, re.I), s, t) for p, s, t in NEGATIVE]


def valuta(*testi):
    """Restituisce (punteggio, tag, motivi) per i testi passati."""
    testo = " \n ".join(t for t in testi if t)
    punteggio = 0
    tag = []
    motivi = []
    for rx, peso, t in _POS:
        m = rx.search(testo)
        if m:
            punteggio += peso
            if t not in tag:
                tag.append(t)
            motivi.append(m.group(0).strip().lower()[:40])
    for rx, peso, t in _NEG:
        m = rx.search(testo)
        if m:
            punteggio += peso
            if t not in tag:
                tag.append(t)
    return punteggio, tag, motivi[:6]


def fascia(punteggio):
    if punteggio >= SOGLIA_ALTA:
        return "alta"
    if punteggio >= SOGLIA_BUONA:
        return "buona"
    return "possibile"
