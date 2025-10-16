# IMPORTANTE: Interprete Pyhton 3.9 e instalar pymavlink, paho-mqtt (version 1.6.1), opencv-python, python-socketio, requests, websocket-client, pillow, pyserial (para conectar a Dron Real)
import json
import tkinter as tk
from dronLink.Dron import Dron
import random
import paho.mqtt.client as mqtt
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
import re


def allowExternal ():
    global client
    global allowExternalBtn
    clientName = "demoDash" + str(random.randint(1000, 9000))
    client = mqtt.Client(clientName, transport="websockets")

    # broker_address = 'broker.hivemq.com'
    broker_address = "dronseetac.upc.edu"
    broker_port = 8000

    client.username_pw_set(
        'dronsEETAC' , 'mimara1456.'
    )

    client.on_message = on_message
    client.on_connect = on_connect
    client.connect(broker_address, broker_port)
    print('Conectado al broker')

    # me subscribo a cualquier mensaje  que venga del mobileFlask
    client.subscribe('mobileFlask/demoDash/#')
    print('demoDash esperando peticiones ')
    client.loop_start()
    allowExternalBtn['text'] = "Conexión a WebApp autorizada"
    allowExternalBtn['fg'] = 'white'
    allowExternalBtn['bg'] = 'green'

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("connected OK Returned code=", rc)
    else:
        print("Bad connection Returned code=", rc)

def procesarTelemetria(telemetryInfo):
    # cada vez que recibo un paquete de telemetría del dron lo envio al broker
    client.publish('demoDash/mobileFlask/telemetryInfo', json.dumps(telemetryInfo))

def publish_event ( event):
    # publico en el broker el evento, que en este caso será 'flying' porque es el único que se considera en esta aplicación
    print ('en el aire')
    client.publish('demoDash/mobileFlask/'+event)


# Variables globales para el modo de conexión
connection_mode = "simulation"  # Por defecto simulación
com_port = "com"  # Puerto COM por defecto

# Ejecuta el botón para conectar de la Estacion de Tierra en el modo que escojamos
def conectar_local():
    if connection_mode == "simulation":
        dron.connect('tcp:127.0.0.1:5763', 115200)
        print('Conectando localmente en modo SIMULACIÓN')
    else:
        dron.connect(com_port, 57600)
        print(f'Conectando localmente en modo PRODUCCIÓN en puerto {com_port.upper()}')

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

