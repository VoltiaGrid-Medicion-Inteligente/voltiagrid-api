# Arranque: todo el sistema en tu máquina

Objetivo (CT-01): alguien que no montó el ambiente tiene todo funcionando en **menos de 30 minutos**.
[English version](GETTING-STARTED.md).

## 1. Requisitos (se instalan una vez)

| Herramienta                                 | Versión    | Verificar                |
| ------------------------------------------- | ---------- | ------------------------ |
| Docker Desktop (con Docker Compose v2)      | 4.30+      | `docker compose version` |
| Git                                         | cualquiera | `git --version`          |
| Python                                      | 3.12       | `python --version`       |
| GNU make                                    | 4.x        | `make --version`         |
| Node.js (solo para la colección de pruebas) | 18+        | `node --version`         |

En Windows instala make con `winget install ezwinports.make` y abre una terminal nueva.
Docker Desktop debe estar **corriendo** antes de cualquier comando.

## 2. Clonar y configurar

```bash
git clone https://github.com/VoltiaGrid-Medicion-Inteligente/voltiagrid-api.git
cd voltiagrid-api
make env
```

`make env` crea `.env` a partir de `.env.example` (solo si no existe). Abre `.env` y cambia todos los
valores `change-me`. Para `JWT_SECRET` genera un valor largo y aleatorio:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`.env` está en `.gitignore`: nunca lo subas ni pegues sus valores en issues o chats.

## 3. Levantar todo

```bash
make up
```

Construye las imágenes, levanta Postgres y RabbitMQ, corre las migraciones y el seed (`migrate-seed`),
luego levanta las APIs y el simulador F3, y espera a que cada API responda `/health`.
La primera vez descarga imágenes y tarda unos minutos; después tarda segundos.

Verifica: `make ps` muestra cada servicio `(healthy)` y `migrate-seed` como `Exited (0)`.

## 4. Usarlo

| Qué                        | URL                        | Notas                                |
| -------------------------- | -------------------------- | ------------------------------------ |
| API de consumo del cliente | http://localhost:8001/docs | `POST /auth/token` entrega el JWT    |
| API de inventario de red   | http://localhost:8003/docs | usuarios internos                    |
| RabbitMQ (administración)  | http://localhost:15672     | usuario y contraseña de `.env`       |
| Postgres                   | `localhost:5433`           | base, usuario y contraseña de `.env` |

Pruébalo en `/docs` de la API de consumo:

1. `POST /auth/token` con `{"username": "CU-MAC000002", "password": "<DEMO_CUSTOMER_PASSWORD>"}` y copia `access_token`.
2. Clic en **Authorize**, pega el token y ejecuta `GET /me/consumption/daily?month=2013-02`.
3. Ejecuta `GET /customers/CU-MAC000003/consumption/daily?month=2013-02` con el mismo token: debe responder **403**.

## 5. Comandos make

| Comando      | Qué hace                                                                      |
| ------------ | ----------------------------------------------------------------------------- |
| `make up`    | Construye y levanta todo; migraciones y seed corren solos                     |
| `make ps`    | Servicios y su salud                                                          |
| `make logs`  | Sigue todos los logs; uno solo: `make logs s=api-customer-consumption`        |
| `make seed`  | Corre migraciones y seed otra vez (idempotente: no crea duplicados)           |
| `make test`  | Corre las pruebas en un contenedor contra la base del stack                   |
| `make down`  | Detiene los contenedores; los datos quedan en los volúmenes                   |
| `make clean` | Detiene y borra los volúmenes: el próximo `make up` arranca con la base vacía |

## 6. Problemas comunes

| Síntoma                                                                          | Causa y solución                                                                                                                                                                                                     |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `failed to connect to the docker API` / `open //./pipe/dockerDesktopLinuxEngine` | Docker Desktop no está corriendo. Ábrelo y espera _Engine running_.                                                                                                                                                  |
| `Bind for 0.0.0.0:5433 failed: port is already allocated`                        | Otro contenedor o un Postgres local usa el puerto. `docker ps` para encontrarlo y detenerlo, o cambia el lado izquierdo del puerto en `docker-compose.yml`. Igual para 5672, 15672, 8001, 8003.                      |
| `make: command not found`                                                        | make no está instalado o la terminal estaba abierta antes de instalarlo. `winget install ezwinports.make` y abre otra terminal. Sin make, corre a mano los comandos del `Makefile` (`docker compose up -d --build`). |
| `migrate-seed` terminó con error                                                 | `make logs s=migrate-seed`. Casi siempre es un valor de `.env`; corrígelo y corre `make seed`.                                                                                                                       |
| Una API sale `(unhealthy)` o `make up` dice _Not ready_                          | `make logs s=<servicio>`. Lo usual es que falte `JWT_SECRET` o que `DATABASE_URL` esté mal.                                                                                                                          |
| Windows bloquea `pip.exe` o `pytest.exe` (Application Control)                   | Usa `python -m pip` y `python -m pytest`, o `make test` (corre dentro de Docker). No desactives Smart App Control.                                                                                                   |
| Quiero empezar de cero                                                           | `make clean` y luego `make up`.                                                                                                                                                                                      |
