# Zyke Backend — Codebase Documentation

Deep, implementation-level documentation for the Zyke Flask backend. This guide mirrors the structure and clarity of the frontend docs and provides exhaustive coverage of architecture, blueprints, configuration, data model, authentication, brand intelligence, trends/ideas/posts engines, image pipelines, payments and credits, API contracts, operational notes, and testing.

Conventions
- References are clickable. Functions or declarations include exact line numbers, e.g., [Python.create_app()](zyke-backend/app.py:22). File links may omit lines, e.g., [zyke-backend/models.py](zyke-backend/models.py).


Contents
- Architecture and boot sequence
- Blueprint overview and responsibilities
- Configuration and environment
- Data model (MongoDB) and helpers
- Authentication lifecycle (email/OTP, OAuth, reset, refresh)
- Brand voice generation (web, files, social; LLM consolidation)
- Trends ingestion and idea generation
- Ideas → posts generation (captions + images)
- Image utilities (mask blend preview and inpainting)
- Repurpose pipeline (URL → normalized topic)
- Credits, orders, and webhooks
- API contracts and payloads
- Error handling and operational notes
- Security notes
- Performance and scalability
- Deployment playbook
- Testing strategy
- Extension guide
- Route matrix (public endpoints)
- Known issues and refactor recommendations
- Glossary


## Architecture and boot sequence

- App factory: [Python.create_app()](zyke-backend/app.py:22)
  - Loads [Python.Config](zyke-backend/config.py:5), applies CORS scoped to production origins, initializes:
    - Mail: [Python.init_mail()](zyke-backend/emailservice.py:8)
    - JWT: [Python.JWTManager()](zyke-backend/app.py:33)
    - OAuth: [Python.oauth_init_app()](zyke-backend/auth.py:51)
  - Registers all Blueprints with domain prefixes.
  - Includes a global error handler returning JSON: [Python.handle_exception()](zyke-backend/app.py:57).
  - Root route: [Python.home()](zyke-backend/app.py:52).

- Data access
  - Mongo client at import time: [Python.MongoClient()](zyke-backend/models.py:12) → db = “zyke_data”.
  - Collections for users, OTP storage, brand profiles/voices, transactions, trends, user_trends, user_last_posts, total_costs.

- External integrations
  - LLMs: OpenRouter (chat), Perplexity (online RAG), Vertex/Gemini (multimodal description), Together (image generation), Stability AI (inpainting).
  - Social/data: Apify (Instagram), Bright Data datasets (Instagram posts/reels).


## Blueprint overview and responsibilities

Auth — /auth ([Python.auth_bp](zyke-backend/auth.py:46))
- Registration with OTP: [Python.register()](zyke-backend/auth.py:75) → [Python.send_otp_email()](zyke-backend/emailservice.py:18) → [Python.verify_otp_route()](zyke-backend/auth.py:118)
- Login / refresh / logout: [Python.login()](zyke-backend/auth.py:202), [Python.refresh()](zyke-backend/auth.py:376), [Python.logout()](zyke-backend/auth.py:396)
- Password reset: [Python.request_reset()](zyke-backend/auth.py:232) → [Python.send_password_reset_email()](zyke-backend/emailservice.py:63) → [Python.reset_password()](zyke-backend/auth.py:250)
- OAuth: [Python.oauth_login()](zyke-backend/auth.py:274), [Python.oauth_callback()](zyke-backend/auth.py:279)
- Current user: [Python.get_current_user()](zyke-backend/auth.py:403)

Brand Voice — /brand_voice_info ([Python.brand_voice_bp](zyke-backend/brandvoiceinfo.py:46))
- Create brand profile + voice: [Python.create_brand()](zyke-backend/brandvoiceinfo.py:1335)
- Read normalized profile + voice: [Python.get_profile()](zyke-backend/brandvoiceinfo.py:1628)

Trends — /trends ([Python.trends_bp](zyke-backend/trends.py:22))
- Cache + enrich recent trends (6h TTL): [Python.get_trends()](zyke-backend/trends.py:114)

Trend → Ideas — /trend_to_idea ([Python.trend_to_idea_bp](zyke-backend/trend_to_idea.py:12))
- Generate ideas from trends/topic/manual: [Python.generate_ideas_api()](zyke-backend/trend_to_idea.py:626)

