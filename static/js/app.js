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

    // Sidebar toggle
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            if (sidebar.style.width === '60px') {
                sidebar.style.width = '';
                sidebar.style.padding = '';
                document.querySelectorAll('.sidebar .nav-link span, .sidebar .fs-5, .sidebar hr + div').forEach(el => el.style.display = '');
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
});
