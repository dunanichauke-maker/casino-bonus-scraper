Tools used: GitHub Copilot for coding and Ollama Llama 3.2 for bonus-text extraction.
Copilot helped with the Python scraper, Angular UI, tests, and documentation.
Ollama converted public offer text into structured fields for the generated JSON.
In an early run, Ollama shortened PlayOJO's offer and missed its no-wagering term; I caught this by comparing the JSON with the source page.
I changed the merge to preserve source wording and deterministic facts, then added tests for that behavior.
