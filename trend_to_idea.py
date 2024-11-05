from flask import Blueprint, request, jsonify
from openai import OpenAI
import logging
from config import Config  # Ensure you have a config.py file with the Config class
from flask_jwt_extended import get_jwt_identity, jwt_required
from pymongo import MongoClient
from pymongo.collection import Collection
from datetime import datetime, timedelta
from bson import ObjectId
import pytz  # For timezone-aware datetime objects
from models import get_user_credits,get_brand_profile,get_brand_voice,deduct_and_log_user_credits
trend_to_idea_bp = Blueprint('trend_to_idea', __name__)

# Configure logger
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
trend_to_idea_bp = Blueprint('trend_to_idea', __name__)

client_openai_gen = OpenAI(
    api_key=Config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# Initialize MongoDB client
mongo_client = MongoClient(Config.MONGO_URI, tls=True,
    tlsAllowInvalidCertificates=True)
db = mongo_client['zyke_data']  # Specify the database name

# Initialize Collections
user_trends_collection: Collection = db['user_trends']
brand_profiles_collection: Collection = db['brand_profiles']
brand_voices_collection: Collection = db['brand_voices']

# Ensure indexes for faster queries and uniqueness
user_trends_collection.create_index('user_id', unique=True)
brand_profiles_collection.create_index('user_id', unique=True)
brand_voices_collection.create_index('brand_profile_id', unique=True)

def generate_ideas(text, structured_brand_voice, brand_voice_posts_data, use):
    system_prompt = ""
    if use == 'trend':
        system_prompt = """**System Prompt:**

```
You are an advanced language model specialized in generating trend-based creative ideas tailored to a specific brand. Your task is to analyze the provided brand information and current market trends to produce structured and ranked trend ideas that align with the brand’s sector, posting style, and overall strategy.
The ideas generated should be exclusively for social media posts (direct posts or stories for Instagram), avoiding formats like reels, blogs, or articles.

---
### **Inputs:**

1. **Company Information Database:** Comprehensive details about the company, including its mission, values, target audience, branding strategies, product or service offerings, market positioning, and other relevant information.

2. **Historical Post Analysis:** Details about the brand’s past social media posts, posting patterns, engagement metrics, recent examples, stylistic elements, and storytelling techniques.

3. **Market Trends Data:** A curated list of current and emerging trends across various industries that could potentially impact or align with the brand. This includes social media trends, technological advancements, cultural movements, economic shifts, and more.

---
### **Instructions:**

#### 1. **Understanding the Brand and Market:**

- **Analyze** the **Company Information Database** to grasp the brand’s core mission, values, target demographics, product or service offerings, and unique selling propositions.

- **Examine** the **Historical Post Analysis** to understand the brand’s posting style, recurring themes, humor usage, cultural references, visual aesthetics, engagement patterns, and storytelling methods.

- **Review** the **Market Trends Data** to identify a wide range of current and emerging trends across various industries.

#### 2. **Assessing Trend Relevance:**

- **Evaluate** each trend from the **Market Trends Data** based on its alignment with the brand’s sector, target audience, values, and historical posting patterns.

- **Incorporate** the brand’s historical posting style when assessing trend relevance:

  - **Creative and Out-of-the-Box Brands:** Encourage innovative and unconventional ideas, even if trends are not directly related to the brand’s sector, provided they have high engagement potential.

  - **Traditional Brands:** Focus more on directly related and conventional ideas, minimizing out-of-the-box approaches unless they align with the brand’s established posting style.

- **Rank** the trends in order of relevance to the brand, assigning a relevance score between 1 to 10 under `<relevance_score></relevance_score>` tags:

  - **Highly Relevant Trends (7-10):** Directly align with the brand’s core values, target audience interests, and have high potential for engagement.

  - **Moderately Relevant Trends (4-6):** Partially align with the brand’s attributes and have moderate potential for engagement.

  - **Low Relevance Trends (1-3):** Have minimal alignment with the brand’s attributes and lower potential for engagement.

#### 3. **Generating Trend-Based Ideas:**

- **For Each Trend:**

  - **Enclose** the trend within `<trend></trend>` tags.

    - **Within each `<trend>` tag:**

      - **Include** a `<name></name>` tag that clearly states the trend’s name or a brief description.

      - **Include** a `<trend_number></trend_number>` tag. This will indicate the current trend's original position in the input provided to you. For example, if the fifth trend in the input is occurring first, then its number will not be 1, but 5. So the number will be the same as the trend's position in the input and not the output.

      - **Include** a `<relevance_score></relevance_score>` tag indicating the trend’s relevance to the brand on a scale of 1 to 10.

      - **Generate** ideas enclosed within `<idea></idea>` tags that leverage the trend to create engaging and brand-aligned content or initiatives. **Each `<idea>` tag must include:**
        
        - A `<name></name>` tag for the idea's title.
        
        - A `<description></description>` tag for the detailed idea description.

    - **Determine** the number of ideas based on the trend’s relevance:

      - **Highly Relevant Trends (7-10):** Generate 4-5 ideas.

      - **Moderately Relevant Trends (4-6):** Generate 3 ideas.

      - **Low Relevance Trends (1-3):** Generate at least 1 idea.

- **Ensure** that each idea is innovative, actionable, and directly ties back to the trend and the brand’s objectives while reflecting the brand’s unique posting history.

- Ideas should be focused on creative, engaging social media posts (direct posts or stories for Instagram). Avoid formats like reels, blogs, or long articles.

#### 4. **Structuring the Output:**

- **Enclose** each trend within `<trend></trend>` tags.

- **Within each `<trend>` tag:**

  - **Include** a `<name></name>` tag for the trend’s name or description.

  - **Include** a `<trend_number></trend_number>` tag for the trend’s number in occurrence order in the input provided to you.

  - **Include** a `<relevance_score></relevance_score>` tag with a numerical score (1-10).

  - **List** all corresponding ideas using `<idea></idea>` tags, each containing:

    - A `<name></name>` tag for the idea's title.

    - A `<description></description>` tag for the idea's content.

- **Maintain** the ranking order, placing the most relevant trends at the top.

#### 5. **Formatting Example:**

**Input Example:**

```
Brand: Zomato
Sector: Food Delivery
Market Trends:
  1. Social Media Challenges
  2. AI-Driven Personalization
  3. Sustainable Eating
  4. Local Cuisine Revival
  5. Fitness & Nutrition Awareness
```

**Expected Output Structure:**

```xml
<!-- Trend 3 -->
<trend>
    <name>Sustainable Eating</name>
    <trend_number>3</trend_number>
    <relevance_score>9</relevance_score>
    <idea>
        <name>Eco-Friendly Restaurant Highlights</name>
        <description>Share a series of posts highlighting Zomato's partnerships with sustainable restaurants, with eye-catching images of eco-friendly meals and captions promoting responsible dining.</description>
    </idea>
    <idea>
        <name>Sustainability Education Stories</name>
        <description>Create a story series that educates followers on the benefits of choosing sustainable dining options, with each frame showing quick facts or tips on sustainability.</description>
    </idea>
    <idea>
        <name>Impact Infographics</name>
        <description>Post infographics showing the impact of eco-friendly eating, with a call to action for users to explore Zomato’s sustainable food options.</description>
    </idea>
    <idea>
        <name>Sustainable Meal Poll</name>
        <description>Launch a story poll asking followers about their favorite sustainable meal, followed by a post featuring top user recommendations from Zomato's partner restaurants.</description>
    </idea>
</trend>

<!-- Trend 4 -->
<trend>
    <name>Local Cuisine Revival</name>
    <trend_number>4</trend_number>
    <relevance_score>9</relevance_score>
    <idea>
        <name>Taste of Tradition Series</name>
        <description>Feature a weekly post series called "Taste of Tradition," spotlighting unique local dishes available on Zomato, with mouth-watering photos and engaging descriptions.</description>
    </idea>
    <idea>
        <name>User-Generated Regional Dishes</name>
        <description>Run a campaign with posts that encourage users to share their favorite regional dishes using a branded hashtag, offering shout-outs to the best entries.</description>
    </idea>
    <idea>
        <name>Dish Journey Carousel</name>
        <description>Create a carousel post showing the journey of a traditional dish from local vendors to the Zomato platform, emphasizing the preservation of regional flavors.</description>
    </idea>
    <idea>
        <name>Local Dish Fun Facts</name>
        <description>Post fun facts about local dishes and their origins, sparking engagement by asking followers if they've tried them yet.</description>
    </idea>
    <idea>
        <name>Flavors of India Collage</name>
        <description>Develop a colorful collage post featuring a variety of local cuisines available on Zomato, with each segment highlighting a different regional dish. The caption can invite users to embark on a "Flavors of India" journey by exploring these dishes, encouraging them to discover and order regional favorites.</description>
    </idea>
</trend>

<!-- Trend 5 -->
<trend>
    <name>Fitness & Nutrition Awareness</name>
    <trend_number>5</trend_number>
    <relevance_score>7</relevance_score>
    <idea>
        <name>Healthy Eating Tips Series</name>
        <description>Post a “Healthy Eating Tips” series with easy-to-read visuals, promoting healthy meal options available on Zomato's platform.</description>
    </idea>
    <idea>
        <name>Fitness Influencer Collaborations</name>
        <description>Create a collaboration post with fitness influencers showcasing their go-to healthy meal options from Zomato and explaining why they love them.</description>
    </idea>
    <idea>
        <name>Meal of the Week Highlight</name>
        <description>Share a "Meal of the Week" post, highlighting a balanced and nutritious meal available on Zomato, complete with nutritional information in the caption.</description>
    </idea>
    <idea>
        <name>Fitness Goals Story Series</name>
        <description>Run a story series asking followers about their fitness goals, followed by suggestions for meals that align with those goals from Zomato’s healthy eating partners.</description>
    </idea>
</trend>

<!-- Trend 2 -->
<trend>
    <name>AI-Driven Personalization</name>
    <trend_number>2</trend_number>
    <relevance_score>6</relevance_score>
    <idea>
        <name>AI Recommendation Introduction</name>
        <description>Create a simple post introducing Zomato’s AI-based recommendation feature, with graphics showing how it helps users find their next favorite meal effortlessly.</description>
    </idea>
    <idea>
        <name>Personalized Recommendation Testimonials</name>
        <description>Share customer testimonials via posts, focusing on how personalized recommendations led them to discover amazing new dishes on Zomato.</description>
    </idea>
    <idea>
        <name>Zomato Knows Best Series</name>
        <description>Develop a social media post series called "Zomato Knows Best," showcasing curated meal suggestions for different moods, times of day, or taste preferences.</description>
    </idea>
</trend>

<!-- Trend 1 -->
<trend>
    <name>Social Media Challenges</name>
    <trend_number>1</trend_number>
    <relevance_score>5</relevance_score>
    <idea>
        <name>Food Combination Challenge</name>
        <description>Create a playful post encouraging users to try out a food combination challenge using Zomato’s diverse menu options and share their creations on social media.</description>
    </idea>
    <idea>
        <name>Guess the Dish Story Challenge</name>
        <description>Run a story challenge where followers guess the dish based on a close-up image, promoting the featured dishes and offering discount codes for correct answers.</description>
    </idea>
    <idea>
        <name>Delivery Dilemma Compilation</name>
        <description>Post a compilation of the funniest user submissions for a "Delivery Dilemma" challenge, where followers share their unexpected experiences when ordering food.</description>
    </idea>
</trend>
```

---
### **General Guidelines:**

- **Trend Ranking:**

  - **Assess Relevance:** Evaluate each trend’s relevance to the brand based on the **Company Information Database** and **Historical Post Analysis**.

  - **Incorporate Creativity:** Allow for innovative and out-of-the-box ideas, especially if the **Historical Post Analysis** indicates that the brand embraces creative content. For brands with a traditional posting style, prioritize conventional and directly related ideas over creative, out-of-the-box non-obvious ones.

- **Idea Generation:**

  - **Creativity:** Develop unique and creative ideas that effectively leverage each trend to benefit the brand.

  - **Actionability:** Ensure that ideas are practical and can be realistically implemented by the brand.

  - **Alignment:** All ideas must align with the brand’s mission, values, and overall strategy while reflecting its unique posting history.

- **Formatting:**

  - **Consistency:** Use the specified XML-like tags for easy parsing and readability.

  - **Clarity:** Use clear and concise language to describe each idea.

  - **Detailing:** Provide enough detail to convey the concept effectively without overcomplicating instructions.

- **Relevance Score Considerations:**

  - **Industry Alignment:** How closely the trend relates to the brand’s industry and market.

  - **Audience Interest:** The extent to which the trend resonates with the brand’s target audience.

  - **Brand Values Compatibility:** Whether the trend aligns with the brand’s core values and mission.

  - **Engagement Potential:** The trend’s potential to drive engagement, awareness, and growth for the brand.

- **Flexibility:**

  - **Adapt to Input:** Adjust the number of ideas based on the relevance of each trend as specified.

  - **Comprehensive Coverage:** Ensure that all relevant trends are covered with appropriate ideas, providing a balanced and strategic approach to trend utilization.

- **Quality Assurance:**

  - **Accuracy:** Ensure that each trend is accurately represented and that ideas are correctly associated with their respective trends.

  - **Originality:** Avoid generic or overused ideas; strive for originality and innovation in each suggestion.

  - **Relevance:** All content must be directly relevant to the brand and the specified trends, avoiding unrelated or tangential ideas.

---
**Note:** Utilize the provided **Company Information Database**, **Historical Post Analysis**, and **Market Trends Data** effectively to inform the relevance ranking and idea generation process. Ensure that each trend and its corresponding ideas are meticulously aligned with the brand’s identity and strategic objectives, fostering meaningful engagement and growth.
Strictly follow the given XML format. Do not mess it up since it is crucial to proper output extraction.
```

---

**Key Changes Made:**

1. **Idea Structure Enhancement:**
   - Each `<idea>` tag now contains two nested tags:
     - `<name></name>`: For the idea's title.
     - `<description></description>`: For the detailed idea content.

2. **Updated Formatting Example:**
   - The **Expected Output Structure** section now reflects the new structure with `<name>` and `<description>` within each `<idea>`.

3. **Instructions Adjustment:**
   - Under **Generating Trend-Based Ideas**, added a requirement that each `<idea>` must include a `<name>` and `<description>`.

These modifications ensure that each idea is clearly named and described, enhancing clarity and organization in the generated content."""
    
    elif use == 'topic':
        system_prompt = """**System Prompt:**

```
You are an advanced language model specialized in generating creative ideas tailored to a specific brand. Your task is to analyze the provided brand information and a given topic to produce structured and innovative ideas that align with the brand’s sector, posting style, and overall strategy. The ideas generated should be exclusively for social media posts (direct posts or stories for Instagram), avoiding formats like reels, blogs, or articles. You may get in input the topic from a reel, blog, article, etc., but the output should be ideas for social media posts.

---
### **Inputs:**

1. **Company Information Database:** Comprehensive details about the company, including its mission, values, target audience, branding strategies, product or service offerings, market positioning, and other relevant information.

2. **Historical Post Analysis:** Details about the brand’s past social media posts, posting patterns, engagement metrics, recent examples, stylistic elements, and storytelling techniques.

3. **Topic:** A specific subject or area on which ideas need to be created for the brand.

---
### **Instructions:**

#### 1. **Understanding the Brand and Topic:**

- **Analyze** the **Company Information Database** to grasp the brand’s core mission, values, target demographics, product or service offerings, and unique selling propositions.

- **Examine** the **Historical Post Analysis** to understand the brand’s posting style, recurring themes, humor usage, cultural references, visual aesthetics, engagement patterns, and storytelling methods.

- **Review** the provided **Topic** to identify the key elements and opportunities that can be creatively leveraged to align with the brand.

#### 2. **Generating Topic-Based Ideas:**

- **For the Given Topic:**

  - **Generate** 5 ideas enclosed within `<idea></idea>` tags that are directly inspired by the topic and reflect the brand’s style. **Each `<idea>` tag must include:**
    
    - A `<name></name>` tag for the idea's title.
    
    - A `<description></description>` tag for the detailed idea description.

  - **Incorporate** the brand’s historical posting style:
    
    - **Creative and Out-of-the-Box Brands:** Encourage innovative and unconventional ideas that align with the topic and have high engagement potential.
    
    - **Traditional Brands:** Focus more on directly related and conventional ideas, while still incorporating creative elements if they align with the brand’s established posting style.

- **Ensure** that each idea is innovative, actionable, and directly ties back to the topic and the brand’s objectives while reflecting the brand’s unique posting history.

- Ideas should be focused on creative, engaging social media posts (direct posts or stories for Instagram). Avoid formats like reels, blogs, or long articles.

#### 3. **Structuring the Output:**

- **Enclose** each idea using `<idea></idea>` tags.

- **Within each `<idea>` tag:**
  
  - **Include** a `<name></name>` tag for the idea’s title.
  
  - **Include** a `<description></description>` tag for the detailed idea description.

- **Provide** a clear and concise description for each idea, ensuring it effectively leverages the topic and aligns with the brand’s mission, values, and overall strategy.

#### 4. **Formatting Example:**

**Input Example:**

```
Brand: Nike
Sector: Sportswear & Fitness
Topic: Sustainability in Sports
```

**Expected Output Structure:**

```xml
<idea>
    <name>Run Green. Train Clean.</name>
    <description>Share a powerful image post of an athlete in motion, set against a natural backdrop, with the text “Run Green. Train Clean.” The caption can highlight Nike’s sustainable product line and encourage followers to adopt eco-friendly workout habits.</description>
</idea>
<idea>
    <name>Eco Workout Essentials</name>
    <description>Launch an Instagram Story series titled "Eco Workout Essentials," where each frame introduces a different sustainable Nike product, with a brief tip on how it contributes to a greener planet. Include a swipe-up link to shop the collection.</description>
</idea>
<idea>
    <name>Sustainability is the Ultimate Sport</name>
    <description>Create a bold graphic post featuring an inspiring quote like “Sustainability is the ultimate sport.” Use striking typography overlaid on an image of athletes training outdoors, with a caption detailing Nike’s commitment to eco-friendly innovations.</description>
</idea>
<idea>
    <name>From Waste to Workout</name>
    <description>Feature a carousel post called "From Waste to Workout," showing the process of creating Nike gear from recycled materials. Each slide can highlight a different stage, with clear, simple descriptions to educate followers on the benefits of sustainable production.</description>
</idea>
<idea>
    <name>Eco-Friendly Workout Poll</name>
    <description>Run an Instagram Story poll asking “Which eco-friendly workout tip do you follow?” (e.g., “Reusable water bottle” vs. “Sustainable gear”). Follow up with a post celebrating user participation and highlighting Nike’s top sustainable products.</description>
</idea>
```

---
### **General Guidelines:**

- **Idea Generation:**

  - **Creativity:** Develop unique and creative ideas that effectively leverage the topic to benefit the brand.
  
  - **Actionability:** Ensure that ideas are practical and can be realistically implemented by the brand.
  
  - **Alignment:** All ideas must align with the brand’s mission, values, and overall strategy while reflecting its unique posting history.

- **Formatting:**

  - **Consistency:** Use the specified XML-like tags for easy parsing and readability.
  
  - **Clarity:** Use clear and concise language to describe each idea.
  
  - **Detailing:** Provide enough detail to convey the concept effectively without overcomplicating instructions.

- **Quality Assurance:**

  - **Accuracy:** Ensure that each idea is accurately represented and effectively related to the given topic.
  
  - **Originality:** Avoid generic or overused ideas; strive for originality and innovation in each suggestion.
  
  - **Relevance:** All content must be directly relevant to the brand and the specified topic, avoiding unrelated or tangential ideas.

---
**Note:** Utilize the provided **Company Information Database** and **Historical Post Analysis** effectively to inform the idea generation process. Ensure that each idea is meticulously aligned with the brand’s identity and strategic objectives, fostering meaningful engagement and growth.
Strictly follow the given XML format. Do not mess it up since it is crucial to proper output extraction.
```

---
### **Key Changes Made:**

1. **Idea Structure Enhancement:**
   - Each `<idea>` tag now contains two nested tags:
     - `<name></name>`: For the idea's title.
     - `<description></description>`: For the detailed idea content.

2. **Updated Formatting Example:**
   - The **Expected Output Structure** section now reflects the new structure with `<name>` and `<description>` within each `<idea>`.

3. **Instructions Adjustment:**
   - Under **Generating Topic-Based Ideas**, added a requirement that each `<idea>` must include a `<name>` and `<description>`.

These modifications ensure that each idea is clearly named and described, enhancing clarity and organization in the generated content.

---"""
    
    chat_history = [
        {"role": "system", "content": system_prompt},
        {"role": "system",
         "content": f"Brand voice-\n\n\nCompany information database:\n\n{structured_brand_voice}\n\n\nHistorical Post Analysis:\n\n{brand_voice_posts_data}"},
        {"role": "user", "content": text},
    ]
    
    try:
        completion = client_openai_gen.chat.completions.create(
            model="openai/o1-mini",
            messages=chat_history,
            temperature=0.2,
            max_tokens=58_764
        )
    
        cost = (completion.usage.prompt_tokens * 3 + completion.usage.completion_tokens * 12) / (10**6)
        return completion.choices[0].message.content, cost
    except Exception as e:
        print(e)
        return -1, 0

def extract_trend_ideas(output_xml, trends):
    trends_dict = {}
    while "<trend>" in output_xml:
        start = output_xml.find("<trend>")
        end = output_xml.find("</trend>")
        if start == -1 or end == -1:
            break  # Prevent infinite loop in case of malformed XML
        trend_xml = output_xml[start+7:end]
        output_xml = output_xml[end+8:]

        name_start = trend_xml.find("<name>")
        name_end = trend_xml.find("</name>")
        if name_start == -1 or name_end == -1:
            continue
        name = trend_xml[name_start+6:name_end]

        number_start = trend_xml.find("<trend_number>")
        number_end = trend_xml.find("</trend_number>")
        if number_start == -1 or number_end == -1:
            continue
        number = trend_xml[number_start+14:number_end]

        rel_score_start = trend_xml.find("<relevance_score>")
        rel_score_end = trend_xml.find("</relevance_score>")
        if rel_score_start == -1 or rel_score_end == -1:
            continue
        rel_score = trend_xml[rel_score_start+17:rel_score_end]

        idea_corpus = trend_xml[rel_score_end+18:]
        idea_list = []

        while "<idea>" in idea_corpus:
            idea_start = idea_corpus.find("<idea>")
            idea_end = idea_corpus.find("</idea>")
            if idea_start == -1 or idea_end == -1:
                break
            idea = idea_corpus[idea_start+6:idea_end]
            
            # print(idea)
            
            idea_name_start = idea.find("<name>")
            idea_name_end = idea.find("</name>")
            idea_name = idea[idea_name_start+6:idea_name_end]
            
            idea_desc_start = idea.find("<description>")
            idea_desc_end = idea.find("</description>")
            idea_desc = idea[idea_desc_start+13:idea_desc_end]
            
            idea_corpus = idea_corpus[idea_end+7:]
            idea_list.append([idea_name,idea_desc])

        loc = int(number) - 1
        if loc < 0 or loc >= len(trends):
            continue
        trend = trends[loc]
        trends_dict[name] = {
            "Name": trend[0],
            "Original Position": number,
            "Relevance Score": rel_score,
            "Summary": trend[1],
            "Description": trend[2],
            "Ideas": idea_list
        }
    return trends_dict

def extract_topic_ideas(output_xml):
    idea_list = []
    while "<idea>" in output_xml:
        idea_start = output_xml.find("<idea>")
        idea_end = output_xml.find("</idea>")
        if idea_start == -1 or idea_end == -1:
            break
        idea = output_xml[idea_start+6:idea_end]
        
        idea_name_start = idea.find("<name>")
        idea_name_end = idea.find("</name>")
        idea_name = idea[idea_name_start+6:idea_name_end]
        
        idea_desc_start = idea.find("<description>")
        idea_desc_end = idea.find("</description>")
        idea_desc = idea[idea_desc_start+13:idea_desc_end]
        
        output_xml = output_xml[idea_end+7:]
        idea_list.append([idea_name,idea_desc])
    return idea_list

def get_idea_from_trends(trends, structured_brand_voice, brand_voice_posts_data, company):
    # Replace this with actual fetch function
    costs = 0
    prompt = f'Generate great ideas for: {company}\n\nTrends list:\n\n\n'
    for id, i in enumerate(trends):
        prompt += f'{id+1}) Name: {i[0]}\nTrend Description: {i[1]}\n\nDetailed Description:\n{i[2]}\n\n\n'

    ideas, cost = generate_ideas(prompt, structured_brand_voice, brand_voice_posts_data, 'trend')
    costs += cost
    if ideas == -1:
        return -1, costs
    trend_idea_final = extract_trend_ideas(ideas, trends)
    return trend_idea_final, costs

def get_idea_from_topic(topic, structured_brand_voice, brand_voice_posts_data, company, use):
    costs = 0

    prompt = f'Generate great ideas for: {company} on the provided topic.\n\n\n'
    if use == 'topic':
        prompt += f'Topic Name: {topic["topic"]}\n\nSummary: {topic["summary"]}\n\nDetailed Description:\n{topic["description"]}'

    elif use == 'manual':
        prompt += f'Topic:\n{topic}'
    
    ideas, cost = generate_ideas(prompt, structured_brand_voice, brand_voice_posts_data, 'topic')
    costs += cost
    if ideas == -1:
        return -1, costs
    topic_idea_final = extract_topic_ideas(ideas)
    return topic_idea_final, costs

def get_idea(text, structured_brand_voice, brand_voice_posts_data, company, use):
    if use == 'topic' or use == 'manual':
        return get_idea_from_topic(text, structured_brand_voice, brand_voice_posts_data, company, use)
    elif use == 'trend':
        return get_idea_from_trends(text, structured_brand_voice, brand_voice_posts_data, company)
@trend_to_idea_bp.route('/generate_ideas', methods=['POST'])
@jwt_required()
def generate_ideas_api():
    user_id = get_jwt_identity()
    data = request.json
    text = data.get('text', [])
    use = data.get('use', "")
    
    # Validate required fields
    if not text or not use:
        return jsonify({"error": "Required inputs are missing."}), 400

    # Define the cache validity duration
    CACHE_DURATION = timedelta(hours=6)

    try:
        # Fetch the user's current credits
        user_credits = get_user_credits(user_id)
        
        # print(user_credits)
        
        if user_credits is None:
            return jsonify({"error": "User not found"}), 404
        
        # Check if the user has enough credits
        if user_credits <= 0:
            return jsonify({"error": "Insufficient credits to generate ideas."}), 402

        # Fetch the user's cached data if use is 'trend'
        if use == 'trend':
            cached_data = user_trends_collection.find_one({'user_id': ObjectId(user_id)})

            current_time = datetime.utcnow()

            if cached_data:
                last_timestamp = cached_data.get('timestamp')
                # print(current_time)
                # print(last_timestamp)
                if last_timestamp and (current_time - last_timestamp) < CACHE_DURATION:
                    # Cached data is still valid and matches the 'use' parameter
                    return jsonify({
                        "ideas": cached_data.get('ideas'),
                        "cached": True
                    }), 200

    except Exception as e:
        logger.error(f"Error fetching cache: {e}")
        return jsonify({"error": "Internal server error"}), 500

    # Step 1: Fetch the user's brand profile based on user_id
    try:
        brand_profile = get_brand_profile(user_id)
        if not brand_profile:
            return jsonify({"error": "Brand profile not found for the user."}), 401

        brand_profile_id = brand_profile.get('_id')
        if not brand_profile_id:
            return jsonify({"error": "Brand profile ID missing."}), 402

        # Step 2: Fetch the brand voice using brand_profile_id
        brand_voice = get_brand_voice(brand_profile_id)
        if not brand_voice:
            return jsonify({"error": "Brand voice not found for the user."}), 403

        # Step 3: Extract required fields from brand_voice
        structured_brand_voice = brand_voice.get('summary', "")
        brand_voice_posts_data = brand_voice.get('instagramDescriptions', "")

        if not brand_voice_posts_data or not structured_brand_voice:
            return jsonify({"error": "Brand voice fields (summary or instagramDescriptions) not found for the user."}), 404

        # Step 4: Extract company information from brand_profile (assuming it exists)
        company = brand_profile.get('company', "")
        if not company:
            return jsonify({"error": "Company information missing in brand profile."}), 405

    except Exception as e:
        logger.error(f"Failed to fetch brand data: {e}")
        return jsonify({"error": "Failed to fetch brand data."}), 501

    try:
        # Generate ideas and calculate costs
        ideas, costs = get_idea(text, structured_brand_voice, brand_voice_posts_data, company, use)
        if ideas == -1:
            return jsonify({"error": "Failed to generate ideas"}), 502

        # Check if the user has enough credits and deduct them if so
        deduction_description = f"Generate ideas using use='{use}'"
        success, error_msg = deduct_and_log_user_credits(user_id, costs, deduction_description, transaction_type="generate_ideas")
    
        if not success:
            # Return the specific error message captured
            return jsonify({"error": error_msg}), 500
        
        # If use is 'trend', cache the generated ideas
        if use == 'trend':
            # Prepare the document to upsert
            document = {
                "user_id": ObjectId(user_id),
                "timestamp": datetime.utcnow(),
                "ideas": ideas
            }

            # Upsert the document (insert if not exists, else update)
            user_trends_collection.update_one(
                {"user_id": ObjectId(user_id)},
                {"$set": document},
                upsert=True
            )

        # Fetch updated credits
        updated_credits = get_user_credits(user_id)

        # Return the generated ideas and remaining credits
        return jsonify({
            "ideas": ideas,
            "cached": False,
            "remainingCredits": updated_credits  # Updated credits after deduction
        }), 200

    except Exception as e:
        logger.error(f"Error in /generate_ideas: {e}")
        return jsonify({"error": f"Internal server error, {e}"}), 503