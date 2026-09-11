"use strict";

chrome.runtime.onMessage.addListener(
    async (
        message,
        sender,
        sendResponse
    ) => {

        if (
            message?.type !==
            "LAINOLIVE_GET_TAB_CAPTURE"
        ) {
            return;
        }

        try {

            const tabId =
                sender?.tab?.id;

            if (
                typeof tabId !==
                "number"
            ) {

                sendResponse({
                    ok: false,
                    error:
                        "شناسه تب پیدا نشد."
                });

                return;
            }

            const streamId =
                await chrome.tabCapture.getMediaStreamId({
                    targetTabId:
                        tabId,

                    consumerTabId:
                        tabId
                });

            sendResponse({
                ok: true,
                streamId:
                    streamId
            });

        } catch (error) {

            console.error(
                "LainoLive tabCapture error:",
                error
            );

            sendResponse({
                ok: false,
                error:
                    error?.message ||
                    String(error)
            });
        }
    }
);