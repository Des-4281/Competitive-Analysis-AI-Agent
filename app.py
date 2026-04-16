# app.py
import os
import re
import threading
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup
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

MODEL_ID = "gpt-4o-mini"
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
        "technology": ["microsoft", "apple", "amazon", "meta", "google", "ibm", "oracle", "intel"],
        "finance": ["jpmorgan", "bank of america", "goldman sachs", "morgan stanley", "citi", "wells fargo"],
        "healthcare": ["johnson & johnson", "pfizer", "merck", "novartis", "roche", "abbvie"],
        "education": ["great learning", "coursera", "udemy", "edx", "khan academy", "byju's", "pluralsight"],
        "retail": ["walmart", "target", "amazon", "home depot", "costco", "best buy"],
        "automotive": ["toyota", "ford", "general motors", "honda", "bmw", "mercedes-benz"],
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
        competitor_candidates = []

        results1 = web_search_tool(f"top {sector} companies competitors market share")
        competitor_candidates.extend(extract_competitors_advanced(results1, company_name, sector))
        time.sleep(1)

        results2 = web_search_tool(f"who are {company_name} main competitors in {sector}")
        competitor_candidates.extend(extract_competitors_advanced(results2, company_name, sector))
        time.sleep(1)

        results3 = web_search_tool(f"{sector} industry key players leading companies")
        competitor_candidates.extend(extract_competitors_advanced(results3, company_name, sector))

        final_competitors = rank_competitors(competitor_candidates, company_name)
        if final_competitors:
            return ", ".join(final_competitors[:3])
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
def generate_report(company_name: str, context: str) -> str:
    competitors = extract_competitors_from_context(context)

    competitor_rows = ""
    for competitor in competitors[:3]:
        competitor_rows += f"| {competitor} | - | - | - | - |\n"

    if not competitor_rows:
        competitor_rows = (
            "| Competitor A | - | - | - | - |\n"
            "| Competitor B | - | - | - | - |\n"
            "| Competitor C | - | - | - | - |\n"
        )

    report = f"""
# Competitive Analysis Report: {company_name}

## Executive Summary
Analysis of {company_name}'s competitive position based on available market data.

## Competitor Comparison

| Competitor | Strategy Type | Key Tactics | Strengths | Weaknesses |
|------------|---------------|-------------|-----------|------------|
{competitor_rows}

## Actionable Insights for {company_name}
- Develop differentiated positioning in the market
- Focus on unique value propositions
- Optimize operational efficiencies
- Enhance customer engagement strategies

*Report generated from context data. Fill in specific details based on comprehensive market research.*
"""
    return report.strip()


# -----------------------------
# Agent prompt templates
# -----------------------------
system_prompt = """
You are an expert Competitive Analysis Agent.

Given a single company name, do the following:
- Validate that it is a real company.
- Determine its primary industry sector.
- Identify its top three competitors, excluding the company itself.
- Gather real-time strategy data such as pricing, marketing, product offerings, quarterly earnings, press releases, and authentic news coverage using available tools.
- Compare the company with its top competitors and generate a formatted report with actionable insights.

Focus only on the provided company and its top three competitors.
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
4. Gather strategy data on the company and those competitors.
5. Analyze strategies and generate a comparison table.
6. Propose actionable insights.
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
    company = input("Enter a company name: ").strip()
    if not company:
        raise ValueError("Please enter a company name.")

    output = run_analysis(company)
    print("\n" + output + "\n")