/**
 * webrtc_drone_receiver.js
 * Receptor WebRTC para la cámara del dron
 * 
 * Equivalente a receiverGlobalWebRTC.py pero para navegador.
 * Solicita stream, recibe oferta, envía respuesta y muestra video.
 */

class WebRTCDroneReceiver {
    constructor(videoElement, socket) {
        this.videoElement = videoElement;
        this.socket = socket;
        this.peerConnection = null;
        this.connectionId = null;
        this.streamId = 'dron_camera';
        this.streamRequested = false; // Evitar solicitudes duplicadas
        
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
        
        this.streamRequested = true;
        console.log('📡 [WebRTC] Solicitando stream:', this.streamId);
        this.socket.emit('webrtc_request_stream', {
            stream_id: this.streamId
        });
    }
    
    /**
     * Registra los handlers de Socket.IO para señalización WebRTC
     */
    _registerSocketHandlers() {
        // El emisor está disponible y listo
        this.socket.on('webrtc_emitter_ready', (data) => {
            if (data.stream_id === this.streamId) {
                console.log('✅ [WebRTC] Emisor disponible:', data.stream_id);
                // No solicitar automáticamente - ya se pidió en requestStream()
            }
        });
        
        // Recibir oferta SDP del emisor
        // Equivalente a recibir {"type": "sdp"} del proxy
        this.socket.on('webrtc_offer', async (data) => {
            console.log('📥 [WebRTC] Oferta recibida');
            this.connectionId = data.connection_id;
            await this._handleOffer(data.sdp, data.sdp_type);
        });
        
        // Recibir ICE candidate del emisor
        this.socket.on('webrtc_ice_candidate', async (data) => {
            if (data.connection_id === this.connectionId) {
                await this._handleIceCandidate(data);
            }
        });
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
                this.socket.emit('webrtc_ice_candidate', {
                    connection_id: this.connectionId,
                    candidate: event.candidate.candidate,
                    sdpMid: event.candidate.sdpMid,
                    sdpMLineIndex: event.candidate.sdpMLineIndex
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
                const candidate = new RTCIceCandidate({
                    candidate: data.candidate,
                    sdpMid: data.sdpMid,
                    sdpMLineIndex: data.sdpMLineIndex
                });
                await this.peerConnection.addIceCandidate(candidate);
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
        
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
        
        this.connectionId = null;
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
                packetsReceived: 0,
                framesReceived: 0
            };
            
            stats.forEach(stat => {
                if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
                    report.bytesReceived = stat.bytesReceived || 0;
                    report.packetsReceived = stat.packetsReceived || 0;
                    report.framesReceived = stat.framesReceived || 0;
                }
            });
            
            return report;
        } catch (error) {
            console.error('Error obteniendo estadísticas:', error);
            return null;
        }
    }
}

// Exportar para uso global
window.WebRTCDroneReceiver = WebRTCDroneReceiver;
