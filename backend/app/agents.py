import os
import requests
import base64
import groq
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# --- Load Identity Context ---
def load_identity_context():
    """Loads the detailed identity and developer information from the text file using a reliable path."""
    try:
        # --- START FIX: Build an absolute path to the identity file ---
        # Get the absolute path to the directory where this script (agents.py) is located.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Construct the full path to identity_context.txt, which is in the same directory as this script.
        file_path = os.path.join(script_dir, "identity_context.txt")
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
        # --- END FIX ---
    except FileNotFoundError:
        print("WARNING: identity_context.txt not found. The agent will have a limited personality.")
        return "You are A-Prime.ai, a helpful assistant. Your developer is Abhishek Chourasia."

IDENTITY_CONTEXT = load_identity_context()

# --- Global API Client Initializations ---
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
    print(f"--- Calling Groq API with model: {model} ---")
    cleaned_messages = _clean_history_for_api(messages)
    return groq_client.chat.completions.create(messages=cleaned_messages, model=model)

# --- Agent Functions ---

def general_chat(chat_history: list[dict]) -> str:
    """Handles general chat queries using the detailed persona from identity_context.txt."""
    print("--- Activating Agent: general_chat (using Groq API) ---")
    
    system_prompt = f"""
    You are A-Prime.ai. Your entire personality, history, and knowledge about your developer are strictly defined by the context below.
    You must use this information to answer any questions about yourself, your developer (Abhishek Chourasia), your creation, or his projects.
    Be friendly, professional, and format your responses clearly using markdown. Do not go beyond the information provided.

    --- IDENTITY CONTEXT ---
    {IDENTITY_CONTEXT}
    --- END CONTEXT ---
    """
    messages = [{"role": "system", "content": system_prompt}] + chat_history
    try:
        completion = _call_groq(messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: Could not process chat. {e}"

def summarize_text(chat_history: list[dict]) -> str:
    """Summarizes the preceding conversation."""
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
    print("--- Activating Router Agent ---")
    system_prompt = """
    You are an extremely efficient routing assistant. Your only purpose is to analyze a user's prompt and classify it into exactly one of the following single-word categories:
    'summarize' - For requests to shorten or condense previous conversation text.
    'tavily_search' - For questions about current events, real-time info, news, or explicit web search requests.
    'groq_search' - For general knowledge questions (e.g., 'What is the capital of France?').
    'qna' - For questions that refer to information already given in the conversation history.
    'code' - For requests to generate or explain programming code.
    'image' - For requests to generate an image.
    'chat' - For general conversation, greetings, asking about the developer, or unclear requests.
    Respond with ONLY ONE SINGLE WORD. Do not add explanations or punctuation.
    """
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    try:
        completion = _call_groq(messages, model="gemma2-9b-it")
        task = completion.choices[0].message.content.strip().lower().replace("'", "").replace(".", "")
        print(f"--- ROUTER DECISION: '{task}' ---")

        valid_tasks = ["summarize", "tavily_search", "groq_search", "qna", "code", "image", "chat"]
        if task in valid_tasks:
            return task
        
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

