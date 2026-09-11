"use strict";


const CACHE_NAME =
    "lainolive-cache-v1";



const APP_FILES = [

    "/",

    "/index.html",

    "/login.html",

    "/live.html",

    "/viewer.html",

    "/profile.html",

    "/settings.html",

    "/manifest.json",

    "/streams-cache.js",

    "/app.js",

    "/chat.js",

    "/icons/icon-192.png",

    "/icons/icon-512.png"

];






/*
    INSTALL
*/


self.addEventListener(
    "install",
    event => {


        event.waitUntil(

            caches.open(
                CACHE_NAME
            )

            .then(
                cache => {

                    return cache.addAll(
                        APP_FILES
                    );

                }

            )

        );



        self.skipWaiting();


    }

);








/*
    ACTIVATE
*/


self.addEventListener(
    "activate",
    event => {


        event.waitUntil(


            caches.keys()

            .then(
                keys => {


                    return Promise.all(

                        keys.map(

                            key => {


                                if(
                                    key !== CACHE_NAME
                                ){

                                    return caches.delete(
                                        key
                                    );

                                }


                            }

                        )

                    );


                }

            )


        );



        self.clients.claim();



    }

);








/*
    FETCH
*/


self.addEventListener(
    "fetch",
    event => {



        const request =
            event.request;




        if(
            request.method !== "GET"
        ){

            return;

        }






        event.respondWith(


            fetch(
                request
            )

            .then(
                response => {


                    const copy =
                        response.clone();



                    caches.open(
                        CACHE_NAME
                    )

                    .then(
                        cache => {


                            cache.put(

                                request,

                                copy

                            );


                        }

                    );



                    return response;


                }

            )

            .catch(


                () => {


                    return caches.match(
                        request
                    );


                }


            )


        );



    }

);