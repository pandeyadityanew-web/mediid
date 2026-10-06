/**
 * SahayID - Client-side Healthcare & Security Interactivity
 * Critical Medical Access Platform
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Top Navigation Menu Toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            const isExpanded = navMenu.classList.toggle('active');
            navToggle.setAttribute('aria-expanded', isExpanded);
        });
    }

    // 2. Dashboard Sidebar Toggle (Mobile)
    const sidebarToggle = document.getElementById('sidebarToggle');
    const dashboardSidebar = document.getElementById('dashboardSidebar');

    if (sidebarToggle && dashboardSidebar) {
        sidebarToggle.addEventListener('click', () => {
            dashboardSidebar.classList.toggle('active');
        });
    }

    // 3. Auto-fade Alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        // Keep active OTP alerts persistent, fade generic notices after 7s
        if (!alert.classList.contains('alert-persistent')) {
            setTimeout(() => {
                alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-6px)';
                setTimeout(() => alert.remove(), 400);
            }, 7000);
        }
    });

    // 4. How SahayID Works - Animated Process Path & Progress Fill
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

            // Ensure first step is active if container is at or above viewport
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

    // 5. Doctor Access Request Live Status Polling
    const pendingPollElement = document.getElementById('pendingRequestTracker');
    if (pendingPollElement) {
        const pollUrl = pendingPollElement.dataset.pollUrl || window.location.href;
        let pollCount = 0;
        const maxPolls = 100; // 5 minutes polling at 3s intervals

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
                
                // If status changed from PENDING (e.g. APPROVED or DENIED or VERIFIED), reload full page
                if (!newTracker || newTracker.dataset.status !== 'PENDING') {
                    clearInterval(pollInterval);
                    window.location.reload();
                }
            })
            .catch(() => {
                // Silently ignore transient network errors during poll
            });
        }, 3000);
    }

    // 6. OTP Form Auto-Focus & Clean Input
    const otpInput = document.getElementById('otpCodeInput');
    if (otpInput) {
        otpInput.focus();
        otpInput.addEventListener('input', (e) => {
            // Keep strictly numeric
            e.target.value = e.target.value.replace(/[^0-9]/g, '').slice(0, 6);
        });
    }

    // 7. PWA Service Worker Registration & Subtle Install Prompt
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/static/sw.js').catch(() => {});
        });
    }

    let deferredPrompt = null;
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

    window.addEventListener('beforeinstallprompt', (e) => {
        if (isStandalone) return;
        e.preventDefault();
        deferredPrompt = e;
        const installBtns = document.querySelectorAll('.pwa-install-btn');
        installBtns.forEach(btn => {
            btn.style.display = 'inline-flex';
            btn.addEventListener('click', async () => {
                if (deferredPrompt) {
                    deferredPrompt.prompt();
                    const choice = await deferredPrompt.userChoice;
                    if (choice && choice.outcome === 'accepted') {
                        installBtns.forEach(b => b.style.display = 'none');
                    }
                    deferredPrompt = null;
                }
            });
        });
    });

    window.addEventListener('appinstalled', () => {
        deferredPrompt = null;
        const installBtns = document.querySelectorAll('.pwa-install-btn');
        installBtns.forEach(b => b.style.display = 'none');
    });

    console.log('SahayID Healthcare Security Engine Initialized.');
});