# aqui recibimos los mensajes de la WebApp
def on_message(client, userdata, message):
        global dron
        # el formato del topic siempre será: mobileFlask/demoDash/comando

        parts = message.topic.split ('/')
        command = parts[2]
        print ('recibo ', command)
        if command == 'connect':
            # Selecciono los parámetros según el modo
            if connection_mode == "simulation":
                connection_string = 'tcp:127.0.0.1:5763'  # Simulación
                baud = 115200  # Simulación
                print('Conectando en modo SIMULACIÓN')
            else:
                connection_string = com_port  # Dron Real con puerto personalizado (producción)
                baud = 57600  # Dron Real (producción)
                print(f'Conectando en modo PRODUCCIÓN en puerto {com_port.upper()}')

            dron.connect(connection_string, baud)
            print('conectado')
            # le pido los datos de telemetria y le indico la función a ejecutar cada vez que tenga un nuevo paquete de datos
            print('pido datos de telemetria')
            dron.send_telemetry_info(procesarTelemetria)

        if command == 'arm_takeOff':
            if dron.state == 'connected':
                # recupero la altura a alcanzar, que viene como payload del mensaje
                alt = int( message.payload.decode("utf-8"))
                dron.arm()
                print ('armado')
                # operación no bloqueante. Cuando acabe publicará el evento correspondiente
                dron.takeOff(alt, blocking=False, callback=publish_event, params='flying')

        if command == 'go':
            if dron.state == 'flying':
                direction = message.payload.decode("utf-8")
                print ('vamos al: ', direction)
                dron.go(direction)

        if command == 'Land':
            if dron.state == 'flying':
                print ('voy a aterrizar')
                # operación no bloqueante
                dron.Land(blocking=False)

        if command == 'RTL':
            if dron.state == 'flying':
                print('Ejecutando RTL')
                # operación no bloqueante
                dron.RTL(blocking=False)

        if command == 'goto':
            if dron.state == 'flying':
                try:
                    coords = json.loads(message.payload.decode("utf-8"))
                    lat = float(coords["lat"])
                    lng = float(coords["lng"])
                    print(f'Moviendo dron a: lat={lat}, lon={lng}')
                    dron.goto(lat, lng, dron.alt, blocking=False)
                except Exception as e:
                    print(f"Error en goto: {str(e)}")

        if command == 'capturarFoto':
            print('Capturando foto del último frame')
            capturar_foto()

        if command == 'iniciarVideo':
            print('Iniciando grabación de video')
            start_recording()

        if command == 'detenerVideo':
            print('Deteniendo grabación de video')
            stop_recording()

        if command == 'waypointRuta':
            if dron.state == 'flying':
                try:
                    ruta = json.loads(message.payload.decode("utf-8"))

                    def recorrer_ruta():
                        for idx, wp in enumerate(ruta):
                            lat = wp["lat"]
                            lng = wp["lng"]
                            captura = wp.get("captura", "ninguna")
                            duracion = int(wp.get("duracion", 0))

                            print(f"[{idx + 1}/{len(ruta)}] Moviendo a waypoint: ({lat}, {lng})")

                            # Usar blocking=False y esperar manualmente
                            dron.goto(lat, lng, dron.alt, blocking=False)

                            # Esperar a que llegue al waypoint usando la función interna del dron
                            tiempo_max_espera = 30  # segundos máximo de espera
                            tiempo_inicio = time.time()

                            while time.time() - tiempo_inicio < tiempo_max_espera:
                                # Calcular distancia usando la función del dron
                                try:
                                    dist = dron._distanceToDestinationInMeters(lat, lng)
                                    if dist <= 1.0:  # Umbral de llegada en metros
                                        print(f"El dron ha llegado al waypoint {idx + 1}")
                                        break
                                except:
                                    # Si hay error calculando distancia, usar coordenadas actuales
                                    dlat = abs(dron.lat - lat)
                                    dlon = abs(dron.lon - lng)
                                    if dlat < 0.00001 and dlon < 0.00001:
                                        break

                                time.sleep(0.5)  # Esperar medio segundo antes de revisar de nuevo

                            # Pequeña pausa adicional para estabilizar
                            time.sleep(1)

                            # Realizar la acción correspondiente
                            if captura == "foto":
                                print(f"Capturando foto en waypoint {idx + 1}")
                                success = capturar_foto()
                                if success:
                                    print(f"Foto {idx + 1} guardada correctamente")
                                else:
                                    print(f"Error al capturar foto en waypoint {idx + 1}")
                                time.sleep(1)  # Esperar tras la foto

                            elif captura == "video":
                                print(f"Iniciando grabación de video en waypoint {idx + 1} por {duracion} seg")
                                success = start_recording()
                                if success:
                                    time.sleep(duracion)  # Grabar la duración especificada por el usuario
                                    stop_recording()
                                    print(f"Video de {duracion}s completado en waypoint {idx + 1}")
                                else:
                                    print(f"Error al iniciar video en waypoint {idx + 1}")
                                time.sleep(1)  # Esperar tras el video

                        print("Ruta completada")

                    threading.Thread(target=recorrer_ruta).start()

                except Exception as e:
                    print(f"Error en la ruta: {e}")

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
                client.publish('demoDash/mobileFlask/flightNameSet', current_flight_name)
            else:
                messagebox.showerror("Error", "Debe introducir un nombre para el vuelo")

        # Botón para iniciar el stream
        start_button = tk.Button(flight_name_window, text="Iniciar", bg="green", fg="white", command=start_video_stream)
        start_button.pack(pady=10)

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

    sendingWebsockets = True
    while sendingWebsockets:
        if frequencySlider.get() > 0:
            ret, frame = cap.read()
            if not ret:
                print("Error: No se pudo leer frame de la cámara")
                break
            # Almacena el último frame capturado
            last_frame = frame.copy()
            # genero el frame con el nivel de calidad seleccionado (entre 0 y 100)
            quality = qualitySlider.get()
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            # envio el frame por el websocket
            sio.emit('video_frame', frame_b64)
            # espera el tiempo establecido según la frecuencia seleccionada
            periodo = 1/frequencySlider.get()
            time.sleep(periodo)

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
        # Envia la confirmación al cliente
        client.publish('demoDash/mobileFlask/fotoCapturada', filename)
        return True
    else:
        print("No hay frame disponible para capturar")
        client.publish('demoDash/mobileFlask/fotoError', "No hay imagen disponible")
        return False

