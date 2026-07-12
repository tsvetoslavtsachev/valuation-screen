#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py — ЛИЦЕТО на оценъчния орган (мандат №29).

Детерминистичен рендер/пренос. Чете САМО (read-only) от
C:/Projects/valuation-organ/cards/ и произвежда нелистнатото Pages лице
в папката, в която живее този скрипт (C:/Projects/valuation-screen/):

  index.html                 <- SCREEN-2026-07.html (+ noindex + навигация + vintage ред)
  cards/{TICKER}-{VARIANT}.html <- съответния .md (markdown -> HTML, ДОСЛОВНО)
  .nojekyll                  (празен)

КАРДИНАЛНО ПРАВИЛО: числата идват от органа; лицето само ги показва.
Никакво преизчисляване, съкращаване или редактиране на съдържанието.
Никакви външни ресурси (CDN/http). Никакви git операции. Органът не се пипа.
"""

import os
import re
import markdown  # pinned: markdown==3.10.2 (виж доклада)

# ---------------------------------------------------------------- пътища
SRC = r"C:\Projects\valuation-organ\cards"          # READ-ONLY вход
OUT = os.path.dirname(os.path.abspath(__file__))     # изход = папката на скрипта
CARDS_OUT = os.path.join(OUT, "cards")

TICKERS = ["NVDA", "MO", "EIX"]
VARIANTS = ["BASE", "REVERSE"]

VARIANT_BG = {"BASE": "оценъчна котва", "REVERSE": "обърнатата сметка"}

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
    for tk in TICKERS:
        for var in VARIANTS:
            name = f"{tk}-{var}"
            src_md = os.path.join(SRC, f"{name}.md")
            body = md.reset().convert(read_text(src_md))
            body = wrap_tables(body)

            sibling = "REVERSE" if var == "BASE" else "BASE"
            sibling_href = f"{tk}-{sibling}.html"
            title = f"{tk} · {var} — {VARIANT_BG[var]} (Р6)"

            page = (
                "<!doctype html>\n"
                '<html lang="bg">\n'
                "<head>\n"
                '<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
                '<meta name="robots" content="noindex, nofollow">\n'
                f"<title>{title}</title>\n"
                f"<style>\n{CARD_CSS}\n</style>\n"
                "</head>\n"
                "<body>\n"
                '<div class="wrap">\n'
                '<nav class="nav">\n'
                '<a href="../index.html">&larr; Скрийн</a>\n'
                f'<a href="{sibling_href}">{tk} · {sibling}</a>\n'
                '<span class="sep"></span>\n'
                f'<span style="color:var(--muted);font-size:12px">{tk} · {var}</span>\n'
                "</nav>\n"
                '<article class="card">\n'
                f"{body}\n"
                "</article>\n"
                '<div class="foot">Лице на оценъчния орган · нелистнат уред · '
                "vintage 2026-07 · съдържанието е дословно копие от органа.</div>\n"
                "</div>\n"
                "</body>\n"
                "</html>\n"
            )
            write_bytes(os.path.join(CARDS_OUT, f"{name}.html"), page)


def build_index():
    src_html = os.path.join(SRC, "SCREEN-2026-07.html")
    html = read_text(src_html)

    # 1) noindex + навигационен стил в <head>
    head_inject = (
        '<meta name="robots" content="noindex, nofollow">\n'
        f"<style>\n{SCREEN_NAV_CSS}\n</style>\n"
    )
    marker_head = "</head>"
    assert html.count(marker_head) >= 1, "липсва </head> маркер в SCREEN html"
    html = html.replace(marker_head, head_inject + marker_head, 1)

    # 2) навигация към картоните + vintage ред, точно след отварянето на .wrap
    nav_links = "\n".join(
        f'<a href="cards/{tk}-{var}.html">{tk} · {var}</a>'
        for tk in TICKERS for var in VARIANTS
    )
    nav_inject = (
        '\n<nav class="vsnav">\n'
        '<span class="vslab">Картони:</span>\n'
        f"{nav_links}\n"
        "</nav>\n"
        '<div class="vsnote">нелистнат уред · vintage 2026-07 · '
        "обновява се с месечния препис</div>\n"
    )
    marker_wrap = '<body><div class="wrap">'
    assert html.count(marker_wrap) == 1, "очаквах точно един .wrap маркер в SCREEN html"
    html = html.replace(marker_wrap, marker_wrap + nav_inject, 1)

    write_bytes(os.path.join(OUT, "index.html"), html)


def main():
    os.makedirs(CARDS_OUT, exist_ok=True)
    build_index()
    build_cards()
    # .nojekyll (празен)
    write_bytes(os.path.join(OUT, ".nojekyll"), "")
    print("publish.py OK ->", OUT)


if __name__ == "__main__":
    main()
