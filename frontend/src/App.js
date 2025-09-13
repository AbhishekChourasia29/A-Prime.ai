import React, { useState, useEffect, useRef, useCallback } from 'react';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import TypingIndicator from './components/TypingIndicator';
import HistorySidebar from './components/HistorySidebar';
import Header from './components/Header';
import './App.css'; 

function App() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [sessions, setSessions] = useState([]);
    const [theme, setTheme] = useState('dark');
    
    // --- NEW STATE FOR MOBILE ---
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    
    const messagesEndRef = useRef(null);
    const API_URL = 'https://a-prime-ai.onrender.com';

    // --- NEW HELPER FUNCTIONS ---
    const toggleSidebar = () => {
        setIsSidebarOpen(prev => !prev);
    };

    // New handler to close sidebar on session click (for mobile)
    const handleSessionClick = (sid) => {
        setSessionId(sid);
        setIsSidebarOpen(false); // Close sidebar after selection
    };

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

    // --- API & Session Functions (No changes needed inside these functions) ---

    // Fetches all chat sessions for the sidebar
    const fetchSessions = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/api/sessions`);
            const data = await response.json();
            setSessions(data);
            return data;
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
        setIsLoading(true);
        try {
            const response = await fetch(`${API_URL}/api/chat_history/${currentSessionId}`);
            const data = await response.json();
            setMessages(data);
        } catch (error) {
            console.error("Error fetching messages:", error);
            setMessages([]);
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
            setMessages([]); 
            setInput(''); 
            await fetchSessions(); 
            setIsSidebarOpen(false); // Also close sidebar on new chat
        } catch (error) {
            console.error("Error starting new chat:", error);
        }
    }, [API_URL, fetchSessions]);

    // Handles sending a message
    const sendMessage = useCallback(async () => {
        if (input.trim() === '') return;

        const userMessage = { id: Date.now(), role: 'user', text: input };
        setMessages(prevMessages => [...prevMessages, userMessage]);
        setInput('');
        setIsLoading(true);

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

            if (data.new_title) {
                setSessions(prevSessions => prevSessions.map(session =>
                    session.id === currentSessionId ? { ...session, title: data.new_title } : session
                ));
            }

            setMessages(prevMessages => [...prevMessages, {
                id: Date.now() + 1, 
                role: 'assistant',
                text: data.response,
                isImage: data.response.startsWith('data:image/'),
                isCode: data.response.includes('```') 
            }]);

            await fetchSessions();

        } catch (error) {
            console.error("Error sending message:", error);
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
                const updatedSessions = await fetchSessions(); 
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

    useEffect(() => {
        const loadInitialData = async () => {
            const fetched = await fetchSessions();
            if (fetched.length > 0) {
                setSessionId(fetched[0].id);
            } else {
                startNewChat(); 
            }
        };
        loadInitialData();
    }, [fetchSessions, startNewChat]); // Dependencies are correct

    useEffect(() => {
        fetchMessages(sessionId);
    }, [sessionId, fetchMessages]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]);

    return (
        <div className="app-container">
            <HistorySidebar
                sessions={sessions}
                activeSessionId={sessionId}
                // Use the new handler here
                onSessionClick={handleSessionClick} 
                onNewChat={startNewChat}
                onDeleteSession={handleDeleteSession}
                theme={theme}
                toggleTheme={toggleTheme}
                // Pass the state down
                isSidebarOpen={isSidebarOpen} 
            />
            <main className="chat-area">
                <Header 
                    // Pass the toggle function to the header
                    toggleSidebar={toggleSidebar} 
                />
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