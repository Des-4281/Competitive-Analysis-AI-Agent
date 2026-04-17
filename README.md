# Competitive Analysis AI Agent

An AI-powered agent that performs automated competitive analysis for any company. Given a company name, it validates the company, identifies its industry sector, finds top competitors, gathers real market and editorial data, and generates a structured Markdown report complete with a SWOT analysis and actionable insights.

## How It Works

When you enter a company name, the agent kicks off a structured research process. It doesn't just search once and guess. It breaks the problem into steps, uses the right tool for each one, and builds up context before synthesizing the final report.

### Architecture

The app has two parts running at the same time:

- **MCP Server** - a local HTTP server that exposes a set of custom research tools (validate, sector detection, competitor search, market data, editorial insights, web browsing, report assembly). It starts in a background thread when you run the app.
- **AI Agent** - a `smolagents` `ToolCallingAgent` powered by GPT-4.1. It connects to the MCP server and decides which tools to call, in what order, based on what it has learned so far.

The agent reasons through the task step by step, calling tools as needed, similar to how a human analyst would work through a problem rather than doing everything at once.

### What the Agent Does and Why

1. **Validate the company** - before doing any research, it confirms the input is a real company and not a typo or ambiguous term. No point analyzing something that doesn't exist.

2. **Identify the sector** - it searches multiple sources (web, Wikipedia, news) and cross-references them to determine the primary industry. This is important because "competitors" means something different in tech vs. healthcare vs. retail.

3. **Find the top 3 competitors** - using the sector as context, it searches for the leading players in that space and ranks them by how often they appear across multiple queries. It deliberately excludes the input company from this list.

4. **Gather market data** - pulls 12-month Google Trends search interest scores and Wikipedia profile data (revenue, employees, founding year) to establish quantitative benchmarks between the input company and its competitors.

5. **Gather editorial insights** - searches for news and editorial coverage explaining why competitors are winning or losing, what challenges the input company faces, and how analysts view the competitive landscape. This grounds the SWOT analysis in real evidence rather than assumptions.

6. **Synthesize and generate the report** - once it has enough context, the agent synthesizes a full SWOT analysis, competitor comparison table, and executive summary, then calls `generate_report` to assemble everything into a single cohesive Markdown report.

<details>
<summary><strong>Technical Deep Dive - What happens step by step during a run</strong></summary>

### Step 1 - Two things start at the same time

When you run the app, Python spins up two things simultaneously:

- **The MCP server** starts in a background thread on `localhost:8000`. Think of this as a toolbox sitting on a local server. It registers seven custom tools — `validate_company`, `identify_sector`, `identify_competitors`, `gather_market_data`, `gather_editorial_insights`, `browse_page`, and `generate_report` — and waits for the agent to connect and use them.
- **The AI agent** waits 3 seconds for the server to be ready, then connects to it. The agent is powered by GPT-4.1 via `smolagents` and communicates with the toolbox over HTTP.

---

### Step 2 - The agent gets its instructions

Before calling any tools, the agent reads prompt templates that define how it should behave:

- **System prompt** - a goal-oriented instruction that tells the agent to validate the company, find its sector, identify the top 3 competitors, gather real market and editorial data, synthesize a full SWOT analysis grounded in that research, and produce a single cohesive report by calling `generate_report` with all findings populated.
- **Planning prompt** - gives the agent a concrete checklist tied to the actual tools it has available.
- **Final answer prompt** - tells the agent what the output must look like: Executive Summary, Market Data, Competitor Comparison Table, SWOT Analysis, What Competitors Are Doing Better, Closing the Gap, Actionable Insights.

---

### Step 3 - The agent works through the tools one by one

Each tool call goes from the agent → over HTTP → to the MCP server → runs the Python function → returns the result back to the agent. The agent reads the result, updates what it knows, and decides what to call next.

**`validate_company`**
Runs a DuckDuckGo search for the company name. Scores the results looking for signals like the company's domain (.com), business terms (Inc, LLC, Corp), a Wikipedia mention, or news coverage. Needs at least 2 signals to confirm the company is real. If it fails, the agent stops early.

