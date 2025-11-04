# Update V7

## Resumen

Transformación completa de la interfaz de usuario con mejoras visuales y funcionales en ambos modos (Control y Piloto), diseño responsive diferenciado para móvil y desktop, sistema unificado de modales, panel de ajustes de parámetros del dron y control total por gamepad USB.

### Objetivos Principales
- Implementar modo pantalla completa en ambos modos
- Desarrollar un diseño adaptado para móviles y ordenadores
- Crear sistema unificado de modales
- Implementar un panel de ajustes del dron con persistencia
- Desarrollar control completo en piloto.html mediante un mando USB
- Mejorar visualmente contol.html

---

## 1. Modo Pantalla Completa

### 1.1. Implementación

Botón con icono SVG dinámico en `control.html` y `piloto.html`:

```html
<button class="fullscreen-btn" id="fullscreenBtn" onclick="toggleFullscreen()">
    <svg id="fullscreenIcon" viewBox="0 0 24 24">
        <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5z..."/>
    </svg>
</button>
```

### 1.2. Lógica JavaScript

Soporte multi-navegador:

```javascript
function toggleFullscreen() {
    if (!isFullscreen) {
        const elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) { // Safari
            elem.webkitRequestFullscreen();
        } else if (elem.msRequestFullscreen) { // IE11
            elem.msRequestFullscreen();
        }
    } else {
        // Salir de fullscreen con APIs correspondientes
    }
}

// Detectar cambios y actualizar icono
document.addEventListener('fullscreenchange', handleFullscreenChange);
document.addEventListener('webkitfullscreenchange', handleFullscreenChange);

function handleFullscreenChange() {
    isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
    document.body.classList.toggle('is-fullscreen', isFullscreen);
    // Cambiar SVG path según estado
}
```

**Compatibilidad:** Chrome, Firefox, Safari, Edge, IE11

---

## 2. Diseño Responsive Diferenciado

### 2.1. Estrategia de Media Queries

El diseño **desktop es el estilo por defecto** (no requiere media query). El media query se usa solo para **móvil**:

```css
/* Desktop (>1024px): Estilos por defecto */
/* No requiere media query */

/* Móvil (<1024px): Ajustes específicos para pantallas pequeñas */
@media (max-width: 1024px) {
    /* Ocultar elementos desktop, ajustar layout */
}
```

### 2.2. Diferencias por Archivo

#### control.html

| Elemento | Desktop (por defecto) | Móvil (táctil) |
|----------|-------------------|-----------------|
| **Cruceta** | ✅ Visible | ❌ Oculta |
| **Joystick** | ❌ Oculto | ✅ Visible |

**CSS del joystick (oculto por defecto en desktop):**

```css
/* Joystick base - oculto por defecto */
.joystick-container {
    position: fixed;
    bottom: 70px;
    left: 80px;
    width: 120px;
    height: 120px;
    display: none;  /* Oculto por defecto */
    z-index: 501;
}

/* Ocultar joystick completamente en dispositivos no táctiles */
.joystick-area.non-touch-hidden {
    display: none !important;
}
```

**JavaScript - Detección y control:**

```javascript
function setupDeviceSpecificUI() {
    const joystickArea = document.getElementById('joystick-area');
    
    if (IS_TOUCH_DEVICE) {
        // Dispositivo táctil: mostrar joystick, ocultar cruceta
        joystickArea.classList.remove('non-touch-hidden');
        navegacion.classList.add('touch-hidden');
    } else {
        // Desktop (no táctil): ocultar joystick, mostrar cruceta
        joystickArea.classList.add('non-touch-hidden');
        navegacion.classList.remove('touch-hidden');
    }
}
```

#### piloto.html

| Elemento | Desktop (por defecto) | Móvil (`@media max-width: 1024px`) |
|----------|-------------------|-----------------|
| **Gamepad Mapping** | ✅ Visible | ❌ Oculta (`display: none`) |


```css
/* Móvil: ocultar gamepad y ajustar panel */
@media (max-width: 1024px) {
    #gamepad-mapping-section { 
        display: none; 
    }
}
```

### 2.3. Detección JavaScript

```javascript
function isDesktop() {
    return !(/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent));
}

// Uso condicional
if (isDesktop()) {
    showGamepadModal();  // Solo desktop
}
```

---

## 3. Sistema de Modales Unificado

