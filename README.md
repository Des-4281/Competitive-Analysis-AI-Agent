# Competitive Analysis AI Agent

An AI-powered agent that performs automated competitive analysis for any company. Given a company name, it validates the company, identifies its industry sector, finds top competitors, and generates a structured Markdown report with actionable insights.

## How It Works

When you enter a company name, the agent kicks off a structured research process. It doesn't just search once and guess. It breaks the problem into steps, uses the right tool for each one, and builds up context before writing the final report.

### Architecture

The app has two parts running at the same time:

- **MCP Server** - a local HTTP server that exposes a set of custom research tools (validate, sector detection, competitor search, web browsing, report generation). It starts in a background thread when you run the app.
- **AI Agent** - a `smolagents` `ToolCallingAgent` powered by GPT-4o-mini. It connects to the MCP server and decides which tools to call, in what order, based on what it has learned so far.

The agent reasons through the task step by step, calling tools as needed, similar to how a human analyst would work through a problem rather than doing everything at once.

### What the Agent Does and Why

1. **Validate the company** - before doing any research, it confirms the input is a real company and not a typo or ambiguous term. No point analyzing something that doesn't exist.

2. **Identify the sector** - it searches multiple sources (web, Wikipedia, news) and cross-references them to determine the primary industry. This is important because "competitors" means something different in tech vs. healthcare vs. retail.

3. **Find the top 3 competitors** - using the sector as context, it searches for the leading players in that space and ranks them by how often they appear across multiple queries. It deliberately excludes the input company from this list.

4. **Gather strategy data** - it browses competitor pages and pulls real-time information like pricing, product offerings, press releases, and news. This is where the `browse_page` tool comes in, scraping and extracting only the content relevant to competitive strategy.

5. **Generate the report** - once it has enough context, it calls the `generate_report` tool to produce a structured Markdown report with an executive summary, a competitor comparison table, and actionable insights tailored to the input company.

## Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run

```bash
python app.py
```

You will be prompted for your OpenAI API key (if not set as `OPENAI_API_KEY` in your environment) and a company name.

## Example

```
Enter your OpenAI API key: sk-...
Enter a company name: Salesforce
```

Output is a Markdown report with an executive summary, competitor comparison table, and actionable insights.

## Project Structure

```
.
├── app.py            # Main agent, MCP server, and helper logic
├── config.json       # Base config (API base URL)
├── requirements.txt  # Python dependencies
```

## Environment Variables

**`OPENAI_API_KEY`** *(required)*
Your OpenAI API key. If not set, the app will prompt for it at runtime.

**`OPENAI_BASE_URL`** *(optional)*
API base URL. Defaults to `https://api.openai.com/v1`. Override in `config.json` to use a compatible provider.

## Tech Stack

- [smolagents](https://github.com/huggingface/smolagents) - agent framework
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server for custom tools
- [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/) - web search
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) - webpage scraping
- OpenAI GPT-4o-mini - language model

## Known Limitations

- **DuckDuckGo rate limits** - searches can fail or return poor results if too many requests are made too quickly
- **Sector detection isn't always accurate** - relies on keyword matching, so niche or lesser-known companies may be misclassified or return "Unknown sector"
- **Competitor list is shallow** - pulls from a hardcoded list of known companies per sector, so smaller or emerging competitors won't appear
- **Web scraping can fail** - the `browse_page` tool depends on target sites not blocking scrapers; many will return no content
- **Report placeholders may not fill in** - the comparison table falls back to generic "Competitor A/B/C" if not enough competitor data is found
- **Requires OpenAI** - hardcoded to GPT-4o-mini, no support for other model providers out of the box

## License

MIT License
