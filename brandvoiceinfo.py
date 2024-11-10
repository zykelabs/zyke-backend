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
from apify_client import ApifyClient
from models import (
    get_brand_profile,
    create_brand_voice,
    update_brand_voice,
    create_brand_profile,
    get_brand_voice,
    get_user_credits,
    deduct_and_log_user_credits
)
from bson import ObjectId
import jwt
from io import BytesIO
from flask_jwt_extended import get_jwt_identity, jwt_required
import requests
import os
from PIL import Image
import pandas as pd
import base64
import json
from httplib2 import Http

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize blueprint
brand_voice_bp = Blueprint('brand_voice_info', __name__)

# Initialize OpenAI clients
from openai import AsyncOpenAI, OpenAI
deepinfra_client = AsyncOpenAI(
    api_key=Config.DEEPINFRA_API_KEY,
    base_url="https://api.deepinfra.com/v1/openai",
)

client_openai_image_desc = AsyncOpenAI(
    api_key=Config.OPENAI_API_KEY,)

client_open_router = AsyncOpenAI(
    api_key=Config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# print(client_open_router)

client_openai_summ = AsyncOpenAI(
    api_key=Config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

client_open_router_async = AsyncOpenAI(
    api_key=Config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

perplexity_token = Config.PERPLEXITY_TOKEN
google_api_key = Config.GOOGLE_API_KEY
google_cse_id = Config.GOOGLE_CSE_ID

# Customize timeout
custom_http = Http(timeout=300)

# def search_webs(trend, nums = 10, delay=None):

#     api_key = google_api_key
#     cse_id = google_cse_id

#     if not api_key or not cse_id:    # Assuming you have these variables set
#         raise ValueError("Please set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables")

#     service = build("customsearch", "v1", developerKey=api_key, http=custom_http)

#     result = None

#     # Set the date range for the last delay
#     if delay is not None:
#       date = datetime.now() - timedelta(days=delay)
#       date_restrict = f"d{delay}"

#       # print(f"Date Restrict : {date_restrict}")

#       result = service.cse().list(q=trend, cx=cse_id, gl='countryIN', num=nums, dateRestrict=date_restrict).execute()

#     else:
#       result = service.cse().list(q=trend, cx=cse_id, gl='countryIN', num=nums).execute()

#     if 'items' in result:
#         return result['items'], 0.005
#     else:
#         return -1, 0
    
# async def scrape_website(url):
#     try:
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
#                           'AppleWebKit/537.36 (KHTML, like Gecko) '
#                           'Chrome/92.0.4515.131 Safari/537.36',
#             'Accept-Language': 'en-US,en;q=0.9',
#             'Accept-Encoding': 'gzip, deflate, br',
#             'Connection': 'keep-alive',
#             'Upgrade-Insecure-Requests': '1',
#             'Sec-Fetch-Dest': 'document',
#             'Sec-Fetch-Mode': 'navigate',
#             'Sec-Fetch-Site': 'none',
#             'Sec-Fetch-User': '?1',
#             'Referer': 'https://www.google.com/',
#             'DNT': '1',  # Do Not Track request header
#         }

#         async with aiohttp.ClientSession(headers=headers) as session:
#             try:
#                 async with session.get(url, timeout=60) as response:
#                     response.raise_for_status()  # Raise exception for bad status codes

#                     # Check if the content is Brotli-encoded
#                     if response.headers.get('Content-Encoding') == 'br':
#                         raw_data = await response.read()
#                         try:
#                             # Manually decompress Brotli-encoded content
#                             html = brotli.decompress(raw_data).decode('utf-8', errors='ignore')
#                         except brotli.error:
#                             # print("Brotli decompression failed.")
#                             return "No information found."
#                     else:
#                         # For other encodings like gzip or deflate
#                         html = await response.text()

#                     # Parse the HTML content
#                     soup = BeautifulSoup(html, 'html.parser')

#                     # Example: Extract all paragraph texts
#                     paragraphs = soup.find_all('p')
#                     txt = "".join([p.get_text() for p in paragraphs])

#                     return txt

#             except asyncio.TimeoutError:
#                 print("Timed out :(")
#                 return "No information found."
#             except aiohttp.ClientResponseError as e:
#                 # print(f"HTTP error occurred: {e.status} {e.message}")
#                 return "No information found."
#             except Exception as e:
#                 # print(f"An unexpected error occurred: {e}")
#                 return "No information found."

#     except aiohttp.ClientError as e:
#         # print(f"Client error occurred: {e}")
#         return "No information found."

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
  
# async def url_summ(text):
#   chat_history = [{"role": "system","content":
# '''**Role:**
# You are a chatbot responsible for summarizing articles about a brand that have been scraped from a website.

# **Task:**
# You will receive a query that was searched on Google, along with the content of an article scraped from a website related to that query. Your task is to summarize the article, ensuring that the summary includes all the important points while painting a complete picture of the information. The summary should be concise, brief, and directly related to the query.

# **Instructions:**
# 1. **Summarize relevant content only**: Focus on summarizing only the information that is directly or indirectly related to the search query. Ignore any unrelated content such as website advertisements, website info, or other irrelevant articles.

# 2. **Complete and concise**: Make sure your summary includes all relevant points and presents the full picture, but in a shortened and simple format. Avoid leaving out key information related to the query.

# 3. **Avoid unnecessary details**: Do not include unrelated information in your response. Stick only to content that matches the query’s topic, title, and description.

# 4. **No additional information**: Do not search for information, rely on your memory, or simulate a response. If no relevant information is provided, respond with:
#    - "No information was provided" if no content is available.
#    - "The information provided is not related to the search query" if the content does not match the query.

# **Purpose:**
# Your summaries will provide key insights from articles related to brands, focusing on relevant information from the scraped website content. These summaries are used to better understand a brand's online presence and messaging while avoiding irrelevant details.'''},
#                   {
#               "role": "user",
#               "content": text,
#           }]

#   response_content = ""
#   try:
#     chat_completion = await deepinfra_client.chat.completions.create(
#                               model="meta-llama/Meta-Llama-3.1-8B-Instruct",
#                               messages=chat_history,
#                               max_tokens=2048,
#                               temperature=0.1)

#     cost = (chat_completion.usage.prompt_tokens * 0.055 + chat_completion.usage.completion_tokens * 0.055) / (10**6)

#     return chat_completion.choices[0].message.content, cost

#   except Exception as e:
#     print(e)
#     return ("Error: " + str(e)), 0

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

# async def query_summ(text):
#   chat_history = [{"role": "system","content":
# '''**Role:**
# You are a chatbot responsible for effectively summarizing information gathered from various online sources.

# **Task:**
# You will receive information about a particular search query, collected from the top search results on Google. Your role is to create an exhaustive summary of this information, ensuring it is non-repetitive, concise, and includes all relevant details from the various sources provided. Your summary should cover the entire content while avoiding redundancy and unnecessary details.

# **Format:**
# You will receive input in the following format:
# ```
# Search Query: <search query>

# a. Title: <title>, Website: <website>
# Content Summary: <summary>

# b. Title: <title>, Website: <website>
# Content Summary: <summary>
# ```

# **Instructions:**
# 1. **Summarize without repetition**: Each source may contain overlapping information. Your task is to ensure that the final summary includes all relevant content from different sources without repeating the same points.

# 2. **Cover all relevant points**: The summary must cover all the key details provided in the content summaries, including information about the company’s products, services, mission, market, target audience, competitors, etc.

# 3. **Contextual understanding of sources**: Use the website name to understand the context of the content. For example:
#    - **Reddit** or public forums likely contain user discussions or opinions.
#    - **Official government or company websites** may contain formal announcements or key information.
#    - **News outlets** might provide articles, insights, or reports.
#    - **Social media handles** could contain public reactions, company updates, or informal discussions.

#    This understanding can help you tailor the summary to capture the most important points depending on the type of source.

# 4. **Simple and concise language**: Make the summary concise, written in clear, simple language that is easy for the reader to follow. Avoid making the summary too long or overly detailed, while still covering all necessary points.

# **Purpose:**
# Your summary will be used to collect important information about a company, its products, services, and related content. This information is critical for equipping other chatbots that generate content for the company (e.g., social media posts, advertisements) with the necessary context to personalize their outputs and align them with the company’s style and messaging. The quality and accuracy of your summaries are crucial to ensuring these chatbots can create highly relevant, personalized content.'''},
#                   {
#               "role": "user",
#               "content": text,
#           }]

#   response_content = ""
#   try:
#     chat_completion = await deepinfra_client.chat.completions.create(
#                               model="meta-llama/Meta-Llama-3.1-70B-Instruct",
#                               messages=chat_history,
#                               max_tokens=2048,
#                               temperature=0.1)

#     cost = (chat_completion.usage.prompt_tokens * 0.35 + chat_completion.usage.completion_tokens * 0.4) / (10**6)

#     return chat_completion.choices[0].message.content, cost

#   except Exception as e:
#     print(e)
#     return ("Error: " + str(e)), 0

async def final_summ(text, prompt, model):

  chat_history = [{"role": "system","content": prompt},
                  {
              "role": "user",
              "content": text,
          }]

  try:
        completion = await client_open_router.chat.completions.create(
        model=model[0],
        messages= chat_history,
        temperature=0.3,
        max_tokens=58_764)
        cost = (completion.usage.prompt_tokens * model[1] + completion.usage.completion_tokens * model[2]) / (10**6)
        return completion.choices[0].message.content, cost
  except Exception as e:
    print(e)
    return ("Error: " + str(e.response.status_code)), 0

async def fetch_search_info_pplx(text, brand_type):
  url = "https://api.perplexity.ai/chat/completions"

  sys_prompt = ""

  if brand_type == "big_brands":
    sys_prompt = '''Be precise.
  You have the role of searching about information (about a brand) and return the best matching information.
  Respond in a detailed manner, but only return relevant information.
  Be as detailed, precise and accurate as possible. Do not compromise on accuracy for over detailing or vice versa.

  **Important:**
  Do not hallucinate or create information by yourself.
  Do not confuse some other brand (with a similar name or work) with the current brand.
  If you do not find information about current brand or find irrelevant information then mention that you were not able to find the required information.
  Do not respond with unrelated information or false information.'''

  if brand_type == "small_brands":
    sys_prompt = '''Be precise.
  You have the role of searching about information (about a brand) and return the best matching information.
  Respond in a detailed manner, but only return relevant information.
  You will get some information about a brand as context, to understand which brand we are exactly talking about, the brand will not be very popular and this context would be helpful for your search.
  Be as detailed, precise and accurate as possible. Do not compromise on accuracy for over detailing or vice versa.

  **Important:**
  Do not hallucinate or create information by yourself.
  Do not confuse some other brand (with a similar name or work) with the current brand.
  If you do not find information about current brand or find irrelevant information then mention that you were not able to find the required information.
  Do not respond with unrelated information or false information.'''

  payload = {
      "model": "llama-3.1-sonar-huge-128k-online",
      "messages": [
          {
              "role": "system",
              "content": sys_prompt
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

async def get_search_query_context(text):
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
        completion = await client_open_router.chat.completions.create(
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
  queries = [f'{company} company overview and history',
  f'{company} founder history and story',
  f'{company} core values, mission and vision',
  f'{company} product and brand differentiation',
  f'{company} recent product launches',
  f'{company} competitors and market share',
  f'{company} market presence regions',
  f'{company} marketing and branding strategy',
  f'{company} successful marketing campaigns',
  f'{company} social media platforms and posting style',
  f'{company} target audience',
  f'{company} public perception and customer reviews',
  f'{company} corporate social responsibility, sustainability initiatives and environmental impact',
  f'{company} industry accolades, awards and recognitions',
  f'{company} news, latest announcements and media coverage',
  f'{company} technological innovations and research and development',
  f'{company} brand voice and tone',
  f'{company} logo, tagline, slogans and key messaging',
  f'{company} brand colors and typography',
  f'{company} influencer partnerships',
  f'{company} customer loyalty programs',
  f'{company} product and service offerings and their pricing',
  f'{company} subsidiaries and sister companies']

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

  total_text = f'####{""} **Name of the {entity}: {company}**\n### Location: {location}\n'

  if len(industries) > 0:
    total_text += "### **Industries:** "
    for industry in industries:
        total_text += f'{industry},'
    total_text += '\n'

  if len(content_types) > 0:
    total_text += f'###{""} **{entity} Content type:**'
    for content_type in content_types:
        total_text += f'{content_type},'
    total_text += '\n'
  
  if len(target_audience) > 0:
    total_text += f'###{""} **{entity} Target Audiences:**'
    for audience in target_audience:
        total_text += f'{audience},'
    total_text += '\n'

  total_text += f'###{""} **{entity} Tone (Options: Neutral; Slightly, Occasionally, Mostly, Completely Casual or Neutal):** {brand_tone}\n'
  
  if len(brand_personalities) > 0:
    total_text += f'###{""} **{entity} Personality:**'
    for personality in brand_personalities:
        total_text += f'{personality},'
    total_text += '\n\n\n\n'

  if (manual_input_text is not None or len(manual_input_text) >= 0) or (design_text is not None or len(design_text) >= 0):
    total_text += f'#### {entity} style information (manually added):\n\n'

    if manual_input_text is not None or len(manual_input_text) >= 0:
        total_text += f'### {entity} information (plain text):\n{manual_input_text}\n\n\n\n'

    if design_text is not None or len(design_text) >= 0:
        total_text += f'### {entity} Design Style Information (Plain Text):\n\n{design_text}\n\n\n\n'

  if attachments_text is not None or len(attachments_text) >= 0:
    total_text += f'### User added attachments:\n\n{attachments_text}\n\n\n\n'

  if manual_urls is not None and len(manual_urls) >= 0:
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
      pplx_brand_type = "big_brands"
      # URLS = {}
      # for i in range(len(queries)):
      #   searches, cost = search_webs(queries[i],10)
      #   costs += cost
      #   for j in searches:
      #     try:
      #       URLS[queries[i]].append([j['title'],j['snippet'],j['link'],None])
      #     except:
      #       URLS[queries[i]] = [[j['title'],j['snippet'],j['link'],None]]

      # scrapes = []
      # for i in URLS:
      #   for j in URLS[i]:
      #     scrapes.append(scrape_website(j[2]))
      # results_scrape = await asyncio.gather(*scrapes)

      # c = 0
      # url_summs = []

      # for i in URLS:
      #   for j in URLS[i]:
      #     j[-1] = results_scrape[c]

      #     url_prompt = f"Search Query: {i}\n\nContent: {j[3]}"
      #     temp = url_summ(url_prompt)
      #     url_summs.append(temp)
      #     c+=1
      # results_url_summ = await asyncio.gather(*url_summs)

      # query_summs_prompts = {}
      # query_summs = []
      # c2 = 0

      # for i in URLS:
      #   query_summs_prompts[i] = f"Search Query: {i}\n\n"
      #   for n,j in enumerate(URLS[i]):
      #     query_summs_prompts[i] += f'''{chr(97+n)}. Title: {j[0]}, Website: {j[2]}
      # Content Summary:\n {results_url_summ[c2][0]} \n\n\n'''
      #     costs += results_url_summ[c2][1]
      #     c2+=1
      #   temp2 = query_summ(query_summs_prompts[i])
      #   query_summs.append(temp2)
      # results_query_summ = await asyncio.gather(*query_summs)

      if brand_type == 2:
        pplx_brand_type = "small_brands"
        context, cost = await get_search_query_context(total_text)
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
        temp = fetch_search_info_pplx(query, pplx_brand_type)
        results_query_summ_async.append(temp)
      results_query_summ = await asyncio.gather(*results_query_summ_async)

    results = ''
    for id,i in enumerate(results_query_summ):
      results += f'Search Query: {queries[id]}\n\n\nInformation:\n\n'
      results += i[0]
      costs += i[1]
      results += '\n\n\n\n'

    # print(results,"\n\n\n\n")
    results = total_text + "##### Company Data Obtained from search:\n\n" + results
    # print(results,"\n\n\n\n")

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

  final_results,cost = await final_summ(results, prompt, model)
  costs += cost
  #   final_results = final_results.replace("#### ", "")
  #   final_results = final_results.replace("### ", "")
  #   final_results = final_results.replace("## ", "")
  #   final_results = final_results.replace("####", "")
  #   final_results = final_results.replace("###", "")
  #   final_results = final_results.replace("##", "")
  #   final_results = final_results.replace("**", "")
  return final_results, costs

#Post Scrapping
def scrape_instagram(username, n = 20):
  insta_images = []
  client_apify = ApifyClient('REDACTED_REVOKED_APIFY_TOKEN')

  # Prepare the Actor input
  run_input = {
      "username": username,
      "resultsLimit": n,
  }

  # Run the Actor and wait for it to finish
  run = client_apify.actor("nH2AHrwxeTRJoN5hX").call(run_input=run_input)

  # Fetch and print Actor results from the run's dataset (if there are any)
  for item in client_apify.dataset(run["defaultDatasetId"]).iterate_items():
      if len(item['images']) != 0:
        insta_images.append([item['caption'],item['images'],datetime.strptime(item['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")])
      elif item['displayUrl']:
        insta_images.append([item['caption'],[item['displayUrl']],datetime.strptime(item['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")])
  cost = 2.3/1000 * n
  return insta_images, cost

async def scrape_img(img_url):
  try:
    response = requests.get(img_url, timeout=60)
    return response
  except:
    return -1

async def image_desc(content, caption):
  # model = "openai/gpt-4o-mini"
  # response = await client_open_router_async.chat.completions.create(
  model = "gpt-4o-mini"
  response = await client_openai_image_desc.chat.completions.create(
  model=model,
  messages=[
    {"role": "system","content":
'''Imagine you are both a brand strategist and a graphic designer, tasked with deeply understanding and replicating the visual style of your brand across an entire post containing multiple images. Each image is accompanied by a caption that provides additional context. Your goal is to create an exhaustive, highly detailed description of the entire post and each individual image to ensure consistency in future posts and designs.


### For the Entire Post:

**Overall Context, Usage, and Messaging:**
Explain the Post: Provide a comprehensive overview of what the post conveys as a whole. Describe the collective meaning and messaging behind all the images and their captions.
Intent Behind the Post: Explain the purpose of the post (e.g., promotional campaign, brand storytelling, product launch) and the intended audience engagement.
Usage Context: Describe where and how this post is intended to be used (e.g., Instagram carousel, Facebook album, website gallery). Discuss how this context influences the overall design and cohesion of the images.
Visual and Thematic Consistency: Analyze how the images and captions work together to create a unified aesthetic and message. Highlight any recurring themes, motifs, or visual elements that tie the post together.


### For Each Individual Image:

**Context, Usage, and Messaging:**
Explain the Image: Describe the specific meaning and messaging of the individual image.
Intent Behind Posting the Image: Explain why this particular image was included in the post and its role in the overall narrative.
Usage Context: Detail where and how this image might be used within the post (e.g., first image to grab attention, middle images to provide information, last image as a call-to-action).
Influence of Context on Design: Describe how the intended usage and placement within the post influence the design elements of the image.

**Composition and Layout:**
Arrangement of Elements: Explain the positioning, balance, and use of negative space within the image.
Alignment and Focal Points: Note how elements are aligned and identify the focal points and visual hierarchy.

**Color Palette:**
Colors Used - Identify and describe the specific colors, including their shades and tones.
Brand Alignment- Explain how these colors align with the brand’s identity and the emotional responses they evoke.

**Imagery and Graphics:**
Subject Matter: Describe the main subjects, including people, objects, or icons.
Style and Symbolism: Discuss the artistic style (e.g., realism, minimalism) and any symbolic elements present.
Overall Mood: Convey the mood or atmosphere created by the visuals.

**Texture and Effects:**
Textures and Patterns: Note any textures or patterns used in the image.
Graphic Effects: Describe effects such as gradients, shadows, overlays, and how they contribute to the image’s depth and feel.

**Branding Elements:**
Logos and Taglines: Identify any logos, taglines, or other brand-specific features included.
Integration and Role: Describe how these elements are integrated into the image and their role in reinforcing brand identity.

**Lighting and Shadows:**
Use of Lighting: Discuss how lighting, shadowing, and reflections are utilized.
Impact on Mood and Focus: Explain how these elements influence the image’s mood and where the viewer’s attention is directed.

**Text Description:**
Text Content: Transcribe all text present in the image, including captions.
Meaning and Conveyance: Describe the meaning behind the text and what message it conveys to the end-user.
Detailed Analysis: Provide a thorough explanation of how the text relates to the visual elements and overall messaging.

**Typography:**
Font Details: Detail the font style, size, weight, and placement of any text.
Design Complementation: Explain how the typography complements the overall design and adheres to brand guidelines.


### Instructions for Execution:

**Consider Captions:** Alongside the image inputs, consider its corresponding caption to get better context for analysis of the images.
**Structured Output:** Present the description for the entire post first, followed by individual sections for each image as outlined above.
**Comprehensive Detail:** Ensure that each description is thorough enough that another designer, with no prior knowledge of the brand, could recreate the style and essence accurately.
**Blueprint Creation:** Think of the descriptions as creating a blueprint for future designs that embody the same branding and visual principles.
**Extensive Output:** Write extremely detailed descriptions, make them vivid. Write description for each of the images provided to you. Do not miss out on any image. Also write detailed description about the whole post in general, as mentioned previously.
**It is very important to follow all instructions mentioned. Be patient and write about the post and all the individual images mentioned previously. Do not miss any of the images.**

### Example Structure:
`Overall Post Description:

[Detailed analysis of the entire post]
Image 1:

Caption: [Caption text]
Context, Usage, and Messaging:
[Detailed description]
Composition and Layout:
[Detailed description]
(Continue with all specified sections)

Image 2:

Caption: [Caption text]
Context, Usage, and Messaging:
[Detailed description]
Composition and Layout:
[Detailed description]
(Continue with all specified sections)
(Continue for all images in the post)

Image 3:
......`

### Usage Tips:

**Consistency is Key:** Ensure that the descriptions maintain a consistent level of detail and structure for both the overall post and individual images.
**Leverage Captions:** Use the captions to enhance understanding of each image’s role and context within the post.
**Focus on Brand Identity:** Pay special attention to elements that reinforce the brand’s identity to maintain coherence across all future designs.'''},
    {"role": "user",
      "content": content,},]

  , max_tokens=8192,
  temperature = 0.15)

  cost = (response.usage.prompt_tokens * 0.15 + response.usage.completion_tokens * 0.6) / (10**6)

  return (response.choices[0].message.content,cost,caption)

async def image_out_summ(text):
  chat_history = [{"role": "system","content":
'''**Instruction:**

You are tasked with structuring the textual description of a collection of highly detailed social media posts from a specific brand. The posts are organized in reverse chronological order, with the most recent posts appearing first. The posts themselves are not provided, rather their extremely detailed descriptions are provided. Each post includes a caption and descriptions of multiple images, focusing on their composition, messaging, color palette, and branding elements. **Please note that each post may contain multiple images, and the description for each post includes both a general overview of the post and individual explanations for each image. Ensure that you understand the difference between the overall post content and the specific individual image details during structuring. Also, in these instructions, by "posts," we mean the entire post, not the individual images.** The objective is to condense the information while preserving the essence of the brand's style and core attributes.
**Give extremely detailed responses, describing the brand's post in a highly extensive manner, keeping your response comprehensive, large and detailed. Do not compress on the information provided and capture every minute aspect. Summarisation would lead to information loss and thus detoriation of quality.**
**Note: You have to keep the description long and detailed. It must be so that a new graphic designer, after reading through it can understand the psychology of the brand, its posting style, and its marketing methods and also get a visual understanding of how the posts look, just by reading it. It should be enough to make the designer visualize each and every aspect of post-designing and post-creation. It should also give him a sense of what type of posts the brand creates, like funny, informative, humorous, witty, youthful, etc. There should also be a number of post examples, at least 10, which should represent a diverse range of posts and should give the designer an idea about the posts. It should be extensive, comprehensive, and detailed. It should also be concise at the same time. It should not contain repetitive information or unnecessary aspects. Thus, you have to properly structure it, describing the posting, marketing, .. styles.**

**Guidelines for Structuring:**

1. **Preserve the Brand’s Style and Voice:**
   - Ensure that the tone, language, and unique vocabulary characteristics of the brand remain intact.
   - Highlight recurring themes and common post structures, such as how captions are framed, the use of emojis, and formatting preferences.

2. **Maintain Key Details of Visual Descriptions:**
   - For image descriptions, capture essential visual elements, including color schemes, composition, and any prominent features (e.g., logos, branding marks).
   - Focus on how these visual elements contribute to the overall messaging of each post.

3. **Provide Detailed Descriptions:**
   - Ensure that the description retain comprehensive details about each aspect of the posts, including nuanced elements of the captions and intricate details of image compositions.
   - Avoid overly general statements; instead, strive to include specific examples and descriptive language that reflect the depth of the original content.

4. **Analyse Recurring Patterns and Elements:**
   - Identify patterns in post types, such as product promotions, behind-the-scenes content, or customer testimonials.
   - Group similar content types and analyse them cohesively, without losing important distinctions between posts.

5. **Minimize Redundancy:**
   - Eliminate unnecessary repetition of identical or very similar information across posts, focusing instead on the unique aspects of each one.
   - Whenever appropriate, generalize across multiple posts where they follow a consistent format or theme.
   - Whenever appropriate, give extremely detailed analysis of individual posts and its elements.

6. **Emphasize Recent Posts:**
   - Give additional importance to the most recent 5-10 posts, ensuring that their unique elements and any new trends in the brand’s style are adequately represented in the response.
   - Analyze these recent posts to capture any shifts or evolutions in the brand’s messaging or visual presentation.

7. **Include Recent Posts as Examples:**
   - **Compulsorily include at least some of the recent posts (specifically from the last 5-10 posts) in their entirety as examples within the response to showcase the latest style and content approaches.**
   - **Ensure that the posts you select as examples from the recent 5-10 posts are diverse and not similar to each other.** *(Do not select similar posts)*

8. **Retain Raw Examples for Multi-Shot Prompting:**
   - **Select and retain approximately 10 posts in their original, detailed form to serve as raw examples for multi-shot prompting.**
   - **Ensure these examples are diverse and representative of the brand’s range, covering different post types and styles.**
   - **Keep the raw examples identical to the input data without any modification.**

9. **Organize the Description Effectively:**
   - Structure the description in a clear and logical manner, possibly grouping similar posts together and highlighting key themes and styles.
   - Ensure that the description flows cohesively, making it easy to understand the brand’s overall social media strategy and style.

**Output Requirements:**

* **Comprehensive Description:** A highly detailed, structured version of the 20 posts, provided to you as input, that captures all essential aspects of the brand’s style, voice, and recurring themes without excessive compression. The description should include thorough descriptions that reflect the depth and nuance of the original posts.
* **Included Recent Examples:** Incorporate at least some of the most recent posts (preferably from the first 5-10) as full examples to illustrate current style and content.
* **Raw Multi-Shot Examples:** Provide atleast 10 posts in their original detailed form to be used as raw examples for multi-shot prompting. Try to make the selection of these posts diverse.
* **Final Conclusion:** Provide a comprehensive conclusion summarizing the brand's marketing or branding style, its posts, and your overall response to the structuring task.
* **Note:** Do not change the content of the Included Recent Examples or the Raw Multi-Shot Examples. Also do not write "(Details as provided above)" in their content, you have to copy-paste that content again.

Focus on clarity and conciseness while maintaining the brand’s distinct identity throughout the response. Ensure that the final output serves as a robust guide for generating future posts that align seamlessly with the established brand style. **Additionally, provide a conclusion that encapsulates the overall findings and insights derived from the posts.**'''},
                  {
              "role": "user",
              "content": f"Here is the social media posts data:\n\n{text}",
          }]

  # response_content = ""
  try:
        completion = await client_openai_summ.chat.completions.create(
        model="openai/o1-mini",
        messages= chat_history,
        temperature=0.1,
        max_tokens=58_764)
        # print(completion.usage)
        cost = (completion.usage.prompt_tokens * 3 + completion.usage.completion_tokens * 12) / (10**6)
        return completion.choices[0].message.content, cost
  except Exception as e:
    print(e)
    return ("Error: " + str(e)), 0

async def brand_post_info_scrape(insta_username):
  costs = 0
  insta_images, cost = scrape_instagram(insta_username)
  costs += cost
  insta_images.sort(key=lambda x: x[2], reverse = True)

  # imgs = []
  # for i in insta_images:
  #   for j in i[1]:
  #     imgs.append(j)

  image_dict = {}
  c = 0
  for i in range(len(insta_images)):
    image_dict[insta_images[i][0]] = [[],insta_images[i][2]]
    for j in insta_images[i][1]:
      image_dict[insta_images[i][0]][0].append(j)
      c += 1

  # imgs = []
  # for i in insta_images:
  #   for j in i[1]:
  #     imgs.append(scrape_img(j))

  # img_scrape = await asyncio.gather(*imgs)
  # image_dict = {}
  # c = 0
  # for i in range(len(insta_images)):
  #   image_dict[insta_images[i][0]] = [[],insta_images[i][2]]
  #   for j in range(len(insta_images[i][1])):
  #     try:
  #       img = BytesIO((img_scrape[c]).content)
  #       image_dict[insta_images[i][0]][0].append(img)
  #     except:
  #       image_dict[insta_images[i][0]][0].append(-1)
  #     c += 1

  # # Modify this for saving brand voice images in directory
  # dir = os.getcwd()
  # if not os.path.exists(f'{dir}/images'):
  #   os.makedirs(f'{dir}/images')

  # l = []
  # idx = 0

  # for i in image_dict:
  #   idx += 1
  #   for id,j in enumerate(image_dict[i][0]):
  #     try:
  #       img = Image.open(j)
  #       filename = f"{dir}/images/{image_dict[i][1]}_{id+1}.jpg"
  #       img.save(filename)
  #       l.append([idx, id+1,f"{image_dict[i][1]}_{id+1}.jpg",i,image_dict[i][1]])
  #     except Exception as e:
  #       # print(f"{image_dict[i][1]}_{id+1}.jpg")
  #       # print(image_dict[i][1])
  #       print(f"Error in Saving part: {e}")

  # df = pd.DataFrame(l, columns=['post_number','image_number_in_post','image_file_dir','caption', 'timestamp'])
  # df.to_csv(f'{dir}/images/insta_image_info.csv', index=False)

  descs = []
  for i in list(image_dict.keys()):

    content = [{"type": "text", "text": f"The caption for the image is: {i}"}]
    # print(i)

    for j in image_dict[i][0]:
      # print(j)
      # base64_image = base64.b64encode(j.getvalue()).decode('utf-8')
      content.append({"type": "image_url",
        "image_url": {
        "url": j,
        "detail": "high"}})

    # if check == 0:
    #   # descs.append(-1)
    #   continue

    descs.append(image_desc(content, i))

  img_descs = await asyncio.gather(*descs)

  # print("Getting Image Desc")
  out = ''
  for i in img_descs:
    gen = i[0]
    # print(f'#### Caption: {i[2]}\n\n#### Output:\n\n{gen}\n\n\n\n')
    out += f'#### Caption: {i[2]}\n\n#### Output:\n\n{gen}\n\n\n\n'
    costs += i[1]

  out2, cost = await image_out_summ(out)
  costs += cost
  return out2, costs

async def generate_brand_voice(company, industries, manual_urls, attachments, manual_input_text, design_text, location, content_types, brand_personalities, target_audience, brand_tone, brand_type, insta_handle):
  # return "Summary post", "Historical Post Analysis", 0.016
  # print("\n\nInsta Handle: ",insta_handle)
  if len(insta_handle) > 0 and len(insta_handle[0].strip()) > 0:
    insta_handle[0] = insta_handle[0].strip()
    general_info = brand_info_scrape(company, industries, manual_urls, attachments, manual_input_text, design_text, location, content_types, brand_personalities, target_audience, brand_tone, brand_type)
    hist_post_analysis = brand_post_info_scrape(insta_handle)
    brand_voice_async = [general_info, hist_post_analysis]
    brand_voice = await asyncio.gather(*brand_voice_async)

    costs = 0
    general_info_text, cost = brand_voice[0]
    costs += cost
    post_data, cost = brand_voice[1]
    costs += cost

    return general_info_text, post_data, cost

  else:
    general_info = await brand_info_scrape(company, industries, manual_urls, attachments, manual_input_text, design_text, location, content_types, brand_personalities, target_audience, brand_tone, brand_type)
    general_info_text, cost = general_info
    return general_info_text, " ", cost

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
    try:
        user_id = get_jwt_identity()

        # Fetch the user's current credits
        user_credits = get_user_credits(user_id)
        if user_credits is None:
            return jsonify({'error': 'User not found'}), 404

        # Check if the user has enough credits
        if user_credits <= 0:
            return jsonify({'error': 'Insufficient credits to generate brand voice.'}), 402

        # Ensure the request is multipart/form-data
        if not request.content_type.startswith('multipart/form-data'):
            return jsonify({'error': 'Content-Type must be multipart/form-data'}), 400

        # Extract form fields
        company = request.form.get('company', '').strip()
        location = request.form.get('location', '').strip()
        brand_voice_name = request.form.get('brandVoiceName', '').strip()
        brand_tone = request.form.get('brandTone', '').strip()
        brand_type = request.form.get('brandType', '').strip()
        industries = request.form.get('industries')

        # Validate required fields
        required_fields = ['company', 'location', 'brandVoiceName', 'brandTone', 'brandType']
        missing_fields = [field for field in required_fields if not request.form.get(field)]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

        # Parse and validate brandType
        try:
            brand_type = int(brand_type)
            if brand_type not in [1, 2, 3, 4]:
                raise ValueError
        except ValueError:
            return jsonify({'error': 'Invalid brandType. Must be one of [1, 2, 3, 4]'}), 400

        # Parse and validate industries
        try:
            industries = json.loads(industries)
            if not isinstance(industries, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for industries.'}), 400

        # Extract and parse otherIndustries
        other_industries = request.form.get('otherIndustries', '[]')
        try:
            other_industries = json.loads(other_industries)
            if not isinstance(other_industries, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for otherIndustries.'}), 400

        # Extract and parse contentTypes
        content_types = request.form.get('contentTypes', '[]')
        try:
            content_types = json.loads(content_types)
            if not isinstance(content_types, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for contentTypes.'}), 400

        # Extract and parse otherContentTypes
        other_content_types = request.form.get('otherContentTypes', '[]')
        try:
            other_content_types = json.loads(other_content_types)
            if not isinstance(other_content_types, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for otherContentTypes.'}), 400

        # Extract and parse targetAudience
        target_audience = request.form.get('targetAudience', '[]')
        try:
            target_audience = json.loads(target_audience)
            if not isinstance(target_audience, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for targetAudience.'}), 400

        # Extract and parse otherTargetAudiences
        other_target_audiences = request.form.get('otherTargetAudiences', '[]')
        try:
            other_target_audiences = json.loads(other_target_audiences)
            if not isinstance(other_target_audiences, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for otherTargetAudiences.'}), 400

        # Extract and parse brandPersonalities
        brand_personalities = request.form.get('brandPersonalities', '[]')
        try:
            brand_personalities = json.loads(brand_personalities)
            if not isinstance(brand_personalities, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for brandPersonalities.'}), 400

        # Extract and parse socialMedia
        social_media_json = request.form.get('socialMedia', '{}')
        try:
            social_media_data = json.loads(social_media_json)
            if not isinstance(social_media_data, dict):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for socialMedia.'}), 400

        instagram = social_media_data.get("instagram", "").strip('@')
        twitter = social_media_data.get("twitter", "").strip('@')
        linkedin = social_media_data.get("linkedin", "").strip()

        if linkedin and not linkedin.startswith("https://www.linkedin.com/"):
            return jsonify({'error': 'LinkedIn URL must start with "https://www.linkedin.com/"'}), 400

        social_media = {
            "instagram": instagram,
            "twitter": twitter,
            "linkedin": linkedin
        }

        # Extract and parse otherUrls
        other_urls_json = request.form.get('otherUrls', '[]')
        try:
            other_urls = json.loads(other_urls_json)
            if not isinstance(other_urls, list):
                raise ValueError
        except:
            return jsonify({'error': 'Invalid format for otherUrls.'}), 400

        # Extract manualInputText and designText
        manual_input_text = request.form.get('manualInputText', '').strip()
        design_text = request.form.get('designText', '').strip()

        # Extract files
        uploaded_files = request.files.getlist('files')
        attachments = []
        for file in uploaded_files:
            if file.filename == '':
                continue
            try:
                file_content = file.read().decode('utf-8', errors='ignore')
                attachments.append(file_content)
                print(file_content)
            except Exception as e:
                logger.error(f"Error reading file {file.filename}: {e}")
                return jsonify({'error': f'Failed to read file {file.filename}.'}), 400

        profile_data = {
            'user_id': user_id,
            'company': company,
            'brandVoiceName': brand_voice_name,
            'industries': industries,
            'otherIndustries': other_industries,
            'location': location,
            'contentTypes': content_types,
            'otherContentTypes': other_content_types,
            'targetAudience': target_audience,
            'otherTargetAudiences': other_target_audiences,
            'brandPersonalities': brand_personalities,
            'brandTone': brand_tone,
            'brandType': brand_type,
            'socialMedia': social_media,
            'otherUrls': other_urls,
            'manualInputText': manual_input_text,
            'designText': design_text,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        # Run async tasks to get the brand voice data and total cost
        # async def run_async_tasks():
        #     total_cost = 0
        #     summary, cost = await brand_info_scrape(
        #         company=profile_data['company'],
        #         industries=industries,
        #         manual_urls=[url['url'] for url in other_urls],
        #         attachments=attachments,
        #         manual_input_text=profile_data['manualInputText'],
        #         design_text=profile_data['designText'],
        #         location=profile_data['location'],
        #         content_types=content_types,
        #         brand_personalities=brand_personalities,
        #         target_audience=target_audience,
        #         brand_tone=profile_data['brandTone'],
        #         brand_type=profile_data['brandType']
        #     )
        #     total_cost += cost
        #     descriptions, cost = await brand_post_info_scrape(social_media['instagram'])
        #     total_cost += cost
        #     sum_posts_data, cost = await image_out_summ(descriptions)
        #     total_cost += cost
        #     return summary, total_cost, sum_posts_data
        
        # print(profile_data['company'])
        # print(industries)
        # print([url['url'] for url in other_urls])
        # print(attachments)
        # print(profile_data['manualInputText'])
        # print(profile_data['designText'])
        # print(content_types)
        # print(brand_personalities)
        # print(target_audience)
        # print(profile_data['brandTone'])
        # print(profile_data['brandType'])
        # print([social_media['instagram']])
        # print(profile_data['location'])

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            summary, insta_descriptions, total_cost = loop.run_until_complete(
              generate_brand_voice(
                company=profile_data['company'],
                industries=industries,
                manual_urls=[url['url'] for url in other_urls],
                attachments=attachments,
                manual_input_text=profile_data['manualInputText'],
                design_text=profile_data['designText'],
                location=profile_data['location'],
                content_types=content_types,
                brand_personalities=brand_personalities,
                target_audience=target_audience,
                brand_tone=profile_data['brandTone'],
                brand_type=profile_data['brandType'],
                insta_handle=[social_media['instagram']],
              )
            )
        except Exception as e:
            logger.exception("Async tasks failed")
            return jsonify({'error': 'Failed to process brand voice.'}), 500
        finally:
            loop.close()

        # Deduct credits and log the transaction
        deduction_description = "Brand voice creation"
        success, error_msg = deduct_and_log_user_credits(user_id, total_cost, deduction_description, transaction_type="brand_voice_creation")

        if not success:
            # Return the specific error message captured
            return jsonify({"error": error_msg}), 500

        # Save the brand profile to MongoDB
        profile_id = create_brand_profile(user_id, profile_data)

        # Prepare the brand voice data
        voice_data = {
            'voiceName': profile_data['brandVoiceName'],
            'summary': summary,
            'instagramDescriptions': insta_descriptions,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        # Save the brand voice to MongoDB
        create_brand_voice(profile_id, voice_data)

        # Fetch updated credits
        updated_credits = get_user_credits(user_id)

        return jsonify({
            'msg': 'Brand profile created successfully.',
            'summary': voice_data['summary'],
            'instagramDescriptions': insta_descriptions,
            'remainingCredits': updated_credits
        }), 201

    except Exception as e:
        logger.exception("Error in /brand/create POST route")
        return jsonify({'error': 'An internal server error occurred.'}), 500

# Apply nest_asyncio to allow nested event loops (necessary for certain environments)
nest_asyncio.apply()

@brand_voice_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user_id = get_jwt_identity()
        # print(user_id)
        # Fetch the brand profile from MongoDB
        brand_profile = get_brand_profile(user_id)
        if not brand_profile:
            return jsonify({'error': 'Brand profile not found.'}), 404

        # Fetch the associated brand voice
        brand_voice = get_brand_voice(brand_profile['_id'])
        if not brand_voice:
            return jsonify({'error': 'Brand voice not found for this profile.'}), 404

        # Retrieve Instagram descriptions and total cost from brand_voice
        insta_descriptions = brand_voice.get("instagramDescriptions", "")

        # Ensure all array fields are lists
        target_audience = brand_profile.get("targetAudience", [])
        if not isinstance(target_audience, list):
            target_audience = [target_audience]

        industries = brand_profile.get("industries", [])
        if not isinstance(industries, list):
            industries = [industries]

        content_types = brand_profile.get("contentTypes", [])
        if not isinstance(content_types, list):
            content_types = [content_types]

        brand_personalities = brand_profile.get("brandPersonalities", [])
        if not isinstance(brand_personalities, list):
            brand_personalities = [brand_personalities]

        other_urls = brand_profile.get("otherUrls", [])
        if not isinstance(other_urls, list):
            other_urls = [other_urls]

        # Prepare and validate social media data for frontend
        social_media = brand_profile.get("socialMedia", {})
        response_social_media = {
            "instagram": social_media.get("instagram", ""),
            "twitter": social_media.get("twitter", ""),
            "linkedin": social_media.get("linkedin", "")
        }

        # Prepare the response data
        response_data = {
            "company": brand_profile.get("company", ""),
            "industries": industries,
            "location": brand_profile.get("location", ""),
            "contentTypes": content_types,
            "brandPersonalities": brand_personalities,
            "targetAudience": target_audience,
            "brandTone": brand_profile.get("brandTone", ""),
            "brandType": brand_profile.get("brandType", ""),
            "socialMedia": response_social_media,
            "otherUrls": other_urls,
            "manualInputText": brand_profile.get("manualInputText", ""),
            "designText": brand_profile.get("designText", ""),
            "brandVoice": {
                "voiceName": brand_voice.get("voiceName", ""),
                "summary": brand_voice.get("summary", ""),
                "instagramDescriptions": insta_descriptions,
            }
        }

        return jsonify(response_data), 200

    except Exception as e:
        logger.exception("Error in /brand/profile GET route")
        return jsonify({'error': 'An internal server error occurred.'}), 500
