import React from 'react';

const Header = () => {
    return (
        <header className="app-header">
            <div className="logo-container">
                {/* You can replace this with your own SVG or <img> tag */}
                <svg className="logo-svg" width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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