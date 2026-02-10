// ═══════════════════════════════════════════════════════════
// Main Application Logic
// ═══════════════════════════════════════════════════════════

const API_BASE = 'http://127.0.0.1:5000';
const MAX_FOLLOW_UPS = 3;

// ═══════════════════════════════════════════════════════════
// State Management
// ═══════════════════════════════════════════════════════════

let appState = {
    currentSource: 'current-tab',
    messages: [],
    followUpCount: 0,
    currentContext: null,
    isProcessing: false,
    dropdownOpen: false,
    settingsOpen: false
};

// ═══════════════════════════════════════════════════════════
// DOM Elements
// ═══════════════════════════════════════════════════════════

const elements = {
    // Header controls
    summarizeBtn: document.getElementById('summarizeBtn'),
    sourceDropdown: document.getElementById('sourceDropdown'),
    settingsBtn: document.getElementById('settingsBtn'),
    settingsPanel: document.getElementById('settingsPanel'),

    // Input controls
    dynamicInputArea: document.getElementById('dynamicInputArea'),
    customUrl: document.getElementById('customUrl'),
    customText: document.getElementById('customText'),

    // Content areas
    contentArea: document.getElementById('contentArea'),
    homePage: document.getElementById('homePage'),

    // Follow-up
    followupInput: document.getElementById('followupInput'),
    followupSendBtn: document.getElementById('followupSendBtn'),
    followupCounter: document.getElementById('followupCounter'),

    // Settings
    colorSelect: document.getElementById('colorSelect')
};

// ═══════════════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════════════

async function init() {
    // Load and apply settings
    await settingsManager.load();
    settingsManager.apply();

    // Initialize settings UI
    initializeSettingsUI();

    // Set up event listeners
    setupEventListeners();

    // Update follow-up counter
    updateFollowUpCounter();

    console.log('Sum-it-up initialized');
}

// ═══════════════════════════════════════════════════════════
// Settings UI Initialization
// ═══════════════════════════════════════════════════════════

function initializeSettingsUI() {
    const settings = settingsManager.settings;

    // Set color select value
    if (elements.colorSelect) {
        elements.colorSelect.value = settings.colorPalette;
    }

    // Highlight active toggle buttons
    document.querySelectorAll('.toggle-group').forEach(group => {
        const setting = group.dataset.setting;
        const value = settings[setting];

        group.querySelectorAll('.toggle-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.value === value);
        });
    });
}

// ═══════════════════════════════════════════════════════════
// Event Listeners
// ═══════════════════════════════════════════════════════════

function setupEventListeners() {
    // Summarize button - toggle dropdown or summarize
    elements.summarizeBtn.addEventListener('click', handleSummarizeClick);

    // Source options in dropdown
    document.querySelectorAll('.source-option').forEach(option => {
        option.addEventListener('click', handleSourceSelect);
    });

    // Settings panel toggle
    elements.settingsBtn.addEventListener('click', toggleSettings);

    // Color select change
    if (elements.colorSelect) {
        elements.colorSelect.addEventListener('change', handleColorChange);
    }

    // Toggle buttons in settings
    document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', handleToggleChange);
    });

    // Follow-up input
    elements.followupSendBtn.addEventListener('click', handleFollowUp);
    elements.followupInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleFollowUp();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.summarize-dropdown-wrapper')) {
            closeDropdown();
        }
    });
}

// ═══════════════════════════════════════════════════════════
// Dropdown Handling
// ═══════════════════════════════════════════════════════════

function handleSummarizeClick(e) {
    e.stopPropagation();

    if (appState.dropdownOpen) {
        closeDropdown();
        performSummarize();
    } else {
        toggleDropdown();
    }
}

function toggleDropdown() {
    appState.dropdownOpen = !appState.dropdownOpen;
    elements.sourceDropdown.classList.toggle('hidden', !appState.dropdownOpen);
    elements.summarizeBtn.classList.toggle('dropdown-open', appState.dropdownOpen);
}

function closeDropdown() {
    appState.dropdownOpen = false;
    elements.sourceDropdown.classList.add('hidden');
    elements.summarizeBtn.classList.remove('dropdown-open');
}

function handleSourceSelect(e) {
    const source = e.currentTarget.dataset.source;

    // Update active state
    document.querySelectorAll('.source-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.source === source);
    });

    appState.currentSource = source;
    updateDynamicInputArea();
    closeDropdown();
}

function updateDynamicInputArea() {
    const source = appState.currentSource;
    const needsInput = source === 'custom-url' || source === 'custom-script';

    // Show/hide dynamic input area
    elements.dynamicInputArea.classList.toggle('hidden', !needsInput);

    // Show/hide specific input modes
    document.querySelectorAll('.input-mode').forEach(mode => {
        mode.classList.toggle('hidden', mode.dataset.mode !== source);
    });
}

// ═══════════════════════════════════════════════════════════
// Settings Panel
// ═══════════════════════════════════════════════════════════

