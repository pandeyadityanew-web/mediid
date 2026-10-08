# SahayID Progressive Web App (PWA) Guide

SahayID is built as a Progressive Web App (PWA), enabling native-like installation on Android, iOS, Windows, macOS, and Linux without app store downloads.

---

## 1. Native Installation Flow

SahayID utilizes modern Web Standards to trigger the browser's native installation prompt rather than relying on custom modal dialogs or manual instructions.

### Mechanics:
1. **Early Event Interception:** In [`static/js/script.js`](file:///C:/Users/pande/.gemini/antigravity/scratch/mediid/static/js/script.js), the `beforeinstallprompt` event is captured immediately during window initialization and preserved in a global `deferredInstallPrompt` reference.
2. **Actionable UI Element:** The "Install App" button (`.pwa-install-btn`) remains permanently visible in the top navigation bar and mobile menu whenever the application is not running in standalone mode (`window.matchMedia('(display-mode: standalone)').matches`).
3. **Trigger Execution:** When clicked:
   ```javascript
   if (deferredInstallPrompt) {
       deferredInstallPrompt.prompt();
       const choice = await deferredInstallPrompt.userChoice;
       if (choice.outcome === 'accepted') {
           hideInstallButtons();
       }
       deferredInstallPrompt = null;
   }
   ```

---

## 2. Web App Manifest Specification

The manifest configuration at [`static/manifest.json`](file:///C:/Users/pande/.gemini/antigravity/scratch/mediid/static/manifest.json) includes:
- **`display: "standalone"`:** Removes browser chrome and address bars for native app immersion.
- **`theme_color: "#0284c7"`:** Coordinates the OS status bar and window header with SahayID's clinical cyan palette.
- **`background_color: "#0c2340"`:** Ensures a polished dark navy splash screen during cold launches.
- **`icons`:** Multi-resolution high-DPI assets (`192x192`, `512x512` maskable PNGs, and `180x180` Apple touch icons).

---

## 3. Service Worker & Caching Strategy

The service worker at [`static/sw.js`](file:///C:/Users/pande/.gemini/antigravity/scratch/mediid/static/sw.js) employs a **Stale-While-Revalidate** / **Cache-First** strategy for core static design assets (CSS, logos, icons, fonts) while bypassing caching for dynamic clinical endpoints (`/dashboard`, `/emergency/*`, `/doctor/*`, `/admin/*`) to guarantee absolute data freshness and prevent HIPAA/GDPR clinical cache poisoning.
