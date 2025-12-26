# IMPORTANTE: Interprete Pyhton 3.9 e instalar pymavlink, opencv-python, python-socketio, requests, websocket-client, pillow, pyserial (para conectar a Dron Real)
import json
import tkinter as tk
from dronLink.Dron import Dron
import random
import socketio
import cv2
import base64
import threading
import os
import time
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk
from tkinter import ttk
import numpy as np
import yaml
import re
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc import RTCConfiguration, RTCIceServer
from av import VideoFrame
from ultralytics import YOLO


def allowExternal():
    global sio
    global allowExternalBtn
    global webapp_commands_enabled
    global videoWebsocketBtn
    global galleryBtn
    global cameraBtn
    
    # Activar el procesamiento de comandos desde la WebApp
    webapp_commands_enabled = True
    print('WebApp AUTORIZADA: Los comandos desde la web serán procesados')
    allowExternalBtn['text'] = "WebApp autorizada"
    allowExternalBtn['fg'] = 'white'
    allowExternalBtn['bg'] = 'green'
    
    # Habilitar los 3 botones de debajo (restaurar comandos y colores)
    videoWebsocketBtn['command'] = videoWebsockets
    videoWebsocketBtn['bg'] = 'violet'
    videoWebsocketBtn['state'] = 'normal'
    
    galleryBtn['command'] = open_gallery
    galleryBtn['bg'] = 'violet'
    galleryBtn['state'] = 'normal'
    
    cameraBtn['command'] = recibirCamara
    cameraBtn['bg'] = 'violet'
    cameraBtn['state'] = 'normal'

def procesarTelemetria(telemetryInfo):
    # Enviar telemetría por WebRTC Data Channels a todos los receptores conectados
    import json
    import asyncio
    telemetry_json = json.dumps(telemetryInfo)
    
    sent_via_webrtc = False
    
    # Función asíncrona para enviar por data channel
    async def send_to_channel(channel, data):
        try:
            channel.send(data)
        except Exception as e:
            print(f"Error enviando telemetría por Data Channel: {e}")
            raise
    
    # Enviar a todos los data channels activos
    for connection_id, channel in list(webrtc_data_channels.items()):
        try:
            if channel.readyState == 'open':
                # Ejecutar send en el event loop de WebRTC
                if webrtc_event_loop and webrtc_event_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        send_to_channel(channel, telemetry_json),
                        webrtc_event_loop
                    )
                    sent_via_webrtc = True
        except Exception as e:
            # Si falla, remover del diccionario
            if connection_id in webrtc_data_channels:
                del webrtc_data_channels[connection_id]
    
    # Fallback: Si no hay data channels activos, usar Socket.IO
    if not sent_via_webrtc:
        try:
            sio.emit('telemetry_data', telemetryInfo)
        except Exception:
            pass

def publish_event(event):
    # Publicar evento al servidor Flask
    print(f'Evento: {event}')
    sio.emit('flight_event', {'event': event})


# ========================================================================
# WEBRTC - Emisor de video del dron
# ========================================================================

# Cola de frames compartida para WebRTC (todas las instancias de DronCameraTrack la usan)
webrtc_shared_frame_queue = []
webrtc_shared_queue_lock = threading.Lock()

class DronCameraTrack(VideoStreamTrack):
    """
    VideoStreamTrack para transmitir frames de la cámara del dron vía WebRTC.
    Similar a CameraVideoTrack del ejemplo de tu profesor, pero adaptado
    para usar los frames que ya captura video_Websocket_thread().
    
    IMPORTANTE: Cada conexión debe tener su PROPIA INSTANCIA de este track.
    No se puede compartir el mismo track entre múltiples RTCPeerConnection.
    """
    kind = "video"
    
    def __init__(self):
        super().__init__()
        self.last_frame = None
    
    async def recv(self):
        """
        Método requerido por VideoStreamTrack.
        Devuelve el siguiente frame disponible para WebRTC.
        """
        pts, time_base = await self.next_timestamp()
        
        # Obtener frame de la cola COMPARTIDA
        with webrtc_shared_queue_lock:
            if len(webrtc_shared_frame_queue) > 0:
                frame_bgr = webrtc_shared_frame_queue[0]  # Leer sin eliminar (múltiples tracks)
                # Convertir BGR (OpenCV) a RGB (WebRTC)
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                self.last_frame = frame_rgb
            elif self.last_frame is not None:
                # Reutilizar último frame si no hay nuevo
                frame_rgb = self.last_frame
            else:
                # Si no hay ningún frame, crear uno negro
                frame_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Convertir a formato VideoFrame de aiortc
        video_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        
        return video_frame


def push_webrtc_frame(frame):
    """
    Agregar un frame a la cola compartida (llamado desde video_Websocket_thread).
    Todas las instancias de DronCameraTrack leerán de esta cola.
    
    Args:
        frame: Frame de OpenCV (numpy array BGR)
    """
    with webrtc_shared_queue_lock:
        # Mantener solo el frame más reciente (no acumular)
        webrtc_shared_frame_queue.clear()
        webrtc_shared_frame_queue.append(frame)


# Variables globales para WebRTC
webrtc_peer_connections = {}  # {connection_id: RTCPeerConnection}
webrtc_data_channels = {}  # {connection_id: RTCDataChannel} para telemetría
webrtc_event_loop = None  # Event loop de asyncio para WebRTC
webrtc_thread = None  # Thread del event loop
webrtc_keepalive_thread = None  # Thread para re-registro periódico
webrtc_keepalive_running = False
webrtc_emitter_registered = False  # Estado de registro del emisor
webrtc_socket_connected = False    # Estado de conexión Socket.IO


def start_webrtc_emitter():
    """
    Inicia el emisor WebRTC en un thread separado.
    Similar a la lógica de senderGlobalWebRTC.py
    """
    global webrtc_event_loop, webrtc_thread, yolo_model
    
    if webrtc_event_loop is not None:
        print("⚠️  Emisor WebRTC ya está en ejecución")
        return
    
    # Cargar modelo YOLO
    if yolo_model is None:
        try:
            print("📦 Cargando modelo YOLO...")
            yolo_model = YOLO('yolov8m.pt')  # Modelo medium (alta precisión)
            print("✅ Modelo YOLO cargado correctamente")
        except Exception as e:
            print(f"❌ Error cargando YOLO: {e}")
            yolo_model = None
    
    # NO crear track aquí - se crean instancias nuevas por cada conexión
    
    # Crear y arrancar event loop en thread separado
    def run_event_loop():
        global webrtc_event_loop
        webrtc_event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(webrtc_event_loop)
        print("📡 [WebRTC] Event loop iniciado")
        webrtc_event_loop.run_forever()
    
    webrtc_thread = threading.Thread(target=run_event_loop, daemon=True)
    webrtc_thread.start()
    
    # Registrarse como emisor en el servidor (una sola vez)
    try:
        sio.emit('webrtc_register_emitter', {'stream_id': 'dron_camera'})
        webrtc_emitter_registered = True
        print("📡 [WebRTC] Emisor registrado: dron_camera")
    except Exception as e:
        print(f"❌ [WebRTC] Error al registrar emisor: {e}")


def stop_webrtc_emitter():
    """
    Detiene el emisor WebRTC y cierra todas las conexiones.
    """
    global webrtc_event_loop, webrtc_peer_connections
    
    if webrtc_event_loop is None:
        return
    
    print("📡 [WebRTC] Deteniendo emisor...")

    # Avisar al servidor que detenemos el streaming
    try:
        sio.emit('webrtc_stop_streaming', {'stream_id': 'dron_camera'})
    except Exception:
        pass

    # Detener keepalive (ya no se usa)
    global webrtc_keepalive_running
    webrtc_keepalive_running = False
    
    # Cerrar todas las conexiones peer
    async def close_all_peers():
        for conn_id, pc in list(webrtc_peer_connections.items()):
            await pc.close()
            del webrtc_peer_connections[conn_id]
    
    if len(webrtc_peer_connections) > 0:
        asyncio.run_coroutine_threadsafe(close_all_peers(), webrtc_event_loop)
        time.sleep(0.5)  # Dar tiempo para cerrar
    
    # Detener event loop
    webrtc_event_loop.call_soon_threadsafe(webrtc_event_loop.stop)
    webrtc_event_loop = None
    # Marcar emisor como no registrado
    global webrtc_emitter_registered
    webrtc_emitter_registered = False
    
    print("📡 [WebRTC] Emisor detenido")


# Variables globales para el modo de conexión
connection_mode = "simulation"  # Por defecto simulación
com_port = "com"  # Puerto COM por defecto

# Variable global para controlar si se aceptan comandos de la WebApp
webapp_commands_enabled = False

# Variable global para controlar mensajes de estado únicos
last_printed_state = None

# Variables globales para detección de objetos
yolo_model = None
detection_enabled = False

# Variables globales para corrección de ojo de pez (fisheye)
fisheye_enabled = False
fisheye_ready = False  # indica si new_cam_mtx y roi están calculados para el tamaño actual
cam_matrix = None
dist_coefs = None
new_cam_mtx = None
roi = None  # (x, y, w, h)

# Variables globales para zoom
zoom_level = 1.0  # 1.0 = sin zoom, 2.0 = 2x zoom, etc.
zoom_center = None  # (x, y) en coordenadas de píxeles del frame
zoom_lock = threading.Lock()

# Ruta por defecto del archivo de calibración (editable)
# Se usará el archivo ubicado directamente en la carpeta EstacionTierra
default_calibration_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calibration_data_px.yaml')

# Límites de altura de seguridad
ALTURA_MINIMA = 2   # metros
ALTURA_MAXIMA = 10  # metros


# Función para deshabilitar botones virtualmente
def deshabilitar_boton(boton, modo_disconnect="desconectado"):
    """
    Deshabilita un botón sin usar el estado 'disabled' de tkinter.
    El botón se vuelve semitransparente y no responde a clics.
    
    Para disconnectBtn:
    - modo_disconnect="desconectado" → "Desconectado" (gris)
    - modo_disconnect="funcionando" → "Aterrizar para Desconectar" (semitransparente)
    """
    # Función vacía que no hace nada
    def comando_vacio():
        pass
    
    # Cambiar el comando a la función vacía
    boton['command'] = comando_vacio
    
    # Caso especial para el botón disconnect
    if boton == disconnectBtn:
        if modo_disconnect == "desconectado":
            boton['text'] = "Desconectado"
            boton['bg'] = "gray"
            boton['fg'] = "white"
        elif modo_disconnect == "funcionando":
            boton['text'] = "Aterriza y desarma para Desconectar"
            bg_deshabilitado = crear_color_semitransparente(boton['bg'])
            fg_deshabilitado = crear_color_semitransparente(boton['fg'])
            boton['bg'] = bg_deshabilitado
            boton['fg'] = fg_deshabilitado
    else:
        # Aplicar efecto visual semitransparente para otros botones
        bg_deshabilitado = crear_color_semitransparente(boton['bg'])
        fg_deshabilitado = crear_color_semitransparente(boton['fg'])
        
        boton['bg'] = bg_deshabilitado
        boton['fg'] = fg_deshabilitado

# Función para habilitar botones - los devuelve a su estado inicial
def habilitar_boton(boton):
    """
    Habilita un botón devolviéndolo a su estado inicial específico.
    """
    # Determinar qué botón es y restaurarlo a su estado inicial
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
        
    elif boton == NorthBtn:
        boton['text'] = "Norte"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = lambda: dron.go('North')
        
    elif boton == SouthBtn:
        boton['text'] = "Sur"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = lambda: dron.go('South')
        
    elif boton == EastBtn:
        boton['text'] = "Este"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = lambda: dron.go('East')
        
    elif boton == WestBtn:
        boton['text'] = "Oeste"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = lambda: dron.go('West')
        
    elif boton == StopBtn:
        boton['text'] = "Parar"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = lambda: dron.go('Stop')
        
    elif boton == RTLBtn:
        boton['text'] = "RTL"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = lambda: rtl_with_feedback()
        
    elif boton == disconnectBtn:
        boton['text'] = "Desconectar"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = desconectar_con_feedback
        
    elif boton == connectBtn:
        boton['text'] = "Conectar"
        boton['bg'] = "dark orange"
        boton['fg'] = "black"
        boton['command'] = conectar_local

# Función auxiliar para crear colores semitransparentes
def crear_color_semitransparente(color):
    """
    Convierte los colores 'dark orange' y 'violet' a versiones más claras y transparentes.
    Para otros colores, los devuelve sin cambios.
    """
    if color.lower() == 'dark orange':
        return '#FFD4B3'  # Naranja muy claro y transparente
    elif color.lower() == 'violet':
        return '#E6D0FF'  # Violeta muy claro y transparente
    
    # Para cualquier otro color, devolverlo sin cambios
    return color

# Ejecuta el botón para conectar de la Estacion de Tierra en el modo que escojamos
def conectar_local():
    # Cambiar el botón a estado "conectando..."
    connectBtn['text'] = "Conectando..."
    connectBtn['bg'] = "yellow"
    connectBtn['fg'] = "black"
    connectBtn.update()  # Forzar la actualización visual
    
    def connection_callback():
        # Esta función se ejecutará cuando la conexión sea exitosa
        connectBtn['text'] = "Conectado"
        connectBtn['bg'] = "green"
        connectBtn['fg'] = "white"
        
        # Deshabilitar funcionalmente el botón de conectar (mantener apariencia pero sin función)
        def comando_vacio():
            pass
        connectBtn['command'] = comando_vacio
        
        # Habilitar botones necesarios tras la conexión
        habilitar_boton(armBtn)  # Permitir armar el dron
        habilitar_boton(disconnectBtn)  # Permitir desconectar
        
        # Configurar callbacks automáticos para el estado del dron
        setup_arm_state_monitoring()
    
    def connection_error_callback():
        # Esta función se ejecutará si hay error en la conexión
        connectBtn['text'] = "Error - Conectar"
        connectBtn['bg'] = "red"
        connectBtn['fg'] = "white"
    
    try:
        if connection_mode == "simulation":
            result = dron.connect('tcp:127.0.0.1:5763', 115200)
            print('Conectando localmente en modo SIMULACIÓN')
        else:
            result = dron.connect(com_port, 57600)
            print(f'Conectando localmente en modo PRODUCCIÓN en puerto {com_port.upper()}')
        
        # Verificar si la conexión fue exitosa
        if hasattr(dron, 'state') and dron.state == 'connected':
            connection_callback()
        elif result:  # Si el método connect retorna True
            connection_callback()
        else:
            connection_error_callback()
            
    except Exception as e:
        print(f"Error al conectar: {e}")
        connection_error_callback()

