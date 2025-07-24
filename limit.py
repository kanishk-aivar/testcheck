import requests
import json
import time
import logging
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus, urlparse, parse_qs
import re
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleSearchScraper:
    def __init__(self):
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
        
        # Results storage
        self.results = {
            "metadata": {
                "total_queries": 0,
                "total_results": 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
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
        
        logger.info(f"Searching for: '{query}' (start: {start_index}, num: {num_results})")
        
        try:
            # Make the API request
            response = requests.get(self.api_endpoint, params=params)
            
            # Check for API errors
            if response.status_code != 200:
                error_info = response.json() if response.text else {"error": "Unknown error"}
                logger.error(f"API error ({response.status_code}): {error_info}")
                
                # Print detailed error information
                if 'error' in error_info:
                    logger.error(f"Error details: {error_info['error'].get('message', 'No message')}")
                
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
            "htmlSnippet": item.get("htmlSnippet", ""),
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
            
            # Extract product information if available
            if "product" in metatags.get("og:type", "").lower():
                processed["product_info"] = {
                    "name": metatags.get("og:title", processed["title"]),
                    "price": metatags.get("og:price:amount", ""),
                    "currency": metatags.get("og:price:currency", ""),
                    "availability": metatags.get("og:availability", ""),
                    "image": metatags.get("og:image", ""),
                    "brand": metatags.get("og:brand", "Kitsch")
                }
        
        # Extract structured data if available
        if "pagemap" in item:
            if "product" in item["pagemap"]:
                product_data = item["pagemap"]["product"][0]
                processed["structured_product"] = {
                    "name": product_data.get("name", ""),
                    "description": product_data.get("description", ""),
                    "price": product_data.get("price", ""),
                    "availability": product_data.get("availability", ""),
                    "sku": product_data.get("sku", ""),
                    "brand": product_data.get("brand", "")
                }
            
            if "offer" in item["pagemap"]:
                offer_data = item["pagemap"]["offer"][0]
                processed["structured_offer"] = {
                    "price": offer_data.get("price", ""),
                    "currency": offer_data.get("pricecurrency", ""),
                    "availability": offer_data.get("availability", "")
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
                            
                            # Also add to products
                            if product_name not in self.results["products"]:
                                self._add_product(result, product_name, collection_name)
        
        elif path.startswith('products'):
            # It's a product
            parts = path.split('/')
            if len(parts) >= 2:
                product_name = parts[1]
                if product_name not in self.discovered_products:
                    self.discovered_products.add(product_name)
                    self._add_product(result, product_name)
        
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
        
        elif path == "" or path.startswith('search'):
            # It's the homepage or search page
            pass
        
        else:
            # It might be a category or other page
            if path not in self.results["categories"] and path:
                self.results["categories"][path] = {
                    "name": path,
                    "url": url,
                    "title": result.get("title", ""),
                    "description": result.get("snippet", "")
                }
    
    def _add_product(self, result, product_name, collection_name=None):
        """Add a product to the results"""
        product_info = {
            "name": product_name,
            "url": result.get("link", ""),
            "title": result.get("title", ""),
            "description": result.get("snippet", ""),
            "image": result.get("image", "")
        }
        
        # Add metadata if available
        if "metadata" in result:
            product_info.update({
                "description": result["metadata"].get("description", product_info["description"]),
                "price": result["metadata"].get("price", ""),
                "currency": result["metadata"].get("currency", ""),
                "availability": result["metadata"].get("availability", ""),
                "image": result["metadata"].get("image", product_info["image"])
            })
        
        # Add structured product data if available
        if "structured_product" in result:
            product_info.update({
                "name": result["structured_product"].get("name", product_info["name"]),
                "description": result["structured_product"].get("description", product_info["description"]),
                "price": result["structured_product"].get("price", product_info.get("price", "")),
                "availability": result["structured_product"].get("availability", product_info.get("availability", "")),
                "sku": result["structured_product"].get("sku", ""),
                "brand": result["structured_product"].get("brand", "Kitsch")
            })
        
        # Add structured offer data if available
        if "structured_offer" in result:
            product_info.update({
                "price": result["structured_offer"].get("price", product_info.get("price", "")),
                "currency": result["structured_offer"].get("currency", product_info.get("currency", "")),
                "availability": result["structured_offer"].get("availability", product_info.get("availability", ""))
            })
        
        # Add collection information if available
        if collection_name:
            product_info["collection"] = collection_name
        
        # Store the product
        self.results["products"][product_name] = product_info
    
    def search_multiple_pages(self, query, total_results=100, search_type=None):
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
            start_index = page * results_per_page + 1
            
            logger.info(f"Fetching page {page+1} of {pages_needed}")
            
            # Make the search request
            response = self.search(
                query=query,
                num_results=results_per_page,
                start_index=start_index,
                search_type=search_type
            )
            
            # Check if there was an error
            if 'error' in response:
                logger.error(f"Error in search request: {response.get('error')}")
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
    
    def discover_site_structure(self):
        """
        Discover the site structure by searching for key sections
        """
        # First, search for the site: operator to get an overview
        logger.info("Discovering site structure...")
        self.search_multiple_pages(f"site:{self.target_site}", total_results=100)
        
        # Search for collections
        logger.info("Discovering collections...")
        self.search_multiple_pages(f"site:{self.target_site}/collections", total_results=100)
        
        # Search for products
        logger.info("Discovering products...")
        self.search_multiple_pages(f"site:{self.target_site}/products", total_results=100)
        
        # Search for specific product categories
        product_categories = [
            "hair", "accessories", "scrunchies", "headbands", "clips", 
            "jewelry", "beauty", "skincare", "bath", "sleep", 
            "travel", "gift", "sale", "new"
        ]
        
        for category in product_categories:
            logger.info(f"Searching for {category} products...")
            self.search(f"site:{self.target_site} {category}")
            time.sleep(1)  # Respect API rate limits
            
            # Also search in collections
            self.search(f"site:{self.target_site}/collections {category}")
            time.sleep(1)
        
        # Search for specific product types
        product_types = [
            "scrunchie", "headband", "clip", "claw", "brush", "towel", 
            "pillow", "mask", "earring", "necklace", "bracelet", "ring"
        ]
        
        for product_type in product_types:
            logger.info(f"Searching for {product_type} products...")
            self.search(f"site:{self.target_site} {product_type}")
            time.sleep(1)
            
            # Also search in products directory
            self.search(f"site:{self.target_site}/products {product_type}")
            time.sleep(1)
    
    def discover_collections(self):
        """
        Discover all collections on the site
        """
        logger.info("Discovering collections in depth...")
        
        # First get all collections
        self.search_multiple_pages(f"site:{self.target_site}/collections", total_results=100)
        
        # Then search for each discovered collection to get more details
        collections_to_search = list(self.discovered_collections)
        for collection in collections_to_search:
            logger.info(f"Searching collection: {collection}")
            self.search(f"site:{self.target_site}/collections/{collection}")
            time.sleep(1)
            
            # Also search for products in this collection
            self.search(f"site:{self.target_site}/collections/{collection}/products")
            time.sleep(1)
    
    def discover_products(self):
        """
        Discover products in depth
        """
        logger.info("Discovering products in depth...")
        
        # Search for all products
        self.search_multiple_pages(f"site:{self.target_site}/products", total_results=100)
        
        # Search for specific product attributes
        attributes = ["color", "size", "material", "price", "sale", "new", "bestseller", "limited"]
        
        for attribute in attributes:
            logger.info(f"Searching for products with attribute: {attribute}")
            self.search(f"site:{self.target_site} {attribute}")
            time.sleep(1)
    
    def save_results(self, filename="kitsch_site_data.json"):
        """Save search results to a JSON file"""
        # Convert sets to lists for JSON serialization
        self.results["metadata"]["discovered_collections"] = list(self.discovered_collections)
        self.results["metadata"]["discovered_products"] = list(self.discovered_products)
        self.results["metadata"]["processed_urls"] = list(self.processed_urls)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filename}")
        return filename
    
    def get_results_summary(self):
        """Get a summary of the search results"""
        summary = {
            "total_queries": self.results["metadata"]["total_queries"],
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
            logger.info(f"Response headers: {response.headers}")
            
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
        # Initialize the scraper
        scraper = GoogleSearchScraper()
        
        # Test the API connection first
        if not scraper.test_api_connection():
            logger.error("API connection test failed. Please check your API key and search engine ID.")
            return
        
        # Discover the site structure
        scraper.discover_site_structure()
        
        # Discover collections in depth
        scraper.discover_collections()
        
        # Discover products in depth
        scraper.discover_products()
        
        # Save the results
        results_file = scraper.save_results("kitsch_comprehensive_data2.json")
        
        # Generate and display summary
        summary = scraper.get_results_summary()
        logger.info("Search Summary:")
        logger.info(f"Total queries: {summary['total_queries']}")
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