**`identify_sector`**
Runs 3 separate searches — one for what the company does, one for its Wikipedia/LinkedIn profile, one for its news and financial coverage. Scores each result against 10 industry keyword patterns (Technology, Finance, Healthcare, Retail, etc.). The sector that scores highest across all three searches wins.

**`identify_competitors`**
Runs 5 searches split into two groups:
- 3 searches to find companies at a similar size and stage to the input company
- 2 searches to find the top industry leaders as benchmarks

Candidates from both groups are ranked by how many times they appear across all searches. The final list puts peer-level competitors first and fills remaining spots with industry leaders, capped at 3 total.

**`gather_market_data`**
Two things happen here:
- Pulls 12-month Google Trends search interest scores (0-100) for the input company and all three competitors. Calculates the gap between the input company's score and each competitor's score.
- Scrapes the Wikipedia infobox for the input company to pull structured data like revenue, employee count, founding year, and headquarters.

**`gather_editorial_insights`**
Runs targeted searches to find editorial and news coverage across three angles:
- The input company's growth strategy and recent successes
- The input company's challenges, weaknesses, and customer friction points
- Why each competitor is winning relative to the input company

These findings are used to populate the SWOT analysis and the "What Competitors Are Doing Better" section with referenced evidence rather than assumptions.

**`browse_page`**
Visits competitor websites and scrapes the page content. Strips out navigation, footers, and scripts, then filters the remaining text down to sentences that match keywords from the research goal (pricing, strategy, product, etc.).

**`generate_report`**
Takes all synthesized findings as explicit parameters — executive summary, SWOT strengths/weaknesses/opportunities/threats, competitor comparison table, market data, and editorial insights — and assembles the final Markdown report. Because every field is a required parameter, the agent must synthesize real content before calling this tool. Placeholder text or dashes are not accepted.

---

### Step 4 - The reasoning loop between tools

After every tool call, `smolagents` runs the agent through a reasoning step. The agent:
- Re-reads the updated facts (what it now knows)
- Checks if the plan needs to change based on what it found
- Decides whether to call another tool or move toward writing the final report

This loop is what makes it an agent rather than a simple script — it adapts based on results instead of blindly executing a fixed sequence.

---

### Step 5 - Final output

Once the agent has gathered enough context, it synthesizes the full SWOT analysis and competitor comparison, then calls `generate_report` to produce a single cohesive Markdown report printed to the terminal.

</details>

## Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key

### Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows
```

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
Enter a company name: Miro
```

See [examples/example_run.md](examples/example_run.md) for a full walkthrough of a real run.
See [examples/example_report.md](examples/example_report.md) for the resulting report.

## Project Structure

```
.
├── app.py                      # Agent, MCP server, tools, and helper logic
├── requirements.txt            # Python dependencies
├── examples/
│   ├── example_run.md          # Annotated walkthrough of a real agent run
│   └── example_report.md      # Example final report output (Miro)
```

## Environment Variables

**`OPENAI_API_KEY`** *(required)*
Your OpenAI API key. If not set, the app will prompt for it at runtime.

**`OPENAI_BASE_URL`** *(optional)*
API base URL. Defaults to `https://api.openai.com/v1`. Override to use a compatible provider.

## Tech Stack

- [smolagents](https://github.com/huggingface/smolagents) - agent framework
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server for custom tools
- [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/) - web search
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) - webpage scraping
- [pytrends](https://pypi.org/project/pytrends/) - Google Trends data
- OpenAI GPT-4.1 - language model

## Known Limitations

- **DuckDuckGo rate limits** - searches can fail or return poor results if too many requests are made too quickly
- **Sector detection isn't always accurate** - relies on keyword matching, so niche or lesser-known companies may be misclassified or return "Unknown sector"
- **Competitor list is shallow** - pulls from a hardcoded list of known companies per sector, so smaller or emerging competitors won't appear
- **Web scraping can fail** - the `browse_page` tool depends on target sites not blocking scrapers; many will return no content
- **Google Trends comparisons against consumer giants are not meaningful** - a niche B2B SaaS product will always score near 0 vs. Apple or Microsoft; the gap analysis is most useful when comparing against direct competitors

## License

MIT License
