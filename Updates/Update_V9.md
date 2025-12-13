# Update V9

## Resumen

Desarrollo del **sistema de sincronización profesor-alumno**, creando interfaces separadas que permiten a múltiples estudiantes observar las acciones del profesor en tiempo real sin poder interactuar con el dron. El objetivo principal es proporcionar una experiencia educativa donde el profesor controla el dron y los alumnos visualizan todas sus acciones sincronizadas.

### Objetivos Principales
- **Crear interfaces para alumnos**: `alumno_control.html`, `alumno_piloto.html`, `movimiento.html`
- **Sistema de sincronización en tiempo real**: Cámara, modales, telemetría
- **Arquitectura de rooms**: Broadcast eficiente a múltiples alumnos
- **Modo observador**: Alumnos solo visualizan, sin control del dron
- **Separación de roles**: Profesor (control total) vs Alumno (visualización)

---

## 1. Arquitectura de Roles

### 1.1. Interfaces Diferenciadas

**control.html (Profesor):**
- Control completo del dron
- Todos los botones habilitados
- Emisor de eventos de sincronización

**alumno_control.html / alumno_piloto.html (Alumnos):**
- Visualización sincronizada
- Botones deshabilitados
- Receptores de eventos de sincronización

### 1.2. Sistema de Rooms

**Backend (WebApp/run.py):**
```python
@socketio.on('join_alumno')
def handle_join_alumno():
    """Los alumnos se unen a su sala para recibir sincronización"""
    join_room('alumnos')
    print(f"👨‍🎓 Alumno conectado y unido a sala 'alumnos'")
    
    # Si ya hay información del dispositivo del profesor, enviarla al nuevo alumno
    if professor_device_info['isTouchDevice'] is not None:
        tipo = "TÁCTIL (Joystick)" if professor_device_info['isTouchDevice'] else "NO TÁCTIL (Cruceta)"
        print(f"  └─> Enviando info de dispositivo del profesor: {tipo}")
        payload = {'isTouchDevice': professor_device_info['isTouchDevice']}
        
        # Si hay buttonMapping guardado, enviarlo también
        if 'buttonMapping' in professor_device_info:
            payload['buttonMapping'] = professor_device_info['buttonMapping']
        
        emit('device_info_sync', payload)
```

**Frontend (alumno_control.html):**
```javascript
// Al cargar la página, unirse a la room de alumnos
socket.emit('join_alumno');
console.log('🎓 Alumno conectado, solicitando unión a sala');
```

---

## 2. Sistema de Sincronización Profesor-Alumno

La característica principal de V9: sincronización en tiempo real de todas las acciones del profesor hacia los alumnos.

### 2.1. Sincronización de Cámara del Dron

**Flujo completo:**
1. Profesor abre/cierra cámara
2. Evento viaja al servidor
3. Servidor emite a room 'alumnos'
4. Todos los alumnos reciben y abren/cierran su cámara

**Profesor emite (control.html, líneas 3805 y 3868):**
```javascript
// Al abrir cámara dron
socket.emit('drone_camera_sync', {
    action: 'open'
});

// Al cerrar cámara dron
socket.emit('drone_camera_sync', {
    action: 'close'
});
```

**Servidor redistribuye (WebApp/run.py, línea 264):**
```python
@socketio.on('drone_camera_sync')
def handle_drone_camera_sync(payload):
    """Sincroniza apertura/cierre de la vista de cámara del dron - SOLO A ALUMNOS"""
    try:
        print(f"[SYNC CÁMARA DRON → ALUMNOS] {payload.get('action').upper()}")
        socketio.emit('drone_camera_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en drone_camera_sync: {e}")
```

**Alumno recibe (alumno_control.html, línea 3216):**
```javascript
socket.on('drone_camera_sync', (payload) => {
    const webcamContainer = document.getElementById('webcam-container');
    
    if (payload.action === 'open') {
        console.log('[ALUMNO] 📷 Abriendo vista de cámara del dron');
        if (webcamContainer) {
            webcamContainer.style.display = 'block';
            // Deshabilitar todos los botones del contenedor para el alumno
            const botonesContainer = webcamContainer.querySelectorAll('button');
            botonesContainer.forEach(btn => {
                btn.disabled = true;
                btn.style.opacity = '0.6';
                btn.style.cursor = 'not-allowed';
            });
        }
        
        // Solicitar stream WebRTC
        if (webrtcReceiver) {
            console.log('📡 [WebRTC] Stream solicitado al abrir cámara');
            webrtcReceiver.requestStream();
        }
    } else if (payload.action === 'close') {
        console.log('[ALUMNO] 📷 Cerrando vista de cámara del dron');
        
        // Resetear receptor WebRTC
        if (webrtcReceiver) {
            webrtcReceiver.reset();
        }
        
        if (webcamContainer) {
            webcamContainer.style.display = 'none';
        }
    }
});
```

### 2.2. Sincronización de Cámara Móvil del Profesor

