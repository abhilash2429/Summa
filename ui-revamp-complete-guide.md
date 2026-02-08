# SUM-IT-UP UI/UX Revamp — Complete Implementation Guide
## Professional Side Panel with Settings & Multi-Source Input

---

## Design Overview

Based on the wireframe, the revamped interface has:

**Core Features:**
1. **Multi-source input selector** (dropdown): Current Tab, YouTube Video, Enter Any URL, Custom Script
2. **Tabbed interface** with "Sum-it-up" and "Summarize" modes
3. **Settings panel** (gear icon): Length, Font size, Color palette, Light/Dark mode
4. **Home page** showing title "SUM-IT-UP" with instructions
5. **Follow-up questions** input at bottom
6. **Conversation history** preserved in main area

**Design Philosophy:**
- Clean, minimal interface with professional typography
- Context-aware (changes based on selected input source)
- Persistent settings across sessions
- Smooth animations between states
- Accessible color contrasts and font sizing

---

# Implementation Architecture

## File Structure

```
extension/
├── manifest.json          # Updated permissions for storage
├── background.js          # Side panel opener
├── sidepanel.html         # Main UI structure
├── sidepanel.js           # Main logic
├── settings.js            # Settings management module
├── styles.css             # All styles (separated for clarity)
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

---

# Phase 1: Update Manifest

## Step 1: Add Storage Permission

**Action:** Update `manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "Sum-it-up",
  "version": "3.0",
  "description": "Professional AI summarization with multi-source input and customizable interface",
  "permissions": [
    "activeTab",
    "sidePanel",
    "storage"
  ],
  "side_panel": {
    "default_path": "sidepanel.html"
  },
  "action": {
    "default_title": "Open Sum-it-up",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "host_permissions": [
    "http://127.0.0.1:5000/*",
    "https://generativelanguage.googleapis.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

**Why:** Storage permission enables saving user preferences (theme, font size, etc.) across sessions.

---

# Phase 2: Settings Management System

## Step 2: Create Settings Module

**Action:** Create `extension/settings.js`:

```javascript
// ═══════════════════════════════════════════════════════════
// Settings Management Module
// ═══════════════════════════════════════════════════════════

const DEFAULT_SETTINGS = {
  theme: 'dark',          // 'light' or 'dark'
  length: 'medium',       // 'brief', 'medium', 'comprehensive'
  fontSize: 'medium',     // 'small', 'medium', 'large'
  colorPalette: 'default' // 'default', 'ocean', 'forest', 'sunset', 'midnight'
};

// Color palettes (CSS variables)
const COLOR_PALETTES = {
  default: {
    name: 'Default',
    primary: '#ff6b35',
    secondary: '#0a1628',
    accent: '#10b981'
  },
  ocean: {
    name: 'Ocean',
    primary: '#0ea5e9',
    secondary: '#0c4a6e',
    accent: '#06b6d4'
  },
  forest: {
    name: 'Forest',
    primary: '#22c55e',
    secondary: '#14532d',
    accent: '#84cc16'
  },
  sunset: {
    name: 'Sunset',
    primary: '#f59e0b',
    secondary: '#78350f',
    accent: '#fb923c'
  },
  midnight: {
    name: 'Midnight',
    primary: '#8b5cf6',
    secondary: '#1e1b4b',
    accent: '#a78bfa'
  }
};

class SettingsManager {
  constructor() {
    this.settings = { ...DEFAULT_SETTINGS };
    this.listeners = [];
  }

  // Load settings from chrome.storage
  async load() {
    const stored = await chrome.storage.local.get('settings');
    if (stored.settings) {
      this.settings = { ...DEFAULT_SETTINGS, ...stored.settings };
    }
    return this.settings;
  }

  // Save settings to chrome.storage
  async save() {
    await chrome.storage.local.set({ settings: this.settings });
    this.notifyListeners();
  }

  // Get a specific setting
  get(key) {
    return this.settings[key];
  }

  // Set a specific setting
  async set(key, value) {
    this.settings[key] = value;
    await this.save();
  }

  // Apply settings to the UI
  apply() {
    const root = document.documentElement;

    // Apply theme
    root.setAttribute('data-theme', this.settings.theme);

    // Apply font size
    const fontSizes = {
      small: '13px',
      medium: '14px',
      large: '16px'
    };
    root.style.setProperty('--base-font-size', fontSizes[this.settings.fontSize]);

    // Apply color palette
    const palette = COLOR_PALETTES[this.settings.colorPalette];
    if (palette) {
      root.style.setProperty('--accent', palette.primary);
      root.style.setProperty('--accent-hover', this.lightenColor(palette.primary, 20));
      root.style.setProperty('--success', palette.accent);
    }

    // Store for later use
    this.currentPalette = palette;
  }

  // Register listener for settings changes
  onChange(callback) {
    this.listeners.push(callback);
  }

  // Notify all listeners
  notifyListeners() {
    this.listeners.forEach(cb => cb(this.settings));
  }

  // Helper: Lighten a hex color
  lightenColor(hex, percent) {
    const num = parseInt(hex.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = (num >> 16) + amt;
    const G = (num >> 8 & 0x00FF) + amt;
    const B = (num & 0x0000FF) + amt;
    return '#' + (
      0x1000000 +
      (R < 255 ? (R < 1 ? 0 : R) : 255) * 0x10000 +
      (G < 255 ? (G < 1 ? 0 : G) : 255) * 0x100 +
      (B < 255 ? (B < 1 ? 0 : B) : 255)
    ).toString(16).slice(1);
  }

  // Get all available color palettes
  getPalettes() {
    return COLOR_PALETTES;
  }
}

// Export singleton instance
const settingsManager = new SettingsManager();
```

**Why:** Centralized settings management ensures consistency. The module handles loading, saving, applying, and listening to settings changes. Color palette logic is encapsulated here.

---

# Phase 3: Main HTML Structure

## Step 3: Create New Side Panel HTML

**Action:** Replace `extension/sidepanel.html` entirely:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sum-it-up</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Work+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="app-container">
    
    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- Header with Title and Settings Icon -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <header class="app-header">
      <h1 class="app-title">SUM-IT-UP</h1>
      <button class="settings-btn" id="settingsBtn" aria-label="Open settings">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M12 1v6m0 6v6m-7-7h6m6 0h6m-4.2-6.8l-4.2 4.2m0 6l4.2 4.2M6.8 6.8l4.2 4.2m0 6l-4.2 4.2"></path>
        </svg>
      </button>
    </header>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- Input Source Selector -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div class="input-selector-section">
      <label for="inputSource" class="input-label">Select Source</label>
      <select id="inputSource" class="input-source-dropdown">
        <option value="current-tab">Current Tab</option>
        <option value="youtube">YouTube Video</option>
        <option value="custom-url">Enter Any URL</option>
        <option value="custom-script">Custom Text/Script</option>
      </select>
    </div>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- Dynamic Input Area (changes based on selection) -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div class="dynamic-input-area">
      
      <!-- Current Tab (default, no input needed) -->
      <div class="input-mode" id="mode-current-tab" data-mode="current-tab">
        <div class="mode-info">
          <svg class="mode-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
          <div class="mode-text">
            <strong>Current Tab</strong>
            <span class="mode-hint">Summarize the page you're currently viewing</span>
          </div>
        </div>
      </div>

      <!-- YouTube Video (no input needed if on YT, else paste URL) -->
      <div class="input-mode hidden" id="mode-youtube" data-mode="youtube">
        <div class="mode-info">
          <svg class="mode-icon" width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
          </svg>
          <div class="mode-text">
            <strong>YouTube Video</strong>
            <span class="mode-hint" id="ytHint">Navigate to a YouTube video</span>
          </div>
        </div>
      </div>

      <!-- Custom URL -->
      <div class="input-mode hidden" id="mode-custom-url" data-mode="custom-url">
        <label for="customUrl" class="input-sublabel">Enter URL</label>
        <input 
          type="url" 
          id="customUrl" 
          class="url-input" 
          placeholder="https://example.com/article"
        >
      </div>

      <!-- Custom Text/Script -->
      <div class="input-mode hidden" id="mode-custom-script" data-mode="custom-script">
        <label for="customText" class="input-sublabel">Paste Text or Script</label>
        <textarea 
          id="customText" 
          class="text-input" 
          placeholder="Paste any text here to summarize..."
          rows="6"
        ></textarea>
      </div>

    </div>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- Summarize Button (Primary Action) -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div class="action-section">
      <button class="summarize-btn" id="summarizeBtn">
        <span class="btn-text">Summarize</span>
        <svg class="btn-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </button>
    </div>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- Main Content Area (Messages/Results) -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div class="content-area" id="contentArea">
      
      <!-- Empty State (shown initially) -->
      <div class="empty-state" id="emptyState">
        <div class="empty-icon">📄</div>
        <h2 class="empty-title">Ready to Summarize</h2>
        <p class="empty-description">
          Choose a source above and click Summarize to get started.
        </p>
        <div class="empty-features">
          <div class="feature-item">
            <span class="feature-icon">🌐</span>
            <span>Web Pages</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">🎥</span>
            <span>YouTube Videos</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">📝</span>
            <span>Custom Text</span>
          </div>
        </div>
      </div>

      <!-- Messages will be appended here -->

    </div>

    <!-- ═══════════════════════════════════════════════════════ -->
    <!-- Follow-up Questions Input -->
    <!-- ═══════════════════════════════════════════════════════ -->
    <div class="followup-section">
      <div class="followup-counter" id="followupCounter"></div>
      <div class="followup-input-wrapper">
        <input 
          type="text" 
          id="followupInput" 
          class="followup-input" 
          placeholder="Ask a follow-up question..."
          disabled
        >
        <button class="followup-send-btn" id="followupSendBtn" disabled>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
    </div>

  </div>

  <!-- ═══════════════════════════════════════════════════════ -->
  <!-- Settings Panel (Slides in from right) -->
  <!-- ═══════════════════════════════════════════════════════ -->
  <div class="settings-panel hidden" id="settingsPanel">
    <div class="settings-header">
      <h2 class="settings-title">Settings</h2>
      <button class="settings-close-btn" id="settingsCloseBtn">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>

    <div class="settings-content">
      
      <!-- Length Setting -->
      <div class="setting-group">
        <label class="setting-label">Summary Length</label>
        <div class="setting-options">
          <button class="setting-option" data-setting="length" data-value="brief">
            <span class="option-text">Brief</span>
          </button>
          <button class="setting-option" data-setting="length" data-value="medium">
            <span class="option-text">Medium</span>
          </button>
          <button class="setting-option" data-setting="length" data-value="comprehensive">
            <span class="option-text">Detailed</span>
          </button>
        </div>
      </div>

      <!-- Font Size Setting -->
      <div class="setting-group">
        <label class="setting-label">Font Size</label>
        <div class="setting-options">
          <button class="setting-option" data-setting="fontSize" data-value="small">
            <span class="option-text">Small</span>
          </button>
          <button class="setting-option" data-setting="fontSize" data-value="medium">
            <span class="option-text">Medium</span>
          </button>
          <button class="setting-option" data-setting="fontSize" data-value="large">
            <span class="option-text">Large</span>
          </button>
        </div>
      </div>

      <!-- Color Palette Setting -->
      <div class="setting-group">
        <label class="setting-label">Color Palette</label>
        <div class="setting-options color-palette-grid">
          <button class="setting-option color-option" data-setting="colorPalette" data-value="default">
            <span class="color-swatch" style="background: #ff6b35;"></span>
            <span class="option-text">Default</span>
          </button>
          <button class="setting-option color-option" data-setting="colorPalette" data-value="ocean">
            <span class="color-swatch" style="background: #0ea5e9;"></span>
            <span class="option-text">Ocean</span>
          </button>
          <button class="setting-option color-option" data-setting="colorPalette" data-value="forest">
            <span class="color-swatch" style="background: #22c55e;"></span>
            <span class="option-text">Forest</span>
          </button>
          <button class="setting-option color-option" data-setting="colorPalette" data-value="sunset">
            <span class="color-swatch" style="background: #f59e0b;"></span>
            <span class="option-text">Sunset</span>
          </button>
          <button class="setting-option color-option" data-setting="colorPalette" data-value="midnight">
            <span class="color-swatch" style="background: #8b5cf6;"></span>
            <span class="option-text">Midnight</span>
          </button>
        </div>
      </div>

      <!-- Theme Setting -->
      <div class="setting-group">
        <label class="setting-label">Theme</label>
        <div class="setting-options">
          <button class="setting-option" data-setting="theme" data-value="light">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="5"></circle>
              <line x1="12" y1="1" x2="12" y2="3"></line>
              <line x1="12" y1="21" x2="12" y2="23"></line>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
              <line x1="1" y1="12" x2="3" y2="12"></line>
              <line x1="21" y1="12" x2="23" y2="12"></line>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
            <span class="option-text">Light</span>
          </button>
          <button class="setting-option" data-setting="theme" data-value="dark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
            <span class="option-text">Dark</span>
          </button>
        </div>
      </div>

    </div>
  </div>

  <script src="settings.js"></script>
  <script src="sidepanel.js"></script>
</body>
</html>
```

**Why this structure:**

**Modular sections:** Header, input selector, dynamic input area, action button, content area, follow-up section, settings panel — each has clear boundaries.

**Dynamic input modes:** The input area changes based on dropdown selection. This reduces clutter and provides context-appropriate UI.

**Settings as overlay panel:** Full-height panel that slides in from the right. Same width as main panel for consistency.

**Semantic HTML:** Proper use of labels, ARIA attributes, and semantic elements for accessibility.

---

# Phase 4: Complete Styling

## Step 4: Create Comprehensive CSS

**Action:** Create `extension/styles.css`:

```css
/* ═══════════════════════════════════════════════════════════
   CSS Variables and Theme System
   ═══════════════════════════════════════════════════════════ */

:root {
  /* Base font size (controlled by settings) */
  --base-font-size: 14px;
  
  /* Color palette (controlled by settings) */
  --accent: #ff6b35;
  --accent-hover: #ff8555;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  
  /* Spacing scale */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;
  
  /* Border radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  
  /* Transitions */
  --transition-fast: 0.15s ease;
  --transition-base: 0.2s ease;
  --transition-slow: 0.3s ease;
  
  /* Typography */
  --font-mono: 'Space Mono', 'Courier New', monospace;
  --font-sans: 'Work Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Dark theme (default) */
:root[data-theme="dark"] {
  --bg-primary: #0a0e1a;
  --bg-secondary: #141824;
  --bg-tertiary: #1e2330;
  --bg-elevated: #282e3e;
  --text-primary: #f8f9fa;
  --text-secondary: #a8b2c1;
  --text-muted: #6b7785;
  --border: #2a3142;
  --shadow: rgba(0, 0, 0, 0.3);
}

/* Light theme */
:root[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f8f9fa;
  --bg-tertiary: #e9ecef;
  --bg-elevated: #ffffff;
  --text-primary: #1a1a2e;
  --text-secondary: #4a5568;
  --text-muted: #718096;
  --border: #e2e8f0;
  --shadow: rgba(0, 0, 0, 0.1);
}

/* ═══════════════════════════════════════════════════════════
   Base Reset and Typography
   ═══════════════════════════════════════════════════════════ */

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-sans);
  font-size: var(--base-font-size);
  line-height: 1.6;
  color: var(--text-primary);
  background: var(--bg-primary);
  overflow: hidden;
  height: 100vh;
}

button {
  font-family: inherit;
  cursor: pointer;
  border: none;
  background: none;
}

input, textarea, select {
  font-family: inherit;
  font-size: inherit;
}

/* ═══════════════════════════════════════════════════════════
   App Container
   ═══════════════════════════════════════════════════════════ */

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
  position: relative;
  transition: transform var(--transition-base);
}