# Ejecuta el botón para armar el dron con monitoreo por eventos
def armar_dron():
    # Cambiar el botón a estado "armando"
    armBtn['text'] = "Armando..."
    armBtn['bg'] = "yellow"
    armBtn['fg'] = "black"
    armBtn.update()  # Forzar la actualización visual
    
    try:
        result = dron.arm()
        print('Comando de armado enviado')
        
        # Implementar timeout de seguridad
        def timeout_check():
            if armBtn['text'] == "Armando...":
                print('Timeout: El dron no se armó en 5 segundos')
                armBtn['text'] = "Error - Armar"
                armBtn['bg'] = "red"
                armBtn['fg'] = "white"

        # Programar timeout en 5 segundos
        ventana.after(5000, timeout_check)

    except Exception as e:
        print(f"Error al armar: {e}")
        # Error al armar
        armBtn['text'] = "Error - Armar"
        armBtn['bg'] = "red"
        armBtn['fg'] = "white"

# Funciones para manejo de eventos del botón armar
def setup_arm_state_monitoring():
    """Configura los callbacks para monitorear el estado del dron automáticamente"""
    if dron and hasattr(dron, 'message_handler') and dron.message_handler:
        # Registrar callback para heartbeat (cambios de estado)
        dron.message_handler.register_handler('HEARTBEAT', on_drone_state_change)
        print('Callbacks de estado del dron configurados')
    else:
        print('No se puede configurar monitoreo: dron no conectado')

def on_drone_state_change(msg):
    """Callback que se ejecuta automáticamente cuando cambia el estado del dron"""
    global last_printed_state
    
    if not dron:
        return
        
    current_state = dron.state
    
    # Usar after() para actualizar UI desde el thread principal
    def update_ui():
        global last_printed_state
        
        if current_state == 'armed' and armBtn['text'] == "Armando...":
            print('Dron ARMADO')
            armBtn['text'] = "Armado"
            armBtn['bg'] = "green"
            armBtn['fg'] = "white"
            
            # Habilitar el botón despegar cuando el dron se arme
            habilitar_boton(takeOffBtn)
            # Deshabilitar desconectar cuando el dron esté armado (seguridad)
            deshabilitar_boton(disconnectBtn, "funcionando")
            last_printed_state = 'armed'
            
        elif current_state in ['takingOff'] and armBtn['text'] in ["Armado", "Armando..."]:
            # Solo imprimir si es la primera vez que entra en este estado
            if last_printed_state != 'takingOff':
                print(f'Dron despegando: {current_state}')
                last_printed_state = 'takingOff'
                
            # El botón armar mantiene "Armado" pero se deshabilita funcionalmente
            armBtn['text'] = "Armado"
            armBtn['bg'] = "green"
            armBtn['fg'] = "white"
            
            # Deshabilitar funcionalmente los botones armar y despegar (mantener apariencia pero sin función)
            def comando_vacio():
                pass
            armBtn['command'] = comando_vacio
            takeOffBtn['command'] = comando_vacio
            
            # Actualizar botón despegar
            takeOffBtn['text'] = "Despegando..."
            takeOffBtn['bg'] = "yellow"
            takeOffBtn['fg'] = "black"
            
            # Mantener desconectar deshabilitado mientras despega (seguridad)
            deshabilitar_boton(disconnectBtn, "funcionando")
            
        elif current_state in ['flying']:
            # Solo imprimir si es la primera vez que entra en este estado
            if last_printed_state != 'flying':
                print(f'Dron VOLANDO')
                last_printed_state = 'flying'
                
            # Actualizar botón despegar a "Volando"
            takeOffBtn['text'] = "Volando"
            takeOffBtn['bg'] = "green"
            takeOffBtn['fg'] = "white"
            
            # AHORA SÍ habilitar los botones de movimiento (solo cuando está volando)
            habilitar_boton(NorthBtn)   # Norte
            habilitar_boton(SouthBtn)   # Sur
            habilitar_boton(EastBtn)    # Este
            habilitar_boton(WestBtn)    # Oeste
            habilitar_boton(StopBtn)    # Parar
            habilitar_boton(RTLBtn)     # RTL
            # Mantener desconectar deshabilitado mientras vuela (seguridad)
            deshabilitar_boton(disconnectBtn, "funcionando")
            
        elif current_state == 'connected' and armBtn['text'] in ["Armado", "Armando..."]:
            # Solo imprimir si es la primera vez que entra en este estado
            if last_printed_state != 'connected':
                print('Dron desarmado - regresando al estado conectado')
                last_printed_state = 'connected'
            
            # Si el RTL estaba activo, el dron completó una misión - reseteo completo
            if RTLBtn['text'] == "Volviendo a Base...":
                print('Misión RTL completada - reseteo completo del sistema')
                RTLBtn['text'] = "Aterrizado"
                RTLBtn['bg'] = "green"
                RTLBtn['fg'] = "white"
                
                # Programar secuencia: habilitar y luego deshabilitar RTL después de 3 segundos
                def reset_and_disable_rtl():
                    habilitar_boton(RTLBtn)  # Restaurar estado original
                    ventana.after(0, lambda: deshabilitar_boton(RTLBtn))  # Deshabilitar tras 0ms
                
                ventana.after(3000, reset_and_disable_rtl)
                
                # RESETEAR COMPLETAMENTE AL ESTADO "CONECTADO" (tras vuelo/misión)
                # 1. Restaurar botón armar a su estado inicial
                habilitar_boton(armBtn)
                habilitar_boton(disconnectBtn)
                
                # 2. Restaurar botón despegar al estado inicial y luego deshabilitarlo
                habilitar_boton(takeOffBtn)
                deshabilitar_boton(takeOffBtn)  # Deshabilitarlo hasta próximo armado
                
                # 3. Deshabilitar todos los botones de vuelo
                deshabilitar_boton(NorthBtn)
                deshabilitar_boton(SouthBtn)
                deshabilitar_boton(EastBtn)
                deshabilitar_boton(WestBtn)
                deshabilitar_boton(StopBtn)
                
            else:
                # Desarme simple (timeout) - solo resetear armar y despegar
                print('Desarme por timeout')
                habilitar_boton(armBtn)
                deshabilitar_boton(takeOffBtn)  # Mantener despegar deshabilitado
                habilitar_boton(disconnectBtn)
    
    # Ejecutar actualización en el thread principal de tkinter
    ventana.after(0, update_ui)

# Ejecuta el botón para despegar con feedback visual
def despegar_dron():
    # Cambiar el botón a estado "despegando..."
    takeOffBtn['text'] = "Despegando..."
    takeOffBtn['bg'] = "yellow"
    takeOffBtn['fg'] = "black"
    takeOffBtn.update()  # Forzar la actualización visual
    
    def takeoff_callback():
        # Esta función se ejecutará cuando el despegue sea exitoso
        takeOffBtn['text'] = "Volando"
        takeOffBtn['bg'] = "green"
        takeOffBtn['fg'] = "white"
    
    def takeoff_error_callback():
        # Esta función se ejecutará si hay error en el despegue
        takeOffBtn['text'] = "Error - Despegar"
        takeOffBtn['bg'] = "red"
        takeOffBtn['fg'] = "white"
    
    try:
        # Usar takeOff con callback no bloqueante
        result = dron.takeOff(3, blocking=False, callback=takeoff_callback)
        
        # Verificar si el despegue se inició correctamente
        if hasattr(dron, 'state'):
            # Dar un momento para que se actualice el estado
            time.sleep(0.5)
            if dron.state in ['takingOff', 'flying']:
                print('Despegue iniciado correctamente')
                # El callback se encargará de actualizar el botón cuando termine
            else:
                print('El dron no cambió a estado de despegue')
                takeoff_error_callback()
        else:
            # Si no tenemos estado, asumir que se inició bien
            print('Comando de despegue enviado')
            
    except Exception as e:
        print(f"Error al despegar: {e}")
        takeoff_error_callback()

# Función para ejecutar RTL con feedback visual
def rtl_with_feedback():
    if dron.state == 'flying':
        # Cambiar el botón a estado "volviendo a base..."
        RTLBtn['text'] = "Volviendo a Base..."
        RTLBtn['bg'] = "yellow"
        RTLBtn['fg'] = "black"
        RTLBtn.update()  # Forzar la actualización visual
        
        try:
            # Ejecutar RTL en modo no bloqueante
            dron.RTL(blocking=False)
            print('Comando RTL enviado')
            
        except Exception as e:
            print(f"Error al ejecutar RTL: {e}")
            # Error al ejecutar RTL
            RTLBtn['text'] = "Error - RTL"
            RTLBtn['bg'] = "red"
            RTLBtn['fg'] = "white"
            # Restaurar después de 3 segundos
            ventana.after(3000, lambda: habilitar_boton(RTLBtn))

# Función para desconectar con feedback visual
def desconectar_con_feedback():
    # Cambiar el botón a estado "desconectando..."
    disconnectBtn['text'] = "Desconectando..."
    disconnectBtn['bg'] = "yellow"
    disconnectBtn['fg'] = "black"
    disconnectBtn.update()  # Forzar la actualización visual
    
    try:
        # Detener el message handler ANTES de desconectar para evitar errores de socket
        if hasattr(dron, 'message_handler') and dron.message_handler:
            print('Deteniendo message handler...')
            dron.message_handler.stop()
            dron.message_handler = None
        
        result = dron.disconnect()
        if result:
            print('Desconexión exitosa')
            # Cambiar el botón a estado desconectado
            deshabilitar_boton(disconnectBtn, "desconectado")
            
            # Resetear todos los botones al estado inicial
            habilitar_boton(connectBtn)
            
            # Deshabilitar todos los demás botones
            deshabilitar_boton(armBtn)
            deshabilitar_boton(takeOffBtn)
            deshabilitar_boton(NorthBtn)
            deshabilitar_boton(SouthBtn)
            deshabilitar_boton(EastBtn)
            deshabilitar_boton(WestBtn)
            deshabilitar_boton(StopBtn)
            deshabilitar_boton(RTLBtn)
            deshabilitar_boton(disconnectBtn, "desconectado")
            
        else:
            print('Error: No se pudo desconectar')
            disconnectBtn['text'] = "Error - Desconectar"
            disconnectBtn['bg'] = "red"
            disconnectBtn['fg'] = "white"
            
    except Exception as e:
        print(f"Error al desconectar: {e}")
        disconnectBtn['text'] = "Error - Desconectar"
        disconnectBtn['bg'] = "red"
        disconnectBtn['fg'] = "white"

# Ejecuta el botón para permitir conectar la WebApp en el modo que escojamos
def toggle_connection_mode():
    global connection_mode, modeBtn, com_port

    if connection_mode == "simulation":
        # Pedir el puerto COM al usuario
        com_window = tk.Toplevel(ventana)
        com_window.title("Configurar Puerto COM")
        com_window.geometry("300x150")
        com_window.resizable(False, False)

        # Centrar la ventana
        com_window.transient(ventana)
        com_window.grab_set()

        tk.Label(com_window, text="Introduce el puerto COM para el dron:\n(Ejemplos: COM3, com3, COM1, com1)", pady=10, justify="center").pack()

        com_entry = tk.Entry(com_window, width=20, font=("Arial", 12))
        com_entry.pack(pady=10)
        com_entry.insert(0, com_port)  # Valor actual por defecto
        com_entry.focus()

        def confirm_com():
            global connection_mode, com_port
            new_com = com_entry.get().strip()

            # Verificar que el formato sea correcto (COM o com seguido de números)
            import re
            if new_com and re.match(r'^(COM|com)\d+$', new_com):
                com_port = new_com.lower()  # Guardar siempre en minúsculas para consistencia interna
                connection_mode = "production"
                modeBtn['text'] = f"Modo: PRODUCCIÓN ({new_com.upper()})"  # Mostrar siempre en mayúsculas
                modeBtn['fg'] = 'white'
                modeBtn['bg'] = 'red'
                com_window.destroy()
            else:
                messagebox.showerror("Error","Por favor introduce un puerto COM válido\n(Ejemplos: COM3, com3, COM1, com1)")

        def cancel_com():
            com_window.destroy()

        # Frame para los botones
        btn_frame = tk.Frame(com_window)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Confirmar", bg="green", fg="white", command=confirm_com).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancelar", bg="red", fg="white", command=cancel_com).pack(side=tk.LEFT, padx=5)

        # Permitir confirmar con Enter
        com_entry.bind('<Return>', lambda e: confirm_com())

    else:
        connection_mode = "simulation"
        modeBtn['text'] = "Modo: SIMULACIÓN"
        modeBtn['fg'] = 'black'
        modeBtn['bg'] = 'light blue'

