# Wybieramy oficjalny obraz Pythona
FROM python:3.11-slim

# Ustawiamy katalog roboczy
WORKDIR /app

# Kopiujemy pliki bota
COPY bot.py requirements.txt ./
COPY .env ./

# Instalujemy wymagane biblioteki
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Ustawiamy komendę uruchamiającą bota
CMD ["python", "bot.py"]
