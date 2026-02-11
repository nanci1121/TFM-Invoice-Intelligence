# Guía Definitiva: Instalación de Docker y Docker Compose en WSL (Windows 11)

Esta guía te ayudará a instalar Docker Engine y Docker Compose de forma nativa en tu distribución Debian/Ubuntu dentro de WSL2.

## 0. Prerrequisito: Si necesitas recuperar tu contraseña de usuario en WSL

Si al usar `sudo` te falla la contraseña y no puedes continuar, sigue estos pasos desde Windows para resetearla:

1. Abre una nueva terminal de **PowerShell** en Windows.
2. Ejecuta el siguiente comando para entrar como `root` (administrador) sin contraseña:
   ```powershell
   wsl -d Debian -u root
   ```
   *(Nota: Si tu distribución se llama diferente a "Debian", ajusta el nombre. Puedes ver los nombres con `wsl -l -v` en PowerShell).*
3. Una vez dentro (el prompt será `root@...`), cambia la contraseña de tu usuario (ej. `venan`):
   ```bash
   passwd venan
   ```
4. Escribe la nueva contraseña dos veces.
5. Escribe `exit` para salir.

Ahora puedes volver a tu terminal de WSL y usar la nueva contraseña para los siguientes pasos.

---

## 1. Preparación del Sistema

Abre tu terminal de WSL (Debian) y ejecuta:

```bash
# Actualizar lista de paquetes
sudo apt-get update

# Instalar paquetes necesarios para permitir que apt use repositorios sobre HTTPS
sudo apt-get install -y ca-certificates curl gnupg
```

## 2. Configurar el Repositorio Oficial de Docker

```bash
# Crear directorio para las llaves GPG si no existe
sudo install -m 0755 -d /etc/apt/keyrings

# Descargar la llave GPG oficial de Docker
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Dar permisos de lectura a la llave
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Añadir el repositorio a las fuentes de Apt
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

*(Nota: Si usas Ubuntu en lugar de Debian, la URL en el comando `echo` cambiaría de `.../linux/debian` a `.../linux/ubuntu`).*

## 3. Instalar Docker Engine y Docker Compose

Ahora instalamos el motor de Docker, la herramienta de línea de comandos, el runtime de contenedores y los plugins (incluyendo Docker Compose v2).

```bash
# Actualizar el índice de paquetes con el nuevo repositorio de Docker incluido
sudo apt-get update

# Instalar los paquetes
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 4. Configuración Post-Instalación (Importante)

### Ejecutar Docker sin `sudo`
Por defecto, Docker requiere permisos de root. Para evitar escribir `sudo` en cada comando:

```bash
# Añadir tu usuario al grupo 'docker'
sudo usermod -aG docker $USER
```
**Importante:** Para que este cambio surta efecto, debes cerrar tu sesión actual. Puedes:
- Cerrar la terminal y volver a abrirla.
- O ejecutar: `newgrp docker`

### Habilitar el servicio
En WSL con systemd habilitado (tu caso), asegúrate de que el servicio arranque:

```bash
sudo systemctl enable --now docker
```

## 5. Verificación

Comprueba que tienes las versiones correctas:

```bash
# Versión de Docker
docker --version

# Versión de Docker Compose (nota el espacio, no es docker-compose con guión en la v2)
docker compose version
```

Prueba a ejecutar un contenedor de prueba:

```bash
docker run hello-world
```

Si ves un mensaje que dice "Hello from Docker!", ¡felicidades! Todo está correctamente instalado.

---

## 6. Monitorización de Logs y Depuración

Para ver los logs del servicio "watcher" en tiempo real y verificar si las facturas se procesan correctamente (útil para detectar errores al cargar archivos):

```bash
docker compose logs -f watcher
```
