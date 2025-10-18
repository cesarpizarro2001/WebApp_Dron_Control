# Update V4

## Resumen

Esta versión implementa una **migración completa de MQTT a Socket.IO** como protocolo único de comunicación entre todos los componentes del sistema. Se elimina la dependencia del broker MQTT externo y se centraliza toda la comunicación en el servidor Flask mediante WebSockets.

### Objetivos Principales
- Migrar completamente de MQTT + Socket.IO a Socket.IO únicamente
- Eliminar dependencias de brokers externos (dronseetac.upc.edu:8883)
- Centralizar toda la comunicación en el servidor Flask
- Implementar sistema de autorización manual para comandos remotos
- Mantener compatibilidad con todas las funcionalidades existentes
- Simplificar la arquitectura del sistema

## Características Principales

### 1. Nueva Arquitectura de Comunicación

#### Antes (MQTT + Socket.IO):
```
Navegador (control.html)
    ├─ MQTT → Broker (dronseetac.upc.edu:8883) ← MQTT ─┐
    └─ Socket.IO → Flask Server (run.py) ← Socket.IO ──┤
                                                         │
                                            Estación Tierra
                                            (EstacionDeTierra.py)
```

**Problemas del sistema anterior:**
- Dependencia de broker MQTT externo
- Credenciales expuestas en el código cliente
- Dos protocolos diferentes de comunicación

#### Ahora (Solo Socket.IO):
```
Navegador (control.html)
    │
    │ Socket.IO (HTTPS puerto 5004)
    │
┌───▼────────────────────┐
│  Servidor Flask        │
│  (run.py)              │
│  - Middleware/Router   │
│  - Broadcasting        │
└───┬────────────────────┘
    │
    │ Socket.IO (include_self=False)
    │
┌───▼────────────────────┐
│  Estación Tierra       │
│  (EstacionDeTierra.py) │
│  - Autorización manual │
│  - Control del dron    │
└────────────────────────┘
```

**Ventajas del nuevo sistema:**
- Sin broker externo: control total del sistema
- Sin credenciales expuestas: mayor seguridad
- Protocolo único: Socket.IO para todo
- Arquitectura simplificada: más fácil de mantener

### 2. Sistema de Autorización Manual

#### Mecanismo de Seguridad webapp_commands_enabled:
```python
# EstacionDeTierra.py

# Variable global de seguridad (línea 47)
webapp_commands_enabled = False

# Función de autorización (líneas 20-29)
def allowExternal():
    global webapp_commands_enabled
    webapp_commands_enabled = True
    print('WebApp AUTORIZADA: Los comandos desde la web serán procesados')
```

#### Handler con Verificación de Autorización:
```python
# EstacionDeTierra.py

# Handler registrado ANTES de conectar (líneas 1556-1568)
@sio.on('ground_station_command')
def handle_ground_station_command(data):
    global webapp_commands_enabled
    
    if not webapp_commands_enabled:
        action = data.get('action', 'desconocido')
        print(f'COMANDO BLOQUEADO: {action}...')
        return
    
    on_command_received(data)
```

| Estado | Comportamiento | Feedback Visual |
|--------|---------------|----------------|
| **No Autorizado** | Comandos bloqueados | Botón violeta "Conectar WebApp" |
| **Autorizado** | Comandos procesados | Botón verde "WebApp autorizada" |

### 3. Migración del Cliente Web (control.html)

#### Eliminación Completa de MQTT:
```javascript
// control.html

// ELIMINADO:
// <script src="https://cdn.jsdelivr.net/npm/mqtt/dist/mqtt.min.js"></script>
// const client = mqtt.connect('wss://dronseetac.upc.edu:8883/mqtt', {...});
// client.publish(...);
// client.on('message', ...);

// NUEVO: Socket.IO únicamente
const socket = io();
console.log("Conectado al servidor via Socket.IO");
```

#### Mappings de Comandos Migrados:

