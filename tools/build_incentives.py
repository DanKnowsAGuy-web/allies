#!/usr/bin/env python3
"""build_incentives.py

Builds the Ally Hub "Utility incentives" door from the verified incentive-atlas cards.

  * incentives/<territory>.html  one page per card whose verdict is pass, using the card HTML
                                 from incentive-atlas/build/render_cards.py, wrapped in the hub's
                                 shell (hub colors, Archivo only, hub header, back link to the door)
  * index.html                   the INC list between the INCENTIVES:BEGIN and INCENTIVES:END
                                 markers (one row per territory, used by the door, the view
                                 and hub search). Nothing else in index.html is touched.

A card whose verdict is not pass is listed as "being checked" with no page, and a stale page
for it is removed. A page with a dash character in it is not written.

Run from anywhere, with PYTHONUTF8=1:
    python tools/build_incentives.py [--atlas PATH_TO_incentive-atlas]
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
DEFAULT_ATLAS = HUB.parent / "Energy Plus" / "incentive-atlas"
OUT = HUB / "incentives"
INDEX = HUB / "index.html"
MARK = re.compile(r"(/\* INCENTIVES:BEGIN[^\n]*\*/\r?\n)(.*?)(\r?\n/\* INCENTIVES:END \*/)", re.S)

UNKNOWN = "No confirmed demand charge on file yet, so we read it from the customer's bill."
CHECKING = "Card is being checked. It opens here once it passes."
DASHES = re.compile("[‒-―−]")
BANNED = re.compile(r"\btun(?:e|es|ed|ing)\b|energy[\s-]+(?:efficien|waste)|before you (?:spend|pay)|"
                    r"prove it before|proof before|on your own (?:meter|equipment|building)|prove every dollar", re.I)
RID = re.compile(r"\s*\[[A-Za-z0-9][^\[\]\s]*\](?!\()")

CSS = """
:root{--teal:#174e58;--teal-deep:#123e46;--teal-darker:#0e3138;--on-teal:#ffffff;--on-teal-body:#d3e2e5;
--on-teal-faint:#a9c4c9;--line-teal:rgba(255,255,255,.22);--ink:#101416;--body:#3b4347;--muted:#5a636a;
--soft:#f1f4f5;--hair:#d3d9dd;--card:#ffffff;--paper:#f3f5f6;--amber:#e0a21c;--amber-ink:#5a3f00;
--amber-wash:#fbf1d9;--font:"Archivo","Helvetica Neue",Arial,sans-serif;--r-ctl:8px;
--shadow:0 1px 0 rgba(16,20,22,.04),0 24px 48px -28px rgba(16,20,22,.45)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--teal);color:var(--on-teal);font-family:var(--font);font-size:17px;line-height:1.6;
-webkit-font-smoothing:antialiased;overflow-x:hidden;min-height:100vh}
a{color:inherit}
:focus-visible{outline:3px solid var(--amber);outline-offset:3px;border-radius:6px}
.wrap{max-width:820px;margin-inline:auto;padding-inline:16px}
header.top{padding-block:20px 16px;border-bottom:1px solid var(--line-teal)}
header.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px 16px;flex-wrap:wrap}
.brand{display:flex;align-items:center;min-height:52px;font-weight:800;font-size:30px;letter-spacing:-.02em;color:#fff;text-decoration:none}
.back{display:inline-flex;align-items:center;gap:8px;border:2px solid var(--line-teal);color:#fff;border-radius:999px;
padding:0 18px 0 12px;min-height:52px;font-size:17px;font-weight:700;text-decoration:none}
.back:hover{border-color:#fff}
.back svg{width:22px;height:22px;flex:none}
.page-h{padding:28px 0 22px}
.page-h .kicker{color:var(--on-teal-body);font-size:17px;font-weight:600}
.page-h h1{font-size:clamp(30px,6vw,42px);font-weight:800;letter-spacing:-.025em;line-height:1.15;color:#fff;margin:4px 0 6px;text-wrap:balance}
.page-h .st{display:inline-block;font-size:.5em;font-weight:700;vertical-align:.3em;margin-left:.45em;padding:.05em .5em;border-radius:6px;background:var(--amber);color:var(--ink);letter-spacing:0}
.page-h .asof{color:var(--on-teal-body);font-size:17px}
.panel{background:var(--card);color:var(--ink);border-radius:10px;box-shadow:var(--shadow);padding:4px 20px 24px}
.panel + .panel{margin-top:16px}
.cs{padding:22px 0 12px;border-bottom:1px solid var(--hair)}
.cs h2{font-size:clamp(21px,4.6vw,26px);font-weight:800;letter-spacing:-.015em;line-height:1.2;color:var(--ink);
border-left:4px solid var(--amber);padding-left:12px;text-wrap:balance}
.cs p,.cs li{max-width:68ch;margin:.65em 0;color:var(--body);overflow-wrap:break-word;text-wrap:pretty}
.cs ul{padding-left:1.2em;margin:.5em 0}
.cs strong{color:var(--ink)}
.num{font-variant-numeric:tabular-nums;color:var(--ink);font-weight:600;white-space:nowrap}
sup.rid{font-size:.8em;line-height:0;margin-left:3px}
sup.rid a{display:inline-block;font-weight:700;text-decoration:none;padding:0 6px;border-radius:4px;background:var(--amber-wash);color:var(--amber-ink)}
sup.rid a:hover,sup.rid a:focus{outline:2px solid var(--amber)}
.floorbox{margin:28px 0 0;background:var(--amber-wash);border-left:6px solid var(--amber);border-radius:8px;padding:18px 20px;color:var(--amber-ink)}
.floorbox p{margin:0;max-width:60ch;font-size:20px;font-weight:700;line-height:1.45}
.recs{padding:8px 20px 18px}
.recs summary{cursor:pointer;font-weight:700;font-size:18px;color:var(--teal);min-height:52px;display:flex;align-items:center}
.recs ol{padding-left:1.4em;color:var(--body)}
.recs li{margin:.45em 0;overflow-wrap:anywhere}
.foot{margin:32px auto 0;padding:12px 16px 60px;border-top:1px solid var(--line-teal);color:var(--on-teal-body);font-size:17px;max-width:820px}
.foot a{display:inline-flex;align-items:center;min-height:52px;color:#fff;font-weight:700;text-decoration:underline;text-decoration-color:var(--amber);text-underline-offset:4px}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
"""

LEFT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg>')


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def load_rc(atlas: Path):
    spec = importlib.util.spec_from_file_location("render_cards", atlas / "build" / "render_cards.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    return rc


def demand_line(md: str) -> str:
    m = re.search(r"^##\s+The demand charge\s*\n(.*?)(?=^##\s|\Z)", md, re.M | re.S)
    if not m:
        return UNKNOWN
    text = " ".join(RID.sub("", m.group(1)).split())
    text = re.sub(r"\*\*(.+?)\*\*|\*(.+?)\*", lambda x: x.group(1) or x.group(2), text)
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text, 1)[0].strip()
    if re.search(r"\$\s?\d", first) and re.search(r"\bk(?:W|VA)\b", first):
        return first
    return UNKNOWN


def counties(pack: dict) -> list:
    lst = ((pack.get("utility") or {}).get("service_counties") or {}).get("list") or []
    return [re.sub(r",\s*[A-Z]{2}$", "", c).strip() for c in lst if isinstance(c, str)]


def page(rc, terr: str, vj: dict, pack: dict) -> str:
    ids: list = []
    smap = rc.source_map(pack)
    labels = {rid: rc.source_label(rid, pack, smap) for rid in re.findall(r"\[([A-Za-z0-9][^\[\]\s]*)\](?!\()", vj["card_markdown"])}
    body_html, floor = rc.render_body(vj["card_markdown"], ids, labels)
    name, st = rc.utility_name(pack), rc.state_of(pack)
    stn = rc.STATES.get(st, st)
    asof = rc.long_date(vj.get("pack_built_on") or pack.get("built_on"))
    floor_html = f'<div class="floorbox" role="note"><p>{esc(floor)}</p></div>' if floor else ""
    recs = "".join(f'<li id="fn-{n}">{esc(labels.get(r) or "Source document")}</li>' for n, r in enumerate(ids, 1))
    recs_html = (f'<section class="panel recs"><details open><summary>Sources cited on this card</summary>'
                 f'<ol>{recs}</ol></details></section>') if ids else ""
    title = f"{name}, {st} | Utility incentives | Ally Hub"
    desc = f"What {name} pays in {stn}, as of {asof}."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" type="image/svg+xml" href="../favicon/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="../favicon/favicon-32.png">
<link rel="apple-touch-icon" href="../favicon/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="../index.html">Ally Hub</a>
<a class="back" href="../index.html#incentives">{LEFT}Utility incentives</a>
</div></header>
<main class="wrap">
<div class="page-h">
<p class="kicker">Utility incentives, {esc(stn)}</p>
<h1>{esc(name)}<span class="st">{esc(st)}</span></h1>
<p class="asof">As of {esc(asof)}</p>
</div>
<article class="panel">
{body_html}
{floor_html}
</article>
{recs_html}
</main>
<div class="foot"><a href="../index.html#incentives">Back to all utilities</a></div>
</body>
</html>
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default=str(DEFAULT_ATLAS))
    atlas = Path(ap.parse_args().atlas)
    rc = load_rc(atlas)
    verified, packs = atlas / "cards" / "verified", atlas / "cards" / "factpacks"
    OUT.mkdir(exist_ok=True)
    rows, problems = [], []
    for vp in sorted(verified.glob("*.json")):
        vj = json.loads(vp.read_text(encoding="utf-8"))
        terr = vj.get("territory_id") or vp.stem
        pp = packs / f"{terr}.json"
        if not pp.exists():
            problems.append(f"{terr}: no fact pack, left out")
            continue
        pack = json.loads(pp.read_text(encoding="utf-8"))
        name, st = rc.utility_name(pack), rc.state_of(pack)
        stn = rc.STATES.get(st, st)
        target = OUT / f"{terr}.html"
        ok = vj.get("verdict") == "pass"
        line = demand_line(vj["card_markdown"]) if ok else CHECKING
        if ok:
            doc = page(rc, terr, vj, pack)
            visible = re.sub(r"<[^>]+>", " ", doc.split("<body>", 1)[1])
            if DASHES.search(doc):
                problems.append(f"{terr}: dash character in output, page not written")
                ok = False
                line = CHECKING
            else:
                for m in BANNED.finditer(visible):
                    ctx = visible[max(0, m.start() - 60): m.end() + 40].replace("\n", " ")
                    problems.append(f"{terr}: check wording '{m.group(0)}' (published name?): ...{ctx.strip()}...")
                target.write_text(doc, encoding="utf-8", newline="\n")
        if not ok and target.exists():
            target.unlink()
        k = " ".join(["incentive rebate utility utilities territory demand charge financing pace county parish",
                      st, stn, name, pack.get("utility", {}).get("common_name") or ""] + counties(pack)).lower()
        rows.append({"id": terr, "st": st, "stn": stn, "name": name, "line": line, "ok": ok, "k": k})
    rows.sort(key=lambda r: (r["stn"], r["name"].lower()))
    for r in rows:
        if DASHES.search(r["line"]):
            r["line"] = r["line"] if not r["ok"] else UNKNOWN
            problems.append(f"{r['id']}: dash in demand line, replaced with the standard sentence")
    data = "const INC = [\n" + ",\n".join(
        "  " + json.dumps(r, ensure_ascii=False).replace("</", "<\\/") for r in rows) + "\n];"
    src = INDEX.read_bytes().decode("utf-8")
    if not MARK.search(src):
        raise SystemExit("INCENTIVES markers not found in index.html")
    nl = "\r\n" if "\r\n" in src else "\n"
    new = MARK.sub(lambda m: m.group(1) + data.replace("\n", nl) + m.group(3), src, count=1)
    INDEX.write_bytes(new.encode("utf-8"))
    pages = sum(r["ok"] for r in rows)
    print(f"territories {len(rows)}, pages {pages}, being checked {len(rows) - pages}")
    for p in problems:
        print("note:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
