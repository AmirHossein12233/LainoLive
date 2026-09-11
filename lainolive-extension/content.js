"use strict";


console.log(
    "LainoLive Tab Audio extension loaded."
);


/*
 * وقتی کاربر روی آیکن افزونه کلیک می‌کند،
 * background.js این پیام را می‌فرستد.
 */

chrome.runtime.onMessage.addListener(
    (
        message
    ) => {

        if (
            !message
        ) {

            return;
        }


        if (
            message.type ===
            "LAINOLIVE_TAB_CAPTURE_READY"
        ) {

            console.log(
                "LainoLive: tab capture ready."
            );


            window.postMessage(

                {
                    type:
                        "LAINOLIVE_TAB_CAPTURE_READY",

                    streamId:
                        message.streamId
                },

                window.location.origin

            );


            return;
        }


        if (
            message.type ===
            "LAINOLIVE_TAB_CAPTURE_ERROR"
        ) {

            console.error(
                "LainoLive capture error:",
                message.error
            );


            window.postMessage(

                {
                    type:
                        "LAINOLIVE_TAB_CAPTURE_ERROR",

                    error:
                        message.error ||
                        "خطای Capture تب"
                },

                window.location.origin

            );
        }

    }
);