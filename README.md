# Cat-O-Meter (FastAPI) + Monitoring Stack

Готовый проект игры (FastAPI) с мониторингом: Prometheus, Grafana, Loki, Promtail, cAdvisor, node-exporter, blackbox-exporter.

## Запуск

1. Собрать и поднять:
```bash
docker compose build cat-api
docker compose up -d
```

2. Открыть:
- Приложение: `http://localhost:8000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (здесь_был_пароль)
- Alertmanager: `http://localhost:9093`

## Что входит
- FastAPI `src/main.py`
  - `/metrics` (prometheus-fastapi-instrumentator)
  - JSON-логи (python-json-logger)
- Мониторинг в `docker-compose.yml`:
  - Prometheus + алерты `monitoring/prometheus/alerts.yml`
  - Grafana + провижининг источников и дашборда `API Overview`
  - Loki + Promtail (логи контейнеров)
  - cAdvisor, node-exporter, blackbox-exporter

## Конфиги
- Prometheus: `monitoring/prometheus/prometheus.yml`
- Алерты: `monitoring/prometheus/alerts.yml`
- Grafana datasources: `monitoring/grafana/provisioning/datasources/datasources.yml`
- Grafana dashboards: `monitoring/grafana/provisioning/dashboards`
- Loki: `monitoring/loki/config.yml`
- Promtail: `monitoring/promtail/config.yml`


## Публикация наружу
- Cloudflare Tunnel (без портов) или Traefik/Caddy (авто-HTTPS на домене).

## Git
```bash
git init
git add .
git commit -m "init: cat-api + monitoring stack"
# HTTPS или SSH (рекомендуется)
git remote add origin git@github.com:YOUR_USER/Cat-O-Meter.git
git branch -M main
git push -u origin main
```


