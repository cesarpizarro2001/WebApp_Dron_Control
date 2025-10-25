# Update V6

## Resumen

Esta versión implementa el **Control por Voz** como nueva funcionalidad principal del sistema, permitiendo el control del dron mediante comandos de voz en español utilizando la API Web Speech Recognition y Web Speech Synthesis. Se desarrolla un botón flotante interactivo con estados visuales diferenciados, validaciones de seguridad integradas, y feedback auditivo inmediato.

El sistema permite controlar todas las operaciones críticas del dron (despegue, aterrizaje, movimiento, ajuste de altitud) mediante lenguaje natural, con soporte para números en palabras y validaciones de rango para garantizar la seguridad operacional.

### Objetivos Principales
- Implementar reconocimiento de voz en español con comandos naturales
- Desarrollar botón flotante con estados visuales diferenciados
- Establecer sistema de feedback auditivo mediante síntesis de voz
- Integrar validaciones de seguridad para altitudes y comandos
- Optimizar procesamiento de comandos con mapeo palabra-número

---

## 1. Implementación del Sistema de Voz

### 1.1. Reconocimiento de Voz

#### Configuración de Web Speech Recognition API

El sistema utiliza la API nativa del navegador para reconocimiento de voz:

```javascript
// control.html (líneas ~1436-1454)

function iniciarControlVoz() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert('Tu navegador no soporta reconocimiento de voz. Usa Chrome o Safari.');
        return;
    }

    // Iniciar reconocimiento
    recognition = new SpeechRecognition();
    recognition.lang = 'es-ES';              // Español de España
    recognition.interimResults = false;      // Solo resultados finales
    recognition.maxAlternatives = 1;         // Una alternativa
    
    recognition.onstart = function() {
        recognizing = true;
        btn.classList.add('listening');
        voiceText.textContent = 'ESCUCHANDO...';
    };
}
```

**Características principales:**

| Característica | Configuración | Descripción |
|----------------|---------------|-------------|
| **Idioma** | `es-ES` | Español de España |
| **Resultados intermedios** | `false` | Solo resultados completos |
| **Alternativas** | `1` | Una única interpretación |
| **Normalización** | `toLowerCase().trim()` | Minúsculas sin espacios extra |

#### Gestión de Estados del Reconocimiento

```javascript
// control.html (líneas ~1456-1493)

recognition.onresult = function(event) {
    const transcript = event.results[0][0].transcript.toLowerCase().trim();
    console.log('Comando reconocido:', transcript);
    
    btn.classList.remove('listening');
    btn.classList.add('processing');
    voiceText.textContent = `"${transcript}"`;

    setTimeout(() => {
        const exitoso = procesarComandoVoz(transcript);
        
        if (exitoso) {
            setTimeout(() => {
                btn.classList.remove('processing');
                voiceText.textContent = 'VOZ';
                recognizing = false;
            }, 1500);
        } else {
            btn.classList.remove('processing');
            btn.classList.add('error');
            voiceText.textContent = 'NO ENTENDIDO';
            setTimeout(() => {
                btn.classList.remove('error');
                voiceText.textContent = 'VOZ';
                recognizing = false;
            }, 2000);
        }
    }, 500);
};
```

**Flujo de estados:**

```
VOZ (normal)
    ↓ (usuario hace click)
ESCUCHANDO... (listening - rojo con pulso)
    ↓ (se detecta voz)
"comando reconocido" (processing - verde expandido)
    ↓ (validación)
    ├─→ VOZ (éxito - 1.5s)
    └─→ NO ENTENDIDO (error - 2s) → VOZ
```

### 1.2. Síntesis de Voz (Text-to-Speech)

#### Función hablar()

Proporciona feedback auditivo inmediato al usuario:

```javascript
// control.html (líneas ~1513-1528)

function hablar(texto) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();  // Cancelar habla anterior
        
        const utterance = new SpeechSynthesisUtterance(texto);
        utterance.lang = 'es-ES';
        utterance.rate = 1.0;    // Velocidad normal
        utterance.pitch = 1.0;   // Tono normal
        utterance.volume = 1.0;  // Volumen máximo
        
        window.speechSynthesis.speak(utterance);
    }
}
```

**Mensajes de confirmación:**

| Comando | Mensaje en Voz Alta |
|---------|------------------|
| Despegar 5 metros | "Despegando a cinco metros" |
| Aterrizar | "Aterrizando" |
| RTL | "Regresando a base" |
| Para | "Deteniendo" |
| Norte | "Moviendo al norte" |
| Subir 3 metros | "Subiendo tres metros" |
| Error rango | "Solo se puede despegar entre 1 y 10 metros" |
| No reconocido | "Comando no reconocido" |

### 1.3. Procesamiento de Comandos

#### Mapeo de Palabras a Números

Sistema de conversión de palabras numéricas en español:

```javascript
// control.html (líneas ~1530-1543)

function palabraANumero(palabra) {
    const numeros = {
        'uno': 1, 'un': 1,
        'dos': 2,
        'tres': 3,
        'cuatro': 4,
        'cinco': 5,
        'seis': 6,
        'siete': 7,
        'ocho': 8,
        'nueve': 9,
        'diez': 10
    };
    return numeros[palabra.toLowerCase()] || null;
}
```

**Soporte de variantes:**
- ✅ "uno" y "un" → 1
- ✅ "despega cinco metros"
- ✅ "sube tres"
- ✅ "despegar a dos metros"

#### Extracción de Altitud

Busca números en cualquier parte del comando:

```javascript
// control.html (líneas ~1545-1561)

function extraerAltura(comando) {
    const palabras = comando.split(' ');
    
    for (let palabra of palabras) {
        // Limpiar "metros" si está pegado
        palabra = palabra.replace(/metros?$/i, '').trim();
        
        const numero = palabraANumero(palabra);
        if (numero !== null) {
            return numero;
        }
    }
    
    return null;
}
```

**Ejemplos reconocidos:**
- "despega cinco" → `5`
- "sube tres metros" → `3`
- "despegar a dos" → `2`
- "baja un metro" → `1`

#### Procesador Principal de Comandos

```javascript
// control.html (líneas ~1563-1731)

function procesarComandoVoz(comando) {
    console.log('Procesando comando:', comando);

    // DESPEGAR con altura específica
    if (comando.includes('despega') || comando.includes('despegar') || 
        comando.includes('takeoff') || comando.includes('vuela')) {
        
        const altura = extraerAltura(comando);
        
        if (altura !== null) {
            // Validar rango: 1-10 metros
            if (altura < 1 || altura > 10) {
                console.log(`Altura fuera de rango: ${altura} metros`);
                hablar('Solo se puede despegar entre 1 y 10 metros');
                return false;
            }
            
            console.log(`Ejecutando: Despegar a ${altura} metros`);
            hablar(`Despegando a ${altura} metros`);
            despegarDronConAltura(altura);
        } else {
            console.log('Ejecutando: Despegar');
            hablar('Despegando');
            despegarDron();
        }
        return true;
    }
    
    // ATERRIZAR
    if (comando.includes('aterriza') || comando.includes('aterrizas') || 
        comando.includes('aterrizar') || comando.includes('land')) {
        console.log('Ejecutando: Aterrizar');
        hablar('Aterrizando');
        aterrizarDron();
        return true;
    }
    
    // RTL
    if (comando.includes('rtl') || comando.includes('vuelve') || 
        comando.includes('regresa') || comando.includes('base') || 
        comando.includes('casa') || comando.includes('home')) {
        console.log('Ejecutando: RTL');
        hablar('Regresando a base');
        returnToLaunch();
        return true;
    }
    
    // PARA - solo si es comando de UNA palabra
    const palabrasComando = comando.trim().split(/\s+/);
    if (palabrasComando.length === 1 && 
        (comando === 'para' || comando === 'parar' || 
         comando === 'quieto' || comando === 'detener' || 
         comando === 'alto' || comando === 'stop')) {
        console.log('Ejecutando: Parar (detener movimiento)');
        hablar('Deteniendo');
        moverDron('Stop');
        return true;
    }
    
    // Comando no reconocido
    console.warn('Comando no reconocido:', comando);
    hablar('Comando no reconocido');
    return false;
}
```

