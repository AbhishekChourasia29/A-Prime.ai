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

def get_db_client():
    """Establishes and returns a connection to MongoDB Atlas."""
    global DB_CLIENT, DB
    if DB_CLIENT is None:
        if not MONGO_URI:
            logging.error("MONGO_URI environment variable not set.")
            raise ValueError("MONGO_URI environment variable not set.")
        try:
            DB_CLIENT = MongoClient(MONGO_URI)
            DB = DB_CLIENT.get_database("a_prime_ai_db")
            DB_CLIENT.admin.command('ping')
            logging.info("MongoDB connection established.")
        except (ConnectionFailure, PyMongoError) as e:
            logging.error(f"MongoDB connection FAILED: {e}")
            DB_CLIENT = None
            DB = None
            raise e
    return DB_CLIENT

def close_db_connection():
    """Closes the database connection during application shutdown."""
    global DB_CLIENT, DB
    if DB_CLIENT is not None:
        DB_CLIENT.close()
        DB_CLIENT = None
        DB = None
        logging.info("MongoDB connection closed.")

def init_db():
    """Initializes the database connection on application startup."""
    try:
        get_db_client()
        logging.info("MongoDB successfully initialized.")
    except Exception as e:
        logging.error(f"Error during MongoDB initialization: {e}")
        raise e

def create_new_session() -> str:
    """Creates a new chat session in the database."""
    client = get_db_client()
    db = client.get_database("a_prime_ai_db")
    sessions_collection = db.sessions
    session_data = {
        "createdAt": datetime.utcnow(),
        "title": "New Chat",
        "lastModified": datetime.utcnow()
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
    db = client.get_database("a_prime_ai_db")
    sessions_collection = db.sessions
    try:
        sessions = list(sessions_collection.find({}, {"_id": 1, "title": 1, "lastModified": 1}).sort("lastModified", -1))
        for session in sessions:
            # Renamed 'id' to 'session_id' for frontend compatibility
            session['session_id'] = str(session.pop('_id'))
        logging.info(f"Fetched {len(sessions)} sessions.")
        return sessions
    except PyMongoError as e:
        logging.error(f"Error fetching all sessions: {e}")
        return []

def get_session_title(session_id: str) -> str:
    """Gets the title of a specific session."""
    client = get_db_client()
    db = client.get_database("a_prime_ai_db")
    sessions_collection = db.sessions
    try:
        if not ObjectId.is_valid(session_id): return "New Chat"
        session = sessions_collection.find_one({"_id": ObjectId(session_id)}, {"title": 1})
        return session.get("title", "New Chat") if session else "New Chat"
    except Exception as e:
        logging.error(f"Error getting session title for {session_id}: {e}")
        return "New Chat"

def update_session_title(session_id: str, new_title: str):
    """Updates the title of a session."""
    client = get_db_client()
    db = client.get_database("a_prime_ai_db")
    sessions_collection = db.sessions
    try:
        if not ObjectId.is_valid(session_id): return
        sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"title": new_title, "lastModified": datetime.utcnow()}}
        )
        logging.info(f"Session {session_id} title updated.")
    except Exception as e:
        logging.error(f"Error updating session title for {session_id}: {e}")

def delete_session(session_id: str) -> bool:
    """Deletes a session and its associated messages."""
    client = get_db_client()
    db = client.get_database("a_prime_ai_db")
    try:
        if not ObjectId.is_valid(session_id): return False
        db.messages.delete_many({"session_id": session_id})
        session_result = db.sessions.delete_one({"_id": ObjectId(session_id)})
        logging.info(f"Deleted session {session_id}.")
        return session_result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting session {session_id}: {e}")
        return False

def add_to_history(session_id: str, role: str, content: str):
    """Adds a message to a session's history."""
    client = get_db_client()
    db = client.get_database("a_prime_ai_db")
    message_data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow()
    }
    try:
        db.messages.insert_one(message_data)
        if ObjectId.is_valid(session_id):
            db.sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"lastModified": datetime.utcnow()}}
            )
    except Exception as e:
        logging.error(f"Error adding message to history for session {session_id}: {e}")

def get_history(session_id: str) -> list[dict]:
    """Gets the message history for a session."""
    client = get_db_client()
    db = client.get_database("a_prime_ai_db")
    try:
        history = list(db.messages.find({"session_id": session_id}).sort("timestamp", 1))
        for message in history:
            message['id'] = str(message.pop('_id'))
            if 'timestamp' in message:
                message['timestamp'] = message['timestamp'].isoformat()
        return history
    except Exception as e:
        logging.error(f"Error getting history for session {session_id}: {e}")
        return []