function toggleSettings() {
    appState.settingsOpen = !appState.settingsOpen;
    elements.settingsPanel.classList.toggle('hidden', !appState.settingsOpen);
}

async function handleColorChange(e) {
    const value = e.target.value;
    await settingsManager.set('colorPalette', value);
    settingsManager.apply();
}

async function handleToggleChange(e) {
    const btn = e.currentTarget;
    const group = btn.closest('.toggle-group');
    const setting = group.dataset.setting;
    const value = btn.dataset.value;

    // Update active state
    group.querySelectorAll('.toggle-btn').forEach(b => {
        b.classList.toggle('active', b === btn);
    });

    // Save setting
    await settingsManager.set(setting, value);
    settingsManager.apply();
}

// ═══════════════════════════════════════════════════════════
// Summarization Logic
// ═══════════════════════════════════════════════════════════

async function performSummarize() {
    const source = appState.currentSource;
    const length = settingsManager.get('length');
    console.log(`[Summarize] Using length: ${length}, source: ${source}`);

    setProcessing(true);

    try {
        switch (source) {
            case 'current-tab':
                await summarizeCurrentTab(length);
                break;
            case 'youtube':
                await summarizeYouTube(length);
                break;
            case 'custom-url':
                await summarizeCustomURL(length);
                break;
            case 'custom-script':
                await summarizeCustomText(length);
                break;
        }
    } catch (error) {
        addMessage('error', `Summarization failed: ${error.message}`);
    } finally {
        setProcessing(false);
    }
}

async function summarizeCurrentTab(length) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tabs[0]?.url;

    if (!url) {
        throw new Error('Could not get current tab URL');
    }

    addMessage('user', `Summarize: ${truncateUrl(url)}`);
    addLoadingMessage();

    const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
    const endpoint = isYouTube ? '/summarize-youtube' : '/summarize-url';

    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, length })
    });

    const data = await response.json();
    removeLoadingMessage();

    if (data.error) {
        throw new Error(data.error);
    }

    addMessage('assistant', formatSummary(data.summary), { source: 'Current Tab' });
    setContext(data.summary, url, isYouTube ? 'youtube' : 'webpage', data.original_content);
}

async function summarizeYouTube(length) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tabs[0]?.url || '';

    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        throw new Error('Please navigate to a YouTube video');
    }

    addMessage('user', `Summarize YouTube: ${truncateUrl(url)}`);
    addLoadingMessage('Extracting transcript...');

    const response = await fetch(`${API_BASE}/summarize-youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, length })
    });

    const data = await response.json();
    removeLoadingMessage();

    if (data.error) {
        throw new Error(data.error);
    }

    addMessage('assistant', formatSummary(data.summary), { source: 'YouTube' });
    setContext(data.summary, url, 'youtube', data.original_content);
}

async function summarizeCustomURL(length) {
    const url = elements.customUrl.value.trim();

    if (!url) {
        throw new Error('Please enter a URL');
    }

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        throw new Error('URL must start with http:// or https://');
    }

    addMessage('user', `Summarize: ${truncateUrl(url)}`);
    addLoadingMessage();

    const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
    const endpoint = isYouTube ? '/summarize-youtube' : '/summarize-url';

    const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, length })
    });

    const data = await response.json();
    removeLoadingMessage();

    if (data.error) {
        throw new Error(data.error);
    }

    addMessage('assistant', formatSummary(data.summary), { source: 'URL' });
    setContext(data.summary, url, isYouTube ? 'youtube' : 'webpage', data.original_content);

    elements.customUrl.value = '';
}

async function summarizeCustomText(length) {
    const text = elements.customText.value.trim();

    if (!text || text.length < 20) {
        throw new Error('Please enter at least 20 characters');
    }

    const preview = text.length > 80 ? text.substring(0, 80) + '...' : text;
    addMessage('user', preview);
    addLoadingMessage();

    const response = await fetch(`${API_BASE}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, length })
    });

    const data = await response.json();
    removeLoadingMessage();

    if (data.error) {
        throw new Error(data.error);
    }

    addMessage('assistant', formatSummary(data.summary), { source: 'Custom Text' });
    setContext(data.summary, null, 'text', data.original_content);

    elements.customText.value = '';
}

function setContext(summary, url, type, originalContent = '') {
    appState.currentContext = { summary, url, type, originalContent: originalContent || '' };
    appState.followUpCount = 0;
    enableFollowUps();
    updateFollowUpCounter();
}

// ═══════════════════════════════════════════════════════════
// Follow-up Questions
// ═══════════════════════════════════════════════════════════

