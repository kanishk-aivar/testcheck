import os
import random
import asyncio
import datetime
import json
import logging

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from twocaptcha import TwoCaptcha
from dotenv import load_dotenv

# --- Load environment (2captcha API key) ---
load_dotenv()
CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY')
if not CAPTCHA_API_KEY:
    print('ERROR: CAPTCHA_API_KEY not found in your .env file')
    exit(1)

# Bright Data proxies (user:pass@host:port format)
BRIGHTDATA_PROXIES = [
    "brd-customer-hl_5b87c58d-zone-residential_proxy1:w0nuleam8o2q@brd.superproxy.io:33335",
    "brd-customer-hl_5b87c58d-zone-residential_proxy2:y44okq7d0wxs@brd.superproxy.io:33335"
]

JSON_FILE = "ai_overview_results_playwright.json"
LOGFILE = "ai_overview_scraper.log"

logging.basicConfig(
    filename=LOGFILE,
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO
)

def get_proxy():
    s = random.choice(BRIGHTDATA_PROXIES)
    # Format: username:password@host:port
    creds, hostport = s.split("@")
    user, pwd = creds.split(":", 1)
    host, port = hostport.split(":", 1)
    return {
        "server": f"http://{host}:{port}",
        "username": user,
        "password": pwd
    }

async def solve_recaptcha(page, query, proxy_dict):
    """
    Detect and solve reCAPTCHA with 2Captcha using the current proxy.
    """
    html = await page.content()
    if "recaptcha" not in html and "I'm not a robot" not in html:
        return False

    logging.warning(f"CAPTCHA encountered for '{query}' on {page.url}")

    # Extract sitekey
    import re
    match = re.search(r'data-sitekey="([\w-]+)"', html)
    sitekey = match.group(1) if match else None
    if not sitekey:
        logging.error("Could not extract sitekey for reCAPTCHA!")
        return False

    solver = TwoCaptcha(CAPTCHA_API_KEY)
    # Prepare proxy for 2Captcha
    server = proxy_dict['server'].replace('http://', '').replace('https://', '')
    host, port = server.split(':')
    user = proxy_dict['username']
    pwd = proxy_dict['password']

    try:
        result = solver.recaptcha(
            sitekey=sitekey,
            url=page.url,
            proxyType='http',
            proxyAddress=host,
            proxyPort=port,
            proxyLogin=user,
            proxyPassword=pwd,
            userAgent=await page.evaluate("() => navigator.userAgent")
        )
        token = result['code']
        logging.info(f"Solved reCAPTCHA with 2Captcha for '{query}'")
        # Set token(s) into the right fields
        await page.evaluate("""
        (token) => {
            document.querySelectorAll('textarea[name="g-recaptcha-response"],input[name="g-recaptcha-response"]').forEach(el => el.value = token);
        }
        """, token)
        # Usually Google reloads automatically; this ensures reload
        await asyncio.sleep(2)
        await page.reload()
        await page.wait_for_load_state("networkidle")
        return True
    except Exception as e:
        logging.error(f"2Captcha error ({str(e)}) for '{query}'")
        return False

async def fetch_ai_overview(query):
    proxy = get_proxy()
    logging.info(f"Using proxy {proxy['server']} for '{query}'")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,   # For debug; if stable change to True for headless
            proxy=proxy
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1320, "height": 850},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            ignore_https_errors=True   # <--- This is crucial for Bright Data proxies!
        )
        page = await context.new_page()
        # Stealth and browser humanization
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en"
        await page.goto(search_url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(random.uniform(3, 6))
        # CAPTCHA check and solve
        captcha_attempted = await solve_recaptcha(page, query, proxy)
        if captcha_attempted:
            await asyncio.sleep(random.uniform(4, 7))
        # --- AI Overview selectors / you may need to update these as Google changes UI!
        selectors = [
            'div[data-md="311"]',
            'div[data-attrid*="ai_overview"]',
            'div:has(span:has-text("AI-powered overview"))',
            'div[aria-label*="AI Overview"]',
            'div:has-text("AI-powered overview")',
        ]
        ai_block = None
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    ai_block = el
                    break
            except Exception:
                continue
        result = None
        if ai_block:
            ai_html = await ai_block.inner_html()
            ai_text = await ai_block.inner_text()
            links = await ai_block.query_selector_all("a")
            hyperlinks = []
            for link in links:
                href = await link.get_attribute("href")
                text = await link.inner_text()
                hyperlinks.append({'url': href, 'text': text})
            result = {
                "searchQuery": query,
                "extractedAt": datetime.datetime.now().isoformat(),
                "raw_html": ai_html,
                "plain_text": ai_text,
                "hyperlinks": hyperlinks,
                "proxy_used": proxy['server']
            }
            logging.info(f"AI Overview fetched for '{query}'")
        else:
            logging.warning(f"No AI Overview found for '{query}'; saving debug files.")
            await page.screenshot(path=f'debug_{query.replace(" ","_")}.png')
            with open(f'debug_{query.replace(" ","_")}.html', "w", encoding="utf-8") as f:
                f.write(await page.content())
        await context.close()
        await browser.close()
        return result

async def main():
    # Load existing results
    if os.path.isfile(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    else:
        data = []
    while True:
        user_query = input("\nEnter a Google query (or 'exit' to stop): ").strip()
        if user_query.lower() in ('exit', 'quit', ''):
            print("Goodbye!"); break
        print(f"\n[LOG] Requesting for: {user_query}")
        try:
            result = await fetch_ai_overview(user_query)
            if result:
                print("HTML preview:\n", result["raw_html"][:500])
                data.append(result)
                with open(JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"Saved to {JSON_FILE}.\n")
            else:
                print("No AI Overview captured.\n")
            logging.info("Sleeping random time before next request.")
            await asyncio.sleep(random.uniform(13, 27))
        except Exception as e:
            print(f"Error: {e} (see {LOGFILE})")
            logging.error(str(e))

if __name__ == "__main__":
    asyncio.run(main())
