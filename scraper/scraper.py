from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

SOURCE_URL = "https://casinobonus.com/"
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


def parse_last_updated(html: str) -> str | None:
    match = re.search(r"All bonuses verified\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", html, re.IGNORECASE)
    if match:
        date_text = match.group(1)
        try:
            return datetime.strptime(date_text, "%B %d, %Y").isoformat()
        except ValueError:
            return date_text
    return None


def extract_example_offers(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    lines: list[dict[str, str]] = []
    for paragraph in soup.select("p"):
        text = paragraph.get_text(" ", strip=True)
        if not text or "Example:" not in text:
            continue
        if "offers" not in text.lower() and "free spins" not in text.lower():
            continue
        match = re.search(
            r"Example:\s*(?P<casino>[A-Z][A-Za-z0-9 .&'-]+?)\s+(?:offers|offers up to|features|gives|has)\s+(?P<offer>.+)",
            text,
            re.IGNORECASE,
        )
        if not match:
            continue
        casino = match.group("casino").strip()
        offer = match.group("offer").strip()
        lines.append({"casino_name": casino, "offer_text": offer})
    # Keep the source’s real examples in a stable, explicit order.
    preferred = ["LeoVegas", "Bet365", "PlayOJO"]
    ordered: list[dict[str, str]] = []
    for name in preferred:
        for entry in lines:
            if entry["casino_name"] == name:
                ordered.append(entry)
                break
    return ordered


def extract_wagering(text: str) -> int | None:
    lower = text.lower()
    if "no wagering requirements" in lower or "wager-free" in lower:
        return 0
    match = re.search(r"(\d+)\s*x\s*(?:wager|wagering)", lower)
    if match:
        return int(match.group(1))
    return None


def extract_minimum_deposit(text: str) -> float | None:
    match = re.search(r"(?:minimum\s+deposit|min(?:imum)?\s+deposit)\s*(?:is|of)?\s*\$?(\d+(?:,\d{3})*(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        value = match.group(1).replace(",", "")
        return float(value)
    return None


def llm_extract_bonus(raw_text: str) -> dict[str, Any] | None:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    messages = [
        {
            "role": "system",
            "content": "You convert casino bonus text into a valid JSON object. Return only JSON with keys: casino_name, welcome_bonus, wagering_requirement, minimum_deposit, source_url. Use null when the text does not specify a value. Do not invent values. Preserve currency symbols and conditions. Wagering requirement must be a number or null, not a percentage or monetary amount.",
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

    if validated["wagering_requirement"] is not None:
        try:
            validated["wagering_requirement"] = int(validated["wagering_requirement"])
        except (TypeError, ValueError):
            validated["wagering_requirement"] = None

    if validated["minimum_deposit"] is not None:
        try:
            validated["minimum_deposit"] = float(validated["minimum_deposit"])
        except (TypeError, ValueError):
            validated["minimum_deposit"] = None

    return validated


def build_output() -> list[dict[str, Any]]:
    page_html = fetch_page(SOURCE_URL)
    examples = extract_example_offers(page_html)
    if not examples:
        raise RuntimeError("No public bonus examples were found in the source HTML.")

    items: list[dict[str, Any]] = []
    last_updated = parse_last_updated(page_html)
    for entry in examples:
        casino_name = entry["casino_name"]
        offer_text = entry["offer_text"]
        fallback = {
            "casino_name": casino_name,
            "welcome_bonus": offer_text,
            "wagering_requirement": extract_wagering(offer_text),
            "minimum_deposit": extract_minimum_deposit(offer_text),
            "source_url": SOURCE_URL,
            "last_updated": last_updated,
            "extraction_status": "deterministic extraction from public source text",
        }

        llm_result = llm_extract_bonus(f"Casino: {casino_name}\nBonus text: {offer_text}\nSource: {SOURCE_URL}")
        if llm_result:
            result = {
                "casino_name": llm_result.get("casino_name") or casino_name,
                "welcome_bonus": offer_text,
                "wagering_requirement": fallback["wagering_requirement"] if fallback["wagering_requirement"] is not None else llm_result.get("wagering_requirement"),
                "minimum_deposit": fallback["minimum_deposit"] if fallback["minimum_deposit"] is not None else llm_result.get("minimum_deposit"),
                "source_url": SOURCE_URL,
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
