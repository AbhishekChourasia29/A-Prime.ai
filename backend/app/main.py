from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import agents, memory 
from typing import Optional, Callable, Any

app = FastAPI()

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# --- Helper Functions ---
def _get_or_create_session(session_id: Optional[str]) -> tuple[str, bool]:
    """Gets an existing session or creates a new one."""
    if not session_id or memory.get_session_title(session_id) is None:
        new_session = new_chat()
        return new_session["session_id"], True
    return session_id, memory.get_session_title(session_id) == "New Chat"

def _update_session_title(session_id: str, first_message: str):
    """Updates the session title based on the first user message."""
    title = first_message[:50].strip() + ("..." if len(first_message) > 50 else "")
    memory.update_session_title(session_id, title)
    return title

# --- API Endpoints ---
@app.get("/api/sessions")
def get_sessions():
    """Gets a list of all chat sessions."""
    return memory.get_all_sessions()

@app.post("/api/new_chat")
def new_chat():
    """Creates a new chat session."""
    session_id = memory.create_new_session()
    return {"session_id": session_id, "title": "New Chat"}

@app.get("/api/chat_history/{session_id}")
def get_chat_history(session_id: str):
    """Gets the formatted chat history for a specific session."""
    history = memory.get_history(session_id)
    return [
        {
            "id": msg.get('id'), 
            "role": msg.get('role'),
            "text": msg.get('content'),
            "timestamp": msg.get('timestamp'),
            "isImage": "data:image" in msg.get('content', ''),
            "isCode": "```" in msg.get('content', '')
        } for msg in history
    ]

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Main endpoint to handle user messages and route to the correct agent."""
    session_id, should_update_title = _get_or_create_session(request.session_id)
    chat_history = memory.get_history(session_id)
    
    # Prepare history for agent context
    full_history = chat_history + [{"role": "user", "content": request.message}]
    
    task, content = agents.route_to_agent(request.message, full_history)
    
    # --- OPTIMIZED AGENT DISPATCHER ---
    # This dictionary maps tasks to their corresponding agent functions.
    # It's more efficient and scalable than a long if/elif/else chain.
    agent_dispatcher: dict[str, Callable[..., Any]] = {
        "identity": agents.answer_identity_question,
        "tavily_search": agents.tavily_search,
        "groq_search": agents.simple_groq_search,
        "code": agents.generate_code,
        "image": agents.generate_image,
        "summarize": lambda: agents.summarize_text(chat_history[-1]['content'] if chat_history else content),
        "qna": lambda: agents.answer_question(chat_history[-1]['content'] if chat_history else "", content),
        "chat": lambda: agents.general_chat(full_history)
    }

    # Get the agent function from the dispatcher, defaulting to 'chat'
    agent_function = agent_dispatcher.get(task, agent_dispatcher["chat"])
    
    # Execute the chosen agent function
    # The lambda functions are called here, others are called with 'content' if needed.
    if task in ["summarize", "qna", "chat"]:
        response_text = agent_function()
    else:
        response_text = agent_function(content)

    # --- Persist and Respond ---
    memory.add_to_history(session_id, "user", request.message)
    memory.add_to_history(session_id, "assistant", response_text)

    response_payload = {"response": response_text, "session_id": session_id}
    if should_update_title and request.message:
        response_payload["new_title"] = _update_session_title(session_id, request.message)
        
    return response_payload

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Deletes a chat session by its ID."""
    if not memory.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": "Session deleted successfully."}

