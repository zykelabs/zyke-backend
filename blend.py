from flask import Blueprint, request, jsonify
import cv2
import numpy as np
from PIL import Image
import io
from io import BytesIO
import base64
# import matplotlib.pyplot as plt

# Create a blueprint for blending
blend_image_bp = Blueprint('blend', __name__)

def dilate_mask(mask, dilate_size):
  mask = mask.astype(np.uint8)
  kernel = np.ones(dilate_size,np.uint8) # You can adjust the kernel size for dilation
  # plt.imshow(mask)
  # print(type(mask))
  # print(mask.shape)
  # print(mask.dtype)
  # print(kernel)
  dilated_mask = cv2.dilate(mask, kernel, iterations = 1) # Dilate the mask

  # plt.imshow(dilated_mask, cmap = 'gray')

  return dilated_mask

def blend_image(img, mask, alpha = 0.6, col = 'b', dilate = True, dilate_size = (17,17)):
  # print(img.shape)
  # print(mask.shape)
  # print("\n\n")
  dilated_mask = mask
  
  if dilate:
    dilated_mask = dilate_mask(mask, dilate_size)
  
  # print(dilated_mask.shape)
  dilated_mask_image = Image.fromarray(dilated_mask)
  resized_dilated_mask = dilated_mask_image.resize((img.shape[1],img.shape[0]), Image.LANCZOS)
  resized_dilated_mask_array = np.array(resized_dilated_mask)
  # print(resized_dilated_mask_array.shape)

  blended_image = img.copy().astype(np.uint8)
  # print(blended_image.shape)
  # print("\n\n")
  col = col.lower().strip()

  # # print(resized_dilated_mask_array.shape)
  # print(type(blended_image), blended_image.shape, blended_image.dtype)
  # print(type(resized_dilated_mask_array), resized_dilated_mask_array.shape, resized_dilated_mask_array.dtype)

  rgb_mask = resized_dilated_mask_array[:,:,None] * [1, 1, 1]
  # print(rgb_mask.shape)
  blue_mask = resized_dilated_mask_array[:,:,None] * [0, 0, 1]
  # print(blue_mask.shape)
  if col == 'r':
    blue_mask = resized_dilated_mask_array[:,:,None] * [1, 0, 0]
  elif col == 'g':
    blue_mask = resized_dilated_mask_array[:,:,None] * [0, 1, 0]
  elif col == 'w':
    blue_mask = resized_dilated_mask_array[:,:,None] * [1, 1, 1]

  if rgb_mask.max() == 1:
    rgb_mask *= 255
    blue_mask *= 255

  blended_image[rgb_mask == 255] = blue_mask[rgb_mask == 255] * alpha + blended_image[rgb_mask == 255] * (1 - alpha)
  # plt.imshow(blended_image)
  # plt.show()
  # blended_image = Image.fromarray(blended_image.astype(np.uint8))
  # blended_image.save("blended_image.png")
  
  # Create a figure with 1 row and 3 columns
  # fig, axes = plt.subplots(1, 4, figsize=(15, 5))

  # Display each image
  # axes[0].imshow(mask)
  # axes[0].set_title("mask")
  # axes[0].axis("off")  # Hide axes
  
  # # Display each image
  # axes[1].imshow(img)
  # axes[1].set_title("image")
  # axes[1].axis("off")  # Hide axes

  # axes[2].imshow(resized_dilated_mask_array)
  # axes[2].set_title("dilated mask")
  # axes[2].axis("off")  # Hide axes

  # axes[3].imshow(blended_image)
  # axes[3].set_title("blended image")
  # axes[3].axis("off")  # Hide axes

  # # Display the plot
  # plt.tight_layout()
  # plt.show()
  
  return blended_image, resized_dilated_mask_array

def convert_array_to_base64_string(array):
  # Convert the NumPy array to a PIL image
  image = Image.fromarray(array)

  # Save the image to a bytes buffer
  buffer = io.BytesIO()
  format_img = "PNG"
  image.save(buffer, format=format_img)

  # Encode the buffer to base64
  base64_string = base64.b64encode(buffer.getvalue()).decode("utf-8")
  base64_string = f"data:image/{format_img.lower()};base64,{base64_string}"
  return base64_string

def convert_base64_string_to_array(base64_string_data, img_type):
  # Convert the NumPy array to a PIL image
  base64_string = base64_string_data.split(",")[1]
  image_data = base64.b64decode(base64_string)
  image = None
  if img_type == "image":
    image = Image.open(BytesIO(image_data)).convert('RGB')
  elif img_type == "mask":
    image = Image.open(BytesIO(image_data)).convert('L')
  image_np = np.array(image)

  return image_np

def blend_all_imgs(img, msks, alpha = 0.6, col = 'b', dilate = True, dilate_size = (5,5)):
  blended_imgs = []
  dilated_msks = []
  img_arr = convert_base64_string_to_array(img, "image")
  for msk in msks:
    mask_arr = convert_base64_string_to_array(msk, "mask")
    blended_img, dilated_msk = blend_image(img_arr, mask_arr, alpha, col, dilate, dilate_size)
    # print(dilated_msk.max())
    blended_imgs.append(convert_array_to_base64_string(blended_img))
    dilated_msks.append(convert_array_to_base64_string(dilated_msk))
  return blended_imgs, dilated_msks

@blend_image_bp.route('blend_masks', methods=['POST'])
def inpaint_route():
  data = request.json
  masks = data.get("masks")
  img = data.get("img")

  if not img or not masks:
    return jsonify({'error': 'img and masks are required'}), 400

  # try:
  blended_imgs, dilated_msks = blend_all_imgs(img, masks)
  return jsonify({"status": "success", "blended_images": blended_imgs, "dilated_masks": dilated_msks}), 200

  # except Exception as e:
  #   print(f"Error in blending images: {e}")
  #   return jsonify({'error': 'An internal server error occurred.'}), 500