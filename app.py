import os, re, sqlite3, hashlib, threading, time, random, html
from collections import Counter
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import feedparser
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_AGE_DAYS = 7  # Default and storage window: seven days.
DB_PATH = os.environ.get("DB_PATH", os.path.join(APP_DIR, "projects.db"))
REFRESH_MINUTES = max(30, int(os.environ.get("REFRESH_MINUTES", "60")))
HTTP = requests.Session()
app = Flask(__name__)

# Public RSS feeds and indexed public search results. These are NOT private platform APIs.
GOOGLE_QUERIES = [
    ("Google News · paid freelance projects", '"looking for" freelancer ("budget" OR "$" OR "paid" OR "hourly") (website OR wordpress OR design OR SEO OR writer)'),
    ("Google News · WordPress client work", '("WordPress developer needed" OR "need a WordPress website" OR "WordPress project") (budget OR paid OR "$" OR hourly)'),
    ("Google News · design client work", '("graphic designer needed" OR "need a logo designer" OR "looking for a designer") (budget OR paid OR "$" OR hourly)'),
    ("Google News · SEO client work", '("SEO expert needed" OR "looking for SEO help" OR "need an SEO specialist") (budget OR paid OR "$" OR hourly)'),
    ("Google News · writing client work", '("content writer needed" OR "looking for a copywriter" OR "need a blog writer") (budget OR paid OR "$" OR per word)'),
    ("Google News · LinkedIn public posts", 'site:linkedin.com/posts ("I am hiring" OR "we are hiring" OR "looking to hire" OR "need a WordPress developer" OR "need a designer" OR "looking for a freelancer" OR "freelancer required") (WordPress OR website OR design OR SEO OR writer)'),
    ("Google News · LinkedIn public jobs", 'site:linkedin.com/jobs/view (freelance OR contract OR "part-time") (WordPress OR developer OR designer OR SEO OR writer) (hiring OR remote OR project)'),
    ("Google News · Upwork indexed listings", 'site:upwork.com/freelance-jobs/ (WordPress OR design OR SEO OR writing) (budget OR hourly)'),
    ("Google News · Freelancer indexed listings", 'site:freelancer.com/projects/ (WordPress OR design OR SEO OR writing)'),
    ("Google News · PeoplePerHour indexed listings", 'site:peopleperhour.com/freelance-jobs (WordPress OR design OR SEO OR writing)'),
    ("Google News · Contra indexed listings", 'site:contra.com (freelance project OR hire freelancer) (design OR website OR SEO)'),
    ("Google News · LinkedIn video editors", 'site:linkedin.com/posts/ ("hiring video editor" OR "looking for video editor" OR "need a video editor" OR "video editor needed") (freelance OR paid OR project OR contract)'),
    ("Google News · LinkedIn remote design", 'site:linkedin.com/jobs/view/ ("graphic designer" OR "brand designer" OR "video editor") (remote OR contract OR freelance)'),
    ("Google News · LinkedIn remote web", 'site:linkedin.com/jobs/view/ ("wordpress developer" OR "shopify developer" OR "web designer") (remote OR freelance OR contract)'),
    ("Google News · LinkedIn remote marketing", 'site:linkedin.com/jobs/view/ ("SEO specialist" OR "digital marketing" OR "content writer") (remote OR freelance OR contract)'),
    ("Google News · video editing clients", '("video editor needed" OR "hiring video editor" OR "looking for video editor") (paid OR budget OR freelance OR contract)'),
    ("Google News · Airtasker indexed listings", 'site:airtasker.com/tasks (website OR design OR SEO OR writing)'),
]
SOURCES = [
    ("Reddit · forhire", "https://www.reddit.com/r/forhire/new/.rss"),
    ("Reddit · hireawriter", "https://www.reddit.com/r/HireaWriter/new/.rss"),
    ("Reddit · DesignJobs", "https://www.reddit.com/r/DesignJobs/new/.rss"),
    ("Reddit · slavelabour", "https://www.reddit.com/r/slavelabour/new/.rss"),
    ("Reddit · DoneDirtCheap", "https://www.reddit.com/r/DoneDirtCheap/new/.rss"),
]
SOURCES += [(name, "https://news.google.com/rss/search?q=" + quote_plus(query + " when:7d") + "&hl=en-US&gl=US&ceid=US:en") for name, query in GOOGLE_QUERIES]

# Public, documented job-board endpoints; no account login or scraping.
API_SOURCES = [
    ("Remotive · remote jobs", "https://remotive.com/api/remote-jobs?limit=100"),
    ("Arbeitnow · remote jobs", "https://www.arbeitnow.com/api/job-board-api"),
]
SOURCES += API_SOURCES

