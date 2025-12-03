# Update V2 - Estación de Tierra

## Resumen

Esta versión implementa un **sistema inteligente, seguro y con feedback visual completo** que guía al usuario a través del flujo de operaciones y previene errores críticos en la operación de drones.

### Objetivos Principales
- Implementar feedback visual mediante colores en botones principales
- Crear un sistema de gestión inteligente de botones basado en estados
- Interface intuitiva, segura y robusta para operación de drones


## Características Principales

### 1. Sistema de Colores Unificado

| Estado | Color | Descripción | Ejemplo |
|--------|-------|-------------|---------|
| **Inicial/Listo** | 🟠 Naranja (`dark orange`) | Botón disponible para usar | "Conectar", "Armar", "Despegar" |
| **Procesando** | 🟡 Amarillo (`yellow`) | Acción en curso | "Conectando...", "Armando...", "Despegando..." |
| **Completado** | 🟢 Verde (`green`) | Acción exitosa | "Conectado", "Armado", "Volando" |
| **Error** | 🔴 Rojo (`red`) | Error en la operación | "Error - Conectar", "Error - Armar" |
| **Deshabilitado** | 🔘 Gris/Semitransparente | No disponible | Botones inactivos |

### 2. Gestión Inteligente de Estados

#### Flujo de Operaciones Guiado:
```
Conectar → Armar → Despegar → [Vuelo] → RTL → Desconectar
```

#### Estados del Sistema:

**Estado Inicial (Desconectado)**:
```
✅ Conectar         (Naranja - Disponible)
✅ Conectar WebApp  (Naranja - Disponible)
🔘 [Todos los demás botones deshabilitados]
```

**Estado Conectado**:
```
🟢 Conectado        (Verde - Completado, funcionalmente deshabilitado)
✅ Armar            (Naranja - Siguiente paso disponible)
✅ Desconectar      (Naranja - Disponible)
🔘 [Resto deshabilitado hasta armado]
```

**Estado Armado**:
```
🟢 Conectado        (Verde - Mantenido)
🟢 Armado           (Verde - Completado, funcionalmente deshabilitado)
✅ Despegar         (Naranja - Siguiente paso disponible)
🔘 Desconectar      (Gris - "Aterrizar para Desconectar")
🔘 [Movimientos deshabilitados hasta vuelo]
```

**Estado Volando**:
```
🟢 Conectado        (Verde - Mantenido)
🟢 Armado           (Verde - Mantenido)
🟢 Volando          (Verde - Estado actual, funcionalmente deshabilitado)
✅ Norte/Sur/Este/Oeste  (Naranja - Controles de vuelo activos)
✅ Parar/RTL        (Naranja - Controles de seguridad activos)
🔘 Desconectar      (Gris - "Aterrizar para Desconectar")
```


## Implementación Técnica

### Arquitectura Basada en Eventos

#### Sistema MessageHandler:
```python
def setup_arm_state_monitoring():
    """Configura los callbacks para monitorear el estado del dron automáticamente"""
    if dron and hasattr(dron, 'message_handler') and dron.message_handler:
        # Registrar callback para heartbeat (cambios de estado)
        dron.message_handler.register_handler('HEARTBEAT', on_drone_state_change)
        print('Callbacks de estado del dron configurados')
```

#### Callback Automático:
```python
def on_drone_state_change(msg):
    """
    Callback que se ejecuta automáticamente cuando cambia el estado del dron.
    Integra feedback visual (V1.1) con gestión de botones (V2.0)
    """
    if not dron:
        return
        
    current_state = dron.state
    
    def update_ui():

        if current_state == 'armed' and armBtn['text'] == "Armando...":
            armBtn['text'] = "Armado"
            armBtn['bg'] = "green"
            armBtn['fg'] = "white"
            
            deshabilitar_boton(armBtn)
            habilitar_boton(takeOffBtn)
            deshabilitar_boton(disconnectBtn, "funcionando")
            
        elif current_state == 'takingOff':
            takeOffBtn['text'] = "Volando"
            takeOffBtn['bg'] = "green"
            takeOffBtn['fg'] = "white"
            
            habilitar_boton(NorthBtn)
            habilitar_boton(SouthBtn)
            habilitar_boton(EastBtn)
            habilitar_boton(WestBtn)
            habilitar_boton(stopBtn)
            habilitar_boton(rtlBtn)
    
    # Thread-safe: actualizar UI en el thread principal
    ventana.after(0, update_ui)
```

