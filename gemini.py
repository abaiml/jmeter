import os
from google import genai

# Set your API key here or use an environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the client
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_with_gemini(prompt):
    """
    Generate text from Gemini using a prompt.

    Args:
        prompt (str): Text prompt to send to Gemini.
        model (str): Model version (default: gemini-2.0-flash).

    Returns:
        str: Generated text response.
    """
    try:
        print(prompt)
        response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
        return response.text.strip() if hasattr(response, "text") else "❌ No text found in response."
    except Exception as e:
        return f"❌ Gemini error: {str(e)}"
