# Базовый образ Python
FROM python:3.11

# Устанавливаем рабочий каталог
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt requirements.txt

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файл с ботом в контейнер
COPY mishbot.py .

# Запускаем бота при старте контейнера
CMD ["python", "mishbot.py"]

