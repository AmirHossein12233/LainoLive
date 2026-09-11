"use strict";


const LainoLiveApp = (() => {


    const KEYS = {

        login:
            "lainolive_logged_in",

        username:
            "lainolive_username",

        displayName:
            "lainolive_display_name",

        avatar:
            "lainolive_avatar"

    };



    let user = {

        username:
            "",

        displayName:
            "",

        avatar:
            ""

    };







    function loadUser(){


        user.username =

            localStorage.getItem(
                KEYS.username
            )
            ||
            "";



        user.displayName =

            localStorage.getItem(
                KEYS.displayName
            )
            ||
            user.username;



        user.avatar =

            localStorage.getItem(
                KEYS.avatar
            )
            ||
            "";



        return user;


    }









    function isLoggedIn(){


        return (

            localStorage.getItem(
                KEYS.login
            )

            ===

            "true"

        );


    }









    function login(username){


        if(!username){

            return false;

        }



        localStorage.setItem(

            KEYS.login,

            "true"

        );



        localStorage.setItem(

            KEYS.username,

            username

        );



        user.username =
            username;



        return true;


    }









    function logout(){



        localStorage.removeItem(
            KEYS.login
        );


        localStorage.removeItem(
            KEYS.username
        );


        sessionStorage.clear();



        window.location.href =
            "/login.html";


    }









    function getUser(){


        return loadUser();


    }









    async function api(url, options = {}){


        try{


            const response =

                await fetch(

                    url,

                    {

                        headers:
                        {

                            "Content-Type":
                                "application/json"

                        },


                        ...options


                    }

                );





            const data =

                await response.json()
                .catch(
                    ()=>({})
                );





            return {


                ok:
                    response.ok,


                status:
                    response.status,


                data:
                    data


            };



        }

        catch(error){



            return {


                ok:
                    false,


                error:
                    error.message


            };


        }



    }









    function requireLogin(){


        if(
            !isLoggedIn()
        ){


            window.location.href =
                "/login.html";


            return false;


        }



        return true;


    }







    loadUser();





    return {


        keys:
            KEYS,


        user:
            getUser,


        login:
            login,


        logout:
            logout,


        api:
            api,


        isLoggedIn:
            isLoggedIn,


        requireLogin:
            requireLogin


    };



})();


/* =====================================================
   CURRENT STREAM
===================================================== */


const STREAM_KEY =
    "lainolive_current_stream";



function saveCurrentStream(stream){


    if(!stream){

        return false;

    }



    try{


        sessionStorage.setItem(

            STREAM_KEY,

            JSON.stringify(
                stream
            )

        );



        localStorage.setItem(

            STREAM_KEY,

            JSON.stringify(
                stream
            )

        );



        return true;



    }

    catch(error){


        console.log(
            error
        );


        return false;


    }



}








function getCurrentStream(){



    try{


        let data =

            sessionStorage.getItem(
                STREAM_KEY
            );



        if(data){

            return JSON.parse(data);

        }




        data =

            localStorage.getItem(
                STREAM_KEY
            );



        if(data){

            return JSON.parse(data);

        }



    }

    catch(error){


        console.log(error);


    }



    return null;



}








function clearCurrentStream(){



    sessionStorage.removeItem(
        STREAM_KEY
    );



    localStorage.removeItem(
        STREAM_KEY
    );



}









/* =====================================================
   STREAM SETTINGS
===================================================== */



const SETTINGS_KEY =
    "lainolive_settings";





function getSettings(){



    try{


        const data =

            localStorage.getItem(
                SETTINGS_KEY
            );



        if(data){

            return JSON.parse(data);

        }



    }

    catch{}



    return {


        videoQuality:
            "720p",


        audioQuality:
            "128kbps",


        autoplay:
            true,


        dataSaver:
            false


    };



}








function saveSettings(settings){



    localStorage.setItem(

        SETTINGS_KEY,

        JSON.stringify(
            settings
        )

    );



    return settings;


}









function updateSetting(
    key,
    value
){



    const settings =
        getSettings();



    settings[key] =
        value;



    saveSettings(
        settings
    );



    return settings;


}









/* =====================================================
   STREAM HELPERS
===================================================== */



function streamId(stream){


    return (

        stream?.id

        ||

        stream?.stream_id

        ||

        null

    );


}






function isMyStream(stream){



    const owner =

        stream?.username
        ||
        "";



    return (

        owner

        ===

        user.username

    );



}








function openViewer(id){



    window.location.href =

        "/viewer.html?id="

        +

        encodeURIComponent(
            id
        );



}








function openLive(){



    window.location.href =

        "/live.html";


}







/* =====================================================
   NOTIFICATIONS
===================================================== */


function notify(
    message,
    type = "info"
){


    const box =
        document.createElement(
            "div"
        );



    box.textContent =
        message;



    box.style.cssText =

    `
    position:fixed;
    top:20px;
    right:20px;
    z-index:9999;
    padding:14px 18px;
    border-radius:14px;
    background:
    rgba(20,20,30,.95);
    color:white;
    font-size:13px;
    border:
    1px solid
    rgba(255,255,255,.1);
    box-shadow:
    0 10px 30px
    rgba(0,0,0,.4);
    `;



    document.body.appendChild(
        box
    );



    setTimeout(

        ()=>{

            box.remove();

        },

        3000

    );



}









/* =====================================================
   COPY TEXT
===================================================== */


async function copyText(text){


    try{


        await navigator.clipboard.writeText(
            text
        );



        notify(
            "کپی شد ✅"
        );



        return true;


    }

    catch{


        return false;


    }


}









/* =====================================================
   TIME FORMAT
===================================================== */


function formatTime(timestamp){



    const date =
        new Date(
            timestamp
        );



    return date.toLocaleTimeString(
        "fa-IR",
        {

            hour:
                "2-digit",

            minute:
                "2-digit"

        }
    );



}









/* =====================================================
   DEVICE INFO
===================================================== */


function device(){



    return {


        mobile:
            /Android|iPhone/i
            .test(
                navigator.userAgent
            ),



        language:
            navigator.language
            ||
            "fa"



    };


}









/* =====================================================
   FINAL EXPORT
===================================================== */


return {


    keys:
        KEYS,


    user:
        getUser,


    login:
        login,


    logout:
        logout,


    api:
        api,


    isLoggedIn:
        isLoggedIn,


    requireLogin:
        requireLogin,


    saveCurrentStream:
        saveCurrentStream,


    getCurrentStream:
        getCurrentStream,


    clearCurrentStream:
        clearCurrentStream,


    getSettings:
        getSettings,


    saveSettings:
        saveSettings,


    updateSetting:
        updateSetting,


    streamId:
        streamId,


    isMyStream:
        isMyStream,


    openViewer:
        openViewer,


    openLive:
        openLive,


    notify:
        notify,


    copyText:
        copyText,


    formatTime:
        formatTime,


    device:
        device


};

