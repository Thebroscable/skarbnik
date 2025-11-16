## Instalacja

1. Sklonuj repozytorium na serwer:

```bash
git clone https://github.com/Thebroscable/smieszek
cd smieszek
```

2. Budowanie obrazu i uruchomienie kontenera:

```bash
docker-compose up -d --build
```

3. Sprawdzenie logów

```bash
docker-compose logs -f
```

4. Zatrzymanie bota

```bash
docker-compose down
```