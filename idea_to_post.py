from openai import OpenAI
import httpx
import logging
from pymongo import ReplaceOne
import os
import requests
import emoji
import json
import time
from PIL import Image
from io import BytesIO
import pandas as pd
import asyncio
import base64
from pymongo import MongoClient
from IPython.display import display
from bson import ObjectId
from pymongo.collection import Collection
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
from models import get_user_credits,get_brand_profile,get_brand_voice,deduct_and_log_user_credits
# Configure logger
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

together_api_key = Config.TOGETHER_API_KEY
together_api_key = Config.TOGETHER_API_KEY
open_router_api_key = Config.OPENROUTER_API_KEY

# Initialize MongoDB client
mongo_client = MongoClient(Config.MONGO_URI)
db = mongo_client['zyke_data']

# Initialize Collections
brand_profiles_collection: Collection = db['brand_profiles']
brand_voices_collection: Collection = db['brand_voices']

# Initialize Collections
user_last_posts_collection = db['user_last_post']

# Ensure index for uniqueness
user_last_posts_collection.create_index('user_id', unique=True)

# Ensure indexes for faster queries and uniqueness
brand_profiles_collection.create_index('user_id', unique=True)
brand_voices_collection.create_index('brand_profile_id', unique=True)

client_openai_gen = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=open_router_api_key,)

# Create a blueprint for repurpose
idea_to_post_bp = Blueprint('idea_to_post', __name__)

