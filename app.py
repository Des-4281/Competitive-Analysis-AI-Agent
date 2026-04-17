# app.py
import os
import re
import threading
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq
from mcp.server.fastmcp import FastMCP
from smolagents import (
    DuckDuckGoSearchTool,
    FinalAnswerPromptTemplate,
    MCPClient,
    ManagedAgentPromptTemplate,
    OpenAIServerModel,
    PlanningPromptTemplate,
    PromptTemplates,
    ToolCallingAgent,
)

# -----------------------------
# Config
# -----------------------------
api_key = os.environ.get("OPENAI_API_KEY") or input("Enter your OpenAI API key: ").strip()
os.environ["OPENAI_API_KEY"] = api_key
os.environ["OPENAI_BASE_URL"] = "https://api.openai.com/v1"

MODEL_ID = "gpt-4.1"
MCP_HOST = "127.0.0.1"
MCP_PORT = 8000
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"

# -----------------------------
# Shared tools / server
# -----------------------------
web_search_tool = DuckDuckGoSearchTool(max_results=5, rate_limit=2.0)

mcp = FastMCP(
    "competitive-analysis",
    host=MCP_HOST,
    port=MCP_PORT,
)


# -----------------------------
# Helpers
# -----------------------------
def is_company_valid_based_on_search(search_results: str, company_name: str) -> bool:
    results_lower = search_results.lower()
    company_lower = company_name.lower()
    evidence_count = 0

    if f"{company_lower}.com" in results_lower:
        evidence_count += 1

    if "official site" in results_lower or "official website" in results_lower:
        evidence_count += 1

    if "company" in results_lower and company_lower in results_lower:
        evidence_count += 1

    business_terms = ["corporation", "inc", "ltd", "llc", "business", "enterprise"]
    if any(term in results_lower for term in business_terms):
        evidence_count += 1

    if "wikipedia" in results_lower or "news" in results_lower:
        evidence_count += 1

    return evidence_count >= 2


def extract_sectors_advanced(search_results: str, company_name: str) -> list[str]:
    results_lower = search_results.lower()
    company_lower = company_name.lower()

    sector_patterns = {
        "Technology": {
            "keywords": ["technology", "software", "hardware", "saas", "cloud", "ai", "artificial intelligence"],
            "weight": 1.0,
        },
        "Finance": {
            "keywords": ["financial", "banking", "investment", "fintech", "insurance", "bank"],
            "weight": 1.0,
        },
        "Healthcare": {
            "keywords": ["healthcare", "medical", "pharmaceutical", "biotech", "hospital", "health"],
            "weight": 1.0,
        },
        "Education": {
            "keywords": ["education", "edtech", "e-learning", "online learning", "educational"],
            "weight": 1.0,
        },
        "Retail": {
            "keywords": ["retail", "e-commerce", "online shopping", "marketplace"],
            "weight": 1.0,
        },
        "Manufacturing": {
            "keywords": ["manufacturing", "industrial", "automotive", "electronics", "factory"],
            "weight": 1.0,
        },
        "Energy": {
            "keywords": ["energy", "renewable", "oil and gas", "solar"],
            "weight": 1.0,
        },
    }

    found_sectors = []

    for sector, pattern in sector_patterns.items():
        for keyword in pattern["keywords"]:
            if keyword in results_lower:
                if company_lower in results_lower or any(
                    phrase in results_lower
                    for phrase in [f"is a {keyword}", f"in the {keyword}"]
                ):
                    found_sectors.extend([sector] * int(pattern["weight"] * 2))
                else:
                    found_sectors.extend([sector] * int(pattern["weight"]))

    return found_sectors


def determine_primary_sector(sectors_list: list[str]) -> str:
    if not sectors_list:
        return ""

    sector_counts = Counter(sectors_list)
    most_common = sector_counts.most_common(1)[0]

    if most_common[1] >= 2:
        return most_common[0]
    if len(sector_counts) == 1 and most_common[1] >= 1:
        return most_common[0]

    return ""


def is_likely_company_name(text: str) -> bool:
    if not text or len(text) < 2:
        return False

    non_company_words = {
        "the", "and", "or", "but", "with", "for", "from", "that", "this",
        "these", "those", "their", "other", "some", "such", "including",
        "etc", "etc.", "among", "various", "several", "many",
    }

    words = text.lower().split()
    if any(word in non_company_words for word in words):
        return False

    return text[0].isupper() and len(text) <= 50 and any(c.isalpha() for c in text)


