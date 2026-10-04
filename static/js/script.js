/**
 * SahayID - Client-side Healthcare & Security Interactivity
 * Critical Medical Access Platform
 * Features: Dark Mode, PWA Install, Dynamic Workflow Timeline, Status Polling, OTP formatting
 */

// 1. Theme Manager (Dark / Light Mode)
function initTheme() {
    const savedTheme = localStorage.getItem('sahayid_theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const activeTheme = savedTheme || (prefersDark ? 'dark' : 'light');
    
    document.documentElement.setAttribute('data-theme', activeTheme);
    updateThemeToggleUI(activeTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('sahayid_theme', nextTheme);
    updateThemeToggleUI(nextTheme);
}

function updateThemeToggleUI(theme) {
    const toggles = document.querySelectorAll('.theme-toggle-btn');
    toggles.forEach(btn => {
        if (theme === 'dark') {
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
                <span class="theme-text">Light</span>
            `;
            btn.setAttribute('aria-label', 'Switch to Light Mode');
            btn.title = 'Switch to Light Mode';
        } else {
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
                <span class="theme-text">Dark</span>
            `;
            btn.setAttribute('aria-label', 'Switch to Dark Mode');
            btn.title = 'Switch to Dark Mode';
        }
    });
}

// 2. PWA Installation Handler
let deferredInstallPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    const installBtns = document.querySelectorAll('.install-app-btn');
    installBtns.forEach(btn => {
        btn.style.display = 'inline-flex';
    });
});

function handleInstallClick() {
    if (deferredInstallPrompt) {
        deferredInstallPrompt.prompt();
        deferredInstallPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                console.log('User accepted the SahayID install prompt');
            }
            deferredInstallPrompt = null;
            const installBtns = document.querySelectorAll('.install-app-btn');
            installBtns.forEach(btn => btn.style.display = 'none');
        });
    } else {
        // Fallback instructions for iOS or desktop browsers where prompt isn't directly invokable
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        if (isIOS) {
            alert("To install SahayID on your iPhone/iPad:\n1. Tap the Share button at the bottom of Safari.\n2. Select 'Add to Home Screen'.");
        } else {
            alert("To install SahayID:\nTap your browser menu (⋮ or ...) and select 'Install SahayID' or 'Add to Home screen'.");
        }
    }
}

// Initialize theme immediately to prevent flashing
initTheme();

document.addEventListener('DOMContentLoaded', () => {
    // Register Service Worker
    if ('serviceWorker' in navigator && (window.location.protocol === 'https:' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
        navigator.serviceWorker.register('/static/sw.js').catch(() => {});
    }

    // Attach Theme Toggle Listeners
    const themeToggles = document.querySelectorAll('.theme-toggle-btn');
    themeToggles.forEach(btn => {
        btn.addEventListener('click', toggleTheme);
    });

    // Attach Install App Button Listeners
    const installBtns = document.querySelectorAll('.install-app-btn');
    installBtns.forEach(btn => {
        btn.addEventListener('click', handleInstallClick);
    });

    // Mobile Top Navigation Menu Toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            const isExpanded = navMenu.classList.toggle('active');
            navToggle.setAttribute('aria-expanded', isExpanded);
        });
    }

    // Dashboard Sidebar Toggle (Mobile)
    const sidebarToggle = document.getElementById('sidebarToggle');
    const dashboardSidebar = document.getElementById('dashboardSidebar');

    if (sidebarToggle && dashboardSidebar) {
        sidebarToggle.addEventListener('click', () => {
            dashboardSidebar.classList.toggle('active');
        });
    }

    // Auto-fade Alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        if (!alert.classList.contains('alert-persistent')) {
            setTimeout(() => {
                alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-6px)';
                setTimeout(() => alert.remove(), 400);
            }, 7000);
        }
    });

    // How SahayID Works - Animated Process Path & Progress Fill
    const processContainer = document.querySelector('.process-flow-container');
    const processSteps = document.querySelectorAll('.process-step-node');
    const processTrackFill = document.getElementById('processTrackFill');

    if (processContainer && processSteps.length > 0) {
        const updateTimeline = () => {
            const viewportMiddle = window.innerHeight * 0.65;
            let activeCount = 0;

            processSteps.forEach((step, idx) => {
                const rect = step.getBoundingClientRect();
                if (rect.top <= viewportMiddle) {
                    step.classList.add('step-active');
                    activeCount = idx + 1;
                } else if (idx > 0) {
                    step.classList.remove('step-active');
                }
            });

            const containerRect = processContainer.getBoundingClientRect();
            if (containerRect.top <= viewportMiddle && activeCount === 0) {
                processSteps[0].classList.add('step-active');
                activeCount = 1;
            }

            if (processTrackFill && activeCount > 0) {
                const fillPct = ((activeCount - 1) / Math.max(1, processSteps.length - 1)) * 100;
                processTrackFill.style.height = `${fillPct}%`;
            }
        };

        window.addEventListener('scroll', updateTimeline, { passive: true });
        window.addEventListener('resize', updateTimeline, { passive: true });
        updateTimeline();
    }

    // Doctor Access Request Live Status Polling
    const pendingPollElement = document.getElementById('pendingRequestTracker');
    if (pendingPollElement) {
        const pollUrl = pendingPollElement.dataset.pollUrl || window.location.href;
        let pollCount = 0;
        const maxPolls = 100;

        const pollInterval = setInterval(() => {
            pollCount++;
            if (pollCount > maxPolls) {
                clearInterval(pollInterval);
                return;
            }

            fetch(pollUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(res => res.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newTracker = doc.getElementById('pendingRequestTracker');
                
                if (!newTracker || newTracker.dataset.status !== 'PENDING') {
                    clearInterval(pollInterval);
                    window.location.reload();
                }
            })
            .catch(() => {});
        }, 3000);
    }

    // OTP Form Auto-Focus & Clean Input
    const otpInput = document.getElementById('otpCodeInput');
    if (otpInput) {
        otpInput.focus();
        otpInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '').slice(0, 6);
        });
    }

    console.log('SahayID Healthcare Engine with PWA & Dark Mode Ready.');
});
