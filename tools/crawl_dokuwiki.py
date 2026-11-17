#!/usr/bin/env python3
"""Static, read-only snapshot of a DokuWiki (stdlib only; runs on the old server).

  python3 crawl_dokuwiki.py http://127.0.0.1:8090 /var/www/dokuwiki/data/pages /root/dw-static \
          "Melonia Civic Society" melonia-wiki.osolia.xyz

Pages are saved as /<ns>/<page>/index.html, media as /_media/<ns>/<file>.
"""
import hashlib
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE, PAGES, OUT, SITENAME, DOMAIN = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
SKIP_NS = ("wiki/", "playground/")
SKIP_PAGES = {"sidebar"}
BAD = re.compile(r'[<>:"|?*\\]')
OUT.mkdir(parents=True, exist_ok=True)
assets, failed = {}, []


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "archive-crawler", "Host": DOMAIN})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Content-Type", "")


ids = []
for f in sorted(PAGES.rglob("*.txt")):
    rel = f.relative_to(PAGES).as_posix()[:-4]
    if rel.startswith(SKIP_NS) or rel in SKIP_PAGES:
        continue
    ids.append(rel)  # slash form == URL form with useslash
idset = set(ids)
print(f"{len(ids)} pages to fetch")


def page_href(i):
    return "/" + urllib.parse.quote(i) + "/"


def safe(name):
    return "/".join(BAD.sub("_", p) for p in name.split("/"))