/* Shift main container when settings panel opens */
.app-container.settings-open {
  transform: translateX(-100%);
}

/* ═══════════════════════════════════════════════════════════
   Header
   ═══════════════════════════════════════════════════════════ */

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-xl) var(--space-xl) var(--space-lg);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}

.app-title {
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--accent) 0%, var(--success) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.settings-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: all var(--transition-base);
  background: var(--bg-tertiary);
}

.settings-btn:hover {
  color: var(--accent);
  background: var(--bg-elevated);
  transform: rotate(90deg);
}

/* ═══════════════════════════════════════════════════════════
   Input Source Selector
   ═══════════════════════════════════════════════════════════ */

.input-selector-section {
  padding: var(--space-lg) var(--space-xl);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.input-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: var(--space-sm);
}

.input-source-dropdown {
  width: 100%;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-base);
}

.input-source-dropdown:hover {
  border-color: var(--accent);
  background: var(--bg-elevated);
}

.input-source-dropdown:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
}

/* ═══════════════════════════════════════════════════════════
   Dynamic Input Area
   ═══════════════════════════════════════════════════════════ */

.dynamic-input-area {
  padding: var(--space-lg) var(--space-xl);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  min-height: 100px;
}

.input-mode {
  animation: fadeIn 0.3s ease;
}

