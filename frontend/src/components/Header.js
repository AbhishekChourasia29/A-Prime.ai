import React from 'react';

// Accept toggleSidebar as a prop
const Header = ({ toggleSidebar }) => {
    return (
        <header className="app-header">
            <div className="logo-container">
                
                {/* --- NEW BURGER MENU BUTTON --- */}
                <button className="menu-toggle-button" onClick={toggleSidebar}>
                    {/* Simple burger icon */}
                    <svg xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="3" y1="12" x2="21" y2="12"></line>
                        <line x1="3" y1="6" x2="21" y2="6"></line>
                        <line x1="3" y1="18" x2="21" y2="18"></line>
                    </svg>
                </button>

                {/* Existing Logo SVG */}
                <svg className="logo-svg" width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)">
                    <path d="M12 2L2 7V17L12 22L22 17V7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                    <path d="M2 7L12 12L22 7" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                    <path d="M12 12V22" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
                </svg>
                <h1 className="bot-name">A-Prime AI</h1>
            </div>
            <p className="bot-tagline">Your Multi-Agent Assistant</p>
        </header>
    );
};

export default Header;