# Zyke Backend — AI-Powered Social Media Automation (Flask Services)

Production-ready Flask API that powers authentication, brand intelligence, trends → ideas → posts generation, image blending/inpainting, and credits/payments for Zyke’s end-to-end content pipeline.

<p align="center">
  <a href="https://flask.palletsprojects.com/">Flask</a> •
  <a href="https://flask-jwt-extended.readthedocs.io/">Flask-JWT-Extended</a> •
  <a href="https://docs.authlib.org/">Authlib (OIDC)</a> •
  <a href="https://www.mongodb.com/">MongoDB (PyMongo)</a> •
  <a href="https://razorpay.com/docs/">Razorpay</a> •
  <a href="https://openrouter.ai/">OpenRouter</a> •
  <a href="https://www.perplexity.ai/">Perplexity</a> •
  <a href="https://cloud.google.com/vertex-ai">Vertex AI (Gemini)</a> •
  <a href="https://www.together.ai/">Together AI (Images)</a> •
  <a href="https://platform.stability.ai/">Stability AI</a> •
  <a href="https://apify.com/">Apify</a> •
  <a href="https://brightdata.com/">Bright Data</a>
</p>

---

## TL;DR

- App factory registers modular Blueprints for auth, brand voice creation, trend ingestion, ideas, post generation, image processing, and payments.
- JWT auth, Google OAuth (OIDC), OTP email verification, password reset.
- Brand voice pipeline combines async web crawling, Perplexity/OpenRouter LLMs, optional Instagram analysis via Gemini, and credit metering.
- Trends → ideas → posts: generate captions + multiple images per post; images via Together; last-bundle persisted per user.
- Image utilities: mask blend previews and Stability AI inpainting with cost tracking.
- Credits via Razorpay; signature-verified webhooks credit user balance.

Key entries:
- App shell: [Python.create_app()](zyke-backend/app.py:22), CORS and registry
- Auth: [Python.register()](zyke-backend/auth.py:75), [Python.verify_otp_route()](zyke-backend/auth.py:118), [Python.login()](zyke-backend/auth.py:202), [Python.oauth_callback()](zyke-backend/auth.py:279), [Python.refresh()](zyke-backend/auth.py:376)
- Brand voice: [Python.create_brand()](zyke-backend/brandvoiceinfo.py:1335), profile read [Python.get_profile()](zyke-backend/brandvoiceinfo.py:1628)
- Trends → Ideas: [Python.get_trends()](zyke-backend/trends.py:114), [Python.generate_ideas_api()](zyke-backend/trend_to_idea.py:626)
- Ideas → Posts: [Python.generate_posts_api()](zyke-backend/idea_to_post.py:405), parse posts [Python.extract_posts()](zyke-backend/idea_to_post.py:292)
- Images: blend [Python.inpaint_route()](zyke-backend/blend.py:138), inpaint [Python.inpaint_route()](zyke-backend/inpaint.py:61)
- Payments: [Python.add_credits()](zyke-backend/transactions.py:159), webhook [Python.handle_webhook()](zyke-backend/transactions.py:352)

---

## Table of Contents

- What is Zyke Backend?
- Feature Highlights
- Architecture Overview
- Repository Structure
- Getting Started
- Environment Variables
- Scripts
- Core Flows (Step-by-step)
- Key Files & Constructs
- API Overview
- Security & Privacy
- Troubleshooting (FAQ)
- Roadmap
- License
- Acknowledgements

---

## What is Zyke Backend?

Zyke Backend is a set of Flask services that power the complete creative loop for social media:
- Authenticate users and manage credentials/credits
- Construct a brand’s voice from web + social footprints
- Ingest current trends or repurpose external URLs into topic ideas
- Turn ideas into platform-ready posts (captions + multiple images)
- Provide in-browser image refinement with mask blending and inpainting
- Manage credit purchases and update balances via Razorpay webhooks

For a deep technical tour, see the comprehensive documentation: [zyke-backend/DOC.md](zyke-backend/DOC.md)

---

## Feature Highlights

- Authentication
  - Email/password with OTP verification: [Python.register()](zyke-backend/auth.py:75) → [Python.verify_otp_route()](zyke-backend/auth.py:118)
  - Google OAuth (OIDC) via Authlib: [Python.oauth_init_app()](zyke-backend/auth.py:51), [Python.oauth_callback()](zyke-backend/auth.py:279)
  - Reset and refresh: [Python.request_reset()](zyke-backend/auth.py:232), [Python.reset_password()](zyke-backend/auth.py:250), [Python.refresh()](zyke-backend/auth.py:376)

