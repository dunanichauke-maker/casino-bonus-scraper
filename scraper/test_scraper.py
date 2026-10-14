import json
import os
import unittest
from unittest.mock import Mock, patch

from scraper.scraper import build_output, llm_extract_bonus


class ScraperTests(unittest.TestCase):
    def test_ollama_response_is_parsed_as_json(self) -> None:
        expected = {
            "casino_name": "PlayOJO",
            "welcome_bonus": "free spins with no wagering requirements",
            "wagering_requirement": 0,
            "minimum_deposit": None,
            "source_url": "https://casinobonus.com/",
        }
        response = Mock()
        response.json.return_value = {
            "message": {"content": json.dumps(expected)}
        }

        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            with patch("scraper.scraper.requests.post", return_value=response) as post:
                result = llm_extract_bonus("PlayOJO bonus text")

        self.assertEqual(result, expected)
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/chat")
        self.assertEqual(post.call_args.kwargs["json"]["format"], "json")

    def test_llm_merge_preserves_source_text_and_known_wagering(self) -> None:
        source_html = """
        <p>Example: LeoVegas offers up to $1,000 + 200 free spins</p>
        <p>Example: Bet365 offers 50 free spins on popular slots</p>
        <p>Example: PlayOJO offers free spins with no wagering requirements</p>
        """
        model_result = {
            "welcome_bonus": "free spins",
            "wagering_requirement": None,
            "minimum_deposit": None,
        }

        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            with patch("scraper.scraper.fetch_page", return_value=source_html):
                with patch("scraper.scraper.llm_extract_bonus", return_value=model_result):
                    records = build_output()

        playojo = next(record for record in records if record["casino_name"] == "PlayOJO")
        self.assertEqual(playojo["welcome_bonus"], "free spins with no wagering requirements")
        self.assertEqual(playojo["wagering_requirement"], 0)
        self.assertEqual(playojo["extraction_status"], "llm-assisted extraction (ollama)")


if __name__ == "__main__":
    unittest.main()