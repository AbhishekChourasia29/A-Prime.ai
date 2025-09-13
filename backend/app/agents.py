import os
import requests
import base64
import groq
from dotenv import load_dotenv
import re
from tavily import TavilyClient

load_dotenv()

# --- Global API Client Initializations ---

# Define Stability AI API URL as a plain string constant
STABILITY_API_BASE_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"

# Groq Client
groq_client = None
try:
    groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
    print("Groq client initialized successfully.")
except Exception as e:
    print(f"Could not initialize Groq client: {e}")
    groq_client = None

# Tavily Client
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = None
if TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("Tavily client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Tavily client: {e}")
else:
    print("TAVILY_API_KEY environment variable not set. Tavily search functionality will be limited or disabled.")

# Stability AI API Key Status
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
stability_api_status = False
if STABILITY_API_KEY:
    stability_api_status = True
    print("Stability AI API key loaded successfully.")
else:
    print("STABILITY_API_KEY environment variable not found. Stability AI image generation will be disabled.")


# --- Helper function to clean history ---
def _clean_history_for_api(history: list[dict]) -> list[dict]:
    """Removes any keys from the history that are not 'role' or 'content'. Converts 'text' to 'content'."""
    cleaned_history = []
    for message in history:
        cleaned_history.append({
            "role": message.get("role"),
            "content": message.get("content") or message.get("text") # Handle both 'content' and 'text'
        })
    return cleaned_history

def _call_groq(messages, model="gemma2-9b-it"):
    """Helper function to call the Groq API and handle exceptions."""
    if not groq_client:
        raise Exception("Groq client is not initialized. Check your API key.")
    
    # Clean the messages right before sending them to the API
    cleaned_messages = _clean_history_for_api(messages)
    
    return groq_client.chat.completions.create(
        messages=cleaned_messages,
        model=model,
    )

def general_chat(chat_history: list[dict]) -> str:
    """Handles general chat queries using the Groq API."""
    try:
        completion = _call_groq(chat_history)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not process chat. {e}"

