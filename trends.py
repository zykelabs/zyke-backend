import asyncio
from flask import Blueprint, jsonify
import aiohttp
from pytrends.request import TrendReq
from config import Config
import requests

# Load environment variables (ensure that PERPLEXITY_TOKEN is set in config.py or env)
PERPLEXITY_TOKEN = Config.PERPLEXITY_TOKEN

# Create a blueprint for trends
trends_bp = Blueprint('trends', __name__)

# Asynchronous function to fetch trend information
async def fetch_trend_info_pplx(trend):
  url = "https://api.perplexity.ai/chat/completions"

  payload = {
      "model": "llama-3.1-sonar-huge-128k-online",
      "messages": [
          {
              "role": "system",
              "content": \
  '''Be precise and concise.
  Tell the user why a particular topic (a trend) is trending at the current moment.
  In your response include a short, one-liner trend description's summary and a longer comprehensive description about the whole trend.
  Your output should follow the following xml format compulsorily (with the tags):
  ```xml
  <summary>!Write your summary here</summary>
  <description>!Write your trend description here</description>```
  If you are unsure about why is a topic trending or there are multiple smaller reasons, then fetch all possible reasons and give a detailed explanation of each.
  Note: Some topic may be generally popular, but you have to tell me why it is trending now and not describe the topic in general.
  '''
          },
          {
              "role": "user",
              "content": f"Why is '{trend}' trending now? Use india as your trend location"
          }
      ],
      "max_tokens": 1024,
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
      "Authorization": f"Bearer {PERPLEXITY_TOKEN}",
      "Content-Type": "application/json"
  }

  try:
    async with aiohttp.ClientSession() as session:
      async with session.post(url, json=payload, headers=headers) as response:
        response = await response.json()
        cost = (response['usage']['prompt_tokens'] * 5 + response['usage']['completion_tokens'] * 5)/(10**6) + 5/1000
        return response['choices'][0]['message']['content'], cost
  except Exception as e:
    print(e)
    return "-1", 0

def extract_trend(trend_xml):
  summary_start = trend_xml.find("<summary>")
  summary_end = trend_xml.find("</summary>")
  summary = trend_xml[summary_start+9:summary_end]

  description_start = trend_xml.find("<description>")
  description_end = trend_xml.find("</description>")
  description = trend_xml[description_start+13:description_end]

  return summary, description

async def fetch_trends_new():
  #   return [["Linda Thorpe","yo i am tasmay tibs","rupam mahato is the goat"]], 0
  pytrends = TrendReq(hl='en-US', tz=330)

  trending_searches_series = pytrends.trending_searches(pn='india')

  costs = 0
  descriptions_async = []
  trending_searches = list(trending_searches_series[0])
  #   print(f"\n\n{trending_searches}\n\n")
  for i, trend in enumerate(trending_searches):
      descriptions_async.append(fetch_trend_info_pplx(trend))
  descriptions = await asyncio.gather(*descriptions_async)

  final_descriptions = []
  for i, trend in enumerate(descriptions):
      unfiltered_desc, cost = trend
      filtered_desc = extract_trend(unfiltered_desc)
      costs += cost
      final_descriptions.append([trending_searches[i],filtered_desc[0],filtered_desc[1]])

  return final_descriptions, costs

# Flask route to fetch trends
@trends_bp.route('/fetch_trends', methods=['GET'])
def get_trends():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        trends, costs = loop.run_until_complete(fetch_trends_new())
        loop.close()
        return jsonify({"trends": trends})
    except Exception as e:
        print(f"Error in fetching trends: {e}")
        return jsonify({"error": f"Failed to fetch trends {e}"}), 500
