import json
import os
import unittest
from unittest.mock import Mock, patch

from scraper.scraper import CASINO_PAGES, build_output, llm_extract_bonus


class ScraperTests(unittest.TestCase):
    def test_ollama_response_is_parsed_as_json(self) -> None:
        expected = {
            "casino_name": "Betfair",
            "welcome_bonus": "Get 50 Free Spins",
            "wagering_requirement": "£10 qualifying stake",
            "minimum_deposit": "£10",
            "source_url": CASINO_PAGES[1]["source_url"],
        }
        response = Mock()
        response.json.return_value = {
            "message": {"content": json.dumps(expected)}
        }

        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            with patch("scraper.scraper.requests.post", return_value=response) as post:
                result = llm_extract_bonus("Betfair bonus text")

        self.assertEqual(result, expected)
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/chat")
        self.assertEqual(post.call_args.kwargs["json"]["format"], "json")

    def test_detailed_source_pages_extract_currency_and_qualifying_terms(self) -> None:
        pages = {
            CASINO_PAGES[0]["source_url"]: """
            <main><h1>Get 100 Free Spins at Bet365</h1>
            <p>A minimum deposit of £10 is required, and you must stake this on qualifying slot games.</p>
            <p>There are no wagering requirements for the Free Spins bonus or winnings.</p></main>
            """,
            CASINO_PAGES[1]["source_url"]: """
            <main><h1>Get 50 Free Spins + Deposit £10 for 50 More</h1>
            <p>Min deposit £10, wager at least £10 on eligible games.</p>
            </main>
            """,
            CASINO_PAGES[2]["source_url"]: """
            <main><h1>60 Free Spins + 100 Extra</h1>
            <p>No wagering rules are attached to the free spins.</p>
            <p>To claim the 100 free extra spins, the £10 deposit must be made by debit card.</p></main>
            """,
        }

        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            with patch("scraper.scraper.fetch_page", side_effect=pages.__getitem__):
                with patch("scraper.scraper.llm_extract_bonus", return_value=None):
                    records = build_output()

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["minimum_deposit"], "£10")
        self.assertEqual(records[0]["wagering_requirement"], "No wagering requirement (0x)")
        self.assertEqual(records[1]["minimum_deposit"], "£10")
        self.assertEqual(records[1]["wagering_requirement"], "£10 qualifying stake; no multiplier stated")
        self.assertEqual(records[2]["minimum_deposit"], "£10")
        self.assertEqual(records[2]["wagering_requirement"], "No wagering requirement (0x)")

    def test_llm_merge_preserves_source_terms(self) -> None:
        pages = {
            casino["source_url"]: """
            <main><h1>Get 100 Free Spins at Bet365</h1>
            <p>A minimum deposit of £10 is required; stake £10 on qualifying slots.</p>
            <p>There are no wagering requirements for the bonus winnings.</p></main>
            """
            for casino in CASINO_PAGES
        }

        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            with patch("scraper.scraper.fetch_page", side_effect=pages.__getitem__):
                with patch("scraper.scraper.llm_extract_bonus", return_value={
                    "welcome_bonus": "shortened offer",
                    "wagering_requirement": None,
                    "minimum_deposit": None,
                }):
                    records = build_output()

        self.assertEqual(records[0]["welcome_bonus"], "Get 100 Free Spins at Bet365")
        self.assertEqual(records[0]["wagering_requirement"], "No wagering requirement (0x); £10 qualifying stake")
        self.assertEqual(records[0]["minimum_deposit"], "£10")
        self.assertEqual(records[0]["extraction_status"], "llm-assisted extraction (ollama)")


if __name__ == "__main__":
    unittest.main()