# aqui recibimos los mensajes de la WebApp via Socket.IO
def on_command_received(data):
    """Procesa comandos recibidos del servidor Flask via Socket.IO"""
    # Declarar todos los globals usados/modificados por las ramas de este handler
    global dron, pilot_mode_active, pilot_rc_thread, last_rc_command_time
    
    action = data.get('action')
    print(f'Comando recibido: {action}')
    
    if action == 'connect':
        print('Conectando desde WebApp')
            
        # Selecciono los parámetros según el modo
        if connection_mode == "simulation":
            connection_string = 'tcp:127.0.0.1:5763'
            baud = 115200
            print('Conectando en modo SIMULACIÓN')
        else:
            connection_string = com_port
            baud = 57600
            print(f'Conectando en modo PRODUCCIÓN en puerto {com_port.upper()}')

        try:
            result = dron.connect(connection_string, baud)
            print('Conectado desde WebApp')
                
            print('Solicitando datos de telemetría')
            dron.send_telemetry_info(procesarTelemetria)
            
        except Exception as e:
            print(f'Error al conectar desde WebApp: {e}')
            import traceback
            traceback.print_exc()

    elif action == 'arm_takeOff':
        if dron.state == 'connected':
            alt = int(data.get('altura', 5))
            pilot_mode = data.get('pilot_mode', False)  # Detectar si es modo piloto
            
            print(f'Armando y despegando desde WebApp a {alt}m')
            dron.arm()
            print('Armado desde WebApp')
            
            if pilot_mode:
                print('Modo piloto detectado - cambiando a LOITER después del despegue')
                
                # Callback para cambiar a LOITER cuando llegue a la altura
                def on_flying_for_pilot(event):
                    global pilot_mode_active, pilot_rc_thread, last_rc_command_time
                    
                    if event == 'flying':
                        print('Dron volando - esperando estabilización...')
                        # Esperar 1 segundo para que el dron se estabilice en la altura
                        time.sleep(1)
                        
                        # PRIMERO: Iniciar el loop RC (antes de cambiar a LOITER)
                        print('Iniciando loop RC...')
                        pilot_mode_active = True
                        last_rc_command_time = time.time()  # Inicializar para evitar timeout inmediato
                        pilot_rc_thread = threading.Thread(target=pilot_rc_loop, daemon=True)
                        pilot_rc_thread.start()
                        
                        # Dar tiempo al thread para arrancar
                        time.sleep(0.2)
                        print('Loop RC activo')
                        
                        # SEGUNDO: Ahora sí, cambiar a LOITER
                        print('Cambiando a modo LOITER para control RC')
                        dron.setFlightMode('LOITER')
                        print('Modo LOITER activado - joysticks listos para uso')
                
                dron.takeOff(alt, blocking=False, callback=on_flying_for_pilot, params='flying')
            else:
                # Modo normal (control.html)
                dron.takeOff(alt, blocking=False, callback=publish_event, params='flying')

    elif action == 'go':
        if dron.state == 'flying':
            direction = data.get('direction')
            print(f'Moviendo al: {direction}')
            dron.go(direction)

    elif action == 'Land':
        if dron.state == 'flying':
            print('Aterrizando desde WebApp')
            dron.Land(blocking=False)

    elif action == 'RTL':
        if dron.state == 'flying':
            print('Ejecutando RTL desde WebApp')
            dron.RTL(blocking=False)

    elif action == 'goto':
        if dron.state == 'flying':
            try:
                lat = float(data.get('lat'))
                lng = float(data.get('lng'))
                print(f'Moviendo dron a: lat={lat}, lon={lng}')
                dron.goto(lat, lng, dron.alt, blocking=False)
            except Exception as e:
                print(f"Error en goto: {str(e)}")

    elif action == 'change_altitude':
        if dron.state == 'flying':
            try:
                altitude_change = float(data.get('altitude', 0))
                new_altitude = dron.alt + altitude_change
                print(f'Ajustando altitud: {altitude_change}m (nueva altitud: {new_altitude}m)')
                dron.goto(dron.lat, dron.lon, new_altitude, blocking=False)
            except Exception as e:
                print(f"Error al cambiar altitud: {str(e)}")

    elif action == 'change_mode':
        try:
            mode = data.get('mode', 'LOITER')
            
            # Si se cambia a LOITER, PRIMERO iniciar el loop RC (antes del cambio de modo)
            if mode == 'LOITER':
                if not pilot_mode_active:
                    print('⚡ INICIANDO loop RC ANTES de cambiar a LOITER (prevención de caída)')
                    pilot_mode_active = True
                    last_rc_command_time = time.time()
                    if pilot_rc_thread is None or not pilot_rc_thread.is_alive():
                        pilot_rc_thread = threading.Thread(target=pilot_rc_loop, daemon=True)
                        pilot_rc_thread.start()
                    # Esperar brevemente a que el thread arranque
                    time.sleep(0.1)
                    print('✅ Loop RC activo - ahora cambiando a LOITER')
            
            print(f'Cambiando modo a: {mode}')
            dron.setFlightMode(mode)
            
        except Exception as e:
            print(f"Error al cambiar modo: {str(e)}")
    
    elif action == 'enable_pilot_mode':
        """Comando específico para activar modo piloto: inicia RC loop y luego cambia a LOITER"""
        try:
            
            print('🎮 Activando modo piloto desde control.html')
            
            # PRIMERO: Iniciar loop RC
            if not pilot_mode_active:
                print('  1️⃣ Iniciando loop RC...')
                pilot_mode_active = True
                last_rc_command_time = time.time()
                if pilot_rc_thread is None or not pilot_rc_thread.is_alive():
                    pilot_rc_thread = threading.Thread(target=pilot_rc_loop, daemon=True)
                    pilot_rc_thread.start()
                # Esperar a que el loop esté activo
                time.sleep(0.15)
                print('  ✅ Loop RC activo y enviando valores neutrales')
            
            # SEGUNDO: Cambiar a LOITER
            print('  2️⃣ Cambiando a modo LOITER...')
            dron.setFlightMode('LOITER')
            print('  ✅ Modo piloto activado correctamente')
            
        except Exception as e:
            print(f"❌ Error al activar modo piloto: {str(e)}")

    elif action == 'capturarFoto':
        print('Capturando foto del último frame')
        capturar_foto()

    elif action == 'iniciarVideo':
        print('Iniciando grabación de video')
        start_recording()

    elif action == 'detenerVideo':
        print('Deteniendo grabación de video')
        stop_recording()

    elif action == 'waypointRuta':
        if dron.state == 'flying':
            try:
                waypoints = data.get('waypoints', [])

                def recorrer_ruta():
                    for idx, wp in enumerate(waypoints):
                        lat = wp["lat"]
                        lng = wp["lng"]
                        captura = wp.get("captura", "ninguna")
                        duracion = int(wp.get("duracion", 0))

                        print(f"[{idx + 1}/{len(waypoints)}] Moviendo a waypoint: ({lat}, {lng})")

                        dron.goto(lat, lng, dron.alt, blocking=False)

                        tiempo_max_espera = 30
                        tiempo_inicio = time.time()

                        while time.time() - tiempo_inicio < tiempo_max_espera:
                            try:
                                dist = dron._distanceToDestinationInMeters(lat, lng)
                                if dist <= 1.0:
                                    print(f"El dron ha llegado al waypoint {idx + 1}")
                                    break
                            except:
                                dlat = abs(dron.lat - lat)
                                dlon = abs(dron.lon - lng)
                                if dlat < 0.00001 and dlon < 0.00001:
                                    break

                            time.sleep(0.5)

                        time.sleep(1)

                        if captura == "foto":
                            print(f"Capturando foto en waypoint {idx + 1}")
                            success = capturar_foto()
                            if success:
                                print(f"Foto {idx + 1} guardada correctamente")
                            else:
                                print(f"Error al capturar foto en waypoint {idx + 1}")
                            time.sleep(1)

                        elif captura == "video":
                            print(f"Iniciando grabación de video en waypoint {idx + 1} por {duracion} seg")
                            success = start_recording()
                            if success:
                                time.sleep(duracion)
                                stop_recording()
                                print(f"Video de {duracion}s completado en waypoint {idx + 1}")
                            else:
                                print(f"Error al iniciar video en waypoint {idx + 1}")
                            time.sleep(1)

                    print("Ruta completada")

                threading.Thread(target=recorrer_ruta).start()

            except Exception as e:
                print(f"Error en la ruta: {e}")

    elif action == 'toggle_detection':
        """Toggle de detección de objetos"""
        global detection_enabled
        detection_enabled = data.get('enabled', False)
        status = "ACTIVADA" if detection_enabled else "DESACTIVADA"
        print(f"🔍 Detección de objetos: {status}")
        
        if detection_enabled and yolo_model is None:
            print("⚠️  Modelo YOLO no cargado")

# Recibir video de la cámara del dron por websockets
def videoWebsockets():
    global sendingWebsockets
    global videoWebsocketBtn
    global current_flight_name
    global showing_video

    if sendingWebsockets:
        sendingWebsockets = False
        showing_video = False

        # Liberar la cámara
        release_camera()

        videoWebsocketBtn['text'] = "Activar cámara dron"
        videoWebsocketBtn['fg'] = 'black'
        videoWebsocketBtn['bg'] = 'violet'
        # Cerrar ventana de video si está abierta
        close_video_display()

    else:
        # Crea una ventana para pedir el nombre del vuelo
        flight_name_window = tk.Toplevel(ventana)
        flight_name_window.title("Nombre del Vuelo")
        flight_name_window.geometry("300x150")

        tk.Label(flight_name_window, text="Introduce un nombre para este vuelo:", pady=10).pack()
        flight_name_entry = tk.Entry(flight_name_window, width=30)
        flight_name_entry.pack(pady=10)

        # Función para iniciar el stream de video después de obtener el nombre
        def start_video_stream():
            global current_flight_name, sendingWebsockets, showing_video
            name = flight_name_entry.get().strip()
            if name:
                # Sanitizar el nombre: reemplazar caracteres problemáticos
                # Reemplazar / y \ por guiones para evitar crear carpetas anidadas
                name = name.replace('/', '-').replace('\\', '-')
                # También reemplazar otros caracteres problemáticos en nombres de archivo
                name = name.replace(':', '-').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
                
                current_flight_name = name
                # Crea directorios si no existen
                if not os.path.exists("captured_photos"):
                    os.makedirs("captured_photos")
                if not os.path.exists("captured_videos"):
                    os.makedirs("captured_videos")

                # Crea las subcarpetas para este vuelo
                photos_flight_dir = os.path.join("captured_photos", current_flight_name)
                videos_flight_dir = os.path.join("captured_videos", current_flight_name)

                if not os.path.exists(photos_flight_dir):
                    os.makedirs(photos_flight_dir)
                if not os.path.exists(videos_flight_dir):
                    os.makedirs(videos_flight_dir)

                flight_name_window.destroy()

                # Inicia el video
                sendingWebsockets = True
                showing_video = True

                # Crear ventana de visualización
                create_video_display()

                # Iniciar threads
                threading.Thread(target=video_Websocket_thread).start()
                threading.Thread(target=update_video_display).start()

                # Actualiza el botón
                videoWebsocketBtn['text'] = "Detener cámara dron"
                videoWebsocketBtn['fg'] = 'white'
                videoWebsocketBtn['bg'] = 'green'

                # Publica mensaje con el nombre del vuelo
                sio.emit('flight_event', {'event': 'flight_name_set', 'name': current_flight_name})
            else:
                messagebox.showerror("Error", "Debe introducir un nombre para el vuelo")

        # Botón para iniciar el stream
        start_button = tk.Button(flight_name_window, text="Iniciar", bg="green", fg="white", command=start_video_stream)
        start_button.pack(pady=10)


# ==========================
# Cámara Móvil por WebRTC (receptor)
# ==========================
def ensure_webrtc_loop():
    """Asegura que existe un event loop de asyncio para WebRTC (sin registrar emisor)."""
    global webrtc_event_loop, webrtc_thread
    if webrtc_event_loop is not None:
        return
    def run_event_loop():
        import asyncio as _asyncio
        nonlocal_loop = _asyncio.new_event_loop()
        globals()['webrtc_event_loop'] = nonlocal_loop
        _asyncio.set_event_loop(nonlocal_loop)
        print("📡 [WebRTC] Event loop iniciado (receptor)")
        nonlocal_loop.run_forever()
    webrtc_thread = threading.Thread(target=run_event_loop, daemon=True)
    webrtc_thread.start()