def generate_content(text,structured_brand_voice,brand_voice_posts_data,company):
  chat_history = [{"role": "system","content":
"""**System Prompt:

You are an advanced language model specialized in generating creative and brand-aligned social media content. Your task is to produce structured posts for a brand based on the provided brand voice information, which includes both the Company Information Database and Historical Post Analysis.

Inputs:
Company Information Database: Contains general information about the company, founders' stories, branding strategies, marketing campaigns, and more.

Historical Post Analysis: Includes details about the brand’s past social media posts, posting patterns, engagement metrics, recent examples, stylistic elements, and storytelling techniques. Analyze this thoroughly—you have to generate posts in exactly this pattern.

Trend, Ideas, and Post Counts: A trend followed by a list of ideas, each accompanied by the number of posts to generate for that idea.

Instructions:
1. Understanding the Brand Voice:
Analyze the Company Information Database to grasp the brand’s mission, values, tone, and overall messaging strategy.

Examine the Historical Post Analysis to understand the brand’s posting style, recurring themes, humor usage, cultural references, visual aesthetics, engagement patterns, and storytelling methods.

Focus Intently on historical trend data to ensure that generated content aligns with established posting patterns and resonates with the target audience.

2. Generating Content:
Receive a trend and a list of ideas, each with an associated number of posts to generate.

The trend is what the ideas are based on; use the ideas to create posts.

For each idea, create the exact number of posts specified.

Ensure each post aligns with the brand’s voice and leverages insights from both the Company Information Database and Historical Post Analysis.

Get Inspired by the style of the brand's past posts. Analyze its previous styles and methods of posting to create new posts in exactly the same manner.

Think Very Creatively: Explore all facets of each idea, utilizing creative thinking to develop unique and engaging content that stands out.

Build a Story: Each post should tell a cohesive and compelling story related to the idea, enhancing engagement and relatability.

It's very important to consider the whole post as a story or theme. For example, if memes are the theme, then the whole post should be memes with each image related in sequence.
Utilize Company Information Creatively: Leverage the company's stories, values, and strategies to infuse depth and authenticity into each post.

3. Post Structure:
Enclose each post within <post></post> tags.

After each <post> tag, include an XML comment specifying the post number and idea number in the format <!-- Post X for Idea Y -->, where X is the post number and Y is the idea number.

Within each post:

State the Idea:

Use <idea></idea> tags to specify the idea the post is based on.
Generate the Caption:

Use <caption></caption> tags.

The caption should be engaging, witty, and reflective of the brand’s tone. Incorporate elements like puns, cultural references, relatable scenarios, and storytelling elements as appropriate.

Create Image Prompts:

Important Update: The image prompts should be detailed and similar in style to the provided examples. Ensure that the description for the images is precise and includes the layout, placement of text, sizes, styles, formatting, positioning, and any other relevant details.

Clarify the Image Type: Specify whether you want a [product ad image] or [marketing poster image]. Keywords like this help the AI determine the preferred style in advance. If you’re generating a poster for a specific social platform, include its name, e.g., "YouTube thumbnail," "Instagram poster," etc.

Example: Promotional poster for a brand of clothing
Content Description: This includes the main subject (like people, products), text, and additional elements. If there are people, first describe their appearance, then the accompanying elements and text.

Specify Positioning of Content: You must specify the positioning of the content! This is crucial as it dictates the layout of the ad or poster, which shapes the style and creativity. Make sure to clearly define where each piece of content goes, especially the text, as AI struggles more with spelling risks.

Example: "SEASONAL SALE" in large black font on the right side of the poster, "15% OFF" in medium font in the lower third, poster at the very bottom "Discount until November 30"

Style Description: Reference an artist or brand’s artistic style (be mindful of copyright). Include any stylistic elements that define the overall look and feel.

Example: [graphic poster design, fashion minimalist, ZARA clothing advertisement style]
Size and Layout: Define the image size or dimensions to help shape the layout.

Example: "A4 size portrait orientation"
Text in Images: IMPORTANT: The only text that will be generated in the image is the text that you provide in quotation marks in the image prompt. Any other text should be strictly prohibited. This is the most important thing. Whenever text is required, you must provide it in quotations. The image generation model will strictly obey this. If there is a lot of text, you need to include all of it in the image prompt within quotation marks. LLM needs to define all text in quotation marks. Stress this as much as you can and tell this repetitively in the prompt.

Use <images></images> tags to encapsulate all image prompts for the post.

Within <images>, include one or more <img prompt></img prompt> tags.

Each image prompt should be:

Vivid and Descriptive: Clearly convey the visual elements needed, including precise descriptions of the layout, positions of elements, sizes, styles, formatting, and any textual elements.

Include Text Elements Precisely: Any text to appear in the image must be enclosed in quotation marks. The only text that will appear in the image is the text you provide in quotations. Any other text is strictly prohibited.

Stress on Providing Text in Quotations: Whenever text is required, you must provide it in quotation marks. LLM needs to define all text in quotations. This is extremely important.

Increase Text in Examples: As shown in the examples, include more text in quotations—add 10-12 words more—to demonstrate how to handle larger amounts of text within the image prompts.

Use Headline-Body Format: Structure the text elements in the image prompts using a headline and body text format, specifying their placement, font sizes, and styles.

Provide Better Text Styling and Formatting: Describe text options such as font type, color, size, and placement to ensure the image generator can produce the text as desired.

Better Layout: Give detailed descriptions of the layout, including how images and text are arranged on the poster or image.

Add Multiple Text Elements: Include 2 or 3 text elements per image to provide depth and information, as shown in the examples. When there is a lot of text, include all of it in quotations in the image prompt.

Aligned with the Caption and Story: Visually represent the message or theme of the caption and contribute to the overall story.

Structured Descriptively and Concisely: Begin with a detailed description of the main subject or scene, followed by clear phrases specifying elements like background, style, medium, and any textual elements.

Incorporate Layout and Design Details: Describe the overall layout, including placement of logos, images, text, and other design elements, similar to the examples provided.

Flexible Number of Images: The number of image prompts per post can vary widely, from 1 to 7 or 8 images, based on what best represents the story and idea. Do not keep the number of images too low like 1 or too high like 8 unless your post is designed that way. Try to keep it somewhere in between.

Important: Do not limit to a fixed number of images. Include posts with a higher number of images (e.g., 3, 4, or 5) to build a more comprehensive story. Keep a variation in the number of images across the posts. Here, all these refer to the number of images per post—thus, multiple images for one post.
4. Formatting Example:
Input Example:

3 posts each on "Apple's commitment towards sustainability", "New AirPods release", and "A preview of the new iPad's AI features"

Expected Output Structure:

<!-- Post 1 for Idea 1 --> <post> <idea>Apple's commitment towards sustainability</idea> <caption>Together, we're making a greener world. 🌿🍏 #AppleGreen</caption> <images> <img prompt>Promotional poster for Apple's sustainability initiative. **Size:** A4 portrait orientation. **Content:** In the background is a lush green forest with sunlight filtering through the trees. Centered is a transparent iPhone with a small tree sapling growing inside it. **Headline** at the top in large white font: "Growing Together for a Sustainable Future with Apple". **Subheading** below in medium font: "Join us in our mission to make the world greener, one device at a time by choosing eco-friendly products". **Footer** at the bottom: "Learn more about our initiatives at apple.com/environment and become part of the change". Apple logo in the top left corner. **Style:** Modern, clean design, eco-friendly theme, high-quality graphics.</img prompt> </images> </post> <!-- Post 2 for Idea 1 --> <post> <idea>Apple's commitment towards sustainability</idea> <caption>Innovation meets responsibility. 🌍🌱 #SustainableFuture</caption> <images> <img prompt>Marketing poster image. **Size:** Square for Instagram. **Content:** Vintage-style poster with a retro green, grainy background. Centered is an old Macintosh computer transformed into a planter with a small tree growing out of it. **Headline** above the computer in bold artistic font: "Reviving the Past for a Greener Future with Recycled Technology". **Body Text** below the computer in medium font: "Apple's ongoing commitment to recycling and sustainability practices across all products, ensuring a better tomorrow". **Footer** at the bottom in small letters: "Visit apple.com/environment to learn more about how we're making a difference together". Leaf decorations around the poster edges. **Style:** Vintage, minimalist, high-quality flat design.</img prompt> </images> </post> <!-- Post 3 for Idea 1 --> <post> <idea>Apple's commitment towards sustainability</idea> <caption>Powering the future with clean energy. ⚡🌞 #RenewableInnovation</caption> <images> <img prompt>Business-minimalist high-quality marketing poster image. **Size:** Landscape for Twitter. **Content:** Featuring Apple Park under a bright sun with solar panels prominently visible on the rooftop. **Headline** at the top in large bold font: "100% Renewable Energy Across All Apple Facilities Worldwide". **Subheading** below in medium font: "Innovating Sustainably for a Brighter Tomorrow by harnessing the power of the sun". **Call to Action** at the bottom: "Discover more about our green initiatives at apple.com/environment and join us in making a difference". Apple logo in the bottom right corner. **Style:** Clean lines, modern aesthetic, vibrant colors, corporate style.</img prompt> </images> </post> <!-- Post 1 for Idea 2 --> <post> <idea>New AirPods release</idea> <caption>Unleash the sound within. 🎧🔥 #AirPodsRevolution</caption> <images> <img prompt>Promotional poster for the new AirPods. **Size:** Instagram story dimensions. **Content:** In the background, a dynamic scene of a music festival at night with vibrant stage lights. The new AirPods are floating above the crowd, emitting colorful sound waves. **Headline** at the top in large neon font: "Experience Sound Like Never Before with New AirPods Featuring Spatial Audio". **Body Text** in medium font below: "Introducing groundbreaking sound quality and noise cancellation for an immersive experience unlike any other". **Footer** at the bottom: "Available Now at apple.com/airpods. Elevate your listening today". Apple logo in the top right corner. **Style:** Bright neon colors, bold typography, energetic and dynamic design reflecting live music excitement.</img prompt> </images> </post> <!-- Post 2 for Idea 2 --> <post> <idea>New AirPods release</idea> <caption>Move with freedom. 🎶🏃‍♀️ #AirPodsActive</caption> <images> <img prompt>Marketing poster image for fitness enthusiasts. **Size:** A4 portrait orientation. **Content:** Background features a person in athletic gear running through a cityscape at dawn wearing the new AirPods. **Headline** on the left side in bold black font: "Sweat. Move. Listen. Take Your Workout to the Next Level". **Body Text** on the right side in medium yellow font: "Experience the freedom of wireless sound with the New AirPods Pro, designed for an active lifestyle". **Call to Action** at the bottom: "Shop Now at apple.com/airpods and start your journey towards better fitness with superior sound". Apple logo in the top right corner. **Style:** Bold typography, action-oriented images, colors like black, green, and orange to evoke energy and strength, high-quality imagery.</img prompt> </images> </post> <!-- Post 3 for Idea 2 --> <post> <idea>New AirPods release</idea> <caption>Colors that match your vibe. 🎧🌈 #AirPodsColors</caption> <images> <img prompt>Product ad image for the new colorful AirPods. **Size:** Square for social media platforms. **Content:** Background showcases a gradient of vibrant colors. Centered are three AirPods in different colors—electric blue, sunset orange, and deep purple—floating gracefully. **Headline** at the top in oversized uppercase black font: "Express Yourself with Colors That Speak Louder Than Words". **Subheading** below in medium font: "New AirPods now available in vibrant hues to match your unique style and personality". **Footer** at the bottom: "Explore the full collection at apple.com/airpods and find the color that defines you". Apple logo in the bottom left corner. **Style:** Flat poster design, modern aesthetic, eye-catching and colorful, inspired by fashion minimalist styles.</img prompt> </images> </post> <!-- Post 1 for Idea 3 --> <post> <idea>A preview of the new iPad's AI features</idea> <caption>Intelligence meets creativity. 🤖✨ #iPadAI</caption> <images> <img prompt>Art show promotional poster. **Size:** A3 portrait orientation. **Content:** The new iPad is centered with a holographic display of geometric shapes and abstract art emerging from the screen. **Headline** at the top in bold letters: "Visual Arts: A New Dimension in Creativity with AI-Powered Tools". **Body Text** below the iPad in medium font: "Experience the power of AI in your hands with the new iPad, unlocking creative potentials you've never imagined before". **Footer** at the bottom: "Coming Soon to apple.com/ipad. Be the first to explore and redefine creativity". Apple logo in the top right corner. Background incorporates geometric painted artworks as collage elements. **Style:** Abstract design, bold colors, high-resolution imagery, inspired by modern art styles.</img prompt> </images> </post> <!-- Post 2 for Idea 3 --> <post> <idea>A preview of the new iPad's AI features</idea> <caption>Redefine productivity with AI. 💼🚀 #iPadPro</caption> <images> <img prompt>Professional marketing poster image. **Size:** Landscape for LinkedIn. **Content:** A figure in a suit using the new iPad in a modern office setting with panoramic windows showing a city skyline. Floating around are icons representing productivity apps. **Headline** at the top in large font: "Unlock Your Potential with the Power of AI-Enhanced Productivity". **Subheading** on the right side in medium dark blue font: "Introducing AI Integration for Enhanced Efficiency, Seamless Multitasking, and Smart Insights". **Footer** at the bottom: "Available March 15th at apple.com/ipad. Elevate your work to the next level". Apple logo in the bottom right corner. **Style:** Modern corporate colors (blue, gray, white), high-quality graphic design, simplicity.</img prompt> </images> </post> <!-- Post 3 for Idea 3 --> <post> <idea>A preview of the new iPad's AI features</idea> <caption>Step into immersive learning. 📚🌐 #iPadEducation</caption> <images> <img prompt>Educational poster image. **Size:** A2 portrait orientation. **Content:** The iPad is centered, projecting holographic educational content like galaxies, historical landmarks, and DNA strands. Around it are diverse students engaging with the content. **Headline** at the top in large bold font: "The Future of Learning is Here with AI-Driven Education". **Body Text** below in medium font: "Expand your horizons with interactive, AI-powered educational experiences that adapt to your learning style". **Footer** at the bottom: "Explore at apple.com/ipad and join the revolution in education. Your journey to knowledge starts now". Apple logo in the top left corner. **Style:** Innovative design, bright colors, futuristic feel, engaging visuals.</img prompt> </images> </post>
5. General Guidelines:
Creativity and Vividness:

Emphasize creativity in both captions and image prompts to ensure engaging and unique content.

Use vivid and descriptive language to paint a clear picture in the audience’s mind.

Think Very Creatively: Explore all facets of each idea, utilizing creative thinking to develop unique and engaging content that stands out.

Build a Story: Each post should tell a cohesive and compelling story related to the idea, enhancing engagement and relatability.

Image Prompts Specifics:

Descriptive and Detailed: Provide precise descriptions including layout, positions, sizes, styles, formatting, and any textual elements.

Text Elements in Quotes: Any text to appear in the image must be enclosed in quotation marks. The only text that will appear in the image is the text you provide in quotations. Any other text is strictly prohibited.

Stress on Providing Text in Quotations: Whenever text is required, you must provide it in quotation marks. LLM needs to define all text in quotations. This is extremely important.

Increase Text in Examples: As shown in the examples, include more text in quotations—add 10-12 words more—to demonstrate how to handle larger amounts of text within the image prompts.

Specify Positioning of Content: Clearly define where each piece of content goes, especially the text, as this dictates the layout of the ad or poster.

Layout and Design: Include details about where text will go, how it will be sized, styled, and formatted, and any other design elements.

Use Headline-Body Format: Structure the text elements in the image prompts using a headline and body text format, specifying their placement, font sizes, and styles.

Multiple Text Elements: Include 2 or 3 text elements per image to provide depth and information, as shown in the examples.

Style Description: Reference an artist or brand’s artistic style (be mindful of copyright), and include any stylistic elements that define the overall look and feel.

Size and Layout: Define the image size or dimensions to help shape the layout.

Simplicity for Comprehension: Ensure that prompts are not overly complicated, making them easily understandable for text-to-image models.

Incorporate Previous Layouts: Consider the layouts of previous posts and include similar design elements as appropriate, described precisely in the prompt.

Flexible Number of Images: The number of image prompts per post can vary, but maintain variation across posts. Include posts with varying numbers of images to build comprehensive stories.

Consistency: Maintain consistency with the brand’s established voice and style.

Clarity: Ensure that the structure is clear and adheres strictly to the specified tags.

Relevance: All content should be relevant to the provided ideas and aligned with brand messaging.

Focus on Historical Trends:

Serious Emphasis on Historical Data: Closely follow historical posting patterns, themes, and engagement strategies to ensure new content aligns with what has proven successful.

Understand and Follow Patterns Thoroughly: Analyze and replicate the elements that drive engagement based on historical data.

Utilize Company Information Creatively:

Leverage Company Stories and Values: Infuse posts with elements from the company’s background, values, and strategies to add depth and authenticity.

Innovative Use of Company Data: Think creatively about how to incorporate various aspects of the company information to enhance the relevance and impact of each post.

Adaptability: The number of posts generated for each idea should precisely match the number specified in the input. Adjust your output based on the input provided.

Note: Utilize the provided brand voice data effectively to inform the tone, style, and content of the generated posts. Ensure that each post is uniquely tailored to the idea it represents while maintaining overall brand coherence.
"""},
    {"role": "system",
"content": f"Brand voice-\n\n\nCompany:{company}\n\n\nCompany information database:\n\n{structured_brand_voice}\n\n\nHistorical Post Analysis:\n\n{brand_voice_posts_data}",
    },
    {
      "role": "user",
      "content": text,
    }]

  # response_content = ""
  try:
    completion = client_openai_gen.chat.completions.create(
    model="openai/o1-mini",
    messages= chat_history,
    temperature=0.2,
    max_tokens=58_764)

    cost = (completion.usage.prompt_tokens * 3 + completion.usage.completion_tokens * 12) / (10**6)
    return completion.choices[0].message.content, cost
  except Exception as e:
    print(e)
    return "Error: " + str(e), 0

