```javascript
"use strict";

const LainoWebRTC = {

    socket: null,
    stream: null,
    streamId: null,

    started: false,
    broadcasterId: null,

    /*
     * برای هر viewer یک PeerConnection جدا
     *
     * viewers = {
     *   viewerId: {
     *      peer: RTCPeerConnection,
     *      pendingIce: [],
     *      remoteDescriptionSet: false
     *   }
     * }
     */
    viewers: {},


    // =====================================================
    // START
    // =====================================================

    start(streamId, mediaStream) {

        this.stop();

        this.streamId =
            String(streamId || "");

        this.stream =
            mediaStream || null;

        if (!this.streamId) {

            console.error(
                "LainoWebRTC: streamId is missing"
            );

            return false;
        }

        if (!this.stream) {

            console.error(
                "LainoWebRTC: media stream is missing"
            );

            return false;
        }


        const protocol =
            location.protocol === "https:"
                ? "wss"
                : "ws";


        const socketUrl =
            protocol +
            "://" +
            location.host +
            "/ws/broadcaster/" +
            encodeURIComponent(
                this.streamId
            );


        console.log(
            "LainoLive broadcaster signaling:",
            socketUrl
        );


        try {

            this.socket =
                new WebSocket(socketUrl);

        } catch (error) {

            console.error(
                "Broadcaster WebSocket creation failed:",
                error
            );

            return false;
        }


        // =================================================
        // SOCKET OPEN
        // =================================================

        this.socket.onopen =
            () => {

                console.log(
                    "LainoLive broadcaster WebRTC connected"
                );

                this.started = true;

            };


        // =================================================
        // SOCKET MESSAGE
        // =================================================

        this.socket.onmessage =
            async (event) => {

                try {

                    const data =
                        JSON.parse(
                            event.data
                        );


                    console.log(
                        "Broadcaster signaling:",
                        data
                    );


                    // -------------------------------------
                    // CONNECTED
                    // -------------------------------------

                    if (
                        data.type ===
                        "connected"
                    ) {

                        this.broadcasterId =
                            data.client_id ||
                            null;

                        console.log(
                            "Broadcaster client id:",
                            this.broadcasterId
                        );

                        return;
                    }


                    // -------------------------------------
                    // VIEWER READY
                    // -------------------------------------

                    if (
                        data.type ===
                        "viewer-ready"
                    ) {

                        const viewerId =
                            data.viewer_id;

                        if (!viewerId) {

                            console.warn(
                                "viewer-ready without viewer_id"
                            );

                            return;
                        }


                        console.log(
                            "New viewer:",
                            viewerId
                        );


                        /*
                         * برای این viewer یک
                         * PeerConnection جدا می‌سازیم.
                         */

                        await this.createViewerPeer(
                            viewerId
                        );

                        return;
                    }


                    // -------------------------------------
                    // VIEWER LEFT
                    // -------------------------------------

                    if (
                        data.type ===
                        "viewer-left"
                    ) {

                        const viewerId =
                            data.viewer_id;

                        if (viewerId) {

                            console.log(
                                "Viewer left:",
                                viewerId
                            );

                            this.removeViewer(
                                viewerId
                            );

                        }

                        return;
                    }


                    // -------------------------------------
                    // ANSWER
                    // -------------------------------------

                    if (
                        data.type ===
                        "answer"
                    ) {

                        const viewerId =
                            data.sender ||
                            data.viewer_id ||
                            null;

                        if (
                            !viewerId ||
                            !data.answer
                        ) {

                            console.warn(
                                "Invalid answer message"
                            );

                            return;
                        }


                        await this.handleAnswer(
                            viewerId,
                            data.answer
                        );

                        return;
                    }


                    // -------------------------------------
                    // ICE CANDIDATE
                    // -------------------------------------

                    if (
                        data.type ===
                            "ice-candidate" &&
                        data.candidate
                    ) {

                        const viewerId =
                            data.sender ||
                            data.viewer_id ||
                            null;

                        if (!viewerId) {

                            console.warn(
                                "ICE candidate without viewer id"
                            );

                            return;
                        }


                        await this.handleIce(
                            viewerId,
                            data.candidate
                        );

                        return;
                    }


                    // -------------------------------------
                    // COMPATIBILITY: candidate
                    // -------------------------------------

                    if (
                        data.type ===
                            "candidate" &&
                        data.candidate
                    ) {

                        const viewerId =
                            data.sender ||
                            data.viewer_id ||
                            null;


                        if (viewerId) {

                            await this.handleIce(
                                viewerId,
                                data.candidate
                            );

                        }

                        return;
                    }


                } catch (error) {

                    console.error(
                        "Broadcaster signaling message error:",
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
                    "Broadcaster WebRTC signaling error:",
                    error
                );

            };


        // =================================================
        // SOCKET CLOSE
        // =================================================

        this.socket.onclose =
            () => {

                console.log(
                    "LainoLive broadcaster signaling closed"
                );

                this.started = false;

            };


        return true;

    },


    // =====================================================
    // CREATE VIEWER PEER
    // =====================================================

    async createViewerPeer(viewerId) {

        if (!viewerId) {
            return;
        }


        if (!this.stream) {

            console.error(
                "Cannot create viewer peer without stream"
            );

            return;
        }


        /*
         * اگر همین viewer قبلاً وجود دارد،
         * اتصال قبلی را می‌بندیم.
         */

        this.removeViewer(
            viewerId
        );


        const peer =
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


        this.viewers[viewerId] = {

            peer:
                peer,

            pendingIce:
                [],

            remoteDescriptionSet:
                false

        };


        // =================================================
        // ADD MEDIA TRACKS
        // =================================================

        this.stream
            .getTracks()
            .forEach(
                (track) => {

                    try {

                        peer.addTrack(
                            track,
                            this.stream
                        );

                    } catch (error) {

                        console.error(
                            "Could not add media track:",
                            error
                        );

                    }

                }
            );


        // =================================================
        // ICE
        // =================================================

        peer.onicecandidate =
            (event) => {

                if (
                    !event.candidate
                ) {
                    return;
                }


                const message = {

                    type:
                        "ice-candidate",

                    target:
                        viewerId,

                    candidate:
                        event.candidate

                };


                this.send(
                    message
                );

            };


        // =================================================
        // CONNECTION STATE
        // =================================================

        peer.onconnectionstatechange =
            () => {

                /*
                 * ممکن است viewer در همین لحظه حذف شده باشد.
                 */

                if (
                    !this.viewers[viewerId]
                ) {
                    return;
                }


                console.log(
                    "Viewer",
                    viewerId,
                    "WebRTC state:",
                    peer.connectionState
                );


                if (
                    peer.connectionState ===
                        "connected"
                ) {

                    console.log(
                        "Viewer connected:",
                        viewerId
                    );

                }


                if (
                    peer.connectionState ===
                        "failed"
                ) {

                    console.warn(
                        "Viewer WebRTC failed:",
                        viewerId
                    );

                }


                if (
                    peer.connectionState ===
                        "closed"
                ) {

                    this.removeViewer(
                        viewerId
                    );

                }

            };


        // =================================================
        // ICE STATE
        // =================================================

        peer.oniceconnectionstatechange =
            () => {

                if (
                    !this.viewers[viewerId]
                ) {
                    return;
                }


                console.log(
                    "Viewer",
                    viewerId,
                    "ICE state:",
                    peer.iceConnectionState
                );

            };


        // =================================================
        // CREATE OFFER
        // =================================================

        try {

            const offer =
                await peer.createOffer({

                    offerToReceiveAudio:
                        false,

                    offerToReceiveVideo:
                        false

                });


            await peer.setLocalDescription(
                offer
            );


            this.send({

                type:
                    "offer",

                target:
                    viewerId,

                offer:
                    peer.localDescription

            });


            console.log(
                "Offer sent to viewer:",
                viewerId
            );


        } catch (error) {

            console.error(
                "Create viewer offer error:",
                error
            );

            this.removeViewer(
                viewerId
            );

        }

    },


    // =====================================================
    // HANDLE ANSWER
    // =====================================================

    async handleAnswer(
        viewerId,
        answer
    ) {

        const entry =
            this.viewers[viewerId];


        if (!entry) {

            console.warn(
                "Answer received for unknown viewer:",
                viewerId
            );

            return;
        }


        if (!answer) {
            return;
        }


        try {

            await entry.peer.setRemoteDescription(
                new RTCSessionDescription(
                    answer
                )
            );


            entry.remoteDescriptionSet =
                true;


            await this.flushPendingIce(
                viewerId
            );


            console.log(
                "Answer applied for viewer:",
                viewerId
            );


        } catch (error) {

            console.error(
                "Handle answer error:",
                viewerId,
                error
            );

        }

    },


    // =====================================================
    // HANDLE ICE
    // =====================================================

    async handleIce(
        viewerId,
        candidate
    ) {

        const entry =
            this.viewers[viewerId];


        if (!entry) {

            console.warn(
                "ICE received for unknown viewer:",
                viewerId
            );

            return;
        }


        if (!candidate) {
            return;
        }


        /*
         * ممکن است ICE قبل از answer برسد.
         */

        if (
            !entry.remoteDescriptionSet
        ) {

            entry.pendingIce.push(
                candidate
            );

            return;

        }


        try {

            await entry.peer.addIceCandidate(
                new RTCIceCandidate(
                    candidate
                )
            );


        } catch (error) {

            console.warn(
                "Add viewer ICE failed:",
                viewerId,
                error
            );

        }

    },


    // =====================================================
    // FLUSH ICE
    // =====================================================

    async flushPendingIce(
        viewerId
    ) {

        const entry =
            this.viewers[viewerId];


        if (!entry) {
            return;
        }


        if (
            !entry.remoteDescriptionSet
        ) {
            return;
        }


        const pending =
            entry.pendingIce || [];


        entry.pendingIce =
            [];


        for (
            const candidate of pending
        ) {

            try {

                await entry.peer.addIceCandidate(
                    new RTCIceCandidate(
                        candidate
                    )
                );

            } catch (error) {

                console.warn(
                    "Pending viewer ICE failed:",
                    viewerId,
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
                "Broadcaster signaling socket is not open"
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
                "Broadcaster signaling send error:",
                error
            );

            return false;

        }

    },


    // =====================================================
    // REMOVE VIEWER
    // =====================================================

    removeViewer(viewerId) {

        const entry =
            this.viewers[viewerId];


        if (!entry) {
            return;
        }


        try {

            entry.peer.close();

        } catch {}


        delete this.viewers[
            viewerId
        ];

    },


    // =====================================================
    // GET VIEWER COUNT
    // =====================================================

    getViewerCount() {

        return Object.keys(
            this.viewers
        ).length;

    },


    // =====================================================
    // STOP
    // =====================================================

    stop() {

        /*
         * تمام PeerConnectionهای viewerها
         * را می‌بندیم.
         */

        for (
            const viewerId
            of Object.keys(this.viewers)
        ) {

            this.removeViewer(
                viewerId
            );

        }


        if (this.socket) {

            try {
                this.socket.close();
            } catch {}

            this.socket = null;

        }


        this.stream = null;
        this.streamId = null;

        this.started = false;
        this.broadcasterId = null;

        this.viewers = {};

    }

};


window.LainoWebRTC =
    LainoWebRTC;
```
