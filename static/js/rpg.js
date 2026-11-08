(() => {
  const nameField = document.getElementById('character_name');
  if (nameField) {
    nameField.addEventListener('input', () => {
      nameField.value = nameField.value.slice(0, 30);
    });
  }

  const form = document.getElementById('profile-form');
  if (form) {
    const preview = document.getElementById('avatar-preview');
    const previewLabel = document.getElementById('avatar-preview-label');
    const avatarOptions = form.querySelectorAll('input[name="avatar"]');

    avatarOptions.forEach((option) => {
      option.addEventListener('change', () => {
        if (preview) {
          preview.src = option.dataset.image;
          preview.alt = option.dataset.label;
        }
        if (previewLabel) previewLabel.textContent = option.dataset.label;

        avatarOptions.forEach((item) => {
          const status = item.closest('.profile-avatar-option')?.querySelector('[data-avatar-selected]');
          if (status) status.textContent = item.checked ? 'Đang chọn' : 'Chọn avatar';
        });
      });
    });

    form.addEventListener('submit', (event) => {
      const avatarSelected = form.querySelector('input[name="avatar"]:checked');
      if (!avatarSelected) {
        event.preventDefault();
        window.alert('Em hãy chọn một avatar trong danh sách nhé.');
      }
    });
  }

  const calendarToggle = document.getElementById('freeze-calendar-toggle');
  const calendar = document.getElementById('freeze-calendar');
  const freezeDialog = document.getElementById('freeze-confirm-dialog');
  if (calendarToggle && calendar && freezeDialog) {
    const selectedDay = document.getElementById('freeze-selected-day');
    const cancelButton = document.getElementById('freeze-cancel');
    const confirmButton = document.getElementById('freeze-confirm');
    const closeButton = document.getElementById('freeze-close');
    const notice = document.getElementById('freeze-preview-notice');

    calendarToggle.addEventListener('click', () => {
      const isExpanded = calendarToggle.getAttribute('aria-expanded') === 'true';
      calendar.hidden = isExpanded;
      calendarToggle.setAttribute('aria-expanded', String(!isExpanded));
      if (!isExpanded) calendar.querySelector('.profile-calendar-day')?.focus();
    });

    calendar.querySelectorAll('.profile-calendar-day').forEach((dayButton) => {
      dayButton.addEventListener('click', () => {
        selectedDay.textContent = `Ngày minh họa ${dayButton.dataset.previewDay} · Bản xem trước`;
        notice.hidden = true;
        confirmButton.hidden = false;
        closeButton.hidden = true;
        freezeDialog.showModal();
      });
    });

    cancelButton.addEventListener('click', () => freezeDialog.close());
    closeButton.addEventListener('click', () => freezeDialog.close());
    confirmButton.addEventListener('click', () => {
      notice.textContent = 'Tính năng sẽ hoạt động khi backend được tích hợp';
      notice.hidden = false;
      confirmButton.hidden = true;
      closeButton.hidden = false;
      closeButton.focus();
    });
    freezeDialog.addEventListener('close', () => calendarToggle.focus());
  }
})();
