#!/usr/bin/env python3
# build_index.py — сборка index.json (СХЕМА v2)
#
# ═══════════════════════════════════════════════════════════════════════════
#  ИНВАРИАНТ-ПРЕДОХРАНИТЕЛЬ (НЕ НАРУШАТЬ):
#
#    fabric_key = "<supplier>__<catalog>__<article>"   — РОВНО 3 части, ВСЕГДА.
#    collection в fabric_key НЕ входит. Коллекция — ТОЛЬКО навигация в M2.
#
#    Требование корректности: catalog-id УНИКАЛЕН внутри поставщика,
#    даже если каталоги лежат в разных коллекциях. Нарушение → сборка ПАДАЕТ.
# ═══════════════════════════════════════════════════════════════════════════
#
# РАСПОЗНАВАНИЕ (одно правило):
#   Папка внутри поставщика:
#     • содержит хотя бы одну ART-* папку  → это КАТАЛОГ (3-звенная цепь)
#     • содержит только под-папки без ART-* → это КОЛЛЕКЦИЯ (4-звенная цепь),
#       её под-папки = каталоги
#   Глубже 4 звеньев не идём (коллекция→коллекция запрещена).

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── пути ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
SUPPLIERS_DIR = ROOT / "suppliers"
INDEX_OUT = ROOT / "index.json"

# ── имена файлов внутри папок (константы структуры) ───────────────────────
INFO_JSON = "info.json"
AVATAR = "avatar.jpg"
COVER = "cover.jpg"
THUMB = "thumb.jpg"
FABRIC = "fabric.jpg"
CALIB = "calib.json"
ART_PREFIX = "ART-"


# ── утилиты ────────────────────────────────────────────────────────────────
def read_name(dir_path: Path, fallback: str) -> str:
    """Читает {'name': ...} из info.json. Нет файла/битый → fallback = имя папки."""
    p = dir_path / INFO_JSON
    if not p.exists():
        return fallback
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        name = data.get("name")
        return name if isinstance(name, str) and name.strip() else fallback
    except (json.JSONDecodeError, OSError):
        print(f"⚠️  битый {p} → имя из папки '{fallback}'")
        return fallback


def rel(path: Path) -> str:
    """Относительный POSIX-путь от корня репо (для index.json / GitHub raw)."""
    return path.relative_to(ROOT).as_posix()


def has_articles(d: Path) -> bool:
    """True, если в папке есть хотя бы одна ART-* под-папка → это КАТАЛОГ."""
    return any(
        child.is_dir() and child.name.startswith(ART_PREFIX)
        for child in d.iterdir()
    )


# ── сборка тканей каталога ─────────────────────────────────────────────────
def build_fabrics(catalog_dir: Path) -> list:
    """
    Собирает список тканей каталога. У каждой ткани — ГОТОВЫЕ относительные
    пути к файлам (fabric_path / calib_path / thumb). M1 берёт путь отсюда,
    сам его НЕ склеивает (чинит техдолг: M1 не знает структуру папок).
    """
    fabrics = []
    for art in sorted(catalog_dir.iterdir()):
        if not (art.is_dir() and art.name.startswith(ART_PREFIX)):
            continue

        fabric_file = art / FABRIC
        if not fabric_file.exists():
            print(f"⚠️  пропуск {rel(art)} — нет {FABRIC}")
            continue

        calib_file = art / CALIB
        thumb_file = art / THUMB

        fabrics.append({
            "article": art.name,
            "thumb": rel(thumb_file) if thumb_file.exists() else None,
            "fabric_path": rel(fabric_file),
            # calib.json может отсутствовать → null (M3.4 возьмёт дефолты)
            "calib_path": rel(calib_file) if calib_file.exists() else None,
        })
    return fabrics


def build_catalog(catalog_dir: Path, collection: dict | None) -> dict:
    """
    Узел каталога для index.json.
    collection: dict {id,name,cover} для 4-звенной цепи, либо None для 3-звенной.
    ВАЖНО: collection — ярлык-приписка к каталогу, в fabric_key НЕ входит.
    """
    cover_file = catalog_dir / COVER
    return {
        "id": catalog_dir.name,
        "name": read_name(catalog_dir, catalog_dir.name),
        "cover": rel(cover_file) if cover_file.exists() else None,
        "collection": collection,   # None → 3-звенный (как раньше)
        "fabrics": build_fabrics(catalog_dir),
    }


