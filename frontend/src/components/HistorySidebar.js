import React from 'react';
import ThemeToggle from './ThemeToggle'; 

// Accept the new isSidebarOpen prop
const HistorySidebar = ({ 
    sessions, 
    onSessionClick, 
    onNewChat, 
    activeSessionId, 
    onDeleteSession, 
    theme, 
    toggleTheme,
    isSidebarOpen 
}) => {

    const handleDelete = (e, sessionId) => {
        e.stopPropagation();
        console.log(`Attempting to delete session: ${sessionId}`);
        onDeleteSession(sessionId);
    };

    return (
        // Add the dynamic 'open' class based on the prop
        <aside className={`history-sidebar ${isSidebarOpen ? 'open' : ''}`}>
            <div className="history-sidebar-header">
                <button className="new-chat-button" onClick={onNewChat}>
                    + New Chat
                </button>
            </div>
            <nav className="history-nav">
                {sessions.map((session) => (
                    <div
                        key={session.id}
                        className={`history-item ${session.id === activeSessionId ? 'active' : ''}`}
                        onClick={() => onSessionClick(session.id)}
                    >
                        <span className="history-item-title">{session.title}</span>
                        <button
                            className="delete-button"
                            onClick={(e) => handleDelete(e, session.id)}
                        >
                            🗑️
                        </button>
                    </div>
                ))}
            </nav>
            <div className="history-sidebar-footer">
                <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
            </div>
        </aside>
    );
};

export default HistorySidebar;