---

## 2. Comandos de Voz Disponibles

### 2.1. Comandos de Vuelo

#### Despegue

**Variantes reconocidas:**
- "despega" / "despegar" / "vuela" / "takeoff"

**Con altura específica:**
```
Usuario: "despega cinco metros"
Sistema: "Despegando a cinco metros" + arm_takeOff(5)

Usuario: "despegar a tres"
Sistema: "Despegando a tres metros" + arm_takeOff(3)
```

**Sin altura (usa campo input):**
```
Usuario: "despega"
Sistema: "Despegando" + despegarDron()
```

**Validación de rango:**
```javascript
if (altura < 1 || altura > 10) {
    hablar('Solo se puede despegar entre 1 y 10 metros');
    return false;
}
```

#### Aterrizaje

**Variantes reconocidas:**
- "aterriza" / "aterrizas" / "aterrizar" / "land"

```
Usuario: "aterriza"
Sistema: "Aterrizando" + aterrizarDron()
```

#### Return to Launch (RTL)

**Variantes reconocidas:**
- "rtl" / "vuelve" / "regresa" / "base" / "casa" / "home"

```
Usuario: "vuelve a base"
Sistema: "Regresando a base" + returnToLaunch()
```

### 2.2. Comandos de Movimiento

#### Detener

**Variantes reconocidas:**
- "para" / "parar" / "quieto" / "detener" / "alto" / "stop"

**Validación especial:**
```javascript
// Solo si es comando de UNA palabra
const palabrasComando = comando.trim().split(/\s+/);
if (palabrasComando.length === 1 && ...) {
    moverDron('Stop');
}
```

**Protección contra falsos positivos:**
- ✅ "para" → Detiene el dron
- ❌ "para adelante" → NO detiene (es comando direccional)
- ❌ "ves para alante" → NO detiene

#### Direcciones Cardinales

| Dirección | Comandos | Acción |
|-----------|----------|--------|
| **Norte** | "norte", "adelante", "alante", "avanza", "recto" | `moverDron('North')` |
| **Sur** | "sur", "atrás", "retrocede", "backward" | `moverDron('South')` |
| **Este** | "este", "derecha", "right" | `moverDron('East')` |
| **Oeste** | "oeste", "izquierda", "left" | `moverDron('West')` |

```
Usuario: "ves para alante"
Sistema: "Moviendo al norte" + moverDron('North')

Usuario: "gira a la derecha"
Sistema: "Moviendo al este" + moverDron('East')
```

### 2.3. Ajuste de Altitud

#### Subir

**Variantes reconocidas:**
- "sube" / "subir" / "arriba" / "up"

**Con altura específica:**
```javascript
// control.html (líneas ~1674-1695)

if (comando.includes('sube') || comando.includes('subir') || 
    comando.includes('arriba') || comando.includes('up')) {
    
    const altura = extraerAltura(comando);
    
    if (altura !== null) {
        if (altura < 1 || altura > 10) {
            hablar('Solo se puede ajustar entre 1 y 10 metros');
            return false;
        }
        
        console.log(`Ejecutando: Subir ${altura} metros`);
        hablar(`Subiendo ${altura} metros`);
        ajustarAltitud(altura);
    } else {
        console.log('Ejecutando: Subir altitud (5m por defecto)');
        hablar('Subiendo 5 metros');
        ajustarAltitud(5);
    }
    return true;
}
```

