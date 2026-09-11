"use strict";


chrome.action.onClicked.addListener(
    async (tab) => {

        try {

            if (
                !tab ||
                typeof tab.id !== "number"
            ) {

                console.error(
                    "LainoLive: active tab id not found."
                );

                return;
            }


            console.log(
                "LainoLive: extension invoked on tab:",
                tab.id
            );


            const streamId =
                await chrome.tabCapture.getMediaStreamId(
                    {
                        targetTabId:
                            tab.id,

                        consumerTabId:
                            tab.id
                    }
                );


            console.log(
                "LainoLive: stream id created."
            );


            await chrome.tabs.sendMessage(
                tab.id,
                {
                    type:
                        "LAINOLIVE_TAB_CAPTURE_READY",

                    streamId:
                        streamId
                }
            );


        } catch (error) {

            console.error(
                "LainoLive tab capture error:",
                error
            );


            try {

                await chrome.tabs.sendMessage(
                    tab.id,
                    {
                        type:
                            "LAINOLIVE_TAB_CAPTURE_ERROR",

                        error:
                            error?.message ||
                            String(error)
                    }
                );

            } catch (
                sendError
            ) {

                console.error(
                    "LainoLive send error:",
                    sendError
                );
            }
        }
    }
);