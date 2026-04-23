"""
AI Web Scraper Agent for Crypto Airdrops
=========================================
Scrapes an airdrop page using Firecrawl, then parses the raw markdown
into a strict JSON schema using OpenAI Structured Outputs + Pydantic.

Install dependencies:
    pip install openai pydantic requests python-dotenv

Usage:
    python scraper.py
"""

import json
import os
import sys
from typing import Optional

import requests
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Schema
# ---------------------------------------------------------------------------

class OfficialLink(BaseModel):
    title: str
    url: str


class SocialLink(BaseModel):
    title: str
    url: str


class Step(BaseModel):
    title: str
    content: str = Field(
        ...,
        description="Step instructions. May contain HTML tags such as <p> and <a>.",
    )


class AirdropData(BaseModel):
    category: str
    createdAt: str = Field(..., description="ISO 8601 datetime string")
    description: str
    endDate: Optional[str] = Field(None, description="ISO 8601 datetime string")
    isArchived: bool
    isFeatured: bool
    isHighlyRated: bool
    networks: list[str]
    officialLinks: list[OfficialLink]
    shortDescription: str
    slug: str
    socialLinks: list[SocialLink]
    startDate: str = Field(..., description="ISO 8601 datetime string")
    steps: list[Step]
    tags: list[str]
    thumbnail: Optional[str] = None
    title: str


# ---------------------------------------------------------------------------
# Firecrawl Scraper
# ---------------------------------------------------------------------------

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"


def scrape_with_firecrawl(url: str) -> str:
    """
    Send a scrape request to the Firecrawl API and return the page's
    markdown content.

    Args:
        url: The target URL to scrape.

    Returns:
        The markdown-formatted page content as a string.

    Raises:
        ValueError: If the Firecrawl API key is not set or the request fails.
    """
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError(
            "FIRECRAWL_API_KEY environment variable is not set. "
            "Please add it to your .env file."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "formats": ["markdown"],
    }

    response = requests.post(FIRECRAWL_API_URL, json=payload, headers=headers, timeout=60)

    if response.status_code != 200:
        raise ValueError(
            f"Firecrawl API returned status {response.status_code}: {response.text}"
        )

    data = response.json()

    # Firecrawl v1 returns { "success": true, "data": { "markdown": "..." } }
    if not data.get("success"):
        raise ValueError(f"Firecrawl scrape failed: {data}")

    markdown = data.get("data", {}).get("markdown", "")
    if not markdown:
        raise ValueError("Firecrawl returned empty markdown content.")

    return markdown


# ---------------------------------------------------------------------------
# OpenAI LLM Parser
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an expert crypto airdrop analyst and data extraction specialist.

Your task is to analyse the provided webpage content (in markdown format) about
a cryptocurrency airdrop and extract every relevant piece of information,
outputting it as structured JSON that strictly conforms to the provided schema.

Guidelines:
- category: Classify the project (e.g. "DeFi", "NFT", "Layer 2", "GameFi", etc.)
- createdAt / startDate / endDate: Use ISO 8601 format (e.g. "2024-01-15T00:00:00Z").
  If a field is unknown, use a sensible default or omit it (endDate is optional).
- description: Full, detailed description of the airdrop / project.
- shortDescription: A concise one-to-two sentence summary.
- slug: URL-friendly identifier derived from the project title (lowercase, hyphens).
- networks: Blockchain networks the airdrop runs on (e.g. ["Ethereum", "Arbitrum"]).
- officialLinks: Website, documentation, whitepaper links with descriptive titles.
- socialLinks: Twitter/X, Discord, Telegram, etc. with descriptive titles.
- steps: Each participation step as an object with a title and HTML-formatted content.
  Preserve any <p> and <a href="..."> tags that improve readability.
- tags: Relevant keywords/labels (e.g. ["airdrop", "testnet", "DeFi"]).
- thumbnail: URL of the project's logo or hero image if found on the page.
- isArchived: true only if the airdrop has definitively ended and been archived.
- isFeatured: true if the page explicitly marks it as featured or highlighted.
- isHighlyRated: true if the page shows high community ratings or strong social proof.

Be thorough, accurate, and extract as much real data as possible from the content.
Do not invent data — if information is not present, use sensible defaults or
leave optional fields empty.
"""


def parse_airdrop_data(markdown_text: str) -> AirdropData:
    """
    Use OpenAI Structured Outputs to parse raw markdown content into an
    AirdropData object that matches the strict Pydantic schema.

    Args:
        markdown_text: Raw markdown content returned by Firecrawl.

    Returns:
        A validated AirdropData instance.

    Raises:
        ValueError: If the OpenAI API key is not set or parsing fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please add it to your .env file."
        )

    client = OpenAI(api_key=api_key)

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Extract all airdrop information from the following webpage "
                    "content and return it as structured JSON:\n\n"
                    f"{markdown_text}"
                ),
            },
        ],
        response_format=AirdropData,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI returned an empty or unparseable response.")

    return parsed


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Load config, scrape a sample airdrop page, parse it, and print JSON."""
    # Load API keys from .env file (won't override existing env vars)
    load_dotenv()

    # -----------------------------------------------------------------------
    # Sample target URL — change this to any airdrop listing page you want
    # to analyse, e.g. from airdropalert.com, airdrops.io, etc.
    # -----------------------------------------------------------------------
    target_url = os.getenv(
        "TARGET_URL",
        "https://airdrops.io/arbitrum/",
    )

    print(f"[*] Scraping URL: {target_url}")

    # Step 1 – Scrape raw content via Firecrawl
    try:
        markdown_content = scrape_with_firecrawl(target_url)
        print(f"[+] Scraped {len(markdown_content):,} characters of markdown content.")
    except ValueError as exc:
        print(f"[!] Scraping failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 2 – Parse content into structured AirdropData via OpenAI
    try:
        airdrop = parse_airdrop_data(markdown_content)
        print("[+] Parsing complete. Structured output:")
    except ValueError as exc:
        print(f"[!] Parsing failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 3 – Print final JSON
    print(json.dumps(airdrop.model_dump(), indent=2))


if __name__ == "__main__":
    main()
