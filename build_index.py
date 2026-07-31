#!/usr/bin/env python3
"""
Генератор index.json для M2 CATALOG.
Обходит suppliers/ → собирает иерархию поставщик→каталог→ткань.
Правило простоты: добавил папку ART-XXXX/ → Action пересобрал → miniapp показал.

Структура (из карты):
  suppliers/<supplier>/info.json + avatar.jpg
    /<catalog>/info.json + cover.jpg
      /<ART-XXXX>/fabric.jpg + thumb.jpg + calib.json(опц.)

fabric_key = "<supplier>__<catalog>__<article>"  — общая константа проекта.
"""
import os, json, sys
from datetime import datetime, timezone

ROOT = "suppliers"
OUT  = "index.json"

# ── base_url для GitHub Pages: https://<user>.github.io/<repo> ──
repo = os.environ.get("GITHUB_REPOSITORY", "")   # "user/repo"
if repo and "/" in repo:
    user, name = repo.split("/", 1)
    PAGES = f"https://{user}.github.io/{name}"
else:
    PAGES = "."   # локальный прогон → относительные пути (см. ниже)

BASE = f"{PAGES}/suppliers" if PAGES != "." else "suppliers"


def read_name(folder, fallback):
    """info.json → {'name': ...}; если нет — имя папки."""
    p = os.path.join(folder, "info.json")
    if os.path.isfile(p):
        try:
            data = json.load(open(p, encoding="utf-8"))
            n = data.get("name")
            if n:
                return n
        except Exception as e:
            print(f"  ⚠️  битый info.json ({p}): {e}", file=sys.stderr)
    return fallback


def first_existing(folder, names):
    """Вернуть первое существующее имя файла из списка (jpg/png)."""
    for n in names:
        if os.path.isfile(os.path.join(folder, n)):
            return n
    return None


def img_url(*parts):
    return "/".join([BASE] + list(parts))


def is_dir(p):
    return os.path.isdir(p) and not os.path.basename(p).startswith(".")


def build():
    if not os.path.isdir(ROOT):
        print(f"❌ нет папки {ROOT}/", file=sys.stderr)
        sys.exit(1)

    suppliers = []
    for sup in sorted(os.listdir(ROOT)):
        sup_dir = os.path.join(ROOT, sup)
        if not is_dir(sup_dir):
            continue

        avatar = first_existing(sup_dir, ["avatar.jpg", "avatar.png", "avatar.jpeg"])
        catalogs = []

        for cat in sorted(os.listdir(sup_dir)):
            cat_dir = os.path.join(sup_dir, cat)
            if not is_dir(cat_dir):
                continue

            cover = first_existing(cat_dir, ["cover.jpg", "cover.png", "cover.jpeg"])
            fabrics = []

            for art in sorted(os.listdir(cat_dir)):
                art_dir = os.path.join(cat_dir, art)
                if not is_dir(art_dir):
                    continue

                thumb = first_existing(art_dir, ["thumb.jpg", "thumb.png", "thumb.jpeg"])
                fabric_file = first_existing(art_dir, ["fabric.jpg", "fabric.png", "fabric.jpeg"])

                # ткань попадает в индекс, только если есть thumb И fabric
                if not thumb:
                    print(f"  ⚠️  пропуск {sup}/{cat}/{art}: нет thumb.*", file=sys.stderr)
                    continue
                if not fabric_file:
                    print(f"  ⚠️  пропуск {sup}/{cat}/{art}: нет fabric.*", file=sys.stderr)
                    continue

                fabrics.append({
                    "article": art,
                    "thumb": img_url(sup, cat, art, thumb),
                    # ИНВАРИАНТ: key == "<supplier.id>__<catalog.id>__<article>"
                    # бот склеит fabric_key из тройки order.json той же формулой →
                    # папка fabrics-src/<fabric_key>/ совпадёт. НЕ РАЗЪЕДИНЯТЬ.
                    "key": f"{sup}__{cat}__{art}",
                })

            if not fabrics:
                print(f"  ⚠️  пропуск каталога {sup}/{cat}: нет тканей", file=sys.stderr)
                continue

            catalogs.append({
                "id": cat,
                "name": read_name(cat_dir, cat),
                "cover": img_url(sup, cat, cover) if cover else None,
                "fabrics": fabrics,
            })

        if not catalogs:
            print(f"  ⚠️  пропуск поставщика {sup}: нет каталогов", file=sys.stderr)
            continue

        suppliers.append({
            "id": sup,
            "name": read_name(sup_dir, sup),
            "avatar": img_url(sup, avatar) if avatar else None,
            "catalogs": catalogs,
        })

    index = {
        "_schema": "catalog-index-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": BASE,
        "suppliers": suppliers,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    n_sup = len(suppliers)
    n_cat = sum(len(s["catalogs"]) for s in suppliers)
    n_fab = sum(len(c["fabrics"]) for s in suppliers for c in s["catalogs"])
    print(f"✅ {OUT}: поставщиков={n_sup} каталогов={n_cat} тканей={n_fab}")


if __name__ == "__main__":
    build()