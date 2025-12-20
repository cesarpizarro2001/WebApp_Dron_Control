/**
 * mediapipe_hands_processor.js
 * Procesador de gestos con MediaPipe Hands en el navegador
 * 
 * Replica EXACTAMENTE el comportamiento del código Python:
 * - Dibuja landmarks (puntos rojos/blancos)
 * - Dibuja conexiones (líneas verdes)
 * - Dibuja chuleta de gestos (esquina inferior izquierda)
 * - Dibuja texto "Orden: NORTE" (esquina superior izquierda)
 * - Detecta gestos y envía comandos vía Socket.IO
 */

class MediaPipeHandsProcessor {
    constructor(videoElement, canvasElement, socket) {
        this.video = videoElement;
        this.canvas = canvasElement;
        this.ctx = this.canvas.getContext('2d');
        this.socket = socket;
        this.hands = null;
        this.camera = null;
        // Último comando EMITIDO (tras estabilización)
        this.lastCommand = null;
        this.gestureImages = {};
        this.isProcessing = false;

        // Estabilización temporal de comandos (menos sensibilidad)
        this.pendingCommand = null;     // Comando detectado actualmente (candidato)
        this.pendingSince = 0;          // Timestamp desde que se detectó el candidato
        this.pendingFrames = 0;         // Frames consecutivos con el mismo candidato
        this.lastEmittedAt = 0;         // Timestamp del último comando emitido
        this.minFrames = 4;             // Mínimo de frames consecutivos
        this.holdTimesMs = {            // Tiempo mínimo de mantenimiento por comando
            'LAND': 1200,
            'DESPEGAR': 800,
            'STOP': 600,
            'NORTE': 300,
            'SUR': 300,
            'ESTE': 300,
            'OESTE': 300
        };
        this.cooldownsMs = {            // Intervalo mínimo entre emisiones por comando
            'LAND': 2000,
            'DESPEGAR': 1500,
            'STOP': 600,
            'NORTE': 300,
            'SUR': 300,
            'ESTE': 300,
            'OESTE': 300
        };
        
        // Configuración de gestos (igual que Python)
        this.gesturesInfo = [
            { key: 'norte', name: 'Norte', color: 'rgb(0, 255, 0)' },      // Verde
            { key: 'sur', name: 'Sur', color: 'rgb(0, 255, 0)' },          // Verde
            { key: 'oeste', name: 'Oeste', color: 'rgb(0, 255, 0)' },      // Verde
            { key: 'este', name: 'Este', color: 'rgb(0, 255, 0)' },        // Verde
            { key: 'stop', name: 'Stop', color: 'rgb(0, 0, 255)' },        // Rojo
            { key: 'despegar', name: 'Despegar', color: 'rgb(255, 0, 0)' },// Azul
            { key: 'aterrizar', name: 'Aterrizar', color: 'rgb(255, 0, 0)' } // Azul
        ];
        
        console.log('📱 [MediaPipe] Procesador inicializado');
    }
    
    /**
     * Carga las imágenes de gestos para la chuleta
     */
    async loadGestureImages() {
        const gestureFiles = {
            'norte': 'pulgar_arriba.PNG',
            'sur': 'pulgar_abajo.PNG',
            'oeste': 'pulgar_izquierda.PNG',
            'este': 'pulgar_derecha.PNG',
            'stop': 'cinco_dedos.PNG',
            'despegar': 'ok.PNG',
            'aterrizar': 'pulgar_indice.PNG'
        };
        
        for (const [key, filename] of Object.entries(gestureFiles)) {
            try {
                const img = new Image();
                img.crossOrigin = 'anonymous';
                // Ruta desde static/gestos
                img.src = `/static/gestos/${filename}`;
                
                await new Promise((resolve, reject) => {
                    img.onload = () => {
                        this.gestureImages[key] = img;
                        console.log(`✅ Imagen cargada: ${key}`);
                        resolve();
                    };
                    img.onerror = () => {
                        console.warn(`⚠️ No se pudo cargar imagen: ${key} desde ${img.src}`);
                        resolve(); // Continuar aunque falle
                    };
                });
            } catch (e) {
                console.warn(`⚠️ Error cargando imagen ${key}:`, e);
            }
        }
    }
    
    /**
     * Inicializa MediaPipe Hands
     */
    async init() {
        console.log('🔧 [MediaPipe] Inicializando MediaPipe Hands...');
        
        // Cargar imágenes de gestos
        await this.loadGestureImages();
        
        // Crear instancia de Hands
        this.hands = new Hands({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }
        });
        
