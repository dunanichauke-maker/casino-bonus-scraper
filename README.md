# Casino Bonus Scraper and UI

This project builds a small full-stack assessment that scrapes three detailed UK welcome-offer pages from one public source, uses an LLM-assisted extraction step, writes a JSON file, and renders it in a responsive Angular table.

## Overview

- Python scraper: reads individual Casinobonus.com UK welcome-offer pages for Bet365, Betfair, and Paddy Power.
- Structured output: saves the data as JSON for the frontend.
- Angular frontend: reads the JSON and shows a mobile-friendly comparison table.
- Source used: https://casinobonus.com/uk/casino-bonuses/welcome-bonuses/

## Repository layout

- `scraper/scraper.py` — public-source scraper and extraction logic.
- `scraper/requirements.txt` — Python dependencies.
- `scraper/.env.example` — sample environment configuration.
- `frontend/` — Angular app that displays the scraped data.
- `README.md` — setup and usage guide.
- `PRODUCTION_PLAN.md` — production architecture plan.
- `PRODUCTION_PLAN.docx` — Word version of the written assessment section.
- `AI_USAGE.md` — five-line AI disclosure.

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm 10+

## Python setup

From the workspace root:

```bash
python -m venv .venv
. .venv/bin/activate   # Linux/macOS
.\.venv\Scripts\Activate.ps1  # PowerShell
pip install -r scraper/requirements.txt
```

## LLM configuration

The scraper supports local Ollama without an API key and OpenAI when an API key is available. For Ollama, install and start Ollama, ensure the configured model is downloaded, then copy the sample environment file:

```bash
copy scraper\.env.example scraper\.env
```

The sample selects local Ollama with `llama3.2`. To use OpenAI instead, edit `scraper/.env`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

The scraper reports how many records used LLM extraction and how many used deterministic fallback. If the selected provider is unavailable or returns invalid JSON, the scraper falls back to the visible source text instead of inventing values.

## Run the scraper

From the workspace root:

```bash
python scraper/scraper.py
```

This generates:

- `scraper/output/bonuses.json`
- `frontend/src/assets/bonuses.json`

## Run scraper tests

The focused unit tests use mocked source and model responses, so they run without network access or an LLM service:

```bash
python -m unittest discover -s . -p "test_*.py"
```

## Run the Angular app locally

```bash
cd frontend
npm install
npm start
```

Then open the local URL shown in the terminal, usually `http://localhost:4200`.

## Build for static hosting

```bash
cd frontend
npx ng build --configuration production --base-href /casino-bonus-scraper/
```

This produces a static build in `frontend/dist/frontend/browser`.

## GitHub Pages deployment

The workflow at `.github/workflows/deploy-pages.yml` builds the Angular app and deploys it to the free GitHub Pages hosting service when code is pushed to `main` or `master`. In the repository settings, set **Pages > Build and deployment > Source** to **GitHub Actions**. The expected URL is `https://<github-username>.github.io/casino-bonus-scraper/`.

The public site is live at https://dunanichauke-maker.github.io/casino-bonus-scraper/. The latest GitHub Actions deployment completed successfully.

## Known limitations

- Time spent on the assessment: approximately 2 hours 45 minutes.
- This is intentionally a small proof-of-concept, not a production-grade scraper platform.
- Offers are UK-specific and may change; the source URL for each casino is retained for verification.
- Betfair specifies a qualifying stake but no wagering multiplier; the scraper labels the stake without converting it into a multiplier.
- Terms absent from a source page remain `null` rather than being guessed.
- Local Ollama extraction runs without an API key; OpenAI extraction requires an API key.

## Verification performed

- Three individual UK offer pages from Casinobonus.com were fetched and parsed.
- Local Ollama (`llama3.2`) completed LLM-assisted extraction for all three records; the JSON records the extraction status.
- The scraper output JSON was generated successfully in both scraper output and frontend asset locations.
- Angular production build was run and verified locally.

## Local repository status

The project is published at https://github.com/dunanichauke-maker/casino-bonus-scraper/ and deployed at https://dunanichauke-maker.github.io/casino-bonus-scraper/.
