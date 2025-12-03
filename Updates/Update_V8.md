# Update V8

## Resumen

Mejoras significativas en el sistema de control por voz con soporte para comandos compuestos y ejecución inteligente, junto con la implementación de una galería completa para visualizar fotos y videos capturados durante los vuelos.

### Objetivos Principales
- Implementar comandos de voz compuestos con ejecución secuencial
- Desarrollar sistema de espera inteligente basado en estados del dron
- Crear galería de fotos y videos con organización por carpetas
- Mejorar gestión del estado del botón de conexión
- Optimizar diseño responsive para móvil y desktop

---

## 1. Sistema de Comandos de Voz Compuestos

### 1.1. Comandos Múltiples

Soporte para ejecutar varios comandos en una sola frase mediante conectores:

```javascript
// Conectores soportados
const conectores = [
                ' y luego ',
                ' y después ',
                ' y despues ',
                ' luego ',
                ' después ',
                ' despues ',
                ' tambien ',
                ' también ',
                ' ademas ',
                ' además ',
                ' y '  // Este debe ir al final porque es el más genérico
            ];

// Ejemplo de uso:
"despega 5 metros y luego avanza 10 metros y después aterriza"
```

### 1.2. Cola de Ejecución Secuencial

Sistema FIFO (First In, First Out) para procesar comandos en orden:

```javascript
let colaComandos = [];
let ejecutandoComando = false;

async function procesarColaComandos() {
    if (colaComandos.length === 0 || ejecutandoComando) return;
    
    ejecutandoComando = true;
    const comando = colaComandos.shift();
    
    // Ejecutar comando
    await ejecutarComandoVoz(comando);
    
    // Esperar completitud según tipo de comando
    await esperarCompletitudComando(comando);
    
    ejecutandoComando = false;
    procesarColaComandos(); // Siguiente comando
}
```

### 1.3. Sistema de Espera Inteligente

Espera basada en estados reales del dron en lugar de delays fijos:

#### Despegar
```javascript
// Espera hasta que el estado sea 'flying'
while (Date.now() - tiempoInicio < 60000) {
    if (telemetry_info && telemetry_info.state === 'flying') {
        return true; // Completado
    }
    await new Promise(resolve => setTimeout(resolve, 200));
}
```

#### Movimientos con Distancia
```javascript
// Espera hasta que movimientoConDistancia.activo === false
while (Date.now() - tiempoInicio < 60000) {
    if (!movimientoConDistancia.activo) {
        return true; // Distancia alcanzada
    }
    await new Promise(resolve => setTimeout(resolve, 200));
}
```

#### Cambios de Altura
```javascript
// Espera dinámica: 1 segundo por metro + 1 segundo base (máx 10s)
const altura = extraerAltura(comando);
const tiempoEspera = Math.min((altura * 1000) + 1000, 10000);
await new Promise(resolve => setTimeout(resolve, tiempoEspera));
```

#### RTL (Return to Launch)
```javascript
// Espera hasta que el estado vuelva a 'connected' (timeout 120s)
while (Date.now() - tiempoInicio < 120000) {
    if (telemetry_info && telemetry_info.state === 'connected') {
        return true;
    }
    await new Promise(resolve => setTimeout(resolve, 200));
}
```

### 1.4. Mejoras en Reconocimiento de Voz

#### Limpieza de Texto
```javascript
function limpiarTranscripcion(texto) {
    return texto
        .toLowerCase()
        .replace(/[.,¿?!¡;:]/g, '')  // Eliminar puntuación
        .trim();
}
```

#### Parseo de Números
Soporte para números en dígitos y palabras:

```javascript
const numerosEspanol = {
    'cero': 0, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
    'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
    'diez': 10, 'quince': 15, 'veinte': 20, 'treinta': 30
};

function extraerAltura(comando) {
    // Extraer dígitos: "sube 5 metros" → 5
    let match = comando.match(/(\d+)\s*metros?/);
    if (match) return parseInt(match[1]);
    
    // Extraer palabras: "sube cinco metros" → 5
    for (let [palabra, numero] of Object.entries(numerosEspanol)) {
        if (comando.includes(palabra + ' metros')) {
            return numero;
        }
    }
    return null;
}
```

