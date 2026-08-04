document.addEventListener('DOMContentLoaded', function () {
    // Clock
    function updateClock() {
        const el = document.getElementById('currentTime');
        if (el) {
            const now = new Date();
            el.textContent = now.toLocaleString('en-ZA', {
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        }
    }
    updateClock();
    setInterval(updateClock, 30000);

    // Sidebar toggle (desktop collapse / mobile drawer)
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    function isMobile() {
        return window.matchMedia('(max-width: 991.98px)').matches;
    }

    function openSidebar() {
        sidebar.classList.add('open');
        overlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    function resetDesktopState() {
        sidebar.style.width = '';
        sidebar.style.padding = '';
        sidebar.querySelectorAll('.nav-link').forEach(el => {
            el.style.textAlign = '';
            el.style.padding = '';
        });
        sidebar.querySelectorAll('.nav-link i').forEach(el => {
            el.style.marginRight = '';
        });
        document.querySelectorAll('.sidebar .nav-link span, .sidebar .fs-5, .sidebar hr + div').forEach(el => {
            el.style.display = '';
        });
    }

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            if (isMobile()) {
                if (sidebar.classList.contains('open')) {
                    closeSidebar();
                } else {
                    openSidebar();
                }
            } else {
                if (sidebar.style.width === '60px') {
                    resetDesktopState();
                } else {
                    sidebar.style.width = '60px';
                    sidebar.querySelectorAll('.nav-link span, .sidebar .fs-5, .sidebar hr + div').forEach(el => el.style.display = 'none');
                    sidebar.querySelectorAll('.nav-link').forEach(el => {
                        el.style.textAlign = 'center';
                        el.style.padding = '8px';
                    });
                    sidebar.querySelectorAll('.nav-link i').forEach(el => {
                        el.style.marginRight = '0';
                    });
                }
            }
        });

        if (overlay) {
            overlay.addEventListener('click', closeSidebar);
        }
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeSidebar();
        });
        sidebar.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                if (isMobile()) closeSidebar();
            });
        });
        window.addEventListener('resize', function () {
            if (isMobile()) {
                resetDesktopState();
                closeSidebar();
            }
        });
    }

    // Auto-dismiss alerts
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });

    // Confirm deletes
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(el.dataset.confirm || 'Are you sure?')) {
                e.preventDefault();
            }
        });
    });

    // Clickable table rows (navigate on row click, unless an inner link/button is used)
    document.querySelectorAll('tr[data-href]').forEach(function (row) {
        row.addEventListener('click', function (e) {
            if (e.target.closest('a, button, form, input')) return;
            window.location.href = row.dataset.href;
        });
    });
});
