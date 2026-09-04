# Job Tracker — Pisa 150 km

Sito statico che raccoglie ogni giorno bandi, concorsi e posizioni entro 150 km da Pisa
e li ordina in base a un profilo di competenze ricavato dal CV (PhD in AI, ingegneria
clinica e biomedica, computer vision su imaging medicale, elaborazione di segnali).

Nessun server, nessun database, nessuna dipendenza esterna: un workflow di GitHub Actions
genera `docs/data/jobs.json` e GitHub Pages serve la cartella `docs/`.

## Cosa fa

- **Raccoglie** da InPA (Portale del reclutamento), dalla Gazzetta Ufficiale 4ª Serie
  Speciale e — se configuri la chiave — da Adzuna per il settore privato.
- **Filtra per distanza**: haversine da Pisa al capoluogo di provincia, soglia 150 km.
  Quando il bando indica solo la regione, prova a dedurre il comune dal nome dell'ente.
- **Assegna un punteggio** con le regole in `scripts/profile.py`: somma parole chiave
  pertinenti e sottrae quelle che rendono un bando inaccessibile (mobilità volontaria,
  stabilizzazioni, interpelli, categorie protette) o fuori profilo.
- **Verifica la classe di laurea**: scarica il PDF di ogni bando e controlla se
  **LM-21 Ingegneria biomedica** è fra le classi ammesse. I bandi che ti escludono
  sono nascosti per impostazione predefinita. Vedi *Il filtro LM-21* più sotto.
- **Mostra** tre fasce — alta corrispondenza, buona, da valutare — con filtri per ambito,
  provincia, distanza e scadenza.
- **Traccia le candidature**: ⭐ salvato, ✅ candidato, ✕ scartato, salvati nel browser
  (`localStorage`), non su GitHub.

## Pubblicarlo su GitHub Pages

1. Crea un repository **pubblico** su GitHub, ad esempio `jobtracker`.
   (Con un account gratuito, Pages funziona solo su repository pubblici.)

2. Dalla cartella del progetto:

   ```bash
   git init -b main
   git add .
   git commit -m "Job tracker Pisa 150 km"
   git remote add origin https://github.com/TUO-UTENTE/jobtracker.git
   git push -u origin main
   ```

3. Su GitHub: **Settings → Pages**. In *Source* scegli `Deploy from a branch`,
   in *Branch* seleziona `main` e la cartella **`/docs`**. Salva.

4. Su GitHub: **Settings → Actions → General**, sezione *Workflow permissions*,
   seleziona **Read and write permissions**. Serve perché il workflow scriva
   `docs/data/jobs.json` nel repository.

5. Vai su **Actions → Aggiorna bandi → Run workflow** per il primo giro.

