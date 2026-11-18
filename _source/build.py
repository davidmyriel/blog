#!/usr/bin/env python3
"""Build davidmyriel.com from Markdown.

  python3 _source/build.py            -> builds the site into the repo root with published posts only
  python3 _source/build.py --drafts   -> also includes posts marked draft: true (for previewing)

Needs: pip install markdown
"""
import json, re, shutil, sys, html, datetime
from pathlib import Path
import markdown

ROOT = Path(__file__).parent
OUT = ROOT.parent  # site is written to the repo root
GENERATED = ["index.html", "work", "about", "newsletter", "posts", "feed.xml"]
CFG = json.loads((ROOT / "config.json").read_text())
DRAFTS = "--drafts" in sys.argv

CSS = """
:root{--fg:#1a1a1a;--muted:#6b6b6b;--line:#e6e6e6;--link:#0b63ce;--bg:#fff;--tag:#f3f4f6;--code:#f6f8fa}
@media(prefers-color-scheme:dark){:root{--fg:#e8e8e8;--muted:#9a9a9a;--line:#2c2c2c;--link:#6aa8ff;--bg:#121212;--tag:#1f1f1f;--code:#1b1b1b}}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,sans-serif;color:var(--fg);background:var(--bg);line-height:1.65;font-size:17px}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
header{border-bottom:1px solid var(--line)}.bar{max-width:760px;margin:0 auto;padding:16px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.brand{font-weight:700;color:var(--fg)}nav a{margin-left:18px;color:var(--muted);font-size:15px}nav a.on{color:var(--fg);font-weight:600}
main{max-width:760px;margin:0 auto;padding:36px 20px 80px}h1{font-size:30px;line-height:1.25;margin:0 0 10px}h2{font-size:21px;margin:36px 0 8px}
.lede{color:var(--muted);margin:0 0 28px}.hire{border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:28px 0;font-size:15.5px}
.post{display:flex;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}.post a{font-weight:600;color:var(--fg)}.post a:hover{color:var(--link)}
.desc{color:var(--muted);font-size:15px;margin-top:2px}.date{color:var(--muted);font-size:14px;white-space:nowrap;font-family:ui-monospace,monospace}
.tag{display:inline-block;background:var(--tag);border-radius:4px;padding:0 7px;font-size:12.5px;color:var(--muted);margin-right:6px}
.draft{color:#b45309;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:15px;margin:14px 0}th,td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.9em}pre{background:var(--code);padding:14px;border-radius:8px;overflow:auto}pre code{padding:0}
blockquote{border-left:3px solid var(--link);margin:20px 0;padding:2px 0 2px 16px;color:var(--muted)}
img{max-width:100%}footer{border-top:1px solid var(--line);color:var(--muted);font-size:14px;text-align:center;padding:22px}
footer a{color:var(--muted);margin:0 8px}input{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);width:260px;max-width:100%}
button{font:inherit;padding:8px 14px;border:0;border-radius:6px;background:var(--link);color:#fff;cursor:pointer}
"""

def parse(path):
    text = path.read_text()
    meta, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                elif v.lower() in ("true", "false"):
                    v = v.lower() == "true"
                meta[k.strip()] = v
        body = m.group(2)
    body = body.replace("{{email}}", CFG["email"])
    meta["html"] = markdown.markdown(body, extensions=["tables", "fenced_code"])
    meta["minutes"] = max(1, round(len(body.split()) / 230))
    return meta

def page(title, content, active="", desc=""):
    nav = [("Blog", "/", "home"), ("Work with me", "/work/", "work"),
           ("Newsletter", "/newsletter/", "newsletter"), ("About", "/about/", "about")]
    navhtml = "".join(f'<a href="{u}"{" class=on" if k == active else ""}>{n}</a>' for n, u, k in nav)
    links = "".join(f'<a href="{u}">{n}</a>' for n, u in CFG["links"].items())
    t = html.escape(title if title == CFG["name"] else f"{title} – {CFG['name']}")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{t}</title>