### 3.1. Diseño Consistente

Estructura común para todos los modales:

```html
<div id="modal" class="modal-camara">
    <div class="modal-content-camara">
        <div class="modal-header-camara">
            <h3>📹 Título</h3>
            <button class="close-modal-btn" onclick="cerrar()">×</button>
        </div>
        <div class="modal-body-camara">
            <!-- Contenido -->
        </div>
        <div class="modal-footer-camara">
            <!-- Botones de acción -->
        </div>
    </div>
</div>
```

**Características visuales:**
- `backdrop-filter: blur(8px)` para fondo difuminado
- Gradientes purple-blue en headers: `linear-gradient(135deg, #667eea, #764ba2)`
- Animaciones: `fadeIn` (0.3s) + `slideIn`
- Botón X con hover rotación 90°

### 3.2. Modales Implementados

| Modal | Archivo | Propósito |
|-------|---------|-----------|
| **Cámara Dron** | control.html | Stream + captura foto/video |
| **Cámara Móvil** | control.html | Stream desde móvil |
| **Foto Capturada** | piloto.html | Preview de foto con gamepad |
| **Video Grabado** | piloto.html | Reproductor de video |
| **Instrucciones Gamepad** | piloto.html | Imagen de controles |

### 3.3. Gestión Socket.IO

```javascript
// Iniciar cámara móvil
function abrirVentanaCamara() {
    socket.emit('iniciar_camara_movil');
    camaraMovilButtonsContainer.classList.add('show');
}

// Recibir foto capturada
socket.on('foto_capturada', function(nombreFoto) {
    mostrarFotoCapturada(nombreFoto);
});

// Recibir video grabado
socket.on('video_detenido', function(nombreVideo) {
    mostrarVideoGrabado(nombreVideo);
    isRecording = false;
});
```

### 3.4. Modal Instrucciones Gamepad

```javascript
function updateGamepadTelemetry(connected) {
    if (connected) {
        statusElement.textContent = 'Conectado';
        statusElement.style.color = '#4CAF50';
        
        if (!gamepadInstructionsShown && isDesktop()) {
            showGamepadModal();  // Auto-show primera vez
        }
    }
}
```

---

## 4. Panel de Ajustes del Dron (piloto.html)

### 4.1. Parámetros Configurables

Panel lateral deslizable con **8 sliders** para configurar parámetros del dron y video:

#### Parámetros de Vuelo (6 sliders)

| Parámetro | ID ArduPilot | Rango | Step | Default | Descripción |
|-----------|--------------|-------|------|---------|-------------|
| **Velocidad Subida** | `PILOT_SPEED_UP` | 50-300 cm/s | 10 | 250 | Velocidad máxima ascenso vertical |
| **Velocidad Bajada** | `PILOT_SPEED_DN` | 50-300 cm/s | 10 | 150 | Velocidad máxima descenso vertical |
| **Velocidad Horizontal** | `LOIT_SPEED` | 50-2500 cm/s | 50 | 1250 | Velocidad máxima desplazamiento horizontal |
| **Velocidad Rotación** | `ATC_RATE_Y_MAX` | 10-180 °/s | 5 | 90 | Velocidad máxima rotación (yaw) |
| **Aceleración Vertical** | `PILOT_ACCEL_Z` | 100-500 cm/s² | 10 | 250 | Aceleración máxima vertical |
| **Aceleración Horizontal** | `LOIT_ACC_MAX` | 250-1000 cm/s² | 25 | 500 | Aceleración máxima horizontal |

#### Parámetros de Video (2 sliders)

| Parámetro | Rango | Step | Default | Descripción |
|-----------|-------|------|---------|-------------|
| **Calidad Video** | 0-100% | **5** | 50 | Compresión JPEG (↑ calidad = ↑ ancho banda) |
| **Frames por Segundo** | 1-30 fps | 1 | 5 | Fluidez video (↑ fps = ↑ suave, ↑ datos) |


### 4.2. Gestión con localStorage

#### Estructura de Datos

