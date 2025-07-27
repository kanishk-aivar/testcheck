# Google Search API Web Scraper for Kitsch Website

This project implements a comprehensive web scraper that leverages Google Search APIs to systematically extract and organize data from the Kitsch website (mykitsch.com). Rather than directly crawling the website, which could violate terms of service or trigger rate limits, we use Google's search capabilities to discover pages, products, collections, and categories.

## Features

- **Comprehensive Data Extraction**: Extracts product information, pricing, images, variants, and metadata
- **Collection Discovery**: Finds and organizes product collections
- **Page Structure Analysis**: Extracts navigation, links, and page content
- **Metadata Extraction**: Captures Open Graph, Twitter Cards, and SEO metadata
- **Rate Limiting**: Built-in delays to respect API limits
- **Duplicate Prevention**: Tracks visited URLs to avoid reprocessing
- **Structured Output**: Saves data in organized JSON format with summaries

## Two API Approaches

### 1. SearchApi.io (Recommended)
- **Endpoint**: `https://www.searchapi.io/api/v1/search`
- **Advantages**: Higher rate limits, more reliable, better documentation
- **Queries**: Up to 100 results per request
- **Cost**: Free tier available

### 2. Google Custom Search API
- **Endpoint**: `https://www.googleapis.com/customsearch/v1`
- **Advantages**: Official Google API, familiar interface
- **Queries**: Up to 10 results per request
- **Cost**: 100 free queries/day, then $5 per 1000 queries

## Setup Instructions

### Prerequisites
- Python 3.7+
- pip package manager

### 1. Clone and Setup Environment
```bash
# Navigate to project directory
cd /path/to/your/project

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 2. Install Dependencies
```bash
# Install required packages
pip install requests beautifulsoup4 python-dotenv
```

### 3. Configure API Keys

#### For SearchApi.io (Recommended):
1. Sign up at [SearchApi.io](https://www.searchapi.io/)
2. Get your API key from the dashboard
3. Update `.env` file:
```bash
echo "SEARCHAPI_KEY=your_searchapi_key_here" > .env
```

#### For Google Custom Search API:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Custom Search API
4. Create credentials (API Key)
5. Create a Custom Search Engine at [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
6. Update `.env` file:
```bash
echo "GOOGLE_SEARCH_API_KEY=your_google_api_key_here" >> .env
echo "GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here" >> .env
```

## Usage Commands

### SearchApi.io Approach (Recommended)
```bash
# Activate virtual environment
source venv/bin/activate

# Run the SearchApi scraper
python searchapi_scraper.py
```

### Google Custom Search API Approach
```bash
# Activate virtual environment
source venv/bin/activate

# Run the Google Custom Search scraper
python google_search_scraper.py
```

### Alternative: Simple Direct Scraper
```bash
# Activate virtual environment
source venv/bin/activate

# Run the simple direct scraper (no API required)
python simple_scraper.py
```

## Output Files

After running the scraper, you'll get:

1. **`kitsch_complete_data.json`** - Complete extracted data
2. **`extraction_summary.json`** - Summary statistics
3. **Console output** - Real-time progress and results

## Data Structure

The scraper extracts the following information:

### Products
- Name, price, sale price
- Description and features
- Images with alt text and titles
- Product variants and options
- Reviews and ratings

### Collections
- Collection title and description
- Products within the collection
- Collection metadata

### Pages
- Page title and description
- Navigation menu items
- Main content (truncated)
- All links on the page
- SEO metadata

### Metadata
- Open Graph tags
- Twitter Card tags
- Standard meta tags
- Page structure information

## Search Queries Used

The scraper uses targeted search queries to discover content:

1. **Site Overview**: `site:mykitsch.com`
2. **Product Categories**: 
   - `site:mykitsch.com products`
   - `site:mykitsch.com collections`
   - `site:mykitsch.com hair care`
   - `site:mykitsch.com accessories`
3. **Specific Product Types**:
   - `site:mykitsch.com best sellers`
   - `site:mykitsch.com hair accessories`
   - `site:mykitsch.com beauty`
   - `site:mykitsch.com shop`

## Rate Limiting and Best Practices

- **SearchApi.io**: 2-second delay between searches, 1-second delay between page requests
- **Google Custom Search**: 1-second delay between searches, 2-second delay between page requests
- **Respectful Crawling**: User-Agent headers and reasonable timeouts
- **Error Handling**: Graceful handling of network errors and missing content

## Example Results

Based on previous runs, the scraper typically discovers:
- **150+ unique URLs**
- **40+ products** with complete information
- **15+ collections** with product listings
- **Comprehensive metadata** for SEO analysis

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   ```bash
   # Check your .env file
   cat .env
   
   # Ensure the key is correctly set
   echo "SEARCHAPI_KEY=your_actual_key" > .env
   ```

2. **Rate Limit Exceeded**
   - Wait a few minutes before retrying
   - Consider upgrading your API plan
   - Reduce the number of search queries

3. **Network Errors**
   - Check your internet connection
   - Verify the target website is accessible
   - Try running with fewer concurrent requests

### Debug Mode
```bash
# Run with verbose logging
python searchapi_scraper.py 2>&1 | tee scraper.log
```

## API Quota Management

### SearchApi.io
- **Free Tier**: 100 searches/month
- **Paid Plans**: Starting at $29/month for 10,000 searches
- **Efficient Usage**: Script uses ~20 queries for comprehensive coverage

### Google Custom Search API
- **Free Tier**: 100 queries/day
- **Paid**: $5 per 1,000 queries
- **Efficient Usage**: Script uses ~20 queries for comprehensive coverage

## Contributing

To extend the scraper:

1. **Add New Selectors**: Update the CSS selectors in extraction methods
2. **New Content Types**: Add new extraction methods for different page types
3. **Additional APIs**: Implement support for other search APIs
4. **Enhanced Parsing**: Add more sophisticated content parsing logic

## License

This project is for educational and research purposes. Please respect website terms of service and robots.txt files when using this scraper.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify your API keys are correct
3. Ensure all dependencies are installed
4. Check the console output for specific error messages# testcheck
