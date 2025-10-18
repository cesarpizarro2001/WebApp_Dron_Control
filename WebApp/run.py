# IMPORTANTE: Interprete Pyhton 3.9 e instalar Flask, Flask-SocketIO, mediapipe
import base64
from app import create_app
from flask_socketio import SocketIO
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
    
# Recibir telemetría de la Estación de Tierra y enviarla al navegador
@socketio.on('telemetry_data')
def handle_telemetry(data):
    # Reenviar telemetría a todos los clientes web conectados
    socketio.emit('telemetry_info', data, include_self=False)

# Recibir eventos de la Estación de Tierra
@socketio.on('flight_event')
def handle_flight_event(data):
    event_type = data.get('event')
    print(f"Evento de vuelo: {event_type}")
    
    if event_type == 'flight_name_set':
        socketio.emit('flight_name_set', data.get('name'), broadcast=True)
    elif event_type == 'foto_capturada':
        socketio.emit('foto_capturada', data.get('filename'), broadcast=True)
    elif event_type == 'video_iniciado':
        socketio.emit('video_iniciado', data.get('filename'), broadcast=True)
    elif event_type == 'video_detenido':
        socketio.emit('video_detenido', broadcast=True)
    elif event_type == 'video_error':
        socketio.emit('video_error', data.get('message'), broadcast=True)

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