| Comando | MQTT (antes) | Socket.IO (ahora) |
|---------|-------------|-------------------|
| **Conectar** | `client.publish('mobileFlask/.../connect')` | `socket.emit('command', {action: 'connect'})` |
| **Despegar** | `client.publish('mobileFlask/.../arm_takeOff', altura)` | `socket.emit('command', {action: 'arm_takeOff', altura: altura})` |
| **Mover** | `client.publish('mobileFlask/.../go', dir)` | `socket.emit('command', {action: 'go', direction: dir})` |
| **Aterrizar** | `client.publish('mobileFlask/.../Land')` | `socket.emit('command', {action: 'Land'})` |
| **RTL** | `client.publish('mobileFlask/.../RTL')` | `socket.emit('command', {action: 'RTL'})` |
| **Goto** | `client.publish('mobileFlask/.../goto', json)` | `socket.emit('command', {action: 'goto', lat: lat, lng: lng})` |
| **Capturar Foto** | `client.publish('mobileFlask/.../capturarFoto')` | `socket.emit('command', {action: 'capturarFoto'})` |
| **Iniciar Video** | `client.publish('mobileFlask/.../iniciarVideo')` | `socket.emit('command', {action: 'iniciarVideo'})` |
| **Detener Video** | `client.publish('mobileFlask/.../detenerVideo')` | `socket.emit('command', {action: 'detenerVideo'})` |
| **Ruta Waypoints** | `client.publish('mobileFlask/.../waypointRuta', json)` | `socket.emit('command', {action: 'waypointRuta', waypoints: waypoints})` |

#### Eventos Recibidos Migrados:

| Tipo de Evento | MQTT Topic (antes) | Socket.IO Event (ahora) |
|----------------|-------------------|------------------------|
| **Telemetría** | `demoDash/mobileFlask/telemetryInfo` | `telemetry_info` |
| **Error Video** | `demoDash/mobileFlask/videoError` | `video_error` |
| **Nombre Vuelo** | `demoDash/mobileFlask/flightNameSet` | `flight_name_set` |
| **Foto Capturada** | `demoDash/mobileFlask/fotoCapturada` | `foto_capturada` |
| **Video Iniciado** | `demoDash/mobileFlask/videoIniciado` | `video_iniciado` |
| **Video Detenido** | `demoDash/mobileFlask/videoDetenido` | `video_detenido` |

### 4. Servidor Flask como Middleware (run.py)

#### Rol del Servidor:
El servidor Flask actúa como router/middleware centralizado que:
1. Recibe comandos del navegador → Reenvía a Estación de Tierra
2. Recibe telemetría de Estación → Reenvía a navegador
3. Recibe eventos de Estación → Distribuye a todos los clientes

#### Handlers Implementados:

```python
# run.py

# Handler para comandos de la WebApp (líneas 112-117)
@socketio.on('command')
def handle_command(data):
    action = data.get('action')
    print(f"Comando recibido de WebApp: {action}")
    socketio.emit('ground_station_command', data, include_self=False)

# Handler para telemetría de Estación (líneas 120-123)
@socketio.on('telemetry_data')
def handle_telemetry(data):
    socketio.emit('telemetry_info', data, include_self=False)

# Handler para eventos de vuelo (líneas 126-138)
@socketio.on('flight_event')
def handle_flight_event(data):
    event_type = data.get('event')
    
    if event_type == 'flight_name_set':
        socketio.emit('flight_name_set', data.get('name'), broadcast=True)
    elif event_type == 'foto_capturada':
        socketio.emit('foto_capturada', data.get('filename'), broadcast=True)
    # ... más eventos
```

### 5. Estación de Tierra (EstacionDeTierra.py)

#### Eliminación de MQTT:
```python
# EstacionDeTierra.py

# ELIMINADO:
# import paho.mqtt.client as mqtt
# client = mqtt.Client()
# client.connect(broker_address, broker_port)
# client.publish(...)

# YA EXISTÍA (mantenido):
import socketio
sio = socketio.Client(ssl_verify=False)
```