def summarize_text(text: str) -> str:
    """Summarizes the given text using the Groq API."""
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes text concisely."},
            {"role": "user", "content": f"Summarize the following text: {text}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not summarize text. {e}"

def tavily_search(query: str) -> str:
    """Searches the web for the given query using Tavily API."""
    if not tavily_client:
        return "Error: Tavily API Key is not configured for web search. Please set TAVILY_API_KEY."
    try:
        response = tavily_client.search(query=query, search_depth="basic", include_answer=True)
        
        if response.get("answer"):
            return response["answer"]
        
        snippets = [result.get("content") for result in response.get("results", []) if result.get("content")]
        
        if not snippets:
            return "Sorry, I couldn't find any relevant information online using Tavily."
        
        context = " ".join(snippets)
        
        messages = [
            {"role": "system", "content": "Answer based *only* on the provided search snippets. If you cannot answer, say you couldn't find information."},
            {"role": "user", "content": f"Search Results: {context}\n\nBased on the above, answer: {query}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Failed to search the web using Tavily. {e}"

def simple_groq_search(query: str) -> str:
    """Answers a question based on Groq's internal knowledge without a web search."""
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that answers questions concisely and accurately from your existing knowledge. Do not perform a web search."},
            {"role": "user", "content": f"Answer the following question: {query}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not get a response from Groq. {e}"


def answer_question(context: str, query: str) -> str:
    """Answers a question based on provided context using the Groq API."""
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not answer question. {e}"

def generate_code(prompt: str) -> str:
    """Generates code based on the given prompt using the Groq API."""
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates code. Provide code within triple backticks (```python)."},
            {"role": "user", "content": f"Generate code for: {prompt}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not generate code. {e}"

def generate_image(prompt: str) -> str:
    """Generates an image based on the given prompt using Stability AI API."""
    global stability_api_status
    if not stability_api_status:
        return "Error: Stability AI API key not found. Image generation is disabled."
    
    try:
        response = requests.post(
            STABILITY_API_BASE_URL,
            headers={
                "authorization": f"Bearer {STABILITY_API_KEY}",
                "accept": "image/*"
            },
            files={"prompt": (None, prompt), "output_format": (None, "png")},
        )
        response.raise_for_status()
        image_bytes = response.content
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{base64_image}"
    except requests.exceptions.RequestException as req_e:
        return f"Error: Failed to connect to Stability AI API. Network or API issue: {req_e}"
    except Exception as e:
        print(f"API Error in generate_image: {e}")
        return f"Error: Could not generate the image using Stability AI. {e}"

def route_to_agent(user_prompt: str, chat_history: list[dict]) -> tuple[str, str]:
    """
    Routes the user's prompt. It can either return a task name (str) or a direct answer (str).
    Now includes a hardcoded check for identity questions.
    """
    # --- Identity Check (Hardcoded for immediate response) ---
    # NOTE: Please replace the placeholder links with the actual URLs.
    identity_keywords = ["who are you", "your name", "who built you", "who developed you", "who is your creator", "who make you","who create you","who build you", "what's your name", "what is your name"]
    if any(keyword in user_prompt.lower() for keyword in identity_keywords):
        print("--- ROUTER DECISION: 'identity' (Direct Response) ---")
        identity_response = """I am **A-Prime.ai**, a Multi-Agent Assistant.

The 'A' in my name stands for Abhishek, my developer. His full name is **Abhishek Chourasia**.

You can learn more about his work and connect with him here:
- **LinkedIn:** [https://www.linkedin.com/in/abhishek291203/](https://www.linkedin.com/in/abhishek291203/)
- **Portfolio Website:** [https://abhishekchourasia29.github.io/resume.ai/](https://abhishekchourasia29.github.io/resume.ai/)
"""
        # Return the 'chat' task so the main loop can just display this message
        return "chat", identity_response

    # --- LLM-based Routing for other tasks ---
    system_prompt = """You are an extremely efficient routing assistant. Your only purpose is to analyze a user's prompt and classify it into one of the following categories.
    Respond with ONLY ONE single word. Do not add any explanation, punctuation, or any other text.

    The categories are:
    - 'summarize' (For requests to shorten or condense text)
    - 'tavily_search' (For questions about current events, real-time information, news, or if explicitly asked to search the web)
    - 'groq_search' (For general knowledge questions like historical facts or common science)
    - 'qna' (For answering a question based on previous conversation context)
    - 'code' (For requests to write or explain programming code)
    - 'image' (For requests to generate an image)
    - 'chat' (For all other general conversation, greetings, or unclear requests)

    Your response MUST be one of the single words from the list above.
    """

    messages_for_intent = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        completion = _call_groq(messages_for_intent, model="gemma2-9b-it")
        task = completion.choices[0].message.content.strip().lower()
        print(f"--- ROUTER DECISION: '{task}' ---")

        valid_tasks = ["summarize", "tavily_search", "groq_search", "qna", "code", "image", "chat"]
        if task in valid_tasks:
            return task, user_prompt # Return the original prompt for the agent to use
        else:
            # Fallback for safety
            return "chat", user_prompt
    except Exception as e:
        print(f"Error calling LLM for intent recognition: {e}. Defaulting to 'chat'.")
        return "chat", user_prompt

# Example of how you might use this in a main loop
if __name__ == '__main__':
    # This is a simplified example loop to show how the functions work together.
    chat_history = []
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['exit', 'quit']:
            break

        chat_history.append({"role": "user", "content": user_input})
        
        # The router now returns the task and the content to be processed
        task, content = route_to_agent(user_input, chat_history)

        response = ""
        if task == "chat":
            # If the router returned the identity response, 'content' will be that response.
            # Otherwise, it's a general chat.
            if "A-Prime.ai" in content:
                 response = content
            else:
                 response = general_chat(chat_history)
        elif task == "tavily_search":
            response = tavily_search(content)
        elif task == "groq_search":
            response = simple_groq_search(content)
        elif task == "code":
            response = generate_code(content)
        elif task == "image":
            response = generate_image(content)
        # Add other task handlers here...
        
        print(f"A-Prime.ai: {response}")
        chat_history.append({"role": "assistant", "content": response})
