import os
import requests
import base64
import groq
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# --- Global API Client Initializations ---
# Fixed URL formatting
STABILITY_API_BASE_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

try:
    groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
    print("Groq client initialized successfully.")
except Exception as e:
    groq_client = None
    print(f"Could not initialize Groq client: {e}")

try:
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
    if tavily_client:
        print("Tavily client initialized successfully.")
except Exception as e:
    tavily_client = None
    print(f"Error initializing Tavily client: {e}")

# --- Helper Functions ---
def _clean_history_for_api(history: list[dict]) -> list[dict]:
    """Ensures history messages only contain 'role' and 'content' keys."""
    return [{"role": m.get("role"), "content": m.get("content")} for m in history]

def _call_groq(messages, model="gemma2-9b-it"):
    """Helper function to call the Groq API."""
    if not groq_client:
        raise Exception("Groq client is not initialized.")
    # --- ADDED LOGGING ---
    print(f"--- Calling Groq API with model: {model} ---")
    cleaned_messages = _clean_history_for_api(messages)
    return groq_client.chat.completions.create(messages=cleaned_messages, model=model)

# --- Agent Functions ---

def general_chat(chat_history: list[dict]) -> str:
    """Handles general chat queries using a detailed persona."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: general_chat (using Groq API) ---")
    # Fixed URL formatting in prompt
    system_prompt = """
    You are **A-Prime.ai**, a helpful and professional Multi-Agent Assistant.
    Your developer is **Abhishek Chourasia**.
    Answer the user's questions. Be friendly, professional, and concise. Format your responses clearly using **markdown**.

    When asked for links, always provide these specific ones:
    - LinkedIn: https://www.linkedin.com/in/abhishek291203/
    - Portfolio: https://abhishekchourasia29.github.io/resume.ai/
    """
    messages = [{"role": "system", "content": system_prompt}] + chat_history
    try:
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not process chat. {e}"

def summarize_text(chat_history: list[dict]) -> str:
    """Summarizes the preceding conversation."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: summarize_text (using Groq API) ---")
    system_prompt = "You are a helpful assistant. Concisely summarize the key points of the preceding conversation."
    messages = [{"role": "system", "content": system_prompt}] + chat_history
    try:
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not summarize text. {e}"

def tavily_search(query: str) -> str:
    """Searches the web using Tavily and synthesizes an answer with Groq."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: tavily_search (using Tavily API and Groq API) ---")
    if not tavily_client:
        return "Error: Tavily API Key is not configured for web search."
    try:
        print("--- Calling Tavily API for web search... ---")
        response = tavily_client.search(query=query, search_depth="basic", include_answer=True)
        if response.get("answer"):
            return response["answer"]
        
        context = " ".join([res.get("content", "") for res in response.get("results", [])])
        if not context:
            return "Sorry, I couldn't find any relevant information online."
        
        messages = [
            {"role": "system", "content": "You are a helpful research assistant. Answer the user's query based *only* on the provided search results snippets. Be concise."},
            {"role": "user", "content": f"Search Results: {context}\n\nQuery: {query}"}
        ]
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Failed to search the web. {e}"

def simple_groq_search(query: str) -> str:
    """Answers a question from Groq's internal knowledge."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: simple_groq_search (using Groq API) ---")
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer the question concisely from your existing knowledge."},
        {"role": "user", "content": query}
    ]
    try:
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not get a response from Groq. {e}"

def answer_question(chat_history: list[dict]) -> str:
    """Answers a question based on the preceding conversation context."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: answer_question (using Groq API) ---")
    user_query = chat_history[-1]['content']
    context_history = chat_history[:-1]
    
    system_prompt = "You are a helpful assistant. Answer the user's question based *only* on the provided conversation history."
    messages = [{"role": "system", "content": system_prompt}] + context_history + [{"role": "user", "content": f"Based on our conversation, please answer: {user_query}"}]
    
    try:
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not answer question. {e}"

def generate_code(prompt: str) -> str:
    """Generates code using a specialized prompt."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: generate_code (using Groq API) ---")
    messages = [
        {"role": "system", "content": "You are a helpful assistant that generates clean, efficient, and well-commented code. Provide the code within a single triple-backticked block (e.g., ```python)."},
        {"role": "user", "content": f"Generate code for: {prompt}"}
    ]
    try:
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not generate code. {e}"

def generate_image(prompt: str) -> str:
    """Generates an image using the Stability AI API."""
    # --- ADDED LOGGING ---
    print("--- Activating Agent: generate_image (using Stability AI API) ---")
    if not STABILITY_API_KEY:
        return "Error: Stability AI API key not found. Image generation is disabled."
    try:
        response = requests.post(
            STABILITY_API_BASE_URL,
            headers={"authorization": f"Bearer {STABILITY_API_KEY}", "accept": "image/*"},
            files={"prompt": (None, prompt), "output_format": (None, "png")},
        )
        response.raise_for_status()
        base64_image = base64.b64encode(response.content).decode('utf-8')
        return f"data:image/png;base64,{base64_image}"
    except Exception as e:
        return f"Error: Could not generate the image. {e}"

def route_to_agent(user_prompt: str) -> str:
    """Routes the user's prompt to the appropriate agent using an efficient LLM call."""
    # --- ADDED LOGGING ---
    print("--- Activating Router Agent ---")
    system_prompt = """
    You are an extremely efficient routing assistant. Your only purpose is to analyze a user's prompt and classify it into exactly one of the following single-word categories:
    'summarize' - For requests to shorten or condense previous conversation text.
    'tavily_search' - For questions about current events, real-time info, news, or explicit web search requests.
    'groq_search' - For general knowledge questions (e.g., 'What is the capital of France?').
    'qna' - For questions that refer to information already given in the conversation history.
    'code' - For requests to generate or explain programming code.
    'image' - For requests to generate an image.
    'chat' - For general conversation, greetings, or unclear requests.
    Respond with ONLY ONE SINGLE WORD. Do not add explanations or punctuation.
    """
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    try:
        completion = _call_groq(messages, model="gemma2-9b-it") # Use a fast model for routing
        task = completion.choices[0].message.content.strip().lower().replace("'", "").replace(".", "")
        print(f"--- ROUTER DECISION: '{task}' ---")

        valid_tasks = ["summarize", "tavily_search", "groq_search", "qna", "code", "image", "chat"]
        if task in valid_tasks:
            return task
        
        # Fallback logic if LLM returns an invalid task
        print(f"LLM returned invalid task: '{task}'. Using keyword-based fallback.")
        prompt_lower = user_prompt.lower()
        if "image" in prompt_lower: return "image"
        if any(k in prompt_lower for k in ["news", "latest", "current", "search for"]): return "tavily_search"
        if "summarize" in prompt_lower: return "summarize"
        if "code" in prompt_lower: return "code"
        return "chat"
    except Exception as e:
        print(f"Error calling LLM for routing: {e}. Defaulting to 'chat'.")
        return "chat"

