# Update V3

## Resumen

Esta versión implementa mejoras en la WebApp mediante la **detección del tipo de dispositivo (táctil o no)** para ofrecerle un sistema de control del dron determinado. Para dispositivos táctiles el dron se controla mediante un **Joystick** y para no táctiles se mantiene la cruceta como control principal.

### Objetivos Principales
- Implementar control por joystick virtual para dispositivos móviles y tablets
- Sistema de detección automática de dispositivo (táctil vs no-táctil)
- Seguimiento automático del dron en el mapa
- Interfaz adaptativa que se optimiza según el dispositivo
- Feedback mejorado de estados del dron en tiempo real

## Características Principales

### 1. Sistema de Detección de Dispositivo

El sistema detecta automáticamente si se está ejecutando en un dispositivo táctil o no táctil:

```javascript
function isTouchDevice() {
    return (('ontouchstart' in window) ||
           (navigator.maxTouchPoints > 0) ||
           (navigator.msMaxTouchPoints > 0));
}

const IS_TOUCH_DEVICE = isTouchDevice();
console.log('Dispositivo táctil detectado:', IS_TOUCH_DEVICE);
```

| Tipo de Dispositivo | Interfaz Mostrada 
|---------------------|-------------------|
| **Móvil/Tablet** | Joystick Virtual 
| **PC** | Cruceta Clásica 

### 2. Joystick Virtual Adaptativo

#### Diseño Visual y Funcional:
```css
.joystick-container {
    position: fixed;
    bottom: 100px;
    left: 100px;
    width: 120px;
    height: 120px;
    background: rgba(255, 255, 255, 0.2);
    border: 3px solid rgba(255, 255, 255, 0.4);
    border-radius: 50%;
    z-index: 501;
}

.joystick-knob {
    width: 50px;
    height: 50px;
    background: rgba(66, 165, 245, 0.7);
    border: 2px solid rgba(33, 150, 243, 0.8);
    border-radius: 50%;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}
```

#### Características del Joystick:
- **Posición Fija**: Se mantiene en esquina inferior izquierda para acceso fácil
- **Área Activa**: Mitad izquierda de la pantalla para máxima comodidad
- **Zona Muerta Única**: Threshold fijo de 15px para todos los dispositivos
- **8 Direcciones**: Norte, Sur, Este, Oeste + diagonales intermedias

### 3. Sistema de Seguimiento del Dron

#### Funcionalidad "Seguir Dron":
```javascript
function toggleFollowDrone() {
    followDrone = !followDrone;
    
    if (followDrone) {
        // Activar modo seguimiento
        botonSeguir.textContent = "Dejar de Seguir";
        botonSeguir.classList.add('boton-verde');
        
        // Centrar inmediatamente en el dron
        map.setView(currentPos, map.getZoom());
        console.log('Modo seguimiento activado');
    } else {
        // Desactivar modo seguimiento
        botonSeguir.textContent = "Seguir Dron";
        botonSeguir.classList.add('boton-azul');
        console.log('Modo seguimiento desactivado');
    }
}
```

#### Características del Seguimiento:
- **Activación Manual**: Botón dedicado "Seguir Dron"
- **Seguimiento Suave**: Animaciones fluidas al seguir al dron
- **Centro Automático**: Mantiene el dron siempre centrado en pantalla
- **Toggle Inteligente**: Se puede activar/desactivar fácilmente

### 4. Gestión Inteligente de Estados del Dron

#### Sistema de Retroalimentación Mejorado:
```javascript
function updateButtonStates(droneState) {
    switch (droneState) {
        case 'connected':
            // Estado en tierra - habilitar despegue
            break;
        case 'flying':
            // Estado volando - habilitar aterrizar y RTL
            break;
        case 'landing':
            // Estado aterrizando - mostrar progreso
            break;
        case 'returning':
            // Estado RTL - mostrar volviendo a base
            break;
    }
}
```

| Estado del Dron | Botón Despegar | Botón Aterrizar | Botón RTL | Feedback Visual |
|------------------|----------------|-----------------|-----------|----------------|
| **Conectado** | Disponible | Deshabilitado | Deshabilitado | Estado base |
| **Volando** |  "Volando" |  Disponible |  Disponible | Verde confirmación |
| **Aterrizando** |  Deshabilitado |  "Aterrizando..." |  Deshabilitado | Amarillo progreso |
| **RTL** |  Deshabilitado |  Deshabilitado |  "Volviendo..." | Amarillo progreso |

### 5. Mejoras en la Experiencia de Usuario

#### Adaptación Automática de Interfaz:
```javascript
function setupDeviceSpecificUI() {
    if (IS_TOUCH_DEVICE) {
        // Mostrar joystick fijo, ocultar cruceta
        joystickContainer.classList.add('touch-device');
        navegacion.classList.add('touch-hidden');
        toggleNavBtn.style.display = 'none';
    } else {
        // Mostrar cruceta, ocultar joystick completamente
        joystickArea.classList.add('non-touch-hidden');
        navegacion.classList.remove('touch-hidden');
    }
}
```