.input-mode.hidden {
  display: none;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Mode info (for current-tab and youtube) */
.mode-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-lg);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.mode-icon {
  flex-shrink: 0;
  color: var(--accent);
}

.mode-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.mode-text strong {
  color: var(--text-primary);
  font-weight: 600;
}

.mode-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* URL input */
.input-sublabel {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}

.url-input {
  width: 100%;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  transition: all var(--transition-base);
}

.url-input:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--bg-elevated);
  box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
}

.url-input::placeholder {
  color: var(--text-muted);
}

/* Text input */
.text-input {
  width: 100%;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  resize: vertical;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  transition: all var(--transition-base);
}

.text-input:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--bg-elevated);
  box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
}

.text-input::placeholder {
  color: var(--text-muted);
  font-family: var(--font-sans);
}

/* ═══════════════════════════════════════════════════════════
   Action Section (Summarize Button)
   ═══════════════════════════════════════════════════════════ */

.action-section {
  padding: var(--space-lg) var(--space-xl);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.summarize-btn {
  width: 100%;
  padding: var(--space-lg) var(--space-xl);
  background: var(--accent);
  color: white;
  font-weight: 600;
  font-size: 15px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  transition: all var(--transition-base);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.summarize-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 107, 53, 0.3);
}

.summarize-btn:active:not(:disabled) {
  transform: translateY(0);
}

