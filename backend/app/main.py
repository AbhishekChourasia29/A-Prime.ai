from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import agents, memory
from typing import Optional

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
    """Gets the chat history for a specific session."""
    history = memory.get_history(session_id)
    formatted_history = []
    for msg in history:
        formatted_msg = {
            "id": msg.get('id'),
            "role": msg.get('role'),
            "text": msg.get('content'),
            "timestamp": msg.get('timestamp'),
            "isImage": msg.get('is_image', False),
            "isCode": msg.get('is_code', False)
        }
        formatted_history.append(formatted_msg)
    return formatted_history

@app.post("/api/chat")
async def chat(request: ChatRequest):
    user_message = request.message
    session_id = request.session_id
    new_title = None

    if not session_id:
        session_data = new_chat()
        session_id = session_data["session_id"]
        new_title = "New Chat"
    elif memory.get_session_title(session_id) == "New Chat":
        new_title = "New Chat"

    # Save user message to DB immediately, so it's always recorded
    memory.add_to_history(session_id, "user", user_message)

    # --- NEW: Check for conversation length limit ---
    full_history = memory.get_history(session_id)
    SESSION_MESSAGE_LIMIT = 50 

    if len(full_history) >= SESSION_MESSAGE_LIMIT:
        response_text = "This conversation has reached its length limit. Please start a new chat to continue."
        memory.add_to_history(session_id, "assistant", response_text)
        return {"response": response_text, "session_id": session_id}

    # --- PRIMARY FIX: Truncate history before sending to agent ---
    AGENT_HISTORY_LIMIT = 20
    recent_history_for_agent = full_history[-AGENT_HISTORY_LIMIT:]
    agent_context_history = [{"role": msg['role'], "content": msg['content']} for msg in recent_history_for_agent]

    # Route to appropriate agent
    task = agents.route_to_agent(user_message)
    
    response_text = ""
    if task == "summarize":
        response_text = agents.summarize_text(agent_context_history)
    elif task == "tavily_search":
        response_text = agents.tavily_search(user_message)
    elif task == "groq_search":
        response_text = agents.simple_groq_search(user_message)
    elif task == "qna":
        response_text = agents.answer_question(agent_context_history)
    elif task == "code":
        response_text = agents.generate_code(user_message)
    elif task == "image":
        response_text = agents.generate_image(user_message)
    else: # 'chat' or fallback
        response_text = agents.general_chat(agent_context_history)

    # Save assistant response to DB
    memory.add_to_history(session_id, "assistant", response_text)

    # Update session title after the first real interaction
    if new_title == "New Chat":
        suggested_title = user_message[:50].strip() + ("..." if len(user_message) > 50 else "")
        memory.update_session_title(session_id, suggested_title)
        new_title = suggested_title

    response_payload = {"response": response_text, "session_id": session_id}
    if new_title and new_title != "New Chat":
        response_payload["new_title"] = new_title
        
    return response_payload

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Deletes a chat session by its ID."""
    if memory.delete_session(session_id):
        return {"message": "Session deleted successfully."}
    raise HTTPException(status_code=404, detail="Session not found.")