def fetch_asset(url):
    if url in assets:
        return assets[url]
    sp = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(sp.path)
    q = urllib.parse.parse_qs(sp.query)
    if path.startswith("/_detail/"):                       # detail page -> just the file
        return fetch_asset("/_media/" + path[len("/_detail/"):])
    if path == "/lib/exe/fetch.php" and "media" in q:      # normalise to /_media/
        extra = {k: v[0] for k, v in q.items() if k in ("w", "h", "tok")}
        return fetch_asset("/_media/" + q["media"][0] + ("?" + urllib.parse.urlencode(extra) if extra else ""))
    if path.endswith("css.php"):  # core and template stylesheets must end in .css to get a CSS content type
        name = "_static/css-" + hashlib.sha1(url.encode()).hexdigest()[:12] + ".css"
    elif path.startswith("/_media/"):
        media = path[len("/_media/"):].replace(":", "/")
        stem, dot, ext = media.rpartition(".")
        size = {k: v[0] for k, v in q.items() if k in ("w", "h")}
        suffix = ("-" + "x".join(size.get(k, "") for k in ("w", "h"))) if size else ""
        name = "_media/" + (f"{stem}{suffix}.{ext}" if dot else media + suffix)
    else:
        name = path.lstrip("/") + (("-" + hashlib.sha1(sp.query.encode()).hexdigest()[:8]) if sp.query else "")
    name = safe(name)
    assets[url] = "/" + urllib.parse.quote(name)
    try:
        body, ctype = get(BASE + url)
    except Exception as e:
        failed.append(f"{url}: {e}")
        return assets[url]
    if name.endswith(".css") or "text/css" in ctype:
        css = body.decode("utf-8", "replace")
        base_dir = path.rsplit("/", 1)[0] + "/"

        def css_url(m):
            u = m.group(2).strip()
            if u.startswith(("data:", "http:", "https:", "#")):
                return m.group(0)
            return f"url({m.group(1)}{fetch_asset(urllib.parse.urljoin(base_dir, u))}{m.group(1)})"
        body = re.sub(r"url\((['\"]?)([^'\")]+)\1\)", css_url, css).encode()
    dst = OUT / urllib.parse.unquote(assets[url].lstrip("/"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(body)
    return assets[url]


HIDE = """<style id="archive-overrides">
a[href*="do="],form.search,#dw__search,.search,.mikio-search,.editbutton_section,.btn_secedit,.secedit,
#dw__pagetools,.mikio-page-tools,.mikio-article-tools,.user-tools,#dokuwiki__usertools,.mikio-user-tools,
.docInfo,.mikio-footer-docinfo{display:none!important}
.archive-banner{background:#fff6dc;color:#5a4300;border:1px solid #f0d98a;padding:8px 12px;margin:0 0 12px;font-size:14px;border-radius:4px}
</style>"""
BANNER = (f'<div class="archive-banner"><strong>Read-only archive.</strong> This is a static copy of '
          f'{SITENAME} ({DOMAIN}). Editing, search and page history are not available.</div>')
ATTR = re.compile(r'(\s(?:href|src))="([^"]*)"')
SRCSET = re.compile(r'\ssrcset="([^"]*)"')
SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)


def rewrite(html):
    html = SCRIPT.sub("", html)

    def fix(url):
        raw = url.replace("&amp;", "&")
        if raw.startswith(("http://", "https://", "//")):
            sp = urllib.parse.urlsplit(raw if not raw.startswith("//") else "https:" + raw)
            if sp.netloc != DOMAIN and sp.netloc != urllib.parse.urlsplit(BASE).netloc:
                return url
            raw = sp.path + ("?" + sp.query if sp.query else "") + ("#" + sp.fragment if sp.fragment else "")
        if not raw.startswith("/"):
            return url
        path, _, frag = raw.partition("#")
        p, _, query = path.partition("?")
        if p.startswith(("/_media/", "/_detail/", "/lib/")) and "js.php" not in p:
            return fetch_asset(path)
        pid = urllib.parse.unquote(p).strip("/").replace(":", "/")
        if p in ("/", "/doku.php") and not query:
            return "/" + ("#" + frag if frag else "")
        if pid in idset and "do=" not in query:
            return page_href(pid) + ("#" + frag if frag else "")
        return url

    html = ATTR.sub(lambda m: f'{m.group(1)}="{fix(m.group(2))}"', html)
    html = SRCSET.sub(lambda m: ' srcset="' + ", ".join(
        " ".join([fix(part.split()[0])] + part.split()[1:]) for part in m.group(1).split(",") if part.strip()) + '"', html)
    html = html.replace("</head>", HIDE + "\n</head>", 1)
    for anchor in (r'(<div class="page[^"]*"[^>]*>)', r'(<article\b[^>]*>)', r'(<main\b[^>]*>)', r'(<body\b[^>]*>)'):
        if re.search(anchor, html):
            html = re.sub(anchor, r"\1" + BANNER, html, count=1)
            break
    return html


REDIR = re.compile(r"~~REDIRECT>([^~]+)~~")
for n, i in enumerate(ids, 1):
    m = REDIR.search((PAGES / (i + ".txt")).read_text(encoding="utf-8", errors="replace"))
    if m:  # redirect plugin page -> static forwarding stub
        target = page_href(m.group(1).strip().replace(":", "/"))
        dst = OUT / safe(i) / "index.html"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(f'<!doctype html><meta charset="utf-8"><title>Redirecting…</title>'
                       f'<meta http-equiv="refresh" content="0; url={target}"><a href="{target}">Continue</a>', encoding="utf-8")
        continue
    try:
        body, _ = get(BASE + "/" + urllib.parse.quote(i))
    except Exception as e:
        failed.append(f"{i}: {e}")
        continue
    html = rewrite(body.decode("utf-8", "replace"))
    dst = OUT / safe(i) / "index.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(html, encoding="utf-8")
    if i == "home":
        (OUT / "index.html").write_text(html, encoding="utf-8")
    if n % 25 == 0:
        print(f"  {n}/{len(ids)}")

(OUT / "404.html").write_text("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Not in the archive</title><script>
(function(){var p=location.pathname,q=new URLSearchParams(location.search),id=q.get('id');
if(p==='/doku.php'&&id){location.replace('/'+id.replace(/:/g,'/')+'/');return;}
if(p.indexOf(':')>-1){location.replace(p.replace(/:/g,'/').replace(/\\/?$/,'/'));return;}
if(!/\\/$/.test(p)&&!/\\.[a-z0-9]+$/i.test(p)){location.replace(p+'/');}})();
</script><style>body{font:16px/1.5 system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px}</style></head>
<body><h1>Not in the archive</h1><p>This page of """ + SITENAME + """ wasn't kept. Editing, page history,
search and the site index were not archived.</p><p><a href="/">Go to the start page</a></p></body></html>""", encoding="utf-8")
(OUT / "CNAME").write_text(DOMAIN + "\n")
(OUT / ".nojekyll").write_text("")
print(f"pages: {len(ids)}  assets: {len(assets)}  failed: {len(failed)}")
for f in failed[:30]:
    print("  FAIL", f)
