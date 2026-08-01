// ═══════════════════════════════════════════
//  M2 — CATALOG (Mini App)
//  ВХОД:  index.json (catalog-index-v2)
//  ВЫХОД: sendData → order.json {job_id, user_id, fabrics:[{supplier,catalog,article}]}
//
//  Навигация: поставщик → коллекция → каталог → ткани.
//  Коллекция — ТОЛЬКО навигация. В fabric_key / order.json НЕ входит.
//  Коллекция id="_default" (name=null, cover=null) → экран коллекции ПРОПУСКАЕТСЯ.
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
let curSupplier   = null;
let curCollection = null;   // новый уровень (только навигация)
let curCatalog    = null;
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
    if (INDEX._schema !== "catalog-index-v2") {
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
  curSupplier = null; curCollection = null; curCatalog = null;
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
    $screen.appendChild(card(sup.avatar, sup.name, () => enterSupplier(sup)));
  }
}

// ═══════════════════════════════════════════
//  РАЗВИЛКА: коллекции ИЛИ сразу каталоги (пропуск _default)
// ═══════════════════════════════════════════
function isDefaultOnly(sup) {
  const cols = sup.collections || [];
  return cols.length === 1 && cols[0].id === "_default";
}

function enterSupplier(sup) {
  curSupplier = sup; curCollection = null; curCatalog = null;
  if (isDefaultOnly(sup)) {
    // единственная синтетическая коллекция → экран коллекции ПРОПУСКАЕМ
    renderCatalogs(sup.collections[0]);
  } else {
    renderCollections(sup);
  }
}

// ═══════════════════════════════════════════
//  ЭКРАН 2 — КОЛЛЕКЦИИ (только навигация)
// ═══════════════════════════════════════════
function renderCollections(sup) {
  curSupplier = sup; curCollection = null; curCatalog = null;
  $title.textContent = sup.name;
  $back.classList.remove("hidden");
  $bottom.classList.add("hidden");
  $screen.className = "";
  $screen.innerHTML = "";

  for (const col of sup.collections) {
    // _default сюда не попадёт (развилка выше), но подстрахуемся именем/обложкой
    const name  = col.name  ?? "Коллекция";
    const cover = col.cover ?? "";
    $screen.appendChild(card(cover, name, () => renderCatalogs(col)));
  }
}

// ═══════════════════════════════════════════
//  ЭКРАН 3 — КАТАЛОГИ
// ═══════════════════════════════════════════
function renderCatalogs(col) {
  curCollection = col; curCatalog = null;
  // заголовок: имя коллекции, а для _default — имя поставщика (старое поведение)
  $title.textContent = (col.id === "_default") ? curSupplier.name : (col.name ?? curSupplier.name);
  $back.classList.remove("hidden");
  $bottom.classList.add("hidden");
  $screen.className = "";
  $screen.innerHTML = "";

  for (const cat of col.catalogs) {
    $screen.appendChild(card(cat.cover, cat.name, () => renderFabrics(cat)));
  }
}

// ═══════════════════════════════════════════
//  ЭКРАН 4 — ТКАНИ (мультивыбор)
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
      supplier: curSupplier.id,   // коллекция в ключ/заказ НЕ входит
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
//  НАВИГАЦИЯ НАЗАД (симметрична пропуску _default)
// ═══════════════════════════════════════════
function goBack() {
  if (curCatalog) {
    // с тканей → к каталогам текущей коллекции
    renderCatalogs(curCollection);
  } else if (curCollection) {
    // с каталогов → к коллекциям;
    // но если коллекция была _default (пропущена) → сразу к поставщикам
    if (curCollection.id === "_default") {
      renderSuppliers();
    } else {
      renderCollections(curSupplier);
    }
  } else if (curSupplier) {
    // с экрана коллекций → к поставщикам
    renderSuppliers();
  }
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