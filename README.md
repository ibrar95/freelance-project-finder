# Freelance Project Finder — Paid Leads

A Flask dashboard that collects selected **public RSS feeds and indexed public search results** for freelance opportunities in Web/WordPress, Graphic Design, SEO/Marketing and Writing/Content.

## Paid-only filter
A listing is stored only when its title/description contains (1) a client-side hiring/request signal, (2) a payment clue, and (3) no obvious freelancer self-promotion signal. Posts marked `[For Hire]`, service advertisements, portfolio pitches and people looking for work are rejected. This is still a text-based heuristic, not a guarantee: some ambiguous posts may pass or genuine jobs may be missed. Verify the original post, budget and whether it is still open.

## Sources and limitations
The app reads public Reddit RSS feeds and Google News RSS searches. Some Google News searches target indexed public pages from LinkedIn, Upwork, Freelancer, PeoplePerHour, Contra and Airtasker. LinkedIn results depend on public pages being indexed by Google News; they may be absent or delayed, and this is not a direct LinkedIn jobs feed. This is **not** a direct integration with those platforms and does not provide complete coverage. It does not bypass login, CAPTCHA, paywalls, private groups or platform access controls. Feeds may be unavailable or return no results.

## Run locally
```bash
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`.

## Deploy on Render
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`

The app refreshes on startup and approximately every four hours while running. A manual refresh is also available. On Render Free, the service may sleep while idle; the next request wakes it. Local SQLite data may not persist across restarts/redeploys on ephemeral storage.