```javascript
// Valores por defecto
const defaultSettings = {
    speedUp: 250,       // PILOT_SPEED_UP (cm/s)
    speedDn: 150,       // PILOT_SPEED_DN (cm/s)
    loitSpeed: 1250,    // LOIT_SPEED (cm/s)
    yawRate: 90,        // ATC_RATE_Y_MAX (deg/s)
    accelZ: 250,        // PILOT_ACCEL_Z (cm/s²)
    loitAcc: 500,       // LOIT_ACC_MAX (cm/s²)
    videoQuality: 50,   // Calidad video (0-100%)
    videoFps: 5         // Frames por segundo (1-30)
};

// Estado actual (copia de defaults al inicio)
let currentSettings = {...defaultSettings};
```

**Clave localStorage:** `'pilotSettings'` (JSON stringificado)

#### Funciones Principales

**1. Cargar ajustes guardados:**
```javascript
function loadSettings() {
    // Recuperar desde localStorage
    const saved = localStorage.getItem('pilotSettings');
    if (saved) {
        currentSettings = JSON.parse(saved);
    }
    
    // Actualizar UI (sliders y valores)
    for (let key in currentSettings) {
        document.getElementById(key + 'Slider').value = currentSettings[key];
        document.getElementById(key + 'Value').textContent = currentSettings[key];
    }
}
```

**2. Actualizar en tiempo real (al mover slider):**
```javascript
function updateSliderValue(setting, value) {
    // Actualizar valor mostrado
    document.getElementById(setting + 'Value').textContent = value;
    // Actualizar objeto (NO guarda en localStorage aún)
    currentSettings[setting] = parseFloat(value);
}
```

**3. Aplicar y guardar (botón "✓ Aplicar"):**
```javascript
function applySettings() {
    // 1. Preparar parámetros del dron
    const params = [
        {ID: 'PILOT_SPEED_UP', Value: currentSettings.speedUp},
        {ID: 'PILOT_SPEED_DN', Value: currentSettings.speedDn},
        {ID: 'LOIT_SPEED', Value: currentSettings.loitSpeed},
        {ID: 'ATC_RATE_Y_MAX', Value: currentSettings.yawRate},
        {ID: 'PILOT_ACCEL_Z', Value: currentSettings.accelZ},
        {ID: 'LOIT_ACC_MAX', Value: currentSettings.loitAcc}
    ];
    
    // 2. GUARDAR en localStorage (sobrescribe datos anteriores)
    localStorage.setItem('pilotSettings', JSON.stringify(currentSettings));
    
    // 3. Enviar parámetros dron → Socket.IO → EstacionDeTierra.py → MAVLink
    socket.emit('set_parameters', params);
    
    // 4. Enviar configuración video por separado
    socket.emit('video_settings', {
        quality: currentSettings.videoQuality,
        fps: currentSettings.videoFps
    });
    
    // 5. Feedback visual (botón verde "✓ ¡Aplicado!")
    // 6. Cerrar panel tras 1.5s
}
```

**4. Restaurar valores por defecto (botón "🔄 Restaurar"):**
```javascript
function resetSettings() {
    if (confirm('¿Restaurar todos los ajustes...?')) {
        // Restaurar parámetros
        currentSettings = {...defaultSettings};
        
        // Actualizar UI
        for (let key in currentSettings) {
            document.getElementById(key + 'Slider').value = currentSettings[key];
            document.getElementById(key + 'Value').textContent = currentSettings[key];
        }
        
        // Restaurar mapeo de botones gamepad
        buttonMapping = { takeoff: 9, land: 1, rtl: 0, photo: 2, video: 3 };
        saveButtonMapping();
    }
}
```

#### ¿Por qué NO se llena localStorage?

**localStorage NO acumula datos** porque:
1. Solo usa **2 claves fijas**: `'pilotSettings'` y `'piloto_button_mapping'`
2. Cada `setItem()` **SOBRESCRIBE** el valor anterior (no añade)

```javascript
// Ejecución 1:
localStorage.setItem('pilotSettings', '{"speedUp":250,...}'); 

// Ejecución 2 (REEMPLAZA, no añade):
localStorage.setItem('pilotSettings', '{"speedUp":300,...}'); 
```

### 4.3. Control con Gamepad

#### Navegación por el Panel

Cuando el panel está abierto y hay gamepad conectado:

```javascript
function initSettingsNavigation() {
    if (!isDesktop()) return;  // Solo desktop
    
    settingsNavigationActive = true;
    settingsItems = [];  // Array con elementos navegables
    
    // Añadir 8 sliders
    document.querySelectorAll('.setting-item:not(.button-mapping-item)').forEach(item => {
        const slider = item.querySelector('.setting-slider');
        settingsItems.push({ type: 'slider', element: item, slider, setting: ... });
    });
    
    // Añadir 5 botones de remapeo (si gamepad conectado)
    if (gamepadConnected) {
        document.querySelectorAll('.button-mapping-item').forEach(item => {
            settingsItems.push({ type: 'remap', element: item, ... });
        });
    }
    
    highlightSettingItem(0);  // Resaltar primer elemento
}
```

#### Controles con Joystick

| Acción | Control | Parámetro |
|--------|---------|-----------|
| **Navegar arriba/abajo** | Joystick izquierdo vertical | Cooldown: 200ms |
| **Ajustar slider izquierda/derecha** | Joystick izquierdo horizontal | Cooldown: 50ms (continuo) |
| **Activar remapeo** | Botón 3 (botón 2) | Solo en botones remapeo |
| **Aplicar ajustes** | Botón Start (botón 9) | Guarda y cierra panel |
| **Cerrar panel** | Botón Select (botón 8) | Sin guardar cambios |

```javascript
// En el loop del gamepad:
if (settingsNavigationActive) {
    // Navegación vertical (entre elementos)
    if (Math.abs(joystickState.throttle) > 0.5) {
        if (joystickState.throttle > 0.5) navigateSettings('up');
        else navigateSettings('down');
    }
    
    // Ajuste horizontal (valor del slider actual)
    if (Math.abs(joystickState.yaw) > 0.5) {
        if (joystickState.yaw < -0.5) adjustCurrentSliderContinuous('left');
        else adjustCurrentSliderContinuous('right');
    }
}
```

#### Feedback Visual

Elemento seleccionado con gamepad:

```css
.gamepad-selected {
    background: linear-gradient(135deg, rgba(103, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
    border: 2px solid rgba(103, 126, 234, 0.6);
    box-shadow: 0 0 20px rgba(103, 126, 234, 0.4);
    transform: scale(1.02);
}
```

**Total elementos navegables:** 13 (8 sliders + 5 botones remapeo)

---

## 5. Mejoras Visuales en Creación de Rutas

### 5.1. Modales de Waypoint (control.html)

**Sistema de modal para configurar waypoints:**
- Modal centrado con backdrop blur
- Opciones de captura: Ninguna (amarillo), Foto (azul), Video (rojo)
- Selector de duración para video (1-60 segundos)
- Gradientes en botones confirmar/cancelar

```html
<div id="waypoint-modal" class="waypoint-modal-overlay">
    <div class="waypoint-modal-content">
        <div class="waypoint-modal-header">
            <div class="waypoint-modal-icon">📍</div>
            <div class="waypoint-modal-title">Waypoint #<span id="waypoint-number">1</span></div>
        </div>
        <div class="waypoint-modal-body">
            <!-- Opciones: ninguna, foto, video -->
            <div class="waypoint-options">
                <button class="waypoint-option-btn ninguna selected">⭕ Ninguna</button>
                <button class="waypoint-option-btn foto">📸 Foto</button>
                <button class="waypoint-option-btn video">🎥 Video</button>
            </div>
        </div>
        <div class="waypoint-modal-buttons">
            <button class="waypoint-modal-button-cancel">Cancelar</button>
            <button class="waypoint-modal-button-confirm">Confirmar</button>
        </div>
    </div>
</div>
```

### 5.2. Markers con SVG Personalizados

Pins de waypoint con números y colores según tipo de captura:

```javascript
function createWaypointPinSVG(number, color) {
    return `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 60">
            <path fill="${color}" d="M20 0C9 0 0 9 0 20c0 15 20 40 20 40s20-25 20-40C40 9 31 0 20 0z"/>
            <circle cx="20" cy="20" r="12" fill="white" opacity="0.9"/>
            <text x="20" y="25" font-size="14" font-weight="bold" text-anchor="middle">${number}</text>
        </svg>
    `;
}

// Colores según tipo
let color = "#FFC107"; // Ninguna (amarillo)
if (selectedCaptureType === "foto") color = "#2196F3"; // Azul
else if (selectedCaptureType === "video") color = "#F44336"; // Rojo
```

### 5.3. Animaciones y Polyline

