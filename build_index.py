#!/usr/bin/env python3
# build_index.py — M2, сборка index.json (catalog-index-v2)
#
# Навигация: поставщик → коллекция → каталог → ткани.
# Коллекция — ТОЛЬКО навигация. В fabric_key НЕ входит.
#
# ┌─ ИНВАРИАНТ (предохранитель, НЕ трогать) ────────────────────────────┐
# │ fabric_key = "<supplier>__<catalog>__<article>"                     │
# │ Коллекция в ключ НЕ входит ⇒ slug каталога должен быть УНИКАЛЕН      │
# │ внутри одного поставщика (across коллекций + _default), иначе ткани  │
# │ склеятся по ключу. При дубле — падаем с понятной ошибкой.           │
# │                                                                     │
# │ Разделитель ключа = "__" (двойное подчёркивание). В артикуле его    │
# │ быть НЕ должно — иначе ключ распадётся. При наличии — падаем.       │
# └─────────────────────────────────────────────────────────────────────┘
#
# Ткань = ПАПКА-ЛИСТ (внутри нет подпапок). Имя папки = артикул.
# Имя артикула — любое: 2011-1, 214-2, ART-1001 и т.п. (кроме "__").

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPPLIERS_DIR = ROOT / "suppliers"
OUT_FILE = ROOT / "index.json"

SCHEMA = "catalog-index-v2"

# base_url для картинок в мини-аппе (как в реале — поле base_url, НЕ slug).
# Пусто = относительные пути (GitHub Pages отдаёт из того же репо).
BASE_URL = ""

# ── ИМЕНА ФАЙЛОВ ──────────────────────────────────────────────────────
INFO = "info.json"
AVATAR = "avatar.jpg"
COVER = "cover.jpg"
THUMB = "thumb.jpg"

DEFAULT_COLLECTION = "_default"


# ── ХЕЛПЕРЫ ───────────────────────────────────────────────────────────
def _subdirs(path: Path):
    """Отсортированные подпапки (стабильный порядок сборки)."""
    return sorted([p for p in path.iterdir() if p.is_dir()], key=lambda p: p.name)


def _is_article_dir(path: Path) -> bool:
    """Ткань = папка-ЛИСТ: внутри нет ни одной подпапки."""
    if not path.is_dir():
        return False
    return not any(p.is_dir() for p in path.iterdir())


def _has_articles(path: Path) -> bool:
    """В папке лежат ткани (папки-листы) ⇒ это КАТАЛОГ."""
    return any(_is_article_dir(p) for p in path.iterdir())


def _read_name(dir_path: Path, fallback: str) -> str:
    """info.json → {"name": ...}; нет файла/битый → fallback (id папки)."""
    info = dir_path / INFO
    if not info.exists():
        return fallback
    try:
        data = json.loads(info.read_text(encoding="utf-8"))
        name = data.get("name")
        return name if isinstance(name, str) and name.strip() else fallback
    except (json.JSONDecodeError, OSError):
        print(f"  ⚠️  битый {info} → имя = '{fallback}'")
        return fallback


def _rel(path: Path) -> str:
    """Путь к картинке относительно корня репо (для мини-аппа)."""
    return path.relative_to(ROOT).as_posix()


def _img_or_none(path: Path):
    """Путь к картинке, если файл есть, иначе None (onerror в app.js подстрахует)."""
    return _rel(path) if path.exists() else None


# ── СБОРКА ОДНОГО КАТАЛОГА ────────────────────────────────────────────
def build_catalog(catalog_dir: Path, supplier_id: str) -> dict:
    catalog_id = catalog_dir.name
    name = _read_name(catalog_dir, catalog_id)

    fabrics = []
    for art_dir in _subdirs(catalog_dir):
        if not _is_article_dir(art_dir):
            continue
        article = art_dir.name

        # ПРЕДОХРАНИТЕЛЬ: "__" — разделитель fabric_key. В артикуле его быть НЕ должно.
        if "__" in article:
            sys.exit(
                f"\n❌ Артикул '{article}' у поставщика '{supplier_id}', каталог '{catalog_id}':\n"
                f"   содержит '__' (двойное подчёркивание) — это разделитель fabric_key.\n"
                f"   Ключ распадётся. Переименуй папку (одиночный '-' или '_' можно).\n"
            )

        # fabric_key — ЕДИНСТВЕННАЯ склейка. Коллекции тут НЕТ.
        key = f"{supplier_id}__{catalog_id}__{article}"
        fabrics.append({
            "article": article,
            "thumb": _img_or_none(art_dir / THUMB),
            "key": key,
        })

    return {
        "id": catalog_id,
        "name": name,
        "cover": _img_or_none(catalog_dir / COVER),
        "fabrics": fabrics,
    }


