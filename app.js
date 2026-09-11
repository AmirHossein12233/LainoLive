"use strict";


const LainoApp = {


    user: null,




    init(){


        this.loadUser();


        this.applySettings();


    },






    loadUser(){


        this.user =

            localStorage.getItem(
                "lainolive_username"
            );


    },







    isLogin(){


        return !!this.user;


    },







    requireLogin(){


        if(!this.isLogin()){


            location.href =
                "login.html";


            return false;


        }


        return true;


    },








    logout(){


        localStorage.removeItem(

            "lainolive_username"

        );



        location.href =
            "login.html";


    },








    applySettings(){


        const settings =

            JSON.parse(

                localStorage.getItem(
                    "lainolive_settings"
                )

                ||

                "{}"

            );





        if(

            settings.mode === "simple"

        ){


            document.body.style.background =

                "#111";


        }


    }






};






document.addEventListener(

"DOMContentLoaded",

()=>{


    LainoApp.init();


});