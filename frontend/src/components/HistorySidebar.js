import React from 'react';
import ThemeToggle from './ThemeToggle'; // Import the new component

const HistorySidebar = ({ sessions, onSessionClick, onNewChat, activeSessionId, onDeleteSession, theme, toggleTheme }) => {

    const handleDelete = (e, sessionId) => {
        e.stopPropagation();
        // IMPORTANT: Replaced window.confirm with a direct call for demonstration.
        // In a real application, you would implement a custom modal for confirmation
        // as per the guidelines to avoid browser's alert/confirm dialogs.
        console.log(`Attempting to delete session: ${sessionId}`);
        onDeleteSession(sessionId);
    };

    return (
        <aside className="history-sidebar">
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
