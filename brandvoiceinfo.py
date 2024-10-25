from flask import Blueprint, request, jsonify
from config import Config
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import aiohttp
import asyncio
import brotli
import chardet
from urllib.parse import urljoin, urlparse
import logging
from typing import Set, Optional, Dict
import re
from aiohttp import ClientTimeout
from collections import deque
import nest_asyncio
import random
from openai import AsyncOpenAI, OpenAI
from models import (
    get_brand_profile,
    create_brand_voice,
    update_brand_voice,
    create_brand_profile,
    get_brand_voice
)
import jwt
from flask_jwt_extended import get_jwt_identity, jwt_required
# Initialize blueprint
brand_voice_bp = Blueprint('brand_voice_info', __name__)

# Initialize OpenAI clients
from openai import AsyncOpenAI, OpenAI
deepinfra_client = AsyncOpenAI(
    api_key=Config.DEEPINFRA_API_KEY,
    base_url="https://api.deepinfra.com/v1/openai",
)

client_open_router = OpenAI(
    api_key=Config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

perplexity_token = Config.PERPLEXITY_TOKEN
google_api_key = Config.GOOGLE_API_KEY
google_cse_id = Config.GOOGLE_CSE_ID

def search_webs(trend, nums = 10, delay=None):

    api_key = google_api_key
    cse_id = google_cse_id

    if not api_key or not cse_id:    # Assuming you have these variables set
        raise ValueError("Please set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables")

    service = build("customsearch", "v1", developerKey=api_key)

    result = None

    # Set the date range for the last delay
    if delay is not None:
      date = datetime.now() - timedelta(days=delay)
      date_restrict = f"d{delay}"

      # print(f"Date Restrict : {date_restrict}")

      result = service.cse().list(q=trend, cx=cse_id, gl='countryIN', num=nums, dateRestrict=date_restrict).execute()

    else:
      result = service.cse().list(q=trend, cx=cse_id, gl='countryIN', num=nums).execute()

    if 'items' in result:
        return result['items'], 0.005
    else:
        return -1, 0
    
async def scrape_website(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/92.0.4515.131 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://www.google.com/',
            'DNT': '1',  # Do Not Track request header
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, timeout=60) as response:
                    response.raise_for_status()  # Raise exception for bad status codes

                    # Check if the content is Brotli-encoded
                    if response.headers.get('Content-Encoding') == 'br':
                        raw_data = await response.read()
                        try:
                            # Manually decompress Brotli-encoded content
                            html = brotli.decompress(raw_data).decode('utf-8', errors='ignore')
                        except brotli.error:
                            # print("Brotli decompression failed.")
                            return "No information found."
                    else:
                        # For other encodings like gzip or deflate
                        html = await response.text()

                    # Parse the HTML content
                    soup = BeautifulSoup(html, 'html.parser')

                    # Example: Extract all paragraph texts
                    paragraphs = soup.find_all('p')
                    txt = "".join([p.get_text() for p in paragraphs])

                    return txt

            except asyncio.TimeoutError:
                print("Timed out :(")
                return "No information found."
            except aiohttp.ClientResponseError as e:
                # print(f"HTTP error occurred: {e.status} {e.message}")
                return "No information found."
            except Exception as e:
                # print(f"An unexpected error occurred: {e}")
                return "No information found."

    except aiohttp.ClientError as e:
        # print(f"Client error occurred: {e}")
        return "No information found."
    
class AsyncMultilingualScraper:
    def __init__(
        self,
        user_agents: Optional[list] = None,
        max_concurrent_requests: int = 3,
        request_delay: float = 1.0,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ):
        """
        Initialize the async scraper with customizable settings.
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.last_request_time = time.time()
        self.seen_urls: Set[str] = set()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # List of User-Agent strings to rotate
        self.user_agents = user_agents or [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0'
        ]

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    async def enforce_delay(self):
        """
        Enforce delay between requests while considering concurrent execution.
        """
        async with asyncio.Lock():
            elapsed = time.time() - self.last_request_time
            if elapsed < self.request_delay:
                await asyncio.sleep(self.request_delay - elapsed)
            self.last_request_time = time.time()

    def get_random_user_agent(self) -> str:
        """
        Select a random User-Agent string from the list.
        """
        return random.choice(self.user_agents)

    def is_valid_url(self, url: str, base_url: str) -> bool:
        """
        Check if URL is valid and belongs to the same domain or its subdomains.
        """
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower().lstrip('www.')
        url_domain = parsed_url.netloc.lower().lstrip('www.')
        return (
            (url_domain == base_domain or url_domain.endswith('.' + base_domain)) and
            parsed_url.scheme in ('http', 'https')
        )

    def clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing extra whitespace and unwanted characters.
        Join different elements' contents with a newline character.
        """
        text = re.sub(r'\s+', ' ', text.strip())
        return text

    async def get_page_content(self, url: str, session: aiohttp.ClientSession, retry_count: int = 0) -> Optional[Dict[str, str]]:
        """
        Fetch and parse content from a single webpage asynchronously.
        Implements retry with exponential backoff on 429 responses.
        """
        try:
            async with self.semaphore:
                await self.enforce_delay()
                headers = self.headers_with_random_agent()
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status == 429:
                        if retry_count < self.max_retries:
                            retry_after = response.headers.get('Retry-After')
                            wait_time = float(retry_after) if retry_after else self.backoff_factor ** retry_count
                            self.logger.warning(f"Received 429 for {url}. Retrying after {wait_time} seconds.")
                            await asyncio.sleep(wait_time)
                            return await self.get_page_content(url, session, retry_count + 1)
                        else:
                            self.logger.error(f"Max retries reached for {url}. Skipping.")
                            return None
                    elif response.status != 200:
                        self.logger.warning(f"Failed to fetch {url}: Status {response.status}")
                        return None

                    content = await response.read()
                    encoding = response.charset or chardet.detect(content)['encoding'] or 'utf-8'
                    text = content.decode(encoding, errors='replace')

                    # Parse with BeautifulSoup using lxml parser
                    soup = BeautifulSoup(text, 'lxml')

                    # Remove unwanted elements
                    for element in soup(['script', 'style', 'meta', 'noscript', 'header', 'footer', 'svg', 'iframe']):
                        element.extract()

                    # Extract title and main content
                    title = soup.title.string.strip() if soup.title and soup.title.string else ''
                    main_content = soup.find('article') or soup.find('main') or soup.body

                    if not main_content:
                        self.logger.warning(f"No main content found for {url}")
                        return None

                    # Extract text from different elements and join with newline
                    texts = [
                        self.clean_text(element.get_text(separator=' ', strip=True))
                        for element in main_content.find_all(
                            ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']
                        )
                        if element.get_text(strip=True)
                    ]

                    full_text = '\n'.join(texts)

                    return {
                        'title': title,
                        'text': full_text,
                        'url': url
                    }

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error(f"Error scraping {url}: {e}")
        except asyncio.CancelledError:
            self.logger.warning(f"Task was cancelled for {url}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error scraping {url}: {e}")
        return None

    def headers_with_random_agent(self) -> Dict[str, str]:
        """
        Generate headers with a random User-Agent.
        """
        return {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
            'Accept-Language': '*'
        }

    async def find_links(self, url: str, session: aiohttp.ClientSession) -> Set[str]:
        """
        Find all valid links on a page asynchronously.
        """
        try:
            async with self.semaphore:
                await self.enforce_delay()
                headers = self.headers_with_random_agent()
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status == 429:
                        retry_after = response.headers.get('Retry-After')
                        wait_time = float(retry_after) if retry_after else self.backoff_factor
                        self.logger.warning(f"Received 429 while finding links on {url}. Retrying after {wait_time} seconds.")
                        await asyncio.sleep(wait_time)
                        return await self.find_links(url, session)
                    elif response.status != 200:
                        self.logger.warning(f"Failed to fetch {url} for link extraction: Status {response.status}")
                        return set()

                    content = await response.text()
                    soup = BeautifulSoup(content, 'lxml')

                    links = {
                        urljoin(url, link['href'])
                        for link in soup.find_all('a', href=True)
                        if not link['href'].startswith('mailto:') and not link['href'].startswith('javascript:')
                    }

                    valid_links = {
                        link for link in links if self.is_valid_url(link, url)
                    }

                    return valid_links
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error(f"Error finding links on {url}: {e}")
        except asyncio.CancelledError:
            self.logger.warning(f"Task was cancelled while finding links on {url}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error finding links on {url}: {e}")
        return set()

    async def scrape_website(self, start_url: str, max_pages: Optional[int] = 50):
        """
        Scrape text content from a website starting from a given URL asynchronously.

        Parameters:
            start_url (str): The URL to start scraping from.
            max_pages (int, optional): The maximum number of pages to scrape. If None, no limit is enforced.

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing scraped data.
        """
        self.seen_urls = set()
        results = []
        urls_to_visit = deque([start_url])

        async with aiohttp.ClientSession() as session:
            tasks = set()
            while urls_to_visit or tasks:
                # Queue up new tasks up to the concurrency limit
                while urls_to_visit and len(tasks) < self.max_concurrent_requests:
                    if max_pages is not None and len(self.seen_urls) >= max_pages:
                        break  # Stop adding new tasks if max_pages is reached
                    current_url = urls_to_visit.popleft()
                    if current_url in self.seen_urls:
                        continue
                    self.seen_urls.add(current_url)
                    self.logger.info(f"Queueing: {current_url}")
                    task = asyncio.create_task(self.process_url(current_url, session, urls_to_visit, max_pages))
                    tasks.add(task)

                if not tasks:
                    if urls_to_visit:
                        continue  # Continue if there are URLs left to process
                    else:
                        break  # No tasks and no URLs left

                # Wait for the first task to complete
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    tasks.remove(task)
                    try:
                        result = task.result()
                        if result:
                            results.append(result)
                            self.logger.info(f"Scraped: {result['url']}")
                    except asyncio.CancelledError:
                        self.logger.warning("A task was cancelled.")
                    except Exception as e:
                        self.logger.error(f"Error processing task: {e}")

        return results

    async def process_url(self, url: str, session: aiohttp.ClientSession, urls_to_visit: deque, max_pages: Optional[int]):
        """
        Process a URL: scrape content and find new links.

        Parameters:
            url (str): The URL to process.
            session (aiohttp.ClientSession): The HTTP session to use.
            urls_to_visit (deque): The deque of URLs to visit.
            max_pages (int, optional): The maximum number of pages to scrape.

        Returns:
            Optional[Dict[str, str]]: The scraped content, if any.
        """
        content = await self.get_page_content(url, session)
        if content:
            # Find new URLs to visit
            new_links = await self.find_links(url, session)
            for link in new_links:
                if (link not in self.seen_urls and
                    link not in urls_to_visit and
                    (max_pages is None or len(self.seen_urls) + len(urls_to_visit) < max_pages)):
                    urls_to_visit.append(link)
        return content

# Example usage function
async def scrape_example(url):
    # Create scraper instance with adjusted settings
    scraper = AsyncMultilingualScraper(
        max_concurrent_requests=3,  # Reduced concurrency
        request_delay=2.0,          # Increased delay between requests
        max_retries=5,              # Increased max retries
        backoff_factor=2.0          # Increased backoff factor for exponential backoff
    )

    # Replace with your target website
    target_url = url  # Replace with your desired URL

    # Scrape the website
    results = await scraper.scrape_website(target_url, max_pages=1)  # Adjust max_pages as needed

    # Print results
    # for result in results:
    #     print(f"Title: {result['title']}")
    #     print(f"URL: {result['url']}")
    #     preview = result['text'][:200] + '...' if len(result['text']) > 200 else result['text']
    #     print(f"Text preview:\n{preview}\n")
    #     print("="*50)

    # Optionally, return results
    try:
      info = results[0]
      text = f"Website Title: {info['title']}\n\nWebsite Info:\n{info['text']}\n\n\n"
      return text
    except:
      return "No information found"
  
async def url_summ(text):
  chat_history = [{"role": "system","content":
'''**Role:**
You are a chatbot responsible for summarizing articles about a brand that have been scraped from a website.

**Task:**
You will receive a query that was searched on Google, along with the content of an article scraped from a website related to that query. Your task is to summarize the article, ensuring that the summary includes all the important points while painting a complete picture of the information. The summary should be concise, brief, and directly related to the query.

**Instructions:**
1. **Summarize relevant content only**: Focus on summarizing only the information that is directly or indirectly related to the search query. Ignore any unrelated content such as website advertisements, website info, or other irrelevant articles.

2. **Complete and concise**: Make sure your summary includes all relevant points and presents the full picture, but in a shortened and simple format. Avoid leaving out key information related to the query.

3. **Avoid unnecessary details**: Do not include unrelated information in your response. Stick only to content that matches the query’s topic, title, and description.

4. **No additional information**: Do not search for information, rely on your memory, or simulate a response. If no relevant information is provided, respond with:
   - "No information was provided" if no content is available.
   - "The information provided is not related to the search query" if the content does not match the query.

**Purpose:**
Your summaries will provide key insights from articles related to brands, focusing on relevant information from the scraped website content. These summaries are used to better understand a brand's online presence and messaging while avoiding irrelevant details.'''},
                  {
              "role": "user",
              "content": text,
          }]

  response_content = ""
  try:
    chat_completion = await deepinfra_client.chat.completions.create(
                              model="meta-llama/Meta-Llama-3.1-8B-Instruct",
                              messages=chat_history,
                              max_tokens=2048,
                              temperature=0.1)

    cost = (chat_completion.usage.prompt_tokens * 0.055 + chat_completion.usage.completion_tokens * 0.055) / (10**6)

    return chat_completion.choices[0].message.content, cost

  except Exception as e:
    print(e)
    return ("Error: " + str(e)), 0

async def url_summ2(text):
  chat_history = [{"role": "system","content":
'''Summarise and structure the content provided to you. The content provided is from a website, relating to a brand or an individual creator / individual ecommerce seller.'''},
                  {
              "role": "user",
              "content": text,
          }]

  response_content = ""
  try:
    chat_completion = await deepinfra_client.chat.completions.create(
                              model="meta-llama/Meta-Llama-3.1-8B-Instruct",
                              messages=chat_history,
                              max_tokens=2048,
                              temperature=0.1)

    cost = (chat_completion.usage.prompt_tokens * 0.055 + chat_completion.usage.completion_tokens * 0.055) / (10**6)

    return chat_completion.choices[0].message.content, cost

  except Exception as e:
    print(e)
    return ("Error: " + str(e)), 0

async def query_summ(text):
  chat_history = [{"role": "system","content":
'''**Role:**
You are a chatbot responsible for effectively summarizing information gathered from various online sources.

**Task:**
You will receive information about a particular search query, collected from the top search results on Google. Your role is to create an exhaustive summary of this information, ensuring it is non-repetitive, concise, and includes all relevant details from the various sources provided. Your summary should cover the entire content while avoiding redundancy and unnecessary details.

**Format:**
You will receive input in the following format:
```
Search Query: <search query>

a. Title: <title>, Website: <website>
Content Summary: <summary>

b. Title: <title>, Website: <website>
Content Summary: <summary>
```

**Instructions:**
1. **Summarize without repetition**: Each source may contain overlapping information. Your task is to ensure that the final summary includes all relevant content from different sources without repeating the same points.

2. **Cover all relevant points**: The summary must cover all the key details provided in the content summaries, including information about the company’s products, services, mission, market, target audience, competitors, etc.

3. **Contextual understanding of sources**: Use the website name to understand the context of the content. For example:
   - **Reddit** or public forums likely contain user discussions or opinions.
   - **Official government or company websites** may contain formal announcements or key information.
   - **News outlets** might provide articles, insights, or reports.
   - **Social media handles** could contain public reactions, company updates, or informal discussions.

   This understanding can help you tailor the summary to capture the most important points depending on the type of source.

4. **Simple and concise language**: Make the summary concise, written in clear, simple language that is easy for the reader to follow. Avoid making the summary too long or overly detailed, while still covering all necessary points.

**Purpose:**
Your summary will be used to collect important information about a company, its products, services, and related content. This information is critical for equipping other chatbots that generate content for the company (e.g., social media posts, advertisements) with the necessary context to personalize their outputs and align them with the company’s style and messaging. The quality and accuracy of your summaries are crucial to ensuring these chatbots can create highly relevant, personalized content.'''},
                  {
              "role": "user",
              "content": text,
          }]

  response_content = ""
  try:
    chat_completion = await deepinfra_client.chat.completions.create(
                              model="meta-llama/Meta-Llama-3.1-70B-Instruct",
                              messages=chat_history,
                              max_tokens=2048,
                              temperature=0.1)

    cost = (chat_completion.usage.prompt_tokens * 0.35 + chat_completion.usage.completion_tokens * 0.4) / (10**6)

    return chat_completion.choices[0].message.content, cost

  except Exception as e:
    print(e)
    return ("Error: " + str(e)), 0

def final_summ(text, prompt, model):

  chat_history = [{"role": "system","content": prompt},
                  {
              "role": "user",
              "content": text,
          }]

  try:
        completion = client_open_router.chat.completions.create(
        model=model[0],
        messages= chat_history,
        temperature=0.3,
        max_tokens=58_764)
        cost = (completion.usage.prompt_tokens * model[1] + completion.usage.completion_tokens * model[2]) / (10**6)
        return completion.choices[0].message.content, cost
  except Exception as e:
    print(e)
    return ("Error: " + str(e.response.status_code)), 0
async def fetch_search_info_pplx(text):
  url = "https://api.perplexity.ai/chat/completions"

  payload = {
      "model": "llama-3.1-sonar-huge-128k-online",
      "messages": [
          {
              "role": "system",
              "content": \
  '''Be precise.
  You have the role of searching about information (about a brand) and return the best matching information.
  Respond in a detailed manner, but only return relevant information.
  You will get some information about a brand as context, to understand which brand we are exactly talking about, the brand will not be very popular and this context would be helpful for your search.
  Be as detailed, precise and accurate as possible. Do not compromise on accuracy for over detailing or vice versa.

  **Important:**
  Do not hallucinate or create information by yourself.
  Do not confuse some other brand (with a similar name or work) with the current brand.
  If you do not find information about current brand or find irrelevant information then mention that you were not able to find the required information.
  Do not respond with unrelated information or false information.
  '''
          },
          {
              "role": "user",
              "content": text
          }
      ],
      "max_tokens": 4096,
      "temperature": 0.15,
      "top_p": 0.9,
      "return_citations": False,
      "search_domain_filter": [],
      "return_images": False,
      "return_related_questions": False,
      "search_recency_filter": "week",
      "top_k": 0,
      "stream": False,
      "presence_penalty": 0,
      "frequency_penalty": 1
  }
  headers = {
      "Authorization": f"Bearer {perplexity_token}",
      "Content-Type": "application/json"
  }

  try:
    async with aiohttp.ClientSession() as session:
      async with session.post(url, json=payload, headers=headers) as response:
        response_json = await response.json()
        # print("1")
        cost = (response_json['usage']['prompt_tokens'] * 5 + response_json['usage']['completion_tokens'] * 5)/(10**6) + 5/1000
        return response_json['choices'][0]['message']['content'], cost
  except Exception as e:
    print(f"Error: {e}")
    # print(response)
    # print(response.text())
    return "-1", 0

def get_search_query_context(text):
  chat_history = [{"role": "system","content":
'''**System Prompt:**
You will be provided with the information about a company. You have to return me a small piece of text explaining the basics of the company. What it does, industry, location, .. etc.
This will be used as a basic context while researching about the company on the internet. Since the company would be of a smaller size, limited information is available about it on the internet.
Thus the research engine may confuse the searches and the obtained information between other companies. To perform search part effectively. We would need a very basic, short, precise and concise context about the company.
This must help us to uniquely identify the company on the internet. Keep your response short and concise, keep it just enough to basically describe the company. No need of getting into the details.
'''},
                  {
              "role": "user",
              "content": text,
          }]

  try:
        completion = client_open_router.chat.completions.create(
        model= "openai/o1-mini-2024-09-12",
        messages= chat_history,
        temperature=0.4,
        max_tokens=58_764)
        cost = (completion.usage.prompt_tokens * 3 + completion.usage.completion_tokens * 12) / (10**6)
        return completion.choices[0].message.content, cost
  except Exception as e:
    print("Error: " + str(e))
    return "-1", 0

def extract_search_queries(text):
  queries = []
  while "<search query>" in text:
    start = text.find("</search query>")
    end = text.find("</search query>")
    query = text[start+14:end]
    text = text[end+15:]
    queries.append(query)
  return queries

async def brand_info_scrape(company, industries, manual_urls, attachments, manual_input_text, design_text, location, content_types, brand_personalities, target_audience, brand_tone, brand_type):
  queries = [f'{company} company overview',
  f'{company} about us',
  f'{company} information',
  f'{company} history',
  f'{company} founder story',
  f'{company} mission statement',
  f'{company} vision statement',
  f'{company} core values',
  f'{company} product differentiation',
  f'{company} recent product launches',
  f'{company} product positioning',
  f'{company} pricing strategy',
  f'{company} market positioning',
  f'{company} competitors',
  f'{company} competitive analysis',
  f'{company} market share trends',
  f'{company} market presence regions',
  f'industry trends affecting {company}',
  f'{company} brand positioning',
  f'{company} overall branding strategy',
  f'{company} overall marketing strategy',
  f'{company} successful marketing campaigns',
  f'top innovative marketing tactics used by {company}',
  f'{company} social media platforms',
  f'{company} social media strategies',
  f'{company} popular social campaigns',
  f'{company} popular social media posts',
  f'{company} social media posting style',
  f'{company} target audience',
  f'{company} public perception',
  f'{company} and customer emotional connections',
  f'{company} user psyche',
  f'{company} customer reviews',
  f'{company} customer testimonials',
  f'{company} corporate social responsibility',
  f'{company} sustainability initiatives',
  f'{company} environmental impact',
  f'{company} awards and recognitions',
  f'{company} industry accolades',
  f'{company} press releases',
  f'{company} media coverage',
  f'{company} technological innovations',
  f'{company} research and development',
  f'{company} challenges faced',
  f'{company} legal issues or controversies',
  f'{company} brand voice and tone',
  f'{company} key messaging',
  f'{company} tagline and slogans',
  f'{company} brand colors and typography',
  f'{company} logo usage guidelines',
  f'{company} customer journey map',
  f'{company} touchpoints with customers',
  f'{company} website SEO strategy',
  f'{company} digital marketing channels',
  f'{company} influencer partnerships',
  f'{company} affiliate marketing programs',
  f'{company} customer loyalty programs',
  f'{company} engagement metrics',
  f'{company} product offerings',
  f'{company} service offerings',
  f'{company} subsidiaries',
  f'{company} brand differentiation',
  f'{company} latest announcements',]

  costs = 0
  tasks = []
  results = ''
  prompt = ''
  model = []
  if manual_urls is not None or len(manual_urls) != 0:
    tasks = [scrape_example(url) for url in manual_urls]
    # Run all tasks concurrently and gather the results
  website_manual_uns = await asyncio.gather(*tasks)

  entity = 'Brand'
  if brand_type == 2:
    entity = 'Brand (Startup/SMB business)'
  elif brand_type == 3:
    entity = "Individual Creator's Entity"
  elif brand_type == 4:
    entity = "Ecommerce Seller's Entity"

  website_manual_async = []
  website_manual = []
  for id, website_info in enumerate(website_manual_uns):
    info = f"Website url: {manual_urls[id]}\n\nWebsite Content:\n{website_info}"
    website_manual_async.append(url_summ2(info))
  website_summ = await asyncio.gather(*website_manual_async)

  for i in website_summ:
    website_manual.append(i[0])
    costs += i[1]

  attachments_text = ''
  for i, attachment in enumerate(attachments):
    attachments_text += f'### Attachment {i+1}:\n---\n{attachment}\n\n\n\n'

  total_text = f'#### **Name of the {entity}: {company}**\n### Location: {location}\n### **Industries:** '
  for industry in industries:
    total_text += f'{industry},'
  total_text += '\b\n'

  total_text += f'### **{entity} Content type:**'
  for content_type in content_types:
    total_text += f'{content_type},'
  total_text += '\b\n'

  total_text += f'### **{entity} Target Audiences:**'
  for audience in target_audience:
    total_text += f'{audience},'
  total_text += '\b\n'

  total_text += f'### **{entity} Tone (Options: Neutral; Slightly, Occasionally, Mostly, Completely Casual or Neutal):** {brand_tone}\n'
  total_text += f'### **{entity} Personality:**'
  for personality in brand_personalities:
    total_text += f'{personality},'
  total_text += '\b\n\n\n\n'

  total_text += f'#### {entity} style information (manually added):\n\n'

  if manual_input_text is not None or len(manual_input_text) != 0:
    total_text += f'### {entity} information (plain text):\n{manual_input_text}\n\n\n\n'

  if design_text is not None or len(design_text) != 0:
    total_text += f'### {entity} Design Style Information (Plain Text):\n\n{design_text}\n\n\n\n'

  if attachments_text is not None or len(attachments_text) != 0:
    total_text += f'### User added attachments:\n\n{attachments_text}\n\n\n\n'

  if manual_urls is not None or len(manual_urls) != 0:
    total_text += '### Website Scrapped Data:\n\n'
    for id, i in enumerate(website_manual):
      total_text += f'# Website URL: {manual_urls[id]}\n'
      total_text += f"{i}\n\n"
    total_text += '\n\n'
  # print(total_text)

  # Seperating for Individual and non-individual
  if brand_type == 1 or brand_type == 2:

    model = ["openai/o1-mini-2024-09-12",3,12]

    prompt = \
'''Your task is to build a highly detailed, structured information text corpus using a provided input text corpus, which contains two parts: critical brand-specific information and search query results.

1. The brand-specific information (such as company name, industries, website content, design styles, types of content to generate, brand personality, target audience, and tone) should be mostly preserved since it is directly relevant to the use case. However, a small description should be given along it describing what could be inferred from the information provided. Also this information, even-though is preserved but it must be structured properly. No information from this part of the corpus shall be removed, since it is highly relevant to the use case.

2. From the search query results, preserve only the information that is essential for creating personalized and effective posts for the brand. Focus on key aspects such as:
   - **Founder story** and the company's **mission and values**
   - **Product and market information**
   - **Consumer perception** and **psyche**
   - **Competitors** and **industry insights**
   - **Design elements** and **styling information** for brand posts
   - **Target audiences and markets**
   - **Marketing and branding strategies**
   - **Historical post performance** or analysis
   - **Geographical and cultural context** related to the company, markets, and customers
   - **Relevant news and announcements** about the company.

Ensure the selected information helps guide designers in making highly personalized and relevant content for the brand, while avoiding irrelevant or redundant details. Structure the data clearly, and explain all key points in detail to support an LLM in generating content for social media posts, blogs, ads, and more. Do not hallucinate or omit relevant details.'''

    results_query_summ = []

    if brand_type == 1:
      URLS = {}
      for i in range(len(queries)):
        searches, cost = search_webs(queries[i],10)
        costs += cost
        for j in searches:
          try:
            URLS[queries[i]].append([j['title'],j['snippet'],j['link'],None])
          except:
            URLS[queries[i]] = [[j['title'],j['snippet'],j['link'],None]]

      scrapes = []
      for i in URLS:
        for j in URLS[i]:
          scrapes.append(scrape_website(j[2]))
      results_scrape = await asyncio.gather(*scrapes)

      c = 0
      url_summs = []

      for i in URLS:
        for j in URLS[i]:
          j[-1] = results_scrape[c]

          url_prompt = f"Search Query: {i}\n\nContent: {j[3]}"
          temp = url_summ(url_prompt)
          url_summs.append(temp)
          c+=1
      results_url_summ = await asyncio.gather(*url_summs)

      query_summs_prompts = {}
      query_summs = []
      c2 = 0

      for i in URLS:
        query_summs_prompts[i] = f"Search Query: {i}\n\n"
        for n,j in enumerate(URLS[i]):
          query_summs_prompts[i] += f'''{chr(97+n)}. Title: {j[0]}, Website: {j[2]}
      Content Summary:\n {results_url_summ[c2][0]} \n\n\n'''
          costs += results_url_summ[c2][1]
          c2+=1
        temp2 = query_summ(query_summs_prompts[i])
        query_summs.append(temp2)
      results_query_summ = await asyncio.gather(*query_summs)

    elif brand_type == 2:
      context, cost = get_search_query_context(total_text)
      costs += cost

      queries = \
["Get me information about its `Company Overview`",
"Get me information about its `Product & Services`",
"Get me information about its `Market & Competitors`",
"Get me information about its `Branding & Marketing`",
"Get me information about its `Social Media`",
"Get me information about its `Customers, demographics and target audience`",
"Get me information about its `Recent updates and news`",]

      queries = [f"Context: {context}\nSearch Query: {query}" for query in queries]
      # queries_raw, cost = get_search_queries(total_text)
      # costs += cost
      # queries = extract_search_queries(queries_raw)

      # print(context, queries)

      results_query_summ_async = []
      for query in queries:
        temp = fetch_search_info_pplx(query)
        results_query_summ_async.append(temp)
      results_query_summ = await asyncio.gather(*results_query_summ_async)

    results = ''
    for id,i in enumerate(results_query_summ):
      results += f'Search Query: {queries[id]}\n\n\nInformation:\n\n'
      results += i[0]
      costs += i[1]
      results += '\n\n\n\n'

      results = total_text + "##### Company Data Obtained from search:\n\n" + results

  else:
    results = total_text

    model = ['openai/o1-mini-2024-09-12',3,12]

    prompt = \
'''Here’s an expanded version of the prompt with additional instructions to ensure thorough analysis and expansion of the provided information:

---

**Your task is to build a highly detailed, structured database using a provided text corpus, focusing on individual creators or e-commerce sellers.**

The key information (such as name, niche or product offering, website content, design styles, types of content to generate, personality, target audience, and tone) should be preserved and structured properly as it is directly relevant to the use case.

For each piece of information, follow these steps:
1. **Break down** the information into smaller, actionable insights. Analyze each detail, ensuring no point is overlooked.
2. **Infer deeper meaning** from the content provided. For example, if a design style is mentioned, explain how it could influence branding or content creation. If the tone or personality is specified, describe how it affects communication with the target audience.
3. **Expand upon each point** with specific examples or scenarios that could be relevant to the individual creator or e-commerce seller. If a target audience is provided, break it down by demographics or preferences and describe how the content could be tailored to their interests.
4. **Analyze connections** between different pieces of information. For instance, how does the brand personality align with the content types they want to generate? How do design styles complement the target audience's preferences?
5. **Provide detailed explanations** of the inferred insights, making sure to relate everything back to the goal of creating personalized and effective content.

Since this data will guide an LLM to create social media posts, product descriptions, blogs, and marketing campaigns, ensure your response is structured and highly detailed. Do not omit or summarize any relevant information. Expand upon each point thoroughly to offer a complete, comprehensive analysis that will support creative, personalized content generation.'''

  final_results,cost = final_summ(results, prompt, model)
  costs += cost
  final_results = final_results.replace("#### ", "")
  final_results = final_results.replace("### ", "")
  final_results = final_results.replace("## ", "")
  final_results = final_results.replace("####", "")
  final_results = final_results.replace("###", "")
  final_results = final_results.replace("##", "")
  final_results = final_results.replace("**", "")
  return final_results, costs

# # Function to verify next-auth JWT tokens
# def verify_nextauth_jwt(token: str) -> Optional[str]:
#     try:
#         payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
#         user_id = payload.get("sub")
#         return user_id
#     except jwt.ExpiredSignatureError:
#         logging.error("JWT token has expired.")
#     except jwt.InvalidTokenError:
#         logging.error("Invalid JWT token.")
#     return None

# Assuming necessary imports are already present

@brand_voice_bp.route('/create', methods=['POST'])
@jwt_required()
def create_brand():
    data = request.json
    try:
        # Retrieve the user ID from the JWT token
        user_id = get_jwt_identity()

        # Validate required fields (similar to frontend validation)
        required_fields = [
            'company', 'brandVoiceName', 'industries', 'location', 'contentTypes',
            'brandPersonalities', 'targetAudience', 'brandTone',
            'brandType', 'socialMedia', 'otherUrls',
            'manualInputText', 'designText'
        ]
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

        # Additional validations can be added here as needed
        # For example, validate URLs, social media handles, etc.

        # Save the brand profile to MongoDB
        profile_data = {
            'user_id': user_id,
            'company': data['company'],
            'brandVoiceName': data['brandVoiceName'],  # Store brandVoiceName
            'industries': data['industries'],
            'location': data['location'],
            'contentTypes': data['contentTypes'],
            'brandPersonalities': data['brandPersonalities'],
            'targetAudience': data['targetAudience'],
            'brandTone': data['brandTone'],
            'brandType': data['brandType'],
            'socialMedia': data['socialMedia'],
            'otherUrls': data['otherUrls'],
            'manualInputText': data['manualInputText'],
            'designText': data['designText'],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        profile_id = create_brand_profile(user_id, profile_data)

        # Generate Brand Voice using the provided functions
        # Extract necessary fields from the profile_data
        company = data['company']
        brand_voice_name = data['brandVoiceName']  # Extract brandVoiceName
        industries = data['industries']
        location = data['location']
        content_types = data['contentTypes']
        brand_personalities = data['brandPersonalities']
        target_audience = data['targetAudience']
        brand_tone = data['brandTone']
        brand_type = int(data['brandType'])  # Assuming brandType is sent as string in frontend

        # Extract other necessary fields
        manual_urls = data.get('otherUrls', [])
        attachments = []  # Assuming attachments are handled elsewhere
        manual_input_text = data.get('manualInputText', '')
        design_text = data.get('designText', '')

        # Run the brand_info_scrape function asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        summary, cost = loop.run_until_complete(
            brand_info_scrape(
                company=company,
                industries=industries,
                manual_urls=manual_urls,
                attachments=attachments,
                manual_input_text=manual_input_text,
                design_text=design_text,
                location=location,
                content_types=content_types,
                brand_personalities=brand_personalities,
                target_audience=target_audience,
                brand_tone=brand_tone,
                brand_type=brand_type
            )
        )
        loop.close()

        # Prepare the brand voice data using brandVoiceName from user
        voice_data = {
            'voiceName': data['brandVoiceName'],  # Use brandVoiceName from user
            'audience': data['targetAudience'],
            'summary': summary,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        # Save the brand voice to MongoDB
        create_brand_voice(profile_id, voice_data)

        return jsonify({'msg': 'Brand profile created and brand voice generated successfully.', 'summary': summary, 'cost': cost}), 201

    except Exception as e:
        logging.exception("Error in /brand/create POST route")
        return jsonify({'error': str(e)}), 500


# Apply nest_asyncio to allow nested event loops (necessary for certain environments)
nest_asyncio.apply()


@brand_voice_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """
    Retrieve the authenticated user's brand profile and associated brand voice.
    """
    try:
        # Retrieve the user ID from the JWT token
        user_id = get_jwt_identity()
        
        # Fetch the brand profile from MongoDB
        brand_profile = get_brand_profile(user_id)
        
        if not brand_profile:
            return jsonify({'error': 'Brand profile not found.'}), 404
        
        # Fetch the brand voice associated with the brand profile
        brand_voice = get_brand_voice(brand_profile['_id'])
        
        # If brand voice does not exist, notify the frontend
        if not brand_voice:
            return jsonify({'error': 'Brand voice not found for this profile.'}), 404
        
        # Prepare the response data
        response_data = {
            "company": brand_profile.get("company", ""),
            "industries": brand_profile.get("industries", []),
            "location": brand_profile.get("location", ""),
            "contentTypes": brand_profile.get("contentTypes", []),
            "brandPersonalities": brand_profile.get("brandPersonalities", []),
            "targetAudience": brand_profile.get("targetAudience", []),
            "brandTone": brand_profile.get("brandTone", ""),
            "brandType": brand_profile.get("brandType", ""),
            "socialMedia": brand_profile.get("socialMedia", {}),
            "otherUrls": brand_profile.get("otherUrls", []),
            "manualInputText": brand_profile.get("manualInputText", ""),
            "designText": brand_profile.get("designText", ""),
            "brandVoice": {
                "voiceName": brand_voice.get("voiceName", ""),
                "summary": brand_voice.get("summary", ""),
            }
        }
        
        return jsonify(response_data), 200
    
    except Exception as e:
        logging.exception("Error in /brand/profile GET route")
        return jsonify({'error': 'An internal server error occurred.'}), 500