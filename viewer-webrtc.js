"use strict";


const LainoViewerRTC = {


    peer: null,

    socket: null,

    streamId: null,

    video: null,





    connect(
        streamId,
        videoElement
    ){


        this.streamId =
            streamId;


        this.video =
            videoElement;




        const protocol =

            location.protocol === "https:"
            ?
            "wss"
            :
            "ws";



        const host =

            location.hostname
            +
            ":8000";



        this.socket =

            new WebSocket(

                protocol
                +
                "://"
                +
                host
                +
                "/ws/webrtc/"
                +
                streamId

            );






        this.socket.onopen = ()=>{


            console.log(
                "Viewer WebRTC connected"
            );


            this.createPeer();



        };







        this.socket.onmessage =

        async(event)=>{


            const data =

                JSON.parse(
                    event.data
                );





            if(data.offer){



                await this.peer.setRemoteDescription(

                    new RTCSessionDescription(
                        data.offer
                    )

                );





                const answer =

                    await this.peer.createAnswer();




                await this.peer.setLocalDescription(

                    answer

                );





                this.socket.send(

                    JSON.stringify({

                        answer:

                            answer

                    })

                );



            }







            if(data.ice){


                try{


                    await this.peer.addIceCandidate(

                        data.ice

                    );


                }

                catch(e){}


            }



        };







    },









    createPeer(){



        this.peer =

        new RTCPeerConnection({

            iceServers:[

                {

                    urls:

                    "stun:stun.l.google.com:19302"

                }

            ]

        });








        this.peer.ontrack =

        event =>{


            this.video.srcObject =

                event.streams[0];


        };







        this.peer.onicecandidate =

        event =>{


            if(event.candidate){



                this.socket.send(

                    JSON.stringify({

                        ice:

                            event.candidate

                    })

                );



            }


        };



    },








    close(){



        if(this.peer){


            this.peer.close();


            this.peer = null;


        }



        if(this.socket){


            this.socket.close();


            this.socket = null;


        }



    }



};