### Sistema de Gestión de Botones

#### Función de Habilitación:
```python
def habilitar_boton(boton):
    """Restaura un botón a su estado inicial específico"""
    if boton == armBtn:
        boton['text'] = "Armar"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = armar_dron
    elif boton == takeOffBtn:
        boton['text'] = "Despegar"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = despegar_dron
    # ... casos específicos para cada botón
```

#### Función de Deshabilitación:
```python
def deshabilitar_boton(boton, modo_disconnect="desconectado"):
    """
    Deshabilita un botón sin usar el estado 'disabled' de tkinter.
    El botón se vuelve semitransparente y no responde a clics.
    """
    def comando_vacio():
        if modo_disconnect == "funcionando" and boton == disconnectBtn:
            messagebox.showwarning("Acción no permitida", 
                                 "Aterrizar para Desconectar")
    
    boton['command'] = comando_vacio
    
    # Aplicar efecto visual semitransparente
    bg_deshabilitado = crear_color_semitransparente(boton['bg'])
    fg_deshabilitado = crear_color_semitransparente(boton['fg'])
    
    boton['bg'] = bg_deshabilitado
    boton['fg'] = fg_deshabilitado
```

### Funciones Principales

#### Función `conectar_local()`:
```python
def conectar_local():
    connectBtn['text'] = "Conectando..."
    connectBtn['bg'] = "yellow"
    connectBtn['fg'] = "black"
    connectBtn.update()
    
    def connection_callback():
        connectBtn['text'] = "Conectado"
        connectBtn['bg'] = "green"
        connectBtn['fg'] = "white"
        
        deshabilitar_boton(connectBtn)
        habilitar_boton(armBtn)
        habilitar_boton(disconnectBtn)
        
        setup_arm_state_monitoring()
    
    def connection_error_callback():
        connectBtn['text'] = "Error - Conectar"
        connectBtn['bg'] = "red"
        connectBtn['fg'] = "white"
        
        ventana.after(3000, lambda: habilitar_boton(connectBtn))
    
    try:
        result = dron.connect_local()
        if result:
            connection_callback()
        else:
            connection_error_callback()
    except Exception as e:
        connection_error_callback()
```

#### Función `armar_dron()`:
```python
def armar_dron():
    armBtn['text'] = "Armando..."
    armBtn['bg'] = "yellow"
    armBtn['fg'] = "black"
    armBtn.update()
    
    deshabilitar_boton(disconnectBtn, "funcionando")
    
    try:
        result = dron.arm()
        print('Comando de armado enviado')
        
        def timeout_check():
            if armBtn['text'] == "Armando...":
                armBtn['text'] = "Error - Armar"
                armBtn['bg'] = "red"
                armBtn['fg'] = "white"
                
                ventana.after(3000, lambda: habilitar_boton(armBtn))
                habilitar_boton(disconnectBtn)
        
        ventana.after(10000, timeout_check)
        
    except Exception as e:
        armBtn['text'] = "Error - Armar"
        armBtn['bg'] = "red"
        armBtn['fg'] = "white"
        
        ventana.after(3000, lambda: habilitar_boton(armBtn))
        habilitar_boton(disconnectBtn)
```


## Experiencia de Usuario

### Mejoras Implementadas:
- Feedback visual inmediato de todas las acciones
- Flujo intuitivo guiado para usuarios novatos y expertos
- Prevención de errores por acciones inapropiadas
- Estados claros (procesando, exitoso, error)
- Interfaz robusta ante interacciones incorrectas
- Seguridad mejorada mediante deshabilitación contextual
- Experiencia consistente y predecible



## Beneficios de Seguridad

### Prevención de Errores Críticos:
- Imposibilidad de armar sin estar conectado
- Imposibilidad de despegar sin estar armado
- Desconexión bloqueada durante operaciones críticas
- Controles de vuelo disponibles solo en vuelo
- Mensajes informativos para acciones no permitidas

### Flujo Operacional Seguro:
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐
│ Conectar │ →  │  Armar   │ →  │ Despegar │ →  │  Volar   │ →  │   RTL    │ →  │Desconectar│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └───────────┘
     1               2               3               4               5               6
                     │                                               │
                     └───────────────────────────────────────────────┘
                                 (Regreso a estado armado)
```

Cada paso debe completarse exitosamente antes de avanzar al siguiente.

---

**Versión**: V2
**Fecha**: 6 Octubre 2025  