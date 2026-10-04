/**
 * MediID - Client-side Scripts
 * Modern, lightweight interactive functionality
 */

document.addEventListener('DOMContentLoaded', () => {
    // Mobile navigation menu toggle
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', () => {
            const isExpanded = navMenu.classList.toggle('active');
            navToggle.setAttribute('aria-expanded', isExpanded);
        });
    }

    // Dismissible alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        // Auto-fade alert after 5 seconds if displayed
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 400);
        }, 5000);
    });

    console.log('MediID Client initialized successfully.');
});
