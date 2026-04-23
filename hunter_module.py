"""
Hunter Module — AI Web Scraper Agent
=====================================
Finds crypto airdrop URLs from RSS feeds and Twitter, deduplicates them with a
local SQLite database, and prepares them for downstream extraction.

Install dependencies:
    pip install feedparser apify-client
"""

import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta

import feedparser
from apify_client import ApifyClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = "tracker.db"

# Load the Apify API token from the environment to avoid hardcoding secrets.
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def init_db() -> sqlite3.Connection:
    """Create tracker.db and the processed_urls table if they don't exist.

    Returns the open database connection so callers can reuse it.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_urls (
            url TEXT UNIQUE NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def is_new_url(conn: sqlite3.Connection, url: str) -> bool:
    """Return True if *url* has not been seen before, then persist it.

    The INSERT OR IGNORE approach is atomic: if the URL is already present the
    insert is silently skipped and the function returns False.
    """
    cursor = conn.execute(
        "INSERT OR IGNORE INTO processed_urls (url) VALUES (?)", (url,)
    )
    conn.commit()
    return cursor.rowcount == 1  # 1 row inserted → genuinely new


# ---------------------------------------------------------------------------
# Hunter 1 — RSS Monitor
# ---------------------------------------------------------------------------


def get_rss_urls(feed_urls_list: list[str]) -> list[str]:
    """Parse a list of RSS feed URLs and return article links from the last 24 h.

    Args:
        feed_urls_list: RSS/Atom feed URLs to monitor.

    Returns:
        Deduplicated list of article URLs published within the past 24 hours.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    urls: list[str] = []

    for feed_url in feed_urls_list:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            # feedparser normalizes published date into a 9-tuple; fall back to
            # updated_parsed when published_parsed is absent.
            time_tuple = getattr(entry, "published_parsed", None) or getattr(
                entry, "updated_parsed", None
            )
            if time_tuple is None:
                # No date available — skip to avoid processing stale entries.
                continue

            published = datetime(*time_tuple[:6], tzinfo=timezone.utc)
            if published < cutoff:
                continue

            link = getattr(entry, "link", None)
            if link and link not in urls:
                urls.append(link)

    return urls


# ---------------------------------------------------------------------------
# Hunter 2 — Twitter Monitor
# ---------------------------------------------------------------------------


def get_twitter_urls() -> list[str]:
    """Scrape tweets via the Apify *apidojo/tweet-scraper* actor and extract URLs.

    The search query targets airdrop-related tweets with at least 50 likes to
    filter out low-signal noise.

    Returns:
        List of URLs extracted from matching tweet text.
    """
    client = ApifyClient(APIFY_API_TOKEN)

    run_input = {
        "searchTerms": ['("testnet" OR "points") AND "airdrop" min_faves:50'],
        "maxItems": 10,
        "queryType": "Latest",
    }

    run = client.actor("apidojo/tweet-scraper").call(run_input=run_input)

    url_pattern = re.compile(r"https?://[^\s\"'>]+")
    urls: list[str] = []

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        tweet_text = item.get("full_text") or item.get("text") or ""
        found = url_pattern.findall(tweet_text)
        for url in found:
            if url not in urls:
                urls.append(url)

    return urls


# ---------------------------------------------------------------------------
# Main orchestration loop
# ---------------------------------------------------------------------------


def main() -> None:
    """Initialize the database, gather URLs from all hunters, and deduplicate."""

    # 1. Initialize the SQLite database.
    conn = init_db()
    try:
        # 2. Gather URLs from the RSS Hunter.
        rss_feeds = [
            "https://cointelegraph.com/rss",
            "https://coindesk.com/arc/outboundfeeds/rss/",
            # Add more RSS feed URLs here as needed.
        ]
        rss_urls = get_rss_urls(rss_feeds)

        # 3. Gather URLs from the Twitter Hunter.
        twitter_urls: list[str] = []
        try:
            twitter_urls = get_twitter_urls()
        except Exception as exc:  # noqa: BLE001
            print(f"Twitter Hunter failed, skipping: {exc}")

        # 4. Combine into a single deduplicated candidate list.
        all_urls = rss_urls + twitter_urls

        # 5. Loop through, check novelty, and dispatch new URLs.
        for url in all_urls:
            if is_new_url(conn, url):
                print(f"New Airdrop Found: {url} - Ready for Firecrawl Extractor")

                # ------------------------------------------------------------
                # PLUG-IN POINT: call your Firecrawl extractor here, e.g.:
                #   scrape_with_firecrawl(url)
                # ------------------------------------------------------------
    finally:
        conn.close()


if __name__ == "__main__":
    main()