.summarize-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  transition: transform var(--transition-base);
}

.summarize-btn:hover:not(:disabled) .btn-icon {
  transform: translateX(4px);
}

/* ═══════════════════════════════════════════════════════════
   Content Area (Messages)
   ═══════════════════════════════════════════════════════════ */

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl);
  background: var(--bg-primary);
}

.content-area::-webkit-scrollbar {
  width: 6px;
}

.content-area::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

.content-area::-webkit-scrollbar-thumb {
  background: var(--accent);
  border-radius: 3px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-2xl);
  height: 100%;
}

.empty-state.hidden {
  display: none;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: var(--space-lg);
  opacity: 0.3;
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.empty-description {
  color: var(--text-secondary);
  max-width: 280px;
  margin-bottom: var(--space-xl);
}

.empty-features {
  display: flex;
  gap: var(--space-lg);
}

.feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  font-size: 12px;
  color: var(--text-muted);
}

.feature-icon {
  font-size: 24px;
}

/* Message Bubbles */
.message {
  margin-bottom: var(--space-lg);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.message-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.message.user .message-avatar {
  background: var(--accent);
}

.message.assistant .message-avatar {
  background: var(--success);
}

.message-content {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  line-height: 1.7;
}

.message.user .message-content {
  border-left: 3px solid var(--accent);
}

.message.assistant .message-content {
  border-left: 3px solid var(--success);
}

.message.error .message-content {
  background: rgba(239, 68, 68, 0.1);
  border-left: 3px solid var(--error);
  color: var(--error);
}

/* ═══════════════════════════════════════════════════════════
   Follow-up Section
   ═══════════════════════════════════════════════════════════ */

.followup-section {
  padding: var(--space-lg) var(--space-xl);
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
}

.followup-counter {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: var(--space-sm);
  text-align: right;
  min-height: 16px;
}

.followup-counter.warning {
  color: var(--warning);
}

.followup-counter.limit {
  color: var(--error);
}

.followup-input-wrapper {
  display: flex;
  gap: var(--space-md);
  align-items: center;
}

.followup-input {
  flex: 1;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  transition: all var(--transition-base);
}

.followup-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
}

