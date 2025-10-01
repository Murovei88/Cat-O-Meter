FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь исходный код (включая статику и шаблоны)
COPY src/ ./src/

# Создаем папку для данных с правильными правами
RUN mkdir -p /app/data && chmod 755 /app/data

# Создаем пользователя для безопасности
RUN useradd -m -r app && chown -R app:app /app
USER app

# Экспортируем порт
EXPOSE 8000

# Запускаем приложение
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
