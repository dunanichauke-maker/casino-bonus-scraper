from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

SOURCE_URL = "https://casinobonus.com/"
CASINO_PAGES = [
    {
        "casino_name": "Bet365",
        "source_url": "https://casinobonus.com/uk/casino-bonuses/welcome-bonuses/bet365",
    },
    {
        "casino_name": "Betfair",
        "source_url": "https://casinobonus.com/uk/casino-bonuses/welcome-bonuses/betfair",
    },
    {
        "casino_name": "Paddy Power",
        "source_url": "https://casinobonus.com/uk/casino-bonuses/welcome-bonuses/paddy-power",
    },
]
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "bonuses.json"
ASSET_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "assets" / "bonuses.json"

def load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    response = requests.get(url, timeout=30, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    return response.text


def extract_offer_details(html: str, casino_name: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("main") or soup.body or soup
    headings = [heading.get_text(" ", strip=True) for heading in content.find_all("h1")]
    if not headings:
        raise RuntimeError(f"No offer heading found for {casino_name}.")

    source_text = "\n".join(
        text
        for element in content.find_all(["h1", "h2", "h3", "p", "li"])
        if (text := element.get_text(" ", strip=True))
    )
    return {
        "welcome_bonus": headings[0],
        "source_text": source_text[:16000],
    }


def extract_wagering(text: str) -> str | None:
    no_wagering = re.search(r"no wagering (?:requirements?|rules)", text, re.IGNORECASE)
    stake_match = re.search(
        r"(?:stake|spend|wager)\s+(?:at least\s+)?([£$€]\s?\d[\d,]*(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE,
    )
    if no_wagering:
        if stake_match:
            return f"No wagering requirement (0x); {stake_match.group(1).replace(' ', '')} qualifying stake"
        return "No wagering requirement (0x)"

    multiplier_match = re.search(
        r"(\d+(?:\.\d+)?)\s*x\s*(?:wager|wagering|rollover)",
        text,
        re.IGNORECASE,
    )
    if multiplier_match:
        return f"{multiplier_match.group(1)}x wagering requirement"
    if stake_match:
        return f"{stake_match.group(1).replace(' ', '')} qualifying stake; no multiplier stated"
    return None


def extract_minimum_deposit(text: str) -> str | None:
    amount = r"([£$€]\s?\d[\d,]*(?:\.\d{1,2})?)"
    patterns = (
        rf"(?:minimum|min\.?)\s+deposit(?:\s+(?:of|is))?\s*(?:at least\s*)?{amount}",
        rf"(?:first|qualifying)\s+deposit\s+(?:of\s+)?(?:at least\s*)?{amount}",
        rf"deposit\s+(?:of\s+)?(?:at least\s*)?{amount}",
        rf"{amount}\s+deposit",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(" ", "").rstrip(".,")
    return None


def llm_extract_bonus(raw_text: str) -> dict[str, Any] | None:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    messages = [
        {
            "role": "system",
            "content": "You convert casino bonus source text into a valid JSON object. Return only JSON with keys: casino_name, welcome_bonus, wagering_requirement, minimum_deposit, source_url. Use null when the text does not specify a value. Do not invent values. Preserve exact offer wording and currency symbols. Wagering requirement must be a string that distinguishes a rollover multiplier from a qualifying stake; do not mislabel a stake as a multiplier.",
        },
        {
            "role": "user",
            "content": raw_text,
        },
    ]

    if provider == "ollama":
        url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')}/api/chat"
        payload = {
            "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        headers = {"Content-Type": "application/json"}
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        print(f"Unsupported LLM_PROVIDER '{provider}'; using deterministic fallback.", file=sys.stderr)
        return None

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(5, 120),
        )
        response.raise_for_status()
        response_data = response.json()
        if provider == "ollama":
            content = response_data["message"]["content"]
        else:
            content = response_data["choices"][0]["message"]["content"]
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"{provider} extraction failed: {exc}", file=sys.stderr)
        return None
    return None


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    validated = {
        "casino_name": record.get("casino_name") or record.get("casino") or "Unknown casino",
        "welcome_bonus": record.get("welcome_bonus") or record.get("bonus") or record.get("offer_text") or "Not available",
        "wagering_requirement": record.get("wagering_requirement"),
        "minimum_deposit": record.get("minimum_deposit"),
        "source_url": record.get("source_url") or SOURCE_URL,
        "last_updated": record.get("last_updated"),
        "extraction_status": record.get("extraction_status") or "verified from source text",
    }

    for field in ("wagering_requirement", "minimum_deposit"):
        if validated[field] is not None:
            validated[field] = str(validated[field])

    return validated


def build_output() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    last_updated = datetime.now(timezone.utc).isoformat()
    for casino in CASINO_PAGES:
        casino_name = casino["casino_name"]
        source_url = casino["source_url"]
        page_html = fetch_page(source_url)
        details = extract_offer_details(page_html, casino_name)
        offer_text = details["welcome_bonus"]
        fallback = {
            "casino_name": casino_name,
            "welcome_bonus": offer_text,
            "wagering_requirement": extract_wagering(details["source_text"]),
            "minimum_deposit": extract_minimum_deposit(details["source_text"]),
            "source_url": source_url,
            "last_updated": last_updated,
            "extraction_status": "deterministic extraction from source page",
        }

        llm_result = llm_extract_bonus(
            f"Casino: {casino_name}\nSource: {source_url}\nOffer and terms:\n{details['source_text']}"
        )
        if llm_result:
            result = {
                "casino_name": llm_result.get("casino_name") or casino_name,
                "welcome_bonus": offer_text,
                "wagering_requirement": fallback["wagering_requirement"] if fallback["wagering_requirement"] is not None else llm_result.get("wagering_requirement"),
                "minimum_deposit": fallback["minimum_deposit"] if fallback["minimum_deposit"] is not None else llm_result.get("minimum_deposit"),
                "source_url": source_url,
                "last_updated": last_updated,
                "extraction_status": f"llm-assisted extraction ({os.getenv('LLM_PROVIDER', 'openai').strip().lower()})",
            }
        else:
            result = fallback

        items.append(validate_record(result))

    return items


def write_json(data: list[dict[str, Any]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    ASSET_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ASSET_OUTPUT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    load_env()
    try:
        data = build_output()
        write_json(data)
        print(f"Wrote {len(data)} casino records to {OUTPUT_PATH}")
        llm_count = sum("llm-assisted extraction" in item["extraction_status"] for item in data)
        fallback_count = len(data) - llm_count
        print(f"LLM-assisted extraction used for {llm_count}/{len(data)} records.")
        if fallback_count:
            print(f"Deterministic extraction fallback used for {fallback_count} records.")
    except Exception as exc:  # pragma: no cover - explicit failure message for the user
        raise SystemExit(f"Scraper failed: {exc}")


if __name__ == "__main__":
    main()
