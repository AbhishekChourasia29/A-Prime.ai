import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError
from bson.objectid import ObjectId # Import ObjectId for querying by _id

load_dotenv()

# --- Setup a logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - MEMORY - %(levelname)s - %(message)s')

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
DB_CLIENT = None
DB = None
HISTORY_LIMIT = 20 # Still keep a limit for fetching, but MongoDB will store all.

def get_db_client():
    """Establishes and returns a connection to MongoDB Atlas."""
    global DB_CLIENT, DB
    if DB_CLIENT is None:
        if not MONGO_URI:
            logging.error("MONGO_URI environment variable not set.")
            raise ValueError("MONGO_URI environment variable not set.")
        try:
            DB_CLIENT = MongoClient(MONGO_URI)
            # The database name can be configured here or passed dynamically
            DB = DB_CLIENT.get_database("chatbot_db")
            # The ping command is cheap and does not require auth.
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

def close_db_connection():
    """This is a cleanup function. It properly closes the database connection when the application is shutting down."""
    global DB_CLIENT, DB
    if DB_CLIENT is not None:
        DB_CLIENT.close()
        DB_CLIENT = None
        DB = None
        logging.info("MongoDB connection closed.")

def init_db():
    """An initializer that simply calls get_db_client() to make sure the database is connected and ready when the app starts."""
    try:
        client = get_db_client()
        db = client.get_database("chatbot_db") # Ensure database name is consistent
        # Ensure collections exist (they are created on first insert if not present)
        # You can add indexes here if needed for performance, e.g., db.sessions.create_index("createdAt")
        logging.info("MongoDB collections ensured.")
    except Exception as e:
        logging.error(f"Error during MongoDB initialization: {e}")
        raise e

def create_new_session() -> str:
    """When you start a new chat, this function creates a new "session" record in the database. It gives this session a unique ID (session_id) and returns it. This ID is like the label on the new folder."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions

    session_data = {
        "createdAt": datetime.now(),
        "title": "New Chat", # Default title, will be updated with first message
        "lastModified": datetime.now()
    }
    try:
        result = sessions_collection.insert_one(session_data)
        session_id = str(result.inserted_id) # MongoDB ObjectId as string
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
        # Fetch sessions, sort by last modified, and return relevant fields
        sessions = list(sessions_collection.find({}, {"_id": 1, "title": 1, "lastModified": 1}).sort("lastModified", -1))
        # Convert ObjectId to string for front-end compatibility
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
        # Ensure session_id is a valid ObjectId before querying
        if not ObjectId.is_valid(session_id):
            logging.warning(f"Invalid session ID format for get_session_title: {session_id}")
            return "New Chat" # Return default if ID is invalid

        session = sessions_collection.find_one({"_id": ObjectId(session_id)}, {"title": 1})
        if session:
            return session.get("title", "New Chat")
        return "New Chat"
    except PyMongoError as e:
        logging.error(f"Error getting session title for {session_id}: {e}")
        return "New Chat"
    except Exception as e: # Catch other potential errors, e.g., if ObjectId conversion fails unexpectedly
        logging.error(f"Unexpected error in get_session_title for {session_id}: {e}")
        return "New Chat"

def update_session_title(session_id: str, new_title: str):
    """Updates the title of a session."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions
    try:
        # Ensure session_id is a valid ObjectId before querying
        if not ObjectId.is_valid(session_id):
            logging.warning(f"Invalid session ID format for update_session_title: {session_id}")
            return

        sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"title": new_title, "lastModified": datetime.now()}}
        )
        logging.info(f"Session {session_id} title updated to '{new_title}'.")
    except PyMongoError as e:
        logging.error(f"Error updating session title for {session_id}: {e}")
    except Exception as e: # Catch other potential errors
        logging.error(f"Unexpected error in update_session_title for {session_id}: {e}")


def delete_session(session_id: str) -> bool:
    """Deletes a session and its associated messages from the database."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    sessions_collection = db.sessions
    messages_collection = db.messages

    try:
        # Ensure session_id is a valid ObjectId before querying for session deletion
        if not ObjectId.is_valid(session_id):
            logging.warning(f"Invalid session ID format for delete_session: {session_id}")
            return False

        # Delete messages first (using string session_id as it's stored that way in messages collection)
        messages_result = messages_collection.delete_many({"session_id": session_id})
        logging.info(f"Deleted {messages_result.deleted_count} messages for session {session_id}.")

        # Then delete the session (using ObjectId for _id field)
        session_result = sessions_collection.delete_one({"_id": ObjectId(session_id)})
        logging.info(f"Deleted session {session_id}.")
        return session_result.deleted_count > 0
    except PyMongoError as e:
        logging.error(f"Error deleting session {session_id}: {e}")
        return False
    except Exception as e: # Catch other potential errors
        logging.error(f"Unexpected error in delete_session for {session_id}: {e}")
        return False

def add_to_history(session_id: str, role: str, content: str):
    """Adds a message to a session in the database."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    messages_collection = db.messages
    sessions_collection = db.sessions

    message_data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    }
    try:
        messages_collection.insert_one(message_data)
        # Update session's lastModified timestamp (ensure session_id is valid ObjectId)
        if ObjectId.is_valid(session_id):
            sessions_collection.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"lastModified": datetime.now()}}
            )
        else:
            logging.warning(f"Invalid session ID format when adding message (not updating lastModified): {session_id}")

        logging.info(f"Added message to history for session {session_id}: role={role}")
    except PyMongoError as e:
        logging.error(f"Error adding message to history for session {session_id}: {e}")
    except Exception as e: # Catch other potential errors
        logging.error(f"Unexpected error in add_to_history for {session_id}: {e}")


def get_history(session_id: str) -> list[dict]:
    """Gets the most recent messages for a session, up to a defined limit."""
    client = get_db_client()
    db = client.get_database("chatbot_db")
    messages_collection = db.messages

    try:
        # No need to validate ObjectId for session_id here, as it's stored as a string in messages collection
        history = list(messages_collection.find({"session_id": session_id}).sort("timestamp", 1))
        # Convert ObjectId to string and remove it for cleaner output
        for message in history:
            message['id'] = str(message['_id'])
            del message['_id']
            # Convert datetime objects to string for JSON serialization
            message['timestamp'] = message['timestamp'].isoformat() if 'timestamp' in message else None

        logging.info(f"Fetched {len(history)} messages for session {session_id}.")
        return history
    except PyMongoError as e:
        logging.error(f"Error getting history for session {session_id}: {e}")
        return []
    except Exception as e: # Catch other potential errors
        logging.error(f"Unexpected error in get_history for {session_id}: {e}")
        return []
