# Freelance Project Finder

A read-only dashboard that collects publicly accessible freelance opportunity candidates from public Reddit RSS feeds and Google News indexed search results. It does not log into platforms, bypass access controls, submit proposals, or apply to jobs.

## What the filters do

- Keeps posts with a recognizable client-side hiring/request signal.
- Rejects obvious freelancer self-promotion, including `[For Hire]` posts and service advertisements.
- Shows two payment-confidence labels:
  - `budget_confirmed`: a currency amount was found in a payment-related context.
  - `budget_discuss`: the client indicates paid work or says the budget/rate is negotiable or to be discussed.
- Excludes unpaid/volunteer posts and posts without a reliable publication date.
- Shows posts published within the last 72 hours only.
- Each card links to the original source; users must verify that the listing is still open and confirm payment details themselves.

## Source limitations

- LinkedIn, Upwork, Freelancer, PeoplePerHour, Contra and Airtasker results are discovered through public Google News/indexed search results, not direct platform APIs. Coverage is incomplete and new posts may not be indexed immediately.
- Reddit results use public RSS feeds. Feed availability and search coverage can change.
- The Source health panel shows which feeds were reached, how many entries were checked, how many passed the filters, and how many new records were stored.
- A source can be reachable but return zero matching leads. This does not prove there are no projects on that platform.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Deploy

Configured for Render with `gunicorn app:app`.

## Important

This tool only surfaces leads for manual review. It does not guarantee project availability, client legitimacy, or payment. Verify the original listing, client identity, scope, budget, deadline and payment method before accepting work. Never pay a client to receive a job.
