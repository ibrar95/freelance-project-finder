# Freelance Project Finder — Paid Leads

A Flask dashboard that collects selected **public RSS feeds and indexed public search results** for freelance opportunities in Web/WordPress, Graphic Design, SEO/Marketing and Writing/Content.

## Paid-only filter
A listing is stored only when its title/description contains (1) a payment clue such as a budget, currency amount, hourly rate, paid-work wording or per-word rate, and (2) wording that suggests a client request or project. Editorial articles, tutorials, volunteer work and explicitly unpaid opportunities are filtered out. This is a heuristic: it may miss paid posts that do not mention payment and may occasionally include ambiguous listings. Verify every original post.

## Sources and limitations
The app reads public Reddit RSS feeds and Google News RSS searches. Some Google News searches target indexed public pages from LinkedIn, Upwork, Freelancer, PeoplePerHour, Contra and Airtasker. This is **not** a direct integration with those platforms and does not provide complete coverage. It does not bypass login, CAPTCHA, paywalls, private groups or platform access controls. Feeds may be unavailable or return no results.

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
