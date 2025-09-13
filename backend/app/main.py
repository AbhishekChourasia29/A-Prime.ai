from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# Assuming your 'agents.py' and 'memory.py' are in a folder named 'app'
from app import agents, memory 
from typing import Optional

app = FastAPI()

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
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
    # Format history for the frontend
    formatted_history = []
    for msg in history:
        formatted_msg = {
            "id": msg.get('id'), 
            "role": msg.get('role'),
            "text": msg.get('content'),
            "timestamp": msg.get('timestamp')
        }
        if "data:image" in msg.get('content', ''):
            formatted_msg["isImage"] = True
        if "```" in msg.get('content', ''):
            formatted_msg["isCode"] = True
        formatted_history.append(formatted_msg)
    return formatted_history


@app.post("/api/chat")
async def chat(request: ChatRequest):
    user_message = request.message
    session_id = request.session_id

    if not session_id:
        session_data = new_chat()
        session_id = session_data["session_id"]
        # Use a flag to indicate that the title might need updating
        should_update_title = True
    else:
        current_session_title = memory.get_session_title(session_id)
        should_update_title = current_session_title == "New Chat"

    chat_history = memory.get_history(session_id)
    
    temp_history_for_agent = [{"role": msg['role'], "content": msg['content']} for msg in chat_history]
    temp_history_for_agent.append({"role": "user", "content": user_message})

    # --- UPDATED LOGIC ---
    # The router now returns both the task and the content to be processed.
    task, content = agents.route_to_agent(user_message, temp_history_for_agent)
    
    response_text = ""

    if task == "identity":
        # For the identity task, the content is the full, pre-made response.
        response_text = content
    elif task == "summarize":
        context_for_summary = temp_history_for_agent[-2]['content'] if len(temp_history_for_agent) > 1 else content
        response_text = agents.summarize_text(context_for_summary)
    elif task == "tavily_search":
        response_text = agents.tavily_search(content)
    elif task == "groq_search":
        response_text = agents.simple_groq_search(content)
    elif task == "qna":
        context_for_qna = temp_history_for_agent[-2]['content'] if len(temp_history_for_agent) > 1 else ""
        response_text = agents.answer_question(context_for_qna, content)
    elif task == "code":
        response_text = agents.generate_code(content)
    elif task == "image":
        response_text = agents.generate_image(content)
    else: # 'chat' or if routing fails
        response_text = agents.general_chat(temp_history_for_agent)

    # Save user message and assistant response to history
    memory.add_to_history(session_id, "user", user_message)
    memory.add_to_history(session_id, "assistant", response_text)

    # Update session title if this is the first real message
    new_title = None
    if should_update_title and user_message:
        suggested_title = user_message[:50].strip()
        if len(user_message) > 50:
            suggested_title += "..."
        memory.update_session_title(session_id, suggested_title)
        new_title = suggested_title

    response_payload = {"response": response_text, "session_id": session_id}
    if new_title:
        response_payload["new_title"] = new_title
        
    return response_payload

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Deletes a chat session by its ID."""
    if memory.delete_session(session_id):
        return {"message": "Session deleted successfully."}
    raise HTTPException(status_code=404, detail="Session not found.")
