(() => {
  'use strict';

  const toggle = document.querySelector('.nav-toggle');
  const panel = document.querySelector('#primary-navigation');

  if (toggle && panel) {
    const closeMenu = () => {
      panel.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Mở menu');
    };

    toggle.addEventListener('click', () => {
      const isOpen = toggle.getAttribute('aria-expanded') === 'true';
      panel.classList.toggle('is-open', !isOpen);
      toggle.setAttribute('aria-expanded', String(!isOpen));
      toggle.setAttribute('aria-label', isOpen ? 'Mở menu' : 'Đóng menu');
    });

    panel.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeMenu();
    });
    document.addEventListener('click', (event) => {
      if (!panel.contains(event.target) && !toggle.contains(event.target)) closeMenu();
    });
  }

  document.querySelectorAll('.flash-close').forEach((button) => {
    button.addEventListener('click', () => {
      const message = button.closest('.flash');
      if (message) message.remove();
    });
  });

  const contactSubmit = document.querySelector('#contact-submit');
  if (contactSubmit) {
    let remaining = Number.parseInt(contactSubmit.dataset.cooldown || '0', 10);
    if (Number.isFinite(remaining) && remaining > 0) {
      contactSubmit.disabled = true;
      contactSubmit.textContent = `Đã gửi — thử lại sau ${remaining} giây`;
      const countdown = window.setInterval(() => {
        remaining -= 1;
        if (remaining > 0) {
          contactSubmit.textContent = `Đã gửi — thử lại sau ${remaining} giây`;
          return;
        }
        window.clearInterval(countdown);
        contactSubmit.disabled = false;
        contactSubmit.textContent = 'Gửi lời nhắn';
      }, 1000);
    }
  }
})();
