# Update V5

## Resumen

Esta versión implementa el **Modo Piloto** como nueva funcionalidad principal del sistema, permitiendo el control manual del dron en tiempo real mediante joysticks virtuales y comandos RC (Radio Control). Se desarrolla una interfaz dedicada (`piloto.html`) con transmisión continua de vídeo, telemetría en tiempo real, y minimapa con rotación dinámica según la orientación del dron.

Adicionalmente, se rediseña la interfaz de control principal (`control.html`) con un layout optimizado para dispositivos táctiles, mejorando la organización de funcionalidades y la retroalimentación visual de las acciones del usuario.

### Objetivos Principales
- Implementar control manual del dron mediante comandos RC en tiempo real
- Desarrollar interfaz piloto con joysticks virtuales para dispositivos táctiles
- Establecer sistema de telemetría continua en modo piloto
- Optimizar interfaz de control con layout responsive y organizado
- Mejorar feedback visual inmediato en botones de acción críticos

---

## 1. Implementación del Modo Piloto

### 1.1. Control RC Continuo

#### Implementación del Loop RC en EstacionDeTierra.py

El control RC se implementa mediante un loop continuo que envía comandos ada 50ms:

```python
# EstacionDeTierra.py (líneas ~1687-1715)

def pilot_rc_loop():
    """Loop continuo que envía comandos RC al dron mientras está en modo piloto"""
    global pilot_mode_active, pilot_rc_values, last_rc_command_time
    
    while pilot_mode_active and dron.state == "flying":
        # Si no hemos recibido comandos en los últimos 0.3 segundos, resetear a 0
        if last_rc_command_time is not None:
            time_since_last_command = time.time() - last_rc_command_time
            if time_since_last_command > 0.3:
                # No hay comandos recientes - resetear a posición neutra
                pilot_rc_values['throttle'] = 0
                pilot_rc_values['yaw'] = 0
                pilot_rc_values['pitch'] = 0
                pilot_rc_values['roll'] = 0
        
        # Convertir de [-1, 1] a [1100, 1900]
        def normalize_to_pwm(value):
            return int(1500 + (value * 400))
        
        throttle_pwm = normalize_to_pwm(pilot_rc_values['throttle'])
        yaw_pwm = normalize_to_pwm(pilot_rc_values['yaw'])
        pitch_pwm = normalize_to_pwm(pilot_rc_values['pitch'])
        roll_pwm = normalize_to_pwm(pilot_rc_values['roll'])
        
        # Enviar comandos RC al dron
        dron.send_rc(pitch=pitch_pwm, roll=roll_pwm, throttle=throttle_pwm, yaw=yaw_pwm)
        
        # Esperar 0.05 segundos (20 Hz)
        time.sleep(0.05)
```

**Características del loop:**
- **Frecuencia**: 20 Hz (50ms entre comandos)
- **Thread independiente**: No bloquea la recepción de telemetría
- **Timeout de seguridad**: Resetea a valores neutros si no recibe comandos en 300ms
- **Rango de valores**: [-1, 1] convertido a PWM [1100, 1900]
- **Valor neutro**: 0 (equivale a 1500 PWM)

#### Handler de Comandos RC desde WebApp

```python
# EstacionDeTierra.py (líneas ~1717-1735)

@sio.on("pilot_rc")
def handle_pilot_rc(data):
    """Handler para datos de joystick del modo piloto: [throttle, yaw, pitch, roll]"""
    global webapp_commands_enabled, pilot_rc_values, last_rc_command_time
    
    if not webapp_commands_enabled:
        return
    
    # data es un array: [throttle, yaw, pitch, roll] con valores de -1 a 1
    # Actualizar valores globales (el loop continuo los usará)
    if dron.state == "flying":
        # Intercambiar pitch y roll directamente al desempaquetar
        throttle, yaw, roll, pitch = data
        pilot_rc_values['throttle'] = throttle
        pilot_rc_values['yaw'] = yaw
        pilot_rc_values['pitch'] = pitch
        pilot_rc_values['roll'] = roll
        
        # Actualizar timestamp del último comando
        last_rc_command_time = time.time()
```

**Funcionamiento:**
- El handler actualiza los valores RC en memoria (diccionario `pilot_rc_values`)
- El loop RC lee estos valores cada 100ms de forma independiente
- Arquitectura desacoplada: recepción de comandos independiente del envío
- Recibe array con 4 valores: `[throttle, yaw, pitch, roll]` normalizados [-1, 1]
- Actualiza `last_rc_command_time` para el mecanismo de timeout de seguridad

