/**
 * SahayID - Client-side Healthcare & Security Interactivity
 * Critical Medical Access Platform
 */

// Early PWA beforeinstallprompt capture & Service Worker registration
let deferredPrompt = window.deferredPrompt || null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    window.deferredPrompt = e;
    console.log('[SahayID PWA] beforeinstallprompt event captured.');
});

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch((err) => {
            console.warn('[SahayID PWA] Service Worker registration skipped:', err);
        });
    });
}

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

    // 4. FAQ Accordion Toggle Interaction
    const faqButtons = document.querySelectorAll('.faq-question-btn');
    faqButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const answerPane = btn.nextElementSibling;
            const isOpen = btn.classList.contains('active');

            // Close other open FAQ items in the same list
            faqButtons.forEach(otherBtn => {
                if (otherBtn !== btn) {
                    otherBtn.classList.remove('active');
                    otherBtn.setAttribute('aria-expanded', 'false');
                    if (otherBtn.nextElementSibling) {
                        otherBtn.nextElementSibling.classList.remove('open');
                    }
                }
            });

            if (isOpen) {
                btn.classList.remove('active');
                btn.setAttribute('aria-expanded', 'false');
                if (answerPane) answerPane.classList.remove('open');
            } else {
                btn.classList.add('active');
                btn.setAttribute('aria-expanded', 'true');
                if (answerPane) answerPane.classList.add('open');
            }
        });
    });

    // 5. How SahayID Works - Animated Process Path & Progress Fill
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

    // 6. Doctor Access Request Live Status Polling
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

    // 7. OTP Form Auto-Focus & Clean Input
    const otpInput = document.getElementById('otpCodeInput');
    if (otpInput) {
        otpInput.focus();
        otpInput.addEventListener('input', (e) => {
            // Keep strictly numeric
            e.target.value = e.target.value.replace(/[^0-9]/g, '').slice(0, 6);
        });
    }

    // 8. Profile Photo Camera Snapshot Handler (Patient & Doctor)
    const patientCameraBtn = document.getElementById('patientCameraBtn');
    const doctorCameraBtn = document.getElementById('doctorCameraBtn');
    const cameraModal = document.getElementById('cameraModal');
    const cameraVideo = document.getElementById('cameraVideo');
    const cameraCanvas = document.getElementById('cameraCanvas');
    const snapPhotoBtn = document.getElementById('snapPhotoBtn');
    const closeCameraModal = document.getElementById('closeCameraModal');
    const cancelCameraBtn = document.getElementById('cancelCameraBtn');
    const cameraSnapshotForm = document.getElementById('cameraSnapshotForm');
    const cameraSnapshotBase64 = document.getElementById('cameraSnapshotBase64');
    const cameraStatusMsg = document.getElementById('cameraStatusMsg');

    let cameraStream = null;

    const startCamera = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Camera access is not supported by your browser.');
            return;
        }

        try {
            if (cameraStatusMsg) cameraStatusMsg.textContent = 'Requesting camera access...';
            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                audio: false
            });
            if (cameraVideo) {
                cameraVideo.srcObject = cameraStream;
                cameraVideo.play();
            }
            if (cameraModal) cameraModal.style.display = 'flex';
            if (cameraStatusMsg) cameraStatusMsg.textContent = 'Position your face within the frame and click Capture.';
        } catch (err) {
            console.error('Camera access error:', err);
            alert('Unable to access camera. Please ensure camera permissions are granted.');
        }
    };

    const stopCamera = () => {
        if (cameraStream) {
            cameraStream.getTracks().forEach(t => t.stop());
            cameraStream = null;
        }
        if (cameraVideo) cameraVideo.srcObject = null;
        if (cameraModal) cameraModal.style.display = 'none';
    };

    if (patientCameraBtn) patientCameraBtn.addEventListener('click', startCamera);
    if (doctorCameraBtn) doctorCameraBtn.addEventListener('click', startCamera);
    if (closeCameraModal) closeCameraModal.addEventListener('click', stopCamera);
    if (cancelCameraBtn) cancelCameraBtn.addEventListener('click', stopCamera);

    if (snapPhotoBtn && cameraVideo && cameraCanvas && cameraSnapshotForm && cameraSnapshotBase64) {
        snapPhotoBtn.addEventListener('click', () => {
            const width = cameraVideo.videoWidth || 640;
            const height = cameraVideo.videoHeight || 480;
            cameraCanvas.width = width;
            cameraCanvas.height = height;
            const ctx = cameraCanvas.getContext('2d');
            // Mirror image horizontally for intuitive selfie capture
            ctx.translate(width, 0);
            ctx.scale(-1, 1);
            ctx.drawImage(cameraVideo, 0, 0, width, height);

            const dataUri = cameraCanvas.toDataURL('image/jpeg', 0.85);
            cameraSnapshotBase64.value = dataUri;
            stopCamera();
            cameraSnapshotForm.submit();
        });
    }

    // 9. Doctor Camera QR Scanner Handler
    const startQrScanBtn = document.getElementById('startQrScanBtn');
    const qrScannerModal = document.getElementById('qrScannerModal');
    const qrScannerVideo = document.getElementById('qrScannerVideo');
    const qrScannerCanvas = document.getElementById('qrScannerCanvas');
    const qrScannerStatus = document.getElementById('qrScannerStatus');
    const closeQrScannerBtn = document.getElementById('closeQrScannerBtn');
    const cancelQrScannerBtn = document.getElementById('cancelQrScannerBtn');
    const flipCameraBtn = document.getElementById('flipCameraBtn');
    const doctorSahayIdInput = document.getElementById('doctorSahayIdInput');
    const doctorSearchForm = document.getElementById('doctorSearchForm');

    let qrStream = null;
    let qrScanAnimationId = null;
    let currentFacingMode = 'environment';

    const stopQrScanner = () => {
        if (qrScanAnimationId) {
            cancelAnimationFrame(qrScanAnimationId);
            qrScanAnimationId = null;
        }
        if (qrStream) {
            qrStream.getTracks().forEach(t => t.stop());
            qrStream = null;
        }
        if (qrScannerVideo) qrScannerVideo.srcObject = null;
        if (qrScannerModal) qrScannerModal.style.display = 'none';
    };

    const extractMediId = (text) => {
        if (!text) return null;
        // Check for direct SahayID format
        const directMatch = text.match(/MED-[A-Z0-9]{4,16}/i);
        if (directMatch) return directMatch[0].toUpperCase();

        // Check for URL containing /emergency/MED-XXXXXXXX
        if (text.includes('/emergency/')) {
            const parts = text.split('/emergency/');
            const candidate = parts[1].split(/[?#/]/)[0].trim().toUpperCase();
            if (candidate.startsWith('MED-')) return candidate;
        }
        return null;
    };

    const scanQrFrame = async () => {
        if (!qrScannerVideo || qrScannerVideo.readyState !== qrScannerVideo.HAVE_ENOUGH_DATA) {
            qrScanAnimationId = requestAnimationFrame(scanQrFrame);
            return;
        }

        const width = qrScannerVideo.videoWidth;
        const height = qrScannerVideo.videoHeight;
        if (qrScannerCanvas) {
            qrScannerCanvas.width = width;
            qrScannerCanvas.height = height;
            const ctx = qrScannerCanvas.getContext('2d');
            ctx.drawImage(qrScannerVideo, 0, 0, width, height);

            // 1. Try native BarcodeDetector if available in browser
            if ('BarcodeDetector' in window) {
                try {
                    const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
                    const barcodes = await detector.detect(qrScannerCanvas);
                    if (barcodes && barcodes.length > 0) {
                        const rawValue = barcodes[0].rawValue;
                        const mediId = extractMediId(rawValue);
                        if (mediId) {
                            handleQrScanned(mediId);
                            return;
                        }
                    }
                } catch (e) {
                    // Fall through
                }
            }
        }

        qrScanAnimationId = requestAnimationFrame(scanQrFrame);
    };

    const handleQrScanned = (mediId) => {
        stopQrScanner();
        if (doctorSahayIdInput) {
            doctorSahayIdInput.value = mediId;
        }
        if (doctorSearchForm) {
            doctorSearchForm.submit();
        } else {
            window.location.href = `/doctor/patient/search?sahay_id=${encodeURIComponent(mediId)}`;
        }
    };

    const startQrScanner = async (facingMode = 'environment') => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Camera scanner is not supported on this browser. Please enter the SahayID manually.');
            return;
        }

        try {
            if (qrScannerStatus) qrScannerStatus.textContent = 'Starting camera viewfinder...';
            currentFacingMode = facingMode;
            qrStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: facingMode }, width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false
            });

            if (qrScannerVideo) {
                qrScannerVideo.srcObject = qrStream;
                await qrScannerVideo.play();
            }
            if (qrScannerModal) qrScannerModal.style.display = 'flex';
            if (qrScannerStatus) qrScannerStatus.textContent = 'Align patient QR badge within the square viewport.';
            qrScanAnimationId = requestAnimationFrame(scanQrFrame);
        } catch (err) {
            console.error('QR camera error:', err);
            // Fallback to default camera if environment camera fails
            if (facingMode === 'environment') {
                startQrScanner('user');
            } else {
                alert('Unable to access camera for scanning. Please check camera permissions.');
            }
        }
    };

    if (startQrScanBtn) {
        startQrScanBtn.addEventListener('click', () => startQrScanner('environment'));
    }
    if (closeQrScannerBtn) closeQrScannerBtn.addEventListener('click', stopQrScanner);
    if (cancelQrScannerBtn) cancelQrScannerBtn.addEventListener('click', stopQrScanner);

    if (flipCameraBtn) {
        flipCameraBtn.addEventListener('click', () => {
            if (qrStream) {
                qrStream.getTracks().forEach(t => t.stop());
            }
            const nextMode = currentFacingMode === 'environment' ? 'user' : 'environment';
            startQrScanner(nextMode);
        });
    }

    // 10. Dark / Light Mode Theme System
    const applyTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        const toggleBtns = document.querySelectorAll('.theme-toggle-btn');
        toggleBtns.forEach(btn => {
            const icon = btn.querySelector('.theme-toggle-icon');
            const text = btn.querySelector('.theme-toggle-text');
            if (icon) {
                icon.textContent = theme === 'dark' ? '☀️' : '🌙';
            }
            if (text) {
                text.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
            }
            btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
            btn.setAttribute('title', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
        });
    };

    const currentTheme = localStorage.getItem('sahayid-theme') || 'light';
    applyTheme(currentTheme);

    const themeToggleBtns = document.querySelectorAll('.theme-toggle-btn');
    themeToggleBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const activeTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const nextTheme = activeTheme === 'dark' ? 'light' : 'dark';
            applyTheme(nextTheme);
            localStorage.setItem('sahayid-theme', nextTheme);
        });
    });

    // 11. Role Selection Flow Modal ("Get Started")
    const roleModal = document.getElementById('roleSelectModal');
    const closeRoleModalBtn = document.getElementById('closeRoleModalBtn');
    const roleTriggers = document.querySelectorAll('.get-started-trigger');

    const openRoleModal = (e) => {
        if (e) e.preventDefault();
        if (roleModal) {
            roleModal.style.display = 'flex';
            // Force reflow for smooth animation
            void roleModal.offsetWidth;
            roleModal.classList.add('active');
            roleModal.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
        }
    };

    const closeRoleModal = () => {
        if (roleModal) {
            roleModal.classList.remove('active');
            roleModal.setAttribute('aria-hidden', 'true');
            setTimeout(() => {
                if (!roleModal.classList.contains('active')) {
                    roleModal.style.display = 'none';
                    document.body.style.overflow = '';
                }
            }, 250);
        }
    };

    roleTriggers.forEach(trigger => {
        trigger.addEventListener('click', openRoleModal);
    });

    if (closeRoleModalBtn) {
        closeRoleModalBtn.addEventListener('click', closeRoleModal);
    }

    if (roleModal) {
        roleModal.addEventListener('click', (e) => {
            if (e.target === roleModal) {
                closeRoleModal();
            }
        });

        const roleModalBreakGlass = document.getElementById('roleModalBreakGlassLink');
        if (roleModalBreakGlass) {
            roleModalBreakGlass.addEventListener('click', () => {
                closeRoleModal();
            });
        }
    }

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && roleModal && roleModal.classList.contains('active')) {
            closeRoleModal();
        }
    });

    // 12. Native PWA & Install App Handling
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                         window.navigator.standalone === true ||
                         document.referrer.includes('android-app://');
    const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const installBtns = document.querySelectorAll('.pwa-install-btn');

    // Create & reveal iOS install guidance sheet
    function openIosInstallSheet() {
        let sheet = document.getElementById('iosInstallSheet');
        if (!sheet) {
            sheet = document.createElement('div');
            sheet.id = 'iosInstallSheet';
            sheet.className = 'ios-install-backdrop';
            sheet.innerHTML = `
                <div class="ios-install-card">
                    <div class="ios-install-header">
                        <div class="ios-install-title">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            Install SahayID
                        </div>
                        <button type="button" class="ios-install-close" aria-label="Close modal">&times;</button>
                    </div>
                    <p class="ios-install-desc">Install SahayID on your device for instant emergency access and clinical records:</p>
                    <div class="ios-install-steps">
                        <div class="ios-step-item">
                            <span class="ios-step-badge">1</span>
                            <span>Tap the <strong>Share</strong> button <svg style="display:inline; vertical-align:middle;" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg> in Safari toolbar.</span>
                        </div>
                        <div class="ios-step-item">
                            <span class="ios-step-badge">2</span>
                            <span>Scroll down and select <strong>Add to Home Screen</strong>.</span>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(sheet);
            const closeBtn = sheet.querySelector('.ios-install-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    sheet.classList.remove('active');
                });
            }
            sheet.addEventListener('click', (e) => {
                if (e.target === sheet) {
                    sheet.classList.remove('active');
                }
            });
        }
        sheet.classList.add('active');
    }

    if (isStandalone) {
        installBtns.forEach(b => b.style.display = 'none');
    } else {
        // Keep Install App button visible in navigation
        installBtns.forEach(b => {
            b.style.display = 'inline-flex';
            b.addEventListener('click', async (e) => {
                e.preventDefault();
                const activePrompt = window.deferredPrompt || deferredPrompt;
                if (activePrompt) {
                    // Trigger native browser installation prompt dialog
                    activePrompt.prompt();
                    try {
                        const choiceResult = await activePrompt.userChoice;
                        if (choiceResult && choiceResult.outcome === 'accepted') {
                            installBtns.forEach(btn => btn.style.display = 'none');
                        }
                    } catch (err) {
                        console.warn('[SahayID PWA] Prompt outcome error:', err);
                    }
                    window.deferredPrompt = null;
                    deferredPrompt = null;
                } else if (isIos) {
                    openIosInstallSheet();
                } else {
                    console.log('[SahayID PWA] Native prompt requested; awaiting browser installation readiness.');
                }
            });
        });
    }

    window.addEventListener('appinstalled', () => {
        window.deferredPrompt = null;
        deferredPrompt = null;
        installBtns.forEach(b => b.style.display = 'none');
        console.log('[SahayID PWA] SahayID was successfully installed.');
    });

    console.log('SahayID Healthcare Security Engine Initialized.');
});