Ideas → Posts — /idea_to_post ([Python.idea_to_post_bp](zyke-backend/idea_to_post.py:54))
- Generate platform-ready posts (captions + images): [Python.generate_posts_api()](zyke-backend/idea_to_post.py:405)

Last Posts — /fetch_last_post ([Python.fetch_last_post_bp](zyke-backend/fetch_last_post.py:12))
- Returns the last saved posts bundle per user: [Python.generate_posts_api()](zyke-backend/fetch_last_post.py:15)

Image Blend — /blend ([Python.blend_image_bp](zyke-backend/blend.py:11))
- Mask overlay preview on an image: [Python.inpaint_route()](zyke-backend/blend.py:138) (function name misaligned; see Known issues)

Image Inpaint — /inpaint ([Python.inpainting_bp](zyke-backend/inpaint.py:10))
- Masked inpainting via Stability API: [Python.inpaint_route()](zyke-backend/inpaint.py:61)

Repurpose — /repurpose ([Python.repurpose_bp](zyke-backend/repurpose.py:43))
- Normalize URL to {topic, summary, description}: [Python.repurpose_content()](zyke-backend/repurpose.py:709)

Transactions — /transactions ([Python.transactions_bp](zyke-backend/transactions.py:25))
- Credits endpoints and order creation: [Python.get_user_credits_route()](zyke-backend/transactions.py:138), [Python.add_credits()](zyke-backend/transactions.py:159), [Python.get_user_transactions()](zyke-backend/transactions.py:245), [Python.get_user_transactions_admin()](zyke-backend/transactions.py:277)
- Webhook (signature-verified): [Python.handle_webhook()](zyke-backend/transactions.py:352)

Webhooks — /webhooks ([Python.webhooks_bp](zyke-backend/webhooks.py:12))
- Legacy Razorpay webhook handler: [Python.razorpay_webhook()](zyke-backend/webhooks.py:20)


## Configuration and environment

Central config: [Python.Config](zyke-backend/config.py:5)
- Mongo/JWT: MONGO_URI, JWT_SECRET_KEY
- Mail: MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
- URLs: FRONTEND_URL, BACKEND_URL
- Google Cloud: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_JSON_AUTH_PATH
- Scraping: APIFY_API_KEY, BRIGHT_DATA_TOKEN, BRIGHT_DATA_INSTA_POST_DATASET_ID, BRIGHT_DATA_INSTA_REEL_DATASET_ID
- Razorpay: RAZORPAY_KEY, RAZORPAY_SECRET, RAZORPAY_WEBHOOK_SECRET
- Model keys: DEEPINFRA_API_KEY, OPENROUTER_API_KEY, PERPLEXITY_TOKEN, TOGETHER_API_KEY, OPENAI_API_KEY, STABILITY_AI_API_KEY
- Google Search: GOOGLE_API_KEY, GOOGLE_CSE_ID

Loading
- .env is loaded early by [Python.load_dotenv()](zyke-backend/config.py:2) and [Python.load_dotenv()](zyke-backend/app.py:19).

Operational notes
- Production must disable OAuth insecure transport: see [Python.auth.py](zyke-backend/auth.py:44).
- Configure CORS production origins in [Python.CORS()](zyke-backend/app.py:27). The transactions blueprint allows localhost:3000 for dev ([Python.transactions.py](zyke-backend/transactions.py:28)).


## Data model (MongoDB) and helpers

Connection and db selection
- Mongo client: [Python.MongoClient()](zyke-backend/models.py:12)
- Database: [Python.db](zyke-backend/models.py:13) -> name="zyke_data"

Collections and helpers (selected)
- Users: users
  - Find/create/update: [Python.find_user_by_email()](zyke-backend/models.py:31), [Python.get_user_by_id()](zyke-backend/models.py:35), [Python.create_user()](zyke-backend/models.py:39), [Python.update_user_password()](zyke-backend/models.py:62), [Python.update_user_razorpay_customer_id()](zyke-backend/models.py:115)
  - Credits: [Python.get_user_credits()](zyke-backend/models.py:239), [Python.update_user_credits()](zyke-backend/models.py:244)
- OTP temporary storage (alternate persistent design)
  - [Python.store_temporary_user_data()](zyke-backend/models.py:74), [Python.get_temporary_user_data()](zyke-backend/models.py:91), [Python.delete_temporary_user_data()](zyke-backend/models.py:102), [Python.move_user_to_main_collection()](zyke-backend/models.py:106)
  - Note: current flow uses in-memory store in [Python.otp.py](zyke-backend/otp.py:6)
