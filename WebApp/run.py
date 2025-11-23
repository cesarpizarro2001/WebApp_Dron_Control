# IMPORTANTE: Interprete Pyhton 3.9 e instalar Flask, Flask-SocketIO, mediapipe
import base64
from app import create_app
from flask_socketio import SocketIO, emit, join_room
import cv2
import numpy as np
import mediapipe as mp
import traceback
import os

# Inicializa MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

app = create_app()
socketio = SocketIO(app, cors_allowed_origins="*")

# Variable global para almacenar el tipo de dispositivo del profesor
professor_device_info = {'isTouchDevice': None}

# Cargar imágenes de gestos de MediaPipe
def load_gesture_images():
    gesture_images = {}
    gesture_files = {
        'norte': 'gestos/pulgar_arriba.png',
        'sur': 'gestos/pulgar_abajo.png',
        'oeste': 'gestos/pulgar_izquierda.png',
        'este': 'gestos/pulgar_derecha.png',
        'stop': 'gestos/cinco_dedos.png',
        'despegar': 'gestos/ok.png',
        'aterrizar': 'gestos/pulgar_indice.png'
    }

    for gesture, file_path in gesture_files.items():
        try:
            if os.path.exists(file_path):
                img = cv2.imread(file_path, cv2.IMREAD_COLOR)
                if img is not None:
                    gesture_images[gesture] = img
                    print(f"Imagen cargada: {gesture}")
                else:
                    print(f"Error al cargar imagen: {file_path}")
            else:
                print(f"Archivo no encontrado: {file_path}")
        except Exception as e:
            print(f"Error cargando {gesture}: {e}")

    print(f"Total imágenes cargadas: {len(gesture_images)}")
    return gesture_images

# Cargar imágenes al inicio
gesture_images = load_gesture_images()

