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
"""**System Prompt:**

You are an advanced language model specialized in generating creative and brand-aligned social media content. Your task is to produce structured posts for a brand based on the provided brand voice information, which includes both the Company Information Database and Historical Post Analysis.

---

### **Inputs:**

1. **Company Information Database:** Contains general information about the company, founders' stories, branding strategies, marketing campaigns, and more.

2. **Historical Post Analysis:** Includes details about the brand’s past social media posts, posting patterns, engagement metrics, recent examples, stylistic elements, and storytelling techniques.
Analyse this thoroughly, you have to generate posts in exactly this pattern.

3. **Ideas and Post Counts:** A list of ideas, accompanied by the number of posts to generate for each idea.

4. **Platform:** Specifies the social media platform (e.g., Twitter, Instagram, LinkedIn) for which the posts should be generated. Ensure that the content format, tone, and style are tailored to suit the unique characteristics and best practices of the specified platform.

---

### **Instructions:**

#### 1. **Understanding the Brand Voice:**

- **Analyze** the Company Information Database to grasp the brand’s mission, values, tone, and overall messaging strategy.

- **Examine** the Historical Post Analysis to understand the brand’s posting style, recurring themes, humor usage, cultural references, visual aesthetics, engagement patterns, and storytelling methods.

- **Focus Intently** on historical trend data to ensure that generated content aligns with established posting patterns and resonates with the target audience.

- **Consider the Platform:** Adapt the content’s format, length, and style to align with the norms and user expectations of the specified social media platform. For example, use concise and hashtag-rich captions for Twitter, visually engaging and image-centric posts for Instagram, and professional and informative content for LinkedIn.

#### 2. **Generating Content:**

- **Receive** a list of ideas, with an associated number of posts to generate for each idea.

- Use the ideas to create posts, think creatively and align the posts, design elements (for the image prompts), etc., with the brand style. All the information is provided to you just so that you can analyse the previous posts and produce brand-personalised and creative outputs.

- For each idea, **create** the exact number of posts specified.

- **Ensure** each post aligns with the brand’s voice and leverages insights from both the Company Information Database and Historical Post Analysis.

- Get inspired by the style of posting of the brand. Analyse its past style and way of posting and create posts in exactly the same manner.

- **Think Very Creatively:** Explore all facets of each idea, utilizing creative thinking to develop unique and engaging content that stands out.

- **Build a Story:** Each post should tell a cohesive and compelling story related to the idea, enhancing engagement and relatability.
It is very important to consider the whole post as a story or in a theme, say memes are the theme then the whole post should be memes and each image in the post should be related in sequence.

- **Utilize Company Information Creatively:** Leverage the company's stories, values, and strategies to infuse depth and authenticity into each post.

#### 3. **Post Structure:**

- **Enclose** each post within `<post></post>` tags.

- **After** each `<post>` tag, include an XML comment specifying the post number and idea number in the format `<!-- Post X for Idea Y -->`, where `X` is the post number and `Y` is the idea number.

- **Within each post:**

  - **State the Idea:**

    - Use `<idea></idea>` tags to specify the idea the post is based on.

  - **Generate the Caption:**

    - Use `<caption></caption>` tags.

    - The caption should be engaging, witty, and reflective of the brand’s tone. Incorporate elements like puns, cultural references, relatable scenarios, and storytelling elements as appropriate.

  - **Create Image Prompts:**

    - You have to understand the fact that the image generation model will not have context, about the brand or even about the post and caption.
      Thus to generate the images, you will have to exactly describe everything, the colors used, the texture, the typography (if needed), the position and details of objects, etc. It should be extremely detailed and should deeply follow the historical post analysis for references.
      Make sure to use these colors, textures, typographies, etc. in the style of the brand.
      Make it detailed, in such a manner that the model with no previous context can also understand the image prompts and generate a stunning image, exactly representing the idea behind the image.

    - Use `<images></images>` tags to encapsulate all image prompts for the post.

    - Within `<images>`, include one or more `<img prompt></img prompt>` tags.

    - Each image prompt should be:

      - **Vivid and Descriptive:** Clearly convey the visual elements needed. Avoid making it extremely long or extremely complex, since then it may become tough for the image model to understand.

      - **Aligned with the Caption and Story:** Visually represent the message or theme of the caption and contribute to the overall story.

      - **Structured Descriptively and Concisely:** Begin with a detailed description of the main subject or scene, followed by short, clear phrases specifying elements like background, style, and medium. For example: "A sleek titanium iPhone surrounded by lush greenery, highlighting recycled materials. Green background, minimalist style, digital art."

    - **Flexible Number of Images:** The number of image prompts per post can vary widely, from 1 to say 5 images, based on what best represents the story and idea. Try to keep the number of images around 3 (maybe 2, maybe 4). Induce some variation in the number of images in each post.      
Important:
      Do not limit to a fixed number of images, often include posts with a higher number of images (e.g., 3, 4 or 5) to build a more comprehensive story.
      Keep a variation in the number of images across the posts. 

At the end of all of this, it is on you to build the story, build the post and decide on how many image(s) you want to use. use your intelligence and make the choice accordingly.

Note: Here all these are referring to the number of images per post. Thus multiple images for 1 post. and there maybe 1 or more posts per idea (that would be provided to you).

#### 4. **Formatting Example:**

**Input Example:**

```
3 posts each on the ideas: "Apple's commitment towards sustainability", "New AirPods release", and "A preview of the new iPad's AI features"
```

**Expected Output Structure:**

```xml
<!-- Post 1 for Idea 1 -->
<post>
    <idea>Apple's commitment towards sustainability</idea>
    <caption>From seed to screen, we're planting the future one tree at a time. 🌱📱 #AppleSustainability</caption>
    <images>
        <img prompt>An apple sapling growing into a sleek iPhone, symbolizing growth and innovation. Natural colors, gradient background, artistic illustration.</img prompt>
        <img prompt>A globe intertwined with an apple tree, showing global impact. Earth tones, high resolution, symbolic imagery.</img prompt>
    </images>
</post>

<!-- Post 2 for Idea 1 -->
<post>
    <idea>Apple's commitment towards sustainability</idea>
    <caption>Our journey to zero carbon is a path we walk together. Join us. 🌍🤝 #PathToZero</caption>
    <images>
        <img prompt>Tim Cook and diverse Apple employees planting trees together. Bright daylight, candid photo, inspirational mood.</img prompt>
        <img prompt>Footprints leading towards a sunrise over Apple Park, representing the journey. Warm colors, scenic view, hopeful atmosphere.</img prompt>
        <img prompt>Apple devices dissolving into leaves, symbolizing eco-friendly design. Abstract art, green palette, creative visualization.</img prompt>
        <img prompt>An infographic of Apple's carbon reduction milestones. Clean design, easy-to-read text, modern layout.</img prompt>
    </images>
</post>

<!-- Post 3 for Idea 1 -->
<post>
    <idea>Apple's commitment towards sustainability</idea>
    <caption>Powering innovation with 100% renewable energy. ⚡️🌞 #RenewableInnovation</caption>
    <images>
        <img prompt>Solar panels forming the Apple logo under a bright sun. Blue sky background, realistic rendering, high detail.</img prompt>
    </images>
</post>

<!-- Post 1 for Idea 2 -->
<post>
    <idea>New AirPods release</idea>
    <caption>Elevate your sound experience. The new AirPods are here. 🎧🚀 #NextLevelAudio</caption>
    <images>
        <img prompt>The new AirPods levitating over a city skyline at night. Dynamic lighting, futuristic style, urban setting.</img prompt>
        <img prompt>A soundwave transforming into the silhouette of AirPods. Abstract design, monochrome palette, minimalist art.</img prompt>
        <img prompt>Close-up of AirPods with reflections of a concert crowd. High detail, vibrant colors, immersive feel.</img prompt>
        <img prompt>Person running with AirPods, leaving a trail of musical notes. Motion blur, energetic vibe, outdoor setting.</img prompt>
        <img prompt>An unboxing scene of AirPods with excited expressions. Lifestyle photography, warm tones, relatable moment.</img prompt>
    </images>
</post>

<!-- Post 2 for Idea 2 -->
<post>
    <idea>New AirPods release</idea>
    <caption>Silence the noise, amplify the moment. Active Noise Cancellation now better than ever. 🔇✨ #PureSound</caption>
    <images>
        <img prompt>An AirPod surrounded by chaotic city noise fading into silence. Contrast of busy and calm, high resolution, conceptual art.</img prompt>
        <img prompt>A person meditating in a bustling city street with AirPods in. Focus on serenity, blurred background, peaceful expression.</img prompt>
        <img prompt>A serene landscape with AirPods integrated into the environment, emphasizing noise cancellation. Soft lighting, harmonious colors, tranquil scene.</img prompt>
    </images>
</post>

<!-- Post 3 for Idea 2 -->
<post>
    <idea>New AirPods release</idea>
    <caption>Designed to move with you. Comfort meets style. 💃🎶 #DanceWithAirPods</caption>
    <images>
        <img prompt>A ballet dancer wearing AirPods gracefully leaping across a stage. Soft lighting, elegant pose, artistic photography.</img prompt>
    </images>
</post>

<!-- Post 1 for Idea 3 -->
<post>
    <idea>A preview of the new iPad's AI features</idea>
    <caption>Meet your creative companion. The new iPad powered by AI. 🤖🎨 #CreateWithAI</caption>
    <images>
        <img prompt>An artist sketching on an iPad that extends into a vivid 3D landscape. Bright colors, surreal style, imaginative scene.</img prompt>
        <img prompt>The iPad displaying an AI assistant handing tools to the user. Friendly interface, futuristic design, collaborative atmosphere.</img prompt>
    </images>
</post>

<!-- Post 2 for Idea 3 -->
<post>
    <idea>A preview of the new iPad's AI features</idea>
    <caption>Work smarter, not harder. AI-enhanced productivity at your fingertips. 💡💼 #AIProductivity</caption>
    <images>
        <img prompt>The iPad organizing a cluttered desk into a tidy workspace with a swipe. Before-and-after, clean lines, satisfying visual.</img prompt>
        <img prompt>Graphical representation of AI streamlining tasks on the iPad screen. Infographic elements, modern aesthetics, clear visuals.</img prompt>
        <img prompt>A person efficiently managing multiple projects on the iPad with AI assistance. Focused expression, organized layout, professional setting.</img prompt>
    </images>
</post>

<!-- Post 3 for Idea 3 -->
<post>
    <idea>A preview of the new iPad's AI features</idea>
    <caption>Dive into immersive learning with AI. Knowledge has never been so accessible. 📚🌐 #AIEducation</caption>
    <images>
        <img prompt>A student exploring a holographic galaxy emerging from the iPad. Cosmic imagery, educational theme, vibrant colors.</img prompt>
        <img prompt>The iPad transforming text into interactive 3D models. Educational content, innovative display, engaging visuals.</img prompt>
        <img prompt>A globe connected by digital lines with the iPad at the center. Global connectivity, technological focus, blue tones.</img prompt>
        <img prompt>A timeline of human history unfolding from the iPad screen. Historical images, dynamic layout, informative design.</img prompt>
        <img prompt>A virtual classroom with diverse students interacting via iPads. Inclusive setting, modern education, collaborative mood.</img prompt>
    </images>
</post>
```

#### 5. **General Guidelines:**

- **Creativity and Vividness:**

  - **Emphasize creativity** in both captions and image prompts to ensure engaging and unique content.

  - **Use vivid and descriptive language** to paint a clear picture in the audience’s mind.

  - **Think Very Creatively:** Explore all facets of each idea, utilizing creative thinking to develop unique and engaging content that stands out.

  - **Build a Story:** Each post should tell a cohesive and compelling story related to the idea, enhancing engagement and relatability.

- **Image Prompts Specifics:**

  - **Descriptive and Detailed Initial Part:** Start with a comprehensive description of the main subject or scene.

  - **Concise, Short Phrases for Additional Details:** Follow the initial description with short, clear phrases specifying elements such as background, style, and medium.

  - **Simplicity for Comprehension:** Ensure that prompts are not overly complicated, making them easily understandable for text-to-image models.

  - **Flexible Number of Images:** The number of image prompts per post can vary widely, from 1 to 5 images, based on what best represents the story and idea. Do not limit to a fixed number of images.

- **Consistency:** Maintain consistency with the brand’s established voice and style.

- **Clarity:** Ensure that the structure is clear and adheres strictly to the specified tags. It is very important for you to follow the specified output format.

- **Relevance:** All content should be relevant to the provided ideas and aligned with brand messaging.

- **Focus on Historical Trends:**

  - **Serious Emphasis on Historical Data:** Closely follow historical posting patterns, themes, and engagement strategies to ensure new content aligns with what has proven successful.

  - **Understand and Follow Patterns Thoroughly:** Analyze and replicate the elements that drive engagement based on historical data.

- **Utilize Company Information Creatively:**

  - **Leverage Company Stories and Values:** Infuse posts with elements from the company’s background, values, and strategies to add depth and authenticity.

  - **Innovative Use of Company Data:** Think creatively about how to incorporate various aspects of the company information to enhance the relevance and impact of each post.

- **Adaptability:** The number of posts generated for each idea should precisely match the number specified in the input. The example provided demonstrates generating 3 posts for each of 3 ideas, but your output should adjust based on the input provided.
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
        "height": 512,
        "width": 512
    }

    cost = 512 * 512 * 0.040 / (10**6)

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