async function handleFollowUp() {
    const question = elements.followupInput.value.trim();

    if (!question) return;

    if (appState.followUpCount >= MAX_FOLLOW_UPS) {
        addMessage('error', 'Follow-up limit reached. Start a new summary.');
        return;
    }

    if (!appState.currentContext) {
        addMessage('error', 'Please summarize something first.');
        return;
    }

    setProcessing(true);
    addMessage('user', question);
    addLoadingMessage('Thinking...');

    try {
        const history = appState.messages
            .filter(m => m.role === 'user' || m.role === 'assistant')
            .map(m => ({ role: m.role, content: m.content }));

        const response = await fetch(`${API_BASE}/follow-up`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question,
                context: appState.currentContext.summary,
                original_content: appState.currentContext.originalContent,
                history
            })
        });

        const data = await response.json();
        removeLoadingMessage();

        if (data.error) {
            throw new Error(data.error);
        }

        appState.followUpCount++;
        addMessage('assistant', formatSummary(data.answer), {
            source: `Follow-up ${appState.followUpCount}/${MAX_FOLLOW_UPS}`
        });

        updateFollowUpCounter();
        elements.followupInput.value = '';

    } catch (error) {
        removeLoadingMessage();
        addMessage('error', `Follow-up failed: ${error.message}`);
    } finally {
        setProcessing(false);
    }
}

function enableFollowUps() {
    elements.followupInput.disabled = false;
    elements.followupSendBtn.disabled = false;
}

function disableFollowUps() {
    elements.followupInput.disabled = true;
    elements.followupSendBtn.disabled = true;
}

function updateFollowUpCounter() {
    const remaining = MAX_FOLLOW_UPS - appState.followUpCount;

    if (!appState.currentContext) {
        elements.followupCounter.textContent = '';
        elements.followupCounter.className = 'followup-counter';
        disableFollowUps();
        return;
    }

    if (remaining > 0) {
        elements.followupCounter.textContent = `${remaining} follow-up${remaining !== 1 ? 's' : ''} remaining`;
        elements.followupCounter.className = remaining === 1 ? 'followup-counter warning' : 'followup-counter';
    } else {
        elements.followupCounter.textContent = 'Limit reached';
        elements.followupCounter.className = 'followup-counter limit';
        disableFollowUps();
    }
}

// ═══════════════════════════════════════════════════════════
// UI Helpers
// ═══════════════════════════════════════════════════════════

function hideHomePage() {
    if (elements.homePage) {
        elements.homePage.classList.add('hidden');
    }
}

function addMessage(role, content, metadata = {}) {
    hideHomePage();

    const message = document.createElement('div');
    message.className = `message ${role}`;

    const avatarContent = role === 'user' ? '👤' : role === 'assistant' ? '✨' : '⚠️';
    const headerText = role === 'user' ? 'You' : role === 'assistant' ? 'Summary' : 'Error';

    let metaHTML = '';
    if (metadata.source) {
        metaHTML = `<div class="message-meta">${metadata.source}</div>`;
    }

    message.innerHTML = `
    <div class="message-header">
      <div class="message-avatar">${avatarContent}</div>
      <span>${headerText}</span>
    </div>
    <div class="message-content">
      ${content}
      ${metaHTML}
    </div>
  `;

    elements.contentArea.appendChild(message);
    elements.contentArea.scrollTop = elements.contentArea.scrollHeight;

    appState.messages.push({ role, content, metadata });
}

function addLoadingMessage(text = 'Summarizing...') {
    hideHomePage();

    const loading = document.createElement('div');
    loading.className = 'message assistant';
    loading.id = 'loadingMessage';
    loading.innerHTML = `
    <div class="message-header">
      <div class="message-avatar">✨</div>
      <span>AI</span>
    </div>
    <div class="message-content">
      <div class="loading-content">
        <div class="loading-spinner"></div>
        <span>${text}</span>
      </div>
    </div>
  `;

    elements.contentArea.appendChild(loading);
    elements.contentArea.scrollTop = elements.contentArea.scrollHeight;
}

function removeLoadingMessage() {
    const loading = document.getElementById('loadingMessage');
    if (loading) loading.remove();
}

function setProcessing(isProcessing) {
    appState.isProcessing = isProcessing;
    elements.summarizeBtn.disabled = isProcessing;

    if (!isProcessing && appState.currentContext) {
        enableFollowUps();
    } else if (isProcessing) {
        disableFollowUps();
    }
}

function truncateUrl(url) {
    try {
        const parsed = new URL(url);
        let display = parsed.hostname.replace('www.', '');
        if (parsed.pathname.length > 1) {
            display += parsed.pathname.length > 30
                ? parsed.pathname.substring(0, 30) + '...'
                : parsed.pathname;
        }
        return display;
    } catch {
        return url.length > 50 ? url.substring(0, 50) + '...' : url;
    }
}

function formatSummary(text) {
    if (!text) return '';

    // Convert markdown-style formatting to HTML
    return text
        // Headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // Bold and italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Lists
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.+<\/li>\n?)+/g, '<ul>$&</ul>')
        // Paragraphs
        .replace(/\n\n/g, '</p><p>')
        .replace(/^(.+)$/gm, (match) => {
            if (match.startsWith('<')) return match;
            return match;
        });
}

// ═══════════════════════════════════════════════════════════
// Start Application
// ═══════════════════════════════════════════════════════════

init();