Dopo un paio di minuti il sito è su `https://TUO-UTENTE.github.io/jobtracker/`.
[https://Gnazio.github.io/jobtracker/docs/](https://gnazio.github.io/Jobtracker/docs/)
Da lì in poi si aggiorna da solo ogni mattina alle 6.

## Lavorarci in locale

```bash
python scripts/build.py
python -m http.server 8000 --directory docs
```

Poi apri <http://localhost:8000>. Serve un server: aprendo `index.html` con doppio clic
il browser blocca la lettura di `jobs.json`.

Se un antivirus o un proxy intercetta il TLS e Python rifiuta i certificati:

```bash
JOBTRACKER_INSECURE=1 python scripts/build.py
```

Su GitHub Actions il problema non si presenta e la verifica resta attiva.

## Tararlo

| Cosa vuoi cambiare | Dove |
| --- | --- |
| Parole chiave e pesi, soglie delle fasce | `scripts/profile.py` |
| Classi di laurea possedute | `CLASSI_POSSEDUTE` in `scripts/requisiti.py` |
| Raggio in km | `RAGGIO_KM` in `scripts/build.py` |
| Province e distanze | `scripts/geo.py` |
| Enti e aziende della lista curata | `data/curated.json` |
| Orario dell'aggiornamento | `.github/workflows/update.yml` |

Se aggiungi parole chiave, rilancia `python scripts/build.py` e controlla cosa entra:
il modo più veloce per capire se un peso è troppo alto è guardare la fascia
"da valutare".

## Attivare Adzuna (annunci privati)

InPA e la Gazzetta coprono solo la pubblica amministrazione. Per il privato serve
Adzuna: è l'unico aggregatore con API ufficiale, gratuita e con ricerca per raggio
che copra bene l'Italia.

1. Registrati su <https://developer.adzuna.com/> e prendi `Application ID` e `Application Key`.
2. Su GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
   Crea `ADZUNA_APP_ID` e `ADZUNA_APP_KEY`.
3. Lancia il workflow. Senza le chiavi la fonte viene semplicemente saltata.

In locale:

```bash
ADZUNA_APP_ID=xxx ADZUNA_APP_KEY=yyy python scripts/build.py
```

Le query cercate sono in `QUERY` dentro `scripts/sources/adzuna.py`.

**Perché non gli altri**: LinkedIn, Indeed e InfoJobs vietano l'uso automatizzato nei
termini di servizio e lo bloccano attivamente. Le API dei gestionali di recruiting
(Greenhouse, Lever, Workable, Recruitee) sono pulite, ma nessuna delle aziende target
— Esaote, Dedalus, IIT, Datalogic, Kedrion, ION, Zerynth — le usa: hanno portali
interni o SAP/Workday, senza endpoint pubblici. Verificato, non supposto.

## Il filtro LM-21

Nei concorsi pubblici le classi di laurea ammesse sono tassative: se la tua non è
elencata, la domanda è inammissibile a prescindere dall'attinenza del profilo.

Le classi non compaiono nell'API di InPA, stanno nel PDF del bando. `scripts/requisiti.py`
lo scarica da `portale.inpa.gov.it/api/media/{id}`, isola la sezione dei requisiti e
riconosce tre forme:

1. **codici di classe** (`LM-21`, `26/S`) — attenzione ai trattini: i PDF usano
   indifferentemente `-`, `–`, `—` e persino il segno meno matematico `−`;
2. **nomi dei corsi per esteso** ("Diploma di laurea in Medicina e Chirurgia");
3. **nessun vincolo** ("laurea magistrale ai sensi del D.M. 270/2004").

Verdetti: `ammesso`, `escluso`, `ignoto`. Gli esclusi restano nel JSON ma la pagina
li nasconde, e mostra sempre quali classi ha trovato, così il controllo finale resta tuo.

I risultati stanno in `data/requisiti_cache.json`, indicizzati per id del PDF: ogni
bando si legge una volta sola. Cancella il file per rianalizzare tutto.

**Limite noto**: una parte dei bandi resta `ignoto`, perché il PDF è una scansione senza
livello di testo, non è allegato, o i requisiti sono in una tabella che l'estrattore
non ricompone. Quei bandi vanno aperti a mano.

## Aggiungere una fonte

Ogni fonte è un modulo in `scripts/sources/` che espone `scarica(raggio_km)` e
restituisce una lista di dizionari con almeno: `id`, `fonte`, `titolo`, `ente`, `url`,
`sede`, `provincia`, `km`, `ambito`, `scadenza`. Poi aggiungila alla tupla in
`raccogli()` dentro `scripts/build.py`.

## Limiti da tenere presenti

- Le distanze sono **in linea d'aria**, non stradali: 150 km in linea d'aria sono
  circa 150–190 km di strada.
- Il punteggio è un aiuto alla lettura, non un verdetto. **Apri sempre il bando**:
  requisiti di accesso, riserve di posti e scadenze reali stanno solo lì.
- I bandi marcati "verifica la sede nel bando" sono nazionali o regionali senza
  provincia: la sede effettiva va letta nel testo.
- La Gazzetta Ufficiale espone via RSS solo il fascicolo più recente. Il build tiene
  in memoria i suoi annunci per 45 giorni, quindi la copertura si costruisce nel tempo:
  i primi giorni vedrai pochi risultati da questa fonte.
- InPA è la fonte per la PA. Le aziende private non ci sono: per quelle serve la
  scheda **Enti da contattare**.
