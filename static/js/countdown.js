document.addEventListener("DOMContentLoaded", function() {
    const timerElement = document.getElementById('countdown');
    if (!timerElement) return;

    let seconds = parseInt(timerElement.getAttribute('data-seconds'), 10);
    const bookingCode = timerElement.getAttribute('data-code');
    
    function formatTime(sec) {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    function checkStatus() {
        fetch(`/status/${bookingCode}/`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'checked_in' || data.is_expired) {
                    window.location.reload(); // Reload to show updated status
                } else if (data.time_remaining !== undefined) {
                    // Sync timer with server
                    seconds = data.time_remaining;
                }
            })
            .catch(console.error);
    }

    function updateTimer() {
        if (seconds <= 0) {
            timerElement.textContent = "00:00";
            timerElement.classList.add('timer-critical');
            clearInterval(interval);
            setTimeout(() => window.location.reload(), 2000);
            return;
        }

        timerElement.textContent = formatTime(seconds);

        if (seconds < 60) {
            timerElement.classList.remove('timer-warning');
            timerElement.classList.add('timer-critical');
        } else if (seconds < 300) { // under 5 mins
            timerElement.classList.add('timer-warning');
        }

        seconds--;
    }

    // Initial call
    updateTimer();
    
    // Update every second
    const interval = setInterval(updateTimer, 1000);

    // Sync with server every 10 seconds
    setInterval(checkStatus, 10000);
});