def extract_competitors_advanced(search_results: str, exclude_company: str, sector: str) -> list[str]:
    exclude_lower = exclude_company.lower()
    sector_lower = sector.lower()
    results_lower = search_results.lower()

    competitors = []

    sector_companies = {
        "technology": ["microsoft", "apple", "amazon", "meta", "google", "ibm", "oracle", "intel", "salesforce", "adobe", "sap", "nvidia", "cisco", "dell", "hp", "servicenow", "workday", "snowflake", "palantir", "twilio"],
        "finance": ["jpmorgan", "bank of america", "goldman sachs", "morgan stanley", "citi", "wells fargo", "blackrock", "charles schwab", "american express", "visa", "mastercard", "paypal", "stripe", "square", "fidelity"],
        "healthcare": ["johnson & johnson", "pfizer", "merck", "novartis", "roche", "abbvie", "unitedhealth", "cvs health", "cigna", "anthem", "humana", "medtronic", "abbott", "boston scientific", "becton dickinson"],
        "education": ["great learning", "coursera", "udemy", "edx", "khan academy", "byju's", "pluralsight", "chegg", "duolingo", "skillshare", "linkedin learning", "2u", "pearson", "mcgraw hill"],
        "retail": ["walmart", "target", "amazon", "home depot", "costco", "best buy", "kroger", "walgreens", "cvs", "lowe's", "ebay", "etsy", "shopify", "wayfair", "dollar general"],
        "automotive": ["toyota", "ford", "general motors", "honda", "bmw", "mercedes-benz", "tesla", "volkswagen", "stellantis", "hyundai", "kia", "nissan", "rivian", "lucid", "subaru"],
        "manufacturing": ["ge", "siemens", "honeywell", "3m", "caterpillar", "deere", "emerson", "parker hannifin", "illinois tool works", "rockwell automation"],
        "energy": ["exxonmobil", "chevron", "shell", "bp", "totalenergies", "conocophillips", "nextera energy", "duke energy", "dominion energy", "enphase", "first solar"],
        "media": ["netflix", "disney", "warner bros", "comcast", "paramount", "sony", "nbc universal", "fox", "spotify", "apple tv"],
        "telecommunications": ["at&t", "verizon", "t-mobile", "comcast", "charter", "dish", "lumen", "frontier", "windstream"],
    }

    if sector_lower in sector_companies:
        for company in sector_companies[sector_lower]:
            if company in results_lower and company != exclude_lower and company not in competitors:
                competitors.append(company.title())

    list_patterns = [
        r"(?:competitors|companies|players):? ([^\.]+)",
        r"(?:including|such as) ([^\.]+)",
        r"top \d+ ([^:]+) companies",
    ]

    for pattern in list_patterns:
        matches = re.findall(pattern, search_results, re.IGNORECASE)
        for match in matches:
            potential_companies = re.split(r",|\band\b|\bor\b|;", match)
            for comp in potential_companies:
                comp = comp.strip()
                if (
                    is_likely_company_name(comp)
                    and comp.lower() != exclude_lower
                    and comp not in competitors
                ):
                    competitors.append(comp)

    numbered_pattern = r"\b\d+\.\s*([A-Z][a-zA-Z\s&-]+?)(?=\.|\n|$)"
    matches = re.findall(numbered_pattern, search_results)
    for match in matches:
        comp = match.strip()
        if (
            is_likely_company_name(comp)
            and comp.lower() != exclude_lower
            and comp not in competitors
        ):
            competitors.append(comp)

    return competitors


def rank_competitors(competitor_candidates: list[str], exclude_company: str) -> list[str]:
    if not competitor_candidates:
        return []

    exclude_lower = exclude_company.lower()
    filtered = [
        comp for comp in competitor_candidates
        if comp.lower() != exclude_lower and comp.strip()
    ]

    if not filtered:
        return []

    counts = Counter(filtered)
    return [comp for comp, _ in counts.most_common()]


def fetch_webpage_content(url: str) -> str | None:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        main_content = soup.find_all(["main", "article", "div", "p"])
        text_parts = []

        for element in main_content:
            text = element.get_text(strip=True)
            if text and len(text) > 20:
                text_parts.append(text)

        return " ".join(text_parts[:5000])

    except Exception:
        return None


def extract_relevant_content(content: str, instructions: str) -> str:
    instructions_lower = instructions.lower()
    sentences = [s.strip() for s in content.split(".") if s.strip()]
    relevant_sentences = []

    for sentence in sentences:
        sentence_lower = sentence.lower()
        instruction_words = set(instructions_lower.split())
        sentence_words = set(sentence_lower.split())
        matching_words = instruction_words.intersection(sentence_words)

        if len(matching_words) >= 1 and len(sentence) > 10:
            relevant_sentences.append(sentence)

    if not relevant_sentences and sentences:
        return ". ".join(sentences[:5]) + "..."

    return ". ".join(relevant_sentences[:10])


