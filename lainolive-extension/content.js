"use strict";

console.log(
    "LainoLive Tab Audio extension loaded."
);

window.addEventListener(
    "message",
    async (event) => {

        if (
            event.source !== window
        ) {
            return;
        }

        const message =
            event.data;

        if (
            !message ||
            message.type !==
                "LAINOLIVE_REQUEST_TAB_CAPTURE"
        ) {
            return;
        }

        try {

            const response =
                await chrome.runtime.sendMessage({
                    type:
                        "LAINOLIVE_GET_TAB_CAPTURE"
                });

            window.postMessage(
                {
                    type:
                        "LAINOLIVE_TAB_CAPTURE_RESULT",

                    requestId:
                        message.requestId,

                    response:
                        response
                },

                window.location.origin
            );

        } catch (error) {

            window.postMessage(
                {
                    type:
                        "LAINOLIVE_TAB_CAPTURE_RESULT",

                    requestId:
                        message.requestId,

                    response: {
                        ok: false,

                        error:
                            error?.message ||
                            String(error)
                    }
                },

                window.location.origin
            );
        }
    }
);