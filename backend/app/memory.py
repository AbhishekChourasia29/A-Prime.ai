import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError
from bson.objectid import ObjectId

load_dotenv()

# --- Setup a logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - MEMORY - %(levelname)s - %(message)s')

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
DB_CLIENT = None
DB = None
# REMOVED: Unused HISTORY_LIMIT variable. Truncation logic is now handled in main.py before calling an agent.

def get_db_client():
    """Establishes and returns a connection to MongoDB Atlas."""
    global DB_CLIENT, DB
    if DB_CLIENT is None:
        if not MONGO_URI:
            logging.error("MONGO_URI environment variable not set.")
            raise ValueError("MONGO_URI environment variable not set.")
        try:
            DB_CLIENT = MongoClient(MONGO_URI)
            DB = DB_CLIENT.get_database("chatbot_db")
            DB_CLIENT.admin.command('ping')
            logging.info("MongoDB connection established.")
        except ConnectionFailure as e:
            logging.error(f"MongoDB connection FAILED: {e}")
            DB_CLIENT = None
            DB = None
            raise e
        except PyMongoError as e:
            logging.error(f"MongoDB error during connection: {e}")
            DB_CLIENT = None
            DB = None
            raise e
    return DB_CLIENT

def create_new_session() -> str:
    """Creates a new session record in the database."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions

    session_data = {
        "createdAt": datetime.now(),
        "title": "New Chat",
        "lastModified": datetime.now()
    }
    try:
        result = sessions_collection.insert_one(session_data)
        session_id = str(result.inserted_id)
        logging.info(f"New session created with ID: {session_id}")
        return session_id
    except PyMongoError as e:
        logging.error(f"Error creating new session: {e}")
        raise e

def get_all_sessions() -> list[dict]:
    """Gets a list of all chat sessions for the history sidebar."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions

    try:
        sessions = list(sessions_collection.find({}, {"_id": 1, "title": 1, "lastModified": 1}).sort("lastModified", -1))
        for session in sessions:
            session['id'] = str(session['_id'])
            del session['_id']
        logging.info(f"Fetched {len(sessions)} sessions.")
        return sessions
    except PyMongoError as e:
        logging.error(f"Error fetching all sessions: {e}")
        return []

def get_session_title(session_id: str) -> str:
    """Gets the title of a specific session."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions
    try:
        if not ObjectId.is_valid(session_id):
            logging.warning(f"Invalid session ID format for get_session_title: {session_id}")
            return "New Chat"
        session = sessions_collection.find_one({"_id": ObjectId(session_id)}, {"title": 1})
        return session.get("title", "New Chat") if session else "New Chat"
    except Exception as e:
        logging.error(f"Error in get_session_title for {session_id}: {e}")
        return "New Chat"

def update_session_title(session_id: str, new_title: str):
    """Updates the title of a session."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions
    try:
        if ObjectId.is_valid(session_id):
            sessions_collection.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"title": new_title, "lastModified": datetime.now()}}
            )
            logging.info(f"Session {session_id} title updated to '{new_title}'.")
    except Exception as e:
        logging.error(f"Error in update_session_title for {session_id}: {e}")

def delete_session(session_id: str) -> bool:
    """Deletes a session and its associated messages."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    try:
        if not ObjectId.is_valid(session_id):
            logging.warning(f"Invalid session ID format for delete_session: {session_id}")
            return False
        db.messages.delete_many({"session_id": session_id})
        result = db.sessions.delete_one({"_id": ObjectId(session_id)})
        logging.info(f"Deleted session {session_id} and associated messages.")
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error in delete_session for {session_id}: {e}")
        return False

def add_to_history(session_id: str, role: str, content: str):
    """Adds a message to a session, pre-calculating content type flags."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    messages_collection = db.messages
    sessions_collection = db.sessions

    # --- IMPROVEMENT: Pre-calculate content type flags on save ---
    is_image = "data:image" in content
    # A simple check for code blocks
    is_code = "```" in content and any(lang in content for lang in ["python", "javascript", "java", "c", "cpp", "sql", "html", "css"])

    message_data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
        "is_image": is_image,
        "is_code": is_code
    }
    try:
        messages_collection.insert_one(message_data)
        if ObjectId.is_valid(session_id):
            sessions_collection.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"lastModified": datetime.now()}}
            )
        logging.info(f"Added message to history for session {session_id}: role={role}")
    except Exception as e:
        logging.error(f"Error in add_to_history for {session_id}: {e}")

def get_history(session_id: str) -> list[dict]:
    """Gets all messages for a session."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    messages_collection = db.messages
    try:
        history = list(messages_collection.find({"session_id": session_id}).sort("timestamp", 1))
        for message in history:
            message['id'] = str(message['_id'])
            del message['_id']
            message['timestamp'] = message['timestamp'].isoformat()
        logging.info(f"Fetched {len(history)} messages for session {session_id}.")
        return history
    except Exception as e:
        logging.error(f"Error in get_history for {session_id}: {e}")
        return []
