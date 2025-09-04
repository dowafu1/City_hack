document.addEventListener('DOMContentLoaded', () => {
    console.log('JS loaded for CMP Tomsk Telegram Bot frontend');

    const toggleButtons = document.querySelectorAll('.toggle-section');
    toggleButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target');
            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                targetSection.classList.toggle('hidden');
                button.textContent = targetSection.classList.contains('hidden')
                    ? 'Показать'
                    : 'Скрыть';
            }
        });
    });

    const aiButton = document.querySelector('#ai-button');
    if (aiButton) {
        aiButton.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/ai-support', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: 'Получить совет дня' })
                });
                const data = await response.json();
                alert(data.message || 'AI-поддержка активирована!');
            } catch (error) {
                console.error('AI request failed:', error);
                alert('Ошибка при обращении к AI');
            }
        });
    }

    const adminForm = document.querySelector('#admin-form');
    if (adminForm) {
        adminForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(adminForm);
            const data = Object.fromEntries(formData);
            try {
                const response = await fetch('/api/admin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                alert(result.success ? '✅ Сохранено' : '❌ Неверный формат');
            } catch (error) {
                console.error('Admin form submission failed:', error);
                alert('Ошибка при сохранении данных');
            }
        });
    }
});