# ── СБОРКА ОДНОГО ПОСТАВЩИКА ──────────────────────────────────────────
def build_supplier(supplier_dir: Path) -> dict:
    supplier_id = supplier_dir.name
    name = _read_name(supplier_dir, supplier_id)

    collections = []
    default_catalogs = []          # каталоги напрямую под поставщиком → _default
    seen_catalog_slugs = {}        # slug каталога → откуда пришёл (для ошибки о дубле)

    def register_catalog(cat_dir: Path, source: str):
        """Проверка дубля slug каталога внутри поставщика + возврат dict каталога."""
        slug = cat_dir.name
        if slug in seen_catalog_slugs:
            first = seen_catalog_slugs[slug]
            sys.exit(
                f"\n❌ ДУБЛЬ slug каталога '{slug}' у поставщика '{supplier_id}':\n"
                f"     • {first}\n"
                f"     • {source}\n"
                f"   fabric_key = supplier__catalog__article, коллекция в ключ НЕ входит.\n"
                f"   Одинаковый slug каталога в двух местах ⇒ ткани СКЛЕЯТСЯ по ключу.\n"
                f"   Переименуй одну из папок каталога.\n"
            )
        seen_catalog_slugs[slug] = source
        return build_catalog(cat_dir, supplier_id)

    # Проходим по всем подпапкам поставщика.
    # Папка = КАТАЛОГ, если внутри есть ткани (папки-листы) напрямую.
    # Папка = КОЛЛЕКЦИЯ, если тканей напрямую нет, но есть подпапки-каталоги.
    for child in _subdirs(supplier_dir):
        if _has_articles(child):
            # прямой каталог → уедет в _default
            default_catalogs.append(
                register_catalog(child, f"suppliers/{supplier_id}/{child.name}/ (напрямую → _default)")
            )
        else:
            # это коллекция — внутри ищем каталоги
            coll_id = child.name
            coll_name = _read_name(child, coll_id)
            coll_catalogs = []
            for cat_dir in _subdirs(child):
                if _has_articles(cat_dir):
                    coll_catalogs.append(
                        register_catalog(
                            cat_dir,
                            f"suppliers/{supplier_id}/{coll_id}/{cat_dir.name}/"
                        )
                    )
                # папки без тканей внутри коллекции просто игнорируем (мусор/пусто)

            if coll_catalogs:
                collections.append({
                    "id": coll_id,
                    "name": coll_name,
                    "cover": _img_or_none(child / COVER),
                    "catalogs": coll_catalogs,
                })

    # Прямые каталоги оборачиваем в синтетическую коллекцию _default
    if default_catalogs:
        collections.insert(0, {
            "id": DEFAULT_COLLECTION,
            "name": None,          # app.js: если единственная коллекция _default → экран пропускается
            "cover": None,
            "catalogs": default_catalogs,
        })

    return {
        "id": supplier_id,
        "name": name,
        "avatar": _img_or_none(supplier_dir / AVATAR),
        "collections": collections,
    }


# ── ГЛАВНАЯ СБОРКА ────────────────────────────────────────────────────
def build_index() -> dict:
    if not SUPPLIERS_DIR.exists():
        sys.exit(f"❌ нет папки {SUPPLIERS_DIR}")

    suppliers = []
    for supplier_dir in _subdirs(SUPPLIERS_DIR):
        suppliers.append(build_supplier(supplier_dir))

    return {
        "_schema": SCHEMA,
        "base_url": BASE_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suppliers": suppliers,
    }


def _count(index: dict):
    n_sup = len(index["suppliers"])
    n_coll = n_cat = n_fab = 0
    for s in index["suppliers"]:
        for coll in s["collections"]:
            # _default не считаем реальной коллекцией в статистике
            if coll["id"] != DEFAULT_COLLECTION:
                n_coll += 1
            for cat in coll["catalogs"]:
                n_cat += 1
                n_fab += len(cat["fabrics"])
    return n_sup, n_coll, n_cat, n_fab


def main():
    index = build_index()
    OUT_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    n_sup, n_coll, n_cat, n_fab = _count(index)
    print(
        f"✅ index.json ({SCHEMA}): "
        f"поставщиков={n_sup} коллекций={n_coll} каталогов={n_cat} тканей={n_fab}"
    )


if __name__ == "__main__":
    main()