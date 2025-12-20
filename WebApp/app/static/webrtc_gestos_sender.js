/**
 * webrtc_gestos_sender.js
 * Emisor WebRTC para transmitir el canvas de gestos MediaPipe a los alumnos
 * 
 * El profesor captura el canvas procesado (con landmarks, gestos, chuleta)
 * y lo transmite vía WebRTC a todos los alumnos conectados.
 */

class WebRTCGestosSender {
    constructor(socket, streamId = 'gestos_profesor') {
        this.socket = socket;
        this.streamId = streamId;
        this.stream = null;
        this.peerConnections = new Map(); // connection_id -> RTCPeerConnection
        this.isStreaming = false;
        this._handlersRegistered = false;
        this._onPrepareOffer = null;
        this._onAnswer = null;
        this._onIceCandidate = null;
        
        // Configuración ICE servers
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
        console.log('📡 [WebRTC Sender] Emisor de gestos inicializado');
    }
    
    /**
     * Inicia la transmisión del stream del canvas
     * @param {MediaStream} canvasStream - Stream del canvas de MediaPipe
     */
    async startStreaming(canvasStream) {
        if (!canvasStream) {
            console.error('❌ [WebRTC Sender] No hay stream para transmitir');
            return;
        }
        
        this.stream = canvasStream;
        this.isStreaming = true;
        
        // Registrar emisor en el servidor de señalización
        this.socket.emit('webrtc_register_emitter', {
            stream_id: this.streamId
        });
        
        console.log('✅ [WebRTC Sender] Transmisión iniciada:', this.streamId);
    }
    
    /**
     * Detiene la transmisión y cierra todas las conexiones
     */
    stopStreaming() {
        console.log('🛑 [WebRTC Sender] Deteniendo transmisión');
        this.isStreaming = false;
        
        // Cerrar todas las peer connections
        this.peerConnections.forEach((pc, connectionId) => {
            pc.close();
            console.log('🔌 [WebRTC Sender] Conexión cerrada:', connectionId);
        });
        this.peerConnections.clear();
        
        // Detener tracks del stream del canvas si existen
        if (this.stream) {
            try {
                this.stream.getTracks().forEach(t => t.stop());
            } catch (_) {}
            this.stream = null;
        }

        // Notificar al servidor
        this.socket.emit('webrtc_stop_streaming', {
            stream_id: this.streamId
        });

        // Desregistrar handlers para evitar duplicados al reabrir
        this._unregisterSocketHandlers();
    }
    
    /**
     * Registra los handlers de Socket.IO para señalización
     */
    _registerSocketHandlers() {
        if (this._handlersRegistered) return;

        // El servidor nos pide preparar una oferta para un receptor concreto
        this._onPrepareOffer = async (data) => {
            if (!this.isStreaming) return;
            const connectionId = data && data.connection_id;
            if (connectionId) {
                console.log('📨 [WebRTC Sender] Preparar oferta para conexión:', connectionId);
                await this._createOffer(connectionId);
            }
        };

        this._onAnswer = async (data) => {
            const pc = this.peerConnections.get(data.connection_id);
            if (pc) {
                console.log('📥 [WebRTC Sender] Respuesta recibida de:', data.connection_id);
                await pc.setRemoteDescription(new RTCSessionDescription({
                    type: data.sdp_type,
                    sdp: data.sdp
                }));
            }
        };

        this._onIceCandidate = async (data) => {
            const pc = this.peerConnections.get(data.connection_id);
            if (!pc) return;
            try {
                let candidateInit = null;
                if (data && typeof data.candidate === 'object' && data.candidate !== null) {
                    // Receiver envió objeto directamente
                    candidateInit = data.candidate;
                } else if (data && data.candidateObj) {
                    // Receiver envió ambos formatos
                    candidateInit = data.candidateObj;
                } else if (typeof data.candidate === 'string') {
                    // Receiver envió string + índices
                    candidateInit = {
                        candidate: data.candidate,
                        sdpMid: data.sdpMid,
                        sdpMLineIndex: data.sdpMLineIndex
                    };
                }
                if (candidateInit && candidateInit.candidate) {
                    await pc.addIceCandidate(new RTCIceCandidate(candidateInit));
                }
            } catch (e) {
                console.warn('[WebRTC Sender] Error agregando ICE candidate:', e);
            }
        };

        // Orquestado por el servidor: escuchar 'webrtc_prepare_offer'
        this.socket.on('webrtc_prepare_offer', this._onPrepareOffer);
        this.socket.on('webrtc_answer', this._onAnswer);
        this.socket.on('webrtc_ice_candidate', this._onIceCandidate);
        this._handlersRegistered = true;
    }

    _unregisterSocketHandlers() {
        if (!this._handlersRegistered) return;
        try {
            if (this._onPrepareOffer) this.socket.off('webrtc_prepare_offer', this._onPrepareOffer);
            if (this._onAnswer) this.socket.off('webrtc_answer', this._onAnswer);
            if (this._onIceCandidate) this.socket.off('webrtc_ice_candidate', this._onIceCandidate);
        } catch (_) {}
        this._handlersRegistered = false;
        this._onPrepareOffer = null;
        this._onAnswer = null;
        this._onIceCandidate = null;
    }
    
    /**
     * Crea una oferta SDP para un alumno
     */
    async _createOffer(connectionId) {
        try {
            // Crear nueva peer connection
            const pc = new RTCPeerConnection(this.iceServers);
            this.peerConnections.set(connectionId, pc);
            
            // Agregar tracks del stream al peer connection
            this.stream.getTracks().forEach(track => {
                pc.addTrack(track, this.stream);
                console.log('🎬 [WebRTC Sender] Track agregado:', track.kind);
            });
            
            // Manejar ICE candidates
            pc.onicecandidate = (event) => {
                if (event.candidate) {
                    this.socket.emit('webrtc_ice_candidate', {
                        stream_id: this.streamId,
                        connection_id: connectionId,
                        candidate: event.candidate.toJSON()
                    });
                }
            };
            
            // Monitorear estado de conexión
            pc.onconnectionstatechange = () => {
                console.log(`🔗 [WebRTC Sender] Estado ${connectionId}:`, pc.connectionState);
                if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
                    this.peerConnections.delete(connectionId);
                }
            };
            
            // Crear oferta
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            
            // Enviar oferta al alumno
            this.socket.emit('webrtc_offer', {
                stream_id: this.streamId,
                connection_id: connectionId,
                sdp: offer.sdp,
                sdp_type: offer.type
            });
            
            console.log('📤 [WebRTC Sender] Oferta enviada a:', connectionId);
            
        } catch (error) {
            console.error('❌ [WebRTC Sender] Error creando oferta:', error);
        }
    }
}
