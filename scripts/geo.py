"""Geografia: distanza in linea d'aria da Pisa e mappatura sede -> provincia.

Le distanze sono calcolate con la formula dell'emisenoverso (haversine) fra Pisa
e il capoluogo di provincia. Sono distanze in linea d'aria, non stradali: un
raggio di 150 km in linea d'aria corrisponde grosso modo a 150-190 km di strada.
Se preferisci un criterio piu' stretto, abbassa RAGGIO_KM in build.py.
"""

import re
from math import asin, cos, radians, sin, sqrt

PISA = (43.7167, 10.4000)

# capoluogo -> (lat, lon, regione). Coperte le regioni che hanno almeno una
# provincia potenzialmente entro il raggio; il filtro sul raggio fa il resto.
PROVINCE = {
    # Toscana
    "Pisa": (43.7167, 10.4000, "Toscana"),
    "Livorno": (43.5486, 10.3106, "Toscana"),
    "Lucca": (43.8430, 10.5079, "Toscana"),
    "Massa-Carrara": (44.0355, 10.1414, "Toscana"),
    "Pistoia": (43.9333, 10.9167, "Toscana"),
    "Prato": (43.8800, 11.0967, "Toscana"),
    "Firenze": (43.7696, 11.2558, "Toscana"),
    "Siena": (43.3188, 11.3308, "Toscana"),
    "Arezzo": (43.4633, 11.8797, "Toscana"),
    "Grosseto": (42.7635, 11.1130, "Toscana"),
    # Liguria
    "La Spezia": (44.1024, 9.8241, "Liguria"),
    "Genova": (44.4056, 8.9463, "Liguria"),
    "Savona": (44.3080, 8.4810, "Liguria"),
    "Imperia": (43.8894, 8.0384, "Liguria"),
    # Emilia-Romagna
    "Parma": (44.8015, 10.3279, "Emilia Romagna"),
    "Reggio Emilia": (44.6983, 10.6310, "Emilia Romagna"),
    "Modena": (44.6471, 10.9252, "Emilia Romagna"),
    "Bologna": (44.4949, 11.3426, "Emilia Romagna"),
    "Ferrara": (44.8378, 11.6197, "Emilia Romagna"),
    "Ravenna": (44.4184, 12.2035, "Emilia Romagna"),
    "Forli'-Cesena": (44.2226, 12.0407, "Emilia Romagna"),
    "Rimini": (44.0678, 12.5695, "Emilia Romagna"),
    "Piacenza": (45.0526, 9.6930, "Emilia Romagna"),
    # Umbria (fuori raggio, tenute per completezza del filtro)
    "Perugia": (43.1107, 12.3908, "Umbria"),
    "Terni": (42.5636, 12.6427, "Umbria"),
}

# Capoluoghi di regione, usati quando il bando indica solo la regione.
CAPOLUOGHI_REGIONE = {
    "Toscana": "Firenze",
    "Liguria": "Genova",
    "Emilia Romagna": "Bologna",
    "Emilia-Romagna": "Bologna",
    "Umbria": "Perugia",
}

# InPA scrive alcune province in forme diverse da quelle qui sopra.
ALIAS = {
    "Massa Carrara": "Massa-Carrara",
    "Forli-Cesena": "Forli'-Cesena",
    "Forlì-Cesena": "Forli'-Cesena",
    "Forli'-Cesena": "Forli'-Cesena",
    "Reggio nell'Emilia": "Reggio Emilia",
    "La Spezia": "La Spezia",
    "Emilia-Romagna": "Emilia Romagna",
}