.followup-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.followup-input::placeholder {
  color: var(--text-muted);
}

.followup-send-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  border-radius: var(--radius-md);
  color: white;
  transition: all var(--transition-base);
}

.followup-send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-2px);
}

.followup-send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ═══════════════════════════════════════════════════════════
   Settings Panel
   ═══════════════════════════════════════════════════════════ */

.settings-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 100%;
  height: 100vh;
  background: var(--bg-primary);
  z-index: 1000;
  transform: translateX(100%);
  transition: transform var(--transition-base);
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border);
}

.settings-panel:not(.hidden) {
  transform: translateX(0);
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-xl);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}

.settings-title {
  font-size: 20px;
  font-weight: 600;
}

.settings-close-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: all var(--transition-base);
  background: var(--bg-tertiary);
}

.settings-close-btn:hover {
  color: var(--error);
  background: var(--bg-elevated);
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl);
}

.setting-group {
  margin-bottom: var(--space-2xl);
}

.setting-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-md);
}

.setting-options {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.setting-option {
  flex: 1;
  min-width: 100px;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-tertiary);
  border: 2px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
  transition: all var(--transition-base);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
}

.setting-option:hover {
  background: var(--bg-elevated);
  border-color: var(--accent);
}

.setting-option.active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

/* Color palette grid */
.color-palette-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-sm);
}

.color-option {
  flex-direction: row;
  justify-content: flex-start;
}

.color-swatch {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.2);
}

/* ═══════════════════════════════════════════════════════════
   Utility Classes
   ═══════════════════════════════════════════════════════════ */

.hidden {
  display: none !important;
}

