import os
import requests
import base64
import groq
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# --- API Client Initializations ---
groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")) if os.getenv("TAVILY_API_KEY") else None
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
STABILITY_API_BASE_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"

# --- Pre-load Identity Context for Performance ---
IDENTITY_CONTEXT = ""
def _load_identity_context():
    """Loads the identity context from the file into memory at startup."""
    global IDENTITY_CONTEXT
    try:
        script_dir = os.path.dirname(__file__)
        file_path = os.path.join(script_dir, "identity_context.txt")
        with open(file_path, "r", encoding="utf-8") as f:
            IDENTITY_CONTEXT = f.read()
        print("Identity context loaded successfully.")
    except FileNotFoundError:
        print("WARNING: identity_context.txt not found. Identity agent is disabled.")
        IDENTITY_CONTEXT = None
_load_identity_context()

# --- Centralized System Prompts ---
SYSTEM_PROMPTS = {
    "identity": """You are A-Prime.ai, a helpful and professional Multi-Agent Assistant. Your developer is Abhishek Chourasia.
Answer the user's question based *only* on the provided context about your developer and your own architecture.
Be friendly, professional, and concise. Format your response clearly using markdown and directly provide portfolio and LinkedIn links when relevant.""",
    "summarize": "You are a helpful assistant that summarizes text concisely.",
    "tavily_search": "You are a web search assistant. Answer the user's query professionally and concisely based *only* on the provided web search results. Cite your sources if possible. If the context does not contain the answer, state that you couldn't find the information.",
    "groq_search": "You are a helpful assistant that answers questions concisely and accurately from your existing knowledge. Do not perform a web search.",
    "qna": "You are a helpful assistant that answers questions based on the provided conversation context.",
    "code": "You are a helpful assistant that generates code. Provide the code within triple backticks (e.g., ```python).",
    "router": """You are an extremely efficient routing assistant. Your purpose is to classify a user's prompt into a single category.
Respond with ONLY ONE word from this list: identity, summarize, tavily_search, groq_search, qna, code, image, chat."""
}

# --- Core Agent Functions ---

def _call_groq(messages, model="gemma2-9b-it"):
    """Helper function to call the Groq API with robust error handling."""
    if not groq_client: raise ValueError("Groq API key is not configured.")
    try:
        return groq_client.chat.completions.create(messages=messages, model=model)
    except Exception as e:
        print(f"Groq API call failed: {e}")
        raise

def answer_identity_question(query: str) -> str:
    """Answers questions about the AI's identity using pre-loaded context."""
    if not IDENTITY_CONTEXT: return "I'm sorry, my identity context is not available right now."
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["identity"]},
        {"role": "user", "content": f"Context:\n{IDENTITY_CONTEXT}\n\nQuestion: {query}"}
    ]
    completion = _call_groq(messages)
    return completion.choices[0].message.content

def summarize_text(text: str) -> str:
    """Summarizes text using the Groq API."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["summarize"]},
        {"role": "user", "content": f"Summarize the following text: {text}"}
    ]
    completion = _call_groq(messages)
    return completion.choices[0].message.content

def tavily_search(query: str) -> str:
    """Performs a web search with Tavily and summarizes results with Groq."""
    if not tavily_client: return "Error: Tavily API key is not configured for web search."
    try:
        response = tavily_client.search(query=query, search_depth="basic", include_answer=True, max_results=5)
        if response.get("answer"): return response["answer"]
        
        context = " ".join([r["content"] for r in response.get("results", []) if r.get("content")])
        if not context: return "I searched online, but couldn't find any relevant information to answer your question."

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["tavily_search"]},
            {"role": "user", "content": f"Web Search Results: {context}\n\nBased on these results, please answer the query: '{query}'"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Tavily search failed: {e}")
        return "Sorry, I encountered an error while searching the web. Please try again."

def simple_groq_search(query: str) -> str:
    """Answers a general knowledge question using Groq."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["groq_search"]},
        {"role": "user", "content": query}
    ]
    completion = _call_groq(messages)
    return completion.choices[0].message.content

def answer_question(context: str, query: str) -> str:
    """Answers a question based on conversation history."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["qna"]},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
    ]
    completion = _call_groq(messages)
    return completion.choices[0].message.content

def generate_code(prompt: str) -> str:
    """Generates code using the Groq API."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["code"]},
        {"role": "user", "content": prompt}
    ]
    completion = _call_groq(messages)
    return completion.choices[0].message.content

def general_chat(chat_history: list[dict]) -> str:
    """Handles general conversation."""
    completion = _call_groq(chat_history)
    return completion.choices[0].message.content

def generate_image(prompt: str) -> str:
    """Generates an image using the Stability AI API."""
    if not STABILITY_API_KEY: return "Error: Stability AI API key not found. Image generation is disabled."
    try:
        response = requests.post(
            STABILITY_API_BASE_URL,
            headers={"authorization": f"Bearer {STABILITY_API_KEY}", "accept": "image/*"},
            files={"prompt": (None, prompt), "output_format": (None, "png")},
        )
        response.raise_for_status()
        base64_image = base64.b64encode(response.content).decode('utf-8')
        return f"data:image/png;base64,{base64_image}"
    except requests.exceptions.HTTPError as e:
        print(f"Stability AI HTTP Error: {e.response.text}")
        return f"Error: Failed to generate image due to an API issue (Status {e.response.status_code}). Please check the prompt or API key."
    except requests.exceptions.RequestException as e:
        print(f"Stability AI Connection Error: {e}")
        return "Error: Could not connect to the image generation service. Please check your network connection."

def route_to_agent(user_prompt: str, chat_history: list[dict]) -> tuple[str, str]:
    """Routes the user's prompt to the correct agent using a multi-layer approach."""
    # --- Layer 1: Deterministic Keyword Triggers ---
    identity_keywords = ["who are you", "your name", "who built you", "who developed you", "creator", "create you", "make you", "about yourself", "your purpose"]
    if any(keyword in user_prompt.lower() for keyword in identity_keywords):
        return "identity", user_prompt

    web_search_keywords = ["latest", "current", "today's news", "what is the price of", "what is the stock", "search for", "find information on"]
    if any(keyword in user_prompt.lower() for keyword in web_search_keywords):
        return "tavily_search", user_prompt

    # --- Layer 2: LLM-based Classification (Fallback) ---
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["router"]},
        {"role": "user", "content": user_prompt}
    ]
    try:
        completion = _call_groq(messages)
        task = completion.choices[0].message.content.strip().lower().replace("'", "")
        # Validate the task from the LLM to prevent unexpected behavior
        valid_tasks = ["summarize", "tavily_search", "groq_search", "qna", "code", "image", "chat"]
        return task if task in valid_tasks else "chat", user_prompt
    except Exception as e:
        print(f"Router LLM call failed: {e}. Defaulting to chat.")
        return "chat", user_prompt

