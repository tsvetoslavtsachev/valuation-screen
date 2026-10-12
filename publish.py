#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py — ЛИЦЕТО на оценъчния орган (мандат №29).

Детерминистичен рендер/пренос. Чете САМО (read-only) от
C:/Projects/companies/valuation-organ/cards/ и произвежда нелистнатото Pages лице
в папката, в която живее този скрипт (C:/Projects/companies/valuation-screen/):

  index.html                 <- най-новият SCREEN-YYYY-MM.html (+ noindex + навигация + vintage ред)
  cards/{TICKER}-{VARIANT}.html <- съответния .md (BASE, REVERSE, METHOD; markdown -> HTML, ДОСЛОВНО)

ПРЕДПАЗИТЕЛЯТ (ПНЛ6): тикерите идват от cards/; отказ без запис, ако REVERSE или METHOD
не е на бара на BASE. `--check` сверява вече записаното лице с органа (exit 1 при изоставане).
`--src DIR` пуска от друго копие на cards/ (чист worktree на комитнатото състояние).
  .nojekyll                  (празен)

КАРДИНАЛНО ПРАВИЛО: числата идват от органа; лицето само ги показва.
Никакво преизчисляване, съкращаване или редактиране на съдържанието.
Никакви външни ресурси (CDN/http). Никакви git операции. Органът не се пипа.
"""

import json
import os
import re
import sys
import markdown  # pinned: markdown==3.10.2 (виж доклада)

# ---------------------------------------------------------------- пътища
ORGAN_CARDS = r"C:\Projects\companies\valuation-organ\cards"   # READ-ONLY вход


def _arg_src():
    """`--src DIR` пуска от друго копие на cards/ (напр. чист git worktree на органа
    на комитнато състояние), за да не излезе чужда незавършена работа (ПНЛ6)."""
    a = sys.argv[1:]
    return os.path.abspath(a[a.index("--src") + 1]) if "--src" in a else ORGAN_CARDS


SRC = _arg_src()
OUT = os.path.dirname(os.path.abspath(__file__))     # изход = папката на скрипта
CARDS_OUT = os.path.join(OUT, "cards")

VARIANTS = ["BASE", "REVERSE"]
METHOD_HEAD = re.compile(r"^## \S+, карта по метода\s+\(винтидж ([^,)]+)[^)]*?, "
                         r"цена ([\d.]+), (\d{4}-\d{2}-\d{2})\)")


def card_pairs():
    """Тикерите се вземат от органа, не от ръчен списък (ПНЛ6): всеки тикер,
    който има и BASE, и REVERSE (.json и .md) в cards/."""
    fs = set(os.listdir(SRC))
    pat = re.compile(r"^([A-Z][A-Z0-9.]*)-REVERSE\.json$")
    out = []
    for f in sorted(fs):
        m = pat.match(f)
        if m and all(f"{m.group(1)}-{v}.{e}" in fs for v in VARIANTS for e in ("json", "md")):
            out.append(m.group(1))
    return out


def method_tickers():
    """Живите карти по метода {T}-METHOD.md; датираните копия са архив на органа."""
    pat = re.compile(r"^([A-Z][A-Z0-9.]*)-METHOD\.md$")
    return sorted(m.group(1) for f in os.listdir(SRC) if (m := pat.match(f)))


def load_card(name):
    with open(os.path.join(SRC, f"{name}.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def method_head(tk):
    """(винтидж, цена, дата) от шапката на картата по метода."""
    with open(os.path.join(SRC, f"{tk}-METHOD.md"), "r", encoding="utf-8") as f:
        m = METHOD_HEAD.match(f.readline())
    if not m:
        raise SystemExit(f"[ОТКАЗ] {tk}-METHOD.md: шапката няма „винтидж …, цена X, дата“")
    return m.group(1), m.group(2), m.group(3)


def pair_problems(tickers):
    """Двойка BASE/REVERSE на различен бар или с различна цена = разминаване.
    Картата по метода на име с BASE трябва да носи цената и датата на бара на BASE."""
    probs = []
    for tk in tickers:
        b, r = load_card(f"{tk}-BASE"), load_card(f"{tk}-REVERSE")
        if r["bar_date"] != b["D_last"] or abs(r["price"] - b["price"]) > 1e-6:
            probs.append(f"{tk}: BASE на бар {b['D_last']} (${b['price']:.2f}), "
                         f"REVERSE на бар {r['bar_date']} (${r['price']:.2f})")
    for tk in METHOD_TICKERS:
        if tk not in tickers:
            continue
        b = load_card(f"{tk}-BASE")
        _, px, d = method_head(tk)
        if (px, d) != (f"{b['price']:.2f}", b["D_last"]):
            probs.append(f"{tk}: BASE на бар {b['D_last']} (${b['price']:.2f}), "
                         f"METHOD на цена ${px}, {d}")
    return probs


def latest_vintage():
    """Най-новият SCREEN-YYYY-MM.html в органа (месечният цикъл сам мести лицето).
    Детерминистично: лексикографски максимум на YYYY-MM. Отказва при липса."""
    pat = re.compile(r"^SCREEN-(\d{4}-\d{2})\.html$")
    vs = sorted(m.group(1) for f in os.listdir(SRC) if (m := pat.match(f)))
    if not vs:
        raise SystemExit(f"[ОТКАЗ] няма SCREEN-*.html в {SRC}")
    return vs[-1]


VINTAGE = latest_vintage()
TICKERS = card_pairs()
METHOD_TICKERS = method_tickers()


def face_cards():
    """[(тикер, вариант)] за лицето: двойките BASE/REVERSE и картите по метода."""
    out = []
    for tk in sorted(set(TICKERS) | set(METHOD_TICKERS)):
        out += [(tk, v) for v in VARIANTS if tk in TICKERS]
        if tk in METHOD_TICKERS:
            out.append((tk, "METHOD"))
    return out


def card_label(tk, var):
    """(бар, етикет) на една карта: на кой бар и с кой консенсус е, прочетено от органа."""
    if var == "METHOD":
        v, px, d = method_head(tk)
        if tk in TICKERS:
            return d, f"бар {d} · конс. {v}"
        return f"vendor-{d}", f"цена на доставчика ${px} от булк {v} · картата от {d}"
    b = load_card(f"{tk}-BASE")
    if var == "BASE":
        return b["D_last"], f"бар {b['D_last']}"
    r = load_card(f"{tk}-REVERSE")
    kind = " булк" if r.get("consensus_format") else ""
    return r["bar_date"], f"бар {r['bar_date']} · конс. {r['vintage']}{kind}"


VARIANT_BG = {"BASE": "оценъчна котва", "REVERSE": "обърнатата сметка",
              "METHOD": "картата по метода"}

# ------------------------------------------------------------ стил (картон)
CARD_CSS = """
:root{
  --bg:#f9f9f7; --surface:#ffffff; --ink:#111111; --ink2:#444444; --muted:#8a8a85;
  --grid:#e2e1da; --line:#cfcec6; --accent:#2a6fc4; --codebg:#f0efec; --quote:#f3f2ee;
}
@media (prefers-color-scheme: dark){:root{
  --bg:#0d0d0d; --surface:#161615; --ink:#f2f2f0; --ink2:#c9c8c1; --muted:#8a8a85;
  --grid:#2b2b28; --line:#3a3a36; --accent:#6ba6ea; --codebg:#232320; --quote:#1b1b19;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.62 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:20px 22px 72px}
.nav{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 20px;
  padding-bottom:12px;border-bottom:1px solid var(--grid)}
.nav a{text-decoration:none;border:1px solid var(--grid);background:var(--surface);
  color:var(--ink2);border-radius:8px;padding:5px 12px;font-size:13px}
.nav a:hover{border-color:var(--ink2);color:var(--ink)}
.nav .sep{flex:1}
.card h1{font-size:22px;line-height:1.28;margin:.3em 0 .55em}
.card h2{font-size:18px;margin:1.7em 0 .5em;padding-bottom:.22em;
  border-bottom:1px solid var(--grid)}
.card h3{font-size:15px;margin:1.3em 0 .4em;color:var(--ink2)}
.card p{margin:.65em 0}
.card a{color:var(--accent)}
.card strong{color:var(--ink)}
.card code{background:var(--codebg);border-radius:4px;padding:.1em .35em;
  font:12.5px/1.4 ui-monospace,"Cascadia Code",Consolas,monospace;word-break:break-all}
.card blockquote{margin:.9em 0;padding:.5em 14px;background:var(--quote);
  border-left:3px solid var(--line);color:var(--ink2);border-radius:0 6px 6px 0}
.card blockquote p{margin:.35em 0}
.card ul,.card ol{padding-left:1.35em;margin:.65em 0}
.card li{margin:.28em 0}
.card hr{border:0;border-top:1px solid var(--grid);margin:1.9em 0}
.tablewrap{overflow-x:auto;margin:1.05em 0;border:1px solid var(--grid);
  border-radius:7px;-webkit-overflow-scrolling:touch}
.tablewrap table{border-collapse:collapse;width:100%;min-width:480px;font-size:13.5px}
.tablewrap th,.tablewrap td{border-bottom:1px solid var(--grid);
  border-right:1px solid var(--grid);padding:6px 11px;text-align:left;vertical-align:top}
.tablewrap tr>*:last-child{border-right:0}
.tablewrap tbody tr:last-child>*{border-bottom:0}
.tablewrap th{background:var(--surface);font-weight:600;color:var(--ink2);
  white-space:nowrap}
.tablewrap tbody tr:nth-child(even) td{background:rgba(128,128,128,.045)}
.foot{margin-top:34px;padding-top:12px;border-top:1px solid var(--grid);
  color:var(--muted);font-size:11.5px}
""".strip()

# --------------------------------------------- стил (навигация на скрийна)
SCREEN_NAV_CSS = """
.vsnav{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 8px}
.vsnav .vslab{color:var(--muted);font-size:12px;margin-right:2px}
.vsnav a{text-decoration:none;border:1px solid var(--grid);background:var(--surface);
  color:var(--ink2);border-radius:14px;padding:3px 11px;font-size:12px}
.vsnav a:hover{border-color:var(--ink2);color:var(--ink)}
.vsnote{color:var(--muted);font-size:11.5px;margin:0 0 14px}
""".strip()


def read_text(path):
    """Чете като текст (universal newlines -> \\n), UTF-8. Не пипа файла."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_bytes(path, text):
    """Пише детерминистично: UTF-8 байтове, без newline-транслация."""
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def wrap_tables(html):
    """Обгръща всяка <table>...</table> в скролируем контейнер (детерминистично)."""
    html = html.replace("<table>", '<div class="tablewrap"><table>')
    html = html.replace("</table>", "</table></div>")
    return html


def build_cards():
    md = markdown.Markdown(extensions=["tables"])
    cards = face_cards()
    for tk, var in cards:
        name = f"{tk}-{var}"
        body = md.reset().convert(read_text(os.path.join(SRC, f"{name}.md")))
        body = wrap_tables(body)

        bar, label = card_label(tk, var)
        siblings = "\n".join(f'<a href="{tk}-{v}.html">{tk} · {v}</a>'
                             for t, v in cards if t == tk and v != var)
        title = f"{tk} · {var} — {VARIANT_BG[var]} (Р6)"

        page = (
            "<!doctype html>\n"
            '<html lang="bg">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<meta name="robots" content="noindex, nofollow">\n'
            f'<meta name="vorgan-card" content="{name} bar={bar}">\n'
            f"<title>{title}</title>\n"
            f"<style>\n{CARD_CSS}\n</style>\n"
            "</head>\n"
            "<body>\n"
            '<div class="wrap">\n'
            '<nav class="nav">\n'
            '<a href="../index.html">&larr; Скрийн</a>\n'
            f"{siblings}\n"
            '<span class="sep"></span>\n'
            f'<span style="color:var(--muted);font-size:12px">{tk} · {var} · {label}</span>\n'
            "</nav>\n"
            '<article class="card">\n'
            f"{body}\n"
            "</article>\n"
            '<div class="foot">Лице на оценъчния уред · нелистнат уред · '
            f"тази карта: {label} · скрийнът е vintage {VINTAGE} · "
            "съдържанието е дословно копие от органа.</div>\n"
            "</div>\n"
            "</body>\n"
            "</html>\n"
        )
        write_bytes(os.path.join(CARDS_OUT, f"{name}.html"), page)


def build_index():
    src_html = os.path.join(SRC, f"SCREEN-{VINTAGE}.html")
    html = read_text(src_html)

    # 1) noindex + навигационен стил в <head>
    head_inject = (
        '<meta name="robots" content="noindex, nofollow">\n'
        f"<style>\n{SCREEN_NAV_CSS}\n</style>\n"
    )
    marker_head = "</head>"
    assert html.count(marker_head) >= 1, "липсва </head> маркер в SCREEN html"
    html = html.replace(marker_head, head_inject + marker_head, 1)

    # 2) навигация към картоните (ред на тикер, с бара и консенсуса) + vintage ред
    cards = face_cards()
    rows = []
    for tk in sorted({t for t, _ in cards}):
        vs = [v for t, v in cards if t == tk]
        links = " ".join(f'<a href="cards/{tk}-{v}.html">{tk} · {v}</a>' for v in vs)
        labs = []
        for v in vs:
            lab = card_label(tk, v)[1]
            if lab not in labs:
                labs.append(lab)
        rows.append(f'<nav class="vsnav">{links}<span class="vslab">{" | ".join(labs)}</span></nav>')
    nav_inject = (
        '\n<div class="vsnav"><span class="vslab">Картони:</span></div>\n'
        + "\n".join(rows) + "\n"
        f'<div class="vsnote">нелистнат уред · vintage {VINTAGE} · '
        "обновява се с месечния препис · всяка карта носи своя бар и консенсус</div>\n"
    )
    marker_wrap = '<body><div class="wrap">'
    assert html.count(marker_wrap) == 1, "очаквах точно един .wrap маркер в SCREEN html"
    html = html.replace(marker_wrap, marker_wrap + nav_inject, 1)

    write_bytes(os.path.join(OUT, "index.html"), html)


def face_lag():
    """Къде лицето (вече записаното в OUT) изостава от органа."""
    lag = []
    idx = os.path.join(OUT, "index.html")
    m = re.search(r"vintage (\d{4}-\d{2})", read_text(idx)) if os.path.exists(idx) else None
    face_v = m.group(1) if m else "няма"
    if face_v != VINTAGE:
        lag.append(f"скрийн: на лицето е {face_v}, най-новият в органа е {VINTAGE}")
    want_names = set()
    for tk, var in face_cards():
        want = card_label(tk, var)[0]
        want_names.add(f"{tk}-{var}.html")
        p = os.path.join(CARDS_OUT, f"{tk}-{var}.html")
        if not os.path.exists(p):
            lag.append(f"{tk}-{var}: липсва на лицето (в органа е на бар {want})")
            continue
        m = re.search(r'name="vorgan-card" content="[^"]* bar=([^"]+)"', read_text(p))
        got = m.group(1) if m else "без маркер"
        if got != want:
            lag.append(f"{tk}-{var}: на лицето е бар {got}, в органа {want}")
    if os.path.isdir(CARDS_OUT):
        for f in sorted(os.listdir(CARDS_OUT)):
            if f.endswith(".html") and f not in want_names:
                lag.append(f"{f[:-5]}: на лицето е, а в органа вече я няма")
    return lag


def main():
    """Предпазителят (ПНЛ6) върви преди всеки запис.
    `--check` само сверява лицето с органа и не пише нищо."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # кирилицата в конзола cp1252
    probs = pair_problems(TICKERS)
    if "--check" in sys.argv[1:]:
        lag = face_lag()
        for line in probs:
            print("[РАЗМИНАВАНЕ]", line)
        for line in lag:
            print("[ИЗОСТАВА]", line)
        if probs or lag:
            raise SystemExit(1)
        print(f"publish.py --check OK: лицето е в синхрон (скрийн {VINTAGE}, "
              f"{len(face_cards())} карти)")
        return
    if probs:
        for line in probs:
            print("[ОТКАЗ]", line, file=sys.stderr)
        raise SystemExit("[ОТКАЗ] карта на различен бар от BASE; нищо не е записано")
    os.makedirs(CARDS_OUT, exist_ok=True)
    build_index()
    build_cards()
    # .nojekyll (празен)
    write_bytes(os.path.join(OUT, ".nojekyll"), "")
    print("publish.py OK ->", OUT, f"(скрийн {VINTAGE}, {len(face_cards())} карти, от {SRC})")


if __name__ == "__main__":
    main()