### 1.2. Interfaz piloto.html

#### A. Clase VirtualJoystick

La clase `VirtualJoystick` implementa un joystick virtual táctil que funciona tanto en dispositivos móviles como en desktop:

```javascript
// piloto.html (líneas ~517-633)

class VirtualJoystick {
    constructor(joystickElement, stickElement, onMove) {
        this.joystick = joystickElement;      // Área circular externa (contenedor)
        this.stick = stickElement;            // Círculo interno móvil
        this.onMove = onMove;                 // Callback al mover el joystick
        this.touchId = null;                  // ID único del touch para multitouch
        this.maxDistance = 35;                // Distancia máxima en píxeles
        
        // Eventos touch para dispositivos móviles
        this.joystick.addEventListener('touchstart', this.handleTouchStart.bind(this));
        this.joystick.addEventListener('touchmove', this.handleTouchMove.bind(this));
        this.joystick.addEventListener('touchend', this.handleTouchEnd.bind(this));
        this.joystick.addEventListener('touchcancel', this.handleTouchEnd.bind(this));
    }
    
    updatePosition(clientX, clientY) {
        // Calcular desplazamiento desde el centro
        let dx = clientX - this.centerX;
        let dy = clientY - this.centerY;
        
        // Limitar a maxDistance (35px)
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance > this.maxDistance) {
            const angle = Math.atan2(dy, dx);
            dx = Math.cos(angle) * this.maxDistance;
            dy = Math.sin(angle) * this.maxDistance;
        }
        
        // Mover el stick visualmente
        this.stick.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
        
        // Normalizar a rango [-1, 1]
        const normalizedX = dx / this.maxDistance;
        const normalizedY = -dy / this.maxDistance;  // Invertir Y (arriba = positivo)
        
        // Llamar callback con valores normalizados
        if (this.onMove) {
            this.onMove(normalizedX, normalizedY);
        }
    }
    
    resetPosition() {
        // Volver al centro con animación
        this.stick.style.transition = 'transform 0.2s';
        this.stick.style.transform = 'translate(-50%, -50%)';
        
        // Llamar callback con valores en 0 (posición neutra)
        if (this.onMove) {
            this.onMove(0, 0);
        }
    }
}
```

**Características principales:**

| Característica | Descripción |
|----------------|-------------|
| **Soporte Multitouch** | Usa `touch.identifier` para distinguir entre múltiples toques simultáneos |
| **Solo Táctil** | Diseñado exclusivamente para dispositivos móviles y tablets |
| **Normalización** | Convierte píxeles a rango [-1, 1] para envío al dron |
| **Límite circular** | Restringe movimiento a `maxDistance` (35px) del centro |
| **Callback en tiempo real** | Llama `onMove(x, y)` en cada frame de movimiento |
| **Reset automático** | Vuelve al centro (0, 0) al soltar con animación suave |

**Gestión de Multitouch:**

```javascript
handleTouchStart(e) {
    // Solo capturar el primer touch que toca ESTE joystick
    if (this.touchId === null && e.changedTouches.length > 0) {
        const touch = e.changedTouches[0];
        this.touchId = touch.identifier;  // Guardar ID único
        // ... calcular centro
    }
}

handleTouchMove(e) {
    // Buscar el touch que corresponde a ESTE joystick
    for (let i = 0; i < e.touches.length; i++) {
        const touch = e.touches[i];
        if (touch.identifier === this.touchId) {  // Filtrar por ID
            this.updatePosition(touch.clientX, touch.clientY);
            break;
        }
    }
}
```

**Flujo de datos:**

```
Usuario mueve joystick
    ↓
updatePosition() calcula dx, dy en píxeles
    ↓
Normaliza a [-1, 1]: normalizedX, normalizedY
    ↓
Llama callback: onMove(normalizedX, normalizedY)
    ↓
Actualiza joystickState.throttle / yaw / pitch / roll
    ↓
sendJoystickData() envía via Socket.IO a 20 Hz
```

#### B. Instancias de Joysticks

**Joystick Izquierdo (Throttle + Yaw)**

