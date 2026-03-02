'use strict';

document.addEventListener('DOMContentLoaded', function () {
    // AJAX Hint System
    const hintBtn = document.getElementById('hint-btn');
    if (hintBtn) {
        hintBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const roomId = hintBtn.dataset.roomId;
            const hintsList = document.getElementById('hints-list');
            const noHintsMsg = document.getElementById('no-hints-msg');

            hintBtn.disabled = true;
            hintBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading...';

            fetch(`/room/${roomId}/hint`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    if (data.error) {
                        hintBtn.textContent = 'No more hints';
                        hintBtn.classList.replace('btn-outline-warning', 'btn-secondary');
                        return;
                    }

                    // Remove "no hints yet" placeholder if present
                    if (noHintsMsg) {
                        noHintsMsg.remove();
                    }

                    // Append new hint item
                    const li = document.createElement('li');
                    li.className = 'hint-item';
                    li.innerHTML = '<i class="bi bi-chevron-right text-warning me-1"></i>' + escapeHtml(data.hint);
                    hintsList.appendChild(li);

                    const remaining = data.max_hints - data.hints_used;

                    // Update the "X / 3 used" counter
                    const counter = document.getElementById('hints-used-counter');
                    if (counter) {
                        counter.textContent = data.hints_used + ' / 3 used';
                    }

                    if (remaining <= 0) {
                        hintBtn.outerHTML = '<p style="color: rgba(255,255,255,0.4); font-size: 0.9rem;"><i class="bi bi-lightbulb-off me-1"></i>No more hints available.</p>';
                    } else {
                        hintBtn.disabled = false;
                        hintBtn.innerHTML = '<i class="bi bi-lightbulb me-1"></i>Get Hint (' + remaining + ' remaining)';
                    }
                })
                .catch(function () {
                    // Fallback to regular link if fetch fails
                    hintBtn.disabled = false;
                    hintBtn.innerHTML = '<i class="bi bi-lightbulb me-1"></i>Get Hint';
                    window.location.href = `/room/${roomId}/hint`;
                });
        });
    }

    // Wrong answer shake animation
    const wrongAlert = document.getElementById('wrong-answer-alert');
    if (wrongAlert) {
        wrongAlert.classList.add('shake');
        wrongAlert.addEventListener('animationend', function () {
            wrongAlert.classList.remove('shake');
        });
    }

    // Attempt counter pulse on load
    const attemptDisplay = document.getElementById('attempt-display');
    if (attemptDisplay && parseInt(attemptDisplay.textContent, 10) > 0) {
        attemptDisplay.style.transition = 'color 0.5s';
        setTimeout(function () {
            attemptDisplay.style.color = '#ff6b6b';
        }, 300);
    }

    // Auto focus answer input
    const answerInput = document.getElementById('answer-input');
    if (answerInput) {
        answerInput.focus();
    }

    // Feedback page: press Enter to follow the main action button
    const feedbackBtn = document.getElementById('feedback-action-btn');
    if (feedbackBtn) {
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                window.location.href = feedbackBtn.href;
            }
        });
    }

    // Confirm restart
    const restartForms = document.querySelectorAll('form[action*="restart"]');
    restartForms.forEach(function (form) {
        // Only confirm if we are inside the game (session active nav shows player name)
        const inGame = document.querySelector('.navbar [name]') !== null;
        if (!inGame) return;
        form.addEventListener('submit', function (e) {
            if (!confirm('Are you sure you want to restart? Your progress will be lost.')) {
                e.preventDefault();
            }
        });
    });

});

// utils escape html for dynamic content
function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}
