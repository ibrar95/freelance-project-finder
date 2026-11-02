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

# Public RSS feeds and indexed public search results. These are NOT private platform APIs.
GOOGLE_QUERIES = [
    ("Google News · paid freelance projects", '"looking for" freelancer ("budget" OR "$" OR "paid" OR "hourly") (website OR wordpress OR design OR SEO OR writer)'),
    ("Google News · WordPress client work", '("WordPress developer needed" OR "need a WordPress website" OR "WordPress project") (budget OR paid OR "$" OR hourly)'),
    ("Google News · design client work", '("graphic designer needed" OR "need a logo designer" OR "looking for a designer") (budget OR paid OR "$" OR hourly)'),
    ("Google News · SEO client work", '("SEO expert needed" OR "looking for SEO help" OR "need an SEO specialist") (budget OR paid OR "$" OR hourly)'),
    ("Google News · writing client work", '("content writer needed" OR "looking for a copywriter" OR "need a blog writer") (budget OR paid OR "$" OR per word)'),
    ("Google News · LinkedIn public posts", 'site:linkedin.com/posts ("freelance project" OR "looking for a freelancer" OR "hiring a freelancer") (paid OR budget OR "$" OR hourly)'),
    ("Google News · LinkedIn public jobs", 'site:linkedin.com/jobs/view (freelance OR contract) (WordPress OR designer OR SEO OR writer)'),
    ("Google News · Upwork indexed listings", 'site:upwork.com/freelance-jobs/ (WordPress OR design OR SEO OR writing) (budget OR hourly)'),
    ("Google News · Freelancer indexed listings", 'site:freelancer.com/projects/ (WordPress OR design OR SEO OR writing)'),
    ("Google News · PeoplePerHour indexed listings", 'site:peopleperhour.com/freelance-jobs (WordPress OR design OR SEO OR writing)'),
    ("Google News · Contra indexed listings", 'site:contra.com (freelance project OR hire freelancer) (design OR website OR SEO)'),
    ("Google News · Airtasker indexed listings", 'site:airtasker.com/tasks (website OR design OR SEO OR writing)'),
]
SOURCES = [
    ("Reddit · forhire", "https://www.reddit.com/r/forhire/search.rss?q=(wordpress%20OR%20website%20OR%20SEO%20OR%20logo%20OR%20design%20OR%20writing)&restrict_sr=1&sort=new"),
    ("Reddit · hireawriter", "https://www.reddit.com/r/HireaWriter/new/.rss"),
    ("Reddit · DesignJobs", "https://www.reddit.com/r/DesignJobs/new/.rss"),
    ("Reddit · slavelabour", "https://www.reddit.com/r/slavelabour/search.rss?q=(website%20OR%20wordpress%20OR%20design%20OR%20SEO)&restrict_sr=1&sort=new"),
    ("Reddit · DoneDirtCheap", "https://www.reddit.com/r/DoneDirtCheap/search.rss?q=(design%20OR%20website%20OR%20SEO)&restrict_sr=1&sort=new"),
]
SOURCES += [(name, "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-US&gl=US&ceid=US:en") for name, query in GOOGLE_QUERIES]