**Ejemplos:**
```
"sube tres metros" → ajustarAltitud(3)
"subir" → ajustarAltitud(5)  // Por defecto
```

#### Bajar

**Variantes reconocidas:**
- "baja" / "bajar" / "abajo" / "down"

**Con altura específica:**
```
"baja dos metros" → ajustarAltitud(-2)
"bajar" → ajustarAltitud(-5)  // Por defecto
```


---


## 3. Integración con Sistema Existente

### 3.1. Función Compartida: despegarDronConAltura()

Esta función es utilizada tanto por control de voz como por control de gestos:

```javascript
// control.html (líneas ~1401-1423)

function despegarDronConAltura(altura) {
    // Validar que la altura sea un número válido
    if (!altura || isNaN(altura) || altura <= 0) {
        alert("Por favor, proporcione una altura válida.");
        return;
    }
    
    // Actualizar el campo de altura (feedback visual)
    const alturaInput = document.getElementById("altura");
    if (alturaInput) {
        alturaInput.value = altura;
    }
    
    // Configurar estado de despegue
    despegando = true;
    const botonDespegar = document.getElementById('botonDespegar');
    botonDespegar.textContent = 'Despegando...';
    botonDespegar.classList.add('boton-amarillo');
    botonDespegar.disabled = true;
    
    // Enviar comando de despegue con la altura especificada
    socket.emit('command', { action: 'arm_takeOff', altura: String(altura) });
}
```

**Utilizada por:**
1. Control de voz: `despegarDronConAltura(altura)` cuando se reconoce comando con altura específica
2. Control de gestos (MediaPipe): `socket.on('arm_takeOff', (data) => despegarDronConAltura(data))`

### 3.3. Coexistencia con Otros Controles

El control por voz funciona en paralelo con:

| Método de Control | Compatibilidad | Notas |
|-------------------|----------------|-------|
| **Botones Táctiles** | ✅ Total | Puede usarse alternadamente |
| **Joystick (Móvil)** | ✅ Total | Independiente |
| **Cruceta Desktop** | ✅ Total | Independiente |
| **Click en Mapa** | ✅ Total | Comandos goto compatibles |
| **Gestos (MediaPipe)** | ✅ Total | Comparten función `despegarDronConAltura()` |
| **Modo Piloto** | ⚠️ Limitado | Voz funciona pero RC override puede interferir |

---

## 4. Compatibilidad del Navegador

**Web Speech Recognition API:**

| Navegador | Soporte | Notas |
|-----------|---------|-------|
| **Chrome Desktop** | ✅ Completo | Requiere permisos de micrófono |
| **Chrome Android** | ✅ Completo | Funciona perfectamente |
| **Edge** | ✅ Completo | Basado en Chromium |
| **Safari Desktop** | ✅ Completo | macOS 12+ |
| **Safari iOS** | ✅ Completo | iOS 14.5+ |
| **Firefox** | ❌ No soportado | API no implementada |
| **Opera** | ⚠️ Limitado | Depende de versión |

**Detección de compatibilidad:**

```javascript
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SpeechRecognition) {
    alert('Tu navegador no soporta reconocimiento de voz. Usa Chrome o Safari.');
    return;
}
```

### Mejoras de UX

| Aspecto | V5 | V6 |
|---------|----|----|
| **Control Hands-Free** | No | Sí (voz) |
| **Feedback Auditivo** | Solo visual | Visual + Auditivo |
| **Lenguaje Natural** | Comandos exactos | Frases flexibles |
| **Validación Proactiva** | Post-ejecución | Pre-ejecución con mensaje |
| **Estados Visuales** | Estáticos | Animados con transiciones |
| **Accesibilidad** | Táctil/Click | Táctil/Click/Voz |


---

**Versión**: V6  
**Fecha**: 25 Octubre 2025  
**Cambios Principales**: Implementación completa de Control por Voz con reconocimiento en español, síntesis de voz