### 1.5. Cola de Voz para Feedback

Sistema que evita solapamiento de mensajes de voz:

```javascript
let colaVoz = [];
let hablando = false;

function hablar(texto) {
    colaVoz.push(texto);
    if (!hablando) procesarColaVoz();
}

function procesarColaVoz() {
    if (colaVoz.length === 0) {
        hablando = false;
        return;
    }
    
    hablando = true;
    const texto = colaVoz.shift();
    
    const utterance = new SpeechSynthesisUtterance(texto);
    utterance.lang = 'es-ES';
    
    utterance.onend = function() {
        setTimeout(() => procesarColaVoz(), 300); // Pausa 300ms
    };
    
    window.speechSynthesis.speak(utterance);
}
```

### 1.6. Mejoras en Duración de Reconocimiento

```javascript
recognition.addEventListener('result', (event) => {
    // Acumular transcripción de resultados interim
    let interimTranscript = '';
    let finalTranscript = '';
    
    for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
            finalTranscript += transcript;
        } else {
            interimTranscript += transcript;
        }
    }
    
    // Mostrar feedback visual en tiempo real
    if (interimTranscript) {
        console.log('Escuchando:', interimTranscript);
    }
});
```

---

## 2. Galería de Fotos y Videos

### 2.1. Estructura y Organización

Sistema de galería con carpetas expandibles organizadas por vuelo:

```javascript
// Agrupación automática por carpeta
const carpetas = {};
archivos.forEach(archivo => {
    const nombreCarpeta = archivo.nombre.split('/')[0];
    if (!carpetas[nombreCarpeta]) {
        carpetas[nombreCarpeta] = [];
    }
    carpetas[nombreCarpeta].push(archivo);
});
```

### 2.2. Interfaz de Usuario

#### Modal Principal
```css
.gallery-modal-content {
    width: 85vw;
    height: 75vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
```

#### Carpetas Expandibles
```html
<div class="gallery-folder collapsed">
    <div class="gallery-folder-header" onclick="toggleFolder()">
        <div class="gallery-folder-title">
            <span class="gallery-folder-icon">📁</span>
            <span>NombreCarpeta</span>
        </div>
        <span class="gallery-folder-count">24 archivos</span>
    </div>
    <div class="gallery-folder-items">
        <!-- Grid de thumbnails -->
    </div>
</div>
```

**Características visuales:**
- Carpetas cerradas por defecto
- Header con gradiente morado (`#667eea` → `#764ba2`)
- Icono 📁 que rota -90° cuando está colapsada
- Contador de archivos en cada carpeta

### 2.3. Thumbnails y Preview

#### Grid Responsive
```css
.gallery-folder-items {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    min-height: 200px;
    max-height: 450px;
    overflow-y: auto;
}

/* Móvil */
@media (max-width: 768px) {
    .gallery-folder-items {
        grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
        min-height: auto;
        max-height: 350px;
    }
}
```

#### Tipos de Archivos
```javascript
// Fotos
item.innerHTML = `
    <img src="${ruta}" alt="${nombreArchivo}">
    <div class="gallery-item-icon">📸</div>
    <div class="gallery-item-overlay">${nombreArchivo}</div>
`;

// Videos - Thumbnail del primer frame
item.innerHTML = `
    <video muted>
        <source src="${ruta}" type="video/mp4">
    </video>
    <div class="gallery-item-icon">🎥</div>
    <div class="gallery-item-overlay">${nombreArchivo}</div>
`;

video.addEventListener('loadeddata', () => {
    video.currentTime = 1; // Frame del segundo 1
});
```

### 2.4. Navegación y Preview

#### Sistema de Navegación
```javascript
let abrioDesdeGaleria = false;

// Al hacer click en thumbnail
item.addEventListener('click', () => {
    abrioDesdeGaleria = true;
    
    // Ocultar galería temporalmente
    document.getElementById('gallery-modal-container').style.display = 'none';
    
    // Mostrar modal de foto/video
    if (esVideo) {
        mostrarVideoGrabado(archivo.nombre);
    } else {
        mostrarFotoCapturada(archivo.nombre);
    }
});
```