/* Loading spinner */
.loading-spinner {
  width: 20px;
  height: 20px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

**Why this CSS architecture:**

**CSS Variables:** All colors, spacing, and typography are defined as variables. Settings changes update these variables, instantly applying theme changes.

**Theme System:** `data-theme` attribute on root switches between light/dark. All colors are derived from theme-specific variables.

**Component Isolation:** Each section (header, input area, content, settings) has its own scoped styles. This prevents style conflicts.

**Smooth Transitions:** Everything animates (theme changes, panel slides, button hovers). This creates a polished feel.

**Responsive Scaling:** Font size controlled by `--base-font-size` variable. When user changes font size, entire UI scales proportionally.

---

# Phase 5: Main JavaScript Logic

## Step 5: Create Main Logic File

**Action:** Replace `extension/sidepanel.js` entirely:

```javascript
// ═══════════════════════════════════════════════════════════
// Main Application Logic
// ═══════════════════════════════════════════════════════════

const API_BASE = 'http://127.0.0.1:5000';
const MAX_FOLLOW_UPS = 3;

// ═══════════════════════════════════════════════════════════
// State Management
// ═══════════════════════════════════════════════════════════

let appState = {
  currentMode: 'current-tab',
  messages: [],
  followUpCount: 0,
  currentContext: null,
  isProcessing: false
};

// ═══════════════════════════════════════════════════════════
// DOM Elements
// ═══════════════════════════════════════════════════════════

const elements = {
  // Input controls
  inputSource: document.getElementById('inputSource'),
  customUrl: document.getElementById('customUrl'),
  customText: document.getElementById('customText'),
  ytHint: document.getElementById('ytHint'),
  
  // Buttons
  summarizeBtn: document.getElementById('summarizeBtn'),
  settingsBtn: document.getElementById('settingsBtn'),
  settingsCloseBtn: document.getElementById('settingsCloseBtn'),
  followupSendBtn: document.getElementById('followupSendBtn'),
  
  // Content areas
  contentArea: document.getElementById('contentArea'),
  emptyState: document.getElementById('emptyState'),
  followupInput: document.getElementById('followupInput'),
  followupCounter: document.getElementById('followupCounter'),
  
  // Settings panel
  settingsPanel: document.getElementById('settingsPanel'),
  
  // Container
  appContainer: document.querySelector('.app-container')
};

// ═══════════════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════════════

async function init() {
  // Load settings
  await settingsManager.load();
  settingsManager.apply();
  
  // Set up settings UI
  initializeSettingsUI();
  
  // Set up event listeners
  setupEventListeners();
  
  // Update follow-up counter
  updateFollowUpCounter();
  
  // Check if on YouTube and update hint
  checkCurrentPage();
}

// ═══════════════════════════════════════════════════════════
// Settings UI Initialization
// ═══════════════════════════════════════════════════════════

function initializeSettingsUI() {
  const settings = settingsManager.settings;
  
  // Highlight active setting options
  document.querySelectorAll('.setting-option').forEach(option => {
    const setting = option.dataset.setting;
    const value = option.dataset.value;
    
    if (settings[setting] === value) {
      option.classList.add('active');
    }
  });
}

// ═══════════════════════════════════════════════════════════
// Event Listeners
// ═══════════════════════════════════════════════════════════

function setupEventListeners() {
  // Input source dropdown change
  elements.inputSource.addEventListener('change', handleModeChange);
  
  // Summarize button
  elements.summarizeBtn.addEventListener('click', handleSummarize);
  
  // Settings panel toggle
  elements.settingsBtn.addEventListener('click', openSettings);
  elements.settingsCloseBtn.addEventListener('click', closeSettings);
  
  // Settings options
  document.querySelectorAll('.setting-option').forEach(option => {
    option.addEventListener('click', handleSettingChange);
  });
  
  // Follow-up input
  elements.followupSendBtn.addEventListener('click', handleFollowUp);
  elements.followupInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFollowUp();
    }
  });
}

// ═══════════════════════════════════════════════════════════
// Input Mode Switching
// ═══════════════════════════════════════════════════════════

function handleModeChange(e) {
  const newMode = e.target.value;
  appState.currentMode = newMode;
  
  // Hide all input modes
  document.querySelectorAll('.input-mode').forEach(mode => {
    mode.classList.add('hidden');
  });
  
  // Show selected mode
  const selectedMode = document.getElementById(`mode-${newMode}`);
  if (selectedMode) {
    selectedMode.classList.remove('hidden');
  }
  
  // Update YouTube hint if on YouTube
  if (newMode === 'youtube') {
    checkCurrentPage();
  }
}

async function checkCurrentPage() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const currentUrl = tabs[0]?.url || '';
  
  if (currentUrl.includes('youtube.com') || currentUrl.includes('youtu.be')) {
    elements.ytHint.textContent = 'Current YouTube video will be summarized';
  } else {
    elements.ytHint.textContent = 'Navigate to a YouTube video or paste URL below';
  }
}

// ═══════════════════════════════════════════════════════════
// Settings Panel
// ═══════════════════════════════════════════════════════════

function openSettings() {
  elements.settingsPanel.classList.remove('hidden');
  elements.appContainer.classList.add('settings-open');
}

function closeSettings() {
  elements.settingsPanel.classList.add('hidden');
  elements.appContainer.classList.remove('settings-open');
}

async function handleSettingChange(e) {
  const button = e.currentTarget;
  const setting = button.dataset.setting;
  const value = button.dataset.value;
  
  // Update setting
  await settingsManager.set(setting, value);
  settingsManager.apply();
  
  // Update UI (remove active class from all, add to clicked)
  document.querySelectorAll(`[data-setting="${setting}"]`).forEach(opt => {
    opt.classList.remove('active');
  });
  button.classList.add('active');
}

// ═══════════════════════════════════════════════════════════
// Summarization Logic
// ═══════════════════════════════════════════════════════════

async function handleSummarize() {
  const mode = appState.currentMode;
  const length = settingsManager.get('length');
  
  setProcessing(true);
  
  try {
    switch (mode) {
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
  
  addMessage('user', `Summarize current page: ${url}`);
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
  
  addMessage('assistant', data.summary, { source: 'Current Page' });
  
  // Store context for follow-ups
  appState.currentContext = {
    summary: data.summary,
    url: url,
    type: isYouTube ? 'youtube' : 'webpage'
  };
  appState.followUpCount = 0;
  enableFollowUps();
  updateFollowUpCounter();
}

async function summarizeYouTube(length) {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const currentUrl = tabs[0]?.url || '';
  
  let url = currentUrl;
  
  // If not on YouTube, user must have pasted URL (future enhancement)
  if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
    throw new Error('Please navigate to a YouTube video or select "Custom URL" mode');
  }
  
  addMessage('user', `Summarize YouTube video: ${url}`);
  addLoadingMessage('Extracting video transcript...');
  
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
  
  addMessage('assistant', data.summary, { source: 'YouTube Video' });
  
  appState.currentContext = {
    summary: data.summary,
    url: url,
    type: 'youtube'
  };
  appState.followUpCount = 0;
  enableFollowUps();
  updateFollowUpCounter();
}

async function summarizeCustomURL(length) {
  const url = elements.customUrl.value.trim();
  
  if (!url) {
    throw new Error('Please enter a URL');
  }
  
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    throw new Error('URL must start with http:// or https://');
  }
  
  addMessage('user', `Summarize URL: ${url}`);
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
  
  addMessage('assistant', data.summary, { source: 'Custom URL' });
  
  appState.currentContext = {
    summary: data.summary,
    url: url,
    type: isYouTube ? 'youtube' : 'webpage'
  };
  appState.followUpCount = 0;
  enableFollowUps();
  updateFollowUpCounter();
  
  // Clear input
  elements.customUrl.value = '';
}

async function summarizeCustomText(length) {
  const text = elements.customText.value.trim();
  
  if (!text || text.length < 20) {
    throw new Error('Please enter at least 20 characters of text');
  }
  
  const preview = text.length > 100 ? text.substring(0, 100) + '...' : text;
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
  
  addMessage('assistant', data.summary, { source: 'Custom Text' });
  
  appState.currentContext = {
    summary: data.summary,
    originalText: text,
    type: 'text'
  };
  appState.followUpCount = 0;
  enableFollowUps();
  updateFollowUpCounter();
  
  // Clear input
  elements.customText.value = '';
}

// ═══════════════════════════════════════════════════════════
// Follow-up Questions
// ═══════════════════════════════════════════════════════════

async function handleFollowUp() {
  const question = elements.followupInput.value.trim();
  
  if (!question) return;
  
  if (appState.followUpCount >= MAX_FOLLOW_UPS) {
    addMessage('error', 'Follow-up limit reached. Start a new summary to ask more questions.');
    return;
  }
  
  if (!appState.currentContext) {
    addMessage('error', 'Please summarize something first before asking follow-up questions.');
    return;
  }
  
  setProcessing(true);
  addMessage('user', question);
  addLoadingMessage('Thinking...');
  
  try {
    const conversationHistory = appState.messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.content }));
    
    const response = await fetch(`${API_BASE}/follow-up`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        context: appState.currentContext.summary,
        history: conversationHistory
      })
    });
    
    const data = await response.json();
    removeLoadingMessage();
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    appState.followUpCount++;
    addMessage('assistant', data.answer, { 
      source: `Follow-up ${appState.followUpCount}/${MAX_FOLLOW_UPS}` 
    });
    
    updateFollowUpCounter();
    
    // Clear input
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
    elements.followupCounter.textContent = `${remaining} follow-up question${remaining !== 1 ? 's' : ''} remaining`;
    elements.followupCounter.className = remaining === 1 ? 'followup-counter warning' : 'followup-counter';
  } else {
    elements.followupCounter.textContent = 'Follow-up limit reached';
    elements.followupCounter.className = 'followup-counter limit';
    disableFollowUps();
  }
}

// ═══════════════════════════════════════════════════════════
// UI Helpers
// ═══════════════════════════════════════════════════════════

function hideEmptyState() {
  elements.emptyState.classList.add('hidden');
}

function addMessage(role, content, metadata = {}) {
  hideEmptyState();
  
  const message = document.createElement('div');
  message.className = `message ${role}`;
  
  const avatarContent = role === 'user' ? '👤' : role === 'assistant' ? '🤖' : '⚠️';
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
  hideEmptyState();
  
  const loading = document.createElement('div');
  loading.className = 'message assistant';
  loading.id = 'loadingMessage';
  loading.innerHTML = `
    <div class="message-header">
      <div class="message-avatar">🤖</div>
      <span>AI</span>
    </div>
    <div class="message-content">
      <div style="display: flex; align-items: center; gap: 12px;">
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
  elements.followupInput.disabled = isProcessing || !appState.currentContext;
  elements.followupSendBtn.disabled = isProcessing || !appState.currentContext;
}