**Línea de ruta animada:**
```javascript
let rutaPolyline = L.polyline([], { 
    color: '#2196F3',
    weight: 4,
    opacity: 0.8,
    dashArray: '10, 5',  // Línea discontinua
    lineJoin: 'round',
    lineCap: 'round'
}).addTo(map);

// Decorador con flechas
let rutaDecorator = L.polylineDecorator(rutaPolyline, {
    patterns: [{
        offset: 25,
        repeat: 50,
        symbol: L.Symbol.arrowHead({ pixelSize: 12, pathOptions: { color: '#2196F3' } })
    }]
});
```

---

## 6. Sistema de Control con Gamepad

### 6.1. Detección Automática de Ejes

Compatibilidad universal (eje 3 vs 5 para pitch):

```javascript
// Auto-detectar eje pitch
let pitch = gamepad.axes[5] || 0;  // Intentar eje 5 primero (USB)
if (Math.abs(pitch) < 0.05 && gamepad.axes[3] !== undefined) {
    pitch = gamepad.axes[3] || 0;  // Fallback a eje 3 (XBOX)
}

// Aplicar deadzone (10%)
const deadzone = 0.1;
joystickState.pitch = Math.abs(pitch) < deadzone ? 0 : pitch;
```

**Controladores probados:** Xbox 360, USB genérico

### 6.2. Sistema de Remapeo de Botones

#### Mapeo por Defecto

```javascript
let buttonMapping = {
    takeoff: 9,    // Start
    land: 1,       // Botón 2
    rtl: 0,        // Botón 1
    photo: 2,      // Botón 3
    video: 3       // Botón 4
};
```

#### Remapeo Personalizable

```javascript
function startRemapping(action) {
    console.log(`Esperando botón para: ${action}`);
    currentRemappingAction = action;
    
    // Visual feedback
    document.querySelectorAll('.remap-btn').forEach(btn => {
        btn.classList.remove('listening');
    });
    event.target.closest('.remap-btn').classList.add('listening');
}

function completeRemapping(buttonIndex) {
    buttonMapping[currentRemappingAction] = buttonIndex;
    
    // Guardar en localStorage
    localStorage.setItem('piloto_button_mapping', JSON.stringify(buttonMapping));
    
    // Feedback
    console.log(`✅ ${currentRemappingAction} → Botón ${buttonIndex}`);
}
```

**Persistencia:** localStorage con clave `piloto_button_mapping`

### 6.4. Gestión de Estados y Modales

#### Prevención de Acciones Accidentales

```javascript
function handleGamepadButton(buttonIndex) {
    // Si instrucciones nunca se han mostrado, mostrarlas y NO ejecutar acción
    if (!gamepadInstructionsShown) {
        console.log('Primer botón detectado - Mostrando instrucciones');
        showGamepadModal();
        return;  // Salir sin ejecutar acción
    }
    
    // Si modal abierto, cerrarlo
    if (gamepadInstructionsModalOpen) {
        closeGamepadModal();
        return;
    }
    
    // Ejecutar acción normal
    if (buttonMapping.takeoff === buttonIndex) {
        despegar();
    }
    // ...
}
```

### 6.6. Optimizaciones Desktop

Solo en *Desktop*:

```css
.settings-panel {
    width: 500px;  /* Antes: 400px */
}

#gamepad-mapping-section {
    display: block;  /* Visible en desktop */
}

#gamepad-telemetry {
    display: flex;  /* Indicador visible */
}
```

En móvil (`< 1024px`): Gamepad section oculta completamente

---

## 7. Compatibilidad

| Aspecto | Soporte |
|---------|---------|
| **Navegadores** | Chrome, Firefox, Safari, Edge |
| **Dispositivos** | Desktop (>1024px), Tablet (768-1024px), Móvil (<768px) |
| **Gamepads** | Xbox, PlayStation, USB Genérico|
| **APIs** | Fullscreen API, Gamepad API, localStorage, Socket.IO |

---

**Versión**: V7  
**Fecha**: 4 Noviembre 2025
**Cambios Principales**:  
- Modo pantalla completa en ambos modos (multi-navegador)
- Diseño diferenciado móvil (táctil) vs desktop (gamepad)
- Sistema modales unificado
- Panel ajustes dron (8 parámetros) con persistencia localStorage
- Control completo por gamepad USB con remapeo personalizable
- Navegación de ajustes con gamepad (joystick + ajuste continuo)