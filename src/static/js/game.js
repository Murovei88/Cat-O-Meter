// Загрузка глобальной статистики
async function loadGlobalStats() {
    try {
        const response = await fetch('/api/global-stats');
        const stats = await response.json();
        
        const statsElement = document.getElementById('globalStats');
        if (stats.database_available) {
            statsElement.innerHTML = `
                <div>✅ Проверок выполнено: <strong>${stats.total_checks}</strong></div>
                <div>👥 Уникальных пользователей: <strong>${stats.unique_users}</strong></div>
                <div>📊 Средний процент котиковости: <strong>${stats.average_percentage}%</strong></div>
            `;
        } else {
            statsElement.innerHTML = '📊 Статистика временно недоступна';
        }
    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('globalStats').innerHTML = '❌ Ошибка загрузки статистики';
    }
}

// Проверка котиковости
async function checkCatPercentage() {
    const nameInput = document.getElementById('nameInput');
    const checkBtn = document.getElementById('checkBtn');
    const btnText = checkBtn.querySelector('.btn-text');
    const btnLoading = checkBtn.querySelector('.btn-loading');
    const name = nameInput.value.trim();
    
    if (!name) {
        alert('Пожалуйста, введите имя!');
        return;
    }
    
    // Показываем индикатор загрузки
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    checkBtn.disabled = true;
    
    try {
        const response = await fetch(`/api/cat-meter/${encodeURIComponent(name)}`);
        const result = await response.json();
        
        displayResult(result);
        
        // Перезагружаем статистику
        loadGlobalStats();
        
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка при проверке. Попробуйте еще раз!');
    } finally {
        // Восстанавливаем кнопку
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        checkBtn.disabled = false;
    }
}

// Отображение результата
function displayResult(result) {
    const inputSection = document.getElementById('inputSection');
    const resultSection = document.getElementById('resultSection');
    const progressFill = document.getElementById('progressFill');
    
    // Обновляем данные
    document.getElementById('resultName').textContent = result.name;
    document.getElementById('resultPercentage').textContent = result.percentage;
    document.getElementById('resultPhrase').textContent = result.phrase;
    document.getElementById('catEmoji').textContent = result.emoji;
    
    // Показываем результат
    inputSection.style.display = 'none';
    resultSection.style.display = 'block';
    
    // Анимируем прогресс-бар
    setTimeout(() => {
        progressFill.style.width = `${result.percentage}%`;
    }, 100);
}

// Сброс игры
function resetGame() {
    const inputSection = document.getElementById('inputSection');
    const resultSection = document.getElementById('resultSection');
    const progressFill = document.getElementById('progressFill');
    const nameInput = document.getElementById('nameInput');
    
    // Сбрасываем анимацию прогресс-бара
    progressFill.style.width = '0%';
    
    // Показываем форму, скрываем результат
    resultSection.style.display = 'none';
    inputSection.style.display = 'block';
    
    // Очищаем поле ввода и фокусируемся на нем
    nameInput.value = '';
    nameInput.focus();
}

// Обработка нажатия Enter в поле ввода
document.getElementById('nameInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        checkCatPercentage();
    }
});

// Загружаем статистику при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadGlobalStats();
    
    // Фокусируемся на поле ввода
    document.getElementById('nameInput').focus();
});
