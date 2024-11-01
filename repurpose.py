import requests
import time
import nest_asyncio
from aiohttp import ClientTimeout
import asyncio
import logging
from urllib.parse import urljoin, urlparse
import random
import aiohttp
import re
from bs4 import BeautifulSoup
import chardet
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.generativeai.types import GenerationConfig
from vertexai.generative_models import Image as VImage
from google.cloud import storage
import os
from typing import Optional, Set, Dict
from collections import deque
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
from models import get_user_credits,deduct_and_log_user_credits

# Get the absolute path of the current file
file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)

google_cloud_project_id = Config.GOOGLE_CLOUD_PROJECT

# print("File path:", dir_path)

google_vertex_key_path = f'{dir_path}/{Config.GOOGLE_CLOUD_JSON_AUTH_PATH}'

credentials = Credentials.from_service_account_file(
  google_vertex_key_path,
  scopes=['https://www.googleapis.com/auth/cloud-platform'])

# Create a blueprint for repurpose
repurpose_bp = Blueprint('repurpose', __name__)

def get_insta_post(urls, post_type):
  # print("URLS: ",urls)
  # Replace 'your_token' with the actual token
  token = Config.BRIGHT_DATA_TOKEN

  dataset_id = {"post":Config.BRIGHT_DATA_INSTA_POST_DATASET_ID, "reel":Config.BRIGHT_DATA_INSTA_REEL_DATASET_ID}

  url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id[post_type]}"

  # Define headers
  headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json"
  }

  data = []

  for ur in urls:
    ur = ur.rstrip('/')
    ur = ur.replace("reels","reel")
    data.append({"url": ur})
    
  # print(url)
  # print(data)
  # print(headers)

  # Make the request
  response = requests.post(url, headers=headers, json=data).json()
  # print(response)
  # print(response.json())
  
  # print(response)

  snapshot_id = response['snapshot_id']

  url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"

  # Define headers
  headers = {
      "Authorization": f"Bearer {token}",
  }
  
  # print(url)
  # print(headers)

  # Make the request
  response = requests.get(url, headers=headers).json()

  while 'message' in response:
    if 'Snapshot is not ready yet' in response['message']:
      time.sleep(11)
      response = requests.get(url, headers=headers).json()
      
  # print(response[0]['video_url'])

  # print(len(response))

  out = []

  for i in response:
    obj = None
    if post_type == "post":
      obj = i['photos']
    elif post_type == "reel":
      obj = i['video_url']

    caption = i['description']
    out.append([obj, caption])

  return out, len(urls) * 0.001

# Apply nest_asyncio to allow nested event loops (necessary for Colab)
nest_asyncio.apply()
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
    
def describe_post(system_prompt, prompt, url, cont_type):

  if credentials.expired:
    credentials.refresh(Request())

  vertexai.init(project=google_cloud_project_id, location="asia-south1", credentials=credentials)

  model = GenerativeModel("gemini-1.5-flash-002", system_instruction=[system_prompt],)
  generation_config = GenerationConfig(temperature = 0.3, max_output_tokens = 4096)

  contents = [prompt]
  if cont_type == 'yt-video':
    video_file = Part.from_uri(
        uri=url,
        mime_type="video/mp4",
    )

    contents = [video_file, prompt]

  elif cont_type == 'reel':
    # print(url)
    video_file = Part.from_uri(
        uri=url,
        mime_type="video/mp4",
    )

    contents = [video_file, prompt]

  elif cont_type == 'post':
    contents = []
    for ur in url:
      img = Part.from_image(VImage.load_from_file(ur))
      contents.append(img)

    contents.append(prompt)

  response = model.generate_content(contents)
  #   print(response.usage_metadata)
  cost = (response.usage_metadata.prompt_token_count * 0.01875 + response.usage_metadata.candidates_token_count * 0.075) / (10**6)
  return response.text, cost

def extract_topic_info(response_xml):
  topic_start = response_xml.find("<topic>")
  topic_end = response_xml.find("</topic>")
  topic = response_xml[topic_start+7:topic_end]

  description_start = response_xml.find("<description>")
  description_end = response_xml.find("</description>")
  description = response_xml[description_start+13:description_end]

  summary_start = response_xml.find("<summary>")
  summary_end = response_xml.find("</summary>")
  summary = response_xml[summary_start+9:summary_end]

  return topic, summary, description

def delete_file_from_gcp(url_local):
    """Deletes a file from the bucket."""

    bucket_name = "zyke_bucket_gcp"
    blob_name = url_local

    # Initialize the client and get the bucket
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Delete the blob
    if blob.exists():
      blob.delete()