- Brand profiles: brand_profiles
  - [Python.create_brand_profile()](zyke-backend/models.py:172), [Python.get_brand_profile()](zyke-backend/models.py:177)
- Brand voices: brand_voices
  - [Python.create_brand_voice()](zyke-backend/models.py:181), [Python.get_brand_voice()](zyke-backend/models.py:187), [Python.update_brand_voice()](zyke-backend/models.py:191)
- Transactions: transactions
  - [Python.create_transaction()](zyke-backend/models.py:202), [Python.update_transaction()](zyke-backend/models.py:127), [Python.get_transactions_by_user()](zyke-backend/models.py:212)
- Trends cache: trends (raw list + timestamp)
- User trends cache: user_trends (per-user ideas with timestamp)
- User last posts: user_last_posts (see Known issues for naming mismatch)
- Total costs log: total_costs
  - Credit deduction + log insert: [Python.deduct_and_log_user_credits()](zyke-backend/models.py:269)
  - Raw log insert without deduction: [Python.log_credit_usage()](zyke-backend/models.py:334)
  - Aggregate getter: [Python.get_total_cost()](zyke-backend/models.py:380)


## Authentication lifecycle (email/OTP, OAuth, reset, refresh)

Registration
- [Python.register()](zyke-backend/auth.py:75)
  - Validates payload, checks existing user, generates OTP via [Python.generate_otp()](zyke-backend/otp.py:10), mails via [Python.send_otp_email()](zyke-backend/emailservice.py:18), stores hashed temp user in-memory via [Python.store_user_data()](zyke-backend/otp.py:40).
- [Python.verify_otp_route()](zyke-backend/auth.py:118)
  - Verifies OTP via [Python.verify_otp()](zyke-backend/otp.py:16), persists user via [Python.create_user()](zyke-backend/models.py:39), attempts Razorpay customer creation (or lookup) and updates user via [Python.update_user_razorpay_customer_id()](zyke-backend/models.py:115), sends [Python.send_confirmation_email()](zyke-backend/emailservice.py:113), issues both JWTs via cookies.

Login / Logout
- [Python.login()](zyke-backend/auth.py:202) returns { access_token, refresh_token, user } JSON (no cookies).
- [Python.logout()](zyke-backend/auth.py:396) clears cookies for the cookie-based flows.

Password reset
- [Python.request_reset()](zyke-backend/auth.py:232) issues short‑lived token and sends reset link via [Python.send_password_reset_email()](zyke-backend/emailservice.py:63).
- [Python.reset_password()](zyke-backend/auth.py:250) (Bearer) changes hash and mails [Python.send_password_reset_success_email()](zyke-backend/emailservice.py:155).

OAuth (Google)
- Initialize provider: [Python.oauth_init_app()](zyke-backend/auth.py:51) with OIDC discovery.
- Redirect: [Python.oauth_login()](zyke-backend/auth.py:274)
- Callback: [Python.oauth_callback()](zyke-backend/auth.py:279) expects frontend POST with email, names, provider_id; creates/links user and attempts Razorpay customer reconciliation, sets JWT cookies.

Refresh and current user
- Refresh: [Python.refresh()](zyke-backend/auth.py:376) accepts refresh_token JSON and returns a new access_token.
- Current user: [Python.get_current_user()](zyke-backend/auth.py:403) returns non‑sensitive info based on access token identity.


## Brand voice generation (web, files, social; LLM consolidation)

Entry and validation
- Route: POST /brand_voice_info/create → [Python.create_brand()](zyke-backend/brandvoiceinfo.py:1335) (Bearer)
- Validates multipart form data for fields and JSON arrays (industries/contentTypes/targetAudience/brandPersonalities/otherUrls/socialMedia), as well as LinkedIn URL shape.

Async orchestration
- When Instagram handle provided:
  - Run in parallel: general information [Python.brand_info_scrape()](zyke-backend/brandvoiceinfo.py:727) and historical post analysis [Python.brand_post_info_scrape()](zyke-backend/brandvoiceinfo.py:1202), orchestrated by [Python.generate_brand_voice()](zyke-backend/brandvoiceinfo.py:1297).
