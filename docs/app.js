/* Job Tracker Pisa — logica di visualizzazione.
   Nessuna dipendenza. Legge data/jobs.json e filtra lato client.
   I contrassegni personali stanno in localStorage e non lasciano il browser. */

const CHIAVE = "jobtracker-pisa:stati";
const ETICHETTE = {
  ricerca: "Ricerca",
  "ente-ricerca": "Enti di ricerca",
  "ai-ml": "AI / Machine learning",
  biomedico: "Biomedico",
  sanita: "Sanità",
  ict: "Informatica",
  industria: "Industria",
  requisiti: "Requisiti coerenti",
};

let DATI = { annunci: [], curati: [] };
let stati = caricaStati();
const filtri = {
  testo: "", tag: new Set(), prov: new Set(), km: 150,
  mio: "attivi", scad: "", titolo: "possibili",
};

// Etichette del verdetto sulla classe di laurea. "possibili" non è un verdetto:
// è il filtro predefinito, che tiene ammessi e da-verificare e scarta il resto.
const TITOLO = {
  ammesso: { testo: "LM-21 ammessa", classe: "ok" },
  escluso: { testo: "LM-21 non ammessa", classe: "ko" },
  ignoto: { testo: "Requisiti da verificare", classe: "forse" },
  privato: { testo: "Nessun vincolo di classe", classe: "ok" },
};

/* ---------------------------------------------------------------- stato */
function caricaStati() {
  try { return JSON.parse(localStorage.getItem(CHIAVE)) || {}; }
  catch { return {}; }
}
function salvaStati() {
  try { localStorage.setItem(CHIAVE, JSON.stringify(stati)); }
  catch { /* modalità privata o storage pieno: i filtri continuano a funzionare */ }
}

/* ---------------------------------------------------------------- utilità */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function titoloPulito(t) {
  // I titoli di InPA sono spesso tutti maiuscoli: illeggibili in elenco.
  if (!t) return "";
  const lettere = t.replace(/[^A-Za-zÀ-ÿ]/g, "");
  const maiusc = (lettere.match(/[A-ZÀ-Þ]/g) || []).length;
  if (lettere.length > 12 && maiusc / lettere.length > 0.8) {
    return t.toLowerCase().replace(/(^|[.:;!?]\s+)([a-zà-ÿ])/g, (m, a, b) => a + b.toUpperCase());
  }
  return t;
}

function dataIt(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d) ? null : d.toLocaleDateString("it-IT", { day: "numeric", month: "short", year: "numeric" });
}

/* ---------------------------------------------------------------- filtro */
function passa(a) {
  const s = stati[a.id];
  if (filtri.mio === "attivi" && s === "scartato") return false;
  if (["salvato", "candidato", "scartato"].includes(filtri.mio) && s !== filtri.mio) return false;

  if (filtri.km < 150 && a.km !== null && a.km > filtri.km) return false;
  // Un bando nazionale non ha km: lo nascondo solo se restringo davvero il raggio.
  if (filtri.km < 150 && a.km === null) return false;

  const v = a.titolo_verdetto || "ignoto";
  if (filtri.titolo === "possibili" && v === "escluso") return false;
  if (["ammesso", "escluso", "ignoto"].includes(filtri.titolo) && v !== filtri.titolo) return false;

  if (filtri.tag.size && !(a.tag || []).some((t) => filtri.tag.has(t))) return false;
  if (filtri.prov.size && !filtri.prov.has(a.provincia || "Nazionale")) return false;

  if (filtri.scad) {
    if (a.giorni_rimasti === null || a.giorni_rimasti === undefined) return false;
    if (a.giorni_rimasti > Number(filtri.scad)) return false;
  }

  if (filtri.testo) {
    const campo = [a.titolo, a.ente, a.figura, a.descrizione, a.sede].join(" ").toLowerCase();
    if (!filtri.testo.split(/\s+/).every((p) => campo.includes(p))) return false;
  }
  return true;
}

