# Competitive Analysis AI Agent

An AI-powered agent that performs automated competitive analysis for any company. Given a company name, it validates the company, identifies its industry sector, finds top competitors, and generates a structured Markdown report with actionable insights.

## How It Works

The agent uses a local MCP (Model Context Protocol) server to expose custom tools, which are consumed by a `smolagents` `ToolCallingAgent` backed by GPT-4o-mini.

**Analysis pipeline:**
1. Validate the input company is real
2. Identify its primary industry sector
3. Find top 3 competitors
4. Browse competitor pages and gather strategy data
5. Generate a formatted report with comparison table and insights

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

- [smolagents](https://github.com/huggingface/smolagents) — agent framework
- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server for custom tools
- [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/) — web search
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) — webpage scraping
- OpenAI GPT-4o-mini — language model

## License

MIT License
