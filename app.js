// ═══════════════════════════════════════════
//  M2 — CATALOG (Mini App)
//  ВХОД:  index.json
//  ВЫХОД: sendData → order.json {job_id, user_id, fabrics:[{supplier,catalog,article}]}
// ═══════════════════════════════════════════

const LIMIT = 10;
const INDEX_URL = "index.json";

const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

// ── job_id из URL (БЕЗ fallback!), user_id из Telegram ──
const params = new URLSearchParams(location.search);
const JOB_ID  = params.get("job_id");
const USER_ID = tg?.initDataUnsafe?.user?.id ?? 0;

// ── состояние ──
let INDEX = null;
let curSupplier = null;
let curCatalog  = null;
const selected = new Map();

// ── элементы ──
const $screen  = document.getElementById("screen");
const $title   = document.getElementById("title");
const $back    = document.getElementById("back");
const $bottom  = document.getElementById("bottombar");
const $counter = document.getElementById("counter");
const $confirm = document.getElementById("confirm");

$back.addEventListener("click", goBack);
$confirm.addEventListener("click", confirm);

// ═══════════════════════════════════════════
//  ЭКРАНИРОВАНИЕ (XSS-защита)
// ═══════════════════════════════════════════
function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

// ═══════════════════════════════════════════
//  ХЕЛПЕР: карточка (аватар/обложка + имя + клик)
// ═══════════════════════════════════════════
function card(img, name, onClick) {
  const el = document.createElement("div");
  el.className = "card";
  el.innerHTML = `
    <img src="${esc(img)}" alt="${esc(name)}" loading="lazy"
         onerror="this.style.opacity=0.3">
    <div class="card-name">${esc(name)}</div>`;
  el.addEventListener("click", onClick);
  return el;
}

// ═══════════════════════════════════════════
//  ЗАГРУЗКА
// ═══════════════════════════════════════════
(async function init() {
  try {
    const res = await fetch(INDEX_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    INDEX = await res.json();
    if (INDEX._schema !== "catalog-index-v1") {
      $screen.innerHTML = `<div class="msg">Каталог устарел, обнови приложение.</div>`;
      return;
    }
    renderSuppliers();
  } catch (e) {
    $screen.innerHTML = `<div class="msg">Не удалось загрузить каталог.<br>${esc(e.message)}</div>`;
  }
})();

// ═══════════════════════════════════════════
//  ЭКРАН 1 — ПОСТАВЩИКИ
// ═══════════════════════════════════════════
function renderSuppliers() {
  curSupplier = null; curCatalog = null;
  $title.textContent = "Поставщики";
  $back.classList.add("hidden");
  $bottom.classList.add("hidden");
  $screen.className = "";
  $screen.innerHTML = "";

  if (!INDEX.suppliers?.length) {
    $screen.innerHTML = `<div class="msg">Каталог пуст.</div>`;
    return;
  }
  for (const sup of INDEX.suppliers) {
    $screen.appendChild(card(sup.avatar, sup.name, () => renderCatalogs(sup)));
  }
}

// ═══════════════════════════════════════════
//  ЭКРАН 2 — КАТАЛОГИ
// ═══════════════════════════════════════════
function renderCatalogs(sup) {
  curSupplier = sup; curCatalog = null;
  $title.textContent = sup.name;
  $back.classList.remove("hidden");
  $bottom.classList.add("hidden");
  $screen.className = "";
  $screen.innerHTML = "";

  for (const cat of sup.catalogs) {
    $screen.appendChild(card(cat.cover, cat.name, () => renderFabrics(cat)));
  }
}

// ═══════════════════════════════════════════
//  ЭКРАН 3 — ТКАНИ (мультивыбор)
// ═══════════════════════════════════════════
function renderFabrics(cat) {
  curCatalog = cat;
  $title.textContent = cat.name;
  $back.classList.remove("hidden");
  $screen.className = "fabrics";
  $screen.innerHTML = "";
  $bottom.classList.remove("hidden");

  for (const fab of cat.fabrics) {
    const el = document.createElement("div");
    el.className = "fabric" + (selected.has(fab.key) ? " selected" : "");
    el.innerHTML = `
      <div class="check">✓</div>
      <img src="${esc(fab.thumb)}" alt="${esc(fab.article)}" loading="lazy"
           onerror="this.style.opacity=0.3">
      <div class="art">${esc(fab.article)}</div>`;
    el.addEventListener("click", () => toggle(fab, el));
    $screen.appendChild(el);
  }
  updateCounter();
}

// ═══════════════════════════════════════════
//  ВЫБОР
// ═══════════════════════════════════════════
function toggle(fab, el) {
  if (selected.has(fab.key)) {
    selected.delete(fab.key);
    el.classList.remove("selected");
  } else {
    if (selected.size >= LIMIT) {
      if (tg) tg.HapticFeedback?.notificationOccurred("error");
      flashLimit();
      return;
    }
    selected.set(fab.key, {
      supplier: curSupplier.id,
      catalog:  curCatalog.id,
      article:  fab.article,
    });
    el.classList.add("selected");
  }
  updateCounter();
}

function updateCounter() {
  const n = selected.size;
  $counter.textContent = `Выбрано: ${n} / ${LIMIT}`;
  $confirm.disabled = (n === 0);
}

function flashLimit() {
  $counter.textContent = `Максимум ${LIMIT} тканей`;
  $counter.style.color = "#e53935";
  setTimeout(() => { $counter.style.color = ""; updateCounter(); }, 1200);
}

// ═══════════════════════════════════════════
//  НАВИГАЦИЯ НАЗАД
// ═══════════════════════════════════════════
function goBack() {
  if (curCatalog)       { renderCatalogs(curSupplier); }
  else if (curSupplier) { renderSuppliers(); }
}

// ═══════════════════════════════════════════
//  ПОДТВЕРДИТЬ → sendData(order.json)
// ═══════════════════════════════════════════
function confirm() {
  if (selected.size === 0) return;

  if (!JOB_ID) {
    alert("Открой каталог через бота — ссылка без параметров.");
    return;
  }

  const order = {
    job_id:  JOB_ID,
    user_id: USER_ID,
    fabrics: Array.from(selected.values()),
  };
  const payload = JSON.stringify(order);

  if (tg && tg.sendData) {
    tg.sendData(payload);
  } else {
    console.log("order.json →", payload);
    alert("order.json (см. console):\n" + payload);
  }
}
