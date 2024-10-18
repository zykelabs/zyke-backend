from requests_oauthlib import OAuth2Session
from config import Config
import requests
from flask import request

def get_google_provider_cfg():
    return requests.get(Config.GOOGLE_DISCOVERY_URL).json()

def oauth_init(authorization_endpoint):
    google = OAuth2Session(Config.GOOGLE_CLIENT_ID, redirect_uri="http://localhost:3000/auth/google-callback", scope=["openid", "email", "profile"])
    request_uri, state = google.authorization_url(authorization_endpoint)
    return request_uri
0
def fetch_google_user_info():
    google = OAuth2Session(Config.GOOGLE_CLIENT_ID, redirect_uri="http://localhost:3000/auth/google-callback", scope=["openid", "email", "profile"])

    token_url = get_google_provider_cfg()["token_endpoint"]
    google.fetch_token(token_url, client_secret=Config.GOOGLE_CLIENT_SECRET, authorization_response=request.url)

    userinfo_endpoint = get_google_provider_cfg()["userinfo_endpoint"]
    userinfo_response = google.get(userinfo_endpoint)

    if userinfo_response.json().get("email_verified"):
        return userinfo_response.json()

    return None