# Inicia una grabación de la cámara del dron
def start_recording():
    global recording, video_writer, last_frame, current_flight_name

    if recording:
        return False  # Ya estamos grabando

    # Crea un directorio para este vuelo si no existe
    videos_dir = "captured_videos"
    if current_flight_name:
        videos_dir = os.path.join(videos_dir, current_flight_name)

    if not os.path.exists(videos_dir):
        os.makedirs(videos_dir)
        print(f"Directorio {videos_dir} creado.")

    # Genera nombre de archivo con timestamp
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"video_dron_{timestamp}.avi"
    filepath = os.path.join(videos_dir, filename)

    # Configura el VideoWriter
    if last_frame is not None:
        height, width = last_frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))

        # Inicia grabación en un hilo separado
        recording = True
        video_thread = threading.Thread(target=record_video_thread, args=(filepath,))
        video_thread.start()

        print(f"Grabación iniciada: {filepath}")
        client.publish('demoDash/mobileFlask/videoIniciado', filename)
        return True
    else:
        print("No hay frame disponible para iniciar grabación")
        client.publish('demoDash/mobileFlask/videoError', "No hay imagen disponible")
        return False

# Detiene la grabación del video de la cámara del dron
def stop_recording():
    global recording, video_writer

    if not recording:
        return False  # No estamos grabando

    recording = False
    if video_writer is not None:
        video_writer.release()
        video_writer = None
        print("Grabación detenida")
        client.publish('demoDash/mobileFlask/videoDetenido')
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

# Grabar video sin estar viendo la camara
def grabar_video_en_background(duracion, flight_name, frame_inicial):
    global last_frame

    if frame_inicial is None:
        print("No hay frame para iniciar la grabación")
        return

    # Crear carpeta
    videos_dir = os.path.join("captured_videos", flight_name)
    if not os.path.exists(videos_dir):
        os.makedirs(videos_dir)

    # Nombre del archivo
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"video_dron_{timestamp}.avi"
    filepath = os.path.join(videos_dir, filename)

    # VideoWriter independiente
    height, width = frame_inicial.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    writer = cv2.VideoWriter(filepath, fourcc, 20.0, (width, height))

    # Grabación en bucle
    start_time = time.time()
    while time.time() - start_time < duracion:
        if last_frame is not None:
            writer.write(last_frame)
        time.sleep(0.05)

    writer.release()
    print(f"Video guardado en {filepath}")
    client.publish('demoDash/mobileFlask/videoIniciado', filename)
    client.publish('demoDash/mobileFlask/videoDetenido')