- Brand Voice
  - Async web crawl + LLM consolidation: [Python.brand_info_scrape()](zyke-backend/brandvoiceinfo.py:727)
  - Instagram style analysis (optional): [Python.brand_post_info_scrape()](zyke-backend/brandvoiceinfo.py:1202)
  - Credit metering and persistence to Mongo

- Trends → Ideas
  - Google Trends merged with Perplexity reasoning: [Python.get_trends()](zyke-backend/trends.py:114)
  - Ideas shaped by brand corpora: [Python.generate_ideas_api()](zyke-backend/trend_to_idea.py:626)

- Ideas → Posts
  - Captions + multi-image prompts: [Python.generate_content()](zyke-backend/idea_to_post.py:56)
  - Image generation via Together: [Python.generate_images()](zyke-backend/idea_to_post.py:261)
  - Persist “last posts” bundle per user

- Image Editing
  - Blend mask preview overlays: [Python.inpaint_route()](zyke-backend/blend.py:138)
  - StabilityAI inpainting with guardrails: [Python.inpaint()](zyke-backend/inpaint.py:14)

- Credits & Payments
  - Order creation and signature-verified webhook reconciliation: [Python.add_credits()](zyke-backend/transactions.py:159), [Python.handle_webhook()](zyke-backend/transactions.py:352)

---

## Architecture Overview

Backend (this repo)
- Flask app factory: [Python.create_app()](zyke-backend/app.py:22) wires CORS, JWT, OAuth, Mail, and registers Blueprints.
- Blueprints:
  - /auth, /brand_voice_info, /trends, /trend_to_idea, /idea_to_post, /fetch_last_post, /blend, /inpaint, /repurpose, /transactions, /webhooks
- Data: MongoDB via PyMongo with collections for users, brand profiles/voices, transactions, trend caches, user trends cache, and user last posts.

External providers
- LLMs: OpenRouter (chat), Perplexity (online grounding), Gemini (multimodal descriptions via Vertex), Together (image gen), Stability (inpainting)
- Data sources: Apify / Bright Data (Instagram)

Top-level app constructs
- App factory: [Python.create_app()](zyke-backend/app.py:22)
- Home route: [Python.home()](zyke-backend/app.py:52)
- Error mapping: [Python.handle_exception()](zyke-backend/app.py:57)

---

## Repository Structure

```
zyke-backend/
  app.py
  auth.py
  blend.py
  brand.py
  brandvoiceinfo.py
  config.py
  emailservice.py
  fetch_last_post.py
  idea_to_post.py
  inpaint.py
  models.py
  otp.py
  repurpose.py
  transactions.py
  trends.py
  trend_to_idea.py
  utils.py
  requirements.txt
  start_flask.sh
  DOC.md
  README.md
```

---

## Getting Started

Prerequisites
- Python 3.10+
- A running MongoDB instance (MONGO_URI)

Install
```
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r zyke-backend/requirements.txt
```

Development
```
# Ensure .env is present (see Environment Variables)
python zyke-backend/app.py
# or
python -m flask --app zyke-backend/app.py run
```

Production (Gunicorn)
- Launch via script: [bash start_flask.sh](zyke-backend/start_flask.sh) (5 workers, 127.0.0.1:5000)
- Put Nginx/ALB in front with TLS and CORS aligned to your domains

---

## Environment Variables

Populate a .env for backend process (loaded by [Python.Config](zyke-backend/config.py:5)):

| Name | Required | Description |
| ---- | -------- | ----------- |
| MONGO_URI | Yes | MongoDB connection string |
| JWT_SECRET_KEY | Yes | Secret for Flask-JWT-Extended |
| MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER | Optional | Mailer for OTP/reset ([Python.init_mail()](zyke-backend/emailservice.py:8)) |
| FRONTEND_URL, BACKEND_URL | Yes | Base URLs for email links / CORS |
| GOOGLE_CLOUD_PROJECT | Optional | Vertex/Gemini project |
| GOOGLE_CLOUD_JSON_AUTH_PATH | Optional | Relative path to service account JSON (avoid committing) |
| APIFY_API_KEY | Optional | Instagram scrape |
| BRIGHT_DATA_TOKEN, BRIGHT_DATA_INSTA_POST_DATASET_ID, BRIGHT_DATA_INSTA_REEL_DATASET_ID | Optional | Bright Data datasets |
| RAZORPAY_KEY, RAZORPAY_SECRET, RAZORPAY_WEBHOOK_SECRET | Yes | Payments + signature verification |
| DEEPINFRA_API_KEY, OPENROUTER_API_KEY, PERPLEXITY_TOKEN, TOGETHER_API_KEY, OPENAI_API_KEY, STABILITY_AI_API_KEY | Yes (per used features) | Model providers |
| GOOGLE_API_KEY, GOOGLE_CSE_ID | Optional | Google custom search |