- General info workflow:
  - Async crawling with politeness bounds via [Python.AsyncMultilingualScraper](zyke-backend/brandvoiceinfo.py:170) → per‑URL summarization [Python.url_summ2()](zyke-backend/brandvoiceinfo.py:517) → final consolidation [Python.final_summ()](zyke-backend/brandvoiceinfo.py:599) (OpenRouter; model configurable).
- Historical posts workflow:
  - Fetch recent Instagram posts via Apify [Python.scrape_instagram()](zyke-backend/brandvoiceinfo.py:979), then for each caption + image set, generate highly detailed multimodal descriptions via [Python.image_desc()](zyke-backend/brandvoiceinfo.py:1008) (OpenAI “gpt‑4o‑mini”), then structure and analyze them via [Python.image_out_summ()](zyke-backend/brandvoiceinfo.py:1125).

Credits and persistence
- Aggregate cost across steps and deduct via [Python.deduct_and_log_user_credits()](zyke-backend/models.py:269). If insufficient/failed, return error with context.
- Persist brand profile and voice: [Python.create_brand_profile()](zyke-backend/models.py:172), [Python.create_brand_voice()](zyke-backend/models.py:181).

Read profile+voice
- GET /brand_voice_info/profile → [Python.get_profile()](zyke-backend/brandvoiceinfo.py:1628) normalizes arrays and returns voice summary + instagramDescriptions.


## Trends ingestion and idea generation

Trends cache and enrichment
- GET /trends/fetch_trends → [Python.get_trends()](zyke-backend/trends.py:114)
  - Uses pytrends to pull India trending list, fetches Perplexity explanations via [Python.fetch_trend_info_pplx()](zyke-backend/trends.py:25), parses XML into {summary, description} via [Python.extract_trend()](zyke-backend/trends.py:78), caches for 6h and logs platform spend via [Python.log_credit_usage()](zyke-backend/models.py:334).

Ideas from trend/topic/manual
- POST /trend_to_idea/generate_ideas → [Python.generate_ideas_api()](zyke-backend/trend_to_idea.py:626)
  - Validates credits, ensures user has brand profile/voice (company + voice corpora).
  - use="trend": feeds nested list to [Python.generate_ideas()](zyke-backend/trend_to_idea.py:39), then extracts per‑trend ideas with numbering and relevance via [Python.extract_trend_ideas()](zyke-backend/trend_to_idea.py:503).
  - use="topic": feeds single {topic, summary, description}; parse via [Python.extract_topic_ideas()](zyke-backend/trend_to_idea.py:568).
  - use="manual": similar to topic with freeform content.
  - Deducts cost and, for use="trend", upserts per‑user cache with 6h TTL policy (enforced by code path).


## Ideas → posts generation (captions + images)

Entry and validation
- POST /idea_to_post/fetch_posts → [Python.generate_posts_api()](zyke-backend/idea_to_post.py:405)
  - Requires credits, brand profile, and brand voice fields present.

Content generation
- Prompt assembly: [Python.generate_content()](zyke-backend/idea_to_post.py:56) combines the two corpora (summary + instagramDescriptions) with the requested ideas/platform and detailed instruction schema to produce a strict XML response.
- XML posts parsing: [Python.extract_posts()](zyke-backend/idea_to_post.py:292) extracts idea→[{caption, images prompts[]}] mapping.

Image generation
- Together Images call for each prompt: [Python.generate_images()](zyke-backend/idea_to_post.py:261) (FLUX model; cost estimated by resolution).
- Fetch image bytes and embed base64: [Python.scrape_img()](zyke-backend/idea_to_post.py:254), converting each to data URL.

Persistence
- Save “last posts” per user via ReplaceOne upsert in user_last_posts, then return saved:true. Read-back by POST /fetch_last_post/get_stored_post.


## Image utilities (mask blend preview and inpainting)

Blend masks (visualize selection)
- POST /blend/blend_masks → [Python.inpaint_route()](zyke-backend/blend.py:138)
  - Parses input masks + image data URLs, dilates masks ([Python.dilate_mask()](zyke-backend/blend.py:13)) for smoother borders, overlays with color/alpha ([Python.blend_image()](zyke-backend/blend.py:27)), returns blended_images[] + dilated_masks[] (both data URLs).

Inpainting (remove/replace/add)
- POST /inpaint/inpaint_image → [Python.inpaint_route()](zyke-backend/inpaint.py:61)
  - Accepts { image, mask, remove, prompt?, neg_prompt? }:
    - If remove="true", uses a conservative built‑in prompt/negative prompt to forbid text/empty areas and ensure background consistency ([Python.inpaint()](zyke-backend/inpaint.py:14)).
  - Calls Stability API v2beta; returns webp data URL and deducts a fixed per‑call cost.


