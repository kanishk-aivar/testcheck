import requests
import json
import time
import logging
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleSearchScraper:
    def __init__(self, max_queries=50):
        # Load environment variables
        load_dotenv()
        
        # Get API credentials
        self.api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        
        # Validate credentials
        if not self.api_key:
            raise ValueError("GOOGLE_SEARCH_API_KEY not found in environment variables")
        if not self.search_engine_id:
            raise ValueError("GOOGLE_SEARCH_ENGINE_ID not found in environment variables")
        
        # API endpoint
        self.api_endpoint = "https://www.googleapis.com/customsearch/v1"
        
        # Target website
        self.target_site = "mykitsch.com"
        
        # Query counter and limit
        self.query_count = 0
        self.max_queries = max_queries
        
        # Results storage
        self.results = {
            "metadata": {
                "total_queries": 0,
                "total_results": 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "quota_limited": False
            },
            "categories": {},
            "collections": {},
            "products": {},
            "pages": {},
            "search_results": []
        }
        
        # Track URLs to avoid duplicates
        self.processed_urls = set()
        
        # Track categories and collections
        self.discovered_categories = set()
        self.discovered_collections = set()
        self.discovered_products = set()
    
    def check_quota(self):
        """Check if we've reached the query limit"""
        if self.query_count >= self.max_queries:
            logger.warning(f"Query limit reached ({self.max_queries}). Stopping further requests.")
            self.results["metadata"]["quota_limited"] = True
            return False
        return True
    
    def search(self, query, num_results=10, start_index=1, search_type=None):
        """
        Perform a search using Google Custom Search API
        
        Args:
            query (str): The search query
            num_results (int, optional): Number of results to return (max 10 per request)
            start_index (int, optional): Starting index for pagination
            search_type (str, optional): Type of search ('image' for image search)
            
        Returns:
            dict: Search results
        """
        # Check if we've reached the query limit
        if not self.check_quota():
            return {"quota_exceeded": True}
        
        # Prepare parameters
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': min(num_results, 10),  # API limit is 10 per request
            'start': start_index
        }
        
        # Add optional parameters
        if search_type:
            params['searchType'] = search_type
        
        logger.info(f"Searching for: '{query}' (start: {start_index}, num: {num_results}) [Query {self.query_count + 1}/{self.max_queries}]")
        
        try:
            # Increment query counter
            self.query_count += 1
            
            # Make the API request
            response = requests.get(self.api_endpoint, params=params)
            
            # Check for API errors
            if response.status_code != 200:
                error_info = response.json() if response.text else {"error": "Unknown error"}
                logger.error(f"API error ({response.status_code}): {error_info}")
                
                # Print detailed error information
                if 'error' in error_info:
                    logger.error(f"Error details: {error_info['error'].get('message', 'No message')}")
                
                # Check for quota exceeded error
                if response.status_code == 429:
                    logger.error("API quota exceeded. Stopping further requests.")
                    self.results["metadata"]["quota_limited"] = True
                    return {"quota_exceeded": True}
                
                return {"error": error_info}
            
            # Parse the response
            data = response.json()
            
            # Update metadata
            self.results["metadata"]["total_queries"] += 1
            
            # Check if there are search results
            if 'items' in data:
                result_count = len(data['items'])
                logger.info(f"Found {result_count} results")
                self.results["metadata"]["total_results"] += result_count
                
                # Process and store the results
                for item in data['items']:
                    processed_item = self._process_search_item(item)
                    
                    # Only add if it's from the target site
                    if self.target_site in processed_item.get("displayLink", ""):
                        self.results["search_results"].append(processed_item)
                        
                        # Categorize the result
                        self._categorize_result(processed_item)
                
                return data
            else:
                logger.warning(f"No results found for '{query}'")
                return {"items": []}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e}")
            return {"error": str(e)}
    
    def _process_search_item(self, item):
        """Process a single search result item"""
        processed = {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "displayLink": item.get("displayLink", ""),
            "formattedUrl": item.get("formattedUrl", "")
        }
        
        # Add image information if available
        if "pagemap" in item and "cse_image" in item["pagemap"]:
            processed["image"] = item["pagemap"]["cse_image"][0].get("src", "")
        
        # Add additional metadata if available
        if "pagemap" in item and "metatags" in item["pagemap"] and item["pagemap"]["metatags"]:
            metatags = item["pagemap"]["metatags"][0]
            processed["metadata"] = {
                "description": metatags.get("og:description", metatags.get("description", "")),
                "type": metatags.get("og:type", ""),
                "site_name": metatags.get("og:site_name", ""),
                "price": metatags.get("og:price:amount", ""),
                "currency": metatags.get("og:price:currency", ""),
                "availability": metatags.get("og:availability", ""),
                "image": metatags.get("og:image", "")
            }
        
        return processed
    
    def _categorize_result(self, result):
        """Categorize a search result based on its URL pattern"""
        url = result.get("link", "")
        
        # Skip if already processed
        if url in self.processed_urls:
            return
        
        self.processed_urls.add(url)
        
        # Extract path from URL
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        
        # Categorize based on URL pattern
        if path.startswith('collections'):
            # It's a collection
            parts = path.split('/')
            if len(parts) >= 2:
                collection_name = parts[1]
                if collection_name not in self.discovered_collections:
                    self.discovered_collections.add(collection_name)
                    
                    # Store in collections
                    if collection_name not in self.results["collections"]:
                        self.results["collections"][collection_name] = {
                            "name": collection_name,
                            "url": url,
                            "title": result.get("title", ""),
                            "description": result.get("snippet", ""),
                            "products": []
                        }
                    
                    # If it's a product within a collection
                    if len(parts) >= 4 and parts[2] == "products":
                        product_name = parts[3]
                        if product_name not in self.discovered_products:
                            self.discovered_products.add(product_name)
                            self.results["collections"][collection_name]["products"].append({
                                "name": product_name,
                                "url": url,
                                "title": result.get("title", "")
                            })
        
        elif path.startswith('products'):
            # It's a product
            parts = path.split('/')
            if len(parts) >= 2:
                product_name = parts[1]
                if product_name not in self.discovered_products:
                    self.discovered_products.add(product_name)
                    self.results["products"][product_name] = {
                        "name": product_name,
                        "url": url,
                        "title": result.get("title", ""),
                        "description": result.get("snippet", ""),
                        "image": result.get("image", "")
                    }
                    
                    # Add metadata if available
                    if "metadata" in result:
                        self.results["products"][product_name].update({
                            "price": result["metadata"].get("price", ""),
                            "currency": result["metadata"].get("currency", ""),
                            "availability": result["metadata"].get("availability", "")
                        })
        
        elif path.startswith('pages'):
            # It's a page
            parts = path.split('/')
            if len(parts) >= 2:
                page_name = parts[1]
                if page_name not in self.results["pages"]:
                    self.results["pages"][page_name] = {
                        "name": page_name,
                        "url": url,
                        "title": result.get("title", ""),
                        "description": result.get("snippet", "")
                    }
        
        elif path and path not in self.results["categories"]:
            # It might be a category or other page
            self.results["categories"][path] = {
                "name": path,
                "url": url,
                "title": result.get("title", ""),
                "description": result.get("snippet", "")
            }
    
    def search_multiple_pages(self, query, total_results=30, search_type=None):
        """
        Search multiple pages to get more than 10 results
        
        Args:
            query (str): The search query
            total_results (int, optional): Total number of results to fetch
            search_type (str, optional): Type of search ('image' for image search)
            
        Returns:
            list: Combined search results
        """
        all_results = []
        results_per_page = 10
        pages_needed = min(10, (total_results + results_per_page - 1) // results_per_page)  # API limit is 10 pages (100 results)
        
        for page in range(pages_needed):
            # Check if we've reached the query limit
            if not self.check_quota():
                break
                
            start_index = page * results_per_page + 1
            
            logger.info(f"Fetching page {page+1} of {pages_needed}")
            
            # Make the search request
            response = self.search(
                query=query,
                num_results=results_per_page,
                start_index=start_index,
                search_type=search_type
            )
            
            # Check if there was an error or quota exceeded
            if 'error' in response or 'quota_exceeded' in response:
                break
            
            # Check if there are results
            if 'items' in response:
                all_results.extend(response['items'])
            else:
                # No more results
                break
            
            # Respect API rate limits
            if page < pages_needed - 1:
                logger.info("Waiting 1 second before next request...")
                time.sleep(1)
        
        logger.info(f"Total results fetched: {len(all_results)}")
        return all_results
    
    def execute_prioritized_searches(self):
        """Execute searches in priority order until quota is reached"""
        # Priority 1: Main site overview
        if self.check_quota():
            logger.info("Priority 1: Getting site overview...")
            self.search(f"site:{self.target_site}")
        
        # Priority 2: Key product categories
        key_categories = [
            "collections/best-sellers",
            "collections/hair",
            "collections/accessories",
            "products"
        ]
        
        for category in key_categories:
            if not self.check_quota():
                break
            logger.info(f"Priority 2: Searching {category}...")
            self.search(f"site:{self.target_site}/{category}")
        
        # Priority 3: Specific product types
        product_types = [
            "scrunchies",
            "headbands",
            "hair clips",
            "pillowcases",
            "shower caps"
        ]
        
        for product_type in product_types:
            if not self.check_quota():
                break
            logger.info(f"Priority 3: Searching for {product_type}...")
            self.search(f"site:{self.target_site} {product_type}")
        
        # Priority 4: Explore discovered collections
        collections_to_explore = list(self.discovered_collections)[:10]  # Limit to top 10
        for collection in collections_to_explore:
            if not self.check_quota():
                break
            logger.info(f"Priority 4: Exploring collection {collection}...")
            self.search(f"site:{self.target_site}/collections/{collection}")
    
    def save_results(self, filename="kitsch_site_data.json"):
        """Save search results to a JSON file"""
        # Convert sets to lists for JSON serialization
        self.results["metadata"]["discovered_collections"] = list(self.discovered_collections)
        self.results["metadata"]["discovered_products"] = list(self.discovered_products)
        self.results["metadata"]["processed_urls"] = list(self.processed_urls)
        self.results["metadata"]["queries_used"] = self.query_count
        self.results["metadata"]["queries_limit"] = self.max_queries
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filename}")
        return filename
    
    def get_results_summary(self):
        """Get a summary of the search results"""
        summary = {
            "total_queries": self.query_count,
            "query_limit": self.max_queries,
            "quota_limited": self.results["metadata"]["quota_limited"],
            "total_results": self.results["metadata"]["total_results"],
            "collections_found": len(self.results["collections"]),
            "products_found": len(self.results["products"]),
            "categories_found": len(self.results["categories"]),
            "pages_found": len(self.results["pages"]),
            "unique_urls": len(self.processed_urls)
        }
        
        return summary

    def test_api_connection(self):
        """Test the API connection with a simple query"""
        logger.info("Testing API connection...")
        
        # Simple test query
        test_query = "test"
        
        # Prepare parameters
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': test_query,
            'num': 1
        }
        
        try:
            # Make the API request
            response = requests.get(self.api_endpoint, params=params)
            
            # Print full response for debugging
            logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("API connection successful!")
                data = response.json()
                if 'items' in data:
                    logger.info(f"Found {len(data['items'])} results for test query")
                else:
                    logger.warning("No results found for test query")
                return True
            else:
                logger.error(f"API connection failed with status code: {response.status_code}")
                try:
                    error_info = response.json()
                    logger.error(f"Error details: {json.dumps(error_info, indent=2)}")
                except:
                    logger.error(f"Raw response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection test failed: {e}")
            return False


def main():
    try:
        # Initialize the scraper with a limit of 50 queries
        scraper = GoogleSearchScraper(max_queries=50)
        
        # Test the API connection first (counts as 1 query)
        if not scraper.test_api_connection():
            logger.error("API connection test failed. Please check your API key and search engine ID.")
            return
        
        # Execute searches in priority order
        scraper.execute_prioritized_searches()
        
        # Save the results
        results_file = scraper.save_results("kitsch_limited_data2.json")
        
        # Generate and display summary
        summary = scraper.get_results_summary()
        logger.info("Search Summary:")
        logger.info(f"Total queries used: {summary['total_queries']}/{summary['query_limit']}")
        logger.info(f"Quota limited: {summary['quota_limited']}")
        logger.info(f"Total results: {summary['total_results']}")
        logger.info(f"Collections found: {summary['collections_found']}")
        logger.info(f"Products found: {summary['products_found']}")
        logger.info(f"Categories found: {summary['categories_found']}")
        logger.info(f"Pages found: {summary['pages_found']}")
        logger.info(f"Unique URLs: {summary['unique_urls']}")
        
        # Save summary
        with open("kitsch_search_summary2.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info("Search completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()