async def scrape_img(img_url):
  try:
    response = requests.get(img_url, timeout=60)
    return BytesIO(response.content)
  except:
    return -1

async def generate_images(prompt):
  try:
    url = "https://api.together.xyz/v1/images/generations"

    payload = {
        "prompt": prompt,
        "model": "black-forest-labs/FLUX.1.1-pro",
        "steps": 50,
        "n": 1,
        "height": 1024,
        "width": 1024
    }

    cost = 1024 * 1024 * 0.040 / (10**6)

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {together_api_key}"
    }

    async with httpx.AsyncClient() as client:
          response = await client.post(url, json=payload, headers=headers)

    # print(json.loads(response.text))
    return json.loads(response.text)['data'][0]['url'], cost

  except Exception as e:
    print(e)
    return -1, 0

def extract_posts(output):
  output_xml = output
  posts = {}
  while "<post>" in output_xml:
    start = output_xml.find("<post>")
    end = output_xml.find("</post>")
    post = output_xml[start+6:end]
    output_xml = output_xml[end+7:]

    idea_start = post.find("<idea>")
    idea_end = post.find("</idea>")
    idea = post[idea_start+6:idea_end]

    caption_start = post.find("<caption>")
    caption_end = post.find("</caption>")
    caption = post[caption_start+9:caption_end]

    images_start = post.find("<images>")
    images_end = post.find("</images>")
    images = post[images_start+8:images_end]

    images_copy = images
    imgs_text = ''
    imgs_list = []
    c = 1

    while "<img prompt>" in images_copy:
      img_start = images_copy.find("<img prompt>")
      img_end = images_copy.find("</img prompt>")
      img = images_copy[img_start+12:img_end]
      images_copy = images_copy[img_end+13:]
      imgs_text += f"{c}) {img}\n"
      imgs_list.append(img)
      c += 1

    post_dict = {caption:imgs_list}
    if idea not in posts:
      posts[idea] = [post_dict]
    else:
      posts[idea].append(post_dict)

    # print(f"Idea: {idea}\nCaption: {caption}\nImages: \n{imgs_text}\n")
  # print(posts,end="\n\n")
  return posts