```javascript
// piloto.html (líneas ~638-676)

const leftJoystick = new VirtualJoystick(
    document.getElementById('left-joystick'),
    document.getElementById('left-stick'),
    (x, y) => {
        joystickState.yaw = x;
        joystickState.throttle = y;
        document.getElementById('yaw-value').textContent = x.toFixed(2);
        document.getElementById('throttle-value').textContent = y.toFixed(2);
        sendJoystickData();
    }
);

// Enviar datos de joystick
let lastSendTime = 0;
function sendJoystickData() {
    const now = Date.now();
    if (now - lastSendTime < 50) return;  // Throttling a 20 Hz
    lastSendTime = now;

    socket.emit('pilot_rc', [
        joystickState.throttle,  // -1 a 1
        joystickState.yaw,       // -1 a 1
        joystickState.pitch,     // -1 a 1
        joystickState.roll       // -1 a 1
    ]);
}
```

**Mapeo de controles:**

| Movimiento Joystick | Variable | Valor | Efecto |
|---------------------|----------|-------|--------|
| Centro | Throttle | 0 | Mantener altitud (1500 PWM) |
| Arriba (máximo) | Throttle | 1 | Ascender al máximo (1900 PWM) |
| Abajo (máximo) | Throttle | -1 | Descender al máximo (1100 PWM) |
| Izquierda (máximo) | Yaw | -1 | Rotar antihorario (1100 PWM) |
| Derecha (máximo) | Yaw | 1 | Rotar horario (1900 PWM) |

**Joystick Derecho (Pitch + Roll)**

Similar al joystick de throttle/yaw, controla el movimiento horizontal del dron:

```javascript
const rightJoystick = new VirtualJoystick(
    document.getElementById('right-joystick'),
    document.getElementById('right-stick'),
    (x, y) => {
        joystickState.roll = x;   
        joystickState.pitch = -y;  // Invertido para control intuitivo
        document.getElementById('roll-value').textContent = x.toFixed(2);
        document.getElementById('pitch-value').textContent = (-y).toFixed(2);
        sendJoystickData();
    }
);
```

| Movimiento Joystick | Variable | Valor | Efecto |
|---------------------|----------|-------|--------|
| Centro | Pitch/Roll | 0 | Hover (1500 PWM) |
| Arriba | Pitch | 1 | Avanzar (1900 PWM) |
| Abajo | Pitch | -1 | Retroceder (1100 PWM) |
| Izquierda | Roll | -1 | Desplazar izquierda (1100 PWM) |
| Derecha | Roll | 1 | Desplazar derecha (1900 PWM) |

**C. Minimapa con Rotación Dinámica**

El minimapa rota dinámicamente según el heading del dron para mantener la perspectiva del piloto:

```javascript
// piloto.html (líneas ~760-780)

socket.on('telemetry_info', (data) => {
    if (data.heading !== undefined) {
        // Rotar el contenedor del mapa (negativo para compensar)
        const mapContainer = document.getElementById('minimap');
        mapContainer.style.transform = `rotate(${-data.heading}deg)`;
        
        // La flecha mantiene su orientación real (heading del dron)
        // y rota junto con el mapa
        if (directionArrow) {
            directionArrow.setLatLng(newPos);
            
            var DirectionArrow = L.Icon.extend({
                options: {
                    iconSize: [100, 100],
                    iconAnchor: [50, 50]
                }
            });
            
            // La flecha muestra el heading real del dron
            directionArrow.setIcon(new DirectionArrow({
                iconUrl: 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(createArrowSVG(data.heading))
            }));
        }
    }
});
```

---

## 2. Mejoras en control.html

### 2.1. Rediseño de Layout

Se reorganiza la interfaz con una distribución optimizada para dispositivos táctiles:

**Distribución de elementos:**

| Elemento | Posición | Justificación |
|----------|----------|---------------|
| **Telemetría** | Superior izquierda | Información siempre visible, formato vertical compacto |
| **Controles Principales** | Superior centro | Acciones frecuentes de fácil acceso |
| **Dropdown Funcionalidades** | Superior derecha | Funciones secundarias agrupadas |
| **Dropdown Modos** | Inferior derecha (sobre botón seguir) | Cambio de modo de operación |
| **Botón Seguir Dron** | Inferior derecha | Acción rápida de navegación |
| **Grid Navegación** | Inferior izquierda | Control direccional agrupado |

### 2.2. Sistema de Dropdowns

Se implementan dos menús desplegables para organizar funcionalidades:

**Dropdown "Funcionalidades":**
- Crear Ruta
- Cámara Dron
- Hacer Foto
- Hacer Video
- Cámara Móvil
- Ocultar Navegación

**Dropdown "Modos":**
- Modo Piloto (funcional)