def upload_file_to_gcp(url_local):
    """Uploads a file to the bucket."""

    bucket_name = "zyke_bucket_gcp"
    source_file_name = url_local
    destination_blob_name = url_local
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    generation_match_precondition = 0

    # Check if the blob exists
    if blob.exists():
      delete_file_from_gcp(url_local)

    blob.upload_from_filename(source_file_name, if_generation_match=generation_match_precondition)

def post_description(url, content_type, user_id):

  system_prompt = ''
  prompt = ''
  caption = ''
  saved_content_path = []
  costs = 0
  
  current_file_path = os.path.abspath(__file__)
  current_dir_path = os.path.dirname(current_file_path)

  if content_type == "post" or content_type == "reel":
    urls = [url]
    out_list, cost = get_insta_post(urls, content_type)
    costs += cost

    out = out_list[0]
    links = out[0]
    caption = out[1]

    if type(links) == str:
      response = requests.get(links)
      url_local = f'{current_dir_path}/downloaded_video_{user_id}.mp4'
      saved_content_path = [url_local]

      with open(url_local, "wb") as f:
        f.write(response.content)

      url = f"gs://zyke_bucket_gcp/{url_local}"
      upload_file_to_gcp(url_local)

    else:
      for i, link in enumerate(links):
        response = requests.get(link)
        url = f'{current_dir_path}/saved_image_{i}.png'

        saved_content_path.append(url)

        with open(url, "wb") as f:
          f.write(response.content)
      url = saved_content_path

  if content_type == "reel":
    system_prompt = \
    """
      System Prompt:
      Provided to you in input is an instagram reel video with its caption.
      You have to analyse it for understanding its topic and getting its description.
      We will use the the topic and its description, as the base for repurposing the reel as a social media post, so generate your response accordingly.
      We will use your topic and description for generating ideas for the post.

      In your output, respond with:
      1. The topic of the reel in topic tags (<topic></topic>)
      2. A Highly detailed description of it. The description should contain what is happening in the video, what people say, what all is going on, the scenes, animations, background, motion, edits, etc. Use description tags (<description></description>)
      While making the analysis, do not just create a literal analysis of what is happening, also think about what is happening and add in your conclusions about what is happening along with the video's literal description, wherever it is required.
      Thus reply with the detailed video description, and add in your inputs wherever it is required.
      3. A short summary of what the reel is about and what happened in it. Use summary tags (<summary></summary>)

      Use caption of the post to take reference.

      Please follow this sample output format:
      `xml
      <topic>Topic</topic>
      <description>Description</description>
      <summary>Summary</summary>`
    """

    prompt = f"Caption: {caption}"

  elif content_type == "yt-video":
    system_prompt = \
    """
      System Prompt:
      Provided to you in input is a youtube video with its caption.
      You have to analyse it for understanding its topic and getting its description.
      We will use the the topic and its description, as the base for repurposing the video as a social media post, so generate your response accordingly.
      We will use your topic and description for generating ideas for the post.

      In your output, respond with:
      1. The topic of the video in topic tags (<topic></topic>)
      2. A Highly detailed description of it. The description should contain what is happening in the video, what people say, what all is going on, the scenes, animations, background, motion, edits, etc. Use description tags (<description></description>).
      While making the analysis, do not just create a literal analysis of what is happening, also think about what is happening and add in your conclusions about what is happening along with the video's literal description, wherever it is required.
      Thus reply with the detailed video description, and add in your inputs wherever it is required.
      3. A short summary of what the video is about and what happened in it. Use summary tags (<summary></summary>)

      Please follow this sample output format:
      `xml
      <topic>Topic</topic>
      <description>Description</description>
      <summary>Summary</summary>`
    """

    prompt = "The video is provided to you. please respond as instructed."

  elif content_type == "post":
    system_prompt = \
    """
      System Prompt:
      Provided to you is an instagram post with its caption.
      You have to analyse it for understanding its topic and getting its description.
      The post will have multiple images, analyse each image individually and the post as whole.
      Use its caption to get further insights about the post.
      We will use the the topic and its description, as the base for repurposing the existing instagram post, in a new post for another brand, so generate your response accordingly.
      We will use your topic and description for generating ideas for the post.

      In your output, respond with:
      1. The topic of the post in topic tags (<topic></topic>)
      2. A Highly detailed description of the post. The description should contain what the post is about, what information it contains, what is the messaging behind the post and what it is trying to convey. Use description tags (<description></description>).
      While making the analysis, do not just create a literal analysis of what it is about, also think about it yourself and add in your conclusions along with its literal description, wherever it is required.
      3. A short summary of what the post is about and what it is trying to convey. Use summary tags (<summary></summary>)

      Please follow this sample output format:
      `xml
      <topic>Topic</topic>
      <description>Description:

      Image 1:
      description

      Image 2:
      description

      ....

      General post description: ...
      </description>
      <summary>Summary</summary>`
    """

    prompt = f"Caption: {caption}"


  response, cost = describe_post(system_prompt, prompt, url, content_type)
  costs += cost
  topic, summary, description = extract_topic_info(response)

  for content_path in saved_content_path:
    os.remove(content_path)

  if content_type == "reel":
    delete_file_from_gcp(f'{current_dir_path}/downloaded_video_{user_id}.mp4')

  #   print(f"Topic: {topic}\n\nSummary: {summary}\n\nDescription: {description}")
  return topic, summary, description, costs

