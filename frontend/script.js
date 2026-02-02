/**
 * EduBot Frontend - Chat Interface Logic
 * Handles UI interactions, API communication, and conversation management
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const API_BASE_URL = window.location.origin;
const STORAGE_KEY = 'edubot_conversations';
const THEME_KEY = 'edubot_theme';

// Faster response settings
const FAST_MODE = {
    temperature: 0.3,
    max_tokens: 512
};

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let currentConversation = {
    id: generateId(),
    title: 'New Chat',
    messages: [],
    createdAt: new Date().toISOString(),
};

let conversations = [];
let isLoading = false;

// ============================================================================
// DOM ELEMENTS
// ============================================================================

const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const conversationsList = document.getElementById('conversationsList');
const themeToggle = document.getElementById('themeToggle');
const loadingIndicator = document.getElementById('loadingIndicator');
const toastContainer = document.getElementById('toastContainer');
const statusIndicator = document.getElementById('statusIndicator');

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    loadConversations();
    checkBackendStatus();
    loadTheme();
});

function initializeApp() {
    console.log('🚀 EduBot initialized');
    renderWelcomeMessage();
}

function setupEventListeners() {
    sendBtn.addEventListener('click', handleSendMessage);
    
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });
    
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 80) + 'px';
    });
    
    newChatBtn.addEventListener('click', startNewChat);
    themeToggle.addEventListener('click', toggleTheme);
    
    // Add event listeners for feedback and bug report buttons
    document.getElementById('feedbackBtn').addEventListener('click', openFeedbackModal);
    document.getElementById('bugReportBtn').addEventListener('click', openBugReportModal);
}

// ============================================================================
// BACKEND COMMUNICATION
// ============================================================================

async function checkBackendStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            statusIndicator.style.color = '#10a37f';
            console.log('✓ Backend connected');
        }
    } catch (error) {
        statusIndicator.style.color = '#ef4444';
        console.error('✗ Backend connection failed:', error);
        showToast('Backend not available. Make sure the server is running.', 'error');
    }
}

async function sendChatMessage(messages) {
    try {
        setLoading(true);
        console.log('Sending message to backend...');
        
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: messages.slice(-3),
                ...FAST_MODE
            }),
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        if (!response.body) {
            throw new Error('No response body');
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let buffer = ''; // Buffer to accumulate incomplete chunks
        
        // Create assistant message element for streaming
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = '🤖';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = 'Thinking...';
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        messagesContainer.appendChild(messageDiv);
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            buffer += chunk;
            
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    if (data && data !== '[DONE]') {
                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.choices && parsed.choices[0] && parsed.choices[0].delta && parsed.choices[0].delta.content) {
                                const content = parsed.choices[0].delta.content;
                                fullResponse += content;
                                contentDiv.innerHTML = formatMessageContent(fullResponse);
                                scrollToBottom();
                            }
                        } catch (e) {
                            // Skip invalid JSON
                        }
                    }
                }
            }
        }
        
        // If no response was received, show error
        if (!fullResponse.trim()) {
            console.log('No response extracted, fullResponse is empty');
            contentDiv.innerHTML = 'No response received. Please try again.';
            throw new Error('Empty response from server');
        } else {
            console.log('Final response length:', fullResponse.length);
        }
        
        // Final formatting and MathJax rendering
        setTimeout(() => {
            if (window.MathJax) {
                MathJax.typesetPromise([contentDiv]).catch((err) => console.log('MathJax error:', err));
            }
        }, 100);
        
        return fullResponse;
    } catch (error) {
        console.error('Error sending message:', error);
        showToast('Failed to get response. Check backend connection.', 'error');
        throw error;
    } finally {
        setLoading(false);
    }
}

// ============================================================================
// MESSAGE HANDLING
// ============================================================================

async function handleSendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) return;
    if (isLoading) return;
    
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    if (currentConversation.messages.length === 0) {
        messagesContainer.innerHTML = '';
    }
    
    currentConversation.messages.push({
        role: 'user',
        content: message,
    });
    
    renderMessage('user', message);
    
    try {
        const response = await sendChatMessage(currentConversation.messages);
        
        currentConversation.messages.push({
            role: 'assistant',
            content: response,
        });
        
        if (currentConversation.messages.length === 2) {
            currentConversation.title = message.substring(0, 50) + (message.length > 50 ? '...' : '');
        }
        
        saveConversations();
        updateConversationsList();
        
    } catch (error) {
        console.error('Error:', error);
        showToast('Failed to send message. Please try again.', 'error');
    }
}

function renderMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessageContent(content);
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    
    messagesContainer.appendChild(messageDiv);
    
    // Smooth scroll to bottom
    scrollToBottom();
    
    setTimeout(() => {
        if (window.MathJax) {
            MathJax.typesetPromise([contentDiv]).catch((err) => console.log('MathJax error:', err));
        }
        scrollToBottom(); // Scroll again after MathJax rendering
    }, 100);
}

function formatMessageContent(content) {
    let formatted = content
        .replace(/&#39;/g, "'")
        .replace(/&quot;/g, '"')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/```(\w+)?\s*\n([\s\S]*?)\n```/g, (match, language, code) => {
            const lang = language || 'text';
            const codeId = 'code_' + Math.random().toString(36).substr(2, 9);
            return `<div class="code-block-wrapper">
                <div class="code-header">
                    <span class="code-language">${lang}</span>
                    <button class="copy-button" onclick="copyCode('${codeId}')" title="Copy code">Copy</button>
                </div>
                <pre class="code-block"><code id="${codeId}">${code}</code></pre>
            </div>`;
        })
        .replace(/```\s*\n([\s\S]*?)\n```/g, (match, code) => {
            const codeId = 'code_' + Math.random().toString(36).substr(2, 9);
            return `<div class="code-block-wrapper">
                <div class="code-header">
                    <span class="code-language">code</span>
                    <button class="copy-button" onclick="copyCode('${codeId}')" title="Copy code">Copy</button>
                </div>
                <pre class="code-block"><code id="${codeId}">${code}</code></pre>
            </div>`;
        })
        .replace(/^### (.*$)/gm, '<h3 class="section-header">$1</h3>')
        .replace(/^## (.*$)/gm, '<h2 class="main-header">$1</h2>')
        .replace(/^# (.*$)/gm, '<h1 class="title-header">$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="bold-text">$1</strong>')
        .replace(/\*(.*?)\*/g, '<em class="italic-text">$1</em>')
        .replace(/`(.*?)`/g, '<code class="inline-code">$1</code>')
        .replace(/\b(f\([^)]+\))\b/g, '<span class="math-function">$1</span>')
        .replace(/\b(\w+)\^(\d+)\b/g, '<span class="math-expression">$1<sup>$2</sup></span>')
        .replace(/\b(x|y|z|a|b|c)\s*=\s*([^\s]+)/g, '<span class="math-equation">$1 = $2</span>')
        .replace(/\b(\d+x\^?\d*|\d*x\^\d+|\d+x)\b/g, '<span class="math-term">$1</span>')
        .replace(/^\s*[-*+]\s+(.*)$/gm, '<li class="bullet-item">$1</li>')
        .replace(/^\s*\d+\.\s+(.*)$/gm, '<li class="numbered-item">$1</li>')
        .replace(/((<li class="bullet-item">.*?<\/li>\s*)+)/g, '<ul class="bullet-list">$1</ul>')
        .replace(/((<li class="numbered-item">.*?<\/li>\s*)+)/g, '<ol class="numbered-list">$1</ol>')
        .replace(/^>\s+(.*)$/gm, '<blockquote class="quote-text">$1</blockquote>')
        .replace(/\n/g, '<br>');
    
    return formatted;
}

