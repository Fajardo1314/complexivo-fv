# Configuración del Proxy Reverso Nginx en Raspberry Pi

Este documento contiene la guía paso a paso para configurar, desplegar y validar el Proxy Reverso Nginx en la Raspberry Pi.

---

## 📋 Arquitectura de Red y Puertos

El sistema utiliza la red del Host de la Raspberry Pi (`network_mode: host` en Docker Compose) para facilitar la comunicación directa y simplificar el acceso a recursos físicos.

*   **Puerto `80` (Nginx/Web Dashboard)**: Punto de entrada único. Expone la interfaz web y redirige las llamadas API.
*   **Puerto `5000` (Flask/backend-control)**: Escucha localmente en la Raspberry Pi. Solo es accesible externamente a través de la redirección `/api/` en el puerto `80`.
*   **Netbird VPN**: Mapea la IP pública de la VPN (`raspberryfv.netbird.cloud` o la IP de red interna asignada) directamente al puerto `80` de la Raspberry Pi.

---

## ⚙️ Paso 1: Configuración de Nginx (`nginx.conf`)

El archivo [nginx.conf](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/nginx.conf) define el enrutamiento. Asegúrate de que tiene la siguiente estructura:

```nginx
server {
    listen 80;
    server_name localhost;

    # 1. Servir el panel de control web
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 2. Redirigir peticiones API al backend de Flask en el puerto 5000
    location /api/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> [!IMPORTANT]
> El slash final en `proxy_pass http://127.0.0.1:5000/;` es crucial. Remueve el prefijo `/api/` antes de enviar la petición a Flask. Por ejemplo, una llamada a `http://<IP>/api/sensores` se transforma en `http://127.0.0.1:5000/sensores`.

---

## 📦 Paso 2: Orquestación con Docker Compose

El servicio `web-dashboard` debe montarse con acceso a los archivos web y al archivo de configuración de Nginx. En [docker-compose.yml](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/docker-compose.yml):

```yaml
  web-dashboard:
    image: nginx:alpine
    container_name: web-dashboard
    restart: unless-stopped
    network_mode: host
    volumes:
      # Montar carpeta con la interfaz web estática
      - ./web_dashboard:/usr/share/nginx/html:ro
      # Sobrescribir la configuración de Nginx por defecto
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

---

## 🚀 Paso 3: Despliegue y Reinicio

Para aplicar cambios en el proxy reverso sin afectar a los otros contenedores, ejecuta en la terminal de la Raspberry Pi:

```bash
# 1. Ir al directorio del proyecto
cd /home/user/proyecto_grado

# 2. Reiniciar únicamente el contenedor del proxy reverso
sudo docker compose restart web-dashboard
```

Si modificas el archivo `nginx.conf`, debes recrear el contenedor para que Nginx lea la nueva configuración:

```bash
sudo docker compose up -d --force-recreate web-dashboard
```

---

## 🔍 Paso 4: Verificación y Troubleshooting

### 1. Comprobar que Nginx está corriendo
```bash
sudo docker ps --filter name=web-dashboard
```
Debe mostrar el estado `Up`.

### 2. Verificar la sintaxis de la configuración interna
```bash
sudo docker exec -it web-dashboard nginx -t
```
El resultado esperado es:
`nginx: the configuration file /etc/nginx/nginx.conf syntax is ok`  
`nginx: configuration file /etc/nginx/nginx.conf test is successful`

### 3. Probar respuesta localmente desde la Pi
```bash
# Probar acceso al Dashboard
curl -I http://127.0.0.1:80/

# Probar acceso al endpoint de la API redirigida
curl -I http://127.0.0.1:80/api/sensores
```

### 4. Revisar los logs en tiempo real si hay fallas (p. ej. error 502 Bad Gateway)
```bash
sudo docker logs web-dashboard -f
```
*(Si obtienes error `502 Bad Gateway`, significa que Nginx está activo, pero el contenedor `backend-control` está apagado o no está escuchando en el puerto 5000).*