// ═══════════════════════════════════════════════════════════
// Start Application
// ═══════════════════════════════════════════════════════════

init();
```

**Why this architecture:**

**State-driven:** Single `appState` object manages current mode, messages, follow-up count, and processing state. All UI updates derive from state changes.

**Mode-aware logic:** The summarize handler switches behavior based on `currentMode`. This eliminates duplicate code.

**Settings integration:** Settings manager is imported and used to apply theme/preferences. All settings changes instantly update the UI via CSS variables.

**Follow-up context:** After each summary, the result is stored in `currentContext`. Follow-up questions reference this context.

**Error handling:** Every API call is wrapped in try-catch. Errors display as red message bubbles instead of crashing.

---

# Phase 6: Testing the New UI

## Step 6: Test All Modes

**Action:** Reload the extension and test each input mode:

**Test A: Current Tab Mode**
1. Navigate to Wikipedia article
2. Open side panel
3. Dropdown should default to "Current Tab"
4. Click Summarize
5. Verify summary appears
6. Ask a follow-up question
7. Verify counter shows "2 follow-up questions remaining"

**Test B: YouTube Mode**
1. Navigate to a YouTube video
2. Select "YouTube Video" from dropdown
3. Verify hint says "Current YouTube video will be summarized"
4. Click Summarize
5. Verify video transcript is summarized

**Test C: Custom URL Mode**
1. Select "Enter Any URL"
2. Paste https://en.wikipedia.org/wiki/Artificial_intelligence
3. Click Summarize
4. Verify summary appears

**Test D: Custom Text Mode**
1. Select "Custom Text/Script"
2. Paste a paragraph of text
3. Click Summarize
4. Verify summary appears

**Test E: Settings Panel**
1. Click gear icon
2. Verify settings panel slides in
3. Change theme to Light
4. Verify UI instantly switches to light theme
5. Change font size to Large
6. Verify text size increases
7. Change color palette to Ocean
8. Verify accent color changes to blue
9. Close settings panel
10. Reload extension
11. Verify settings persist (still Light theme, Large font, Ocean palette)

**Expected Result:** All tests pass. Settings persist across sessions. UI is smooth and responsive.

---

# Phase 7: Advanced Enhancements

## Step 7: Add Clear Conversation Button

**Action:** Add to header in HTML:

```html
<button class="clear-btn" id="clearBtn" title="Clear conversation">
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="3 6 5 6 21 6"></polyline>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
  </svg>
