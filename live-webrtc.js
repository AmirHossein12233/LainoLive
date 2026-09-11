"use strict";


const LainoWebRTC = {


    peer: null,

    socket: null,

    stream: null,

    streamId: null,





    start: function(
        streamId,
        mediaStream
    ){


        this.streamId =
            streamId;


        this.stream =
            mediaStream;



        const protocol =

            location.protocol === "https:"
            ?
            "wss"
            :
            "ws";



        this.socket =

            new WebSocket(

                protocol
                +
                "://"
                +
                location.host
                +
                "/ws/webrtc/"
                +
                streamId

            );





        this.socket.onopen = ()=>{


            console.log(
                "WebRTC signaling connected"
            );


        };






        this.socket.onmessage =

            async event =>{


                const data =

                    JSON.parse(
                        event.data
                    );



                if(
                    data.answer
                ){


                    await this.peer.setRemoteDescription(

                        new RTCSessionDescription(
                            data.answer
                        )

                    );


                }




                if(
                    data.ice
                ){


                    await this.peer.addIceCandidate(

                        data.ice

                    );


                }



            };







        this.createPeer();



    },







    createPeer: async function(){



        this.peer =

            new RTCPeerConnection({

                iceServers:[

                    {

                        urls:
                        "stun:stun.l.google.com:19302"

                    }

                ]

            });







        this.stream
        .getTracks()
        .forEach(

            track => {


                this.peer.addTrack(

                    track,

                    this.stream

                );


            }

        );







        this.peer.onicecandidate =

            event =>{


                if(

                    event.candidate

                ){


                    this.socket.send(

                        JSON.stringify({

                            ice:
                            event.candidate


                        })

                    );


                }


            };







        const offer =

            await this.peer.createOffer();



        await this.peer.setLocalDescription(

            offer

        );






        this.socket.send(

            JSON.stringify({

                offer:

                    offer


            })

        );




    }






};