## Repurpose pipeline (URL → normalized topic)

Entry and content types
- POST /repurpose/repurpose_url → [Python.repurpose_content()](zyke-backend/repurpose.py:709), content_type ∈ { post, reel, yt-video, blog, news-article, website }.

Media acquisition
- Instagram post/reel:
  - Trigger Bright Data dataset via [Python.get_insta_post()](zyke-backend/repurpose.py:45) (poll snapshot), then:
    - For reel: download MP4, write temp file, upload to GCS ([Python.upload_file_to_gcp()](zyke-backend/repurpose.py:500)), use Vertex/Gemini [Python.describe_post()](zyke-backend/repurpose.py:423), cleanup ([Python.delete_file_from_gcp()](zyke-backend/repurpose.py:481)).
    - For post: download image set to local temp files and feed into Gemini via Part.
- Web/blog/news/website:
  - Async scrape [Python.AsyncMultilingualScraper](zyke-backend/repurpose.py:118) / [Python.scrape_example()](zyke-backend/repurpose.py:392), then [Python.describe_post()](zyke-backend/repurpose.py:423).

Normalization
- All routes shape their output via XML parser [Python.extract_topic_info()](zyke-backend/repurpose.py:466) → {topic, summary, description} (topic semantic, summary short, description long and structured).

Credits
- Aggregate cost and deduct via [Python.deduct_and_log_user_credits()](zyke-backend/models.py:269). Return remainingCredits for client display.


## Credits, orders, and webhooks

Balances and identity
- GET /transactions/user → [Python.get_user_data()](zyke-backend/transactions.py:325)
- GET /transactions/credits → [Python.get_user_credits_route()](zyke-backend/transactions.py:138)

History
- GET /transactions/history → [Python.get_user_transactions()](zyke-backend/transactions.py:245)
- GET /transactions/history/:userId (admin) → [Python.get_user_transactions_admin()](zyke-backend/transactions.py:277)

Order creation
- POST /transactions/add → [Python.add_credits()](zyke-backend/transactions.py:159):
  - Creates Razorpay order (amount in minor units), returns order_id, persists a “created” transaction with invoice link and receipt id.

Webhook processing
- POST /transactions/webhook → [Python.handle_webhook()](zyke-backend/transactions.py:352)
  - Verifies signature via [Python.verify_webhook_signature()](zyke-backend/transactions.py:106), fetches payment status, idempotently updates the transaction, and if captured:
    - Calculates USD equivalent (static rate for INR) via [Python.calculate_amount_usd()](zyke-backend/transactions.py:48)
    - Updates credits via [Python.update_user_credits()](zyke-backend/models.py:244)

Legacy webhook route
- POST /webhooks/razorpay → [Python.razorpay_webhook()](zyke-backend/webhooks.py:20): uses order notes->user_id link and persists a transaction record (signature verified).


## API contracts and payloads

Headers
- Authorization: Bearer <accessToken>
- Content-Type: application/json unless multipart/form-data

Auth (/auth)
- POST /register { email, password, first_name, last_name } → 200 { msg } | 409 conflict
- POST /verify-otp { email, otp } → 200 { msg } (also sets cookies for cookie-based auth)
- POST /login { email, password } → 200 { access_token, refresh_token, user }
- POST /request-reset { email } → 200 { msg }
- POST /reset-password (Bearer) { new_password } → 200 { msg }
- GET /oauth/login → 302 redirect (OIDC)
- POST /oauth/callback { email, first_name, last_name, provider_id } → 200 (sets cookies)
- POST /refresh { refresh_token } → 200 { access_token }
- POST /logout → 200 { msg }
- GET /user (Bearer) → 200 user snapshot

Brand Voice (/brand_voice_info)
- POST /create (multipart/form-data) → 201 { summary, instagramDescriptions, remainingCredits }
- GET /profile (Bearer) → 200 normalized profile + voice

Trends (/trends)
- GET /fetch_trends → 200 { trends: [ [name, summary, description], ... ] }

Trend → Ideas (/trend_to_idea)
- POST /generate_ideas
  - Body: { use: "trend", text: string[][] } OR { use: "topic", text: { topic, summary, description } } OR { use: "manual", text: string }
  - 200: { ideas, cached?: boolean, remainingCredits?: number }

