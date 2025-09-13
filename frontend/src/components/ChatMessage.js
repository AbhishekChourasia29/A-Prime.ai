import React, { useState } from 'react';
// This import is correct
import SyntaxHighlighter from 'react-syntax-highlighter/dist/esm/prism';
// This style import is also correct
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

/**
 * Improvement 1: We now pass in 'language' as a prop.
 * This component no longer needs to know about "python" specifically.
 */
const CodeBlock = ({ code, language }) => {
    const [copyText, setCopyText] = useState('Copy code');

    /**
     * Improvement 2: Replaced execCommand with the modern, async Clipboard API.
     * This is much simpler and more reliable.
     */
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(code);
            setCopyText('Copied!');
        } catch (err) {
            console.error('Failed to copy text: ', err);
            setCopyText('Failed to copy');
        }
        setTimeout(() => setCopyText('Copy code'), 2000);
    };

    // Use the detected language in the header and for the syntax highlighter.
    // If no language is provided, default to 'text'.
    const langToShow = language || 'text';

    return (
        <div className="code-message">
            <div className="code-header">
                {/* Display the dynamically detected language */}
                <span>{langToShow}</span>
                <button onClick={handleCopy}>{copyText}</button>
            </div>
            <SyntaxHighlighter 
                language={langToShow} 
                style={vscDarkPlus} 
                showLineNumbers
            >
                {code}
            </SyntaxHighlighter>
        </div>
    );
};


const ChatMessage = ({ message }) => {
    if (message.isImage) {
        return (
            <div className={`message bot`}>
                <img src={message.text} alt="Generated content" />
            </div>
        );
    }

    /**
     * Improvement 3: Upgraded Regex to capture the language.
     * /```(.*?)      <-- Capture Group 1: The language (e.g., "python", "javascript")
     * \n              <-- A newline
     * ([\s\S]*?)     <-- Capture Group 2: The code block itself
     * \n```           <-- The closing fence
     */
    if (message.isCode) {
        const codeMatch = message.text.match(/```(.*?)\n([\s\S]*?)\n```/);
        
        // Group 1 is the language, Group 2 is the code.
        const language = codeMatch ? codeMatch[1] : 'text'; // Default to 'text' if no lang specified
        const code = codeMatch ? codeMatch[2] : '';

        return (
            <div className={`message bot`}>
                {/* Pass both the code and the detected language to the component */}
                <CodeBlock code={code} language={language} />
            </div>
        );
    }

    return (
        // Use message.role ('user' or 'assistant' which maps to 'bot') for class
        <div className={`message ${message.role === 'user' ? 'user' : 'bot'}`}>
            <p>{message.text}</p>
        </div>
    );
};

export default ChatMessage;