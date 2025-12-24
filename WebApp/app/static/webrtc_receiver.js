/**
 * webrtc_receiver.js
 * Receptor WebRTC genérico para streams de video
 * 
 * Puede recibir:
 * - Cámara del dron (streamId: 'dron_camera')
 * - Gestos del profesor (streamId: 'gestos_profesor')
 * - Cualquier otro stream WebRTC
 */

class WebRTCDroneReceiver {
    constructor(videoElement, socket, streamId = 'dron_camera') {
        this.videoElement = videoElement;
        this.socket = socket;
        this.peerConnection = null;
        this.connectionId = null;
        this.streamId = streamId; // Configurable, default: dron_camera
        this.streamRequested = false; // Evitar solicitudes duplicadas
        this.offerReceived = false; // Para reintentar tras emitter_ready
        // Referencias a handlers para poder desregistrar correctamente
        this._onEmitterReady = null;
        this._onOffer = null;
        this._onIce = null;
        
        // Configuración de ICE servers (STUN para NAT traversal)
        this.iceServers = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'turn:dronseetac.upc.edu:3478',
                   username: "dronseetac",
                   credential: "Mimara00."
                }
            ]
        };
        
        this._registerSocketHandlers();
        console.log('📺 [WebRTC] Receptor inicializado para:', this.streamId);
    }
    
    /**
     * Solicita el stream de video al servidor.
     * Equivalente a enviar {"type": "peticion"} en el ejemplo.
     */
    requestStream() {
        if (this.streamRequested) {
            console.warn('⚠️  [WebRTC] Stream ya solicitado, ignorando duplicado');
            return;
        }
        // Asegurar que los handlers estén registrados (por si reset() los desregistró)
        if (!this._onOffer || !this._onIce || !this._onEmitterReady) {
            this._registerSocketHandlers();
        }
        
        this.streamRequested = true;
        console.log('📡 [WebRTC] Solicitando stream:', this.streamId);
        // Solicitud al servidor de señalización
        // El servidor generará un connection_id y pedirá al emisor preparar oferta
        this.socket.emit('webrtc_request_stream', {
            stream_id: this.streamId
        });
    }
    
    /**
     * Registra los handlers de Socket.IO para señalización WebRTC
     */
    _registerSocketHandlers() {
        // El emisor está disponible y listo
        this._onEmitterReady = (data) => {
            if (data.stream_id === this.streamId) {
                console.log('✅ [WebRTC] Emisor disponible:', data.stream_id);
                // El servidor prepara oferta proactivamente; no re-solicitamos aquí
            }
        };
        this.socket.on('webrtc_emitter_ready', this._onEmitterReady);

        // Recibir oferta SDP del emisor
        // Equivalente a recibir {"type": "sdp"} del proxy
        this._onOffer = async (data) => {
            if (data.stream_id && data.stream_id !== this.streamId) {
                return; // Ignorar ofertas de otros streams
            }
            console.log('📥 [WebRTC] Oferta recibida');
            this.connectionId = data.connection_id;
            this.offerReceived = true;
            await this._handleOffer(data.sdp, data.sdp_type);
        };
        this.socket.on('webrtc_offer', this._onOffer);

        // Recibir ICE candidate del emisor
        this._onIce = async (data) => {
            if (data.connection_id === this.connectionId) {
                // Filtrar por stream si está presente
                if (!data.stream_id || data.stream_id === this.streamId) {
                    await this._handleIceCandidate(data);
                }
            }
        };
        this.socket.on('webrtc_ice_candidate', this._onIce);
    }

    /**
     * Desregistra los handlers del socket para evitar duplicados
     */
    _unregisterSocketHandlers() {
        try {
            if (this._onEmitterReady) this.socket.off('webrtc_emitter_ready', this._onEmitterReady);
            if (this._onOffer) this.socket.off('webrtc_offer', this._onOffer);
            if (this._onIce) this.socket.off('webrtc_ice_candidate', this._onIce);
        } catch (_) {}
        this._onEmitterReady = null;
        this._onOffer = null;
        this._onIce = null;
    }
    
    /**
     * Procesa la oferta SDP recibida del emisor
     */
    async _handleOffer(sdp, sdp_type) {
        try {
            // Siempre cerrar conexión anterior si existe (para reconexión limpia)
            if (this.peerConnection) {
                console.log('   └─> Cerrando conexión anterior antes de crear nueva');
                this.peerConnection.close();
                this.peerConnection = null;
            }
            
            // Crear nueva conexión peer
            this._createPeerConnection();
            
            // Configurar remote description con la oferta
            console.log('   └─> Configurando remote description...');
            const offer = new RTCSessionDescription({
                type: sdp_type,
                sdp: sdp
            });
            await this.peerConnection.setRemoteDescription(offer);
            
            // Crear respuesta (answer)
            console.log('   └─> Creando respuesta...');
            const answer = await this.peerConnection.createAnswer();
            await this.peerConnection.setLocalDescription(answer);
            
            // Enviar respuesta al emisor vía Socket.IO
            // Equivalente a enviar {"type": "sdp", "role": "receiver"}
            this.socket.emit('webrtc_answer', {
                connection_id: this.connectionId,
                sdp: this.peerConnection.localDescription.sdp,
                sdp_type: this.peerConnection.localDescription.type
            });
            console.log('   └─> ✅ Respuesta enviada');
            
        } catch (error) {
            console.error('❌ [WebRTC] Error procesando oferta:', error);
        }
    }
    
    /**
     * Crea la conexión RTCPeerConnection
     */
    _createPeerConnection() {
        console.log('🔗 [WebRTC] Creando RTCPeerConnection');
        this.peerConnection = new RTCPeerConnection(this.iceServers);
        
        // Handler para ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                const obj = event.candidate.toJSON();
                // Enviar en formato compatible con ambos emisores:
                // - Python (dron): espera string en 'candidate' + sdpMid + sdpMLineIndex
                // - Browser (gestos): usa objeto; proveemos 'candidateObj'
                this.socket.emit('webrtc_ice_candidate', {
                    connection_id: this.connectionId,
                    candidate: obj.candidate,
                    sdpMid: obj.sdpMid,
                    sdpMLineIndex: obj.sdpMLineIndex,
                    candidateObj: obj
                });
            }
        };
        
        // Handler para recibir el track de video
        // Equivalente a @pc.on("track") del ejemplo
        this.peerConnection.ontrack = (event) => {
            console.log('🎥 [WebRTC] Stream recibido:', event.streams[0]);
            console.log('   └─> Video element:', this.videoElement);
            console.log('   └─> Stream activo:', event.streams[0].active);
            console.log('   └─> Tracks:', event.streams[0].getTracks());
            
            if (this.videoElement && event.streams && event.streams[0]) {
                // Asignar stream
                this.videoElement.srcObject = event.streams[0];
                console.log('   └─> srcObject asignado');
                
                // Forzar políticas de autoplay móviles: muted + playsinline
                try {
                    this.videoElement.muted = true;
                    this.videoElement.setAttribute('muted', '');
                    this.videoElement.playsInline = true;
                    this.videoElement.setAttribute('playsinline', '');
                } catch (_) {}

                // Forzar carga del video (importante para reconexiones)
                this.videoElement.load();
                console.log('   └─> load() llamado para forzar carga');
                
                // Forzar display block
                this.videoElement.style.display = 'block';
                console.log('   └─> display = block');
                
                // Ocultar placeholder si existe
                const placeholder = document.getElementById('camera-placeholder');
                if (placeholder) {
                    placeholder.style.display = 'none';
                    console.log('   └─> Placeholder ocultado');
                }
                
                // Función para intentar reproducir
                const tryPlay = () => {
                    console.log('   └─> Intentando reproducir video...');
                    console.log('   └─> readyState:', this.videoElement.readyState);
                    
                    this.videoElement.play()
                        .then(() => {
                            console.log('   └─> ✅ Video reproduciéndose');
                        })
                        .catch(err => {
                            console.error('   └─> ❌ Error en play():', err);
                        });
                };
                
                // Si ya tiene metadatos, reproducir inmediatamente
                if (this.videoElement.readyState >= 1) {
                    console.log('   └─> Video ya tiene metadatos (readyState:', this.videoElement.readyState, ')');
                    tryPlay();
                } else {
                    // Esperar a que se carguen los metadatos
                    console.log('   └─> Esperando metadatos del video...');
                    this.videoElement.addEventListener('loadedmetadata', () => {
                        console.log('   └─> Metadatos cargados');
                        tryPlay();
                    }, { once: true }); // once: true para que solo se ejecute una vez
                    
                    // Fallback: intentar reproducir después de un pequeño delay
                    setTimeout(() => {
                        if (this.videoElement.paused) {
                            console.log('   └─> Fallback: intentando reproducir después de delay...');
                            tryPlay();
                        }
                    }, 500);

                    // Fallback adicional: reproducir al primer click/tap del usuario
                    const clickToPlay = () => {
                        if (this.videoElement && this.videoElement.paused) {
                            console.log('   └─> Click/Tap recibido: intentando reproducir...');
                            tryPlay();
                        }
                        this.videoElement.removeEventListener('click', clickToPlay);
                    };
                    this.videoElement.addEventListener('click', clickToPlay);
                }
            } else {
                console.error('   └─> ❌ No se pudo asignar stream - videoElement o stream no disponible');
            }
        };
        
        // Handler para cambios de estado de conexión
        this.peerConnection.onconnectionstatechange = () => {
            console.log('🔌 [WebRTC] Estado:', this.peerConnection.connectionState);
            
            switch (this.peerConnection.connectionState) {
                case 'connected':
                    console.log('✅ [WebRTC] Conexión establecida');
                    break;
                case 'disconnected':
                    console.warn('⚠️  [WebRTC] Desconectado');
                    break;
                case 'failed':
                    console.error('❌ [WebRTC] Conexión falló');
                    break;
            }
        };
    }
    
    /**
     * Procesa ICE candidate recibido
     */
    async _handleIceCandidate(data) {
        try {
            if (this.peerConnection && this.peerConnection.remoteDescription) {
                // Tolerar ambas formas: string en top-level o objeto en data.candidate
                let candidateInit = null;
                if (data && typeof data.candidate === 'object' && data.candidate !== null) {
                    // Formato de sender: candidate.toJSON() -> { candidate, sdpMid, sdpMLineIndex, ... }
                    candidateInit = {
                        candidate: data.candidate.candidate,
                        sdpMid: data.candidate.sdpMid,
                        sdpMLineIndex: data.candidate.sdpMLineIndex
                    };
                } else {
                    // Formato top-level: { candidate: string, sdpMid, sdpMLineIndex }
                    candidateInit = {
                        candidate: data.candidate,
                        sdpMid: data.sdpMid,
                        sdpMLineIndex: data.sdpMLineIndex
                    };
                }

                if (candidateInit && candidateInit.candidate) {
                    await this.peerConnection.addIceCandidate(new RTCIceCandidate(candidateInit));
                    console.log('🧊 [WebRTC] ICE candidate agregado');
                } else {
                    console.warn('⚠️  [WebRTC] ICE candidate inválido recibido:', data);
                }
            }
        } catch (error) {
            console.error('❌ [WebRTC] Error agregando ICE candidate:', error);
        }
    }
    
    /**
     * Detiene la conexión WebRTC
     */
    stop() {
        console.log('🛑 [WebRTC] Deteniendo receptor');
        
        // Desregistrar handlers para evitar duplicados en próximas aperturas
        this._unregisterSocketHandlers();

        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
        
        this.connectionId = null;
        this.offerReceived = false;
        // NO resetear streamRequested aquí - usar reset() para eso
    }
    
    /**
     * Resetea el receptor para permitir nueva solicitud de stream
     * Usar cuando se cierra la cámara intencionalmente
     */
    reset() {
        console.log('🔄 [WebRTC] Reseteando receptor para nueva solicitud');
        
        // Notificar al servidor que cierre esta conexión
        if (this.connectionId) {
            this.socket.emit('webrtc_close_connection', {
                connection_id: this.connectionId
            });
            this.connectionId = null; // Limpiar connectionId
        }
        
        // Cerrar y limpiar completamente la conexión anterior
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        // Desregistrar handlers para evitar duplicados
        this._unregisterSocketHandlers();
        
        // Limpiar el video element y mostrar placeholder
        if (this.videoElement) {
            this.videoElement.srcObject = null;
            this.videoElement.style.display = 'none';
            
            // Mostrar placeholder si existe
            const placeholder = document.getElementById('camera-placeholder');
            if (placeholder) {
                placeholder.style.display = 'block';
            }
        }
        
        // Permitir nueva solicitud
        this.streamRequested = false;
        this.offerReceived = false;
        
        // Volver a registrar handlers para estar listo en la próxima apertura
        this._registerSocketHandlers();
        
        console.log('✅ [WebRTC] Receptor reseteado completamente');
    }
    
    /**
     * Obtiene estadísticas de la conexión (útil para debugging)
     */
    async getStats() {
        if (!this.peerConnection) {
            return null;
        }
        
        try {
            const stats = await this.peerConnection.getStats();
            const report = {
                bytesReceived: 0,
                framesDecoded: 0,
                framesDropped: 0,
                jitter: 0,
                packetsLost: 0
            };
            
            stats.forEach((stat) => {
                if (stat.type === 'inbound-rtp' && !stat.isRemote) {
                    report.bytesReceived += stat.bytesReceived || 0;
                    report.framesDecoded += stat.framesDecoded || 0;
                    report.framesDropped += stat.framesDropped || 0;
                    report.jitter = Math.max(report.jitter, stat.jitter || 0);
                    report.packetsLost += stat.packetsLost || 0;
                }
            });
            
            return report;
        } catch (e) {
            console.warn('⚠️ [WebRTC] Error obteniendo estadísticas:', e);
            return null;
        }
    }
}

// Exportar clase para uso en otras partes del código si se usa módulos
// (No es necesario en entorno clásico con script tag)
// export default WebRTCDroneReceiver;