Ideas → Posts (/idea_to_post)
- POST /fetch_posts { ideas: [ [title, content] ], num: number, platform: "instagram" | "linkedin" }
  - 200: { saved: true, remainingCredits }

Last Posts (/fetch_last_post)
- POST /get_stored_post {} → 200 { posts: { [idea: string]: [ { caption, images[] } ] } }

Images
- POST /blend/blend_masks { img: dataURL, masks: dataURL[] } → 200 { blended_images: dataURL[], dilated_masks: dataURL[] }
- POST /inpaint/inpaint_image { image: dataURL, mask: dataURL, remove: "true"|"false", prompt?: string, neg_prompt?: string } → 200 { result: dataURL, remainingCredits }

Repurpose (/repurpose)
- POST /repurpose_url { url: string, content_type: "post"|"reel"|"yt-video"|"blog"|"news-article"|"website" } → 200 { topic, summary, description, remainingCredits }

Transactions (/transactions)
- GET /user → 200
- GET /credits → 200 { credits }
- GET /history → 200 { transactions }
- GET /history/:userId (admin) → 200 { transactions }
- POST /add { amount: number, currency: "USD"|"INR" } → 200 { order_id, currency, amount }
- POST /webhook (Razorpay) → 200 { msg }


## Error handling and operational notes

Global errors
- All uncaught exceptions are mapped to JSON 500 by [Python.handle_exception()](zyke-backend/app.py:57).

Per-module notes
- Auth: Razorpay customer creation may fail with “exists” error; code attempts a lookup and patch ([Python.verify_otp_route()](zyke-backend/auth.py:118), [Python.oauth_callback()](zyke-backend/auth.py:279)).
- Brand voice: Async tasks wrapped with event loop creation and proper close; failures bubble with a general “Failed to process brand voice.” ([Python.create_brand()](zyke-backend/brandvoiceinfo.py:1335)).
- Trends: Perplexity request errors map to “Failed to fetch trends” with log context.
- Transactions: Signature failures return 400 with explicit msg; idempotency checks avoid double crediting.

Observability
- Module‑level loggers are configured in auth, transactions, brandvoice modules. Consider central logging strategy in production.


## Security notes

- Secrets must be sourced from environment/secret manager. Do not commit service JSON. File present in repo: [zyke-backend/superb-firefly-437014-k4-7ac5371a47e8.json](zyke-backend/superb-firefly-437014-k4-7ac5371a47e8.json) — move out and reference via [Python.GOOGLE_CLOUD_JSON_AUTH_PATH](zyke-backend/config.py:24).
- CORS limited to production domains in [Python.create_app()](zyke-backend/app.py:26); transactions blueprint enables localhost:3000 for dev ([Python.transactions.py](zyke-backend/transactions.py:28)).
- OAuth insecure transport is enabled by [Python.os.environ['OAUTHLIB_INSECURE_TRANSPORT']='1'](zyke-backend/auth.py:44) for dev; remove in prod.
- Use HTTPS and Secure+SameSite cookies when setting auth cookies on prod.


## Performance and scalability

- Async web crawl bounded by semaphore and backoff: [Python.AsyncMultilingualScraper](zyke-backend/brandvoiceinfo.py:170), [Python.AsyncMultilingualScraper](zyke-backend/repurpose.py:118).
- Perplexity/OpenRouter/Together calls are aggregated for minimal round‑trips; Together image gen batches are throttled (every 3–4 prompts) in [Python.generate_content_async()](zyke-backend/idea_to_post.py:337).
- Trends cached for 6 hours; per‑user trend ideas cached likewise by policy.
- Use CDN or object store for large artifacts if persisting generated images long‑term (current flow returns base64 to client and stores structure, not images).


## Deployment playbook

- Gunicorn: see [bash start_flask.sh](zyke-backend/start_flask.sh) (5 workers, 127.0.0.1:5000).
- Reverse proxy: terminate TLS, pass through Authorization, set secure headers, and allow CORS origins configured in app.
- Secrets: inject via environment/secret store; never mount JSON secrets directly from repo.
- Health: consider adding a /health route (current root returns a welcome JSON).
- Logging: configure structured logs and capture external API error contexts.


## Testing strategy