#### Retorno a Galería
```javascript
function cerrarFotoCapturada() {
    const photoModal = document.getElementById('photo-modal-container');
    photoModal.style.display = 'none';
    
    // Si se abrió desde galería, volver a mostrarla
    if (abrioDesdeGaleria) {
        abrioDesdeGaleria = false;
        document.getElementById('gallery-modal-container').style.display = 'block';
    }
}
```

### 2.5. Backend Integration

#### Socket.IO Flow
```python
# EstacionDeTierra.py
@sio.on("request_gallery")
def handle_request_gallery():
    archivos = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Escanear fotos
    photos_dir = os.path.join(base_dir, 'captured_photos')
    if os.path.exists(photos_dir):
        for carpeta_vuelo in os.listdir(photos_dir):
            # ... procesar fotos
            archivos.append({
                'tipo': 'foto',
                'nombre': f"{carpeta_vuelo}/{archivo}",
                'fecha': fecha
            })
    
    # Escanear videos
    videos_dir = os.path.join(base_dir, 'captured_videos')
    # ... similar a fotos
    
    sio.emit('gallery_files', archivos)
```

#### Middleware en run.py
```python
# run.py - Reenvío de eventos
@socketio.on('request_gallery')
def handle_request_gallery():
    socketio.emit('request_gallery', include_self=False)

@socketio.on('gallery_files')
def handle_gallery_files(archivos):
    socketio.emit('gallery_files', archivos, include_self=False)
```

### 2.6. Scroll y Optimización

#### Scroll Personalizado
```css
/* Scroll del modal principal */
.gallery-grid::-webkit-scrollbar {
    width: 8px;
}

.gallery-grid::-webkit-scrollbar-thumb {
    background: rgba(33, 150, 243, 0.5);
    border-radius: 4px;
}

/* Scroll de carpetas individuales */
.gallery-folder-items::-webkit-scrollbar {
    width: 6px;
}

.gallery-folder-items::-webkit-scrollbar-thumb {
    background: rgba(102, 126, 234, 0.5);
    border-radius: 3px;
}
```

#### Prevención de Compresión
```css
.gallery-folder {
    flex-shrink: 0;  /* No comprimir carpetas */
}

.gallery-grid {
    min-height: 0;   /* Permitir scroll en flex */
}
```

### 2.7. Integración con Dropdown

Galería accesible desde el menú de funcionalidades:

```html
<button id="botonGaleria" class="boton-azul" onclick="abrirGaleria(); closeAllDropdowns()">
    🖼️ Galería
</button>
<div id="galeriaButtonsContainer" class="ruta-buttons-container" style="display: none;">
    <button id="botonVerGaleria" class="boton-amarillo">🖼️ Viendo Galería</button>
    <button id="botonCerrarGaleria" onclick="cerrarGaleria(); closeAllDropdowns()">❌</button>
</div>
```

**Comportamiento:**
- Click en "🖼️ Galería" → Oculta botón, muestra estado "Viendo Galería"
- Click en ❌ → Cierra galería, restaura botón original
- Consistente con otros elementos del dropdown (Cámara Dron, Cámara Móvil)

---

## 3. Mejoras en Gestión de Estados

### 3.1. Botón de Conexión

Sistema mejorado con timeout y feedback visual:

```javascript
let timeoutConexion = null;

function conectarDron() {
    socket.emit('command', { action: 'connect' });
    const botonConectar = document.getElementById('botonConectar');
    
    botonConectar.textContent = 'Conectando...';
    botonConectar.classList.remove('boton-verde', 'boton-rojo');
    botonConectar.classList.add('boton-amarillo');
    
    // Timeout de 15 segundos
    timeoutConexion = setTimeout(() => {
        if (telemetry_info && telemetry_info.state !== 'connected') {
            botonConectar.textContent = 'Conectar';
            botonConectar.classList.remove('boton-amarillo');
            console.log("⚠️ Timeout de conexión");
        }
    }, 15000);
}
```