def fetch_google_trends(companies: list[str]) -> dict[str, int]:
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        keywords = companies[:5]
        pytrends.build_payload(keywords, timeframe="today 12-m")
        data = pytrends.interest_over_time()
        if data.empty:
            return {}
        averages = data.drop(columns=["isPartial"], errors="ignore").mean().to_dict()
        return {k: round(v) for k, v in averages.items()}
    except Exception:
        return {}


def fetch_wikipedia_data(company_name: str) -> dict[str, str]:
    try:
        search_name = company_name.replace(" ", "_")
        url = f"https://en.wikipedia.org/wiki/{search_name}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {}

        soup = BeautifulSoup(response.content, "html.parser")
        infobox = soup.find("table", {"class": "infobox"})
        if not infobox:
            return {}

        data = {}
        for row in infobox.find_all("tr"):
            header = row.find("th")
            value = row.find("td")
            if header and value:
                key = header.get_text(strip=True).lower()
                val = value.get_text(strip=True)
                if any(k in key for k in ["revenue", "employees", "founded", "headquarters"]):
                    data[key] = val[:100]

        return data
    except Exception:
        return {}


def extract_competitors_from_context(context: str) -> list[str]:
    competitors = []

    if ", " in context:
        potential = context.split(", ")
        for comp in potential:
            if comp and len(comp) > 2 and comp[0].isupper():
                competitors.append(comp)

    competitor_patterns = [
        r"competitors?[:\s]+([^\.\n]+)",
        r"top.*companies?[:\s]+([^\.\n]+)",
    ]

    for pattern in competitor_patterns:
        matches = re.findall(pattern, context, re.IGNORECASE)
        for match in matches:
            found = re.split(r",|\band\b", match)
            competitors.extend([comp.strip() for comp in found if comp.strip()])

    deduped = []
    seen = set()
    for comp in competitors:
        key = comp.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(comp)

    return deduped[:5]


# -----------------------------
# MCP tools
# -----------------------------
@mcp.tool()
def validate_company(company_name: str) -> str:
    try:
        results = web_search_tool(f"{company_name} company business official site")
        if is_company_valid_based_on_search(results, company_name):
            return f"[VALID COMPANY] {company_name}"
        return f"[NOT VALID COMPANY] No substantial evidence found for '{company_name}'"
    except Exception as e:
        return f"Validation failed: {e}"


@mcp.tool()
def identify_sector(company_name: str) -> str:
    try:
        all_sectors = []

        results1 = web_search_tool(f"what does {company_name} do business industry")
        all_sectors.extend(extract_sectors_advanced(results1, company_name))
        time.sleep(1)

        results2 = web_search_tool(f"{company_name} wikipedia linkedin industry type")
        all_sectors.extend(extract_sectors_advanced(results2, company_name))
        time.sleep(1)

        results3 = web_search_tool(f"{company_name} news financial reports sector")
        all_sectors.extend(extract_sectors_advanced(results3, company_name))

        final_sector = determine_primary_sector(all_sectors)
        return final_sector if final_sector else "Unknown sector"
    except Exception as e:
        return f"Error identifying sector: {e}"


@mcp.tool()
def identify_competitors(sector: str, company_name: str) -> str:
    try:
        peer_candidates = []
        industry_leaders = []

        # Find companies at a similar size and stage
        results1 = web_search_tool(f"{company_name} competitors similar size {sector} market")
        peer_candidates.extend(extract_competitors_advanced(results1, company_name, sector))
        time.sleep(1)

        results2 = web_search_tool(f"who are {company_name} main competitors in {sector}")
        peer_candidates.extend(extract_competitors_advanced(results2, company_name, sector))
        time.sleep(1)

        results3 = web_search_tool(f"{company_name} vs competitors comparison {sector}")
        peer_candidates.extend(extract_competitors_advanced(results3, company_name, sector))
        time.sleep(1)

        # Find top industry leaders to benchmark against
        results4 = web_search_tool(f"top {sector} companies market share leaders 2024")
        industry_leaders.extend(extract_competitors_advanced(results4, company_name, sector))
        time.sleep(1)

        results5 = web_search_tool(f"best {sector} companies ranked revenue growth")
        industry_leaders.extend(extract_competitors_advanced(results5, company_name, sector))

        # Prioritize peers, then fill with industry leaders
        ranked_peers = rank_competitors(peer_candidates, company_name)
        ranked_leaders = rank_competitors(industry_leaders, company_name)

        combined = ranked_peers[:2]
        for leader in ranked_leaders:
            if leader not in combined and len(combined) < 3:
                combined.append(leader)

        if combined:
            return ", ".join(combined)
        return "No competitors identified"
    except Exception as e:
        return f"Error identifying competitors: {e}"