Unit tests (recommend)
- XML parsers: [Python.extract_trend()](zyke-backend/trends.py:78), [Python.extract_trend_ideas()](zyke-backend/trend_to_idea.py:503), [Python.extract_topic_ideas()](zyke-backend/trend_to_idea.py:568), [Python.extract_posts()](zyke-backend/idea_to_post.py:292), [Python.extract_topic_info()](zyke-backend/repurpose.py:466)
- Blend math: [Python.dilate_mask()](zyke-backend/blend.py:13), [Python.blend_image()](zyke-backend/blend.py:27)
- Credit deduction happy/failed paths: [Python.deduct_and_log_user_credits()](zyke-backend/models.py:269)

Integration
- Brand voice end‑to‑end with mocked LLM/providers to verify cost aggregation and persistence.
- Trends→Ideas pipeline with cached and uncached paths.
- Ideas→Posts: verify structure and last posts persistence.

Payments
- Simulate order creation and webhook, assert [Python.update_transaction()](zyke-backend/models.py:127) and [Python.update_user_credits()](zyke-backend/models.py:244) behavior.

Tooling
- pytest + coverage; factory fixtures creating an app via [Python.create_app()](zyke-backend/app.py:22); vcrpy/moto‑style mocks for external HTTP.


## Extension guide

Add a new LLM provider
- Wrap provider call in a small adapter with standardized return (text/cost), wire into brand voice/trends/ideas modules; surface provider model and pricing in Config.

Support a new publishing platform
- Extend platform parameter handling in [Python.generate_content()](zyke-backend/idea_to_post.py:56) and adjust image prompt guidance accordingly.

Alternate inpainting backend
- Implement a function mirroring [Python.inpaint()](zyke-backend/inpaint.py:14) signature and route switch by query param or config flag.

Persist generated media
- Introduce an artifact store (GCS/S3) and store links instead of base64; adjust frontend export path accordingly.

Admin analytics
- Add endpoints to summarize total_costs log by user/date and enrich transactions view.


## Route matrix (public endpoints)

Public
- GET / → [Python.home()](zyke-backend/app.py:52)

Authenticated
- /auth: POST /login /refresh /logout /request-reset /reset-password /register /verify-otp /oauth/callback /oauth/login, GET /user
- /brand_voice_info: POST /create, GET /profile
- /trends: GET /fetch_trends
- /trend_to_idea: POST /generate_ideas
- /idea_to_post: POST /fetch_posts
- /fetch_last_post: POST /get_stored_post
- /blend: POST /blend_masks
- /inpaint: POST /inpaint_image
- /repurpose: POST /repurpose_url
- /transactions: GET /user /credits /history /history/:userId, POST /add, POST /webhook


## Known issues and refactor recommendations

- Collection naming mismatch
  - user_last_post vs user_last_posts across modules (e.g., [Python.user_last_posts_collection](zyke-backend/idea_to_post.py:40) vs [Python.collection](zyke-backend/fetch_last_post.py:9)). Unify with a constant.

- Misleading function name
  - [Python.inpaint_route()](zyke-backend/blend.py:138) in blend.py handles mask blend; rename to blend_masks() for clarity.

- Exception variable typo
  - In [Python.deduct_and_log_user_credits()](zyke-backend/models.py:327) the exception block uses undefined variable “e” when building error_msg; should use “ex”.

- Duplicated declarations
  - user_trends_collection and user_last_post_collection are declared twice in [zyke-backend/models.py](zyke-backend/models.py). Retain only a single definition.

- Secret JSON in repository
  - Remove [zyke-backend/superb-firefly-437014-k4-7ac5371a47e8.json](zyke-backend/superb-firefly-437014-k4-7ac5371a47e8.json) from VCS; parameterize path via env.

- OAuth flow contract
  - Current callback expects frontend JSON POST; consider server-side token exchange using Authlib to simplify the client and reduce cookie/token handling ambiguity.


## Glossary

- Brand Voice: Consolidated brand corpus combining website/file context with social post style analysis.
- Trend: A time-sensitive topic enriched with summary/description via Perplexity.
- Idea: A brand‑aligned, trend‑ or topic‑derived seed including a name and description.
- Post: Generated artifact comprising caption + one or more images.
- Mask: Binary image delineating a region for blending or inpainting.
- Inpainting: Model‑guided synthesis constrained to a mask over an input image.
- Credits: Abstracted unit representing spend against third‑party compute (LLMs, image gen).