References in code:
- [Python.Config](zyke-backend/config.py:5), [Python.create_app()](zyke-backend/app.py:22), [Python.oauth_init_app()](zyke-backend/auth.py:51)

---

## Scripts

- Development server
  - python zyke-backend/app.py
  - python -m flask --app zyke-backend/app.py run
- Production
  - Gunicorn starter: [bash start_flask.sh](zyke-backend/start_flask.sh)

---

## Core Flows (Step-by-step)

1) Authentication
- Register: [Python.register()](zyke-backend/auth.py:75) → OTP mail [Python.send_otp_email()](zyke-backend/emailservice.py:18)
- Verify OTP → create user + Razorpay linkage + tokens: [Python.verify_otp_route()](zyke-backend/auth.py:118)
- Login / Logout / Refresh: [Python.login()](zyke-backend/auth.py:202), [Python.logout()](zyke-backend/auth.py:396), [Python.refresh()](zyke-backend/auth.py:376)
- Forgot/reset: [Python.request_reset()](zyke-backend/auth.py:232) → [Python.reset_password()](zyke-backend/auth.py:250)

2) Brand Voice (profile + voice corpora)
- POST /brand_voice_info/create: [Python.create_brand()](zyke-backend/brandvoiceinfo.py:1335)
  - Scrape websites (async) + summarize via LLMs
  - Optional Instagram multimodal analysis → style corpus
  - Aggregate cost → deduct credits → persist profile+voice

3) Trends → Ideas
- GET /trends/fetch_trends: [Python.get_trends()](zyke-backend/trends.py:114)
- POST /trend_to_idea/generate_ideas: [Python.generate_ideas_api()](zyke-backend/trend_to_idea.py:626)
  - use="trend" with list, or "topic" (repurposed), or "manual"

4) Ideas → Posts
- POST /idea_to_post/fetch_posts: [Python.generate_posts_api()](zyke-backend/idea_to_post.py:405)
  - Validate brand corpora → generate captions + image prompts → generate images → store last bundle

5) Image Editing (in modal on frontend)
- Blend masks preview: POST /blend/blend_masks → [Python.inpaint_route()](zyke-backend/blend.py:138)
- Inpaint masked region: POST /inpaint/inpaint_image → [Python.inpaint_route()](zyke-backend/inpaint.py:61)

6) Credits & Payments
- Create order: POST /transactions/add → [Python.add_credits()](zyke-backend/transactions.py:159)
- Webhook reconcile: POST /transactions/webhook → [Python.handle_webhook()](zyke-backend/transactions.py:352)

---

## Key Files & Constructs

- App factory: [Python.create_app()](zyke-backend/app.py:22), Home [Python.home()](zyke-backend/app.py:52), Errors [Python.handle_exception()](zyke-backend/app.py:57)
- Auth: [Python.register()](zyke-backend/auth.py:75), [Python.verify_otp_route()](zyke-backend/auth.py:118), [Python.login()](zyke-backend/auth.py:202), [Python.oauth_callback()](zyke-backend/auth.py:279), [Python.refresh()](zyke-backend/auth.py:376), [Python.get_current_user()](zyke-backend/auth.py:403)
- Brand voice: [Python.create_brand()](zyke-backend/brandvoiceinfo.py:1335), [Python.brand_info_scrape()](zyke-backend/brandvoiceinfo.py:727), [Python.brand_post_info_scrape()](zyke-backend/brandvoiceinfo.py:1202)
- Trends & Ideas: [Python.get_trends()](zyke-backend/trends.py:114), [Python.generate_ideas_api()](zyke-backend/trend_to_idea.py:626)
- Posts: [Python.generate_posts_api()](zyke-backend/idea_to_post.py:405), [Python.generate_content()](zyke-backend/idea_to_post.py:56), [Python.extract_posts()](zyke-backend/idea_to_post.py:292), [Python.generate_images()](zyke-backend/idea_to_post.py:261)
- Images: [Python.inpaint_route()](zyke-backend/blend.py:138), [Python.inpaint_route()](zyke-backend/inpaint.py:61), [Python.inpaint()](zyke-backend/inpaint.py:14)
- Transactions: [Python.add_credits()](zyke-backend/transactions.py:159), [Python.handle_webhook()](zyke-backend/transactions.py:352)
- Models & credits: [Python.deduct_and_log_user_credits()](zyke-backend/models.py:269), [Python.get_user_credits()](zyke-backend/models.py:239), [Python.update_user_credits()](zyke-backend/models.py:244)