@mcp.tool()
def browse_page(url: str, instructions: str) -> str:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        content = fetch_webpage_content(url)
        if not content:
            return f"Failed to fetch content from {url}"

        extracted_text = extract_relevant_content(content, instructions)
        return extracted_text if extracted_text else "No relevant content found"
    except Exception as e:
        return f"Error browsing page: {e}"


@mcp.tool()
def gather_market_data(company_name: str, competitors: str) -> str:
    try:
        all_companies = [company_name] + [c.strip() for c in competitors.split(",") if c.strip()]

        trends = fetch_google_trends(all_companies)
        wiki_data = fetch_wikipedia_data(company_name)

        output = f"## Market Data for {company_name}\n\n"

        if wiki_data:
            output += "### Company Profile (Wikipedia)\n"
            for key, val in wiki_data.items():
                output += f"- **{key.title()}:** {val}\n"
            output += "\n"

        if trends:
            output += "### Google Trends - 12-Month Search Interest (0-100)\n"
            sorted_trends = sorted(trends.items(), key=lambda x: x[1], reverse=True)
            for company, score in sorted_trends:
                gap = trends.get(company_name, 0) - score
                gap_str = f"(gap: {gap:+d})" if company != company_name else "(input company)"
                output += f"- **{company}:** {score} {gap_str}\n"
            output += "\n"

            if company_name in trends:
                leaders_above = [(c, s) for c, s in sorted_trends if s > trends[company_name]]
                if leaders_above:
                    output += "### Gap Analysis\n"
                    for competitor, score in leaders_above:
                        diff = score - trends[company_name]
                        output += f"- {company_name} trails **{competitor}** by {diff} points in search interest — indicates lower brand visibility or market awareness\n"

        return output if output.strip() else "No market data available"
    except Exception as e:
        return f"Error gathering market data: {e}"


@mcp.tool()
def gather_editorial_insights(company_name: str, competitors: str) -> str:
    try:
        comp_list = [c.strip() for c in competitors.split(",") if c.strip()]
        insights = []

        results1 = web_search_tool(f"{company_name} growth strategy why successful 2024 analysis")
        insights.append(f"### {company_name} - Growth & Strategy\n{results1}")
        time.sleep(1)

        results2 = web_search_tool(f"{company_name} challenges declining losing customers problems")
        insights.append(f"### {company_name} - Challenges & Weaknesses\n{results2}")
        time.sleep(1)

        for competitor in comp_list[:3]:
            results = web_search_tool(f"why is {competitor} beating {company_name} competitive advantage winning")
            insights.append(f"### {competitor} - Why They Are Winning\n{results}")
            time.sleep(1)

        if comp_list:
            all_names = " vs ".join([company_name] + comp_list[:2])
            results = web_search_tool(f"{all_names} who is winning market share comparison editorial")
            insights.append(f"### Direct Comparison - Editorial Coverage\n{results}")

        return "\n\n".join(insights) if insights else "No editorial insights found"
    except Exception as e:
        return f"Error gathering editorial insights: {e}"


@mcp.tool()
def generate_report(
    company_name: str,
    sector: str,
    competitors: str,
    market_data: str,
    editorial_insights: str,
    swot_strengths: str,
    swot_weaknesses: str,
    swot_opportunities: str,
    swot_threats: str,
    competitor_comparison: str,
    executive_summary: str,
) -> str:
    """
    Assemble the final competitive analysis report from pre-synthesized research.
    All parameters must be filled with actual findings — do not pass placeholder text.

    competitor_comparison must be formatted as markdown sections, one per competitor, like:
    ### Competitor Name
    - **Strategy:** ...
    - **Key Tactics:** ...
    - **Strengths:** ...
    - **Weaknesses:** ...
    Do not use a markdown table.
    """
    report = f"""# Competitive Analysis Report: {company_name}

## Executive Summary
{executive_summary}

## Sector
{sector}

## Identified Competitors
{competitors}

## Market Data
{market_data}

## Competitor Comparison

{competitor_comparison}

## SWOT Analysis: {company_name}

**Strengths**
{swot_strengths}

**Weaknesses**
{swot_weaknesses}

**Opportunities**
{swot_opportunities}

**Threats**
{swot_threats}

## What Competitors Are Doing Better (and Why)
{editorial_insights}

## Closing the Gap: How {company_name} Can Gain Market Share
- Target customer segments where top competitors receive the most criticism
- Match or undercut competitor pricing in areas where {company_name} has cost advantages
- Accelerate investment in product capabilities where competitors are weakest
- Pursue partnerships or distribution channels competitors have not yet exploited

## Actionable Insights for {company_name}
- Prioritize the opportunities identified in the SWOT analysis above
- Use Google Trends gap data to guide brand visibility investments
- Monitor competitor moves in areas highlighted by editorial coverage
"""
    return report.strip()


