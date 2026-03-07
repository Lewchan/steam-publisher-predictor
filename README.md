# Steam Publisher Predictor

Local web tool for estimating Steam game sales from Steam data, table-driven audience mapping, and a structured scoring model.

## Stack

- Streamlit for the web UI
- Python 3.11+ for scraping and prediction logic
- `httpx` + `selectolax` for Steam data collection
- `pytest` for tests
- GitHub Actions for CI only

## What It Does

- Search Steam by game name or paste a Steam app URL
- Fetch public store metadata, review summary, and Steam tags
- Estimate a benchmarked quality score from reviews and discussion proxies
- Map Steam tags into a table-driven user pool estimate
- Run the structured CL and sales model
- Show the intermediate values used by the model

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit, then search for a game and adjust the formula as needed.

## Project Layout

- `app.py`: Streamlit entrypoint
- `src/steam_publisher_predictor/services/steam_client.py`: Steam search and fetch logic
- `src/steam_publisher_predictor/services/quality.py`: quality scoring logic
- `src/steam_publisher_predictor/services/user_pool.py`: table-driven user pool mapping
- `src/steam_publisher_predictor/services/calculator.py`: CL and sales calculation
- `docs/Project_Spec.md`: formal project rules for inputs, formulas, and scraping policy
- `docs/Iteration_Development_Spec.md`: automatic iteration rules and execution policy
- `tests/`: unit tests

## Current Model

- `quality_score` uses weighted public-signal scoring
- `user_pool` comes from table-driven genre buckets plus fit adjustments
- `cl_score` is a weighted linear model capped at `3.0`
- `sales = user_pool * exposure * intent * purchase * (1 + cl)^3`

## Notes

- This project currently estimates sales using a structured rules model, not a trained production model.
- Steam endpoints can change. If one source fails, the fetch layer may need to be updated.
- The current "backend" is local Python service code inside the Streamlit app. There is no separate deployed server yet.
