(() => {
  const subjectSelect = document.getElementById('subject');
  const topicSelect = document.getElementById('topic');
  const topicStatus = document.getElementById('topic-status');
  const initialTopic = topicSelect ? topicSelect.dataset.initialTopic : '';

  if (subjectSelect && topicSelect) {
    const loadTopics = async (preferredTopic = '') => {
      const subject = subjectSelect.value;
      topicSelect.replaceChildren(new Option('Tất cả chủ đề', ''));
      if (!subject) {
        if (topicStatus) topicStatus.textContent = 'Chọn môn để tải chủ đề';
        return;
      }
      try {
        const response = await fetch(`/quiz/topics?subject=${encodeURIComponent(subject)}`, {
          headers: { Accept: 'application/json' },
          credentials: 'same-origin',
        });
        if (!response.ok) throw new Error('Không tải được chủ đề');
        const data = await response.json();
        for (const topic of data.topics || []) {
          topicSelect.add(new Option(topic, topic));
        }
        if ((data.topics || []).includes(preferredTopic)) {
          topicSelect.value = preferredTopic;
        }
        if (topicStatus) topicStatus.textContent = `${(data.topics || []).length} chủ đề khả dụng`;
      } catch (_error) {
        if (topicStatus) topicStatus.textContent = 'Không tải được chủ đề; em có thể chọn tất cả chủ đề.';
      }
    };
    subjectSelect.addEventListener('change', () => loadTopics());
    if (subjectSelect.value) loadTopics(initialTopic);
  }

  const playForm = document.getElementById('quiz-play-form');
  const answeredCount = document.getElementById('answered-count');
  if (playForm && answeredCount) {
    const updateCount = () => {
      const selected = playForm.querySelectorAll('input[type="radio"]:checked').length;
      answeredCount.textContent = String(selected);
    };
    playForm.addEventListener('change', updateCount);
    playForm.addEventListener('submit', (event) => {
      const hasAnswer = playForm.querySelector('input[type="radio"]:checked');
      if (!hasAnswer && !window.confirm('Em chưa chọn đáp án nào. Vẫn nộp bài chứ?')) {
        event.preventDefault();
      }
    });
  }
})();
