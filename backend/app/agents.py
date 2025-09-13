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
        # Using Tavily's search endpoint to get concise results for LLMs
        response = tavily_client.search(query=query, search_depth="basic", include_answer=True)
        
        # Tavily often provides an 'answer' directly, which is great for LLMs
        if response.get("answer"):
            return response["answer"]
        
        # If no direct answer, compile snippets from results
        snippets = []
        if response.get("results"):
            for result in response["results"]:
                if result.get("content"):
                    snippets.append(result["content"])
        
        if not snippets:
            return "Sorry, I couldn't find any relevant information online using Tavily."
        
        context = " ".join(snippets)
        
        # Use Groq to answer based on search results
        messages = [
            {"role": "system", "content": "Answer based *only* on the provided search snippets. If you cannot answer, say no."},
            {"role": "user", "content": f"Search Results: {context}\n\nBased on the above, answer: {query}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Failed to search the web using Tavily. {e}"

def simple_groq_search(query: str) -> str:
    """
    Answers a question based on Groq's internal knowledge without a web search.
    """
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
    global stability_api_status # Access the global status variable
    if not stability_api_status:
        return "Error: Stability AI API key not found. Image generation is disabled."
    
    try:
        response = requests.post(
            STABILITY_API_BASE_URL, # Using the global constant here
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
        print(f"API Error in generate_image: {e}")
        return f"Error: Could not generate the image using Stability AI. {e}"

def route_to_agent(user_prompt: str, chat_history: list[dict]) -> str:
    """
    Routes the user's prompt to the appropriate agent based on LLM-based intent recognition.
    """
    system_prompt = """You are an extremely efficient routing assistant your name is A-Prime.ai. Your only purpose is to analyze a user's prompt and classify it into one of the following categories.
    Respond with ONLY ONE single word. Do not add any explanation, punctuation, or any other text.

    The categories are:
    - 'summarize' (For requests to shorten or condense text provided by previous responses)
    - 'tavily_search' (For any questions about **current events, real-time information, news, or a search explicitly requested with words like 'search', 'find', 'latest', or 'current'**)
    - 'groq_search' (For questions that can be answered from general knowledge, like historical facts or common science questions, without needing a live web search)
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
            return task
        else:
            print(f"LLM returned invalid task: '{task}'. Using fallback logic.")
            # Fallback logic for common keywords
            if "image" in user_prompt.lower(): return "image"
            if "news" in user_prompt.lower() or "latest" in user_prompt.lower() or "current" in user_prompt.lower() or "search" in user_prompt.lower(): return "tavily_search"
            if "summarize" in user_prompt.lower(): return "summarize"
            if "code" in user_prompt.lower(): return "code"
            if "who is" in user_prompt.lower() or "what is" in user_prompt.lower() or "web search" is user_prompt.lower(): return "groq_search"
            return "chat"
            
    except Exception as e:
        print(f"Error calling LLM for intent recognition: {e}. Defaulting to 'chat'.")
        return "chat"