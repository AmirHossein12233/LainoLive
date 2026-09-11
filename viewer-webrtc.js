```javascript
"use strict";

const LainoViewerRTC = {

    peer: null,
    socket: null,

    streamId: null,
    videoElement: null,

    clientId: null,
    broadcasterId: null,

    started: false,
    remoteDescriptionSet: false,

    pendingIceCandidates: [],


    // =====================================================
    // CONNECT
    // =====================================================

    connect(streamId, videoElement) {

        this.close();

        this.streamId = String(streamId || "");
        this.videoElement = videoElement;

        if (!this.streamId) {
            console.error(
                "LainoViewerRTC: streamId is missing"
            );
            return;
        }

        if (!this.videoElement) {
            console.error(
                "LainoViewerRTC: video element is missing"
            );
            return;
        }

        const protocol =
            location.protocol === "https:"
                ? "wss"
                : "ws";

        const socketUrl =
            protocol +
            "://" +
            location.host +
            "/ws/viewer/" +
            encodeURIComponent(this.streamId);

        console.log(
            "LainoLive viewer signaling:",
            socketUrl
        );

        try {

            this.socket =
                new WebSocket(socketUrl);

        } catch (error) {

            console.error(
                "WebSocket creation failed:",
                error
            );

            return;
        }


        // =================================================
        // SOCKET OPEN
        // =================================================

        this.socket.onopen = () => {

            console.log(
                "LainoLive viewer WebRTC signaling connected"
            );

            this.started = true;

            /*
             * به سرور اعلام می‌کنیم که viewer آماده است.
             */
            this.send({
                type: "viewer-ready"
            });

        };


        // =================================================
        // SOCKET MESSAGE
        // =================================================

        this.socket.onmessage =
            async (event) => {

                try {

                    const data =
                        JSON.parse(event.data);

                    console.log(
                        "Viewer signaling:",
                        data
                    );


                    // -------------------------------------
                    // CONNECTED
                    // -------------------------------------

                    if (
                        data.type === "connected"
                    ) {

                        this.clientId =
                            data.client_id || null;

                        console.log(
                            "Viewer client id:",
                            this.clientId
                        );

                        /*
                         * بعضی سرورها بعد از connected
                         * viewer-ready را لازم دارند.
                         */

                        this.send({
                            type: "viewer-ready"
                        });

                        return;
                    }


                    // -------------------------------------
                    // BROADCASTER READY
                    // -------------------------------------

                    if (
                        data.type ===
                        "broadcaster-ready"
                    ) {

                        console.log(
                            "Broadcaster is ready"
                        );

                        this.send({
                            type: "viewer-ready"
                        });

                        return;
                    }


                    // -------------------------------------
                    // OFFER
                    // -------------------------------------

                    if (
                        data.type === "offer" &&
                        data.offer
                    ) {

                        this.broadcasterId =
                            data.sender ||
                            data.broadcaster_id ||
                            null;

                        await this.handleOffer(
                            data.offer
                        );

                        return;
                    }


                    /*
                     * سازگاری با نسخه‌هایی که offer
                     * را بدون type ارسال می‌کنند.
                     */

                    if (
                        data.offer &&
                        typeof data.offer === "object"
                    ) {

                        this.broadcasterId =
                            data.sender ||
                            data.broadcaster_id ||
                            null;

                        await this.handleOffer(
                            data.offer
                        );

                        return;
                    }


                    // -------------------------------------
                    // ICE CANDIDATE
                    // -------------------------------------

                    if (
                        data.type === "ice-candidate" &&
                        data.candidate
                    ) {

                        await this.handleIce(
                            data.candidate
                        );

                        return;
                    }


                    /*
                     * سازگاری با candidate
                     */

                    if (
                        data.type === "candidate" &&
                        data.candidate
                    ) {

                        await this.handleIce(
                            data.candidate
                        );

                        return;
                    }


                    /*
                     * سازگاری با ساختار قدیمی:
                     * { ice: ... }
                     */

                    if (data.ice) {

                        await this.handleIce(
                            data.ice
                        );

                        return;
                    }


                    // -------------------------------------
                    // BROADCASTER LEFT
                    // -------------------------------------

                    if (
                        data.type ===
                        "broadcaster-left"
                    ) {

                        console.warn(
                            "Broadcaster disconnected"
                        );

                        this.stopPlayback();

                        return;
                    }


                    // -------------------------------------
                    // STREAM ENDED
                    // -------------------------------------

                    if (
                        data.type ===
                        "stream-ended"
                    ) {

                        console.log(
                            "Stream ended"
                        );

                        this.stopPlayback();

                        return;
                    }


                } catch (error) {

                    console.error(
                        "Viewer signaling message error:",
                        error
                    );

                }

            };


        // =================================================
        // SOCKET ERROR
        // =================================================

        this.socket.onerror =
            (error) => {

                console.error(
                    "Viewer WebRTC signaling error:",
                    error
                );

            };


        // =================================================
        // SOCKET CLOSE
        // =================================================

        this.socket.onclose =
            () => {

                console.log(
                    "Viewer WebRTC signaling closed"
                );

                this.started = false;

            };

    },


    // =====================================================
    // CREATE PEER
    // =====================================================

    async createPeer() {

        if (this.peer) {

            try {
                this.peer.close();
            } catch {}

            this.peer = null;
        }


        this.remoteDescriptionSet = false;

        this.pendingIceCandidates = [];


        this.peer =
            new RTCPeerConnection({

                iceServers: [

                    {
                        urls:
                            "stun:stun.l.google.com:19302"
                    },

                    {
                        urls:
                            "stun:stun1.l.google.com:19302"
                    }

                ]

            });


        // =================================================
        // TRACK
        // =================================================

        this.peer.ontrack =
            (event) => {

                console.log(
                    "Viewer received remote track"
                );

                if (!this.videoElement) {
                    return;
                }


                let remoteStream = null;


                if (
                    event.streams &&
                    event.streams.length > 0
                ) {

                    remoteStream =
                        event.streams[0];

                }


                /*
                 * بعضی مرورگرها ممکن است stream را
                 * مستقیم در event.streams ندهند.
                 */

                if (!remoteStream) {

                    if (
                        !this.videoElement.srcObject
                    ) {

                        remoteStream =
                            new MediaStream();

                        this.videoElement.srcObject =
                            remoteStream;

                    } else {

                        remoteStream =
                            this.videoElement.srcObject;

                    }

                    remoteStream.addTrack(
                        event.track
                    );

                } else {

                    this.videoElement.srcObject =
                        remoteStream;

                }


                this.videoElement.autoplay = true;
                this.videoElement.playsInline = true;

                /*
                 * mute=false تا صدای لایو پخش شود.
                 * ممکن است مرورگر به دلیل autoplay آن را
                 * مسدود کند؛ در این صورت کاربر باید روی صفحه
                 * کلیک کند.
                 */

                this.videoElement.muted = false;


                const playPromise =
                    this.videoElement.play();


                if (
                    playPromise &&
                    typeof playPromise.catch ===
                        "function"
                ) {

                    playPromise.catch(
                        (error) => {

                            console.warn(
                                "Video autoplay was blocked:",
                                error
                            );

                        }
                    );

                }

            };


        // =================================================
        // ICE
        // =================================================

        this.peer.onicecandidate =
            (event) => {

                if (!event.candidate) {
                    return;
                }


                const message = {

                    type:
                        "ice-candidate",

                    candidate:
                        event.candidate

                };


                /*
                 * اگر broadcasterId را داریم،
                 * candidate مستقیماً برای broadcaster
                 * ارسال می‌شود.
                 */

                if (this.broadcasterId) {

                    message.target =
                        this.broadcasterId;

                }


                this.send(message);

            };


        // =================================================
        // CONNECTION STATE
        // =================================================

        this.peer.onconnectionstatechange =
            () => {

                if (!this.peer) {
                    return;
                }


                console.log(
                    "Viewer WebRTC connection:",
                    this.peer.connectionState
                );


                switch (
                    this.peer.connectionState
                ) {

                    case "connected":

                        console.log(
                            "LainoLive viewer connected to stream"
                        );

                        break;


                    case "disconnected":

                        console.warn(
                            "Viewer WebRTC disconnected"
                        );

                        break;


                    case "failed":

                        console.error(
                            "Viewer WebRTC connection failed"
                        );

                        break;


                    case "closed":

                        console.log(
                            "Viewer WebRTC connection closed"
                        );

                        break;

                }

            };


        // =================================================
        // ICE CONNECTION STATE
        // =================================================

        this.peer.oniceconnectionstatechange =
            () => {

                if (!this.peer) {
                    return;
                }

                console.log(
                    "Viewer ICE state:",
                    this.peer.iceConnectionState
                );

            };

    },


    // =====================================================
    // HANDLE OFFER
    // =====================================================

    async handleOffer(offer) {

        try {

            if (!offer) {
                return;
            }


            if (!this.peer) {

                await this.createPeer();

            }


            console.log(
                "Setting remote offer..."
            );


            await this.peer.setRemoteDescription(
                new RTCSessionDescription(
                    offer
                )
            );


            this.remoteDescriptionSet =
                true;


            /*
             * ICEهایی که زودتر از offer رسیده‌اند
             * حالا اضافه می‌شوند.
             */

            await this.flushPendingIce();


            const answer =
                await this.peer.createAnswer();


            await this.peer.setLocalDescription(
                answer
            );


            const message = {

                type:
                    "answer",

                answer:
                    this.peer.localDescription

            };


            if (this.broadcasterId) {

                message.target =
                    this.broadcasterId;

            }


            this.send(message);


            console.log(
                "Viewer answer sent"
            );


        } catch (error) {

            console.error(
                "Handle offer error:",
                error
            );

        }

    },


    // =====================================================
    // HANDLE ICE
    // =====================================================

    async handleIce(candidate) {

        try {

            if (!candidate) {
                return;
            }


            /*
             * ممکن است ICE قبل از offer برسد.
             * در آن صورت نگهش می‌داریم.
             */

            if (
                !this.peer ||
                !this.remoteDescriptionSet
            ) {

                this.pendingIceCandidates.push(
                    candidate
                );

                return;

            }


            await this.peer.addIceCandidate(
                new RTCIceCandidate(
                    candidate
                )
            );


        } catch (error) {

            console.warn(
                "Add ICE candidate failed:",
                error
            );

        }

    },


    // =====================================================
    // FLUSH PENDING ICE
    // =====================================================

    async flushPendingIce() {

        if (!this.peer) {
            return;
        }


        if (
            !this.remoteDescriptionSet
        ) {
            return;
        }


        if (
            this.pendingIceCandidates.length === 0
        ) {
            return;
        }


        const candidates =
            this.pendingIceCandidates;


        this.pendingIceCandidates = [];


        for (
            const candidate of candidates
        ) {

            try {

                await this.peer.addIceCandidate(
                    new RTCIceCandidate(
                        candidate
                    )
                );

            } catch (error) {

                console.warn(
                    "Pending ICE candidate failed:",
                    error
                );

            }

        }

    },


    // =====================================================
    // SEND
    // =====================================================

    send(data) {

        if (
            !this.socket ||
            this.socket.readyState !==
                WebSocket.OPEN
        ) {

            console.warn(
                "Viewer signaling socket is not open"
            );

            return false;

        }


        try {

            this.socket.send(
                JSON.stringify(data)
            );

            return true;

        } catch (error) {

            console.error(
                "Viewer signaling send error:",
                error
            );

            return false;

        }

    },


    // =====================================================
    // STOP PLAYBACK
    // =====================================================

    stopPlayback() {

        if (this.videoElement) {

            try {

                this.videoElement.pause();

            } catch {}


            try {

                this.videoElement.srcObject =
                    null;

            } catch {}

        }


        if (this.peer) {

            try {
                this.peer.close();
            } catch {}

            this.peer = null;

        }

        this.remoteDescriptionSet = false;

        this.pendingIceCandidates = [];

    },


    // =====================================================
    // CLOSE
    // =====================================================

    close() {

        this.stopPlayback();


        if (this.socket) {

            try {
                this.socket.close();
            } catch {}

            this.socket = null;

        }


        this.streamId = null;
        this.videoElement = null;

        this.clientId = null;
        this.broadcasterId = null;

        this.started = false;

    }

};


window.LainoViewerRTC =
    LainoViewerRTC;
```