# Recibir thread del frame de la camara del movil
def recibirCamaraThread():
    global latest_frame
    global receivingCamera
    global contador
    # El nombre de la ventana tiene que ser diferente cada vez que inicio el thread, para eso uso el contador
    while receivingCamera:
        if latest_frame is not None:
            cv2.imshow("Video camara " + str(contador), latest_frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

# Se recibe la camara del movil
def recibirCamara ():
    global receivingCamera
    global cameraBtn
    global contador

    if receivingCamera:
        receivingCamera = False
        cameraBtn['text'] = "Recibir video del movil"
        cameraBtn['fg'] = 'black'
        cameraBtn['bg'] = 'violet'
    else:
        contador = contador + 1
        receivingCamera = True
        cameraBtn['text'] = "Detener video del movil"
        cameraBtn['fg'] = 'white'
        cameraBtn['bg'] = 'green'
        threading.Thread (target = recibirCamaraThread).start()

# Crea la ventana para mostrar el video del dron
def create_video_display():
    global video_display_window, video_label

    video_display_window = tk.Toplevel(ventana)
    video_display_window.title(f"Video del Dron - {current_flight_name}")
    video_display_window.geometry("800x600")

    # Frame principal
    main_frame = tk.Frame(video_display_window)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Label para mostrar el video
    video_label = tk.Label(main_frame, text="Esperando video...", bg="black", fg="white")
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
        sendingWebsockets = False
        showing_video = False
        videoWebsocketBtn['text'] = "Activar cámara dron"
        videoWebsocketBtn['fg'] = 'black'
        videoWebsocketBtn['bg'] = 'violet'
        video_display_window.destroy()

    video_display_window.protocol("WM_DELETE_WINDOW", on_closing)

# Thread para actualizar la visualización del video
def update_video_display():
    global video_label, last_frame, showing_video, video_display_window

    while showing_video and video_display_window and video_display_window.winfo_exists():
        try:
            if last_frame is not None and video_label:
                # Convertir frame de BGR a RGB
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
sendingMQTT = False
sendingWebsockets = False
last_frame = None # Variable para almacenar el último frame (la foto)
sio = socketio.Client()
recording = False
video_writer = None
video_thread = None
current_flight_name = None  # Variable para almacenar el nombre del vuelo actual
gallery_window = None
selected_flight = None
video_display_window = None
video_label = None
showing_video = False

receivingCamera = False
contador = 0

# esto es para conectarme al websocket del servidor en desarrollo
sio.connect('http://localhost:8766')

# esto es para conectarme al websocket del servidor en producción
#sio.connect('http://dronseetac.upc.edu:8102')

@sio.event
def processed_frame(data):
    # aqui entramos cada vez que recibimos un frame de la cámara del movil
    global latest_frame
    print ("recibo frame de camara")
    frame_bytes = base64.b64decode(data.split(",")[1])
    # Convertir los bytes en un array NumPy
    np_arr = np.frombuffer(frame_bytes, np.uint8)
    # Decodificar la imagen
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    latest_frame = frame

@sio.on("go")
def handle_go(direction):
    print(f"MediaPipe pidió mover al dron: {direction}")
    if dron.state == "flying":
        dron.changeNavSpeed(2)  # Limita la velocidad a 2 m/s en MediaPipe
    dron.go(direction)

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

armBtn = tk.Button(ventana, text="Armar", bg="dark orange", command=lambda: dron.arm())
armBtn.grid(row=2, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

takeOffBtn = tk.Button(ventana, text="Despegar", bg="dark orange", command=lambda: dron.takeOff(3))
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

RTLBtn = tk.Button(ventana, text="RTL", bg="dark orange", command=lambda: dron.RTL())
RTLBtn.grid(row=9, column=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)

disconnectBtn = tk.Button(ventana, text="Desconectar", bg="dark orange", command=lambda: dron.disconnect())
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
frequencySlider.set(5)
frequencySlider.grid(row=1, column=1, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)


### Código para la recepción de peticiones a través de MQTT

'''client.on_message = on_message
client.on_connect = on_connect
client.connect(broker_address, broker_port)
print('Conectado a broker.hivemq.com:8000')

# me subscribo a cualquier mensaje  que venga del mobileFlask
client.subscribe('mobileFlask/demoDash/#')
print('demoDash esperando peticiones ')
client.loop_start()'''

ventana.mainloop()