<meta name="description" content="{html.escape(desc or CFG['tagline'])}">
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="{CFG['name']}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><div class="bar"><a class="brand" href="/">{CFG['name']}</a><nav>{navhtml}</nav></div></header>
<main>{content}</main>
<footer>{links}<a href="/feed.xml">RSS</a><br>© {datetime.date.today().year} {CFG['name']}</footer>
</body></html>"""

HIRE = '<div class="hire">Need retrieval or agents built? I take a few consulting clients at a time. <a href="/work/">Work with me →</a></div>'

def write(rel, content):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)

def build():
    for g in GENERATED:  # only remove what this script made; topk/ and other folders are left alone
        p = OUT / g
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()

    posts = []
    for f in sorted((ROOT / "posts").glob("*.md")):
        if f.name.startswith("_"):
            continue
        p = parse(f)
        if p.get("draft") and not DRAFTS:
            continue
        p["slug"] = f.stem
        posts.append(p)
    posts.sort(key=lambda p: str(p.get("date", "")), reverse=True)

    for p in posts:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p.get("tags", []))
        flag = ' · <span class="draft">DRAFT</span>' if p.get("draft") else ""
        body = (f'<p><a href="/">← All posts</a></p><h1>{html.escape(p["title"])}</h1>'
                f'<p class="date">{p.get("date","")} · {p["minutes"]} min read{flag}</p><p>{tags}</p>'
                f'{p["html"]}{HIRE}')
        write(f"posts/{p['slug']}/index.html", page(p["title"], body, "home", p.get("description", "")))

    rows = ""
    for p in posts:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p.get("tags", []))
        d = "draft" if p.get("draft") else p.get("date", "")
        rows += (f'<div class="post"><div><a href="/posts/{p["slug"]}/">{html.escape(p["title"])}</a>'
                 f'<div class="desc">{tags}{html.escape(p.get("description",""))}</div></div>'
                 f'<div class="date">{d}</div></div>')
    if not rows:
        rows = '<p class="desc">First field report coming soon. <a href="/newsletter/">Get it by email →</a></p>'
    home = (f'<h1>{CFG["name"]}</h1><p class="lede">{html.escape(CFG["tagline"])}</p>{HIRE}'
            f'<h2>Field reports</h2>{rows}')
    if CFG.get("projects"):
        home += "<h2>Projects</h2>" + "".join(
            f'<div class="post"><div><a href="{u}">{html.escape(t)}</a><div class="desc">{html.escape(d)}</div></div></div>'
            for t, u, d in CFG["projects"])
    write("index.html", page(CFG["name"], home, "home"))

    for f in (ROOT / "pages").glob("*.md"):
        p = parse(f)
        slug = p.get("slug", f.stem)
        write(f"{slug}/index.html", page(p["title"], f'<h1>{html.escape(p["title"])}</h1>{p["html"]}', slug))

    action = CFG.get("newsletter_form_action")
    if action:
        form = (f'<form action="{action}" method="post" target="_blank">'
                '<input type="email" name="email" placeholder="you@company.com" required> <button>Subscribe</button></form>')
    else:
        form = f'<p>Email <strong>{CFG["email"]}</strong> with "subscribe" and I\'ll add you.</p>'
    write("newsletter/index.html", page("Newsletter",
          f'<h1>Newsletter</h1><p>One field report when I have something worth sending. No filler.</p>{form}', "newsletter"))

    items = "".join(
        f"<item><title>{html.escape(p['title'])}</title><link>https://{CFG['domain']}/posts/{p['slug']}/</link>"
        f"<guid>https://{CFG['domain']}/posts/{p['slug']}/</guid><description>{html.escape(p.get('description',''))}</description></item>"
        for p in posts if not p.get("draft"))
    write("feed.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{CFG["name"]}</title>'
          f'<link>https://{CFG["domain"]}/</link><description>{html.escape(CFG["tagline"])}</description>{items}</channel></rss>')
    print(f"Built {len(posts)} post(s) into {OUT}" + (" (drafts included)" if DRAFTS else ""))

if __name__ == "__main__":
    build()
