from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    create_brand_profile,
    get_brand_profile,
    create_brand_voice,
    update_brand_voice
)
from utils import validate_url
import logging
import asyncio
from datetime import datetime
from brandvoiceinfo import brand_info_scrape

brand_bp = Blueprint('brand', __name__, url_prefix='/brand')