# Dibuja una chuleta visual con imágenes de gestos
def draw_gesture_cheat_sheet(frame, gesture_images):
    try:
        height, width = frame.shape[:2]

        # Configuración de la chuleta
        start_x = 10
        start_y = height - 420
        img_size = 50
        text_offset_x = 55
        row_spacing = 55

        gestures_info = [
            ('norte', 'Norte', (0, 255, 0)),
            ('sur', 'Sur', (0, 255, 0)),
            ('oeste', 'Oeste', (0, 255, 0)),
            ('este', 'Este', (0, 255, 0)),
            ('stop', 'Stop', (0, 0, 255)),
            ('despegar', 'Despegar', (255, 0, 0)),
            ('aterrizar', 'Aterrizar', (255, 0, 0))
        ]

        # Dibujar fondo semitransparente para la chuleta
        overlay = frame.copy()
        cv2.rectangle(overlay, (start_x - 5, start_y - 10),
                      (start_x + 160, start_y + len(gestures_info) * row_spacing + 5),
                      (0, 0, 0), -1)
        frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

        for i, (gesture_key, gesture_name, color) in enumerate(gestures_info):
            y_pos = start_y + i * row_spacing

            # Verificar que las coordenadas estén dentro del frame
            if y_pos + img_size <= height and start_x + img_size <= width:
                # Dibujar imagen si está disponible
                if gesture_key in gesture_images:
                    img = gesture_images[gesture_key]
                    # Redimensionar la imagen al nuevo tamaño
                    img_resized = cv2.resize(img, (img_size, img_size))
                    frame[y_pos:y_pos + img_size, start_x:start_x + img_size] = img_resized
                else:
                    # Si no hay imagen, dibujar un interrogante
                    cv2.rectangle(frame, (start_x, y_pos), (start_x + img_size, y_pos + img_size), (128, 128, 128), 2)
                    cv2.putText(frame, "?", (start_x + 15, y_pos + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)  # Ajustado

            # Dibujar texto del gesto
            cv2.putText(frame, gesture_name, (start_x + text_offset_x, y_pos + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

        return frame
    except Exception as e:
        print(f"Error en draw_gesture_cheat_sheet: {e}")
        return frame

# Recibimos los frames del video que nos envía la estación de tierra por el websocket, enviamos el frame al navegador
@socketio.on('video_frame')
def handle_video_frame(data):
    print ("Recibo frame")
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

# Handler para solicitud de galería
@socketio.on('request_gallery')
def handle_request_gallery():
    """Recibe solicitud de galería desde la WebApp y la reenvía a la Estación de Tierra"""
    print("📂 Solicitud de galería recibida desde WebApp, reenviando a Estación de Tierra")
    socketio.emit('request_gallery', include_self=False)

# Handler para recibir archivos de galería desde la Estación de Tierra
@socketio.on('gallery_files')
def handle_gallery_files(archivos):
    """Recibe archivos de galería desde la Estación de Tierra y los envía al navegador"""
    print(f"📂 Recibidos {len(archivos)} archivos de galería, reenviando al navegador")
    socketio.emit('gallery_files', archivos, include_self=False)
    
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
        emit('professor_device_type', {'isTouchDevice': professor_device_info['isTouchDevice']})

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
        print(f"[SYNC BOTONES → ALUMNOS] {payload.get('buttonId')} -> {payload.get('text')}")
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

# Sincronización de modal de galería
@socketio.on('gallery_modal_sync')
def handle_gallery_modal_sync(payload):
    """Sincroniza apertura/cierre del modal de galería - SOLO A ALUMNOS"""
    try:
        action = payload.get('action')
        print(f"[SYNC GALERÍA → ALUMNOS] {action.upper()}")
        socketio.emit('gallery_modal_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en gallery_modal_sync: {e}")

# Sincronización del contenido de la galería
@socketio.on('gallery_content_sync')
def handle_gallery_content_sync(payload):
    """Sincroniza el contenido de archivos de la galería - SOLO A ALUMNOS"""
    try:
        archivos = payload.get('archivos', [])
        print(f"[SYNC CONTENIDO GALERÍA → ALUMNOS] {len(archivos)} archivos")
        socketio.emit('gallery_content_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en gallery_content_sync: {e}")

# Sincronización de carpetas expandidas/colapsadas en la galería
@socketio.on('gallery_folder_sync')
def handle_gallery_folder_sync(payload):
    """Sincroniza el estado (expandido/colapsado) de carpetas en la galería - SOLO A ALUMNOS"""
    try:
        folder_name = payload.get('folderName')
        collapsed = payload.get('collapsed')
        estado = "CERRADA" if collapsed else "ABIERTA"
        print(f"[SYNC CARPETA GALERÍA → ALUMNOS] '{folder_name}' → {estado}")
        socketio.emit('gallery_folder_sync', payload, room='alumnos')
    except Exception as e:
        print(f"❌ Error en gallery_folder_sync: {e}")

# Sincronización del tipo de dispositivo del profesor
@socketio.on('professor_device_type')
def handle_professor_device_type(payload):
    """Sincroniza el tipo de dispositivo del profesor (táctil/no táctil) - SOLO A ALUMNOS"""
    try:
        is_touch = payload.get('isTouchDevice')
        tipo = "TÁCTIL (Joystick)" if is_touch else "NO TÁCTIL (Cruceta)"
        print(f"[SYNC DISPOSITIVO PROFESOR → ALUMNOS] {tipo}")
        
        # Guardar el tipo de dispositivo del profesor
        professor_device_info['isTouchDevice'] = is_touch
        
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
        button_id = payload.get('buttonId')
        text = payload.get('text')
        print(f"[SYNC BOTÓN PILOTO → TODOS] {button_id}: {text}")
        socketio.emit('pilot_button_sync', payload, include_self=False)
    except Exception as e:
        print(f"❌ Error en pilot_button_sync: {e}")

# ==================================================================================
# FIN HANDLERS DE SINCRONIZACIÓN ALUMNO_PILOTO
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
        elif event_type == 'foto_capturada':
            filename = data.get('filename')
            print(f"📸 Emitiendo foto_capturada con filename: '{filename}'", flush=True)
            socketio.emit('foto_capturada', filename)
            print(f"✓ foto_capturada emitido al navegador", flush=True)
        elif event_type == 'video_iniciado':
            socketio.emit('video_iniciado', data.get('filename'))
            print(f"✓ Emitido video_iniciado", flush=True)
        elif event_type == 'video_detenido':
            filename = data.get('filename')
            if filename:
                socketio.emit('video_detenido', filename)
                print(f"✓ Emitido video_detenido con filename: '{filename}'", flush=True)
            else:
                socketio.emit('video_detenido')
                print(f"✓ Emitido video_detenido sin filename", flush=True)
        elif event_type == 'video_error':
            socketio.emit('video_error', data.get('message'))
            print(f"✓ Emitido video_error", flush=True)
    except Exception as e:
        print(f"❌ ERROR al emitir evento {event_type}: {e}", flush=True)
        import traceback
        traceback.print_exc()

# Enviar frame de video del movil procesado al navegador y a la estación de tierra
@socketio.on("frame_from_camera")
def handle_video(data):
    processed_frame = process_frame_hands (data)
    socketio.emit("processed_frame", f"data:image/jpeg;base64,{processed_frame}")

# Procesa el video que se recibe de la cámara del móvil
def process_frame_hands(data):
    try:
        img_data = base64.b64decode(data.split(",")[1])
        np_arr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Convertir a RGB para MediaPipe
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, _ = frame.shape

        # Mostrar la chuleta visual con imágenes de gestos
        frame = draw_gesture_cheat_sheet(frame, gesture_images)

        with mp_hands.Hands(static_image_mode=False,
                            max_num_hands=2,
                            min_detection_confidence=0.6,
                            min_tracking_confidence=0.6) as hands:

            results = hands.process(image_rgb)

            command = None

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Dibuja los puntos y líneas de la mano detectada
                    mp_drawing.draw_landmarks(
                        frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                    # Extraer landmarks de la mano
                    landmarks = {}
                    for point_id, landmark in enumerate(hand_landmarks.landmark):
                        landmarks[point_id] = (int(landmark.x * width), int(landmark.y * height), landmark.z)

                    # Calcular vectores direccionales para una mejor detección
                    # Vectores de la muñeca a las puntas de los dedos
                    wrist = landmarks[0]
                    thumb_tip = landmarks[4]
                    index_tip = landmarks[8]
                    middle_tip = landmarks[12]
                    ring_tip = landmarks[16]
                    pinky_tip = landmarks[20]

                    # Centro de la palma
                    palm_center = landmarks[0]  # Usar la muñeca como referencia para el centro de la palma

                    # Nudillos (MCP) de los dedos
                    thumb_mcp = landmarks[2]
                    index_mcp = landmarks[5]
                    middle_mcp = landmarks[9]
                    ring_mcp = landmarks[13]
                    pinky_mcp = landmarks[17]

                    # Base de los dedos (PIP, segunda articulación)
                    index_pip = landmarks[6]
                    middle_pip = landmarks[10]
                    ring_pip = landmarks[14]
                    pinky_pip = landmarks[18]

                    def distance(p1, p2):
                        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

                    # Verificar si un dedo está extendido usando la distancia
                    # Un dedo está extendido si la punta está significativamente más lejos de la muñeca que su base
                    thumb_extended = distance(thumb_tip, wrist) > distance(thumb_mcp, wrist) * 1.2
                    index_extended = distance(index_tip, wrist) > distance(index_pip, wrist) * 1.3
                    middle_extended = distance(middle_tip, wrist) > distance(middle_pip, wrist) * 1.3
                    ring_extended = distance(ring_tip, wrist) > distance(ring_pip, wrist) * 1.3
                    pinky_extended = distance(pinky_tip, wrist) > distance(pinky_pip, wrist) * 1.3

                    fingers_extended = [thumb_extended, index_extended, middle_extended, ring_extended, pinky_extended]

                    # Verificar dirección del pulgar (para ir a: norte, sur, este, oeste)
                    thumb_direction_x = thumb_tip[0] - wrist[0]
                    thumb_direction_y = thumb_tip[1] - wrist[1]

                    # Determinar la dirección del pulgar basado en los ángulos
                    angle_rad = np.arctan2(thumb_direction_y, thumb_direction_x)
                    angle_deg = np.degrees(angle_rad)

                    # Verificar posturas y asignar comandos

                    # Todos los 5 dedos extendidos - STOP (exactamente 5 dedos)
                    if all(fingers_extended):
                        command = "STOP"
                        command_go = "Stop"
                        socketio.emit("go", command_go)

                    # Gesto OK (pulgar e índice formando círculo) - DESPEGAR
                    # Comprobamos que la distancia entre la punta del pulgar y del índice es muy pequeña
                    elif distance(thumb_tip, index_tip) < width * 0.05:
                        # Verificamos que los otros dedos estén extendidos
                        if middle_extended and ring_extended and pinky_extended:
                            command = "DESPEGAR"
                            socketio.emit("arm_takeOff", 5)

                    # Solo pulgar extendido
                    elif thumb_extended and sum(fingers_extended[1:]) == 0:
                        # Determinar dirección basado en el ángulo
                        if -45 <= angle_deg <= 45:  # Pulgar a la izquierda (OESTE)
                            command = "OESTE"
                            command_go = "West"
                            socketio.emit("go", command_go)
                        elif 45 < angle_deg <= 135:  # Pulgar abajo (SUR)
                            command = "SUR"
                            command_go = "South"
                            socketio.emit("go", command_go)
                        elif -135 <= angle_deg < -45:  # Pulgar arriba (NORTE)
                            command = "NORTE"
                            command_go = "North"
                            socketio.emit("go", command_go)
                        elif abs(angle_deg) > 135:  # Pulgar a la derecha (ESTE)
                            command = "ESTE"
                            command_go = "East"
                            socketio.emit("go", command_go)

                    # Solo pulgar e índice extendidos - LAND
                    elif thumb_extended and index_extended and not middle_extended and not ring_extended and not pinky_extended:
                        command = "LAND"
                        socketio.emit("Land")

            # Mostrar el comando en el frame
            if command:
                print(f"Comando detectado: {command}")
                cv2.putText(frame, f"Orden: {command}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Codificar el frame procesado a base64
        _, buffer = cv2.imencode(".jpg", frame)
        processed_frame = base64.b64encode(buffer).decode("utf-8")
        return processed_frame

    except Exception as e:
        print(f"Error al procesar el frame: {e}")
        traceback.print_exc()
        return None

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
    ssl_context.load_cert_chain('public_certificate.pem', 'private_key.pem')
    
    # socketio.run() ejecuta tanto Flask como Socket.IO en el mismo puerto
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5004,
        debug=True,
        allow_unsafe_werkzeug=True,
        use_reloader=False,
        ssl_context=ssl_context
    )
    
    print('\nServidor detenido.')