**Backend (WebApp/run.py, línea 255):**
```python
@socketio.on('camera_modal_sync')
def handle_camera_modal_sync(payload):
    """Sincroniza apertura/cierre del modal de cámara móvil del profesor - SOLO A ALUMNOS"""
    try:
        print(f"[SYNC CÁMARA MÓVIL → ALUMNOS] {payload.get('action').upper()}")
        socketio.emit('camera_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en camera_modal_sync: {e}")
```

### 2.3. Sincronización de Fotos Capturadas

**Backend (WebApp/run.py, línea 273):**
```python
@socketio.on('photo_modal_sync')
def handle_photo_modal_sync(payload):
    """Sincroniza visualización de fotos capturadas - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        photo = payload.get('photoName', '')
        if action == 'open':
            print(f"[SYNC FOTO → ALUMNOS] Mostrando: {photo}")
        else:
            print(f"[SYNC FOTO → ALUMNOS] Cerrando modal")
        socketio.emit('photo_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en photo_modal_sync: {e}")
```

### 2.4. Sincronización de Videos

**Backend (WebApp/run.py, línea 286):**
```python
@socketio.on('video_modal_sync')
def handle_video_modal_sync(payload):
    """Sincroniza visualización de videos grabados - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        video = payload.get('videoName', '')
        if action == 'open':
            print(f"[SYNC VIDEO → ALUMNOS] Mostrando: {video}")
        else:
            print(f"[SYNC VIDEO → ALUMNOS] Cerrando modal")
        socketio.emit('video_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en video_modal_sync: {e}")
```

### 2.5. Sistema de Rooms

**Conexión del alumno (WebApp/run.py, línea 196):**
```python
@socketio.on('join_alumno')
def handle_join_alumno():
    """Los alumnos se unen a su sala para recibir sincronización"""
    join_room('alumnos')
    print(f"👨‍🎓 Alumno conectado y unido a sala 'alumnos'")
    
    # Si ya hay información del dispositivo del profesor, enviarla al nuevo alumno
    if professor_device_info['isTouchDevice'] is not None:
        tipo = "TÁCTIL (Joystick)" if professor_device_info['isTouchDevice'] else "NO TÁCTIL (Cruceta)"
        print(f"  └─> Enviando info de dispositivo del profesor: {tipo}")
        payload = {'isTouchDevice': professor_device_info['isTouchDevice']}
        
        # Si hay buttonMapping guardado, enviarlo también
        if 'buttonMapping' in professor_device_info:
            payload['buttonMapping'] = professor_device_info['buttonMapping']
        
        emit('device_info_sync', payload)
```

**Alumno se une al cargar (alumno_control.html):**
```javascript
// Al conectarse, unirse a la room de alumnos
socket.emit('join_alumno');
console.log('🎓 Alumno conectado, solicitando unión a sala');
```

---

## 3. Interfaces de Alumno

### 3.1. alumno_control.html

Copia de `control.html` con **todos los botones deshabilitados**.

**Código de deshabilitación (línea ~3223):**
```javascript
// Deshabilitar todos los botones del contenedor para el alumno
const botonesContainer = webcamContainer.querySelectorAll('button');
botonesContainer.forEach(btn => {
    btn.disabled = true;
    btn.style.opacity = '0.6';
    btn.style.cursor = 'not-allowed';
});
```

### 3.2. alumno_piloto.html

Interfaz de modo piloto para alumnos (solo visualización).

### 3.3. movimiento.html

Interfaz experimental con detección de sensores de orientación.

**Nota:** Implementación básica, no integrada completamente con control RC.

---

## 4. Resumen de Funcionalidades

### 4.1. Lo que SÍ funciona

✅ Sincronización de apertura/cierre de cámara dron  
✅ Sincronización de modales (cámara móvil, fotos, videos)  
✅ Broadcast a múltiples alumnos simultáneos  
✅ Deshabilitación automática de botones en interfaces alumno  
✅ Stream WebRTC sincronizado entre profesor y alumnos  

### 4.2. Limitaciones

⚠️ Sin persistencia de estado al reconectar  
⚠️ Control por movimiento (movimiento.html) no integrado con RC  
⚠️ No hay recuperación automática de estado de cámara al reconectar

---

**Versión**: V9  
**Fecha**: Noviembre 2025  
**Cambios Principales**:  
- **Creación de interfaces para alumnos**: `alumno_control.html`, `alumno_piloto.html`, `movimiento.html`
- **Modo observador**: Los alumnos pueden ver lo que hace el profesor sin interactuar con el dron
- **Sincronización en tiempo real**: Cámara, modales de fotos/videos, telemetría
- **Sistema de rooms**: Arquitectura para broadcast eficiente a múltiples alumnos
- **Separación de roles**: Profesor (control total) vs Alumno (solo visualización)

**Objetivo de la V9**: Permitir que múltiples alumnos observen y aprendan de las acciones del profesor en tiempo real, sin riesgo de interferencia en el control del dron.
 
