import json
import datetime
from serpapi import GoogleSearch
import os
from dotenv import load_dotenv

# --- Load your SerpApi key securely
load_dotenv()
api_key = os.getenv("SERPAPI_API_KEY")
if not api_key:
    print("ERROR: Please set SERPAPI_API_KEY in your .env file")
    exit(1)

JSON_FILE = 'ai_overview_results.json'

# Load or start new JSON array
if os.path.isfile(JSON_FILE):
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
else:
    data = []

def extract_ai_overview_full(query, api_key):
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "hl": "en",
        "gl": "us"
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    ai_overview = results.get('ai_overview')
    if not ai_overview:
        return None

    # Build a result containing ALL fields ("window") from ai_overview
    full_window = {
        "searchQuery": query,
        "extractedAt": datetime.datetime.now().isoformat(),
    }
    # Merge all ai_overview fields as-is
    full_window.update(ai_overview)
    return full_window

while True:
    user_query = input("\nEnter a Google query (or 'exit' to stop): ").strip()
    if user_query.lower() in ('exit', 'quit', ''):
        print("Goodbye!")
        break
    print(f"Fetching full AI Overview window for: {user_query} ...")
    result = extract_ai_overview_full(user_query, api_key)
    if not result:
        print("No AI Overview returned for this query.")
        continue

    print(f"=== AI Overview WINDOW keys: {list(result.keys())}")
    print("Sample of summary/text/HTML:\n", result.get('summary', '')[:400] or result.get('text', '')[:400])
    print("\nSaving full AI Overview...")

    data.append(result)
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved AI Overview window for '{user_query}' in {JSON_FILE}.\n")
