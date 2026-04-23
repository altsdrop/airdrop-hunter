# airdrop-hunter

An **AI Web Scraper Agent** that extracts crypto airdrop data from any URL and parses it into a strict, structured JSON schema using the **Firecrawl API** and **OpenAI Structured Outputs**.

---

## Features

- 🔍 **Firecrawl-powered scraping** – converts any airdrop page to clean markdown
- 🤖 **OpenAI GPT-4o-mini parser** – uses Structured Outputs to guarantee schema compliance
- 📐 **Pydantic v2 schema** – fully typed, validated output every time
- ⚙️ **`.env` based configuration** – keep API keys out of source control

---

## Quick Start

### 1. Install dependencies

```bash
pip install openai pydantic requests python-dotenv
```

Or install from the lock file:

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=sk-...
FIRECRAWL_API_KEY=fc-...
```

> - Get an OpenAI API key at <https://platform.openai.com/api-keys>
> - Get a Firecrawl API key at <https://www.firecrawl.dev>

### 3. Run the agent

```bash
python scraper.py
```

By default the agent scrapes `https://airdrops.io/arbitrum/`. You can override the target URL with an environment variable:

```bash
TARGET_URL=https://airdrops.io/uniswap/ python scraper.py
```

---

## Output Schema

The agent returns a JSON object matching the following structure:

| Field | Type | Description |
|---|---|---|
| `category` | string | Project category (e.g. DeFi, NFT, Layer 2) |
| `createdAt` | ISO 8601 string | Record creation timestamp |
| `description` | string | Full project/airdrop description |
| `endDate` | ISO 8601 string *(optional)* | Airdrop end date |
| `isArchived` | boolean | Whether the airdrop is archived |
| `isFeatured` | boolean | Whether the airdrop is featured |
| `isHighlyRated` | boolean | Whether it has high community ratings |
| `networks` | list of strings | Blockchain networks supported |
| `officialLinks` | list of `{title, url}` objects | Website, docs, whitepaper links |
| `shortDescription` | string | One-to-two sentence summary |
| `slug` | string | URL-friendly identifier |
| `socialLinks` | list of `{title, url}` objects | Twitter/X, Discord, Telegram, etc. |
| `startDate` | ISO 8601 string | Airdrop start date |
| `steps` | list of `{title, content}` objects | Participation steps (HTML content) |
| `tags` | list of strings | Relevant keywords/labels |
| `thumbnail` | string *(optional)* | Logo or hero image URL |
| `title` | string | Project/airdrop name |

### Example output

```json
{
  "category": "Layer 2",
  "createdAt": "2023-03-23T00:00:00Z",
  "description": "Arbitrum is a Layer 2 scaling solution for Ethereum ...",
  "endDate": null,
  "isArchived": false,
  "isFeatured": true,
  "isHighlyRated": true,
  "networks": ["Ethereum", "Arbitrum"],
  "officialLinks": [
    {"title": "Official Website", "url": "https://arbitrum.io"},
    {"title": "Documentation", "url": "https://docs.arbitrum.io"}
  ],
  "shortDescription": "Arbitrum is a leading Ethereum Layer 2 network offering fast, cheap transactions.",
  "slug": "arbitrum",
  "socialLinks": [
    {"title": "Twitter/X", "url": "https://twitter.com/arbitrum"},
    {"title": "Discord", "url": "https://discord.gg/arbitrum"}
  ],
  "startDate": "2023-03-23T00:00:00Z",
  "steps": [
    {
      "title": "Bridge Assets",
      "content": "<p>Go to the <a href=\"https://bridge.arbitrum.io\">Arbitrum Bridge</a> and transfer ETH to Arbitrum One.</p>"
    }
  ],
  "tags": ["airdrop", "layer2", "ethereum", "defi"],
  "thumbnail": "https://arbitrum.io/logo.png",
  "title": "Arbitrum"
}
```

---

## Project Structure

```
airdrop-hunter/
├── scraper.py        # Main agent script
├── requirements.txt  # Python dependencies
├── .env.example      # API key template
└── README.md
```

---

## How It Works

```
Target URL
   │
   ▼
scrape_with_firecrawl(url)
   │  Firecrawl API converts the page to clean markdown
   ▼
parse_airdrop_data(markdown_text)
   │  OpenAI gpt-4o-mini uses Structured Outputs
   │  to enforce the Pydantic AirdropData schema
   ▼
Validated JSON output
```

1. **`scrape_with_firecrawl(url)`** – POSTs to `https://api.firecrawl.dev/v1/scrape` and returns the page as markdown.
2. **`parse_airdrop_data(markdown_text)`** – Calls `client.beta.chat.completions.parse()` with the `AirdropData` Pydantic model as `response_format`, guaranteeing a schema-compliant response.
3. **`main()`** – Orchestrates the pipeline, handles errors, and prints the final JSON.