# Comuni non capoluogo ricorrenti nei bandi, ricondotti alla loro provincia.
COMUNI = {
    "pontedera": "Pisa", "cascina": "Pisa", "navacchio": "Pisa", "calambrone": "Pisa",
    "san giuliano terme": "Pisa", "pontasserchio": "Pisa", "volterra": "Pisa",
    "empoli": "Firenze", "sesto fiorentino": "Firenze", "scandicci": "Firenze",
    "calenzano": "Firenze", "campi bisenzio": "Firenze", "figline": "Firenze",
    "viareggio": "Lucca", "castelnuovo di garfagnana": "Lucca", "capannori": "Lucca",
    "carrara": "Massa-Carrara", "massa": "Massa-Carrara", "aulla": "Massa-Carrara",
    "piombino": "Livorno", "cecina": "Livorno", "rosignano": "Livorno", "portoferraio": "Livorno",
    "montecatini": "Pistoia", "pescia": "Pistoia", "quarrata": "Pistoia",
    "poggibonsi": "Siena", "montepulciano": "Siena", "colle di val d'elsa": "Siena",
    "montevarchi": "Arezzo", "cortona": "Arezzo", "sansepolcro": "Arezzo",
    "follonica": "Grosseto", "orbetello": "Grosseto",
    "sarzana": "La Spezia", "lerici": "La Spezia",
    "sestri levante": "Genova", "rapallo": "Genova", "chiavari": "Genova",
    "casalecchio": "Bologna", "imola": "Bologna", "san lazzaro di savena": "Bologna",
    "carpi": "Modena", "sassuolo": "Modena", "vignola": "Modena",
    "fidenza": "Parma", "salsomaggiore": "Parma",
    "scandiano": "Reggio Emilia", "correggio": "Reggio Emilia",
    "cesena": "Forli'-Cesena", "forli": "Forli'-Cesena", "forlì": "Forli'-Cesena",
    "faenza": "Ravenna", "lugo": "Ravenna",
}

_RX_LUOGO = None


def citta_da_testo(*testi):
    """Cerca un capoluogo o un comune noto dentro titolo/ente di un bando.

    Serve quando il bando indica solo la regione: il nome dell'ente
    ('Comune di Ravenna', 'Universita' di Pisa') di solito basta.
    """
    global _RX_LUOGO
    if _RX_LUOGO is None:
        nomi = sorted(
            list(PROVINCE) + list(COMUNI), key=len, reverse=True
        )
        _RX_LUOGO = re.compile(
            r"\b(" + "|".join(re.escape(n) for n in nomi) + r")\b", re.I
        )
    testo = " ".join(t for t in testi if t)
    for m in _RX_LUOGO.finditer(testo):
        trovato = m.group(1)
        prov = COMUNI.get(trovato.lower())
        if prov is None:
            for p in PROVINCE:
                if p.lower() == trovato.lower():
                    prov = p
                    break
        if prov:
            return prov
    return None


def haversine(a, b):
    """Distanza in km fra due coppie (lat, lon)."""
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def normalizza(nome):
    nome = (nome or "").strip()
    return ALIAS.get(nome, nome)


def distanza_provincia(nome):
    """km da Pisa al capoluogo della provincia, o None se sconosciuta."""
    p = PROVINCE.get(normalizza(nome))
    if not p:
        return None
    return round(haversine(PISA, (p[0], p[1])))


def regioni_entro(raggio_km):
    """Regioni con almeno una provincia entro il raggio: le sole da interrogare."""
    out = []
    for _, (lat, lon, reg) in PROVINCE.items():
        if haversine(PISA, (lat, lon)) <= raggio_km and reg not in out:
            out.append(reg)
    return out


def risolvi_sedi(sedi, raggio_km):
    """Interpreta la lista `sedi` di un bando InPA.

    Restituisce (etichetta, provincia, km, ambito) dove ambito e' uno fra
    'provincia', 'regione', 'nazionale', 'fuori'. `km` e' None per i bandi
    nazionali, che restano validi perche' la sede va letta nel testo del bando.
    """
    sedi = [normalizza(s) for s in (sedi or []) if s]
    if not sedi:
        return ("Sede non indicata", None, None, "nazionale")

    # 1) match diretto su provincia: prendo la piu' vicina a Pisa.
    # I nomi di regione non compaiono in PROVINCE, quindi non interferiscono;
    # una sede come ['Toscana', 'Firenze'] risolve correttamente su Firenze.
    migliori = [(distanza_provincia(s), s) for s in sedi if s in PROVINCE]
    if migliori:
        km, prov = min(migliori)
        if km <= raggio_km:
            return (prov, prov, km, "provincia")
        return (prov, prov, km, "fuori")

    # 2) solo regione indicata
    for s in sedi:
        cap = CAPOLUOGHI_REGIONE.get(s)
        if cap:
            km = distanza_provincia(cap)
            if km is not None and km <= raggio_km:
                return (f"{s} (provincia da verificare)", None, km, "regione")
            return (s, None, km, "fuori")

    if any(s.lower() == "nazionale" for s in sedi):
        return ("Nazionale", None, None, "nazionale")

    return (", ".join(sedi[:2]), None, None, "fuori")
