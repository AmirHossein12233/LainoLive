"use strict";


const StreamsCache = {


    key:
    "lainolive_streams",


    time:
    5000,







    save(streams){


        localStorage.setItem(

            this.key,

            JSON.stringify({

                created:
                Date.now(),


                data:
                streams


            })

        );


    },








    get(){


        const item =

        localStorage.getItem(
            this.key
        );



        if(!item)

            return null;





        try{


            const cache =

            JSON.parse(
                item
            );



            if(

                Date.now()
                -
                cache.created

                >

                this.time

            ){


                return null;


            }



            return cache.data;



        }

        catch(e){


            return null;


        }



    },








    clear(){


        localStorage.removeItem(

            this.key

        );


    },








    async load(){



        const cached =

        this.get();





        if(cached){


            return cached;


        }






        try{


            const response =

            await fetch(

                "http://127.0.0.1:8000/api/streams"

            );





            const data =

            await response.json();





            if(data.success){


                this.save(

                    data.streams

                );



                return data.streams;


            }



        }

        catch(error){


            console.log(

                "Streams cache error",

                error

            );


        }




        return [];



    }






};