def create_mobile_display():
    global mobile_display_window, mobile_video_label
    mobile_display_window = tk.Toplevel(ventana)
    mobile_display_window.title("Cámara Móvil (WebRTC)")
    mobile_display_window.geometry("640x520")

    main_frame = tk.Frame(mobile_display_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    mobile_video_label = tk.Label(main_frame, text="Esperando cámara móvil...", bg="black", fg="white")
    mobile_video_label.pack(fill=tk.BOTH, expand=True)

    def on_close_mobile():
        stop_mobile_webrtc()
        if mobile_display_window and mobile_display_window.winfo_exists():
            mobile_display_window.destroy()
    mobile_display_window.protocol("WM_DELETE_WINDOW", on_close_mobile)

def update_mobile_display():
    global mobile_video_label, mobile_last_frame, mobile_showing, mobile_display_window
    while mobile_showing and mobile_display_window and mobile_display_window.winfo_exists():
        try:
            if mobile_last_frame is not None and mobile_video_label:
                frame_rgb = cv2.cvtColor(mobile_last_frame, cv2.COLOR_BGR2RGB)
                # Ajuste de tamaño
                h, w = frame_rgb.shape[:2]
                max_w, max_h = 600, 440
                scale = min(max_w / w, max_h / h)
                new_w, new_h = int(w * scale), int(h * scale)
                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
                img_pil = Image.fromarray(frame_resized)
                img_tk = ImageTk.PhotoImage(img_pil)
                if mobile_video_label and mobile_video_label.winfo_exists():
                    mobile_video_label.configure(image=img_tk, text="")
                    mobile_video_label.image = img_tk
            time.sleep(0.03)
        except Exception as e:
            print(f"Error actualizando móvil display: {e}")
            time.sleep(0.1)

async def _mobile_reader(track):
    """Lee frames del track de video entrante (async en el event loop)."""
    global mobile_receiving, mobile_last_frame
    from av import VideoFrame as _VideoFrame
    try:
        while mobile_receiving:
            frame = await track.recv()
            if isinstance(frame, _VideoFrame):
                img = frame.to_ndarray(format='bgr24')
                mobile_last_frame = img
    except Exception as e:
        print(f"[Mobile] Reader finalizado: {e}")

async def _mobile_handle_offer(connection_id, sdp, sdp_type):
    """Crea PC receptor, procesa oferta y responde con answer."""
    global mobile_pc, mobile_connection_id
    try:
        # Cerrar PC anterior si existiera
        if mobile_pc is not None:
            try:
                await mobile_pc.close()
            except Exception:
                pass
            mobile_pc = None

        config = RTCConfiguration(iceServers=[
            RTCIceServer(urls="stun:stun.relay.metered.ca:80"),
            RTCIceServer(urls="turn:dronseetac.upc.edu:3478", username="dronseetac", credential="Mimara00.")
        ])
        pc = RTCPeerConnection(config)
        mobile_pc = pc
        mobile_connection_id = connection_id

        @pc.on("track")
        def on_track(track):
            if track.kind == 'video':
                # Lanzar lector de frames en el loop actual
                asyncio.ensure_future(_mobile_reader(track))

        # Procesar oferta
        offer = RTCSessionDescription(sdp=sdp, type=sdp_type)
        await pc.setRemoteDescription(offer)

        # Crear y enviar respuesta
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        sio.emit('webrtc_answer', {
            'connection_id': connection_id,
            'sdp': pc.localDescription.sdp,
            'sdp_type': pc.localDescription.type
        })
        print("📺 [Mobile] Respuesta enviada")
    except Exception as e:
        print(f"❌ [Mobile] Error en handle_offer: {e}")

def start_mobile_webrtc():
    """Solicita stream móvil y abre ventana de previsualización."""
    global mobile_receiving, mobile_showing
    ensure_webrtc_loop()
    mobile_receiving = True
    mobile_showing = True

    create_mobile_display()
    threading.Thread(target=update_mobile_display, daemon=True).start()

    # Solicitar stream al servidor
    try:
        sio.emit('webrtc_request_stream', { 'stream_id': MOBILE_STREAM_ID })
        print(f"📡 [Mobile] Solicitado stream: {MOBILE_STREAM_ID}")
    except Exception as e:
        print(f"❌ [Mobile] Error solicitando stream: {e}")

def stop_mobile_webrtc():
    """Detiene la recepción y cierra la conexión y la ventana."""
    global mobile_receiving, mobile_showing, mobile_pc, mobile_connection_id, mobile_display_window
    mobile_receiving = False
    mobile_showing = False

    # Notificar cierre al servidor para esta conexión
    try:
        if mobile_connection_id:
            sio.emit('webrtc_close_connection', { 'connection_id': mobile_connection_id })
    except Exception:
        pass

    # Cerrar PC
    try:
        if mobile_pc is not None:
            if webrtc_event_loop:
                async def _close():
                    try:
                        await mobile_pc.close()
                    except Exception:
                        pass
                asyncio.run_coroutine_threadsafe(_close(), webrtc_event_loop)
            mobile_pc = None
    except Exception:
        pass

    mobile_connection_id = None

    # Cerrar ventana si sigue abierta
    try:
        if mobile_display_window and mobile_display_window.winfo_exists():
            mobile_display_window.destroy()
    except Exception:
        pass

def recibirCamara():
    """Toggle para recibir la cámara del móvil por WebRTC."""
    global cameraBtn
    if not mobile_receiving:
        cameraBtn['text'] = "Detener video del movil"
        cameraBtn['fg'] = 'white'
        cameraBtn['bg'] = 'green'
        start_mobile_webrtc()
    else:
        stop_mobile_webrtc()
        cameraBtn['text'] = "Recibir video del movil"
        cameraBtn['fg'] = 'black'
        cameraBtn['bg'] = 'violet'

# Thread para trabajar sobre el video
def video_Websocket_thread():
    global cap, sendingWebsockets, sio, last_frame
    global frequencySlider, qualitySlider

    # Inicializar la cámara solo cuando se necesite
    if cap is None:
        cap = cv2.VideoCapture(0)  # NO CAMBIAR: (0) en desarrollo es webcam, (0) en produccion es camara dron
        if not cap.isOpened():
            print("Error: No se pudo abrir la cámara del dron")
            return

    # Iniciar emisor WebRTC
    start_webrtc_emitter()
    
    sendingWebsockets = True
    while sendingWebsockets:
        if frequencySlider.get() > 0:
            ret, frame = cap.read()
            if not ret:
                print("Error: No se pudo leer frame de la cámara")
                break
            
            # Corrección de ojo de pez (si está activada y hay calibración)
            try:
                if fisheye_enabled and cam_matrix is not None and dist_coefs is not None:
                    # Preparar matrices para el tamaño actual del frame si aún no están listas
                    if not fisheye_ready or new_cam_mtx is None or roi is None:
                        h, w = frame.shape[:2]
                        new_cam_mtx_local, roi_local = cv2.getOptimalNewCameraMatrix(cam_matrix, dist_coefs, (w, h), 1, (w, h))
                        # Guardar para reutilizar
                        globals()['new_cam_mtx'] = new_cam_mtx_local
                        globals()['roi'] = roi_local
                        globals()['fisheye_ready'] = True
                    # Aplicar undistort y recortar ROI
                    u_img = cv2.undistort(frame, cam_matrix, dist_coefs, None, new_cam_mtx)
                    x, y, rw, rh = roi
                    # Validar ROI contra tamaño actual
                    if rw > 0 and rh > 0:
                        frame = u_img[y:y+rh, x:x+rw]
                    else:
                        frame = u_img
            except Exception as e:
                # En caso de error, registrar y continuar sin corrección
                print(f"⚠️ Error aplicando corrección de ojo de pez: {e}")
            
            # DETECCIÓN DE OBJETOS (si está activada)
            if detection_enabled and yolo_model is not None:
                try:
                    results = yolo_model(frame, verbose=False, max_det=4, conf=0.5)
                    frame = results[0].plot()  # Frame con bounding boxes y labels
                except Exception as e:
                    print(f"❌ Error en detección: {e}")
            
            # ZOOM (si está activado)
            with zoom_lock:
                current_zoom = zoom_level
                current_center = zoom_center
            
            if current_zoom > 1.0 and current_center is not None:
                try:
                    h, w = frame.shape[:2]
                    cx, cy = current_center
                    
                    # Calcular tamaño de la región a cropear
                    crop_w = int(w / current_zoom)
                    crop_h = int(h / current_zoom)
                    
                    # Calcular límites del crop centrado en (cx, cy)
                    x1 = max(0, cx - crop_w // 2)
                    y1 = max(0, cy - crop_h // 2)
                    x2 = min(w, x1 + crop_w)
                    y2 = min(h, y1 + crop_h)
                    
                    # Ajustar si nos salimos de los límites
                    if x2 - x1 < crop_w:
                        x1 = max(0, x2 - crop_w)
                    if y2 - y1 < crop_h:
                        y1 = max(0, y2 - crop_h)
                    
                    # Cropear y redimensionar al tamaño original
                    cropped = frame[y1:y2, x1:x2]
                    frame = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
                except Exception as e:
                    print(f"⚠️ Error aplicando zoom: {e}")
            
            # Almacena el último frame capturado
            last_frame = frame.copy()
            
            # Enviar frame a la cola compartida de WebRTC
            push_webrtc_frame(frame)
            
            # [DESHABILITADO] Envío por Socket.IO de frames (usamos WebRTC)
            # quality = qualitySlider.get()
            # _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            # frame_b64 = base64.b64encode(buffer).decode('utf-8')
            # try:
            #     sio.emit('video_frame', frame_b64)
            # except Exception:
            #     pass
            
            # espera el tiempo establecido según la frecuencia seleccionada
            periodo = 1/frequencySlider.get()
            time.sleep(periodo)
    
    # Detener emisor WebRTC al finalizar
    stop_webrtc_emitter()

# Captura una foto de la cámara del dron
def capturar_foto():
    global last_frame, current_flight_name
    if last_frame is not None:
        # Crea un directorio para este vuelo si no existe
        photos_dir = "captured_photos"
        if current_flight_name:
            photos_dir = os.path.join(photos_dir, current_flight_name)

        if not os.path.exists(photos_dir):
            os.makedirs(photos_dir)
            print(f"Directorio {photos_dir} creado.")

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"foto_dron_{timestamp}.jpg"
        filepath = os.path.join(photos_dir, filename)

        cv2.imwrite(filepath, last_frame)
        print(f"Foto guardada como {filepath}")
        # Efecto visual de destello en la Estación de Tierra
        try:
            ventana.after(0, trigger_flash_overlay)
        except Exception:
            pass
        
        # Enviar la ruta relativa completa (incluyendo subcarpeta si existe)
        # Convertir a formato de URL (/ en lugar de \)
        relative_path = os.path.join(current_flight_name, filename) if current_flight_name else filename
        relative_path = relative_path.replace('\\', '/')  # Convertir barras para URLs
        print(f"Enviando ruta: {relative_path}")
        # Envia la confirmación al cliente
        sio.emit('flight_event', {'event': 'foto_capturada', 'filename': relative_path})
        return True
    else:
        print("No hay frame disponible para capturar")
        sio.emit('flight_event', {'event': 'foto_error', 'message': 'No hay imagen disponible'})
        return False

# Inicia una grabación de la cámara del dron
def start_recording():
    global recording, video_writer, last_frame, current_flight_name, current_video_filename, current_video_filepath

    if recording:
        return False  # Ya estamos grabando

    # Crea un directorio para este vuelo si no existe
    videos_dir = "captured_videos"
    if current_flight_name:
        videos_dir = os.path.join(videos_dir, current_flight_name)

    if not os.path.exists(videos_dir):
        os.makedirs(videos_dir)
        print(f"Directorio {videos_dir} creado.")

    # Genera nombre de archivo con timestamp (la extensión puede cambiar según el codec)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"video_dron_{timestamp}.mp4"
    filepath = os.path.join(videos_dir, filename)

    # Configura el VideoWriter
    if last_frame is not None:
        height, width = last_frame.shape[:2]
        # Intentar con diferentes codecs según disponibilidad
        # Preferencia: H264 (avc1) → mp4v (MPEG-4 Part 2) → MJPG (AVI)
        writer_opened = False
        # Intento 1: H264 (puede requerir OpenH264/x264 instalado en el sistema)
        try:
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            vw = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))
            if vw.isOpened():
                video_writer = vw
                writer_opened = True
            else:
                try:
                    vw.release()
                except Exception:
                    pass
        except Exception:
            pass

        # Intento 2: mp4v (MPEG-4 Part 2), más ampliamente soportado en OpenCV/FFMPEG
        if not writer_opened:
            try:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                vw = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))
                if vw.isOpened():
                    video_writer = vw
                    writer_opened = True
                else:
                    try:
                        vw.release()
                    except Exception:
                        pass
            except Exception:
                pass

        # Intento 3: MJPG (AVI). Cambiar extensión si los anteriores fallan
        if not writer_opened:
            filename = f"video_dron_{timestamp}.avi"
            filepath = os.path.join(videos_dir, filename)
            try:
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                vw = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))
                if vw.isOpened():
                    video_writer = vw
                    writer_opened = True
                else:
                    try:
                        vw.release()
                    except Exception:
                        pass
            except Exception:
                pass

        if not writer_opened:
            print("Error: No se pudo inicializar el VideoWriter con H264/mp4v/MJPG")
            sio.emit('flight_event', {'event': 'video_error', 'message': 'No hay codecs soportados por OpenCV/FFMPEG'})
            return False

        # Guarda el nombre del archivo con la ruta relativa (incluyendo flight_name si existe)
        relative_path = os.path.join(current_flight_name, filename) if current_flight_name else filename
        current_video_filename = relative_path.replace('\\', '/')
        current_video_filepath = filepath

        # Inicia grabación en un hilo separado
        recording = True
        video_thread = threading.Thread(target=record_video_thread, args=(filepath,))
        video_thread.start()

        sio.emit('flight_event', {'event': 'video_iniciado', 'filename': current_video_filename})
        # Mostrar overlay REC en la Estación de Tierra
        try:
            ventana.after(0, show_rec_overlay)
        except Exception:
            pass
        return True
    else:
        print("No hay frame disponible para iniciar grabación")
        sio.emit('flight_event', {'event': 'video_error', 'message': 'No hay imagen disponible'})
        return False

# Detiene la grabación del video de la cámara del dron
def stop_recording():
    global recording, video_writer, current_video_filename, current_video_filepath, current_flight_name

    if not recording:
        return False  # No estamos grabando

    recording = False
    if video_writer is not None:
        video_writer.release()
        video_writer = None
        
        # Enviar la ruta relativa que ya fue construida en start_recording()
        if current_video_filename:
            sio.emit('flight_event', {'event': 'video_detenido', 'filename': current_video_filename})
            current_video_filename = None
            current_video_filepath = None
        else:
            sio.emit('flight_event', {'event': 'video_detenido'})
        # Ocultar overlay REC
        try:
            ventana.after(0, hide_rec_overlay)
        except Exception:
            pass
        
        return True
    return False

