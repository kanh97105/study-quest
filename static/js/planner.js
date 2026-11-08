/* Smart Exam Planner: server remains the source of truth for progress. */
(function () {
  'use strict';

  document.querySelectorAll('[data-plan-form]').forEach(function (form) {
    form.addEventListener('submit', function () {
      var button = form.querySelector('button');
      if (button) {
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
      }
    });
  });

  // Progressive enhancement only: the percentage is rendered by the server.
  // No client-supplied progress is posted or trusted.
  var progressValue = document.querySelector('[data-progress-value]');
  var progressBar = document.querySelector('[data-progress-bar]');
  if (progressValue && progressBar) {
    var percent = parseInt(progressValue.textContent, 10);
    if (!Number.isNaN(percent)) {
      percent = Math.max(0, Math.min(100, percent));
      progressBar.style.width = percent + '%';
    }
  }
}());
