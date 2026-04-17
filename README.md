# Competitive Analysis AI Agent

An AI-powered agent that performs automated competitive analysis for any company. Given a company name, it validates the company, identifies its industry sector, finds top competitors, gathers real market and editorial data, and generates a structured Markdown report complete with a SWOT analysis and actionable insights.

## How It Works

When you enter a company name, the agent kicks off a structured research process. It doesn't just search once and guess. It breaks the problem into steps, uses the right tool for each one, and builds up context before synthesizing the final report.

## Architecture

The app has two parts running at the same time:

- **MCP Server** - a local HTTP server that exposes a set of custom research tools (validate, sector detection, competitor search, market data, editorial insights, web browsing, report assembly). It starts in a background thread when you run the app.
- **AI Agent** - a smolagents `ToolCallingAgent` powered by GPT-4.1. It connects to the MCP server and decides which tools to call, in what order, based on what it has learned so far.

The agent reasons through the task step by step, calling tools as needed, similar to how a human analyst would work through a problem rather than doing everything at once.

## What the Agent Does and Why

- **Validate the company** - before doing any research, it confirms the input is a real company and not a typo or ambiguous term.
- **Identify the sector** - searches multiple sources (web, Wikipedia, news) and cross-references them to determine the primary industry.
- **Find the top 3 competitors** - using the sector as context, it searches for the leading players in that space and ranks them by frequency across multiple queries.
- **Gather market data** - pulls 12-month Google Trends data and Wikipedia profile information.
- **Gather editorial insights** - searches for news and analysis explaining why competitors are winning or losing.
- **Synthesize and report** - once the agent has enough context, it produces a full SWOT analysis, competitor comparison table, and executive summary via `generate_report`.

## Setup

### Prerequisites
Make sure you have the following installed before running:
- Python 3.11+ — [Download here](https://www.python.org/downloads/)
- Git — [Download here](https://git-scm.com/)
- An OpenAI API key — [Get one here](https://platform.openai.com/api-keys)

### Run Locally

Clone the repository:
```bash
git clone https://github.com/Des-4281/Competitive-Analysis-AI-Agent.git
cd Competitive-Analysis-AI-Agent
```

Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run:
```bash
python app.py
```

You will be prompted for your OpenAI API key and a company name. Alternatively, set them as environment variables to skip the prompts:
```bash
export OPENAI_API_KEY=sk-...
export COMPANY_NAME=Miro
python app.py
```

> **Note:** The agent takes 3–8 minutes to complete a full analysis. It performs multiple web searches, scrapes market data, and synthesizes a full report using GPT-4.1. This is expected behavior.

### Example
Enter your OpenAI API key: sk-...
Enter a company name: Miro

See `examples/example_run.md` for a full walkthrough of a real run. See `examples/example_report.md` for the resulting report.

## GCP Deployment (Cloud Run Jobs)

This app is containerized with Docker and deployed to Google Cloud Run Jobs.

### Prerequisites
- Google Cloud CLI installed and initialized (`gcloud init`)
- A GCP project with billing enabled
- Cloud Build, Cloud Run, and Container Registry APIs enabled

### Enable GCP Services
```bash
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com
```

### Set Permissions for Cloud Build
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### Deploy via Cloud Build
Connect your GitHub repo to Cloud Build and create a trigger pointing at `cloudbuild.yaml` on the `main` branch. Every push to `main` will automatically build and deploy.

### Set Environment Variables
```bash
gcloud run jobs update competitive-analysis-agent \
  --region=us-central1 \
  --set-env-vars=OPENAI_API_KEY=your-key-here,COMPANY_NAME=Miro
```

### Run the Job
```bash
gcloud run jobs execute competitive-analysis-agent --region=us-central1
```

View logs at: `console.cloud.google.com/run/jobs`

## Project Structure
.
├── app.py                      # Agent, MCP server, tools, and helper logic
├── Dockerfile                  # Container configuration
├── cloudbuild.yaml             # GCP Cloud Build pipeline
├── requirements.txt            # Python dependencies
├── config.json                 # API configuration
├── examples/
│   ├── example_run.md          # Annotated walkthrough of a real agent run
│   └── example_report.md      # Example final report output (Miro)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key. If not set, the app will prompt at runtime. |
| `COMPANY_NAME` | Yes (GCP) | The company to analyze. Required for GCP deployment since there is no interactive terminal. |
| `OPENAI_BASE_URL` | No | API base URL. Defaults to `https://api.openai.com/v1`. |

## Tech Stack
- **smolagents** - agent framework
- **FastMCP** - MCP server for custom tools
- **DuckDuckGo Search** - web search
- **BeautifulSoup4** - webpage scraping
- **pytrends** - Google Trends data
- **OpenAI GPT-4.1** - language model
- **Docker** - containerization
- **Google Cloud Run Jobs** - cloud deployment
- **Google Cloud Build** - CI/CD pipeline

## Known Limitations
- **DuckDuckGo rate limits** - searches can fail or return poor results if too many requests are made too quickly
- **Web scraping can fail** - the `browse_page` tool depends on target sites not blocking scrapers
- **Google Trends comparisons against consumer giants are not meaningful** - a niche B2B SaaS product will always score near 0 vs. Apple or Microsoft; the gap analysis is most useful when comparing against direct competitors

## License

MIT License