#### Patrón Crítico: Registro de Handlers ANTES de Conexión:

**INCORRECTO (no funciona en Socket.IO Python):**
```python
# EstacionDeTierra.py

sio.connect('https://localhost:5004')
# Registrar handler DESPUÉS de conectar - NO FUNCIONA
@sio.on('ground_station_command')
def handler(data):
    pass
```

**CORRECTO (implementado en V4):**
```python
# EstacionDeTierra.py

# Registrar handler ANTES de conectar (líneas 1556-1568)
@sio.on('ground_station_command')
def handle_ground_station_command(data):
    if not webapp_commands_enabled:
        return
    on_command_received(data)

# LUEGO conectar (líneas 1598-1601)
def connect_to_socketio_server():
    sio.connect('https://localhost:5004')
```

#### Función procesarTelemetria Migrada:
```python
# EstacionDeTierra.py

# ANTES (MQTT):
def procesarTelemetria(telemetryInfo):
    client.publish('demoDash/mobileFlask/telemetryInfo', json.dumps(telemetryInfo))

# AHORA (Socket.IO):
def procesarTelemetria(telemetryInfo):
    sio.emit('telemetry_data', telemetryInfo)
```

#### Función publish_event Migrada:
```python
# EstacionDeTierra.py

# ANTES (MQTT):
def publish_event(event):
    client.publish('demoDash/mobileFlask/' + event)

# AHORA (Socket.IO):
def publish_event(event):
    sio.emit('flight_event', {'event': event})
```

#### Migración de Eventos de Video/Foto:

| Función | Líneas | Cambio |
|---------|--------|--------|
| **videoWebsockets()** | ~743 | `client.publish('...flightNameSet', ...)` → `sio.emit('flight_event', {'event': 'flight_name_set', ...})` |
| **capturar_foto()** | ~802, 806 | `client.publish('...fotoCapturada', filename)` → `sio.emit('flight_event', {'event': 'foto_capturada', ...})` |
| **start_recording()** | ~842, 846 | `client.publish('...videoIniciado', filename)` → `sio.emit('flight_event', {'event': 'video_iniciado', ...})` |
| **stop_recording()** | ~861 | `client.publish('...videoDetenido')` → `sio.emit('flight_event', {'event': 'video_detenido'})` |

### 6. Flujo de Comunicación Completo

#### Flujo de Comando (WebApp → Dron):
```
1. Usuario hace clic en "Conectar" (control.html)
   ↓
2. socket.emit('command', {action: 'connect'})
   ↓
3. Servidor Flask recibe en handle_command() (run.py)
   ↓
4. socketio.emit('ground_station_command', data, include_self=False)
   ↓
5. Estación recibe en handle_ground_station_command() (EstacionDeTierra.py)
   ↓
6. Verifica webapp_commands_enabled
   ↓
7. Si autorizado: on_command_received(data)
   ↓
8. dron.connect('tcp:127.0.0.1:5763', 115200)
```

#### Flujo de Telemetría (Dron → WebApp):
```
1. dron.send_telemetry_info(procesarTelemetria) (EstacionDeTierra.py)
   ↓
2. procesarTelemetria(telemetryInfo)
   ↓
3. sio.emit('telemetry_data', telemetryInfo)
   ↓
4. Servidor Flask recibe en handle_telemetry() (run.py)
   ↓
5. socketio.emit('telemetry_info', data, include_self=False)
   ↓
6. Navegador recibe en socket.on('telemetry_info', ...) (control.html)
   ↓
7. Actualiza UI: altitud, velocidad, estado, posición en mapa
```

