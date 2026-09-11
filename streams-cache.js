"use strict";


const LainoLiveStreams = (() => {


    const CACHE_KEY =
        "lainolive_streams_cache";


    const CACHE_TIME_KEY =
        "lainolive_streams_cache_time";



    let memoryCache = [];

    let lastFetch = 0;

    let loading = false;



    /*
        دریافت لیست لایوها
    */

    async function fetchStreams(options = {}) {


        const force =
            options.force === true;


        const ttl =
            options.ttl || 3000;




        const now =
            Date.now();




        if(
            !force &&
            memoryCache.length > 0 &&
            (now - lastFetch) < ttl
        ){

            return memoryCache;

        }




        if(loading){


            return memoryCache;


        }



        loading = true;




        try{


            const response =

                await fetch(

                    "/api/streams",

                    {

                        method:
                            "GET",


                        headers:
                        {

                            "Accept":
                            "application/json"

                        },


                        cache:
                            "no-store"

                    }

                );





            if(!response.ok){


                throw new Error(
                    "Streams API error"
                );


            }





            const data =

                await response.json();





            let streams = [];




            if(
                Array.isArray(data)
            ){

                streams =
                    data;


            }

            else if(
                Array.isArray(
                    data.streams
                )
            ){

                streams =
                    data.streams;


            }






            memoryCache =
                streams;



            lastFetch =
                Date.now();





            localStorage.setItem(

                CACHE_KEY,

                JSON.stringify(
                    streams
                )

            );





            localStorage.setItem(

                CACHE_TIME_KEY,

                String(
                    lastFetch
                )

            );






            return streams;



        }

        catch(error){



            console.log(
                "streams cache:",
                error
            );




            return loadLocalCache();



        }

        finally{


            loading =
                false;


        }



    }








    /*
        دریافت کش ذخیره شده
    */

    function loadLocalCache(){



        try{


            const saved =

                localStorage.getItem(
                    CACHE_KEY
                );




            if(saved){



                memoryCache =

                    JSON.parse(
                        saved
                    );



                return memoryCache;


            }



        }

        catch(error){


            console.log(error);


        }




        return [];



    }









    /*
        گرفتن یک لایو با ID
    */

    function getStream(id){



        return memoryCache.find(

            stream =>


                String(

                    stream.id ||

                    stream.stream_id

                )

                ===

                String(id)


        )

        ||

        null;


    }








    /*
        ذخیره یا بروزرسانی لایو
    */

    function save(stream){



        if(!stream){

            return;

        }




        const id =

            stream.id ||

            stream.stream_id;





        memoryCache =

            memoryCache.filter(

                item =>


                    String(

                        item.id ||

                        item.stream_id

                    )

                    !==

                    String(id)


            );






        memoryCache.unshift(
            stream
        );





        saveLocal();



    }









    /*
        حذف لایو
    */

    function remove(id){



        memoryCache =

            memoryCache.filter(

                item =>


                    String(

                        item.id ||

                        item.stream_id

                    )

                    !==

                    String(id)


            );





        saveLocal();



    }









    /*
        ذخیره دستی کش
    */

    function saveLocal(){



        localStorage.setItem(

            CACHE_KEY,

            JSON.stringify(
                memoryCache
            )

        );



        localStorage.setItem(

            CACHE_TIME_KEY,

            String(
                Date.now()
            )

        );



    }









    /*
        پاک کردن کامل کش
    */

    function clear(){



        memoryCache = [];


        lastFetch = 0;



        localStorage.removeItem(
            CACHE_KEY
        );


        localStorage.removeItem(
            CACHE_TIME_KEY
        );


    }









    /*
        تعداد لایوها
    */

    function count(){


        return memoryCache.length;


    }









    /*
        آخرین زمان بروزرسانی
    */

    function updatedAt(){


        return lastFetch;


    }








    return {


        fetch:
            fetchStreams,


        get:
            getStream,


        save:
            save,


        remove:
            remove,


        clear:
            clear,


        count:
            count,


        updatedAt:
            updatedAt


    };



})();