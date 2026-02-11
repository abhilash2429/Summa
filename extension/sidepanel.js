

const API_BASE = 'http://127.0.0.1:5000';
const MAX_FOLLOW_UPS = 3;



let appState = {
    currentSource: 'current-tab',
    messages: [],
    followUpCount: 0,
    currentContext: null,
    isProcessing: false,
    dropdownOpen: false,
    settingsOpen: false
};



const elements = {
    // Header controls
    summarizeBtn: document.getElementById('summarizeBtn'),
    sourceDropdown: document.getElementById('sourceDropdown'),
    settingsBtn: document.getElementById('settingsBtn'),
    settingsPanel: document.getElementById('settingsPanel'),
    appTitle: document.getElementById('appTitle'),
    deleteBtn: document.getElementById('deleteBtn'),

    // Input controls
    dynamicInputArea: document.getElementById('dynamicInputArea'),
    customUrl: document.getElementById('customUrl'),
    customText: document.getElementById('customText'),

    // Content areas
    contentArea: document.getElementById('contentArea'),
    homePage: document.getElementById('homePage'),
    jumpToLatest: document.getElementById('jumpToLatest'),

    // Follow-up
    followupInput: document.getElementById('followupInput'),
    followupSendBtn: document.getElementById('followupSendBtn'),
    followupCounter: document.getElementById('followupCounter'),

    // Settings
    colorSelect: document.getElementById('colorSelect')
};



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



function setupEventListeners() {
    // Summarize button - direct click summarizes
    elements.summarizeBtn.addEventListener('click', (e) => {
        // If clicking the chevron, toggle dropdown
        if (e.target.closest('.btn-chevron')) {
            e.stopPropagation();
            toggleDropdown();
        } else {
            // Clicking the button itself - close dropdown if open and summarize
            if (appState.dropdownOpen) {
                closeDropdown();
            }
            performSummarize();
        }
    });

    // Source options in dropdown
    document.querySelectorAll('.source-option').forEach(option => {
        option.addEventListener('click', handleSourceSelect);
    });

    // Settings panel toggle
    elements.settingsBtn.addEventListener('click', toggleSettings);

    // Delete conversation
    elements.deleteBtn.addEventListener('click', clearConversation);

    // Jump to latest
    elements.jumpToLatest.addEventListener('click', () => {
        elements.contentArea.scrollTo({
            top: elements.contentArea.scrollHeight,
            behavior: 'smooth'
        });
    });

    // Show/hide jump to latest on scroll
    elements.contentArea.addEventListener('scroll', handleScroll);

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

    const pageTitle = await fetchPageTitle(url);
    updateHeaderTitle(pageTitle);

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

    await streamMessage('assistant', formatSummary(data.summary), { source: pageTitle });
    setContext(data.summary, url, isYouTube ? 'youtube' : 'webpage', data.original_content, pageTitle);
}

async function summarizeYouTube(length) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tabs[0]?.url || '';

    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        throw new Error('Please navigate to a YouTube video');
    }

    updateHeaderTitle('YouTube Video');

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

    await streamMessage('assistant', formatSummary(data.summary), { source: 'YouTube Video' });
    setContext(data.summary, url, 'youtube', data.original_content, 'YouTube Video');
}

async function summarizeCustomURL(length) {
    const url = elements.customUrl.value.trim();

    if (!url) {
        throw new Error('Please enter a URL');
    }

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        throw new Error('URL must start with http:// or https://');
    }

    const pageTitle = await fetchPageTitle(url);
    updateHeaderTitle(pageTitle);

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

    await streamMessage('assistant', formatSummary(data.summary), { source: pageTitle });
    setContext(data.summary, url, isYouTube ? 'youtube' : 'webpage', data.original_content, pageTitle);

    elements.customUrl.value = '';
}

async function summarizeCustomText(length) {
    const text = elements.customText.value.trim();

    if (!text || text.length < 20) {
        throw new Error('Please enter at least 20 characters');
    }

    updateHeaderTitle('Custom Text Summary');

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

    await streamMessage('assistant', formatSummary(data.summary), { source: 'Custom Text' });
    setContext(data.summary, null, 'text', data.original_content, 'Custom Text Summary');

    elements.customText.value = '';
}