#### Flujo de Eventos (Estación → WebApp):
```
1. Evento de vuelo ocurre (foto capturada, video iniciado, etc.)
   ↓
2. sio.emit('flight_event', {'event': 'foto_capturada', 'filename': ...})
   ↓
3. Servidor Flask recibe en handle_flight_event() (run.py)
   ↓
4. Identifica tipo de evento y reenvía:
   socketio.emit('foto_capturada', data.get('filename'), broadcast=True)
   ↓
5. Navegador recibe en socket.on('foto_capturada', ...) (control.html)
   ↓
6. Muestra notificación al usuario
```

### 7. Configuración SSL/TLS

#### Certificados Autofirmados:
```python
# run.py (líneas 322-333)

import ssl
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('public_certificate.pem', 'private_key.pem')

socketio.run(
    app, 
    host='0.0.0.0', 
    port=5004,
    ssl_context=ssl_context
)
```

#### Cliente Socket.IO:
```python
# EstacionDeTierra.py (línea 1557)

# Deshabilitar verificación SSL para certificados autofirmados
sio = socketio.Client(ssl_verify=False)
```

#### Acceso desde Dispositivos:
- **PC Local:** `https://localhost:5004`
- **Móvil en Red Local:** `https://192.168.1.232:5004` (IP del PC)
- **Producción:** `https://dronseetac.upc.edu:8102`

### 8. Gestión de Logging

#### Principio de Logging Limpio:
Solo registros esenciales para operación en producción.

#### Control.html (navegador):
```javascript
// control.html

// Logs esenciales mantenidos
console.log("Conectado al servidor via Socket.IO");
console.log('Dispositivo táctil detectado:', IS_TOUCH_DEVICE);
```

#### Run.py (servidor):
```python
# run.py

# Solo comandos y eventos críticos
print(f"Comando recibido de WebApp: {action}")
print(f"Evento de vuelo: {event_type}")
```

#### EstacionDeTierra.py (estación):
```python
# EstacionDeTierra.py

# Logs operacionales únicamente
print(f'Comando recibido: {action}')
print('Conectado exitosamente al servidor Socket.IO')
print('WebApp AUTORIZADA: Los comandos desde la web serán procesados')
```

### 9. Manejo de Reconexiones y Errores

#### Reintentos Automáticos:
```python
# EstacionDeTierra.py (líneas 1578-1601)

def connect_to_socketio_server():
    max_retries = 10
    retry_delay = 2  # segundos
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Intentando conectar... (intento {attempt}/{max_retries})")
            sio.connect('https://localhost:5004')
            print("Conectado exitosamente al servidor Socket.IO")
            return True
        except Exception as e:
            if attempt < max_retries:
                print(f"Reintentando en {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"ERROR: No se pudo conectar después de {max_retries} intentos")
                return False
```

#### Manejo de Desconexión del Message Handler:
```python
# EstacionDeTierra.py (líneas 434-437)

def desconectar_con_feedback():
    if hasattr(dron, 'message_handler') and dron.message_handler:
        print('Deteniendo message handler...')
        dron.message_handler.stop()
        dron.message_handler = None
    
    dron.disconnect()
```

## Comparación V3 vs V4

### Funcionalidades Nuevas en V4:

| Característica | V3 | V4 |
|---------------|----|----|
| **Protocolo de Comunicación** | MQTT + Socket.IO | Socket.IO únicamente |
| **Broker Externo** | Requerido (dronseetac.upc.edu) | No 
| **Credenciales Expuestas** | Sí | No |
| **Arquitectura** | 3 componentes + broker | 2 componentes |

### Cambios Técnicos:

#### Archivos Modificados:
- **control.html**: Eliminación completa de MQTT.js, implementación Socket.IO
- **run.py**: Nuevos handlers para comandos, telemetría y eventos
- **EstacionDeTierra.py**: Migración de MQTT a Socket.IO, sistema de autorización

---

**Versión**: V4  
**Fecha**: 18 Octubre 2025  
**Cambios Principales**: Migración completa de MQTT a Socket.IO  
