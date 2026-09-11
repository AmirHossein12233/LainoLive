(function () {
    "use strict";

    const CACHE_KEY =
        "lainolive_streams_cache";

    const CACHE_TIME_KEY =
        "lainolive_streams_cache_time";

    const DEFAULT_TTL =
        1000;

    let activeRequest = null;

    async function fetchStreams(
        options = {}
    ) {

        const force =
            options.force === true;

        const ttl =
            Number(
                options.ttl ??
                DEFAULT_TTL
            );

        const now =
            Date.now();

        /*
         * -----------------------------------------
         * استفاده از کش موجود
         * -----------------------------------------
         */

        if (!force) {

            try {

                const cached =
                    sessionStorage.getItem(
                        CACHE_KEY
                    );

                const cachedTime =
                    Number(
                        sessionStorage.getItem(
                            CACHE_TIME_KEY
                        ) || 0
                    );

                if (
                    cached &&
                    now - cachedTime < ttl
                ) {

                    const parsed =
                        JSON.parse(
                            cached
                        );

                    return normalizeStreams(
                        parsed
                    );
                }

            } catch (error) {

                console.warn(
                    "streams cache read error:",
                    error
                );
            }
        }


        /*
         * -----------------------------------------
         * جلوگیری از درخواست هم‌زمان
         * -----------------------------------------
         */

        if (
            activeRequest
        ) {

            return activeRequest;
        }


        /*
         * -----------------------------------------
         * درخواست جدید
         * -----------------------------------------
         */

        activeRequest =
            fetch(
                "/api/streams",
                {
                    method:
                        "GET",

                    cache:
                        "no-store",

                    headers: {
                        "Accept":
                            "application/json"
                    }
                }
            )
                .then(
                    async response => {

                        if (
                            !response.ok
                        ) {

                            throw new Error(
                                "streams request failed: " +
                                response.status
                            );
                        }


                        const data =
                            await response.json();


                        /*
                         * ذخیره در کش
                         */

                        try {

                            sessionStorage.setItem(
                                CACHE_KEY,
                                JSON.stringify(
                                    data
                                )
                            );

                            sessionStorage.setItem(
                                CACHE_TIME_KEY,
                                String(
                                    Date.now()
                                )
                            );

                        } catch (error) {

                            console.warn(
                                "streams cache write error:",
                                error
                            );
                        }


                        return normalizeStreams(
                            data
                        );
                    }
                )
                .catch(
                    error => {

                        console.error(
                            "fetch streams error:",
                            error
                        );

                        /*
                         * اگر درخواست شکست خورد،
                         * در صورت وجود کش قبلی از آن
                         * استفاده کن.
                         */

                        try {

                            const cached =
                                sessionStorage.getItem(
                                    CACHE_KEY
                                );

                            if (cached) {

                                return normalizeStreams(
                                    JSON.parse(
                                        cached
                                    )
                                );
                            }

                        } catch (cacheError) {

                            console.warn(
                                "fallback cache error:",
                                cacheError
                            );
                        }


                        throw error;
                    }
                )
                .finally(
                    () => {

                        activeRequest =
                            null;
                    }
                );


        return activeRequest;
    }


    function normalizeStreams(
        data
    ) {

        if (
            Array.isArray(
                data?.streams
            )
        ) {

            return data.streams;
        }


        if (
            Array.isArray(data)
        ) {

            return data;
        }


        return [];
    }


    function clearStreamsCache() {

        try {

            sessionStorage.removeItem(
                CACHE_KEY
            );

            sessionStorage.removeItem(
                CACHE_TIME_KEY
            );

        } catch (error) {

            console.warn(
                "clear streams cache error:",
                error
            );
        }
    }


    function getCachedStreams() {

        try {

            const cached =
                sessionStorage.getItem(
                    CACHE_KEY
                );

            if (!cached) {
                return [];
            }

            return normalizeStreams(
                JSON.parse(
                    cached
                )
            );

        } catch {

            return [];
        }
    }


    function getCacheAge() {

        try {

            const time =
                Number(
                    sessionStorage.getItem(
                        CACHE_TIME_KEY
                    ) || 0
                );

            if (!time) {
                return Infinity;
            }

            return Date.now() - time;

        } catch {

            return Infinity;
        }
    }


    /*
     * -----------------------------------------
     * عمومی کردن API
     * -----------------------------------------
     */

    window.LainoLiveStreams = {
        fetch:
            fetchStreams,

        clear:
            clearStreamsCache,

        getCached:
            getCachedStreams,

        getAge:
            getCacheAge
    };

})();
