from flask import Blueprint, request, jsonify
import requests
import base64
import io
from config import Config
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import get_user_credits, deduct_and_log_user_credits

# Create a blueprint for inpainting
inpainting_bp = Blueprint('inpaint', __name__)

stability_api_key = Config.STABILITY_AI_API_KEY

def inpaint(img, mask, prompt=None, neg_prompt=None, remove="True"):
    key = stability_api_key
    if remove == "true":
      prompt = "blend the highlighted part with the rest of the image, merge it with the background. fill the whole portion, do not leave the generated part partially/fully empty. no text, no empty image generation, no blank image generation, no same part in a different manner."
      neg_prompt = "unfilled image, partially unfilled image, text, any text, characters, alphabets, words, same portion, same part, same part in a different manner, part not blended with the rest image, empty part, empty image, blank image, blank part"
    elif prompt is None:
      raise ValueError("Prompt given is None, which is only compatible if remove = True, i.e. you want to remove the image. Please provide a prompt or make remove = True.")

    if neg_prompt is None:
      neg_prompt = ""

    base64_string = img.split(",")[1]
    image_data = base64.b64decode(base64_string)
    buffered_image = io.BytesIO(image_data)
    buffered_reader_image = io.BufferedReader(buffered_image)

    base64_string_mask = mask.split(",")[1]
    image_data_mask = base64.b64decode(base64_string_mask)
    buffered_mask = io.BytesIO(image_data_mask)
    buffered_reader_mask = io.BufferedReader(buffered_mask)

    response = requests.post(
        f"https://api.stability.ai/v2beta/stable-image/edit/inpaint",
        headers={
            "authorization": key,
            "accept": "image/*"
        },
        files={
            "image": buffered_reader_image,
            "mask": buffered_reader_mask,
        },
        data={
            "prompt": prompt,
            "negative_prompt": neg_prompt,
            "output_format": "webp",
        },
    )
    
    cost = 0.03

    if response.status_code == 200:
      base64_encoded_image = base64.b64encode(response.content).decode('utf-8')
      base64_image_uri = f"data:image/webp;base64,{base64_encoded_image}"
      return base64_image_uri, cost
    else:
      return f"Error: {str(response.json())}", 0

@inpainting_bp.route('/inpaint_image', methods=['POST'])
@jwt_required()
def inpaint_route():
  user_id = get_jwt_identity()
  data = request.json
  img = data.get("image")
  mask = data.get("mask")
  prompt = data.get("prompt")
  neg_prompt = data.get("neg_prompt")
  remove = data.get("remove")

  if not img or not mask:
    print({'error': 'image and mask are compulosrily required'})
    return jsonify({'error': 'img and mask are compulosrily required'}), 400

  if not remove and not prompt:
    print({'error': 'either remove or prompt is required'})
    return jsonify({'error': 'either remove or prompt is required'}), 400

  try:
    # Fetch the user's current credits
    user_credits = get_user_credits(user_id)
    if user_credits is None:
      return jsonify({'error': 'User not found'}), 404

    # Check if the user has enough credits
    if user_credits <= 0:
      return jsonify({'error': 'Insufficient credits to repurpose content.'}), 402

    result, cost = inpaint(img, mask, prompt, neg_prompt, remove)

    # Deduct credits and log the transaction
    deduction_description = f"Inpainting image content for user: {user_id}"
    success, error_msg = deduct_and_log_user_credits(user_id, cost, deduction_description, transaction_type="inpaint_image")

    if not success:
        # Return the specific error message captured
        return jsonify({"error": error_msg}), 500

    # Fetch updated credits
    updated_credits = get_user_credits(user_id)

    return jsonify({"status": "success", "result": result, 'remainingCredits': updated_credits})
  
  except Exception as e:
    print(f"Error in inpainting images: {e}")
    return jsonify({'error': 'An internal server error occurred.'}), 500