function setContext(summary, url, type, originalContent = '', title = '') {
    appState.currentContext = { summary, url, type, originalContent: originalContent || '', title };
    appState.followUpCount = 0;
    enableFollowUps();
    updateFollowUpCounter();
}



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

        await streamMessage('assistant', formatSummary(data.answer), {
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



function hideHomePage() {
    if (elements.homePage) {
        elements.homePage.classList.add('hidden');
    }
}

function clearConversation() {
    if (!appState.currentContext && appState.messages.length === 0) {
        return; // Nothing to clear
    }

    if (confirm('Clear all messages and start over?')) {
        // Clear state
        appState.messages = [];
        appState.followUpCount = 0;
        appState.currentContext = null;

        // Clear UI
        elements.contentArea.innerHTML = '';
        elements.homePage.classList.remove('hidden');
        elements.contentArea.appendChild(elements.homePage);

        // Reset header title
        updateHeaderTitle();

        // Disable follow-ups
        disableFollowUps();
        updateFollowUpCounter();

        // Hide jump to latest
        elements.jumpToLatest.classList.add('hidden');
    }
}

function handleScroll() {
    if (!elements.contentArea || !elements.jumpToLatest) return;

    const { scrollTop, scrollHeight, clientHeight } = elements.contentArea;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    const hasMessages = appState.messages.length > 0;

    // Show jump button if there are messages and user is not near bottom
    if (hasMessages && !isNearBottom) {
        elements.jumpToLatest.classList.remove('hidden');
    } else {
        elements.jumpToLatest.classList.add('hidden');
    }
}

function addMessage(role, content, metadata = {}) {
    hideHomePage();

    const message = document.createElement('div');
    message.className = `message ${role}`;

    let sourceHTML = '';
    if (metadata.source) {
        sourceHTML = `<span class="message-source">${metadata.source}</span>`;
    }

    message.innerHTML = `
    <div class="message-content" data-role="${role}">
      ${content}
    </div>
    ${sourceHTML}
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
    <div class="message-content" data-role="assistant">
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



async function streamMessage(role, fullText, metadata = {}) {
    hideHomePage();

    const message = document.createElement('div');
    message.className = `message ${role}`;

    let sourceHTML = '';
    if (metadata.source) {
        sourceHTML = `<span class="message-source">${metadata.source}</span>`;
    }

    message.innerHTML = `
    <div class="message-content streaming" data-role="${role}"></div>
    ${sourceHTML}
  `;

    elements.contentArea.appendChild(message);

    const contentDiv = message.querySelector('.message-content');

    const CHARS_PER_CHUNK = 5;  // Increased for smoother flow
    const INTERVAL_MS = 10;     // Decreased for faster, smoother animation
    let currentIndex = 0;

    return new Promise(resolve => {
        const streamInterval = setInterval(() => {
            if (currentIndex >= fullText.length) {
                clearInterval(streamInterval);
                contentDiv.classList.remove('streaming');
                // Replace textContent with innerHTML for markdown
                contentDiv.innerHTML = fullText;
                appState.messages.push({ role, content: fullText, metadata });
                resolve();
                return;
            }

            const nextChunk = fullText.slice(currentIndex, currentIndex + CHARS_PER_CHUNK);
            contentDiv.textContent += nextChunk;
            currentIndex += CHARS_PER_CHUNK;

            elements.contentArea.scrollTop = elements.contentArea.scrollHeight;
        }, INTERVAL_MS);
    });
}



function updateHeaderTitle(title = null) {
    if (title) {
        elements.appTitle.textContent = title;
        elements.appTitle.classList.add('has-summary');
        elements.appTitle.title = title;
    } else {
        elements.appTitle.textContent = 'Sum-it-up';
        elements.appTitle.classList.remove('has-summary');
        elements.appTitle.title = '';
    }
}

function extractTitleFromURL(url) {
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname.replace('www.', '');
        const pathname = urlObj.pathname;

        // GitHub
        if (hostname === 'github.com') {
            const parts = pathname.split('/').filter(Boolean);
            if (parts.length >= 2) return `GitHub - ${parts[0]}/${parts[1]}`;
            if (parts.length === 1) return `GitHub - ${parts[0]}`;
            return 'GitHub Page';
        }

        // Wikipedia
        if (hostname.includes('wikipedia.org')) {
            const article = pathname.split('/wiki/')[1];
            if (article) {
                const decoded = decodeURIComponent(article).replace(/_/g, ' ');
                return `${decoded} - Wikipedia`;
            }
        }

        // YouTube
        if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) {
            return 'YouTube Video';
        }

        // Generic: capitalize domain name
        const domain = hostname.split('.').slice(-2, -1)[0];
        return domain.charAt(0).toUpperCase() + domain.slice(1);

    } catch (e) {
        return 'Web Page';
    }
}

async function fetchPageTitle(url) {
    return extractTitleFromURL(url);
}



init();