/* ---------------------------------------------------------------- render */
function scheda(a) {
  const s = stati[a.id];
  const g = a.giorni_rimasti;
  const badge = [];

  if (a.km !== null && a.km !== undefined) {
    badge.push(`<span class="badge km">📍 ${esc(a.sede)}${a.km ? ` · ${a.km} km` : ""}</span>`);
  } else {
    badge.push(`<span class="badge verifica">📍 ${esc(a.sede)} — verifica la sede nel bando</span>`);
  }
  if (g !== null && g !== undefined) {
    badge.push(`<span class="badge tempo${g <= 7 ? " urgente" : ""}">⏳ ${
      g <= 0 ? "scade oggi" : g === 1 ? "1 giorno" : g + " giorni"}</span>`);
  }
  const t = TITOLO[a.titolo_verdetto] || TITOLO.ignoto;
  badge.push(
    `<span class="badge titolo ${t.classe}" title="${esc(a.titolo_nota || "")}">🎓 ${t.testo}</span>`
  );

  (a.tag || []).forEach((x) => {
    if (ETICHETTE[x] && x !== "requisiti") badge.push(`<span class="badge">${esc(ETICHETTE[x])}</span>`);
  });
  badge.push(`<span class="badge fonte">${esc(a.fonte)}</span>`);

  const meta = [];
  if (a.ente) meta.push(`<b>${esc(a.ente)}</b>`);
  if (a.figura) meta.push(esc(a.figura));
  if (a.posti) meta.push(`${a.posti} post${a.posti === 1 ? "o" : "i"}`);
  const scad = dataIt(a.scadenza) || a.scadenza_testo;
  if (scad) meta.push(`scadenza ${esc(scad)}`);

  return `<article class="card${s === "candidato" || s === "scartato" ? " fatto" : ""}">
    <h3><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(titoloPulito(a.titolo))}</a></h3>
    ${meta.length ? `<p class="meta">${meta.join(" · ")}</p>` : ""}
    <div class="badge-riga">${badge.join("")}</div>
    ${a.titolo_nota ? `<p class="requisiti ${t.classe}">${esc(a.titolo_nota)}</p>` : ""}
    <div class="azioni">
      <button data-id="${esc(a.id)}" data-st="salvato"   class="${s === "salvato" ? "on" : ""}"   title="Salva">⭐</button>
      <button data-id="${esc(a.id)}" data-st="candidato" class="${s === "candidato" ? "on" : ""}" title="Mi sono candidato">✅</button>
      <button data-id="${esc(a.id)}" data-st="scartato"  class="${s === "scartato" ? "on" : ""}"  title="Scarta">✕</button>
    </div>
  </article>`;
}

function disegnaBandi() {
  const visibili = DATI.annunci.filter(passa);
  const gruppi = { alta: [], buona: [], possibile: [] };
  visibili.forEach((a) => gruppi[a.fascia]?.push(a));

  const nomi = {
    alta: "Alta corrispondenza",
    buona: "Buona corrispondenza",
    possibile: "Da valutare",
  };

  let html = "";
  for (const f of ["alta", "buona", "possibile"]) {
    if (!gruppi[f].length) continue;
    html += `<h2 class="gruppo"><span class="pallino ${f}"></span>${nomi[f]} (${gruppi[f].length})</h2>`;
    html += gruppi[f].map(scheda).join("");
  }
  if (!html) {
    html = `<p class="vuoto">Nessun bando corrisponde ai filtri.<br>
      Prova ad allargare il raggio o ad azzerare i filtri.</p>`;
  }

  document.getElementById("lista").innerHTML = html;
  const salvati = Object.values(stati).filter((v) => v === "salvato").length;
  document.getElementById("conteggio").textContent =
    `${visibili.length} di ${DATI.annunci.length} bandi` +
    (salvati ? ` · ${salvati} salvat${salvati === 1 ? "o" : "i"}` : "");
}

function disegnaCurati() {
  const v = [...(DATI.curati || [])].sort(
    (a, b) => (a.priorita || 9) - (b.priorita || 9) || (a.km ?? 999) - (b.km ?? 999));

  document.getElementById("lista-curati").innerHTML = v.map((c) => {
    const cerca = `https://www.google.com/search?q=${encodeURIComponent(
      `"${c.nome}" lavora con noi OR bandi OR posizioni aperte`)}`;
    const badge = [
      c.km !== null && c.km !== undefined
        ? `<span class="badge km">📍 ${esc(c.sede)}${c.km ? ` · ${c.km} km` : ""}</span>`
        : `<span class="badge km">📍 ${esc(c.sede)}</span>`,
      `<span class="badge">${esc(c.tipo)}</span>`,
      ...(c.tag || []).filter((t) => ETICHETTE[t]).map((t) => `<span class="badge">${esc(ETICHETTE[t])}</span>`),
    ];
    return `<article class="card card-curata">
      <h3>${esc(c.nome)}</h3>
      <div class="badge-riga">${badge.join("")}</div>
      <p class="perche">${esc(c.perche)}</p>
      <div class="link">
        ${c.carriere && c.carriere_ok !== false ? `<a href="${esc(c.carriere)}" target="_blank" rel="noopener">Bandi e posizioni ↗</a>` : ""}
        ${c.sito && c.sito_ok !== false ? `<a href="${esc(c.sito)}" target="_blank" rel="noopener">Sito ↗</a>` : ""}
        <a href="${esc(cerca)}" target="_blank" rel="noopener">Cerca su Google ↗</a>
      </div>
    </article>`;
  }).join("");
}