function copyCode(codeId) {
    const codeElement = document.getElementById(codeId);
    if (!codeElement) return;
    
    const code = codeElement.textContent;
    
    const textarea = document.createElement('textarea');
    textarea.value = code;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    
    textarea.select();
    try {
        document.execCommand('copy');
        
        const button = document.querySelector(`button[onclick="copyCode('${codeId}')"]`);
        if (button) {
            const originalText = button.textContent;
            button.textContent = 'Copied!';
            button.style.backgroundColor = '#10a37f';
            
            setTimeout(() => {
                button.textContent = originalText;
                button.style.backgroundColor = '';
            }, 2000);
        }
        
        showToast('Code copied to clipboard!', 'success');
    } catch (err) {
        showToast('Failed to copy code', 'error');
    }
    
    document.body.removeChild(textarea);
}

function renderWelcomeMessage() {
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🎓</div>
            <h2>EduBot - Fast Learning Assistant</h2>
            <p>Ask me anything and I'll help you understand concepts through guided learning!</p>
            
            <div class="example-prompts">
                <button class="example-btn" onclick="sendMessage('How does photosynthesis work?')">
                    How does photosynthesis work?
                </button>
                <button class="example-btn" onclick="sendMessage('Explain derivatives in calculus')">
                    Explain derivatives in calculus
                </button>
                <button class="example-btn" onclick="sendMessage('Help me understand the French Revolution')">
                    Help me understand the French Revolution
                </button>
            </div>
        </div>
    `;
}

function sendMessage(text) {
    messageInput.value = text;
    messageInput.focus();
    handleSendMessage();
}

// ============================================================================
// CONVERSATION MANAGEMENT
// ============================================================================

function startNewChat() {
    if (currentConversation.messages.length > 0) {
        saveConversations();
    }
    
    currentConversation = {
        id: generateId(),
        title: 'New Chat',
        messages: [],
        createdAt: new Date().toISOString(),
    };
    
    renderWelcomeMessage();
    updateConversationsList();
}

function loadConversation(id) {
    const conversation = conversations.find(c => c.id === id);
    if (conversation) {
        currentConversation = JSON.parse(JSON.stringify(conversation));
        renderConversation();
        updateConversationsList();
    }
}

function renderConversation() {
    messagesContainer.innerHTML = '';
    
    if (currentConversation.messages.length === 0) {
        renderWelcomeMessage();
        return;
    }
    
    currentConversation.messages.forEach(msg => {
        renderMessage(msg.role, msg.content);
    });
    
    if (window.MathJax) {
        MathJax.typesetPromise([messagesContainer]).catch((err) => console.log('MathJax error:', err));
    }
}

function updateConversationsList() {
    conversationsList.innerHTML = '';
    
    conversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = `conversation-item ${conv.id === currentConversation.id ? 'active' : ''}`;
        item.textContent = conv.title;
        item.addEventListener('click', () => loadConversation(conv.id));
        conversationsList.appendChild(item);
    });
    
    // Auto-scroll to the active conversation
    const activeItem = conversationsList.querySelector('.conversation-item.active');
    if (activeItem) {
        activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// ============================================================================
// STORAGE
// ============================================================================

function saveConversations() {
    const existingIndex = conversations.findIndex(c => c.id === currentConversation.id);
    if (existingIndex >= 0) {
        conversations[existingIndex] = currentConversation;
    } else {
        conversations.unshift(currentConversation);
    }
    
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

function loadConversations() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
        conversations = JSON.parse(stored);
        updateConversationsList();
    }
}

// ============================================================================
// THEME MANAGEMENT
// ============================================================================

function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.classList.toggle('dark-mode');
    localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
    updateThemeIcon();
}

function loadTheme() {
    const theme = localStorage.getItem(THEME_KEY) || 'light';
    if (theme === 'dark') {
        document.documentElement.classList.add('dark-mode');
    }
    updateThemeIcon();
}

function updateThemeIcon() {
    const isDark = document.documentElement.classList.contains('dark-mode');
    themeToggle.textContent = isDark ? '☀️' : '🌙';
}

// ============================================================================
// UI UTILITIES
// ============================================================================

function setLoading(loading) {
    isLoading = loading;
    loadingIndicator.classList.toggle('active', loading);
    sendBtn.classList.toggle('loading', loading);
    sendBtn.disabled = loading;
    messageInput.disabled = loading;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

// ============================================================================
// UTILITIES
// ============================================================================

function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

function scrollToBottom() {
    messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth'
    });
}

// ============================================================================
// MODAL FUNCTIONS
// ============================================================================

function openFeedbackModal() {
    document.getElementById('feedbackModal').classList.add('active');
    document.getElementById('feedbackText').focus();
}

function closeFeedbackModal() {
    document.getElementById('feedbackModal').classList.remove('active');
    document.getElementById('feedbackText').value = '';
}

function openBugReportModal() {
    document.getElementById('bugReportModal').classList.add('active');
    document.getElementById('bugReportText').focus();
}

function closeBugReportModal() {
    document.getElementById('bugReportModal').classList.remove('active');
    document.getElementById('bugReportText').value = '';
}

async function submitFeedback() {
    const feedback = document.getElementById('feedbackText').value.trim();
    if (!feedback) {
        showToast('Please enter your feedback before submitting.', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/submit-feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                feedback: feedback,
                user_agent: navigator.userAgent
            })
        });
        
        if (response.ok) {
            showToast('Thank you for your feedback! We appreciate your input.', 'success');
            closeFeedbackModal();
        } else {
            throw new Error('Failed to submit feedback');
        }
    } catch (error) {
        console.error('Error submitting feedback:', error);
        showToast('Failed to submit feedback. Please try again.', 'error');
    }
}

async function submitBugReport() {
    const bugReport = document.getElementById('bugReportText').value.trim();
    if (!bugReport) {
        showToast('Please describe the bug before submitting.', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/submit-bug-report`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                bug_report: bugReport,
                user_agent: navigator.userAgent
            })
        });
        
        if (response.ok) {
            showToast('Bug report submitted! We\'ll look into this issue.', 'success');
            closeBugReportModal();
        } else {
            throw new Error('Failed to submit bug report');
        }
    } catch (error) {
        console.error('Error submitting bug report:', error);
        showToast('Failed to submit bug report. Please try again.', 'error');
    }
}

// Close modals when clicking outside
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        if (e.target.id === 'feedbackModal') {
            closeFeedbackModal();
        } else if (e.target.id === 'bugReportModal') {
            closeBugReportModal();
        }
    }
});

// Close modals with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeFeedbackModal();
        closeBugReportModal();
    }
});