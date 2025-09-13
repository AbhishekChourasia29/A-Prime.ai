import React from 'react';

const ThemeToggle = ({ theme, toggleTheme }) => {
    return (
        <button onClick={toggleTheme} className="theme-toggle-button">
            {theme === 'dark' ? '☀️ Switch to Light Mode' : '🌙 Switch to Dark Mode'}
        </button>
    );
};

export default ThemeToggle;