KEYWORDS = {
    "Web / WordPress": ["wordpress", "website", "web developer", "web development", "landing page", "shopify", "woocommerce", "ecommerce", "web design"],
    "Graphic Design": ["logo", "branding", "brand identity", "graphic design", "graphic designer", "flyer", "brochure", "banner", "social media design", "packaging"],
    "SEO / Marketing": ["seo", "keyword research", "on-page", "backlink", "digital marketing", "social media manager", "facebook ads", "instagram ads"],
    "Writing / Content": ["content writing", "content writer", "blog", "article", "copywriting", "copywriter", "product description", "website content", "writer", "proofreading"],
}
# Reject editorial/search-noise, unpaid work and generic employment content.
EXCLUDE = [
    "best freelance websites", "best freelancing websites", "how to find freelancers", "how to hire freelancers",
    "top freelance websites", "freelance website list", "freelancing tips", "ultimate guide", "quick guide",
    "what is freelancing", "course", "webinar", "tutorial", "template download", "job alert newsletter",
    "volunteer", "unpaid", "no pay", "no payment", "exposure only", "commission only", "internship unpaid",
    "full-time employee", "full time employee", "salary package", "investment opportunity"
]
PROJECT_INTENT = [
    "looking for", "need a", "need an", "needed", "hiring", "hire a", "seeking", "project", "client",
    "want to build", "want someone", "who can", "can someone", "freelancer required", "freelancer wanted",
    "job post", "apply", "contract"
]
PAID_PATTERNS = [
    r"\$\s?\d", r"\b(?:usd|aud|gbp|eur|pkr)\s?\d", r"\b\d+(?:\.\d+)?\s?(?:usd|aud|gbp|eur|pkr)\b",
    r"\b(?:budget|fixed[- ]price|hourly rate|per hour|paid project|paid work|payment|paying|rate is|\$\d+|negotiable budget)\b",
    r"\b\d+(?:\.\d+)?\s?(?:/hour|per hour|an hour|per word|per article|per project)\b"
]

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

def paid_details(text):
    t = text.lower()
    if any(x in t for x in EXCLUDE):
        return False, ""
    if not any(re.search(p, t, re.I) for p in PAID_PATTERNS):
        return False, ""
    # A payment clue alone is not enough: require a likely client/project request.
    if not any(x in t for x in PROJECT_INTENT):
        return False, ""
    m = re.search(r"(?:\$\s?\d[\d,.]*(?:\s?(?:-|to)\s?\$?\d[\d,.]*)?|\b\d[\d,.]*\s?(?:USD|AUD|GBP|EUR|PKR)\b|\b(?:budget|hourly rate|fixed[- ]price|per hour|per word|negotiable budget)\b[^.;,]{0,45})", text, re.I)
    return True, (m.group(0).strip() if m else "Paid terms mentioned")

def fetch_source(name, url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FreelanceProjectFinder/2.0; +https://github.com/)"}
    try:
        response = requests.get(url, headers=headers, timeout=18)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        added = 0
        with db() as c:
            for e in parsed.entries[:100]:
                title = clean_html(e.get("title", ""))
                summary = clean_html(e.get("summary", e.get("description", "")))
                link = e.get("link", "")
                combined = f"{title} {summary}"
                cat = category_for(combined)
                is_paid, budget = paid_details(combined)
                if not title or not link or not cat or not is_paid:
                    continue
                published = e.get("published", e.get("updated", ""))
                ident = hashlib.sha256(link.encode()).hexdigest()
                cur = c.execute("""INSERT OR IGNORE INTO projects
                    (id,title,description,url,source,category,published,collected,budget)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (ident, title[:300], summary[:3000], link, name, cat, published,
                     datetime.now(timezone.utc).isoformat(), budget[:120]))
                added += cur.rowcount
        return {"source": name, "ok": True, "added": added, "checked": len(parsed.entries)}
    except Exception as ex:
        return {"source": name, "ok": False, "added": 0, "error": str(ex)[:180]}

def refresh_all():
    return [fetch_source(n, u) for n, u in SOURCES]

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
        # Recheck old database rows so previously collected articles/unpaid posts disappear.
        rows = [r for r in rows if paid_details(f"{r.get('title','')} {r.get('description','')}")[0]]
        total = len(rows)
    return jsonify({"projects": rows, "total": total})

@app.route("/api/refresh", methods=["POST"])
def refresh():
    return jsonify({"results": refresh_all()})

@app.route("/api/status")
def status():
    init_db()
    with db() as c:
        rows = c.execute("SELECT title, description FROM projects").fetchall()
        total = sum(1 for x in rows if paid_details(f"{x['title']} {x['description']}")[0])
        latest = c.execute("SELECT MAX(collected) FROM projects").fetchone()[0]
    return jsonify({"total": total, "last_refresh": latest, "sources": len(SOURCES)})

@app.route("/health")
def health():
    return {"ok": True}

init_db()
threading.Thread(target=background_refresh, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
