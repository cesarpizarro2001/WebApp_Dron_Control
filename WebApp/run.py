# IMPORTANTE: Interprete Pyhton 3.9 e instalar Flask, Flask-SocketIO
from app import create_app
from flask_socketio import SocketIO, emit, join_room

app = create_app()
socketio = SocketIO(app, cors_allowed_origins="*")

# [Deprecado] Gestión de rutas locales de galería eliminada del servidor.

# Variable global para almacenar el tipo de dispositivo del profesor
professor_device_info = {'isTouchDevice': None}
# Estado UI compartido para re-sincronizar a alumnos que se conectan tarde
ui_state = {
    'gamepad_modal': None  # 'open' | 'close' | None
}

# ========================================================================
# WEBRTC SIGNALING - Gestión de emisores y receptores
# ========================================================================
# Diccionario de emisores: {stream_id: socket_id}
webrtc_emitters = {}

# Diccionario de receptores esperando: {stream_id: [socket_ids]}
webrtc_pending_receivers = {}

# Diccionario de conexiones activas: {connection_id: {'emitter': sid, 'receiver': sid}}
webrtc_active_connections = {}

# [Deprecado] Carga y dibujo de imágenes de gestos en servidor eliminados.

# Recibimos los frames del video que nos envía la estación de tierra por el websocket, enviamos el frame al navegador
@socketio.on('video_frame')
def handle_video_frame(data):
    socketio.emit('stream_frame', data)

# Recibir comandos de la WebApp y reenviarlos a la Estación de Tierra
@socketio.on('command')
def handle_command(data):
    action = data.get('action')
    print(f"Comando recibido de WebApp: {action}")
    
    # Reenviar el comando a la Estación de Tierra
    socketio.emit('ground_station_command', data, include_self=False)

# Handler para datos de joystick del modo piloto
@socketio.on('pilot_rc')
def handle_pilot_rc(data):
    """Recibe datos de joystick: [throttle, yaw, pitch, roll]"""
    # Reenviar a la Estación de Tierra
    socketio.emit('pilot_rc', data, include_self=False)

# Handler para acciones del modo piloto (aterrizar, RTL)
@socketio.on('pilot_action')
def handle_pilot_action(data):
    action = data.get('action')
    print(f"Acción del modo piloto: {action}")
    # Reenviar a la Estación de Tierra
    socketio.emit('pilot_action', data, include_self=False)

# Handler para establecer parámetros del dron
@socketio.on('set_parameters')
def handle_set_parameters(params):
    """Recibe parámetros desde la WebApp y los envía a la Estación de Tierra"""
    print(f"Parámetros recibidos para configurar:")
    for param in params:
        print(f"  - {param['ID']}: {param['Value']}")
    
    # Reenviar los parámetros a la Estación de Tierra
    socketio.emit('set_parameters', params, include_self=False)
    print("Parámetros enviados a la Estación de Tierra")

# Handler para configuración de video (calidad y fps)
@socketio.on('video_settings')
def handle_video_settings(settings):
    """Recibe configuración de video desde la WebApp y la envía a la Estación de Tierra"""
    quality = settings.get('quality', 50)
    fps = settings.get('fps', 5)
    print(f"📹 Configuración de video recibida:")
    print(f"  - Calidad: {quality}%")
    print(f"  - FPS: {fps}")
    
    # Reenviar la configuración a la Estación de Tierra
    socketio.emit('video_settings', settings, include_self=False)
    print("✓ Configuración de video enviada a la Estación de Tierra")