# -----------------------------
# Agent prompt templates
# -----------------------------
system_prompt = """
You are an expert Competitive Analysis Agent.

Given a single company name, produce a comprehensive competitive analysis by:
- Validating that it is a real company
- Determining its primary industry sector
- Identifying its top three competitors
- Gathering real market data including Google Trends scores, Wikipedia profile data, quarterly earnings, and press releases
- Finding editorial and news coverage explaining why competitors are winning or losing
- Synthesizing a full SWOT analysis for the input company grounded in the research — every point must reference specific evidence from the data gathered
- Building a competitor comparison table covering strategy, key tactics, strengths, and weaknesses
- Calling generate_report with all synthesized findings populated — every field must contain real research, not placeholder text or dashes

Your final answer must be the output of generate_report: one cohesive, well-structured report. Do not output intermediate research steps as the final answer.
"""

planning_prompts = PlanningPromptTemplate(
    initial_facts="""
Key facts about the input company and its top three competitors from initial research:
{facts}
""",
    initial_plan="""
Step-by-step plan:
1. Validate the company name.
2. Determine the sector.
3. Identify the top 3 competitors.
4. Gather real market data including search trends and company profile information.
5. Gather strategy data on the company and those competitors.
6. Search for editorial and news coverage explaining why competitors are winning or losing relative to the input company.
7. Analyze all findings and generate a structured comparison report.
8. Propose actionable insights backed by the research.
""",
    update_facts_pre_messages="Reassess facts with new information, focusing on the input company and its competitors:",
    update_facts_post_messages="Updated facts considered for the single-company analysis.",
    update_plan_pre_messages="Revise the analysis plan based on new data while staying focused on one company:",
    update_plan_post_messages="Analysis plan revised for targeted competitive insights.",
)

managed_agent_prompts = ManagedAgentPromptTemplate(
    task="""
Your task is to analyze the strategies of the top 3 competitors relative to the single input company {task_description}
and produce a comparison table with actionable insights tailored to helping {task_description} outperform them.
""",
    report="Generate a detailed, focused report based on the task results for {task_description}: {results}",
)

final_answer_prompts = FinalAnswerPromptTemplate(
    pre_messages="""
Based on the analysis of the input company and its top three competitors,
prepare a well-formatted report with a comparison table and actionable insights.
""",
    post_messages="Ensure the response is clear, concise, professional, and centered on the single input company.",
    final_answer_template="""
Provide a Markdown report for the input company with sections:
- Executive Summary
- Comparison Table
- SWOT Analysis
- What Competitors Are Doing Better (backed by editorial sources, not assumptions)
- Closing the Gap (how the company can gain market share vs peers and industry leaders)
- Actionable Insights
""",
)

prompt_templates = PromptTemplates(
    system_prompt=system_prompt,
    planning=planning_prompts,
    managed_agent=managed_agent_prompts,
    final_answer=final_answer_prompts,
)


# -----------------------------
# Runtime
# -----------------------------
def start_mcp_server() -> None:
    mcp.run(transport="streamable-http")


def run_analysis(company_name: str) -> str:
    server_thread = threading.Thread(target=start_mcp_server, daemon=True)
    server_thread.start()
    time.sleep(3)

    model = OpenAIServerModel(model_id=MODEL_ID)

    with MCPClient({"url": MCP_URL, "transport": "streamable-http"}) as tools:
        agent = ToolCallingAgent(
            tools=tools,
            model=model,
            add_base_tools=True,
            prompt_templates=prompt_templates,
        )
        result = agent.run(company_name)

    return result


if __name__ == "__main__":
    company = os.environ.get("COMPANY_NAME") or input("Enter a company name: ").strip()
    if not company:
        raise ValueError("Please enter a company name. Set the COMPANY_NAME environment variable.")

    output = run_analysis(company)
    print("\n" + output + "\n")