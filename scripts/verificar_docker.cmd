@echo off
REM Verificacion del Hito 004: docker compose config + up --build + /health + CLI dentro del contenedor.
REM Guarda toda la salida en docker_evidence.txt en la raiz del repositorio.
cd /d "%~dp0.."
set LOG=docker_evidence.txt
echo Ejecutando verificacion Docker... la salida se guarda en %LOG%
(
echo $ docker compose version
docker compose version
echo.
echo $ docker compose config -q ^&^& echo "Compose OK"
docker compose config -q && echo Compose OK
echo.
echo $ docker compose up --build -d --wait
docker compose up --build -d --wait
echo.
echo $ docker compose ps
docker compose ps
echo.
echo $ curl -i http://localhost:8000/health
curl -s -i http://localhost:8000/health
echo.
echo.
echo $ docker compose exec api python -m src.adapters.inbound.cli health
docker compose exec -T api python -m src.adapters.inbound.cli health
echo.
echo $ docker compose exec api python -m src.adapters.inbound.cli create --incident-id INC-DOCKER-1 --title "Caida pagos" --raw-text "HTTP 502 Bad Gateway en todas las transacciones de la pasarela de pagos. Ningun comercio puede cobrar." --created-at 2026-11-09T10:00:00
docker compose exec -T api python -m src.adapters.inbound.cli create --incident-id INC-DOCKER-1 --title "Caida pagos" --raw-text "HTTP 502 Bad Gateway en todas las transacciones de la pasarela de pagos. Ningun comercio puede cobrar." --created-at 2026-11-09T10:00:00
echo.
echo $ docker compose exec api python -m src.adapters.inbound.cli summary --reference-time 2026-11-09T12:00:00
docker compose exec -T api python -m src.adapters.inbound.cli summary --reference-time 2026-11-09T12:00:00
echo.
echo $ curl "http://localhost:8000/api/v1/incidents/INC-DOCKER-1/sla?reference_time=2026-11-09T10:30:00"
curl -s "http://localhost:8000/api/v1/incidents/INC-DOCKER-1/sla?reference_time=2026-11-09T10:30:00"
echo.
echo.
echo $ docker compose stop db   [simula caida de la base]
docker compose stop db
echo $ curl -i http://localhost:8000/health
curl -s -i http://localhost:8000/health
echo.
echo.
echo $ docker compose start db
docker compose start db
timeout /t 8 /nobreak >nul
echo $ curl -i http://localhost:8000/health
curl -s -i http://localhost:8000/health
echo.
echo.
echo $ docker compose logs --tail 15 api
docker compose logs --tail 15 api
echo.
echo FIN
) > "%LOG%" 2>&1
echo Listo. Revisa %LOG%
timeout /t 5 >nul