#### Actualización al Conectar
```javascript
// En updateButtonStates()
case 'connected':
    // Limpiar timeout
    if (timeoutConexion) {
        clearTimeout(timeoutConexion);
        timeoutConexion = null;
    }
    
    botonConectar.textContent = 'Conectado';
    botonConectar.classList.add('boton-verde');
    break;
```

## 4. Comandos de Voz Soportados

### 4.1. Comandos Básicos

| Comando | Variantes | Acción |
|---------|-----------|--------|
| **Despegar** | "despega", "despegar", "take off" | Despega a altura especificada |
| **Aterrizar** | "aterriza", "aterrizar", "land" | Aterriza en posición actual |
| **RTL** | "vuelve a casa", "return to launch", "rtl" | Retorno a punto de despegue |
| **Parar** | "para", "parar", "stop", "detente" | Detiene movimiento actual |

### 4.2. Movimientos con Distancia

| Comando | Patrón | Ejemplo |
|---------|--------|---------|
| **Avanzar** | "avanza X metros" | "avanza 10 metros" |
| **Retroceder** | "retrocede X metros" | "retrocede 5 metros" |
| **Izquierda** | "ve a la izquierda X metros" | "ve a la izquierda 3 metros" |
| **Derecha** | "ve a la derecha X metros" | "ve a la derecha 7 metros" |
| **Subir** | "sube X metros" | "sube 5 metros" |
| **Bajar** | "baja X metros" | "baja 3 metros" |

### 4.3. Captura

| Comando | Variantes | Acción |
|---------|-----------|--------|
| **Foto** | "foto", "captura foto", "saca foto" | Captura foto actual |
| **Video** | "video", "graba video", "empieza video" | Inicia grabación |
| **Parar Video** | "para video", "detén video" | Detiene grabación |

### 4.4. Consultas de Telemetría

| Comando | Respuesta |
|---------|-----------|
| "¿cuál es mi altura?" | Lee altura actual en metros |
| "¿qué velocidad tengo?" | Lee velocidad en metros/segundo |
| "¿cuál es mi batería?" | Lee porcentaje de batería |
| "¿cuál es mi estado?" | Lee estado del dron (connected, flying, etc.) |

### 4.5. Ejemplos de Comandos Compuestos

```
"despega 5 metros y luego avanza 10 metros"
→ [despega 5 metros] → espera flying → [avanza 10 metros]

"avanza 8 metros y después sube 3 metros y luego aterriza"
→ [avanza 8] → espera distancia → [sube 3] → espera altura → [aterriza]

"saca una foto y después graba un video"
→ [foto] → pausa 5s → [iniciar video]

"retrocede 5 metros y luego vuelve a casa"
→ [retrocede 5] → espera distancia → [RTL] → espera connected
```

---

## 7. Mejoras de UX

### 7.1. Feedback Visual

- **Comandos de voz**: Visualización en tiempo real durante reconocimiento
- **Carpetas**: Animación de rotación del icono al expandir/colapsar
- **Thumbnails**: Hover con escala 1.05 y sombra azul
- **Scroll**: Barras personalizadas con colores del tema

### 7.2. Feedback Auditivo

- **Cola de voz**: Evita solapamiento de mensajes
- **Pausas**: 300ms entre mensajes consecutivos
- **Confirmaciones**: Respuesta auditiva para cada comando ejecutado
- **Errores**: Notificación de comandos no reconocidos

### 7.3. Navegación Intuitiva

- **Galería → Foto/Video → Galería**: Navegación fluida sin perder contexto
- **Carpetas colapsables**: Menos scroll, organización clara
- **Dropdown consistente**: Todos los elementos siguen el mismo patrón visual

---

**Versión**: V8  
**Fecha**: 6 Noviembre 2025  
**Cambios Principales**:  
- Comandos de voz compuestos con ejecución secuencial inteligente
- Sistema de espera basado en estados reales del dron
- Galería completa con organización por carpetas
- Thumbnails de fotos y videos con preview
- Cola de voz para feedback sin solapamiento
- Navegación fluida entre galería y modales de preview
