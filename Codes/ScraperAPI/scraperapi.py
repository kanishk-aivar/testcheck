import os
import json
from dotenv import load_dotenv
import requests
import datetime

# Load ScraperAPI key from .env
load_dotenv()
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
if not SCRAPERAPI_KEY:
    raise ValueError("Please set SCRAPERAPI_KEY in your .env file")

JSON_FILE = 'ai_overview_results_scraperapi.json'

# Load existing results if available
if os.path.isfile(JSON_FILE):
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
else:
    data = []

def fetch_google_ai_overview(query, country='us', lang='en'):
    params = {
        "api_key": SCRAPERAPI_KEY,
        "autoparse": "true",
        "country": country,
        "query": query,
        "hl": lang
    }
    api_url = "https://api.scraperapi.com/structured/google/search"

    resp = requests.get(api_url, params=params)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}")
        return None

    serp = resp.json()
    # The AI Overview will usually be in another field in the JSON.
    # Print all top-level fields for inspection if needed:
    # print(json.dumps(serp, indent=2))

    ai_overview = None
    # Look for "ai_overview" or any field containing the AI module
    for key in serp:
        if "ai_overview" in key or "generative" in key:
            ai_overview = serp[key]
            break

    # If not present, check organic_results for generative segments
    if not ai_overview and "organic_results" in serp:
        for result in serp["organic_results"]:
            if isinstance(result, dict) and ("ai_overview" in result or "generative" in result):
                ai_overview = result.get("ai_overview") or result.get("generative")
                break

    # Fallback: capture whole JSON if still not found
    if not ai_overview:
        print("No explicit AI overview detected; saving full SERP JSON for manual inspection.")
        ai_overview = None # let the record be flagged

    return {
        "searchQuery": query,
        "extractedAt": datetime.datetime.now().isoformat(),
        "full_serp": serp,
        "ai_overview": ai_overview
    }

def main():
    while True:
        user_query = input("\nEnter a Google query (or 'exit' to stop): ").strip()
        if user_query.lower() in ('exit', 'quit', ''):
            print("Goodbye!")
            break

        print(f"Fetching Google AI Overview (via ScraperAPI) for: '{user_query}'")
        record = fetch_google_ai_overview(user_query)
        if record is None:
            print("No data returned (API error or limit hit).")
            continue

        if record['ai_overview']:
            print("AI Overview: ", str(record['ai_overview'])[:500], "...")
        else:
            print("No AI Overview found for this query. See 'full_serp' field in output for further details.")

        data.append(record)
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved output for '{user_query}' to {JSON_FILE}\n")

if __name__ == "__main__":
    main()
