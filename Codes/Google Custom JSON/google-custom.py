import requests
import json
import time
import logging
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

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
        
        # Results storage
        self.results = {
            "metadata": {
                "total_queries": 0,
                "total_results": 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "search_results": []
        }
    
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
                    self.results["search_results"].append(processed_item)
                
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
                "site_name": metatags.get("og:site_name", "")
            }
        
        return processed
    
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
    
    def save_results(self, filename="google_search_results.json"):
        """Save search results to a JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filename}")
        return filename
    
    def get_results_summary(self):
        """Get a summary of the search results"""
        summary = {
            "total_queries": self.results["metadata"]["total_queries"],
            "total_results": self.results["metadata"]["total_results"],
            "unique_domains": set(),
            "result_types": {}
        }
        
        # Analyze the results
        for result in self.results["search_results"]:
            # Count unique domains
            if "displayLink" in result:
                summary["unique_domains"].add(result["displayLink"])
            
            # Count result types if available
            if "metadata" in result and "type" in result["metadata"]:
                result_type = result["metadata"]["type"]
                summary["result_types"][result_type] = summary["result_types"].get(result_type, 0) + 1
        
        # Convert set to list for JSON serialization
        summary["unique_domains"] = list(summary["unique_domains"])
        summary["unique_domain_count"] = len(summary["unique_domains"])
        
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
        
        # Define search queries
        search_queries = [
            "kitsch hair accessories",
            "kitsch jewelry",
            "kitsch beauty products",
            "kitsch scrunchies",
            "kitsch headbands"
        ]
        
        # Search for each query
        for query in search_queries:
            logger.info(f"Searching for: {query}")
            
            # Perform the search
            scraper.search(query=query, num_results=10)
            
            # Wait between requests to respect API rate limits
            time.sleep(1)
        
        # Save the results
        results_file = scraper.save_results("kitsch_search_results.json")
        
        # Generate and display summary
        summary = scraper.get_results_summary()
        logger.info("Search Summary:")
        logger.info(f"Total queries: {summary['total_queries']}")
        logger.info(f"Total results: {summary['total_results']}")
        logger.info(f"Unique domains: {summary['unique_domain_count']}")
        logger.info(f"Result types: {summary['result_types']}")
        
        # Save summary
        with open("search_summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info("Search completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()