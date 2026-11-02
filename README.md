# Freelance Project Finder

A deployable Flask dashboard that collects publicly accessible project leads from RSS feeds and displays them in one searchable page.

## Included sources
- Reddit public RSS feeds: r/forhire, r/HireaWriter, r/slavelabour, r/DesignJobs, r/DoneDirtCheap
- Google News RSS public index queries for web/WordPress, graphic design and freelance opportunities

## Run locally
1. Install Python 3.10+.
2. In this folder run:
   `python -m venv .venv`
3. Activate the environment, then:
   `pip install -r requirements.txt`
4. Run:
   `python app.py`
5. Open `http://127.0.0.1:5000`

The app refreshes feeds every four hours while running. Use the Refresh button for a manual refresh.

## Deploy a public link on Render
1. Create a GitHub repository and upload all files in this folder.
2. Sign in to Render and choose **New + → Blueprint**.
3. Select the GitHub repository containing `render.yaml`.
4. Deploy. Render will provide the public `onrender.com` URL.
5. Open the URL and press **Refresh projects**.

## Important limitations
- This is a public-feed aggregator, not an unrestricted scraper of every marketplace.
- Upwork, Freelancer, PeoplePerHour, Contra, Airtasker, LinkedIn and X may restrict automated access, require login, provide no stable public RSS feed, or prohibit scraping under their terms. This app does not bypass those controls.
- Google News results are indexed public pages, not verified job listings. Always open the original link and check that it is a genuine client request before bidding.
- The free Render service may sleep when idle; its local SQLite database may not be persistent across some free-tier restarts/redeploys. For reliable continuous use, use a persistent disk/database and an always-on hosting plan.
- This project does not auto-apply, send messages, or submit bids.
