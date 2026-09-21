# Guía de Despliegue en Producción

**Plataforma de Evaluación y Corrección Climatológica (GridCorr)**  
*Ministerio de Medio Ambiente y Recursos Naturales (MARN) — El Salvador*

---

## 1. Opciones de Despliegue

La plataforma puede desplegarse en infraestructura institucional bajo tres modalidades:

1. **Contenedor Docker / Docker Compose** (Recomendado para servidores Linux en MARN).
2. **Servicio Systemd con Proxy Inverso Nginx** (Despliegue nativo en servidor Linux).
3. **Ejecución Local / Intranet en Estaciones de Trabajo** (Para meteorólogos e investigadores).

---

## 2. Despliegue con Docker Compose (Recomendado)

### 2.1 Configuración de Volúmenes y Variables
Edita el archivo `.env` o `compose.yaml` para enlazar el repositorio central de datos climatológicos del MARN:

```yaml
services:
  gridcorr-app:
    build: .
    container_name: gridcorr_evaluation_app
    ports:
      - "8501:8501"
    volumes:
      - /mnt/datos_clima/DATA:/app/DATA:ro
      - /mnt/almacenamiento/salidas_gridcorr:/app/salidas:rw
    restart: always
```

### 2.2 Despliegue y Gestión
```bash
# Iniciar en segundo plano
docker compose up -d --build

# Ver logs en tiempo real
docker compose logs -f

# Detener el servicio
docker compose down
```

---

## 3. Despliegue con Systemd y Nginx (Servidor Bare-Metal / VM)

### 3.1 Crear Servicio Systemd (`/etc/systemd/system/gridcorr.service`)
```ini
[Unit]
Description=GridCorr Streamlit Climatology Application
After=network.target

[Service]
Type=simple
User=meteorologia
WorkingDirectory=/opt/gridcorr-evaluation
ExecStart=/opt/gridcorr-evaluation/.venv/bin/streamlit run app.py --server.port=8501 --server.address=127.0.0.1 --server.headless=true
Restart=always
RestartSec=5
Environment=PATH=/opt/gridcorr-evaluation/.venv/bin:/usr/bin
Environment=CHIRPTS_DATA_DIR=/opt/gridcorr-evaluation/DATA
Environment=CHIRPTS_OUT_DIR=/opt/gridcorr-evaluation/salidas

[Install]
WantedBy=multi-user.target
```

Habilitar e iniciar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gridcorr
sudo systemctl start gridcorr
sudo systemctl status gridcorr
```

### 3.2 Configuración de Nginx como Reverse Proxy (`/etc/nginx/sites-available/gridcorr`)
```nginx
server {
    listen 80;
    server_name gridcorr.ambiente.gob.sv;

    # Redireccionar HTTP a HTTPS si hay certificados SSL disponibles
    # return 301 https://$host$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

Activar y recargar Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/gridcorr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4. Estrategia de Seguridad y Recursos

1. **Permisos de Solo Lectura en Datos de Entrada**:
   El contenedor o proceso solo debe requerir permisos de lectura sobre el directorio `DATA/` para proteger la integridad de las series históricas.
2. **Control de Concurrencia**:
   Streamlit maneja sesiones aisladas por navegador. Para operaciones concurrentes pesadas, `CHIRPTS_MAX_WORKERS` limita la sobrecarga de CPU.
3. **Respaldos de Salidas**:
   El directorio `salidas/` debe respaldarse periódicamente mediante tareas cron o almacenamiento persistente adjunto.
