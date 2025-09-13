import os
import requests # Ensure requests is imported for Stability AI
import base64
import groq
from dotenv import load_dotenv
import re
from tavily import TavilyClient
# import openai # No longer needed if not using DALL-E

load_dotenv()
def generate_image(prompt: str) -> str:
    """Generates an image based on the given prompt using Stability AI API."""
    STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
    if not STABILITY_API_KEY:
        return "Error: Stability AI API key not found. Please set STABILITY_API_KEY in your .env file."
    try:
        response = requests.post(
            "[https://api.stability.ai/v2beta/stable-image/generate/core](https://api.stability.ai/v2beta/stable-image/generate/core)",
            headers={
                "authorization": f"Bearer {STABILITY_API_KEY}",
                "accept": "image/*"
            },
            files={"prompt": (None, prompt), "output_format": (None, "png")},
        )
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        image_bytes = response.content
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{base64_image}"
    except requests.exceptions.RequestException as req_e:
        return f"Error: Failed to connect to Stability AI API. Network or API issue: {req_e}"
    except Exception as e:
        return f"Error: Could not generate the image using Stability AI. {e}"