---

## API Overview

Auth (/auth)
- POST /register → email OTP
- POST /verify-otp → create user + set cookies
- POST /login → tokens in JSON
- POST /request-reset → mail link
- POST /reset-password (Bearer) → update hash
- GET /oauth/login → redirect
- POST /oauth/callback → tokens via cookies
- POST /refresh → new access_token
- POST /logout → clear cookies
- GET /user (Bearer) → user snapshot

Brand Voice (/brand_voice_info)
- POST /create (multipart/form-data) → { summary, instagramDescriptions, remainingCredits }
- GET /profile (Bearer) → normalized profile + voice

Trends (/trends)
- GET /fetch_trends → cached + enriched list

Trend → Ideas (/trend_to_idea)
- POST /generate_ideas → { ideas, cached? }

Ideas → Posts (/idea_to_post)
- POST /fetch_posts → { saved: true, remainingCredits }

Last Posts (/fetch_last_post)
- POST /get_stored_post → last bundle for user

Images
- POST /blend/blend_masks → { blended_images[], dilated_masks[] }
- POST /inpaint/inpaint_image → { result, remainingCredits }

Repurpose (/repurpose)
- POST /repurpose_url → { topic, summary, description, remainingCredits }

Transactions (/transactions)
- GET /user /credits /history /history/:userId (admin)
- POST /add → Razorpay order
- POST /webhook → payment capture reconcile

All authenticated calls include Authorization: Bearer <accessToken>.

---

## Security & Privacy

- Secrets via environment only. Do not commit service account JSON. The file [zyke-backend/superb-firefly-437014-k4-7ac5371a47e8.json](zyke-backend/superb-firefly-437014-k4-7ac5371a47e8.json) must be moved out of VCS and referenced by GOOGLE_CLOUD_JSON_AUTH_PATH.
- CORS is restricted to production domains in [Python.create_app()](zyke-backend/app.py:26); the transactions blueprint allows localhost:3000 for dev ([Python.transactions.py](zyke-backend/transactions.py:28)).
- Use HTTPS + Secure cookies in production; disable [Python.os.environ['OAUTHLIB_INSECURE_TRANSPORT']='1'](zyke-backend/auth.py:44).

---

## Troubleshooting (FAQ)

- 401 Unauthorized on protected routes
  - Ensure Authorization header is present and tokens are fresh; refresh via [Python.refresh()](zyke-backend/auth.py:376).
- “Insufficient credits” on generation flows
  - Check balance via [Python.get_user_credits_route()](zyke-backend/transactions.py:138).
- Razorpay order succeeds but credits not updated
  - Check webhook signature and logs in [Python.handle_webhook()](zyke-backend/transactions.py:352).
- Inpainting returns error
  - Validate Stability API key and base64 inputs; see [Python.inpaint()](zyke-backend/inpaint.py:14).

---

## Roadmap

Near-term
- Unify collection names (user_last_posts) across modules
- Rename blend endpoint handler to descriptive name
- Centralize logging and add /health readiness/liveness endpoints

Mid-term
- Provider adapters with feature flags for quick swap/fallback
- Media persistence to object storage + signed URLs

Long-term
- Admin analytics: credit spend dashboards, per-user heatmaps
- Multiplatform post templates and export targets

---

## License

Proprietary. All rights reserved.

---

## Acknowledgements

- Flask and Python ecosystem
- Razorpay for payments
- OpenRouter, Perplexity, Vertex/Gemini, Together, Stability AI for ML services
- Apify and Bright Data for social data pipelines

For exhaustive internal details, see: [zyke-backend/DOC.md](zyke-backend/DOC.md)