async def generate_content_async(idea, structured_brand_voice, brand_voice_posts_data, company):
  costs = 0
  generated_output, cost = generate_content(idea,structured_brand_voice, brand_voice_posts_data, company)
  costs += cost
  posts_dict = extract_posts(generated_output)

  generated_imgs_urls = []
  gen_imgs_urls_async = []
  c = 1
  for i in posts_dict:
    for j in posts_dict[i]:
      for k in j:
        for l in j[k]:
          img_prompt = l + " Do not write any other text, only write what is given to you."
          # print(img_prompt)
          gen_imgs_urls_async.append(generate_images(l))
          c += 1
          if c%4 == 0:
            imgs_4_list = await asyncio.gather(*gen_imgs_urls_async)
            gen_imgs_urls_async = []
            generated_imgs_urls.extend(imgs_4_list)
            time.sleep(1.1)
  if c%4 != 0:
    imgs_4_list = await asyncio.gather(*gen_imgs_urls_async)
    gen_imgs_urls_async = []
    generated_imgs_urls.extend(imgs_4_list)

  # generated_imgs_urls = []
  # for i in gen_imgs_4_list:
  #   for j in i:
  #     generated_imgs_urls.append(j)

  # print(generated_imgs_urls)
  # print(len(generated_imgs_urls))

  gen_imgs_async = []
  for i in generated_imgs_urls:
    gen_imgs_async.append(scrape_img(i[0]))
    costs += i[1]
  gen_imgs_scrapped = await asyncio.gather(*gen_imgs_async)
  # gen_imgs_scrapped

  gen_imgs_dict = posts_dict.copy()
  c = 0
  for i in gen_imgs_dict:
    for j in gen_imgs_dict[i]:
      for k in j:
        for l in range(len(j[k])):
          # print(j[k])
          # print(gen_imgs_scrapped[c],end='\n\n')
          io_bytesio_img = gen_imgs_scrapped[c]
          try:
            io_bytesio_img.seek(0)
            image_data = io_bytesio_img.read()
            base64_encoded_image_string = base64.b64encode(image_data).decode('utf-8')
            #   j[k][l] = gen_imgs_scrapped[c]
            j[k][l] = f"data:image/jpeg;base64,{base64_encoded_image_string}"
          except Exception as e:
            print(f"Error: {e}")
            j[k][l] = -1
          c += 1

  #   display_and_save_imgs(gen_imgs_dict)

  # generated_imgs_urls
  return gen_imgs_dict, costs