def build_collection_meta(collection_dir: Path) -> dict:
    """Метаданные коллекции (id/name/cover) — только для навигации в M2."""
    cover_file = collection_dir / COVER
    return {
        "id": collection_dir.name,
        "name": read_name(collection_dir, collection_dir.name),
        "cover": rel(cover_file) if cover_file.exists() else None,
    }


# ── сборка поставщика (рекурсия глубины 3/4) ───────────────────────────────
def build_supplier(supplier_dir: Path) -> dict:
    """
    Плоский список catalogs (как в v1) — старый код M2 продолжает работать.
    Каждый каталог несёт поле collection: null (3-звенный) или {id,name,cover}.
    """
    catalogs = []

    for entry in sorted(supplier_dir.iterdir()):
        if not entry.is_dir():
            continue
        # служебные файлы (info.json, avatar.jpg) отсеяны is_dir()

        if has_articles(entry):
            # ── 3-звенная цепь: прямой каталог, коллекции нет ──
            catalogs.append(build_catalog(entry, collection=None))
        else:
            # ── 4-звенная цепь: это КОЛЛЕКЦИЯ, внутри каталоги ──
            collection = build_collection_meta(entry)
            for sub in sorted(entry.iterdir()):
                if not sub.is_dir():
                    continue
                if has_articles(sub):
                    catalogs.append(build_catalog(sub, collection=collection))
                else:
                    # глубже 4 звеньев не идём (коллекция→коллекция запрещена)
                    print(f"⚠️  {rel(sub)} — нет ART-* и это уже внутри "
                          f"коллекции '{collection['id']}', пропуск "
                          f"(коллекция→коллекция не поддерживается)")

    # ── ПРОВЕРКА ИНВАРИАНТА: catalog-id уникален внутри поставщика ──
    # Единственный способ сломать fabric_key ловим ЗДЕСЬ, до прода.
    seen = {}
    for cat in catalogs:
        cid = cat["id"]
        if cid in seen:
            src_a = seen[cid]
            src_b = (f"коллекция '{cat['collection']['id']}'"
                     if cat["collection"] else "прямой каталог")
            sys.exit(
                f"❌ ДУБЛЬ catalog-id '{cid}' у поставщика "
                f"'{supplier_dir.name}':\n"
                f"     первый:  {src_a}\n"
                f"     второй:  {src_b}\n"
                f"   catalog-id ДОЛЖЕН быть уникален внутри поставщика — "
                f"он входит в fabric_key, а collection НЕТ.\n"
                f"   Переименуй одну из папок каталога."
            )
        seen[cid] = (f"коллекция '{cat['collection']['id']}'"
                     if cat["collection"] else "прямой каталог")

    avatar_file = supplier_dir / AVATAR
    return {
        "id": supplier_dir.name,
        "name": read_name(supplier_dir, supplier_dir.name),
        "avatar": rel(avatar_file) if avatar_file.exists() else None,
        "catalogs": catalogs,
    }


# ── главная сборка ─────────────────────────────────────────────────────────
def build_index() -> dict:
    if not SUPPLIERS_DIR.is_dir():
        sys.exit(f"❌ нет папки {SUPPLIERS_DIR}")

    suppliers = []
    for supplier_dir in sorted(SUPPLIERS_DIR.iterdir()):
        if supplier_dir.is_dir():
            suppliers.append(build_supplier(supplier_dir))

    return {
        "_schema": "catalog-index-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suppliers": suppliers,
    }


def main():
    index = build_index()

    INDEX_OUT.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── контрольные цифры сборки (эталон для сверки) ──
    n_suppliers = len(index["suppliers"])
    n_catalogs = sum(len(s["catalogs"]) for s in index["suppliers"])
    n_fabrics = sum(
        len(c["fabrics"])
        for s in index["suppliers"]
        for c in s["catalogs"]
    )
    n_collections = len({
        c["collection"]["id"]
        for s in index["suppliers"]
        for c in s["catalogs"]
        if c["collection"]
    })

    print(f"✅ index.json (v2): поставщиков={n_suppliers} "
          f"каталогов={n_catalogs} тканей={n_fabrics} "
          f"коллекций={n_collections}")


if __name__ == "__main__":
    main()