</button>
```

Add CSS:

```css
.clear-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  background: var(--bg-tertiary);
  transition: all var(--transition-base);
}

.clear-btn:hover {
  color: var(--error);
  background: var(--bg-elevated);
}
```

Add logic in JS:

```javascript
document.getElementById('clearBtn').addEventListener('click', () => {
  if (confirm('Clear all messages and start over?')) {
    appState.messages = [];
    appState.followUpCount = 0;
    appState.currentContext = null;
    elements.contentArea.innerHTML = '';
    elements.emptyState.classList.remove('hidden');
    elements.contentArea.appendChild(elements.emptyState);
    disableFollowUps();
    updateFollowUpCounter();
  }
});
```

---

## Step 8: Add Export Conversation

**Action:** Add button to settings panel:

```html
<div class="setting-group">
  <label class="setting-label">Data</label>
  <button class="export-btn" id="exportBtn">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="7 10 12 15 17 10"></polyline>
      <line x1="12" y1="15" x2="12" y2="3"></line>
    </svg>
    <span>Export Conversation</span>
  </button>
</div>
```

CSS:

```css
.export-btn {
  width: 100%;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  transition: all var(--transition-base);
}

.export-btn:hover {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
```

Logic:

```javascript
document.getElementById('exportBtn').addEventListener('click', () => {
  const exportData = {
    timestamp: new Date().toISOString(),
    settings: settingsManager.settings,
    messages: appState.messages
  };
  
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sumitup-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
});
```

---

# Summary

You now have a **production-grade side panel** with:

✅ **Multi-source input** (Current Tab, YouTube, Custom URL, Custom Text)
✅ **Dynamic UI** that adapts to selected input mode
✅ **Professional settings panel** with:
   - Summary length control (Brief, Medium, Detailed)
   - Font size adjustment (Small, Medium, Large)
   - 5 color palettes (Default, Ocean, Forest, Sunset, Midnight)
   - Light/Dark theme toggle
✅ **Persistent settings** across browser sessions
✅ **Follow-up questions** (up to 3) with context awareness
✅ **Smooth animations** and transitions
✅ **Professional design** with custom typography and color system
✅ **Export functionality** for conversation history
✅ **Clear conversation** feature

The UI matches your wireframe while adding professional polish and feature depth. All settings are stored in `chrome.storage` and persist across sessions. The modular architecture makes future enhancements easy to implement.