        // Configurar opciones más estrictas para evitar falsos positivos (cara/labios)
        this.hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.8,
            minTrackingConfidence: 0.8
        });
        
        // Handler para resultados
        this.hands.onResults((results) => this.onResults(results));
        
        console.log('✅ [MediaPipe] MediaPipe Hands inicializado');
    }
    
    /**
     * Inicia el procesamiento de video
     */
    async start() {
        if (this.isProcessing) {
            console.warn('⚠️ Ya está procesando');
            return;
        }
        
        console.log('▶️ [MediaPipe] Iniciando procesamiento...');
        
        // Ajustar tamaño del canvas al video
        this.canvas.width = this.video.videoWidth || 640;
        this.canvas.height = this.video.videoHeight || 480;
        
        // Crear cámara de MediaPipe
        this.camera = new Camera(this.video, {
            onFrame: async () => {
                if (this.hands && this.isProcessing) {
                    await this.hands.send({ image: this.video });
                }
            },
            width: 640,
            height: 480
        });
        
        this.isProcessing = true;
        await this.camera.start();
        
        console.log('✅ [MediaPipe] Procesamiento iniciado');
    }
    
    /**
     * Detiene el procesamiento
     */
    stop() {
        console.log('⏹️ [MediaPipe] Deteniendo procesamiento...');
        
        this.isProcessing = false;
        
        if (this.camera) {
            this.camera.stop();
            this.camera = null;
        }
        
        // Limpiar canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        console.log('✅ [MediaPipe] Procesamiento detenido');
    }
    
    /**
     * Callback cuando MediaPipe procesa un frame
     * Replica EXACTAMENTE el comportamiento de process_frame_hands en Python
     */
    onResults(results) {
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        // === IMPORTANTE: Dibujar el video primero ===
        // Esto asegura que el canvas muestre el video de fondo
        this.ctx.save();
        this.ctx.clearRect(0, 0, width, height);
        this.ctx.drawImage(results.image, 0, 0, width, height);
        this.ctx.restore();
        
        // Dibujar chuleta de gestos (igual que Python)
        this.drawGestureCheatSheet();
        
        // Comando detectado en este frame (sin estabilización)
        let detected = null;
        
        // Si hay manos detectadas
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            // Procesar cada mano detectada con filtros de plausibilidad
            for (let i = 0; i < results.multiHandLandmarks.length; i++) {
                const landmarks = results.multiHandLandmarks[i];

                // Filtrar por confidence de handedness si disponible
                let handednessOk = true;
                if (results.multiHandedness && results.multiHandedness[i]) {
                    handednessOk = (results.multiHandedness[i].score || 0) >= 0.8;
                }
                if (!handednessOk) continue;
                // Dibujar conexiones (líneas verdes)
                drawConnectors(this.ctx, landmarks, HAND_CONNECTIONS, {
                    color: '#00FF00',  // Verde
                    lineWidth: 2
                });
                
                // Dibujar landmarks (puntos)
                drawLandmarks(this.ctx, landmarks, {
                    color: '#FF0000',      // Rojo
                    fillColor: '#FFFFFF',  // Blanco
                    lineWidth: 1,
                    radius: 3
                });
                
                // Comprobar tamaño de palma para evitar falsos positivos (ej. labios)
                const widthPx = this.canvas.width;
                const getPoint = (index) => ({
                    x: landmarks[index].x * widthPx,
                    y: landmarks[index].y * this.canvas.height,
                    z: landmarks[index].z
                });
                const wrist = getPoint(0);
                const index_mcp = getPoint(5);
                const distance = (p1, p2) => Math.hypot(p1.x - p2.x, p1.y - p2.y);
                const palmSize = distance(wrist, index_mcp);
                const minPalm = widthPx * 0.08; // ~8% del ancho: umbral de tamaño
                if (palmSize < minPalm) {
                    // Demasiado pequeño: probablemente no es una mano real
                    continue;
                }

                // Detectar gesto (misma lógica) tras pasar filtros
                detected = this.detectGesture(landmarks) || detected;
            }
        }
        
        // Mostrar comando detectado (UI responsiva), aunque la emisión se estabiliza
        if (detected) {
            this.drawCommand(detected);
        }

        // Estabilizar y emitir comando si cumple criterios de tiempo/frames
        this._maybeEmitCommand(detected);
    }
    
    /**
     * Detecta el gesto de la mano
     * MISMA LÓGICA EXACTA que Python
     */
    detectGesture(landmarks) {
        const width = this.canvas.width;
        
        // Convertir landmarks normalizados a coordenadas de píxeles
        const getPoint = (index) => ({
            x: landmarks[index].x * width,
            y: landmarks[index].y * this.canvas.height,
            z: landmarks[index].z
        });
        
        // Puntos clave (igual que Python)
        const wrist = getPoint(0);
        const thumb_tip = getPoint(4);
        const index_tip = getPoint(8);
        const middle_tip = getPoint(12);
        const ring_tip = getPoint(16);
        const pinky_tip = getPoint(20);
        
        const thumb_mcp = getPoint(2);
        const index_mcp = getPoint(5);
        const middle_mcp = getPoint(9);
        const ring_mcp = getPoint(13);
        const pinky_mcp = getPoint(17);
        
        const index_pip = getPoint(6);
        const middle_pip = getPoint(10);
        const ring_pip = getPoint(14);
        const pinky_pip = getPoint(18);
        
        // Función de distancia (igual que Python)
        const distance = (p1, p2) => {
            return Math.sqrt(
                Math.pow(p1.x - p2.x, 2) + 
                Math.pow(p1.y - p2.y, 2)
            );
        };
        
        // Verificar dedos extendidos (MISMA LÓGICA que Python)
        const thumb_extended = distance(thumb_tip, wrist) > distance(thumb_mcp, wrist) * 1.2;
        const index_extended = distance(index_tip, wrist) > distance(index_pip, wrist) * 1.3;
        const middle_extended = distance(middle_tip, wrist) > distance(middle_pip, wrist) * 1.3;
        const ring_extended = distance(ring_tip, wrist) > distance(ring_pip, wrist) * 1.3;
        const pinky_extended = distance(pinky_tip, wrist) > distance(pinky_pip, wrist) * 1.3;
        
        const fingers_extended = [thumb_extended, index_extended, middle_extended, ring_extended, pinky_extended];
        
        // Dirección del pulgar (igual que Python)
        const thumb_direction_x = thumb_tip.x - wrist.x;
        const thumb_direction_y = thumb_tip.y - wrist.y;
        const angle_rad = Math.atan2(thumb_direction_y, thumb_direction_x);
        const angle_deg = angle_rad * (180 / Math.PI);
        
        // DETECTAR GESTOS (EXACTAMENTE igual que Python)
        
        // Todos los 5 dedos extendidos - STOP
        if (fingers_extended.every(f => f)) {
            return "STOP";
        }
        
        // Gesto OK - DESPEGAR
        if (distance(thumb_tip, index_tip) < width * 0.05) {
            if (middle_extended && ring_extended && pinky_extended) {
                return "DESPEGAR";
            }
        }
        
        // Solo pulgar extendido - DIRECCIONES
        if (thumb_extended && !index_extended && !middle_extended && !ring_extended && !pinky_extended) {
            if (angle_deg >= -45 && angle_deg <= 45) {
                return "OESTE";
            } else if (angle_deg > 45 && angle_deg <= 135) {
                return "SUR";
            } else if (angle_deg >= -135 && angle_deg < -45) {
                return "NORTE";
            } else if (Math.abs(angle_deg) > 135) {
                return "ESTE";
            }
        }
        
        // Pulgar e índice extendidos - LAND
        if (thumb_extended && index_extended && !middle_extended && !ring_extended && !pinky_extended) {
            return "LAND";
        }
        
        return null;
    }
    
    /**
     * Envía el comando detectado vía Socket.IO (igual que Python)
     */
    sendCommand(command) {
        switch (command) {
            case "STOP":
                this.socket.emit("go", "Stop");
                break;
            case "DESPEGAR":
                this.socket.emit("arm_takeOff", 5);
                // Actualizar botón Despegar inmediatamente (UI local)
                try {
                    const botonDespegar = document.getElementById('botonDespegar');
                    if (botonDespegar) {
                        botonDespegar.textContent = 'Despegando...';
                        botonDespegar.disabled = true;
                        botonDespegar.classList.remove('boton-verde', 'boton-rojo');
                        botonDespegar.classList.add('boton-amarillo');
                    }
                } catch (_) {}
                // Sincronizar estilo con alumnos
                try {
                    this.socket.emit('button_style_sync', {
                        buttonId: 'botonDespegar',
                        text: 'Despegando...',
                        removeClass: ['boton-verde', 'boton-rojo'],
                        addClass: ['boton-amarillo']
                    });
                } catch (_) {}
                break;
            case "NORTE":
                this.socket.emit("go", "North");
                break;
            case "SUR":
                this.socket.emit("go", "South");
                break;
            case "OESTE":
                this.socket.emit("go", "West");
                break;
            case "ESTE":
                this.socket.emit("go", "East");
                break;
            case "LAND":
                this.socket.emit("Land");
                break;
        }
    }

    /**
     * Lógica de estabilización: requiere mantener el mismo gesto
     * por cierto tiempo y frames consecutivos antes de emitir.
     */
    _maybeEmitCommand(detected) {
        const now = Date.now();

        // Si no hay gesto detectado, resetear candidato
        if (!detected) {
            this.pendingCommand = null;
            this.pendingFrames = 0;
            this.pendingSince = 0;
            return;
        }

        // Actualizar candidato y contadores
        if (detected === this.pendingCommand) {
            this.pendingFrames += 1;
        } else {
            this.pendingCommand = detected;
            this.pendingFrames = 1;
            this.pendingSince = now;
        }

        // Calcular requisitos para el comando actual
        const holdMs = this.holdTimesMs[this.pendingCommand] || 300;
        const cooldownMs = this.cooldownsMs[this.pendingCommand] || 300;

        const heldLongEnough = (now - this.pendingSince) >= holdMs;
        const framesEnough = this.pendingFrames >= this.minFrames;
        const cooldownPassed = (now - this.lastEmittedAt) >= cooldownMs;

        // Emitir solo si cumple todos los criterios y evita duplicados consecutivos
        if (heldLongEnough && framesEnough && cooldownPassed) {
            if (this.pendingCommand !== this.lastCommand) {
                console.log(`✅ Comando estabilizado: ${this.pendingCommand} (frames=${this.pendingFrames}, holdMs=${now - this.pendingSince})`);
                this.sendCommand(this.pendingCommand);
                this.lastCommand = this.pendingCommand;
                this.lastEmittedAt = now;
            }
        }
    }
    
    /**
     * Dibuja el comando actual en el canvas
     * Replica: cv2.putText(frame, f"Orden: {command}", (10, 30), ...)
     */
    drawCommand(command) {
        this.ctx.font = 'bold 30px Arial';
        this.ctx.fillStyle = 'rgb(0, 255, 0)';  // Verde (igual que Python)
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 2;
        
        const text = `Orden: ${command}`;
        
        // Borde negro (para mejor visibilidad)
        this.ctx.strokeText(text, 10, 40);
        // Texto verde
        this.ctx.fillText(text, 10, 40);
    }
    
    /**
     * Dibuja la chuleta de gestos
     * Replica EXACTAMENTE draw_gesture_cheat_sheet de Python
     */
    drawGestureCheatSheet() {
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        const startX = 10;
        const startY = height - 420;
        const imgSize = 50;
        const textOffsetX = 55;
        const rowSpacing = 55;
        
        // Fondo semitransparente (igual que Python: cv2.addWeighted)
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        this.ctx.fillRect(
            startX - 5, 
            startY - 10,
            165,
            this.gesturesInfo.length * rowSpacing + 5
        );
        
        // Dibujar cada gesto
        this.gesturesInfo.forEach((gesture, i) => {
            const yPos = startY + i * rowSpacing;
            
            // Verificar que está dentro del canvas
            if (yPos + imgSize <= height && startX + imgSize <= width) {
                // Dibujar imagen si está disponible
                if (this.gestureImages[gesture.key]) {
                    try {
                        this.ctx.drawImage(
                            this.gestureImages[gesture.key],
                            startX, yPos,
                            imgSize, imgSize
                        );
                    } catch (e) {
                        // Si falla, dibujar placeholder
                        this.drawGesturePlaceholder(startX, yPos, imgSize);
                    }
                } else {
                    // Placeholder si no hay imagen (igual que Python)
                    this.drawGesturePlaceholder(startX, yPos, imgSize);
                }
            }
            
            // Texto del gesto (igual que Python)
            this.ctx.fillStyle = gesture.color;
            this.ctx.font = 'bold 16px Arial';
            this.ctx.fillText(gesture.name, startX + textOffsetX, yPos + 30);
        });
    }
    
    /**
     * Dibuja un placeholder cuando no hay imagen
     */
    drawGesturePlaceholder(x, y, size) {
        this.ctx.strokeStyle = '#808080';
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(x, y, size, size);
        
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.font = 'bold 20px Arial';
        this.ctx.fillText('?', x + 18, y + 35);
    }
    
    /**
     * Obtiene el stream del canvas para transmisión WebRTC
     * @param {number} frameRate - FPS del stream (default: 30)
     * @returns {MediaStream} Stream del canvas procesado
     */
    getCanvasStream(frameRate = 30) {
        if (!this.canvas) {
            console.error('❌ [MediaPipe] Canvas no disponible');
            return null;
        }
        
        const stream = this.canvas.captureStream(frameRate);
        console.log('🎥 [MediaPipe] Canvas stream capturado:', frameRate, 'fps');
        return stream;
    }
}

// Exportar para uso global
window.MediaPipeHandsProcessor = MediaPipeHandsProcessor;

