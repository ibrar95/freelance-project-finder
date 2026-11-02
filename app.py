import os, re, sqlite3, hashlib, threading, time
from datetime import datetime, timezone
from urllib.parse import quote_plus
import feedparser
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "projects.db")
app = Flask(__name__)

# Public RSS/search feeds. Add or remove sources in SOURCES below.
SOURCES = [
    ("Reddit · forhire", "https://www.reddit.com/r/forhire/search.rss?q=(wordpress%20OR%20website%20OR%20SEO%20OR%20logo%20OR%20design%20OR%20writing)&restrict_sr=1&sort=new"),
    ("Reddit · hireawriter", "https://www.reddit.com/r/HireaWriter/new/.rss"),
    ("Reddit · slavelabour", "https://www.reddit.com/r/slavelabour/search.rss?q=(website%20OR%20wordpress%20OR%20design%20OR%20SEO)&restrict_sr=1&sort=new"),
    ("Reddit · DesignJobs", "https://www.reddit.com/r/DesignJobs/new/.rss"),
    ("Reddit · DoneDirtCheap", "https://www.reddit.com/r/DoneDirtCheap/search.rss?q=(design%20OR%20website%20OR%20SEO)&restrict_sr=1&sort=new"),
    ("Google News · freelance projects", "https://news.google.com/rss/search?q=" + quote_plus('"looking for" freelancer (website OR wordpress OR design OR SEO OR content)')),
    ("Google News · WordPress work", "https://news.google.com/rss/search?q=" + quote_plus('"WordPress" "looking for" freelancer OR project')),
    ("Google News · graphic design work", "https://news.google.com/rss/search?q=" + quote_plus('"graphic designer" "looking for" freelance project')),
]

KEYWORDS = {
    "Web / WordPress": ["wordpress", "website", "web developer", "web development", "landing page", "shopify", "woocommerce", "ecommerce", "web design"],
    "Graphic Design": ["logo", "branding", "brand identity", "graphic design", "flyer", "brochure", "banner", "social media design", "packaging"],
    "SEO / Marketing": ["seo", "keyword research", "on-page", "backlink", "digital marketing", "social media manager", "facebook ads", "instagram ads"],
    "Writing / Content": ["content writing", "blog", "article", "copywriting", "product description", "website content", "writer", "proofreading"],
}
EXCLUDE = ["course", "webinar", "job alert newsletter", "hiring full time", "salary package", "investment opportunity"]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, title TEXT, description TEXT, url TEXT UNIQUE,
            source TEXT, category TEXT, published TEXT, collected TEXT,
            budget TEXT DEFAULT '', status TEXT DEFAULT 'new'
        )""")

def clean_html(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)

def category_for(text):
    t = text.lower()
    for category, words in KEYWORDS.items():
        if any(w in t for w in words):
            return category
    return None

def fetch_source(name, url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProjectFinder/1.0; +https://example.com)"}
    try:
        response = requests.get(url, headers=headers, timeout=18)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        count = 0
        with db() as c:
            for e in parsed.entries[:80]:
                title = clean_html(e.get("title", ""))
                summary = clean_html(e.get("summary", e.get("description", "")))
                link = e.get("link", "")
                text = f"{title} {summary}"
                cat = category_for(text)
                if not title or not link or not cat:
                    continue
                if any(x in text.lower() for x in EXCLUDE):
                    continue
                published = e.get("published", e.get("updated", ""))
                ident = hashlib.sha256(link.encode()).hexdigest()
                c.execute("""INSERT OR IGNORE INTO projects
                    (id,title,description,url,source,category,published,collected)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (ident, title[:300], summary[:3000], link, name, cat, published, datetime.now(timezone.utc).isoformat()))
                count += c.total_changes
        return {"source": name, "ok": True, "added": count}
    except Exception as ex:
        return {"source": name, "ok": False, "error": str(ex)[:180]}

def refresh_all():
    results = [fetch_source(n, u) for n, u in SOURCES]
    return results

def background_refresh():
    while True:
        try:
            refresh_all()
        except Exception:
            pass
        time.sleep(60 * 60 * 4)

@app.route("/")
def home():
    init_db()
    return render_template("index.html")

@app.route("/api/projects")
def projects():
    init_db()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    with db() as c:
        sql = "SELECT * FROM projects WHERE 1=1"
        args = []
        if q:
            sql += " AND (title LIKE ? OR description LIKE ?)"
            args += [f"%{q}%", f"%{q}%"]
        if cat:
            sql += " AND category = ?"
            args.append(cat)
        sql += " ORDER BY COALESCE(published,'') DESC, collected DESC LIMIT 250"
        rows = [dict(x) for x in c.execute(sql, args).fetchall()]
        total = c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    return jsonify({"projects": rows, "total": total})

@app.route("/api/refresh", methods=["POST"])
def refresh():
    return jsonify({"results": refresh_all()})

@app.route("/api/status")
def status():
    init_db()
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        latest = c.execute("SELECT MAX(collected) FROM projects").fetchone()[0]
    return jsonify({"total": total, "last_refresh": latest, "sources": len(SOURCES)})

@app.route("/health")
def health():
    return {"ok": True}

init_db()
threading.Thread(target=background_refresh, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
