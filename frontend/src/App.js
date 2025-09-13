import React, { useState, useEffect, useRef, useCallback } from 'react';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import TypingIndicator from './components/TypingIndicator';
import HistorySidebar from './components/HistorySidebar';
import Header from './components/Header';
import './App.css'; // Ensure App.css is correctly imported

function App() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [sessions, setSessions] = useState([]);
    const [theme, setTheme] = useState('dark');
    const messagesEndRef = useRef(null);
    const API_URL = 'https://a-prime-ai.onrender.com'; // Your FastAPI backend URL

    // --- Theme Management ---
    useEffect(() => {
        const savedTheme = localStorage.getItem('chat-theme') || 'dark';
        setTheme(savedTheme);
        document.body.setAttribute('data-theme', savedTheme);
    }, []);

    const toggleTheme = () => {
        const newTheme = theme === 'dark' ? 'light' : 'dark';
        setTheme(newTheme);
        localStorage.setItem('chat-theme', newTheme);
        document.body.setAttribute('data-theme', newTheme);
    };

    // --- API & Session Functions ---

    // Fetches all chat sessions for the sidebar
    const fetchSessions = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/api/sessions`);
            const data = await response.json();
            setSessions(data);
            return data; // Return data for immediate use if needed
        } catch (error) {
            console.error("Error fetching sessions:", error);
            return [];
        }
    }, [API_URL]);

    // Fetches messages for the currently active session
    const fetchMessages = useCallback(async (currentSessionId) => {
        if (!currentSessionId) {
            setMessages([]);
            return;
        }
        setIsLoading(true); // Indicate loading while fetching history
        try {
            const response = await fetch(`${API_URL}/api/chat_history/${currentSessionId}`);
            const data = await response.json();
            // Ensure data is an array and each message has 'id', 'role', 'text'
            // The backend is now responsible for mapping 'content' to 'text' and adding isImage/isCode flags.
            setMessages(data);
        } catch (error) {
            console.error("Error fetching messages:", error);
            setMessages([]); // Clear messages on error
        } finally {
            setIsLoading(false);
        }
    }, [API_URL]);

    // Starts a new chat session
    const startNewChat = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/api/new_chat`, { method: 'POST' });
            const data = await response.json();
            setSessionId(data.session_id);
            setMessages([]); // Clear messages for the new chat
            setInput(''); // Clear input field
            await fetchSessions(); // Refresh sessions list to show the new chat
        } catch (error) {
            console.error("Error starting new chat:", error);
        }
    }, [API_URL, fetchSessions]);

    // Handles sending a message
    const sendMessage = useCallback(async () => {
        if (input.trim() === '') return;

        // Use a temporary ID for the user message until it's saved to DB and re-fetched
        const userMessage = { id: Date.now(), role: 'user', text: input };
        // Optimistically add user message to UI
        setMessages(prevMessages => [...prevMessages, userMessage]);
        setInput('');
        setIsLoading(true);

        // If no session is active, create a new one first
        let currentSessionId = sessionId;
        if (!currentSessionId) {
            try {
                const response = await fetch(`${API_URL}/api/new_chat`, { method: 'POST' });
                const data = await response.json();
                currentSessionId = data.session_id;
                setSessionId(currentSessionId);
            } catch (error) {
                console.error("Error creating new session before sending message:", error);
                setIsLoading(false);
                return;
            }
        }

        try {
            const response = await fetch(`${API_URL}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage.text, session_id: currentSessionId }),
            });
            const data = await response.json();

            // Check for new_title and update sessions if present
            if (data.new_title) {
                // Update the title of the current session in the sessions state
                setSessions(prevSessions => prevSessions.map(session =>
                    session.id === currentSessionId ? { ...session, title: data.new_title } : session
                ));
            }

            // The backend already sends formatted messages, so just add the response
            setMessages(prevMessages => [...prevMessages, {
                id: Date.now() + 1, // Unique ID for assistant message
                role: 'assistant',
                text: data.response,
                isImage: data.response.startsWith('data:image/'), // Check if it's an image
                isCode: data.response.includes('```python') && data.response.includes('```') // Check if it's code
            }]);

            // After successful message, ensure all sessions are re-fetched to update lastModified
            await fetchSessions();

        } catch (error) {
            console.error("Error sending message:", error);
            // Add an error message to the chat
            setMessages(prevMessages => [...prevMessages, {
                id: Date.now() + 1,
                role: 'assistant',
                text: "Sorry, I couldn't get a response. Please try again.",
                isError: true
            }]);
        } finally {
            setIsLoading(false);
        }
    }, [input, sessionId, API_URL, fetchSessions]);


    // Handles session deletion
    const handleDeleteSession = useCallback(async (sid) => {
        try {
            const response = await fetch(`${API_URL}/api/sessions/${sid}`, { method: 'DELETE' });
            if (response.ok) {
                const updatedSessions = await fetchSessions(); // Re-fetch sessions after deletion
                // If the deleted session was the active one, switch to the first available session or start a new chat
                if (sessionId === sid) {
                    if (updatedSessions.length > 0) {
                        setSessionId(updatedSessions[0].id);
                    } else {
                        startNewChat();
                    }
                }
            } else {
                console.error("Failed to delete session:", response.statusText);
            }
        } catch (error) { console.error("Error deleting session:", error); }
    }, [sessionId, fetchSessions, startNewChat, API_URL]);


    // --- Effects ---

    // Initial fetch of sessions on component mount
    useEffect(() => {
        const loadInitialData = async () => {
            const fetched = await fetchSessions();
            if (fetched.length > 0) {
                // Set the most recently modified session as active initially
                // Sessions are already sorted by lastModified in memory.py
                setSessionId(fetched[0].id);
            } else {
                startNewChat(); // Start a new chat if no sessions exist
            }
        };
        loadInitialData();
    }, [fetchSessions, startNewChat]);

    // Fetch messages whenever the active sessionId changes
    useEffect(() => {
        fetchMessages(sessionId);
    }, [sessionId, fetchMessages]);

    // Scroll to the bottom of the messages container
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]); // Scroll when messages change or loading state changes

    return (
        <div className="app-container">
            <HistorySidebar
                sessions={sessions}
                activeSessionId={sessionId}
                onSessionClick={setSessionId}
                onNewChat={startNewChat}
                onDeleteSession={handleDeleteSession}
                theme={theme}
                toggleTheme={toggleTheme}
            />
            <main className="chat-area">
            <Header /> {/* <-- Add the Header component here */}
                <div className="chat-window">
                    <div className="messages-container">
                        {messages.map((msg) => (
                            <ChatMessage key={msg.id} message={msg} />
                        ))}
                        {isLoading && <TypingIndicator />}
                        <div ref={messagesEndRef} />
                    </div>
                </div>
                <div className="chat-input-area">
                    <div className="chat-input-wrapper">
                        <ChatInput
                            input={input}
                            setInput={setInput}
                            sendMessage={sendMessage}
                            isLoading={isLoading}
                        />
                    </div>
                </div>
            </main>
        </div>
    );
}

export default App;