# Se abre la galería fotos y videos
def open_gallery():
    global gallery_window, selected_flight

    # Cerrar la ventana de galería si ya existe
    if gallery_window is not None and gallery_window.winfo_exists():
        gallery_window.destroy()

    # Crear nueva ventana para la galería
    gallery_window = tk.Toplevel(ventana)
    gallery_window.title("Galería de Fotos y Videos")
    gallery_window.geometry("800x600")

    # Frame principal con dos secciones
    main_frame = tk.Frame(gallery_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Panel izquierdo para selección de vuelo
    left_panel = tk.Frame(main_frame, width=200, borderwidth=1, relief="solid")
    left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

    # Panel derecho para mostrar fotos y videos
    right_panel = tk.Frame(main_frame)
    right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # Crear notebooks para separar fotos y videos
    gallery_notebook = ttk.Notebook(right_panel)
    gallery_notebook.pack(fill=tk.BOTH, expand=True)

    # Pestañas para fotos y videos
    photos_frame = tk.Frame(gallery_notebook)
    videos_frame = tk.Frame(gallery_notebook)
    gallery_notebook.add(photos_frame, text="Fotos")
    gallery_notebook.add(videos_frame, text="Videos")

    # Canvas con scrollbar para las fotos
    photos_canvas = tk.Canvas(photos_frame)
    photos_scrollbar = tk.Scrollbar(photos_frame, orient="vertical", command=photos_canvas.yview)
    photos_scrollable_frame = tk.Frame(photos_canvas)

    photos_scrollable_frame.bind(
        "<Configure>",
        lambda e: photos_canvas.configure(scrollregion=photos_canvas.bbox("all"))
    )

    photos_canvas.create_window((0, 0), window=photos_scrollable_frame, anchor="nw")
    photos_canvas.configure(yscrollcommand=photos_scrollbar.set)
    photos_canvas.pack(side="left", fill="both", expand=True)
    photos_scrollbar.pack(side="right", fill="y")

    # Canvas con scrollbar para los videos
    videos_canvas = tk.Canvas(videos_frame)
    videos_scrollbar = tk.Scrollbar(videos_frame, orient="vertical", command=videos_canvas.yview)
    videos_scrollable_frame = tk.Frame(videos_canvas)

    videos_scrollable_frame.bind(
        "<Configure>",
        lambda e: videos_canvas.configure(scrollregion=videos_canvas.bbox("all"))
    )

    videos_canvas.create_window((0, 0), window=videos_scrollable_frame, anchor="nw")
    videos_canvas.configure(yscrollcommand=videos_scrollbar.set)
    videos_canvas.pack(side="left", fill="both", expand=True)
    videos_scrollbar.pack(side="right", fill="y")

    # Obtener la lista de vuelos disponibles
    flight_names = get_available_flights()

    # Etiqueta para la selección de vuelo
    tk.Label(left_panel, text="Selecciona un vuelo:", font=("Arial", 12)).pack(pady=(10, 5), anchor="w")

    # Combobox para seleccionar el vuelo
    flight_selector = ttk.Combobox(left_panel, values=flight_names, width=25)
    flight_selector.pack(pady=(0, 20), fill="x", padx=5)

    # Función para cargar la galería del vuelo seleccionado
    def load_flight_gallery(event=None):
        global selected_flight
        selected_flight = flight_selector.get()
        if selected_flight:
            # Limpiar los frames anteriores
            for widget in photos_scrollable_frame.winfo_children():
                widget.destroy()
            for widget in videos_scrollable_frame.winfo_children():
                widget.destroy()

            # Cargar imágenes y videos
            load_photos(selected_flight, photos_scrollable_frame)
            load_videos(selected_flight, videos_scrollable_frame)

    flight_selector.bind("<<ComboboxSelected>>", load_flight_gallery)

    # Botón para cargar el vuelo seleccionado
    tk.Button(left_panel, text="Cargar Galería", bg="violet", command=load_flight_gallery).pack(fill="x", padx=5)


# Función para obtener la lista de vuelos disponibles con fotos o videos
def get_available_flights():
    flights = set()

    # Buscar en la carpeta de fotos
    if os.path.exists("captured_photos"):
        flights.update(os.listdir("captured_photos"))

    # Buscar en la carpeta de videos
    if os.path.exists("captured_videos"):
        flights.update(os.listdir("captured_videos"))

    # Filtrar sólo directorios
    flights = [f for f in flights if (os.path.isdir(os.path.join("captured_photos", f)) or
                                      os.path.isdir(os.path.join("captured_videos", f)))]

    return sorted(flights)


# Cargar las fotos de cada vuelo
def load_photos(flight_name, frame):
    photos_dir = os.path.join("captured_photos", flight_name)
    if not os.path.exists(photos_dir):
        tk.Label(frame, text=f"No hay fotos disponibles para el vuelo {flight_name}").pack(pady=20)
        return

    photos = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    photos.sort()  # Ordenar alfabéticamente

    if not photos:
        tk.Label(frame, text=f"No hay fotos disponibles para el vuelo {flight_name}").pack(pady=20)
        return

    # Crear un grid de imágenes (3 columnas)
    current_row = 0
    current_col = 0

    for i, photo in enumerate(photos):
        photo_path = os.path.join(photos_dir, photo)
        try:
            # Abrir y redimensionar la imagen como thumbnail
            img = Image.open(photo_path)
            img.thumbnail((200, 150))
            photo_img = ImageTk.PhotoImage(img)

            # Frame para contener la imagen y su etiqueta
            photo_frame = tk.Frame(frame)
            photo_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")

            # Label para la imagen
            photo_label = tk.Label(photo_frame, image=photo_img)
            photo_label.image = photo_img  # Mantener una referencia
            photo_label.pack()

            # Etiqueta con el nombre de la foto
            tk.Label(photo_frame, text=photo[:20] + "..." if len(photo) > 20 else photo,
                     font=("Arial", 8)).pack()

            # Añadir evento de clic para ver en tamaño completo con navegación
            photo_label.bind("<Button-1>", lambda e, img_path=photo_path, idx=i, fn=flight_name:
                              show_full_image(img_path, fn, idx))

            # Actualizar la posición en el grid
            current_col += 1
            if current_col >= 3:
                current_col = 0
                current_row += 1

        except Exception as e:
            print(f"Error al cargar la imagen {photo}: {str(e)}")

# Cargar los videos de cada vuelo
def load_videos(flight_name, frame):
    videos_dir = os.path.join("captured_videos", flight_name)
    if not os.path.exists(videos_dir):
        tk.Label(frame, text=f"No hay videos disponibles para el vuelo {flight_name}").pack(pady=20)
        return

    videos = [f for f in os.listdir(videos_dir) if f.lower().endswith(('.mp4', '.avi', '.mov'))]
    videos.sort()

    if not videos:
        tk.Label(frame, text=f"No hay videos disponibles para el vuelo {flight_name}").pack(pady=20)
        return

    current_row = 0
    current_col = 0

    for i, video in enumerate(videos):
        video_path = os.path.join(videos_dir, video)
        video_frame = tk.Frame(frame)
        video_frame.grid(row=current_row, column=current_col, padx=5, pady=5, sticky="nsew")

        try:
            # Capturar primer frame usando OpenCV
            cap = cv2.VideoCapture(video_path)
            ret, frame_first = cap.read()
            cap.release()

            if ret:
                frame_rgb = cv2.cvtColor(frame_first, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail((200, 150))
                video_thumbnail = ImageTk.PhotoImage(img)

                thumb_label = tk.Label(video_frame, image=video_thumbnail)
                thumb_label.image = video_thumbnail  # evitar que se elimine
                thumb_label.pack()
            else:
                tk.Label(video_frame, text="Sin preview", bg="#ccc", width=30, height=5).pack()

        except Exception as e:
            print(f"Error cargando thumbnail de {video}: {e}")
            tk.Label(video_frame, text="Error preview", bg="#ccc", width=30, height=5).pack()

        # Nombre del archivo
        tk.Label(video_frame, text=video[:20] + "..." if len(video) > 20 else video, font=("Arial", 8)).pack()

        # Botón de reproducción
        play_btn = tk.Button(video_frame, text="Reproducir", bg="green", fg="white",
                             command=lambda v_path=video_path, idx=i, fn=flight_name:
                                     play_video(v_path, fn, idx))
        play_btn.pack(pady=5)

        current_col += 1
        if current_col >= 3:
            current_col = 0
            current_row += 1

# Muestra la imagen en grande y la centra
def show_full_image(img_path, flight_name=None, index=None):
    global full_img_window

    # Cerrar la ventana existente si hay una abierta
    if 'full_img_window' in globals() and full_img_window is not None and full_img_window.winfo_exists():
        full_img_window.destroy()

    full_img_window = tk.Toplevel()
    full_img_window.title("Visualización de Imagen")

    # Obtener dimensiones de la pantalla
    screen_width = full_img_window.winfo_screenwidth()
    screen_height = full_img_window.winfo_screenheight()

    # Crear frame principal
    main_frame = tk.Frame(full_img_window)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Frame para la imagen
    img_frame = tk.Frame(main_frame)
    img_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Frame para los botones
    btn_frame = tk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    # Cargar la imagen
    img = Image.open(img_path)

    # Redimensionar si es necesario (para que quepa en la pantalla)
    img_width, img_height = img.size
    if img_width > screen_width * 0.8 or img_height > screen_height * 0.8:
        # Calcular factor de escala
        scale = min(screen_width * 0.8 / img_width, screen_height * 0.8 / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    # Convertir para Tkinter
    photo_img = ImageTk.PhotoImage(img)

    # Mostrar la imagen
    img_label = tk.Label(img_frame, image=photo_img)
    img_label.image = photo_img  # Mantener una referencia
    img_label.pack(padx=10, pady=10)

    # Mostrar nombre del archivo
    filename = os.path.basename(img_path)
    tk.Label(img_frame, text=filename).pack(pady=5)

    # Si tenemos información del vuelo y el índice, podemos navegar
    if flight_name and index is not None:
        photos_dir = os.path.join("captured_photos", flight_name)
        photos = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        photos.sort()  # Ordenar las fotos alfabéticamente

        # Función para navegar a la foto anterior
        def prev_photo():
            prev_index = (index - 1) % len(photos)
            # Guardar la posición actual para reutilizarla
            current_geometry = full_img_window.geometry()
            full_img_window.destroy()
            show_full_image(os.path.join(photos_dir, photos[prev_index]), flight_name, prev_index)
            # Centrar la nueva ventana
            center_window(full_img_window)

        # Función para navegar a la foto siguiente
        def next_photo():
            next_index = (index + 1) % len(photos)
            # Guardar la posición actual para reutilizarla
            current_geometry = full_img_window.geometry()
            full_img_window.destroy()
            show_full_image(os.path.join(photos_dir, photos[next_index]), flight_name, next_index)
            # Centrar la nueva ventana
            center_window(full_img_window)

        # Botones de navegación
        prev_btn = tk.Button(btn_frame, text="← Anterior", command=prev_photo, bg="blue", fg="white")
        prev_btn.pack(side=tk.LEFT, padx=5)

        # Indicador de posición
        position_label = tk.Label(btn_frame, text=f"Imagen {index + 1} de {len(photos)}")
        position_label.pack(side=tk.LEFT, padx=20, expand=True)

        next_btn = tk.Button(btn_frame, text="Siguiente →", command=next_photo, bg="blue", fg="white")
        next_btn.pack(side=tk.LEFT, padx=5)

    # Botón para cerrar
    close_btn = tk.Button(btn_frame, text="Cerrar", command=full_img_window.destroy, bg="red", fg="white")
    close_btn.pack(side=tk.RIGHT, padx=5)

    # Esperar a que la ventana se dibuje para centrarla
    full_img_window.update_idletasks()
    center_window(full_img_window)

# Muestra el video en grande y lo centra
def play_video(video_path, flight_name=None, index=None):
    global video_player_window

    if 'video_player_window' in globals() and video_player_window is not None and video_player_window.winfo_exists():
        video_player_window.destroy()

    video_player_window = tk.Toplevel()
    video_player_window.title("Reproductor de Video")
    video_player_window.geometry("600x500")

    main_frame = tk.Frame(video_player_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Mostrar nombre del archivo
    filename = os.path.basename(video_path)
    tk.Label(main_frame, text=filename, font=("Arial", 12, "bold")).pack(pady=5)

    # Mostrar preview (primer frame del video)
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame_first = cap.read()
        cap.release()

        if ret:
            frame_rgb = cv2.cvtColor(frame_first, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((400, 250))
            preview_img = ImageTk.PhotoImage(img)

            preview_label = tk.Label(main_frame, image=preview_img)
            preview_label.image = preview_img  # evitar que se borre
            preview_label.pack(pady=5)
        else:
            tk.Label(main_frame, text="Sin preview disponible").pack()

    except Exception as e:
        print(f"Error cargando preview del video: {e}")
        tk.Label(main_frame, text="Error en la preview").pack()

    btn_frame = tk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=10)

    play_btn = tk.Button(btn_frame, text="▶️ Reproducir",
                         command=lambda: open_video_external(video_path),
                         bg="green", fg="white", font=("Arial", 10, "bold"))
    play_btn.pack(pady=10)

    # Navegación entre videos si hay más
    if flight_name and index is not None:
        videos_dir = os.path.join("captured_videos", flight_name)
        videos = [f for f in os.listdir(videos_dir) if f.lower().endswith(('.mp4', '.avi', '.mov'))]
        videos.sort()

        nav_frame = tk.Frame(main_frame)
        nav_frame.pack(pady=5)

        def prev_video():
            prev_index = (index - 1) % len(videos)
            video_player_window.destroy()
            play_video(os.path.join(videos_dir, videos[prev_index]), flight_name, prev_index)

        def next_video():
            next_index = (index + 1) % len(videos)
            video_player_window.destroy()
            play_video(os.path.join(videos_dir, videos[next_index]), flight_name, next_index)

        tk.Button(nav_frame, text="← Video Anterior", command=prev_video, bg="blue", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Label(nav_frame, text=f"Video {index + 1} de {len(videos)}").pack(side=tk.LEFT, padx=10)
        tk.Button(nav_frame, text="Video Siguiente →", command=next_video, bg="blue", fg="white").pack(side=tk.RIGHT, padx=5)

    close_btn = tk.Button(main_frame, text="Cerrar", command=video_player_window.destroy, bg="red", fg="white")
    close_btn.pack(pady=10)

    video_player_window.update_idletasks()
    center_window(video_player_window)

# Función para centrar una ventana en la pantalla
def center_window(window):
    # Obtener dimensiones de la pantalla
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # Obtener dimensiones de la ventana
    window_width = window.winfo_width()
    window_height = window.winfo_height()

    # Calcular posición
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2

    # Centrar la ventana en la pantalla
    window.geometry(f"+{x}+{y}")

# Función para abrir el video con el reproductor externo
def open_video_external(video_path):
    try:
        # En sistemas Windows, usar el reproductor predeterminado
        if os.name == 'nt':
            os.startfile(video_path)
        # En macOS
        elif os.name == 'posix' and 'darwin' in os.uname().sysname.lower():
            os.system(f'open "{video_path}"')
        # En Linux
        else:
            os.system(f'xdg-open "{video_path}"')
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo reproducir el video: {str(e)}")

# Función para grabar el thread de video
def record_video_thread(filepath):
    global recording, video_writer, last_frame

    try:
        while recording and video_writer is not None:
            if last_frame is not None:
                video_writer.write(last_frame)
            time.sleep(0.05)  # Pequeña pausa para no saturar el ordenador
    except Exception as e:
        print(f"Error en la grabación: {str(e)}")
    finally:
        if video_writer is not None:
            video_writer.release()
            print(f"Video guardado: {filepath}") 

# [Eliminado] Ruta legacy de cámara móvil por Socket.IO/OpenCV.

# Crea la ventana para mostrar el video del dron
def create_video_display():
    global video_display_window, video_label, video_container

    video_display_window = tk.Toplevel(ventana)
    video_display_window.title(f"Video del Dron - {current_flight_name}")
    video_display_window.geometry("800x600")

    # Frame principal
    main_frame = tk.Frame(video_display_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Contenedor para el video y overlays (evita parpadeo del REC)
    video_container = tk.Frame(main_frame, bg="black", borderwidth=0, highlightthickness=0)
    video_container.pack(fill=tk.BOTH, expand=True)

    # Label para mostrar el video (hijo del contenedor)
    video_label = tk.Label(video_container, text="Esperando video...", bg="black", fg="white", borderwidth=0, highlightthickness=0)
    video_label.pack(fill=tk.BOTH, expand=True)

    # Frame para controles
    controls_frame = tk.Frame(main_frame)
    controls_frame.pack(fill=tk.X, pady=5)

    # Frame intermedio para centrar botones
    buttons_frame = tk.Frame(controls_frame)
    buttons_frame.pack(expand=True)

    # Botones de control
    capture_btn = tk.Button(buttons_frame, text="Capturar Foto",
                            command=capturar_foto, bg="blue", fg="white")
    capture_btn.pack(side=tk.LEFT, padx=5)

    record_btn = tk.Button(buttons_frame, text="Iniciar Grabación",
                           command=start_recording, bg="red", fg="white")
    record_btn.pack(side=tk.LEFT, padx=5)

    stop_record_btn = tk.Button(buttons_frame, text="Detener Grabación",
                                command=stop_recording, bg="orange", fg="white")
    stop_record_btn.pack(side=tk.LEFT, padx=5)

    # Función para manejar el cierre de la ventana
    def on_closing():
        global sendingWebsockets, showing_video
        # Ocultar overlays si están activos
        try:
            ventana.after(0, hide_rec_overlay)
        except Exception:
            pass
        try:
            if 'flash_overlay' in globals() and flash_overlay is not None and flash_overlay.winfo_exists():
                flash_overlay.destroy()
        except Exception:
            pass
        sendingWebsockets = False
        showing_video = False
        videoWebsocketBtn['text'] = "Activar cámara dron"
        videoWebsocketBtn['fg'] = 'black'
        videoWebsocketBtn['bg'] = 'violet'
        video_display_window.destroy()

    video_display_window.protocol("WM_DELETE_WINDOW", on_closing)


# ==========================
# Overlays de la previsualización
# ==========================
def show_rec_overlay():
    """Muestra un indicador REC con temporizador sobre el video."""
    global rec_overlay_label, rec_timer_job, rec_start_time, rec_blink_state
    # Determinar el contenedor adecuado para overlays
    parent = video_container if (video_container is not None and video_container.winfo_exists()) else video_label
    if parent is None or not parent.winfo_exists():
        return

    # Crear label si no existe
    if rec_overlay_label is None or not rec_overlay_label.winfo_exists():
        rec_overlay_label = tk.Label(parent, text="REC 00:00", bg="#220000", fg="red",
                                     font=("Arial", 12, "bold"))
        # Posicionar arriba-izquierda con un pequeño margen
        rec_overlay_label.place(in_=parent, x=10, y=10)

    rec_start_time = time.time()
    rec_blink_state = False

    # Arrancar actualización
    def tick():
        global rec_timer_job, rec_blink_state
        if rec_overlay_label is None or not rec_overlay_label.winfo_exists():
            rec_timer_job = None
            return

        # Calcular tiempo transcurrido
        elapsed = int(time.time() - rec_start_time) if rec_start_time else 0
        mm = elapsed // 60
        ss = elapsed % 60

        try:
            rec_overlay_label.configure(text=f"REC {mm:02d}:{ss:02d}", fg="red")
            # Asegurar que el overlay quede por encima del frame del video
            rec_overlay_label.lift()
        except Exception:
            pass

        # Reprogramar
        rec_timer_job = ventana.after(500, tick)

    # Iniciar el ciclo
    if rec_timer_job is None:
        rec_timer_job = ventana.after(0, tick)


def hide_rec_overlay():
    """Oculta y limpia el indicador REC y su temporizador."""
    global rec_overlay_label, rec_timer_job, rec_start_time
    # Cancelar temporizador
    try:
        if rec_timer_job is not None:
            ventana.after_cancel(rec_timer_job)
    except Exception:
        pass
    rec_timer_job = None
    rec_start_time = None

    # Destruir label
    try:
        if rec_overlay_label is not None and rec_overlay_label.winfo_exists():
            rec_overlay_label.destroy()
    except Exception:
        pass
    rec_overlay_label = None


def trigger_flash_overlay(duration_ms=300):
    """Muestra un destello blanco breve sobre el video para indicar foto."""
    global flash_overlay
    parent = video_container if (video_container is not None and video_container.winfo_exists()) else video_label
    if parent is None or not parent.winfo_exists():
        return

    # Crear overlay a pantalla completa del label de video
    try:
        # Destruir cualquier overlay anterior activo
        if flash_overlay is not None and flash_overlay.winfo_exists():
            flash_overlay.destroy()
    except Exception:
        pass

    flash_overlay = tk.Label(parent, bg="white")
    flash_overlay.place(in_=parent, relx=0, rely=0, relwidth=1, relheight=1)

    # Quitar overlay tras el tiempo indicado
    ventana.after(duration_ms, lambda: (flash_overlay.winfo_exists() and flash_overlay.destroy()))

# Thread para actualizar la visualización del video
def update_video_display():
    global video_label, last_frame, showing_video, video_display_window

    while showing_video and video_display_window and video_display_window.winfo_exists():
        try:
            if last_frame is not None and video_label:
                # Convertir frame de BGR a RGB (last_frame ya está flippeado)
                frame_rgb = cv2.cvtColor(last_frame, cv2.COLOR_BGR2RGB)

                # Redimensionar frame para ajustarlo a la ventana (manteniendo aspecto)
                height, width = frame_rgb.shape[:2]
                max_width = 780
                max_height = 500

                # Calcular nueva escala
                scale = min(max_width / width, max_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)

                # Redimensionar
                frame_resized = cv2.resize(frame_rgb, (new_width, new_height))

                # Convertir a formato PIL y luego a PhotoImage
                img_pil = Image.fromarray(frame_resized)
                img_tk = ImageTk.PhotoImage(img_pil)

                # Actualizar el label con la nueva imagen
                if video_label and video_label.winfo_exists():
                    video_label.configure(image=img_tk, text="")
                    video_label.image = img_tk  # Mantener referencia
                    # Mantener REC overlay en primer plano si existe
                    try:
                        if 'rec_overlay_label' in globals() and rec_overlay_label is not None and rec_overlay_label.winfo_exists():
                            rec_overlay_label.lift()
                        if 'flash_overlay' in globals() and flash_overlay is not None and flash_overlay.winfo_exists():
                            flash_overlay.lift()
                    except Exception:
                        pass

            time.sleep(0.03)

        except Exception as e:
            print(f"Error actualizando video display: {e}")
            time.sleep(0.1)

# Cerrar la ventana de la cámara del dron si está abierta
def close_video_display():
    global video_display_window, showing_video, sendingWebsockets

    showing_video = False
    sendingWebsockets = False

    # Liberar la cámara del dron
    release_camera()

    # Actualizar el botón
    videoWebsocketBtn['text'] = "Activar cámara dron"
    videoWebsocketBtn['fg'] = 'black'
    videoWebsocketBtn['bg'] = 'violet'

    # Limpiar overlays si existen
    try:
        ventana.after(0, hide_rec_overlay)
    except Exception:
        pass
    try:
        if 'flash_overlay' in globals() and flash_overlay is not None and flash_overlay.winfo_exists():
            flash_overlay.destroy()
    except Exception:
        pass

    if video_display_window and video_display_window.winfo_exists():
        video_display_window.destroy()
        video_display_window = None

# Función para liberar la cámara del dron
def release_camera():
    # Libera la cámara cuando se detiene el stream
    global cap
    if cap is not None:
        cap.release()
        cap = None
        print("Cámara liberada")

# Función que espera a que el dron llegue al waypoint correspondiente
def wait_for_waypoint_arrival(target_lat, target_lng, timeout=30):

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Se usa la función interna del dron
            if hasattr(dron, '_distanceToDestinationInMeters'):
                dist = dron._distanceToDestinationInMeters(target_lat, target_lng)
                if dist <= 1.0:  # 1 metro de tolerancia
                    return True
            else:
                # Metodo alternativo usando coordenadas actuales
                dlat = abs(dron.lat - target_lat)
                dlon = abs(dron.lon - target_lng)
                # Aproximadamente 1 metro en coordenadas
                if dlat < 0.00001 and dlon < 0.00001:
                    return True

        except Exception as e:
            print(f"Error calculando distancia: {e}")
            # Usar metodo básico como respaldo
            dlat = abs(dron.lat - target_lat)
            dlon = abs(dron.lon - target_lng)
            if dlat < 0.00001 and dlon < 0.00001:
                return True

        time.sleep(0.5)  # Revisar cada medio segundo

    print(f"Timeout esperando llegada a waypoint ({target_lat}, {target_lng})")
    return False

cap = None
sendingWebsockets = False
last_frame = None # Variable para almacenar el último frame (la foto)

# Configurar cliente Socket.IO para aceptar certificados SSL autofirmados
import ssl
sio = socketio.Client(ssl_verify=False)  # Deshabilitar verificación SSL

# Registrar handler ANTES de conectar (forma correcta en Socket.IO Python)
@sio.on('ground_station_command')
def handle_ground_station_command(data):
    """Handler para comandos desde el servidor Flask"""
    global webapp_commands_enabled
    
    # Verificar si los comandos de la WebApp están habilitados
    if not webapp_commands_enabled:
        action = data.get('action', 'desconocido')
        print(f'COMANDO BLOQUEADO: {action} (WebApp no autorizada - haz clic en "Conectar WebApp")')
        return
    
    # Si está autorizado, procesar el comando
    on_command_received(data)


# ========================================================================
# WEBRTC HANDLERS - Responder a señales del servidor
# ========================================================================

@sio.on('webrtc_prepare_offer')
def handle_webrtc_prepare_offer(data):
    """
    El servidor pide preparar una oferta para un nuevo receptor.
    Similar a cuando el proxy avisa: {"type": "receptor", "id": 0}
    
    data = {'connection_id': str, 'receiver_sid': str, 'stream_id': str}
    """
    connection_id = data.get('connection_id')
    receiver_sid = data.get('receiver_sid')
    stream_id = data.get('stream_id', 'dron_camera')
    
    print(f"📤 [WebRTC] Preparando oferta para receptor: {receiver_sid} (stream: {stream_id})")
    
    if webrtc_event_loop is None:
        print("   └─> ⚠️ Event loop no disponible")
        return
    
    # Crear la oferta en el event loop de asyncio
    asyncio.run_coroutine_threadsafe(
        create_webrtc_offer(connection_id, stream_id),
        webrtc_event_loop
    )


@sio.on('webrtc_answer')
def handle_webrtc_answer(data):
    """
    El receptor envía su respuesta SDP.
    Similar a cuando el receiver acepta la oferta.
    
    data = {'connection_id': str, 'sdp': str, 'sdp_type': str}
    """
    connection_id = data.get('connection_id')
    sdp = data.get('sdp')
    sdp_type = data.get('sdp_type')
    
    print(f"📥 [WebRTC] Respuesta recibida para conexión: {connection_id}")
    
    if webrtc_event_loop is None:
        print("   └─> ⚠️ Event loop no disponible")
        return
    
    # Procesar la respuesta en el event loop
    asyncio.run_coroutine_threadsafe(
        process_webrtc_answer(connection_id, sdp, sdp_type),
        webrtc_event_loop
    )


@sio.on('webrtc_offer')
def handle_webrtc_offer_receiver(data):
    """Oferta recibida para receptor (cámara móvil)."""
    stream_id = data.get('stream_id')
    connection_id = data.get('connection_id')
    sdp = data.get('sdp')
    sdp_type = data.get('sdp_type')

    # Solo gestionar la oferta si es para la cámara móvil
    if stream_id != MOBILE_STREAM_ID:
        return

    print(f"📥 [Mobile] Oferta recibida para conexión: {connection_id}")
    ensure_webrtc_loop()
    asyncio.run_coroutine_threadsafe(
        _mobile_handle_offer(connection_id, sdp, sdp_type),
        webrtc_event_loop
    )


@sio.on('webrtc_close_connection')
def handle_webrtc_close_connection(data):
    """
    El servidor notifica que una conexión se cerró (receptor cerró la cámara).
    """
    connection_id = data.get('connection_id')
    
    if connection_id in webrtc_peer_connections:
        print(f"🗑️ [WebRTC] Cerrando conexión: {connection_id}")
        pc = webrtc_peer_connections[connection_id]
        
        # Eliminar data channel asociado
        if connection_id in webrtc_data_channels:
            del webrtc_data_channels[connection_id]
        
        # Eliminar inmediatamente del diccionario para permitir reconexión
        del webrtc_peer_connections[connection_id]
        
        # Cerrar la peer connection de forma asíncrona
        if webrtc_event_loop:
            async def close_pc():
                try:
                    await pc.close()
                    print(f"   └─> ✅ Conexión cerrada completamente")
                except Exception as e:
                    print(f"   └─> ⚠️ Error cerrando conexión: {e}")
            
            asyncio.run_coroutine_threadsafe(close_pc(), webrtc_event_loop)
    else:
        # ¿Es la conexión móvil?
        if connection_id == mobile_connection_id and mobile_pc is not None:
            print(f"🗑️ [Mobile] Cerrando conexión: {connection_id}")
            if webrtc_event_loop:
                async def close_pc():
                    try:
                        await mobile_pc.close()
                    except Exception:
                        pass
                asyncio.run_coroutine_threadsafe(close_pc(), webrtc_event_loop)
            # Reset móviles
            try:
                if mobile_display_window and mobile_display_window.winfo_exists():
                    mobile_display_window.destroy()
            except Exception:
                pass
            globals()['mobile_pc'] = None
            globals()['mobile_connection_id'] = None
        else:
            print(f"🗑️ [WebRTC] Conexión {connection_id} ya no existe (ya cerrada)")


@sio.on('webrtc_ice_candidate')
def handle_webrtc_ice_candidate(data):
    """
    Recibir ICE candidate del receptor.
    """
    connection_id = data.get('connection_id')
    
    if webrtc_event_loop is None:
        return
    
    # Agregar ICE candidate en el event loop
    async def add_ice_to(pc_target):
        try:
            from aiortc.sdp import candidate_from_sdp
            # Soportar formatos string u objeto
            candidate_str = data.get('candidate')
            sdp_mid = data.get('sdpMid')
            sdp_index = data.get('sdpMLineIndex')
            if isinstance(candidate_str, dict) and candidate_str.get('candidate'):
                sdp_mid = candidate_str.get('sdpMid')
                sdp_index = candidate_str.get('sdpMLineIndex')
                candidate_str = candidate_str.get('candidate')

            if not candidate_str:
                return
            ice_candidate = candidate_from_sdp(candidate_str.split(':', 1)[1])
            ice_candidate.sdpMid = sdp_mid
            ice_candidate.sdpMLineIndex = sdp_index
            await pc_target.addIceCandidate(ice_candidate)
        except Exception as e:
            print(f"   └─> Error agregando ICE candidate: {e}")

    # Prioridad: conexiones del emisor (dron) existentes
    if connection_id in webrtc_peer_connections:
        pc = webrtc_peer_connections[connection_id]
        asyncio.run_coroutine_threadsafe(add_ice_to(pc), webrtc_event_loop)
        return

    # Si coincide con la conexión móvil, agregar al PC móvil
    if connection_id == mobile_connection_id and mobile_pc is not None:
        asyncio.run_coroutine_threadsafe(add_ice_to(mobile_pc), webrtc_event_loop)


async def create_webrtc_offer(connection_id, stream_id='dron_camera'):
    """
    Crea una conexión peer y genera una oferta SDP.
    
    Args:
        connection_id: ID único de la conexión
        stream_id: 'telemetry' (solo Data Channel) o 'dron_camera' (Data Channel + Video)
    """
    global webrtc_peer_connections
    
    try:
        # Cerrar conexión anterior si existe (para reconexiones limpias)
        if connection_id in webrtc_peer_connections:
            print(f"   └─> ⚠️ Cerrando conexión anterior antes de crear nueva")
            old_pc = webrtc_peer_connections[connection_id]
            try:
                await old_pc.close()
            except:
                pass
            del webrtc_peer_connections[connection_id]

        config = RTCConfiguration(iceServers=[
            RTCIceServer(urls="stun:stun.relay.metered.ca:80"),
            RTCIceServer(urls="turn:dronseetac.upc.edu:3478",
                         username="dronseetac",
                         credential="Mimara00.")
        ])
        pc = RTCPeerConnection(config)
        webrtc_peer_connections[connection_id] = pc
        print(f"   └─> Nueva RTCPeerConnection creada con ICE servers")
        
        # Crear Data Channel para telemetría (siempre)
        telemetry_channel = pc.createDataChannel('telemetry', ordered=True)
        webrtc_data_channels[connection_id] = telemetry_channel
        print(f"   └─> Data Channel 'telemetry' creado")
        
        # Añadir track de video SOLO si es el stream 'dron_camera' y la cámara está activa
        if stream_id == 'dron_camera' and sendingWebsockets and cap is not None:
            camera_track = DronCameraTrack()
            pc.addTrack(camera_track)
            print(f"   └─> Track de video agregado (kind: {camera_track.kind})")
        else:
            if stream_id == 'telemetry':
                print(f"   └─> Stream de telemetría (sin video)")
            else:
                print(f"   └─> Sin video (cámara inactiva)")
        
        # Crear oferta
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        print(f"   └─> Oferta SDP creada")
        
        # Enviar oferta al servidor vía Socket.IO
        sio.emit('webrtc_offer', {
            'connection_id': connection_id,
            'sdp': pc.localDescription.sdp,
            'sdp_type': pc.localDescription.type
        })
        print(f"   └─> ✅ Oferta enviada al servidor")
        
    except Exception as e:
        print(f"   └─> ❌ Error creando oferta: {e}")
        import traceback
        traceback.print_exc()


async def process_webrtc_answer(connection_id, sdp, sdp_type):
    """
    Procesa la respuesta SDP del receptor.
    Equivalente a cuando el sender recibe el answer.
    """
    global webrtc_peer_connections
    
    try:
        if connection_id not in webrtc_peer_connections:
            print(f"   └─> ⚠️ Conexión no encontrada: {connection_id}")
            return
        
        pc = webrtc_peer_connections[connection_id]
        
        # Verificar si la conexión ya está en estado estable (ya procesó una respuesta)
        if pc.signalingState == 'stable':
            print(f"   └─> ⚠️ Respuesta duplicada ignorada (conexión ya estable)")
            return
        
        # Configurar remote description con la respuesta
        answer = RTCSessionDescription(sdp=sdp, type=sdp_type)
        await pc.setRemoteDescription(answer)
        
        print(f"   └─> ✅ Respuesta procesada. Stream en marcha")
        
    except Exception as e:
        print(f"   └─> ❌ Error procesando respuesta: {e}")
        import traceback
        traceback.print_exc()

recording = False
video_writer = None
video_thread = None
current_video_filename = None  # Variable para almacenar el nombre del video actual
current_video_filepath = None  # Ruta absoluta del archivo de video actual
current_flight_name = None  # Variable para almacenar el nombre del vuelo actual
gallery_window = None
selected_flight = None
video_display_window = None
video_label = None
video_container = None
showing_video = False

# Overlays en la ventana de video (solo Estación de Tierra)
rec_overlay_label = None
rec_timer_job = None
rec_start_time = None
rec_blink_state = False
flash_overlay = None

# ==========================
# WebRTC Receptor: Cámara Móvil
# ==========================
# Nota: el emisor de la cámara móvil en la WebApp transmite el canvas procesado
# de MediaPipe bajo el stream_id 'gestos_profesor'. Para ver ese vídeo aquí,
# el receptor debe solicitar ese mismo stream_id.
MOBILE_STREAM_ID = 'gestos_profesor'
mobile_pc = None
mobile_connection_id = None
mobile_receiving = False
mobile_last_frame = None
mobile_display_window = None
mobile_video_label = None
mobile_showing = False
mobile_reader_task = None

# Variables legacy eliminadas para cámara móvil por Socket.IO

# Conectar al servidor Socket.IO con reintentos automáticos
def connect_to_socketio_server():
    """Intenta conectarse al servidor Socket.IO con reintentos"""
    max_retries = 3
    retry_delay = 2  # segundos
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Intentando conectar al servidor Socket.IO (intento {attempt}/{max_retries})...")
            # Conectar al servidor Flask+Socket.IO (ambos en el mismo puerto)
            # DESARROLLO: HTTPS con certificado autofirmado (ssl_verify=False configurado en el cliente)
            #sio.connect('https://localhost:8106')
            # PRODUCCIÓN: descomentar la siguiente línea
            sio.connect('https://dronseetac.upc.edu:8106')
            print("Conectado exitosamente al servidor Socket.IO")
            # Marcar conectado
            global webrtc_socket_connected
            webrtc_socket_connected = True
            return True
        except Exception as e:
            if attempt < max_retries:
                print(f"No se pudo conectar (intento {attempt}/{max_retries}). Reintentando en {retry_delay}s...")
                print(f"Error: {str(e)[:100]}")
                time.sleep(retry_delay)
            else:
                print(f"ERROR: No se pudo conectar al servidor Socket.IO después de {max_retries} intentos")
                print(f"Asegúrate de que 'run.py' esté ejecutándose primero")
                print(f"Error: {e}")
                return False

# Eventos de conexión/desconexión de Socket.IO
@sio.event
def connect():
    global webrtc_socket_connected
    webrtc_socket_connected = True
    print("🔌 [Socket.IO] Conectado")
    
    # Iniciar emisor WebRTC para telemetría (stream separado, siempre activo)
    try:
        start_webrtc_emitter()
        # Registrar stream de telemetría (sin video, solo Data Channel)
        sio.emit('webrtc_register_emitter', {'stream_id': 'telemetry'})
        print("📡 [WebRTC] Stream 'telemetry' registrado (solo Data Channel)")
    except Exception as e:
        print(f"⚠️ Error iniciando emisor de telemetría: {e}")
    
    # Si la cámara del dron está activa, re-registrar su stream
    try:
        if 'sendingWebsockets' in globals() and globals()['sendingWebsockets']:
            sio.emit('webrtc_register_emitter', {'stream_id': 'dron_camera'})
            print("📡 [WebRTC] Stream 'dron_camera' re-registrado")
    except Exception:
        pass

@sio.event
def disconnect():
    global webrtc_socket_connected, webrtc_emitter_registered
    webrtc_socket_connected = False
    webrtc_emitter_registered = False
    print("🔌 [Socket.IO] Desconectado")
    
    return False

# Intentar conectar al servidor
if not connect_to_socketio_server():
    print("\nADVERTENCIA: Estación de Tierra ejecutándose SIN conexión Socket.IO")
    print("    - No podrás controlar el dron desde la WebApp")
    print("    - Solo podrás usar la interfaz local de la Estación de Tierra")
    print("    - Para habilitar control remoto, ejecuta 'run.py' y reinicia esta aplicación\n")

# [Eliminado] Handler legacy de frames de móvil por Socket.IO (ahora WebRTC)

@sio.on("go")
def handle_go(direction):
    print(f"MediaPipe pidió mover al dron: {direction}")
    if dron.state == "flying":
        dron.changeNavSpeed(2)  # Limita la velocidad a 2 m/s en MediaPipe
    dron.go(direction)

# Variables globales para el modo piloto
pilot_mode_active = False
pilot_rc_values = {'throttle': 0, 'yaw': 0, 'pitch': 0, 'roll': 0}
pilot_rc_thread = None
last_rc_command_time = None  # Timestamp del último comando recibido

def pilot_rc_loop():
    """Loop continuo que envía comandos RC al dron mientras está en modo piloto.
    Mantiene el loop vivo aunque el estado deje de ser 'flying' momentáneamente.
    """
    global pilot_mode_active, pilot_rc_values, last_rc_command_time

    while pilot_mode_active:
        # Esperar si el dron no está volando, pero mantener el loop activo
        if dron.state != "flying":
            time.sleep(0.05)
            continue

        # Si no hemos recibido comandos en los últimos 0.3 segundos, resetear a 0
        if last_rc_command_time is not None:
            time_since_last_command = time.time() - last_rc_command_time
            if time_since_last_command > 0.3:
                pilot_rc_values['throttle'] = 0
                pilot_rc_values['yaw'] = 0
                pilot_rc_values['pitch'] = 0
                pilot_rc_values['roll'] = 0

        # VALIDACIÓN DE LÍMITES DE ALTURA
        current_altitude = dron.alt
        throttle_value = pilot_rc_values['throttle']

        # CRÍTICO: Los valores de throttle deben mantenerse en el rango [-1, 1] para evitar
        # que el PWM resultante (1500 + value*400) caiga fuera del rango [1100, 1900].
        # Si el PWM < 975, se activa el failsafe RTL del dron.
        
        if current_altitude >= 9.5 and throttle_value > 0:
            # Factor puede ser negativo si te pasas del techo (empuja hacia abajo)
            factor = (ALTURA_MAXIMA - current_altitude) / (ALTURA_MAXIMA - 9.5)
            original_throttle = throttle_value
            # Aplicar factor y clampear al rango seguro [-1.0, 1.0]
            pilot_rc_values['throttle'] = max(-1.0, min(1.0, throttle_value * factor))
            if abs(original_throttle - pilot_rc_values['throttle']) > 0.1:
                print(f'🔼 Controlando altura cerca del techo: {current_altitude:.1f}m (throttle: {original_throttle:.2f} → {pilot_rc_values["throttle"]:.2f})')
        elif current_altitude <= 2.5 and throttle_value < 0:
            # Factor puede ser negativo si te pasas del suelo (empuja hacia arriba)
            factor = (current_altitude - ALTURA_MINIMA) / (2.5 - ALTURA_MINIMA)
            original_throttle = throttle_value
            # Aplicar factor y clampear al rango seguro [-1.0, 1.0]
            pilot_rc_values['throttle'] = max(-1.0, min(1.0, throttle_value * factor))
            if abs(original_throttle - pilot_rc_values['throttle']) > 0.1:
                print(f'🔽 Controlando altura cerca del suelo: {current_altitude:.1f}m (throttle: {original_throttle:.2f} → {pilot_rc_values["throttle"]:.2f})')

        def normalize_to_pwm(value):
            return int(1500 + (value * 400))

        throttle_pwm = normalize_to_pwm(pilot_rc_values['throttle'])
        yaw_pwm = normalize_to_pwm(pilot_rc_values['yaw'])
        pitch_pwm = normalize_to_pwm(pilot_rc_values['pitch'])
        roll_pwm = normalize_to_pwm(pilot_rc_values['roll'])

        dron.send_rc(pitch=pitch_pwm, roll=roll_pwm, throttle=throttle_pwm, yaw=yaw_pwm)
        time.sleep(0.05)

@sio.on("pilot_rc")
def handle_pilot_rc(data):
    """Handler para datos de joystick del modo piloto: [throttle, yaw, pitch, roll]"""
    global webapp_commands_enabled, pilot_rc_values, last_rc_command_time, pilot_mode_active, pilot_rc_thread
    
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

        # Asegurar que el loop RC esté activo si llegan datos y el dron está volando
        if not pilot_mode_active or pilot_rc_thread is None or not pilot_rc_thread.is_alive():
            pilot_mode_active = True
            try:
                pilot_rc_thread = threading.Thread(target=pilot_rc_loop, daemon=True)
                pilot_rc_thread.start()
                print('🎮 Loop RC iniciado por recepción de datos')
            except Exception as e:
                print(f'⚠️ Error iniciando loop RC: {e}')

@sio.on("pilot_action")
def handle_pilot_action(data):
    """Handler para acciones del modo piloto (aterrizar, RTL)"""
    global webapp_commands_enabled, pilot_mode_active
    
    if not webapp_commands_enabled:
        action = data.get('action', 'desconocido')
        print(f'ACCIÓN BLOQUEADA: {action} (WebApp no autorizada)')
        return
    
    action = data.get('action')
    print(f"Acción del modo piloto: {action}")
    
    if action == 'land':
        if dron.state == 'flying':
            print('Aterrizando desde modo piloto')
            # Detener loop RC
            pilot_mode_active = False
            print('Loop RC detenido')
            # Cambiar a GUIDED para que el autopilot pueda controlar el aterrizaje
            print('Cambiando a modo GUIDED para aterrizaje automático')
            dron.setFlightMode('GUIDED')
            dron.Land()
    elif action == 'rtl':
        if dron.state == 'flying':
            print('RTL desde modo piloto')
            # Detener loop RC
            pilot_mode_active = False
            print('Loop RC detenido')
            # Cambiar a GUIDED para que el autopilot pueda controlar el RTL
            print('Cambiando a modo GUIDED para RTL automático')
            dron.setFlightMode('GUIDED')
            dron.RTL()

@sio.on("set_parameters")
def handle_set_parameters(params):
    """Handler para configurar parámetros del dron"""
    global webapp_commands_enabled
    
    if not webapp_commands_enabled:
        print('PARÁMETROS BLOQUEADOS: (WebApp no autorizada)')
        return
    
    print('=' * 50)
    print('Configurando parámetros del dron:')
    for param in params:
        print(f"  {param['ID']}: {param['Value']}")
    print('=' * 50)
    
    try:
        # Usar la función setParams del dron
        # Esta función acepta una lista de diccionarios con 'ID' y 'Value'
        dron.setParams(params, blocking=True)
        print('✓ Parámetros configurados correctamente')
        
        # Opcionalmente, verificar que se aplicaron correctamente
        param_names = [p['ID'] for p in params]
        valores_actuales = dron.getParams(param_names, blocking=True)
        print('\nVerificación de parámetros aplicados:')
        for valor in valores_actuales:
            for key, val in valor.items():
                print(f"  {key}: {val}")
        
    except Exception as e:
        print(f'✗ Error al configurar parámetros: {e}')
        import traceback
        traceback.print_exc()

@sio.on("video_settings")
def handle_video_settings(settings):
    """Handler para configurar calidad y fps del video"""
    global qualitySlider, frequencySlider, webapp_commands_enabled, ventana
    
    if not webapp_commands_enabled:
        print('CONFIGURACIÓN DE VIDEO BLOQUEADA: (WebApp no autorizada)')
        return
    
    quality = settings.get('quality', 100)
    fps = settings.get('fps', 30)
    
    print('=' * 50)
    print('📹 Configuración de video recibida desde WebApp:')
    print(f'  Calidad: {quality}%')
    print(f'  FPS: {fps}')
    print('=' * 50)
    
    try:
        # Actualizar los sliders de la interfaz de EstacionDeTierra usando root.after()
        # para evitar problemas de thread-safety con Tkinter
        def update_sliders():
            try:
                qualitySlider.set(quality)
                frequencySlider.set(fps)
                print('✓ Configuración de video aplicada correctamente')
                print(f'  - Slider de calidad actualizado a: {quality}%')
                print(f'  - Slider de FPS actualizado a: {fps} fps')
            except Exception as e:
                print(f'✗ Error al actualizar sliders: {e}')
        
        # Programar la actualización en el thread principal de Tkinter
        ventana.after(0, update_sliders)
        
    except Exception as e:
        print(f'✗ Error al configurar video: {e}')
        import traceback
        traceback.print_exc()

@sio.on("correccion")
def handle_fisheye_toggle(payload):
    """Handler para activar/desactivar corrección de distorsión (ojo de pez).
    Espera un payload con { enabled: bool, calibration_path?: str }.
    """
    global webapp_commands_enabled
    global fisheye_enabled, fisheye_ready, cam_matrix, dist_coefs, new_cam_mtx, roi
    
    if not webapp_commands_enabled:
        print('CORRECCIÓN BLOQUEADA: (WebApp no autorizada)')
        return
    
    try:
        enabled = False
        calibration_path = None
        if isinstance(payload, dict):
            enabled = bool(payload.get('enabled', False))
            calibration_path = payload.get('calibration_path')
        else:
            enabled = bool(payload)
        
        fisheye_enabled = enabled
        fisheye_ready = False  # recalcular matrices al próximo frame
        
        if enabled:
            # Determinar ruta de calibración
            if not calibration_path:
                calibration_path = default_calibration_path
            # Fallback: intentar en la raíz del proyecto si no existe en EstacionTierra
            if not os.path.exists(calibration_path):
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                alt_path = os.path.join(project_root, 'output21', 'calibration_data_px.yaml')
                if os.path.exists(alt_path):
                    calibration_path = alt_path
            
            print('=' * 50)
            print('🐟 Activando corrección de ojo de pez')
            print(f'  Archivo de calibración: {calibration_path}')
            print('=' * 50)
            
            if not os.path.exists(calibration_path):
                print(f"✗ Archivo de calibración no encontrado: {calibration_path}")
                print("   Desactivando corrección por falta de datos de calibración")
                fisheye_enabled = False
                return
            
            try:
                with open(calibration_path, 'r') as f:
                    data = yaml.safe_load(f)
                cam_matrix = np.array(data.get('camera_matrix'))
                dist_coefs = np.array(data.get('distortion_coefficients'))
                new_cam_mtx = None
                roi = None
                print('✓ Datos de calibración cargados')
            except Exception as e:
                print(f'✗ Error leyendo calibración: {e}')
                import traceback
                traceback.print_exc()
                fisheye_enabled = False
        else:
            print('🐟 Corrección de ojo de pez DESACTIVADA')
    except Exception as e:
        print(f'✗ Error en handler de corrección: {e}')
        import traceback
        traceback.print_exc()

@sio.on('zoom')
def handle_zoom(data):
    """Handler para recibir comandos de zoom desde la WebApp"""
    global zoom_level, zoom_center
    
    try:
        x = data.get('x', 0)
        y = data.get('y', 0)
        level = data.get('level', 1.0)
        
        with zoom_lock:
            zoom_level = level
            zoom_center = (x, y)
        
        print(f"🔍 Zoom actualizado: level={level:.2f}, center=({x}, {y})")
    except Exception as e:
        print(f"❌ Error procesando zoom: {e}")

@sio.on('zoom_reset')
def handle_zoom_reset():
    """Handler para resetear el zoom a valores por defecto"""
    global zoom_level, zoom_center
    
    try:
        with zoom_lock:
            zoom_level = 1.0
            zoom_center = None
        
        print("🔍 Zoom reseteado: level=1.0, center=None")
    except Exception as e:
        print(f"❌ Error reseteando zoom: {e}")

@sio.on("request_gallery")
def handle_request_gallery():
    """Handler para solicitar la lista de fotos y videos de la galería"""
    global webapp_commands_enabled
    
    if not webapp_commands_enabled:
        print('SOLICITUD DE GALERÍA BLOQUEADA: (WebApp no autorizada)')
        return
    
    print('📂 Solicitud de galería recibida desde WebApp')
    
    try:
        archivos = []
        
        # Obtener ruta base de EstacionTierra
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Directorio de fotos
        photos_dir = os.path.join(base_dir, 'captured_photos')
        if os.path.exists(photos_dir):
            for carpeta_vuelo in os.listdir(photos_dir):
                carpeta_path = os.path.join(photos_dir, carpeta_vuelo)
                if os.path.isdir(carpeta_path):
                    for archivo in os.listdir(carpeta_path):
                        if archivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                            archivo_path = os.path.join(carpeta_path, archivo)
                            fecha = os.path.getmtime(archivo_path)
                            archivos.append({
                                'tipo': 'foto',
                                'nombre': f"{carpeta_vuelo}/{archivo}",
                                'fecha': fecha
                            })
        else:
            print(f'⚠️  Directorio de fotos no existe: {photos_dir}')
        
        # Directorio de videos
        videos_dir = os.path.join(base_dir, 'captured_videos')
        if os.path.exists(videos_dir):
            for carpeta_vuelo in os.listdir(videos_dir):
                carpeta_path = os.path.join(videos_dir, carpeta_vuelo)
                if os.path.isdir(carpeta_path):
                    for archivo in os.listdir(carpeta_path):
                        if archivo.lower().endswith(('.mp4', '.avi', '.mov')):
                            archivo_path = os.path.join(carpeta_path, archivo)
                            fecha = os.path.getmtime(archivo_path)
                            archivos.append({
                                'tipo': 'video',
                                'nombre': f"{carpeta_vuelo}/{archivo}",
                                'fecha': fecha
                            })
        else:
            print(f'⚠️  Directorio de videos no existe: {videos_dir}')
        
        print(f'✓ Se encontraron {len(archivos)} archivos en la galería')
        
        # Enviar la lista de archivos al cliente
        sio.emit('gallery_files', archivos)
        
    except Exception as e:
        print(f'✗ Error al obtener galería: {e}')
        import traceback
        traceback.print_exc()
        sio.emit('gallery_files', [])

print("Conectado al websocket")
dron = Dron()

ventana = tk.Tk()
ventana.geometry ('450x780')
ventana.title("Estación de Tierra")

# La interfaz tiene 16 filas y una columna

ventana.rowconfigure(0, weight=1)
ventana.rowconfigure(1, weight=1)
ventana.rowconfigure(2, weight=1)
ventana.rowconfigure(3, weight=1)
ventana.rowconfigure(4, weight=1)
ventana.rowconfigure(5, weight=1)
ventana.rowconfigure(6, weight=1)
ventana.rowconfigure(7, weight=1)
ventana.rowconfigure(8, weight=1)
ventana.rowconfigure(9, weight=1)
ventana.rowconfigure(10, weight=1)
ventana.rowconfigure(11, weight=1)
ventana.rowconfigure(12, weight=1)
ventana.rowconfigure(13, weight=1)
ventana.rowconfigure(14, weight=1)
ventana.rowconfigure(15, weight=1)

ventana.columnconfigure(0, weight=1)

# Disponemos de 15 botones y 1 label
modeBtn = tk.Button(ventana, text="Modo: SIMULACIÓN", bg="light blue", command=toggle_connection_mode) # Por defecto inicializa en simulación pero al darle clic inicia en producción
modeBtn.grid(row=0, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

connectBtn = tk.Button(ventana, text="Conectar", bg="dark orange", command=conectar_local)
connectBtn.grid(row=1, column=0, padx=3, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

armBtn = tk.Button(ventana, text="Armar", bg="dark orange", command=armar_dron)
armBtn.grid(row=2, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

takeOffBtn = tk.Button(ventana, text="Despegar", bg="dark orange", command=despegar_dron)
takeOffBtn.grid(row=3, column=0,  padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

NorthBtn = tk.Button(ventana, text="Norte", bg="dark orange", command=lambda: dron.go('North'))
NorthBtn.grid(row=4, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

SouthBtn = tk.Button(ventana, text="Sur", bg="dark orange", command=lambda: dron.go('South'))
SouthBtn.grid(row=5, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

EastBtn = tk.Button(ventana, text="Este", bg="dark orange", command=lambda: dron.go('East'))
EastBtn.grid(row=6, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

WestBtn = tk.Button(ventana, text="Oeste", bg="dark orange", command=lambda: dron.go('West'))
WestBtn.grid(row=7, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

StopBtn = tk.Button(ventana, text="Parar", bg="dark orange", command=lambda: dron.go('Stop'))
StopBtn.grid(row=8, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

RTLBtn = tk.Button(ventana, text="RTL", bg="dark orange", command=lambda: rtl_with_feedback())
RTLBtn.grid(row=9, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

disconnectBtn = tk.Button(ventana, text="Desconectar", bg="dark orange", command=desconectar_con_feedback)
disconnectBtn.grid(row=10, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

allowExternalBtn = tk.Button(ventana, text="Conectar WebApp", bg="violet", command= allowExternal)
allowExternalBtn.grid(row=11, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

videoWebsocketBtn = tk.Button(ventana, text="Activar cámara dron", bg="violet", command=videoWebsockets)
videoWebsocketBtn.grid(row=12, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

galleryBtn = tk.Button(ventana, text="Ver galería", bg="violet", command=open_gallery)
galleryBtn.grid(row=13, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

cameraBtn = tk.Button(ventana, text="Recibir video del móvil", bg="violet", command=recibirCamara)
cameraBtn.grid(row=14, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

videoStreamControlFrame = tk.LabelFrame(ventana, text="Video stream control", padx=5, pady=5)
videoStreamControlFrame.grid(row=15, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)
videoStreamControlFrame.columnconfigure(0, weight=1)
videoStreamControlFrame.columnconfigure(1, weight=1)
videoStreamControlFrame.rowconfigure(0, weight=1)
videoStreamControlFrame.rowconfigure(1, weight=1)

# Controlar la calidad de la cámara del dron
tk.Label(videoStreamControlFrame, text="Quality").grid(row=0, column=0, pady=4, padx=0)
qualitySlider = tk.Scale(
    videoStreamControlFrame,
    from_=0,
    to=100,
    length=100,
    orient="horizontal",
    activebackground="green",
    tickinterval=20,
    resolution=10
)
qualitySlider.grid(row=0, column=1, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)
qualitySlider.set(50)

# Controlar la fluidez (frames/s) de la cámara del dron
tk.Label(videoStreamControlFrame, text="Frames/s").grid(row=1, column=0, pady=4, padx=0)
frequencySlider = tk.Scale(
    videoStreamControlFrame,
    from_=0,
    to=30,
    length=100,
    orient="horizontal",
    activebackground="green",
    tickinterval=5,
    resolution=1
)
frequencySlider.set(30)
frequencySlider.grid(row=1, column=1, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

# Deshabilitar todos los botones excepto "Modo", "Conectar" y "Conectar WebApp" al iniciar
# Solo permitir cambiar modo, conectar al dron, conectar a la WebApp al inicio, activar camara del dron recibir video del móvil y ver galeria.
deshabilitar_boton(armBtn)
deshabilitar_boton(takeOffBtn)
deshabilitar_boton(NorthBtn)
deshabilitar_boton(SouthBtn)
deshabilitar_boton(EastBtn)
deshabilitar_boton(WestBtn)
deshabilitar_boton(StopBtn)
deshabilitar_boton(RTLBtn)
deshabilitar_boton(disconnectBtn, "desconectado")

# Precargar modelo YOLO al inicio
print("🚀 Precargando modelo YOLO...")
try:
    yolo_model = YOLO('yolov8s.pt')
    print("✅ Modelo YOLO precargado y listo")
except Exception as e:
    print(f"⚠️  No se pudo precargar YOLO: {e}")
    yolo_model = None

ventana.mainloop()