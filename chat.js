"use strict";


const LainoChat = {


    socket: null,

    streamId: null,

    callback: null,





    connect(
        streamId,
        onMessage
    ){


        this.streamId =
            streamId;


        this.callback =
            onMessage;




        const protocol =

            location.protocol === "https:"
            ?
            "wss"
            :
            "ws";



        const host =

            "127.0.0.1:8000";



        const url =

            protocol
            +
            "://"
            +
            host
            +
            "/ws/chat/"
            +
            streamId;





        this.socket =

            new WebSocket(
                url
            );






        this.socket.onopen = ()=>{


            console.log(
                "LainoLive chat connected"
            );


        };








        this.socket.onmessage =

            event =>{


                try{


                    const data =

                        JSON.parse(
                            event.data
                        );



                    if(
                        this.callback
                    ){

                        this.callback(
                            data
                        );

                    }



                }

                catch(error){


                    console.log(
                        error
                    );


                }


            };








        this.socket.onclose = ()=>{


            console.log(
                "chat closed"
            );



        };







        this.socket.onerror =

            error =>{


                console.log(
                    "chat error",
                    error
                );


            };



    },








    send(
        message
    ){



        if(

            !this.socket

            ||

            this.socket.readyState !== WebSocket.OPEN

        ){

            return false;

        }





        const username =


            localStorage.getItem(
                "lainolive_username"
            )

            ||

            "guest";







        this.socket.send(

            JSON.stringify({

                username:

                    username,


                message:

                    message,


                time:

                    Date.now()


            })

        );



        return true;


    },








    close(){


        if(
            this.socket
        ){


            this.socket.close();


            this.socket =
                null;


        }


    }



};