# Handler para corrección de ojo de pez (passthrough)
@socketio.on('correccion')
def handle_correccion(payload):
    """Reenvía el toggle de corrección de fisheye a la Estación de Tierra"""
    try:
        enabled = payload.get('enabled') if isinstance(payload, dict) else payload
        estado = 'ACTIVAR' if enabled else 'DESACTIVAR'
        print(f"🐟 Corrección ojo de pez: {estado}")
        socketio.emit('correccion', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error reenviando 'correccion': {e}")

# Handler para zoom de cámara (passthrough)
@socketio.on('zoom')
def handle_zoom(payload):
    """Reenvía el comando de zoom a la Estación de Tierra"""
    try:
        x = payload.get('x', 0)
        y = payload.get('y', 0)
        level = payload.get('level', 1.0)
        print(f"🔍 Zoom: level={level:.2f}, center=({x}, {y})")
        socketio.emit('zoom', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error reenviando 'zoom': {e}")

# Handler para reset de zoom (passthrough)
@socketio.on('zoom_reset')
def handle_zoom_reset():
    """Reenvía el comando de reset de zoom a la Estación de Tierra"""
    try:
        print(f"🔎 Zoom reset")
        socketio.emit('zoom_reset', include_self=False)
    except Exception as e:
        print(f"❌ Error reenviando 'zoom_reset': {e}")

# ==================================================================================
# PASSTHROUGH DE COMANDOS DE GESTOS (MediaPipe en navegador)
# Estos eventos llegan desde el navegador (profesor) y se reenvían a la estación
# ==================================================================================

@socketio.on('go')
def handle_go_direction(direction):
    """Reenvía comandos de dirección (North/South/East/West/Stop) a la Estación de Tierra"""
    try:
        print(f"[GESTOS → ESTACIÓN] go: {direction}")
        socketio.emit('go', direction, include_self=False)
    except Exception as e:
        print(f"❌ Error reenviando 'go': {e}")

@socketio.on('arm_takeOff')
def handle_arm_takeoff_alt(alt):
    """Reenvía comando de armar y despegar con altura a la Estación de Tierra"""
    try:
        altura = 5
        # Altura puede venir como int, float o string
        if alt is not None:
            try:
                altura = int(float(alt))
            except Exception:
                altura = 5
        payload = {'action': 'arm_takeOff', 'altura': altura}
        print(f"[GESTOS → ESTACIÓN] arm_takeOff: {altura}m")
        socketio.emit('ground_station_command', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error reenviando 'arm_takeOff': {e}")

@socketio.on('Land')
def handle_land_command():
    """Reenvía comando de aterrizaje a la Estación de Tierra"""
    try:
        print(f"[GESTOS → ESTACIÓN] Land")
        socketio.emit('ground_station_command', {'action': 'Land'}, include_self=False)
    except Exception as e:
        print(f"❌ Error reenviando 'Land': {e}")

# ==================================================================================
# SISTEMA DE SALA ALUMNOS
# Los alumnos se unen a la sala 'alumnos' para recibir sincronización del profesor
# El profesor NO necesita sala (solo hay 1 y emite eventos directamente)
# ==================================================================================

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
            print(f"  └─> Enviando buttonMapping del profesor: {professor_device_info['buttonMapping']}")
        
        emit('professor_device_type', payload)

    # Reenviar estado actual del modal de instrucciones del mando si está abierto
    try:
        if ui_state.get('gamepad_modal') == 'open':
            print("  └─> Re-sincronizando estado: gamepad_modal ABIERTO para el nuevo alumno")
            emit('gamepad_modal_sync', {'action': 'open'})
    except Exception as e:
        print(f"❌ Error re-sincronizando gamepad_modal al alumno: {e}")

# ==================================================================================

# Recibir telemetría de la Estación de Tierra y enviarla al navegador
@socketio.on('telemetry_data')
def handle_telemetry(data):
    # Reenviar telemetría a todos los clientes web conectados (profesores y alumnos)
    socketio.emit('telemetry_info', data, include_self=False)

# ==================================================================================
# HANDLERS DE SINCRONIZACIÓN PROFESOR -> ALUMNO (alumno_control.html)
# Estos handlers retransmiten eventos del profesor a los alumnos para mantener
# sincronizada la interfaz visual sin permitir interacción de los alumnos
# ==================================================================================

# Sincronización de estilos de botones (Conectar, Despegar, Aterrizar, RTL)
@socketio.on('button_style_sync')
def handle_button_style_sync(payload):
    """Sincroniza cambios de texto y clases CSS de botones principales - SOLO A ALUMNOS"""
    try:
        socketio.emit('button_style_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en button_style_sync: {e}")

# Sincronización de comandos de voz
@socketio.on('voice_command_sync')
def handle_voice_command_sync(payload):
    """Sincroniza estados del control por voz (listening, processing, success, error) - SOLO A ALUMNOS"""
    try:
        status = payload.get('status')
        text = payload.get('text', '')
        if text:
            print(f"[SYNC VOZ → ALUMNOS] {status.upper()} - '{text}'")
        else:
            print(f"[SYNC VOZ → ALUMNOS] {status.upper()}")
        socketio.emit('voice_command_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en voice_command_sync: {e}")

# Sincronización de cámara móvil (modal)
@socketio.on('camera_modal_sync')
def handle_camera_modal_sync(payload):
    """Sincroniza apertura/cierre del modal de cámara móvil del profesor - SOLO A ALUMNOS"""
    try:
        print(f"[SYNC CÁMARA MÓVIL → ALUMNOS] {payload.get('action').upper()}")
        socketio.emit('camera_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en camera_modal_sync: {e}")

# Sincronización de cámara del dron
@socketio.on('drone_camera_sync')
def handle_drone_camera_sync(payload):
    """Sincroniza apertura/cierre de la vista de cámara del dron - SOLO A ALUMNOS"""
    try:
        print(f"[SYNC CÁMARA DRON → ALUMNOS] {payload.get('action').upper()}")
        socketio.emit('drone_camera_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en drone_camera_sync: {e}")

# Sincronización de modal de foto capturada
@socketio.on('sync_photo_capture')
def handle_sync_photo_capture(payload):
    """Reenvía foto capturada (base64) a los alumnos para preview"""
    try:
        print(f"[SYNC FOTO → ALUMNOS] Reenviando foto capturada en base64")
        socketio.emit('sync_photo_capture', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en sync_photo_capture: {e}")

@socketio.on('sync_recording_start')
def handle_sync_recording_start():
    """Notifica a los alumnos que inició grabación de video"""
    try:
        print(f"[SYNC VIDEO → ALUMNOS] INICIO DE GRABACIÓN")
        socketio.emit('sync_recording_start', room='alumnos')
    except Exception as e:
        print(f"❌ Error en sync_recording_start: {e}")

@socketio.on('sync_recording_stop')
def handle_sync_recording_stop():
    """Notifica a los alumnos que finalizó grabación de video"""
    try:
        print(f"[SYNC VIDEO → ALUMNOS] FIN DE GRABACIÓN")
        socketio.emit('sync_recording_stop', room='alumnos')
    except Exception as e:
        print(f"❌ Error en sync_recording_stop: {e}")

@socketio.on('photo_modal_sync')
def handle_photo_modal_sync(payload):
    """Sincroniza visualización de fotos capturadas - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        photo = payload.get('photoName', '')
        if action == 'open':
            print(f"[SYNC FOTO → ALUMNOS] ABRIR - {photo}")
        else:
            print(f"[SYNC FOTO → ALUMNOS] CERRAR")
        socketio.emit('photo_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en photo_modal_sync: {e}")

# Sincronización de modal de video y controles de reproducción
@socketio.on('video_modal_sync')
def handle_video_modal_sync(payload):
    """Sincroniza visualización de videos y controles (play, pause, seek) - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        if action == 'open':
            print(f"[SYNC VIDEO → ALUMNOS] ABRIR - {payload.get('videoName', '')}")
        elif action == 'close':
            print(f"[SYNC VIDEO → ALUMNOS] CERRAR")
        elif action in ['play', 'pause']:
            print(f"[SYNC VIDEO → ALUMNOS] {action.upper()} - {payload.get('currentTime', 0):.1f}s")
        elif action == 'seek':
            print(f"[SYNC VIDEO → ALUMNOS] SEEK -> {payload.get('currentTime', 0):.1f}s")
        socketio.emit('video_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en video_modal_sync: {e}")

# Sincronización del estado del gamepad
@socketio.on('gamepad_status_sync')
def handle_gamepad_status_sync(payload):
    """Sincroniza el estado de conexión del gamepad - SOLO A ALUMNOS"""
    try:
        connected = payload.get('connected')
        status = 'CONECTADO' if connected else 'DESCONECTADO'
        print(f"[SYNC GAMEPAD → ALUMNOS] {status}")
        socketio.emit('gamepad_status_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en gamepad_status_sync: {e}")

 

# Sincronización de navegación por ajustes
@socketio.on('settings_navigation_sync')
def handle_settings_navigation_sync(payload):
    """Sincroniza el elemento seleccionado en ajustes - SOLO A ALUMNOS"""
    try:
        item_index = payload.get('itemIndex')
        print(f"[SYNC NAVEGACIÓN AJUSTES → ALUMNOS] Item {item_index}")
        socketio.emit('settings_navigation_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en settings_navigation_sync: {e}")

# Sincronización de remapeo de botones
@socketio.on('button_remap_sync')
def handle_button_remap_sync(payload):
    """Sincroniza el remapeo de botones del gamepad - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        button_name = payload.get('buttonName')
        print(f"[SYNC REMAPEO → ALUMNOS] {action} → {button_name}")
        socketio.emit('button_remap_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en button_remap_sync: {e}")

# Sincronización de estado de remapeo (listening/cancelled)
@socketio.on('remap_state_sync')
def handle_remap_state_sync(payload):
    """Sincroniza el estado del proceso de remapeo - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        state = payload.get('state')
        print(f"[SYNC ESTADO REMAPEO → ALUMNOS] {action}: {state}")
        socketio.emit('remap_state_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en remap_state_sync: {e}")

# Sincronización de acciones de ajustes (apply/reset)
@socketio.on('settings_action_sync')
def handle_settings_action_sync(payload):
    """Sincroniza acciones de aplicar/restaurar ajustes - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        print(f"[SYNC ACCIÓN AJUSTES → ALUMNOS] {action}")
        socketio.emit('settings_action_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en settings_action_sync: {e}")

# Sincronización del modal de confirmación
@socketio.on('confirm_modal_sync')
def handle_confirm_modal_sync(payload):
    """Sincroniza el modal de confirmación - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        if action == 'open':
            title = payload.get('title', 'Confirmación')
            print(f"[SYNC MODAL CONFIRMACIÓN → ALUMNOS] ABRIR - {title}")
        else:
            result = payload.get('result')
            resultado_texto = 'ACEPTADO' if result else 'CANCELADO'
            print(f"[SYNC MODAL CONFIRMACIÓN → ALUMNOS] CERRAR - {resultado_texto}")
        socketio.emit('confirm_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en confirm_modal_sync: {e}")

# Sincronización del tipo de dispositivo del profesor
@socketio.on('professor_device_type')
def handle_professor_device_type(payload):
    """Sincroniza el tipo de dispositivo del profesor (táctil/no táctil) y su buttonMapping - SOLO A ALUMNOS"""
    try:
        is_touch = payload.get('isTouchDevice')
        button_mapping = payload.get('buttonMapping')
        tipo = "TÁCTIL (Joystick)" if is_touch else "NO TÁCTIL (Cruceta)"
        print(f"[SYNC DISPOSITIVO PROFESOR → ALUMNOS] {tipo}")
        
        # Guardar el tipo de dispositivo y buttonMapping del profesor
        professor_device_info['isTouchDevice'] = is_touch
        if button_mapping:
            professor_device_info['buttonMapping'] = button_mapping
            print(f"[SYNC BUTTON MAPPING → ALUMNOS] {button_mapping}")
        
        # Emitir a todos los alumnos
        socketio.emit('professor_device_type', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en professor_device_type: {e}")

# Sincronización de la posición del joystick del profesor
@socketio.on('joystick_position')
def handle_joystick_position(payload):
    """Sincroniza la posición del joystick del profesor en tiempo real - SOLO A ALUMNOS"""
    try:
        # No imprimir en consola porque genera mucho spam (se actualiza constantemente)
        socketio.emit('joystick_position', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en joystick_position: {e}")

# Sincronización de waypoints individuales
@socketio.on('waypoint_sync')
def handle_waypoint_sync(payload):
    """Sincroniza la creación de waypoints individuales - SOLO A ALUMNOS"""
    try:
        if payload.get('action') == 'add':
            waypoint = payload.get('waypoint')
            print(f"[SYNC WAYPOINT → ALUMNOS] Nuevo waypoint #{waypoint.get('num')} - {waypoint.get('captura')}")
        socketio.emit('waypoint_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en waypoint_sync: {e}")

# Sincronización del modal de instrucciones de ruta
@socketio.on('route_instructions_modal_sync')
def handle_route_instructions_modal_sync(payload):
    """Sincroniza apertura/cierre del modal de instrucciones de ruta - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        print(f"[SYNC MODAL INSTRUCCIONES → ALUMNOS] {action.upper()}")
        socketio.emit('route_instructions_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en route_instructions_modal_sync: {e}")

# Sincronización del modal de crear waypoint
@socketio.on('waypoint_modal_sync')
def handle_waypoint_modal_sync(payload):
    """Sincroniza el modal de crear waypoint (abrir/cerrar/cambiar tipo) - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        if action == 'open':
            print(f"[SYNC MODAL WAYPOINT → ALUMNOS] ABRIR - Waypoint #{payload.get('waypointNum')}")
        elif action == 'close':
            print(f"[SYNC MODAL WAYPOINT → ALUMNOS] CERRAR")
        elif action == 'change_type':
            print(f"[SYNC MODAL WAYPOINT → ALUMNOS] CAMBIO TIPO -> {payload.get('selectedType')}")
        socketio.emit('waypoint_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en waypoint_modal_sync: {e}")

# ==================================================================================
# FIN HANDLERS DE SINCRONIZACIÓN ALUMNO_CONTROL
# ==================================================================================

# ==================================================================================
# HANDLERS DE SINCRONIZACIÓN ALUMNO_PILOTO (piloto.html -> alumno_piloto.html)
# Estos handlers retransmiten eventos del profesor a todos los alumnos
# ==================================================================================

# Sincronización del estado del joystick en modo piloto
@socketio.on('joystick_state')
def handle_joystick_state(payload):
    """Sincroniza la posición del joystick del modo piloto - A TODOS LOS CLIENTES"""
    try:
        # No imprimir en consola porque genera mucho spam (se actualiza constantemente)
        socketio.emit('joystick_state', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en joystick_state: {e}")

# Sincronización del estado de grabación de video
@socketio.on('recording_state')
def handle_recording_state(payload):
    """Sincroniza el estado de grabación de video - A TODOS LOS CLIENTES"""
    try:
        recording = payload.get('recording')
        estado = "GRABANDO" if recording else "DETENIDO"
        print(f"[SYNC GRABACIÓN → TODOS] {estado}")
        socketio.emit('recording_state', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en recording_state: {e}")

# Sincronización del panel de ajustes
@socketio.on('settings_panel_sync')
def handle_settings_panel_sync(payload):
    """Sincroniza la apertura/cierre del panel de ajustes - A TODOS LOS CLIENTES"""
    try:
        is_open = payload.get('open')
        estado = "ABIERTO" if is_open else "CERRADO"
        print(f"[SYNC PANEL AJUSTES → TODOS] {estado}")
        socketio.emit('settings_panel_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en settings_panel_sync: {e}")

# Sincronización de valores de sliders
@socketio.on('slider_value_sync')
def handle_slider_value_sync(payload):
    """Sincroniza los cambios de sliders de ajustes - A TODOS LOS CLIENTES"""
    try:
        setting = payload.get('setting')
        value = payload.get('value')
        # No imprimir cada cambio de slider porque genera mucho spam
        socketio.emit('slider_value_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en slider_value_sync: {e}")

# Sincronización inicial de todos los ajustes
@socketio.on('settings_initial_sync')
def handle_settings_initial_sync(payload):
    """Sincroniza todos los valores de ajustes al cargar - A TODOS LOS CLIENTES"""
    try:
        print(f"[SYNC AJUSTES INICIALES → TODOS] Enviando valores actuales")
        socketio.emit('settings_initial_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en settings_initial_sync: {e}")

# Sincronización de botones de control (despegar, aterrizar, RTL)
@socketio.on('pilot_button_sync')
def handle_pilot_button_sync(payload):
    """Sincroniza el estado de los botones de control del modo piloto - A TODOS LOS CLIENTES"""
    try:
        socketio.emit('pilot_button_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en pilot_button_sync: {e}")

# Sincronización del modal de instrucciones del mando
@socketio.on('gamepad_modal_sync')
def handle_gamepad_modal_sync(payload):
    """Sincroniza apertura/cierre del modal de instrucciones del mando - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        print(f"[SYNC MODAL MANDO → ALUMNOS] {action.upper()}")
        # Guardar estado para re-sincronizar a alumnos que entren más tarde
        if action in ('open', 'close'):
            ui_state['gamepad_modal'] = action
        socketio.emit('gamepad_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en gamepad_modal_sync: {e}")

# ==================================================================================
# FIN HANDLERS DE SINCRONIZACIÓN ALUMNO_PILOTO
# ==================================================================================

# ==================================================================================
# HANDLERS DE SINCRONIZACIÓN ALUMNO_MOVIMIENTO (movimiento.html -> alumno_movimiento.html)
# Estos handlers retransmiten eventos del profesor a todos los alumnos
# ==================================================================================

# Sincronización de orientación del móvil (motion control)
@socketio.on('motion_orientation_sync')
def handle_motion_orientation_sync(payload):
    """Sincroniza la orientación del móvil en tiempo real - A TODOS LOS CLIENTES"""
    try:
        # No imprimir en consola porque genera mucho spam (se actualiza constantemente)
        socketio.emit('motion_orientation_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en motion_orientation_sync: {e}")

# Sincronización de calibración de motion control
@socketio.on('motion_calibration_sync')
def handle_motion_calibration_sync(payload):
    """Sincroniza el evento de calibración del motion control - A TODOS LOS CLIENTES"""
    try:
        side = payload.get('landscapeSide')
        side_text = "IZQUIERDA" if side == 'LEFT' else "DERECHA"
        print(f"[SYNC CALIBRACIÓN MOTION → TODOS] Cámara {side_text}")
        socketio.emit('motion_calibration_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en motion_calibration_sync: {e}")

# ==================================================================================
# FIN HANDLERS DE SINCRONIZACIÓN ALUMNO_MOVIMIENTO
# ==================================================================================

# ==================================================================================
# SINCRONIZACIÓN DE NAVEGACIÓN ENTRE PÁGINAS
# Cuando el profesor cambia de página, los alumnos le siguen automáticamente
# ==================================================================================

@socketio.on('page_navigation_sync')
def handle_page_navigation_sync(payload):
    """Sincroniza la navegación del profesor a los alumnos - SOLO A ALUMNOS"""
    try:
        page = payload.get('page')
        print(f"[SYNC NAVEGACIÓN → ALUMNOS] Profesor fue a: {page}")
        socketio.emit('page_navigation_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en page_navigation_sync: {e}")

# ==================================================================================
# FIN SINCRONIZACIÓN DE NAVEGACIÓN
# ==================================================================================

# Recibir comandos de la WebApp y reenviarlos a la Estación de Tierra
@socketio.on('flight_event')
def handle_flight_event(data):
    event_type = data.get('event')
    print(f"Evento de vuelo: {event_type}", flush=True)
    print(f"Datos completos del evento: {data}", flush=True)
    
    try:
        if event_type == 'flight_name_set':
            socketio.emit('flight_name_set', data.get('name'))
            print(f"✓ Emitido flight_name_set", flush=True)
        else:
            # Eventos de foto/video basados en archivos están deprecados y se ignoran
            print(f"⚠️ Evento deprecado o no soportado: {event_type}", flush=True)
    except Exception as e:
        print(f"❌ ERROR al emitir evento {event_type}: {e}", flush=True)
        import traceback
        traceback.print_exc()

# NOTA: Handlers upload_photo y upload_video eliminados - las fotos/videos ya no se suben al servidor
# La webapp captura localmente en el navegador, la Estación de Tierra guarda en sus carpetas locales

# [Deprecado] Procesamiento de frames del móvil en el servidor eliminado.
# La detección de gestos y el overlay del vídeo ahora se realizan en el navegador
# con MediaPipe, y la transmisión se gestiona por WebRTC.


# ========================================================================
# WEBRTC SIGNALING HANDLERS - Negociación de conexiones WebRTC
# ========================================================================

@socketio.on('webrtc_register_emitter')
def handle_webrtc_register_emitter(data):
    """
    El emisor (EstacionDeTierra) se registra para transmitir video.
    Similar al 'registro' del ejemplo de tu profesor.
    
    data = {'stream_id': 'dron_camera'}
    """
    from flask import request
    stream_id = data.get('stream_id')
    socket_id = request.sid
    
    print(f"📡 [WebRTC] Emisor registrado: {stream_id} (socket: {socket_id})")
    webrtc_emitters[stream_id] = socket_id
    
    # Si hay receptores esperando, avisarles que el emisor ya está disponible
    if stream_id in webrtc_pending_receivers:
        pending = webrtc_pending_receivers[stream_id]
        print(f"   └─> Hay {len(pending)} receptor(es) esperando")
        
        # Avisar a cada receptor que el emisor está listo
        for receiver_sid in pending:
            emit('webrtc_emitter_ready', {
                'stream_id': stream_id
            }, room=receiver_sid)

        # Proactivamente crear conexiones y pedir oferta al emisor
        import time
        for receiver_sid in pending:
            timestamp = int(time.time() * 1000)
            connection_id = f"{socket_id}_{receiver_sid}_{timestamp}"
            webrtc_active_connections[connection_id] = {
                'emitter': socket_id,
                'receiver': receiver_sid,
                'timestamp': timestamp,
                'stream_id': stream_id
            }
            print(f"   └─> Preparando oferta para receptor en espera: {receiver_sid} -> {connection_id}")
            emit('webrtc_prepare_offer', {
                'connection_id': connection_id,
                'receiver_sid': receiver_sid,
                'stream_id': stream_id
            }, room=socket_id)
        
        # Limpiar lista de pendientes
        webrtc_pending_receivers[stream_id] = []


@socketio.on('webrtc_stop_streaming')
def handle_webrtc_stop_streaming(data):
    """
    El emisor indica que detiene la transmisión para un stream.
    Se desregistra como emisor y se cierran conexiones activas relacionadas.
    """
    from flask import request
    stream_id = data.get('stream_id')
    socket_id = request.sid

    print(f"🛑 [WebRTC] Emisor detiene stream: {stream_id} (socket: {socket_id})")

    # Si el emisor registrado coincide, eliminarlo
    if webrtc_emitters.get(stream_id) == socket_id:
        del webrtc_emitters[stream_id]
        print(f"   └─> Emisor desregistrado para stream: {stream_id}")

    # Cerrar conexiones activas de este emisor para el stream
    to_close = [cid for cid, conn in webrtc_active_connections.items()
                if conn.get('emitter') == socket_id and conn.get('stream_id') == stream_id]
    for cid in to_close:
        receiver_sid = webrtc_active_connections[cid]['receiver']
        emit('webrtc_close_connection', {'connection_id': cid}, room=receiver_sid)
        del webrtc_active_connections[cid]
        print(f"   └─> Conexión cerrada: {cid}")


@socketio.on('webrtc_request_stream')
def handle_webrtc_request_stream(data):
    """
    Un receptor (navegador) solicita recibir un stream de video.
    
    data = {'stream_id': 'dron_camera'}
    """
    from flask import request
    import time
    
    stream_id = data.get('stream_id')
    receiver_sid = request.sid
    
    print(f"📺 [WebRTC] Receptor solicita stream: {stream_id} (socket: {receiver_sid})")
    
    # Verificar si el emisor ya está registrado
    if stream_id in webrtc_emitters:
        emitter_sid = webrtc_emitters[stream_id]
        
        # Limpiar TODAS las conexiones anteriores de este receptor (si existen)
        old_connections = [conn_id for conn_id, conn in webrtc_active_connections.items() 
                          if conn['receiver'] == receiver_sid]
        
        for old_conn_id in old_connections:
            print(f"   └─> 🗑️ Cerrando conexión anterior: {old_conn_id}")
            # Notificar al emisor que cierre la conexión anterior
            emit('webrtc_close_connection', {'connection_id': old_conn_id}, room=emitter_sid)
            # Eliminar de activas
            del webrtc_active_connections[old_conn_id]
        
        # Crear ID ÚNICO para esta conexión (con timestamp para evitar colisiones)
        timestamp = int(time.time() * 1000)  # Milisegundos
        connection_id = f"{emitter_sid}_{receiver_sid}_{timestamp}"
        
        print(f"   └─> Emisor disponible. Creando nueva conexión: {connection_id}")
        
        # Registrar nueva conexión
        webrtc_active_connections[connection_id] = {
            'emitter': emitter_sid,
            'receiver': receiver_sid,
            'timestamp': timestamp,
            'stream_id': stream_id
        }
        
        # Pedir al emisor que prepare una oferta para este receptor
        # Similar a cuando el proxy avisa: {"type": "receptor", "id": 0}
        emit('webrtc_prepare_offer', {
            'connection_id': connection_id,
            'receiver_sid': receiver_sid,
            'stream_id': stream_id
        }, room=emitter_sid)
    else:
        # Emisor no disponible, agregar a lista de espera
        print(f"   └─> Emisor no disponible. Receptor en espera.")
        if stream_id not in webrtc_pending_receivers:
            webrtc_pending_receivers[stream_id] = []
        
        if receiver_sid not in webrtc_pending_receivers[stream_id]:
            webrtc_pending_receivers[stream_id].append(receiver_sid)


@socketio.on('webrtc_offer')
def handle_webrtc_offer(data):
    """
    El emisor envía una oferta SDP al receptor.
    Similar a cuando el sender envía {"type": "sdp", "role": "emisor"}
    
    data = {
        'connection_id': str,
        'sdp': str,
        'sdp_type': str
    }
    """
    from flask import request
    connection_id = data.get('connection_id')
    sdp = data.get('sdp')
    sdp_type = data.get('sdp_type')
    stream_id = data.get('stream_id')
    
    print(f"📤 [WebRTC] Oferta recibida para conexión: {connection_id}")
    
    # Obtener el receptor de esta conexión
    if connection_id in webrtc_active_connections:
        receiver_sid = webrtc_active_connections[connection_id]['receiver']
        
        # Reenviar la oferta al receptor
        # Incluir stream_id para que el receptor pueda filtrar el stream correcto
        if not stream_id:
            # Derivar stream_id de la conexión si no viene en el payload
            stream_id = webrtc_active_connections.get(connection_id, {}).get('stream_id')
        emit('webrtc_offer', {
            'connection_id': connection_id,
            'sdp': sdp,
            'sdp_type': sdp_type,
            'stream_id': stream_id
        }, room=receiver_sid)
        
        print(f"   └─> Oferta reenviada al receptor: {receiver_sid}")
    else:
        print(f"   └─> ⚠️ Conexión no encontrada: {connection_id}")


@socketio.on('webrtc_answer')
def handle_webrtc_answer(data):
    """
    El receptor envía una respuesta SDP al emisor.
    Similar a cuando el receiver envía {"type": "sdp", "role": "receiver"}
    
    data = {
        'connection_id': str,
        'sdp': str,
        'sdp_type': str
    }
    """
    from flask import request
    connection_id = data.get('connection_id')
    sdp = data.get('sdp')
    sdp_type = data.get('sdp_type')
    
    print(f"📥 [WebRTC] Respuesta recibida para conexión: {connection_id}")
    
    # Obtener el emisor de esta conexión
    if connection_id in webrtc_active_connections:
        emitter_sid = webrtc_active_connections[connection_id]['emitter']
        
        # Reenviar la respuesta al emisor
        # Añadir stream_id para consistencia
        stream_id = webrtc_active_connections.get(connection_id, {}).get('stream_id')
        emit('webrtc_answer', {
            'connection_id': connection_id,
            'sdp': sdp,
            'sdp_type': sdp_type,
            'stream_id': stream_id
        }, room=emitter_sid)
        
        print(f"   └─> Respuesta reenviada al emisor: {emitter_sid}")
        print(f"   └─> ✅ Conexión WebRTC establecida")
    else:
        print(f"   └─> ⚠️ Conexión no encontrada: {connection_id}")


@socketio.on('webrtc_ice_candidate')
def handle_webrtc_ice_candidate(data):
    """
    Intercambio de ICE candidates entre emisor y receptor.
    Necesario para establecer la conexión peer-to-peer.
    
    data = {
        'connection_id': str,
        'candidate': str,
        'sdpMid': str,
        'sdpMLineIndex': int
    }
    """
    from flask import request
    connection_id = data.get('connection_id')
    socket_id = request.sid
    
    if connection_id not in webrtc_active_connections:
        return
    
    conn = webrtc_active_connections[connection_id]
    
    # Determinar quién es el destinatario (el otro peer)
    if conn['emitter'] == socket_id:
        # Quien envía es el emisor, reenviar al receptor
        target_sid = conn['receiver']
    elif conn['receiver'] == socket_id:
        # Quien envía es el receptor, reenviar al emisor
        target_sid = conn['emitter']
    else:
        return
    
    # Añadir stream_id desde la conexión para que el receptor pueda filtrar
    connection = webrtc_active_connections.get(connection_id, {})
    payload = dict(data)
    payload['stream_id'] = connection.get('stream_id')
    # Reenviar el ICE candidate al peer correspondiente
    emit('webrtc_ice_candidate', payload, room=target_sid)


@socketio.on('webrtc_close_connection')
def handle_webrtc_close_connection(data):
    """
    El receptor notifica que cierra su conexión (para permitir reconectar).
    """
    connection_id = data.get('connection_id')
    
    if connection_id in webrtc_active_connections:
        print(f"🗑️ [WebRTC] Cerrando conexión: {connection_id}")
        
        # Notificar al emisor que cierre también
        emitter_sid = webrtc_active_connections[connection_id]['emitter']
        emit('webrtc_close_connection', {'connection_id': connection_id}, room=emitter_sid)
        
        del webrtc_active_connections[connection_id]


@socketio.on('disconnect')
def handle_disconnect():
    """
    Limpiar recursos WebRTC cuando un socket se desconecta.
    """
    from flask import request
    socket_id = request.sid
    
    print(f"🔌 [WebRTC] Socket desconectado: {socket_id}")
    
    # Limpiar como emisor
    stream_to_remove = None
    for stream_id, emitter_sid in webrtc_emitters.items():
        if emitter_sid == socket_id:
            stream_to_remove = stream_id
            break
    
    if stream_to_remove:
        print(f"   └─> Emisor eliminado: {stream_to_remove}")
        del webrtc_emitters[stream_to_remove]
    
    # Limpiar de receptores pendientes
    for stream_id in list(webrtc_pending_receivers.keys()):
        if socket_id in webrtc_pending_receivers[stream_id]:
            webrtc_pending_receivers[stream_id].remove(socket_id)
    
    # Limpiar conexiones activas
    connections_to_remove = []
    for conn_id, conn in webrtc_active_connections.items():
        if conn['emitter'] == socket_id or conn['receiver'] == socket_id:
            connections_to_remove.append(conn_id)
    
    for conn_id in connections_to_remove:
        print(f"   └─> Conexión cerrada: {conn_id}")
        del webrtc_active_connections[conn_id]


if __name__ == '__main__':
    print('=' * 60)
    print('WebApp con Socket.IO (sin MQTT)')
    print('=' * 60)
    print('Iniciando servidor...')
    print('  - Servidor web (HTTPS): https://localhost:5004')
    print('  - Socket.IO integrado en el mismo puerto')
    print('=' * 60)
    
    # Crear contexto SSL para HTTPS
    import ssl
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    #CERTIFICADO LOCALHOST
    #ssl_context.load_cert_chain('public_certificate.pem', 'private_key.pem')
    #CERTIFICADO SERVIDOR
    ssl_context.load_cert_chain('/etc/letsencrypt/live/dronseetac.upc.edu/cert.pem','/etc/letsencrypt/live/dronseetac.upc.edu/privkey.pem')
    
    # socketio.run() ejecuta tanto Flask como Socket.IO en el mismo puerto
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=8106,
        debug=True,
        allow_unsafe_werkzeug=True,
        use_reloader=False,
        ssl_context=ssl_context
    )
    
    print('\nServidor detenido.')
