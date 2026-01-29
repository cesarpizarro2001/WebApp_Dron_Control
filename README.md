# WebApp Control de Drones

## 1. Presentación
En este repositorio se describe cómo controlar un dron desde cualquier dispositivo conectado a internet, sin necesidad de instalar ninguna app en el dispositivo. Para ello se utiliza el framework Flask para implementar un servidor web en Python.

El sistema incluye:
- Control mediante interfaz web desde cualquier navegador
- Control por voz en español
- Control por gestos mediante cámara
- Control modo piloto (mando real y joysticks virtuales)
- Control por sensores del movil
- Telemetría en tiempo real
- Video camara del dron en tiempo real
- Sistema de waypoints y rutas
- Interfaz para alumnos

## 2. Requerimientos

- Python 3.10.x (versión requerida)
- Mission Planner (para simulación o conexión con dron real)
- Navegador web moderno (Chrome, Firefox, Edge)

## 3. Instalación

### Paso 1: Instalar Python 3.10.x
1. Descargar Python 3.10.x desde la página oficial: https://www.python.org/downloads/release/python-3100/
   - **IMPORTANTE**: Asegúrate de descargar la versión 3.10.x (ejemplo: 3.10.0)
   - **NO** instalar versiones superiores ni inferiores
2. Durante la instalación:
   - ✅ Marcar la opción **"Add Python to PATH"**
   - Seleccionar "Install Now" o personalizar la ubicación si lo deseas
3. Verificar la instalación abriendo CMD y ejecutando:
   ```
   python --version
   ```
   Debe mostrar: `Python 3.10.x`

### Paso 2: Instalar Dependencias Automáticamente
1. Navegar hasta la carpeta del proyecto
2. Ejecutar el archivo **`setup.bat`** haciendo doble clic
3. El script automáticamente:
   - ✅ Verificará que tengas Python 3.10.x instalado
   - ✅ Instalará todas las librerías necesarias desde `requirements.txt`
   - ✅ Configurará el entorno correctamente
4. Esperar a que finalice la instalación (puede tardar varios minutos)
5. Si todo es correcto, verás un mensaje de confirmación

**Nota**: Si el script detecta una versión incorrecta de Python, mostrará un error y deberás instalar Python 3.10.x antes de continuar.

### Paso 3: Configurar Certificados HTTPS
1. Abrir Git Bash en la carpeta del proyecto
2. Ejecutar el siguiente comando:
   ```bash
   openssl req -newkey rsa:2048 -nodes -keyout private_key.pem -x509 -days 365 -out public_certificate.pem
   ```
3. Rellenar los campos solicitados:
   - Nombre del país (código de 2 letras): `ES`
   - Nombre del estado o provincia: `Barcelona`
   - Nombre de la localidad: `Castelldefels`
   - Nombre de la organización: `UPC`
   - Nombre de la unidad organizativa: `DAC`
   - Nombre común: `localhost`
   - Dirección de correo electrónico: (dejar vacío)

## 4. Ejecución

### Paso 1: Iniciar Mission Planner
1. Abrir **Mission Planner**
2. Conectar tu dron real o iniciar simulación SITL:
   - Para simulación: Ir a `Simulation` → `SITL` → Seleccionar vehículo → `Start`
   - Para dron real: Configurar puerto COM y conectar
3. Verificar que la telemetría esté funcionando correctamente

### Paso 2: Ejecutar la Aplicación Web
1. En la carpeta del proyecto, ejecutar **`run.bat`** haciendo doble clic
2. El script iniciará automáticamente:
   - ✅ Servidor Flask (WebApp)
   - ✅ Estación de Tierra (conexión con el dron)
3. Esperar a que aparezcan mensajes indicando que los servidores están corriendo

### Paso 3: Acceder a la Interfaz Web
1. Una vez ejecutado `run.bat`, en la ventana de consola aparecerá:
   - ✅ El **enlace directo** a la aplicación web
   - ✅ Un **código QR** para acceder desde dispositivos móviles

## 5. Recursos Adicionales

### Videos Tutorial
- Video tutorial disponible en: [https://www.youtube.com/watch?v=iixXgZBE0gM&ab_channel=DronsEETAC](https://www.youtube.com/watch?v=C7m6DbcpqIo)
- Video explicación del código disponible en: https://www.youtube.com/watch?v=3-QpJUCHGdY&ab_channel=DronsEETAC

---

**Última actualización**: Diciembre 2025