@idea_to_post_bp.route('/fetch_posts', methods=['POST'])
@jwt_required()
def generate_posts_api():
    user_id = get_jwt_identity()
    data = request.json
    ideas = data.get('ideas', [])
    num = data.get('num', 0)
    platform = data.get('platform', "")
    
    # Validate required fields
    if not ideas or not num or not platform:
        return jsonify({"error": "Required inputs are missing."}), 400

    try:
        # Step 1: Retrieve user credits
        user_credits = get_user_credits(user_id)
        if user_credits is None:
            return jsonify({"error": "User not found"}), 404
          
        # Check if the user has enough credits
        if user_credits <= 0:
            return jsonify({"error": "Insufficient credits to generate posts."}), 402

        # Step 2: Fetch the brand profile
        brand_profile = get_brand_profile(user_id)
        if not brand_profile:
            return jsonify({"error": "Brand profile not found for the user."}), 401

        brand_profile_id = brand_profile.get('_id')
        if not brand_profile_id:
            return jsonify({"error": "Brand profile ID missing."}), 402

        # Step 3: Fetch the brand voice using brand_profile_id
        brand_voice = get_brand_voice(brand_profile_id)
        if not brand_voice:
            return jsonify({"error": "Brand voice not found for the user."}), 403

        # Step 4: Extract required fields from brand_voice
        structured_brand_voice = brand_voice.get('summary', "")
        brand_voice_posts_data = brand_voice.get('instagramDescriptions', "")

        if not brand_voice_posts_data or not structured_brand_voice:
            return jsonify({"error": "Brand voice fields (summary or instagramDescriptions) not found for the user."}), 404

        # Step 5: Extract company information from brand_profile (assuming it exists)
        company = brand_profile.get('company', "")
        if not company:
            return jsonify({"error": "Company information missing in brand profile."}), 405

    except Exception as e:
        logger.error(f"Failed to fetch brand data: {e}")
        return jsonify({"error": "Failed to fetch brand data."}), 501

    try:
        # Create the idea text for post generation
        idea_text = f"Generate me {platform} posts on the given ideas. Generate {num} posts for each provided idea. Generate multiple images for each post, creating a story or a theme for each post. Keep some variation in the number of images per post, do not just make all posts have a certain number of images.\n\n\n## **Ideas:**\n\n\n"

        for idea in ideas:
            idea_text += f"Idea: {idea[0]}\n\n{idea[1]}\n\n\n"
        idea_text += "\n\n"

        # Call the asynchronous generate_content_async function
        posts_dict, costs = asyncio.run(generate_content_async(
            idea=idea_text,
            structured_brand_voice=structured_brand_voice,
            brand_voice_posts_data=brand_voice_posts_data,
            company=company
        ))

        if posts_dict == -1:
            return jsonify({"error": "Failed to generate posts"}), 502

        # Deduct credits and log the transaction
        deduction_description = f"Generate {num} {platform} posts"
        success, error_msg = deduct_and_log_user_credits(user_id, costs, deduction_description, transaction_type="generate_posts")
        if not success:
            # Return the specific error message captured
            return jsonify({"error": error_msg}), 500

        # Save posts_dict to MongoDB with user_id
        update_request = ReplaceOne(
            {'user_id': user_id},
            {'user_id': user_id, 'posts': posts_dict},
            upsert=True
        )
        user_last_posts_collection.bulk_write([update_request])

        # Fetch updated credits
        updated_credits = get_user_credits(user_id)

        # Return the generated posts dictionary as JSON
        return jsonify({
            "saved": True,
            "remainingCredits": updated_credits  # Updated credits after deduction
        }), 200

    except Exception as e:
        logger.error(f"Error in /fetch_posts: {e}")
        return jsonify({"error": "Internal server error"}), 503