**Características técnicas:**
- Menús desplegables con cierre automático al hacer click fuera
- Solo un dropdown abierto a la vez (comportamiento exclusivo)
- Animaciones diferenciadas: `slideDown` (funcionalidades) y `slideUp` (modos)
- Borde redondeado conectado con el botón cuando está activo

```javascript
// control.html

function toggleDropdown(menuId) {
    const dropdown = document.getElementById(menuId);
    
    // Cerrar otros dropdowns
    document.querySelectorAll('.dropdown-menu').forEach(d => {
        if (d.id !== menuId) d.classList.remove('show');
    });
    
    // Toggle del dropdown actual
    dropdown.classList.toggle('show');
    dropdown.previousElementSibling.classList.toggle('active');
}
```

### 2.3. Botón de Seguimiento Estilo Google Maps

Se implementa un botón circular con icono SVG que replica el comportamiento de Google Maps:

**Estados del botón:**
- **Inactivo**: Fondo blanco, icono gris → Mapa estático
- **Activo**: Fondo verde (#4CAF50), icono blanco → Mapa sigue al dron automáticamente

```javascript
function toggleFollowDrone() {
    const followButton = document.getElementById('followButton');
    followDrone = !followDrone;
    
    if (followDrone) {
        followButton.classList.add('active');
        map.setView(currentPos, map.getZoom());
    } else {
        followButton.classList.remove('active');
    }
}
```

### 2.4. Mejoras Adicionales

- **Telemetría vertical**: Formato compacto con bullets verdes (`•`) para mejor legibilidad
- **Grid de navegación mejorado**: Botones 3x3 con hover effects y sombras
- **Backdrop filter**: Efecto de cristal esmerilado (`blur(10px)`) en todos los contenedores
- **Botones más pequeños**: Reducción de tamaño para maximizar área del mapa visible

---

## 3. Comparación V4 vs V5

### Funcionalidades Nuevas

| Característica | V4 | V5 |
|---------------|----|----|
| **Modo Piloto** | No existe | Implementado completo con RC loop |
| **Joysticks Virtuales** | No | Sí (touch-enabled, 2 joysticks) |
| **Transmisión Video Piloto** | Solo en control.html | También en piloto.html |
| **Minimapa Dinámico** | Estático | Rotación según heading del dron |
| **Feedback Botones** | Con race condition | Inmediato con flags de estado |
| **Layout control.html** | Vertical apilado | Responsive con dropdowns temáticos |
| **Telemetría Piloto** | N/A | 20 Hz en tiempo real |
| **Botón Seguir Dron** | Rectangular con texto | Circular con SVG |

### Cambios Técnicos

**Archivos Modificados:**

1. **EstacionDeTierra.py** (~200 líneas modificadas/añadidas):
   - Nuevo: `pilot_rc_loop()` con envío continuo a 20 Hz
   - Nuevo: Handler `@sio.on("pilot_rc")` 
   - Nuevo: Handler `@sio.on("pilot_action")`
   - Nuevo: Variables globales `pilot_mode_active`, `pilot_rc_values`, `last_rc_command_time`
   - Modificado: Sistema de parada del RC loop con timeout de seguridad

2. **piloto.html** (archivo nuevo, ~918 líneas):
   - Interfaz completa de modo piloto
   - Dos joysticks virtuales con mapeo RC (valores normalizados -1 a 1)
   - Minimapa con rotación dinámica
   - Sistema de feedback visual con flags de estado
   - Transmisión de vídeo en tiempo real

3. **control.html** (~450 líneas modificadas):
   - Rediseño completo de layout
   - Sistema de dropdowns temáticos
   - Botón circular de seguimiento
   - Grid de navegación mejorado

4. **run.py** (~40 líneas añadidas):
   - Nuevo handler: `@socketio.on('pilot_rc')` para comandos RC
   - Nuevo handler: `@socketio.on('pilot_action')` para acciones de piloto
   - Nueva ruta: `/piloto` que sirve `piloto.html`


### Mejoras de UX

| Aspecto | Mejora | 
|---------|--------|----------------------|
| **Control Manual** | Joysticks táctiles | 
| **Organización** | Dropdowns temáticos | 
| **Espacio en Pantalla** | Layout optimizado | 
| **Feedback Visual** | Sin race conditions |
| **Orientación** | Mapa rotado |

---

**Versión**: V5  
**Fecha**: 22 Octubre 2025  
**Cambios Principales**: Implementación completa de Modo Piloto con control RC y un rediseño de la interfaz 