function disegnaChip() {
  const contaTag = {}, contaProv = {};
  DATI.annunci.forEach((a) => {
    (a.tag || []).forEach((t) => { if (ETICHETTE[t] && t !== "requisiti") contaTag[t] = (contaTag[t] || 0) + 1; });
    const p = a.provincia || "Nazionale";
    contaProv[p] = (contaProv[p] || 0) + 1;
  });

  document.getElementById("chip-tag").innerHTML = Object.entries(contaTag)
    .sort((a, b) => b[1] - a[1])
    .map(([t, n]) => `<button class="chip" data-tipo="tag" data-v="${esc(t)}">${esc(ETICHETTE[t])} <span>${n}</span></button>`)
    .join("");

  document.getElementById("chip-prov").innerHTML = Object.entries(contaProv)
    .sort((a, b) => b[1] - a[1])
    .map(([p, n]) => `<button class="chip" data-tipo="prov" data-v="${esc(p)}">📍 ${esc(p)} <span>${n}</span></button>`)
    .join("");
}

function disegnaCifre() {
  const st = DATI.statistiche || {};
  const f = st.per_fascia || {};
  document.getElementById("cifre").innerHTML = `
    <div class="cifra"><b>${DATI.annunci.length}</b><span>bandi</span></div>
    <div class="cifra"><b>${(st.per_titolo || {}).escluso || 0}</b><span>ti escludono</span></div>
    <div class="cifra"><b>${(DATI.curati || []).length}</b><span>enti</span></div>`;

  const d = DATI.aggiornato ? new Date(DATI.aggiornato) : null;
  document.getElementById("aggiornato").textContent = d
    ? d.toLocaleString("it-IT", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";

  const diag = document.getElementById("diagnostica");
  const errori = DATI.errori_fonti || [];
  diag.textContent =
    `Ultimo giro: ${st.grezzi || 0} annunci letti, ${st.pubblicati || 0} pubblicati, ` +
    `${st.scartati_distanza || 0} fuori raggio, ${st.scartati_profilo || 0} fuori profilo.` +
    (errori.length ? ` Fonti in errore: ${errori.join("; ")}` : "");
}

/* ---------------------------------------------------------------- eventi */
function collega() {
  document.getElementById("cerca").addEventListener("input", (e) => {
    filtri.testo = e.target.value.trim().toLowerCase();
    disegnaBandi();
  });

  document.querySelectorAll(".riga-chip").forEach((riga) => {
    riga.addEventListener("click", (e) => {
      const b = e.target.closest(".chip");
      if (!b) return;
      const insieme = b.dataset.tipo === "tag" ? filtri.tag : filtri.prov;
      insieme.has(b.dataset.v) ? insieme.delete(b.dataset.v) : insieme.add(b.dataset.v);
      b.classList.toggle("on");
      disegnaBandi();
    });
  });

  const km = document.getElementById("km");
  km.addEventListener("input", (e) => {
    filtri.km = Number(e.target.value);
    document.getElementById("km-out").textContent = filtri.km;
    disegnaBandi();
  });

  document.getElementById("stato-mio").addEventListener("change", (e) => {
    filtri.mio = e.target.value; disegnaBandi();
  });
  document.getElementById("scad").addEventListener("change", (e) => {
    filtri.scad = e.target.value; disegnaBandi();
  });
  document.getElementById("titolo").addEventListener("change", (e) => {
    filtri.titolo = e.target.value; disegnaBandi();
  });

  document.getElementById("azzera").addEventListener("click", () => {
    filtri.testo = ""; filtri.tag.clear(); filtri.prov.clear();
    filtri.km = 150; filtri.mio = "attivi"; filtri.scad = ""; filtri.titolo = "possibili";
    document.getElementById("cerca").value = "";
    document.getElementById("km").value = 150;
    document.getElementById("km-out").textContent = "150";
    document.getElementById("stato-mio").value = "attivi";
    document.getElementById("scad").value = "";
    document.getElementById("titolo").value = "possibili";
    document.querySelectorAll(".chip.on").forEach((c) => c.classList.remove("on"));
    disegnaBandi();
  });

  document.getElementById("lista").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-st]");
    if (!b) return;
    const { id, st } = b.dataset;
    stati[id] === st ? delete stati[id] : (stati[id] = st);
    salvaStati();
    disegnaBandi();
  });

  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("attivo"));
      t.classList.add("attivo");
      ["bandi", "curati", "info"].forEach((v) => {
        document.getElementById("vista-" + v).hidden = v !== t.dataset.vista;
      });
    });
  });
}

/* ---------------------------------------------------------------- avvio */
fetch("data/jobs.json?" + Date.now())
  .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
  .then((d) => {
    DATI = d;
    disegnaCifre();
    disegnaChip();
    disegnaBandi();
    disegnaCurati();
    collega();
  })
  .catch((e) => {
    document.getElementById("lista").innerHTML =
      `<p class="vuoto">Non riesco a leggere <code>data/jobs.json</code> (${esc(e.message)}).<br>
       Se hai appena creato il repository, lancia il workflow <em>Aggiorna bandi</em> da GitHub Actions.</p>`;
  });