KEYWORDS = {
    "Web / WordPress": ["wordpress", "website", "web developer", "web development", "landing page", "shopify", "woocommerce", "ecommerce", "web design"],
    "Graphic Design": ["logo", "branding", "brand identity", "graphic design", "graphic designer", "flyer", "brochure", "banner", "social media design", "packaging"],
    "SEO / Marketing": ["seo", "keyword research", "on-page", "backlink", "digital marketing", "social media manager", "facebook ads", "instagram ads"],
    "Video Editing": ["video editing", "video editor", "video production", "youtube shorts", "youtube editor", "reels editor", "short-form video", "short form video", "tiktok editor", "podcast editing", "motion graphics", "premiere pro", "after effects", "video captions"],
    "Writing / Content": ["content writing", "content writer", "blog", "article", "copywriting", "copywriter", "product description", "website content", "writer", "proofreading"],
}
# Classification is deliberately split into client intent and payment confidence.
# Public feeds contain both buyers and sellers; title-level seller signals take priority.
EXCLUDE = [
    "best freelance websites", "best freelancing websites", "how to find freelancers", "how to hire freelancers",
    "top freelance websites", "freelance website list", "freelancing tips", "ultimate guide", "quick guide",
    "what is freelancing", "course", "webinar", "tutorial", "template download", "job alert newsletter",
    "volunteer", "unpaid", "no pay", "no payment", "exposure only", "commission only", "internship unpaid",
    "full-time employee", "full time employee", "investment opportunity"
]
SELLER_TITLE_PATTERNS = [
    r"^\s*\[\s*for hire\s*\]", r"^\s*\[\s*available for hire\s*\]", r"^\s*\[\s*services?\s*\]",
    r"^\s*for hire\b", r"^\s*i(?:'m| am) (?:a |an )?(?:freelancer|designer|developer|writer|agency)\b"
]
SELLER_BODY_PATTERNS = [
    r"\bi offer\b", r"\bi provide\b", r"\bmy services\b", r"\bmy portfolio\b",
    r"\blooking for work\b", r"\blooking for clients\b", r"\bseeking clients\b",
    r"\bavailable immediately\b", r"\bhire me\b", r"\bmy rate(?:s)?\b", r"\brates start\b",
    r"\bstarting at \$", r"\bfeel free to dm if (?:you|anyone) (?:need|want)",
    r"\bi can (?:help|build|design|create|make|write|redesign) (?:you|your)\b"
]
CLIENT_INTENT_PATTERNS = [
    r"\[\s*hiring\s*\]", r"\[\s*job\s*\]", r"\bwe(?:'re| are) hiring\b", r"\bi(?:'m| am) hiring\b",
    r"\blooking to hire\b", r"\blooking for (?:a |an )?(?:freelancer|developer|designer|writer|editor|videographer|agency|virtual assistant)\b",
    r"\bneed (?:a |an |someone|help|someone to)\b", r"\b(?:developer|designer|writer|video editor|seo specialist|wordpress expert|virtual assistant) needed\b",
    r"\bseeking (?:a |an )?(?:freelancer|developer|designer|writer|video editor|contractor)\b",
    r"\bfreelancer required\b", r"\bfreelancer wanted\b", r"\bclient is looking for\b",
    r"\bcan someone (?:build|design|develop|write|help|create)\b", r"\bwho can (?:build|design|develop|write)\b",
    r"\bneed someone to\b", r"\blooking for someone to\b", r"\bproject for (?:a|an) freelancer\b",
    r"\bcommissioning (?:a|an)\b", r"\bseeking applications\b", r"\bjob opening\b",
    r"\bwant to hire\b", r"\bwe need (?:a |an )?(?:developer|designer|writer|video editor|freelancer|wordpress|website)\b"
]
PAYMENT_PATTERNS = [
    r"\$\s?\d[\d,.]*(?:\s?(?:-|to)\s?\$?\d[\d,.]*)?",
    r"\b(?:usd|aud|gbp|eur|pkr)\s?\d[\d,.]*",
    r"\b(?:budget|fixed[- ]price|hourly rate|per hour|paid project|paid work|payment|paying|compensation|salary|rate is|budget is)\b",
    r"\b\d+(?:\.\d+)?\s?(?:/hour|per hour|an hour|per word|per article|per project)\b"
]
NEGOTIABLE_PATTERNS = [
    r"\bbudget (?:is )?(?:negotiable|flexible|to be discussed|open)\b",
    r"\b(?:rate|payment|compensation) (?:is )?(?:negotiable|flexible|to be discussed)\b",
    r"\bpaid (?:freelance|project|contract|work)\b", r"\bopen to (?:discussing|negotiating) (?:the )?(?:budget|rate|payment)\b",
    r"\bcompetitive (?:pay|rate|compensation)\b", r"\bwill pay\b", r"\bpayment provided\b"
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
        c.execute("""CREATE TABLE IF NOT EXISTS source_runs (
            source TEXT PRIMARY KEY, checked_at TEXT, ok INTEGER, checked INTEGER DEFAULT 0,
            accepted INTEGER DEFAULT 0, rejected INTEGER DEFAULT 0,
            added INTEGER DEFAULT 0, error TEXT DEFAULT ''
        )""")
        columns = {row[1] for row in c.execute("PRAGMA table_info(source_runs)").fetchall()}
        if "accepted" not in columns:
            c.execute("ALTER TABLE source_runs ADD COLUMN accepted INTEGER DEFAULT 0")
        if "rejected" not in columns:
            c.execute("ALTER TABLE source_runs ADD COLUMN rejected INTEGER DEFAULT 0")
        for column in ("stale", "duplicate", "undated"):
            if column not in columns:
                c.execute(f"ALTER TABLE source_runs ADD COLUMN {column} INTEGER DEFAULT 0")

def parse_published(value, parsed_tuple=None):
    """Return an aware UTC datetime; unknown dates are rejected for freshness."""
    if parsed_tuple:
        try:
            return datetime(*parsed_tuple[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    if value:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None

def is_fresh(value, parsed_tuple=None, days=MAX_AGE_DAYS):
    published_dt = parse_published(value, parsed_tuple)
    if not published_dt:
        return False
    now = datetime.now(timezone.utc)
    return now - timedelta(hours=1) <= published_dt <= now + timedelta(minutes=15) or (published_dt <= now + timedelta(minutes=15) and now - published_dt <= timedelta(days=days))

def clean_html(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)

def category_for(text):
    t = text.lower()
    for category, words in sorted(KEYWORDS.items(), key=lambda kv: 0 if kv[0] == "Video Editing" else 1):
        if any(w in t for w in words):
            return category
    return None

def classify_lead(title, description):
    """Return (accepted, budget_label, confidence_status, reason)."""
    title = title or ""
    description = description or ""
    combined = f"{title} {description}"
    t = combined.lower()
    title_l = title.lower()
    if any(x in t for x in EXCLUDE):
        return False, "", "rejected", "unpaid_or_noise"

    # A clear [For Hire] title is a seller advertisement, even if it quotes a price.
    if any(re.search(p, title_l, re.I) for p in SELLER_TITLE_PATTERNS):
        return False, "", "rejected", "seller_advertisement"

    client_signal = any(re.search(p, t, re.I) for p in CLIENT_INTENT_PATTERNS)
    # Relaxed mode: accept clear buyer project requests even without formal "hiring" phrasing.
    project_request = bool(re.search(
        r"\b(?:need|looking for|seeking|wanted|require|required|help with|project for|contract for)\b.{0,95}"
        r"(?:website|wordpress|shopify|logo|branding|design|seo|marketing|copywriting|content|writer|video|editor|reels|youtube|developer|freelancer)\b"
        r"|\b(?:website|wordpress|shopify|logo|branding|design|seo|marketing|copywriting|content|video|editing)\b.{0,65}"
        r"(?:needed|required|wanted|project|contract|freelance gig)\b", t, re.I))
    if not (client_signal or project_request):
        return False, "", "rejected", "no_client_hiring_signal"

    # Reject self-promotion when seller language dominates and there is no explicit hiring title.
    explicit_hiring_title = bool(re.search(r"^\s*\[\s*(?:hiring|job)\s*\]", title_l, re.I))
    seller_signal = any(re.search(p, description.lower(), re.I) for p in SELLER_BODY_PATTERNS)
    if seller_signal and not explicit_hiring_title:
        return False, "", "rejected", "seller_self_promotion"

    amount = re.search(r"(?:\$\s?\d[\d,.]*(?:\s?(?:-|to)\s?\$?\d[\d,.]*)?|\b\d[\d,.]*\s?(?:USD|AUD|GBP|EUR|PKR)\b)", combined, re.I)
    paid_signal = any(re.search(p, t, re.I) for p in PAYMENT_PATTERNS)
    negotiable_signal = any(re.search(p, t, re.I) for p in NEGOTIABLE_PATTERNS)
    if not (paid_signal or negotiable_signal):
        # No invented budget: mark a genuine buyer request as needing verification.
        return True, "Budget not stated — confirm with client", "potential_lead", "client_request_budget_unknown"

    # Avoid accepting unrelated business metrics (e.g. ad spend/ROAS) as the project budget.
    if amount:
        around = t[max(0, amount.start()-80):min(len(t), amount.end()+80)]
        nearby_payment = any(x in around for x in ["budget", "pay", "paid", "rate", "hour", "per project", "compensation", "salary", "payment", "fixed-price", "fixed price"])
        if not nearby_payment and not negotiable_signal:
            return True, "Budget not confirmed — verify with client", "potential_lead", "unrelated_amount_not_budget"

    if amount:
        budget = amount.group(0).strip()
        return True, budget, "budget_confirmed", "client_hiring_with_amount"
    if negotiable_signal:
        return True, "Budget/rate negotiable — confirm with client", "budget_discuss", "client_hiring_budget_discussion"
    m = re.search(r"\b(?:budget|hourly rate|fixed[- ]price|per hour|per word|paid work|paid project)\b[^.;,]{0,55}", combined, re.I)
    return True, (m.group(0).strip() if m else "Payment mentioned — verify details"), "budget_discuss", "client_hiring_payment_clue"

# Backwards-compatible wrapper for existing filtering call sites.
def paid_details(text):
    ok, budget, status, _ = classify_lead(text, text)
    return ok, budget

def save_candidate(c, name, title, summary, link, published, category=None, paid_hint="", job_listing=False):
    """Persist verified-dated leads. Never invent a budget or a publication date."""
    title, summary = clean_html(title), clean_html(summary)
    category = category or category_for(f"{title} {summary}")
    if not title or not link or not category:
        return "rejected"
    if job_listing:
        # A remote job is not automatically a freelance client project.
        if not re.search(r"\b(freelance|contract|contractor|temporary|project.based|part.time)\b", f"{title} {summary}", re.I):
            return "rejected"
        if not paid_hint:
            paid_hint = "Budget not stated — confirm with client"
        if any(re.search(p, title.lower(), re.I) for p in SELLER_TITLE_PATTERNS):
            return "rejected"
        budget, lead_status = paid_hint, ("potential_lead" if "not stated" in paid_hint else "budget_discuss")
        if re.search(r"(?:\$|\bUSD\b|\bAUD\b|\bEUR\b|\bGBP\b)\s*\d", paid_hint, re.I):
            lead_status = "budget_confirmed"
    else:
        accepted, budget, lead_status, _ = classify_lead(title, summary)
        if not accepted:
            return "rejected"
    dt = parse_published(published)
    if not dt:
        return "undated"
    if not is_fresh(published):
        return "stale"
    ident = hashlib.sha256(link.encode()).hexdigest()
    cur = c.execute("""INSERT OR IGNORE INTO projects
        (id,title,description,url,source,category,published,collected,budget,status)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", (ident, title[:300], summary[:3000], link, name, category,
        dt.isoformat(), datetime.now(timezone.utc).isoformat(), budget[:120], lead_status))
    return "new" if cur.rowcount else "duplicate"


def fetch_source(name, url):
    counts = Counter()
    try:
        response = HTTP.get(url, headers={"User-Agent": "FreelanceProjectFinder/3.0 (public job discovery; contact via GitHub)"}, timeout=18)
        response.raise_for_status()
        entries = []
        if name.startswith("Remotive"):
            for job in response.json().get("jobs", []):
                entries.append((job.get("title", ""), job.get("description", ""), job.get("url", ""),
                                job.get("publication_date", ""), job.get("salary", ""), True,
                                " ".join([str(job.get("job_type", "")), str(job.get("candidate_required_location", ""))])))
        elif name.startswith("Arbeitnow"):
            for job in response.json().get("data", []):
                date = datetime.fromtimestamp(job["created_at"], timezone.utc).isoformat() if job.get("created_at") else ""
                entries.append((job.get("title", ""), job.get("description", ""), job.get("url", ""),
                                date, job.get("salary", "") or "", True,
                                " ".join(str(x) for x in job.get("tags", []))))
        else:
            parsed = feedparser.parse(response.content)
            for e in parsed.entries[:100]:
                date = e.get("published", e.get("updated", ""))
                parsed_dt = parse_published(date, e.get("published_parsed", e.get("updated_parsed")))
                entries.append((e.get("title", ""), e.get("summary", e.get("description", "")),
                                e.get("link", ""), parsed_dt.isoformat() if parsed_dt else date,
                                "", False, ""))
        with db() as c:
            for title, summary, link, published, salary, job_listing, extra in entries:
                # Preserve location/contract information to allow users to check eligibility.
                summary = f"{extra} {summary}" if extra else summary
                result = save_candidate(c, name, title, summary, link, published, paid_hint=str(salary), job_listing=job_listing)
                counts[result] += 1
            checked = len(entries)
            c.execute("""INSERT OR REPLACE INTO source_runs
                (source,checked_at,ok,checked,accepted,rejected,added,error,stale,duplicate,undated)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (name, datetime.now(timezone.utc).isoformat(), 1, checked,
                 checked-counts["rejected"], counts["rejected"], counts["new"], "",
                 counts["stale"], counts["duplicate"], counts["undated"]))
        return {"source": name, "ok": True, "added": counts["new"], "checked": checked}
    except Exception as ex:
        error = str(ex)[:180]
        with db() as c:
            c.execute("""INSERT OR REPLACE INTO source_runs
                (source,checked_at,ok,checked,accepted,rejected,added,error,stale,duplicate,undated)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (name, datetime.now(timezone.utc).isoformat(), 0, 0, 0, 0, 0, error, 0, 0, 0))
        return {"source": name, "ok": False, "added": 0, "error": error}

refresh_lock = threading.Lock()
def refresh_all():
    # Avoid simultaneous refreshes from web requests and the scheduler.
    if not refresh_lock.acquire(blocking=False):
        return [{"source": "Scheduler", "ok": False, "added": 0, "error": "Refresh already running"}]
    try:
        results = [fetch_source(n, u) for n, u in SOURCES]
        with db() as c:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS + 2)).isoformat()
            c.execute("DELETE FROM projects WHERE collected < ?", (cutoff,))
        return results
    finally:
        refresh_lock.release()

def background_refresh():
    while True:
        try:
            refresh_all()
        except Exception:
            pass
        time.sleep(REFRESH_MINUTES * 60)

@app.route("/")
def home():
    init_db()
    return render_template("index.html")

@app.route("/api/projects")
def projects():
    init_db()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    days = 3 if request.args.get("days") == "3" else 7
    with db() as c:
        sql = "SELECT * FROM projects WHERE 1=1"
        args = []
        if q:
            sql += " AND (title LIKE ? OR description LIKE ?)"
            args += [f"%{q}%", f"%{q}%"]
        if cat:
            sql += " AND category = ?"
            args.append(cat)
        rows = [dict(x) for x in c.execute(sql, args).fetchall()]
        # Recheck rows using title-aware buyer/seller classification and selected window.
        filtered = []
        for r in rows:
            ok, budget, lead_status, _reason = classify_lead(r.get('title', ''), r.get('description', ''))
            if (ok or r.get('source', '').startswith(('Remotive', 'Arbeitnow'))) and is_fresh(r.get('published', ''), days=days):
                r['budget'] = r.get('budget') or budget
                r['status'] = r.get('status') if r.get('source', '').startswith(('Remotive', 'Arbeitnow')) else lead_status
                filtered.append(r)
        rows = filtered
        rows.sort(key=lambda r: parse_published(r.get('published', '')) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        rows = rows[:250]
        total = len(rows)
    return jsonify({"projects": rows, "total": total, "max_age_days": days})

@app.route("/api/refresh", methods=["POST"])
def refresh():
    return jsonify({"results": refresh_all()})

@app.route("/api/status")
def status():
    init_db()
    with db() as c:
        rows = c.execute("SELECT title, description, published FROM projects").fetchall()
        total = sum(1 for x in rows if is_fresh(x['published'], days=7))
        latest = c.execute("SELECT MAX(checked_at) FROM source_runs").fetchone()[0]
        runs = [dict(x) for x in c.execute("SELECT source, checked_at, ok, checked, accepted, rejected, added, error, stale, duplicate, undated FROM source_runs ORDER BY source").fetchall()]
    return jsonify({"total": total, "last_refresh": latest, "sources": len(SOURCES), "max_age_days": MAX_AGE_DAYS, "source_runs": runs})

@app.route("/health")
def health():
    return {"ok": True}

init_db()
# Starts automatically on each running web instance. Free hosting may sleep,
# so continuous refresh requires an always-on service or an external scheduler.
if os.environ.get("ENABLE_BACKGROUND_REFRESH", "1") == "1":
    threading.Thread(target=background_refresh, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
