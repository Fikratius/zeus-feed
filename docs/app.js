const elFeed = document.getElementById("feed");
const elMeta = document.getElementById("meta");
const elQ = document.getElementById("q");
const elSource = document.getElementById("source");
const elSort = document.getElementById("sort");
const elBiasMax = document.getElementById("biasMax");
const elBiasMaxLabel = document.getElementById("biasMaxLabel");

let items = [];

function fmtDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year:"numeric", month:"short", day:"2-digit",
      hour:"2-digit", minute:"2-digit"
    });
  } catch { return iso || ""; }
}

function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }

function lrLabel(lr, lang){
  const v = Number(lr);
  if (!isFinite(v)) return (lang === "en") ? "n/a" : "н/д";

  if (lang === "en"){
    if (v <= -35) return 'moderately "left"';
    if (v >= 35) return 'moderately "right"';
    return 'near "center"';
  }

  if (v <= -35) return 'умеренно “левее”';
  if (v >= 35) return 'умеренно “правее”';
  return 'ближе к “центру”';
}

function escapeHtml(str){
  return String(str ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function render(){
  const q = (elQ.value || "").trim().toLowerCase();
  const source = elSource.value;
  const sort = elSort.value;
  const biasMax = Number(elBiasMax.value);

  let filtered = items.filter(x => {
    if (source && x.source !== source) return false;
    if ((x.bias_score ?? 0) > biasMax) return false;
    if (!q) return true;

    const hay = `${x.title_neutral||""} ${x.main_idea||""} ${(x.tags||[]).join(" ")}`.toLowerCase();
    return hay.includes(q);
  });

  if (sort === "bias"){
    filtered.sort((a,b)=> (b.bias_score||0) - (a.bias_score||0));
  } else {
    filtered.sort((a,b)=> new Date(b.published_at||0) - new Date(a.published_at||0));
  }

  elMeta.textContent = `Показано ${filtered.length} новостей • обновление: ${fmtDate(window.__last_updated || "")}`;

  elFeed.innerHTML = filtered.map(x => {
    const lang = x.lang || "ru";
    const bias = clamp(Number(x.bias_score ?? 0), 0, 100);
    const lr = Number(x.left_right_index ?? 0);
    const conf = x.confidence || "n/a";
    const tags = (x.tags || []).slice(0,4);

    const title = x.title_neutral || x.title_original || "Без заголовка";
    const recap = x.recap_neutral || "—";
    const mainIdeaLabel = (lang === "en") ? "Main idea:" : "Главная идея:";
    const mainIdea = x.main_idea || "—";
    const biasLabel = (lang === "en") ? "Bias" : "Bias";
    const lrLabelText = lrLabel(lr, lang);
    const published = x.published_at ? fmtDate(x.published_at) : "";
    const sourceLabel = x.source || "";

    return `
      <article class="card">
        <h3 class="h1">${escapeHtml(title)}</h3>
        <div class="subline">${escapeHtml(sourceLabel)} • ${escapeHtml(published)} • ${escapeHtml(lang.toUpperCase())}</div>
        ${meduzaNotice ? `<div class="agent-badge">${escapeHtml(meduzaNotice)}</div>` : ""}
        <div class="scoreline">
          <span class="k">${biasLabel}:</span>
          <div class="dotbar"><div class="dotbar-fill" style="width:${bias}%;"></div></div>
          <span class="num">${bias}/100</span>
          <span class="sep">·</span>
          <span>LR: ${escapeHtml(lr.toFixed(0))} (${escapeHtml(lrLabelText)})</span>
        </div>
        <p class="recap">${escapeHtml(recap)}</p>
        <div class="idea"><strong>${escapeHtml(mainIdeaLabel)}</strong> ${escapeHtml(mainIdea)}</div>
        <div class="chips">
          ${tags.map(t => `<span class="chip">${escapeHtml(t)}</span>`).join("")}
        </div>
        <div class="actions">
          <a class="btn" href="${escapeHtml(x.url || "#")}" target="_blank" rel="noopener">Источник →</a>
          <span class="small">confidence: ${escapeHtml(conf)}</span>
        </div>
      </article>
    `;
  }).join("");
}

async function load(){
  try {
    const res = await fetch("./feed.json", { cache: "no-store" });
    const data = await res.json();
    items = data.items || [];
    window.__last_updated = data.last_updated || "";

    const sources = Array.from(new Set(items.map(x => x.source).filter(Boolean))).sort();
    for (const s of sources){
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      elSource.appendChild(opt);
    }

    render();
  } catch (err){
    elMeta.textContent = "Не удалось загрузить ленту.";
    console.error(err);
  }
}

elQ.addEventListener("input", render);
elSource.addEventListener("change", render);
elSort.addEventListener("change", render);
elBiasMax.addEventListener("input", () => {
  elBiasMaxLabel.textContent = elBiasMax.value;
  render();
});

load();
