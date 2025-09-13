from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import agents, memory 
import re
from typing import Optional

app = FastAPI()

# --- App Lifecycle Events ---
# MongoDB connection is typically handled on demand or lazy-loaded,
# so explicit startup/shutdown events for connection are less critical
# than for SQLite. The connection will be established on the first DB call.

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Allows all headers
)

# --- Pydantic Models ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None # Make session_id optional for new chats

# --- API Endpoints ---

@app.get("/api/sessions")
def get_sessions():
    """Gets a list of all chat sessions for the history sidebar."""
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
    # The frontend expects 'id', 'role', 'text' (or 'content' mapped to 'text')
    # and potentially 'isImage', 'isCode'.
    # Ensure 'content' is mapped to 'text' for the frontend.
    formatted_history = []
    for msg in history:
        formatted_msg = {
            "id": msg.get('id'), # MongoDB _id converted to string
            "role": msg.get('role'),
            "text": msg.get('content'),
            "timestamp": msg.get('timestamp') # Include timestamp
        }
        # Add flags for image/code if they were stored this way
        if "data:image" in msg.get('content', ''):
            formatted_msg["isImage"] = True
        if "```python" in msg.get('content', '') and "```" in msg.get('content', ''):
            formatted_msg["isCode"] = True
        formatted_history.append(formatted_msg)
    return formatted_history


@app.post("/api/chat")
async def chat(request: ChatRequest):
    user_message = request.message
    session_id = request.session_id

    # If no session ID is provided, create a new session
    if not session_id:
        session_data = new_chat()
        session_id = session_data["session_id"]
        new_title = session_data["title"]
    else:
        # Fetch the current title of the session to check if it's the default "New Chat"
        current_session_title = memory.get_session_title(session_id)
        if current_session_title == "New Chat":
            new_title = "New Chat" # Keep this flag to trigger title update below
        else:
            new_title = None # No need to update title if it's already set


    # Get chat history for the current session
    chat_history = memory.get_history(session_id)

    # Prepare history for the agent, ensuring it's in the correct format
    temp_history_for_agent = [{"role": msg['role'], "content": msg['content']} for msg in chat_history]
    temp_history_for_agent.append({"role": "user", "content": user_message})

    # Route to appropriate agent
    task = agents.route_to_agent(user_message, temp_history_for_agent)
    
    response_text = ""
    context = ""

    if task == "summarize":
        context = temp_history_for_agent[-2]['content'] if len(temp_history_for_agent) > 1 else user_message
        response_text = agents.summarize_text(context)
    elif task == "tavily_search":
        response_text = agents.tavily_search(user_message)
    elif task == "groq_search":
        response_text = agents.simple_groq_search(user_message)
    elif task == "qna":
        context = temp_history_for_agent[-2]['content'] if len(temp_history_for_agent) > 1 else ""
        response_text = agents.answer_question(context, user_message)
    elif task == "code":
        response_text = agents.generate_code(user_message)
    elif task == "image":
        response_text = agents.generate_image(user_message)
    else: # 'chat' or if routing fails
        response_text = agents.general_chat(temp_history_for_agent)

    # Save BOTH user message and assistant response to the database
    memory.add_to_history(session_id, "user", user_message)
    memory.add_to_history(session_id, "assistant", response_text)

    # Update session title if it's a new chat and this is the first interaction
    if new_title == "New Chat" and user_message:
        # A simple heuristic: use the first few words of the user's first message as title
        suggested_title = user_message[:50].strip()
        if len(user_message) > 50:
            suggested_title += "..."
        memory.update_session_title(session_id, suggested_title)
        new_title = suggested_title # Update new_title to send back to frontend

    response_payload = {"response": response_text, "session_id": session_id}
    if new_title: # Only include new_title in payload if it was actually updated
        response_payload["new_title"] = new_title
        
    return response_payload

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Deletes a chat session by its ID."""
    if memory.delete_session(session_id):
        return {"message": "Session deleted successfully."}
    raise HTTPException(status_code=404, detail="Session not found.")