async def post_description_text(url, content_type):
  system_prompt = \
f'''System Prompt:
Provided to you in input is the content of a {content_type}.
You have to analyse it for understanding its topic and getting its description.
We will use the the topic and its description, as the base for repurposing the {content_type} for a social media post, so generate your response accordingly.
We will use your topic and description for generating ideas for the post.
You will also be provided with the url of the {content_type} as well, use it for better analysis, since you will be able to identify its source as well.

In your output, respond with:
1. The topic of the {content_type} in topic tags (<topic></topic>)
2. A Highly detailed description of the {content_type}. The description should contain what the {content_type} is about, what information it contains, what is the messaging behind it and what it is trying to convey. Use description tags (<description></description>).
While making the analysis, do not just create a literal analysis of what it is about, also think about it yourself and add in your conclusions along with its literal description, wherever it is required.
3. A short summary of what the {content_type} is about, what it is talking about. Use summary tags (<summary></summary>)

Please follow this sample output format:
`xml
<topic>Topic</topic>
<description>Description</description>
<summary>Summary</summary>`
'''
  text = await scrape_example(url)
  prompt = f'## Content Type: {content_type}\n## {content_type} url: {url}\n## {content_type} content:\n {text}\n\n{"-"*10}\n{"-"*10}\n\n'
  # print(system_prompt)
  # print(prompt)
  response, cost = describe_post(system_prompt, prompt, url = "", cont_type = content_type)
  topic, summary, description = extract_topic_info(response)
  # print("\n\n\n")
#   print(f"Topic: {topic}\n\nSummary: {summary}\n\nDescription: {description}")
  return topic, summary, description, cost

async def repurpose_link (url, content_type, user_id):
  topic, summary, description = '','',''
  if content_type == 'reel' or content_type == 'yt-video' or content_type == 'post':
    topic, summary, description, cost = post_description(url, content_type, user_id)
  if content_type == 'news-article' or content_type == 'blog' or content_type == 'website':
    topic, summary, description, cost = await post_description_text(url, content_type)
  return topic, summary, description, cost

# Configure logging for the repurpose_content function
logger = logging.getLogger(__name__)

@repurpose_bp.route('/repurpose_url', methods=['POST'])
@jwt_required()
def repurpose_content():
    user_id = get_jwt_identity()
    data = request.get_json()
    url = data.get('url')
    content_type = data.get('content_type')
    
    # print(url)

    if not url or not content_type:
        return jsonify({'error': 'url and content_type are required'}), 400

    try:
        # Fetch the user's current credits
        user_credits = get_user_credits(user_id)
        if user_credits is None:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if the user has enough credits
        if user_credits <= 0:
            return jsonify({'error': 'Insufficient credits to repurpose content.'}), 402

        # Call the asynchronous repurpose_link function to get the cost
        topic, summary, description, cost = asyncio.run(repurpose_link(url, content_type, user_id))
        
        # print(topic,summary,description)
        
        # Deduct credits and log the transaction
        deduction_description = f"Repurpose content for URL: {url}"
        success, error_msg = deduct_and_log_user_credits(user_id, cost, deduction_description, transaction_type="repurpose_content")
        
        if not success:
            # Return the specific error message captured
            return jsonify({"error": error_msg}), 500

        # Fetch updated credits
        updated_credits = get_user_credits(user_id)

        # Return the repurposed content along with the topic and description
        return jsonify({
            'topic': topic,
            'summary': summary,
            'description': description,
            'remainingCredits': updated_credits  # Updated credits after deduction
        }), 200

    except Exception as e:
        logger.error(f"Error in repurpose_content: {e}")
        return jsonify({'error': 'An internal server error occurred.'}), 500