#### Optimizaciones Específicas:
- **Móviles/Tablets**: Joystick táctil optimizado, oculta controles innecesarios
- **Desktop**: Cruceta clásica 


### 6. Arquitectura del Joystick

#### Sistema de Coordenadas Inteligente:
```javascript
function joystickToDirection(deltaX, deltaY) {
            
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
            
            const threshold = 15;
                        
            if (distance < threshold) {
                return 'Stop';
            }
            
            // Calcular ángulo (0° = Este, 90° = Norte, 180° = Oeste, 270° = Sur)
            let angle = Math.atan2(-deltaY, deltaX) * 180 / Math.PI; // -deltaY porque Y crece hacia abajo
            if (angle < 0) angle += 360;
            
            // Convertir ángulo a dirección cardinal/intercardinal
            if (angle >= 337.5 || angle < 22.5) return 'East';
            else if (angle >= 22.5 && angle < 67.5) return 'NorthEast';
            else if (angle >= 67.5 && angle < 112.5) return 'North';
            else if (angle >= 112.5 && angle < 157.5) return 'NorthWest';
            else if (angle >= 157.5 && angle < 202.5) return 'West';
            else if (angle >= 202.5 && angle < 247.5) return 'SouthWest';
            else if (angle >= 247.5 && angle < 292.5) return 'South';
            else if (angle >= 292.5 && angle < 337.5) return 'SouthEast';
            
            return 'Stop';
        }
```

#### Event Handling Optimizado:
```javascript
function setupJoystickTouchEvents() {
    joystickArea.addEventListener('touchstart', function(e) {
        e.preventDefault();
        joystickActive = true;
        
        // Coordenadas fijas para dispositivos táctiles
        if (IS_TOUCH_DEVICE) {
            joystickStartX = 100 + 60; 
            joystickStartY = window.innerHeight - 100 - 60;
        }
        
        // Iniciar envío periódico cada 150ms
        joystickInterval = setInterval(sendCommands, 150);
    });
}
```

### Sistema de Seguimiento del Dron

#### Actualización de Posición Inteligente:
```javascript
function updateDronePosition(lat, lon, heading) {
    const newPos = [lat, lon];
    
    // Actualizar marcadores del dron
    droneMarker.setLatLng(newPos);
    directionArrow.setLatLng(newPos);
    
    // Seguimiento automático si está activado
    if (followDrone) {
        map.setView(newPos, map.getZoom(), {
            animate: true, 
            duration: 0.3
        });
    }
    
    // Actualizar orientación visual
    directionArrow.setIcon(new DirectionArrow({
        iconUrl: 'data:image/svg+xml;charset=utf-8,' + 
                encodeURIComponent(createArrowSVG(heading))
    }));
}
```

### Mejoras en Feedback de Estados

#### Gestión Avanzada de Transiciones:
```javascript
// Detectar transiciones de aterrizaje
if ((previousDroneState === 'landing' || previousDroneState === 'returning') && 
    data.state === 'connected') {
    
    // Mostrar "En Tierra" por 3 segundos
    if (previousDroneState === 'landing') {
        showLandedState('botonAterrizar');
    } else if (previousDroneState === 'returning') {
        showLandedState('botonRTL');
    }
} else {
    updateButtonStates(data.state);
}
```

## Experiencia de Usuario Mejorada

### Ventajas para Dispositivos Móviles:
- **Control Intuitivo**: Joystick táctil
- **Una Sola Mano**: Diseño optimizado para uso con pulgar
- **Feedback Inmediato**: Respuesta visual instantánea al movimiento

### Seguimiento del Dron:
- **Orientación Automática**: Nunca perder de vista al dron
- **Navegación Fluida**: Transiciones suaves al seguir movimientos
- **Control Manual**: Toggle rápido para explorar otras áreas
- **Zoom Inteligente**: Mantiene nivel de zoom preferido del usuario

## Comparación V2 vs V3

### Funcionalidades Nuevas en V3:

| Característica | V2 | V3 |
|---------------|----|----|
| **Control Táctil** |  No disponible |  Joystick virtual completo |
| **Detección de Dispositivo** |  Interfaz única |  Adaptación automática |
| **Seguimiento de Dron** |  Manual |  Automático configurable |
| **Feedback de Estados** |  Básico |  Avanzado con transiciones |

### Mejoras de la Interfaz:

#### Gestión de Botones:
- **V2**: Estados básicos con colores
- **V3**: Estados avanzados con transiciones y texto descriptivo

#### Control de Movimiento:
- **V2**: Solo cruceta de 8 botones
- **V3**: Joystick táctil + cruceta adaptativa

#### Experiencia Visual:
- **V2**: Interfaz estática
- **V3**: Seguimiento dinámico del dron  

<br>

---

**Versión**: V3  
**Fecha**: 11 Octubre 2025  
**Cambios Principales**: Control por joystick táctil, seguimiento automático del dron, interfaz adaptativa multi-dispositivo