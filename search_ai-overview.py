import time
import logging
import os
import json
import random
from dotenv import load_dotenv
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleAIOverviewScraper:
    def __init__(self, max_queries=20):
        # Load environment variables
        load_dotenv()
        
        # Get API key
        self.api_key = os.getenv('SERPAPI_KEY')
        if not self.api_key:
            raise ValueError("SERPAPI_KEY not found in environment variables")
        
        # Query counter and limit
        self.query_count = 0
        self.max_queries = max_queries
        
        # Results storage
        self.results = {
            "metadata": {
                "total_queries": 0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "quota_limited": False
            },
            "ai_overviews": []
        }
        
        # Track processed queries
        self.processed_queries = set()
    
    def check_quota(self):
        """Check if we've reached the query limit"""
        if self.query_count >= self.max_queries:
            logger.warning(f"Query limit reached ({self.max_queries}). Stopping further requests.")
            self.results["metadata"]["quota_limited"] = True
            return False
        return True
    
    def search_and_extract_ai_overview(self, query):
        """
        Perform a Google search and extract AI Overview content using SerpAPI
        
        Args:
            query (str): The search query
            
        Returns:
            dict: AI Overview content and links
        """
        # Skip if already processed
        if query in self.processed_queries:
            logger.info(f"Query '{query}' already processed. Skipping.")
            return {"skipped": True}
        
        self.processed_queries.add(query)
        
        # Check if we've reached the query limit
        if not self.check_quota():
            return {"quota_exceeded": True}
        
        logger.info(f"Searching for: '{query}' [Query {self.query_count + 1}/{self.max_queries}]")
        
        try:
            # Increment query counter
            self.query_count += 1
            
            # Prepare the API request
            params = {
                "api_key": self.api_key,
                "engine": "google",
                "q": query,
                "google_domain": "google.com",
                "gl": "us",
                "hl": "en"
            }
            
            # Make the request
            response = requests.get("https://serpapi.com/search", params=params)
            
            # Check for errors
            if response.status_code != 200:
                logger.error(f"API request failed with status code: {response.status_code}")
                return {"error": f"HTTP {response.status_code}"}
            
            # Parse the response
            data = response.json()
            
            # Update metadata
            self.results["metadata"]["total_queries"] += 1
            
            # Extract AI Overview
            ai_overview = self._extract_ai_overview_from_response(data)
            
            if ai_overview:
                logger.info(f"Found AI Overview for '{query}'")
                
                # Add to results
                overview_entry = {
                    "query": query,
                    "content": ai_overview["content"],
                    "links": ai_overview["links"]
                }
                
                self.results["ai_overviews"].append(overview_entry)
                return {"ai_overview": overview_entry}
            else:
                logger.warning(f"No AI Overview found for '{query}'")
                return {"no_ai_overview": True}
                
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return {"error": str(e)}
    
    def _extract_ai_overview_from_response(self, data):
        """Extract AI Overview content from SerpAPI response"""
        try:
            # Check for knowledge graph
            if "knowledge_graph" in data:
                kg = data["knowledge_graph"]
                content = kg.get("description", "")
                
                # Extract source link if available
                links = []
                if "source" in kg and "link" in kg["source"]:
                    links.append(kg["source"]["link"])
                
                if content:
                    return {"content": content, "links": links}
            
            # Check for answer box (featured snippet)
            if "answer_box" in data:
                answer = data["answer_box"]
                
                # Different types of answer boxes
                if "answer" in answer:
                    content = answer["answer"]
                elif "snippet" in answer:
                    content = answer["snippet"]
                elif "snippet_highlighted_words" in answer:
                    content = " ".join(answer["snippet_highlighted_words"])
                else:
                    content = ""
                
                # Extract link if available
                links = []
                if "link" in answer:
                    links.append(answer["link"])
                
                if content:
                    return {"content": content, "links": links}
            
            # Check for featured snippet
            if "featured_snippet" in data:
                snippet = data["featured_snippet"]
                content = snippet.get("snippet", "")
                
                # Extract link if available
                links = []
                if "link" in snippet:
                    links.append(snippet["link"])
                
                if content:
                    return {"content": content, "links": links}
            
            # Check for related questions
            if "related_questions" in data and data["related_questions"]:
                first_question = data["related_questions"][0]
                content = first_question.get("snippet", "")
                
                # Extract link if available
                links = []
                if "link" in first_question:
                    links.append(first_question["link"])
                
                if content:
                    return {"content": content, "links": links}
            
            # Check for organic results (sometimes AI overview appears here)
            if "organic_results" in data and data["organic_results"]:
                first_result = data["organic_results"][0]
                
                # Check if this might be an AI overview
                if "snippet" in first_result and ("AI" in first_result.get("title", "") or "Gemini" in first_result.get("title", "")):
                    content = first_result["snippet"]
                    
                    # Extract link
                    links = []
                    if "link" in first_result:
                        links.append(first_result["link"])
                    
                    return {"content": content, "links": links}
            
            # No AI Overview found
            return None
            
        except Exception as e:
            logger.error(f"Error extracting AI overview: {e}")
            return None
    
    def process_queries(self, queries):
        """Process a list of queries to extract AI Overviews"""
        for query in queries:
            if not self.check_quota():
                break
                
            self.search_and_extract_ai_overview(query)
            
            # Add a delay between requests to avoid rate limiting
            time.sleep(1 + random.random())  # 1-2 seconds
    
    def save_results(self, filename="google_ai_overviews.json"):
        """Save search results to a JSON file"""
        # Add final metadata
        self.results["metadata"]["queries_used"] = self.query_count
        self.results["metadata"]["queries_limit"] = self.max_queries
        self.results["metadata"]["total_overviews"] = len(self.results["ai_overviews"])
        
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
            "total_overviews": len(self.results["ai_overviews"]),
            "queries_with_overviews": [item["query"] for item in self.results["ai_overviews"]]
        }
        
        return summary

    def test_connection(self):
        """Test the connection to SerpAPI"""
        logger.info("Testing connection to SerpAPI...")
        
        try:
            # Simple test query
            params = {
                "api_key": self.api_key,
                "engine": "google",
                "q": "test",
                "google_domain": "google.com",
                "gl": "us",
                "hl": "en"
            }
            
            response = requests.get("https://serpapi.com/search", params=params)
            
            if response.status_code == 200:
                logger.info("Connection to SerpAPI successful!")
                return True
            else:
                logger.error(f"Connection to SerpAPI failed with status code: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"Raw response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


def main():
    try:
        # Initialize the scraper with a limit of 20 queries
        scraper = GoogleAIOverviewScraper(max_queries=20)
        
        # Test the connection first
        if not scraper.test_connection():
            logger.error("Connection test failed. Please check your API key.")
            return
        
        # Get user queries
        print("Enter your queries (one per line). Type 'done' when finished:")
        queries = []
        while True:
            query = input("> ")
            if query.lower() == 'done':
                break
            queries.append(query)
        
        if not queries:
            print("No queries provided. Using default test query.")
            queries = ["What is machine learning?"]
        
        # Process the queries
        scraper.process_queries(queries)
        
        # Save the results
        results_file = scraper.save_results("google_ai_overviews.json")
        
        # Generate and display summary
        summary = scraper.get_results_summary()
        logger.info("Search Summary:")
        logger.info(f"Total queries used: {summary['total_queries']}/{summary['query_limit']}")
        logger.info(f"Quota limited: {summary['quota_limited']}")
        logger.info(f"Total AI Overviews found: {summary['total_overviews']}")
        logger.info(f"Queries with AI Overviews: {', '.join(summary['queries_with_overviews'])}")
        
        # Save summary
        with open("google_ai_overviews_summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info("Search completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()