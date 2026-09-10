/* =========================================
   LainoLive - App JavaScript
   ========================================= */

document.addEventListener("DOMContentLoaded", () => {

    // -----------------------------------------
    // Elements
    // -----------------------------------------

    const startLiveBtn = document.getElementById("startLiveBtn");
    const liveNavBtn = document.getElementById("liveNavBtn");

    const startLiveModal = document.getElementById("startLiveModal");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const confirmLiveBtn = document.getElementById("confirmLiveBtn");

    const liveTitleInput = document.getElementById("liveTitle");

    const liveList = document.getElementById("liveList");
    const emptyState = document.getElementById("emptyState");

    const homeBtn = document.getElementById("homeBtn");
    const notificationsBtn = document.getElementById("notificationsBtn");
    const profileBtn = document.getElementById("profileBtn");


    // -----------------------------------------
    // State
    // -----------------------------------------

    let fakeLiveCount = 3;


    // -----------------------------------------
    // Modal
    // -----------------------------------------

    function openLiveModal() {
        startLiveModal.classList.remove("hidden");

        setTimeout(() => {
            liveTitleInput.focus();
        }, 150);
    }

    function closeLiveModal() {
        startLiveModal.classList.add("hidden");
        liveTitleInput.value = "";
    }


    startLiveBtn.addEventListener("click", openLiveModal);

    liveNavBtn.addEventListener("click", openLiveModal);

    closeModalBtn.addEventListener("click", closeLiveModal);


    // بستن با کلیک روی قسمت تاریک
    startLiveModal.addEventListener("click", (event) => {

        if (event.target === startLiveModal) {
            closeLiveModal();
        }

    });


    // بستن با کلید Escape در کامپیوتر
    document.addEventListener("keydown", (event) => {

        if (event.key === "Escape") {
            closeLiveModal();
        }

    });


    // -----------------------------------------
    // Start Live
    // -----------------------------------------

    confirmLiveBtn.addEventListener("click", () => {

        const title = liveTitleInput.value.trim();

        if (!title) {
            showMessage("لطفاً عنوان پخش را وارد کنید.");
            liveTitleInput.focus();
            return;
        }

        fakeLiveCount++;

        addLiveCard(title);

        closeLiveModal();

        showMessage("پخش زنده شما ایجاد شد 🔴");

    });


    // -----------------------------------------
    // Enter key in title input
    // -----------------------------------------

    liveTitleInput.addEventListener("keydown", (event) => {

        if (event.key === "Enter") {
            event.preventDefault();
            confirmLiveBtn.click();
        }

    });


    // -----------------------------------------
    // Add new live card
    // -----------------------------------------

    function addLiveCard(title) {

        const card = document.createElement("div");

        card.className = "live-card";

        card.dataset.liveId = String(fakeLiveCount);

        card.innerHTML = `
            <div class="live-preview">

                <div class="live-badge">
                    🔴 زنده
                </div>

                <div class="viewer-count">
                    👥 1
                </div>

                <div class="play-icon">
                    ▶
                </div>

            </div>

            <div class="live-info">

                <div class="avatar">
                    📺
                </div>

                <div class="live-text">

                    <h2>${escapeHtml(title)}</h2>

                    <p>پخش زنده شما</p>

                </div>

            </div>
        `;

        liveList.prepend(card);

        attachLiveCard(card);

        updateEmptyState();

    }


    // -----------------------------------------
    // Live card events
    // -----------------------------------------

    function attachLiveCard(card) {

        card.addEventListener("click", () => {

            const titleElement = card.querySelector(".live-text h2");

            const title = titleElement
                ? titleElement.textContent
                : "پخش زنده";

            openLiveViewer(title);

        });

    }


    // اتصال رویداد به کارت‌های اولیه
    document.querySelectorAll(".live-card").forEach((card) => {
        attachLiveCard(card);
    });


    // -----------------------------------------
    // Fake Live Viewer
    // -----------------------------------------

    function openLiveViewer(title) {

        const viewer = document.createElement("div");

        viewer.className = "live-viewer-overlay";

        viewer.innerHTML = `
            <div class="live-viewer">

                <button class="viewer-close">
                    ✕
                </button>

                <div class="viewer-video">

                    <div class="viewer-live-badge">
                        🔴 زنده
                    </div>

                    <div class="viewer-title">
                        ${escapeHtml(title)}
                    </div>

                    <div class="viewer-play">
                        ▶
                    </div>

                    <div class="viewer-loading">
                        در حال اتصال به پخش...
                    </div>

                </div>

                <div class="viewer-info">

                    <div>
                        <strong>${escapeHtml(title)}</strong>
                        <span>👥 در حال تماشا</span>
                    </div>

                    <button class="follow-btn">
                        دنبال کردن
                    </button>

                </div>

                <div class="viewer-actions">

                    <button class="viewer-action">
                        ❤️
                        <span>پسندیدم</span>
                    </button>

                    <button class="viewer-action">
                        💬
                        <span>نظرها</span>
                    </button>

                    <button class="viewer-action">
                        🔗
                        <span>اشتراک</span>
                    </button>

                </div>

            </div>
        `;

        document.body.appendChild(viewer);

        document.body.style.overflow = "hidden";

        const closeViewerBtn =
            viewer.querySelector(".viewer-close");

        closeViewerBtn.addEventListener("click", () => {
            closeLiveViewer(viewer);
        });

        viewer.addEventListener("click", (event) => {

            if (event.target === viewer) {
                closeLiveViewer(viewer);
            }

        });

        const followBtn =
            viewer.querySelector(".follow-btn");

        followBtn.addEventListener("click", () => {

            followBtn.textContent = "دنبال می‌کنید ✓";

            followBtn.classList.add("following");

            showMessage("به این پخش دنبال شد.");

        });

        const actionButtons =
            viewer.querySelectorAll(".viewer-action");

        actionButtons.forEach((button) => {

            button.addEventListener("click", () => {

                const text =
                    button.querySelector("span")?.textContent || "";

                if (text === "پسندیدم") {
                    button.classList.toggle("liked");
                }

                if (text === "نظرها") {
                    showMessage("بخش نظرات در نسخه بعدی فعال می‌شود.");
                }

                if (text === "اشتراک") {
                    shareLive(title);
                }

            });

        });

    }


    function closeLiveViewer(viewer) {

        viewer.remove();

        document.body.style.overflow = "";

    }


    // -----------------------------------------
    // Share
    // -----------------------------------------

    async function shareLive(title) {

        const shareText =
            `پخش زنده «${title}» در لاینو`;

        try {

            if (navigator.share) {

                await navigator.share({
                    title: title,
                    text: shareText
                });

                return;
            }

        } catch (error) {
            // کاربر اشتراک‌گذاری را لغو کرده است.
        }

        try {

            await navigator.clipboard.writeText(shareText);

            showMessage("متن پخش کپی شد.");

        } catch (error) {

            showMessage("اشتراک‌گذاری در این دستگاه در دسترس نیست.");

        }

    }


    // -----------------------------------------
    // Bottom navigation
    // -----------------------------------------

    const navItems = document.querySelectorAll(".nav-item");

    function activateNav(button) {

        navItems.forEach((item) => {
            item.classList.remove("active");
        });

        button.classList.add("active");

    }


    homeBtn.addEventListener("click", () => {

        activateNav(homeBtn);

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });

    });


    notificationsBtn.addEventListener("click", () => {

        activateNav(notificationsBtn);

        showMessage("فعلاً اعلان جدیدی ندارید 🔔");

    });


    profileBtn.addEventListener("click", () => {

        activateNav(profileBtn);

        showMessage("صفحه پروفایل در مرحله بعد ساخته می‌شود.");

    });


    // -----------------------------------------
    // Empty state
    // -----------------------------------------

    function updateEmptyState() {

        if (!liveList) {
            return;
        }

        const cards =
            liveList.querySelectorAll(".live-card");

        if (cards.length === 0) {

            emptyState.style.display = "block";

        } else {

            emptyState.style.display = "none";

        }

    }

    updateEmptyState();


    // -----------------------------------------
    // Message / Toast
    // -----------------------------------------

    function showMessage(text) {

        const oldToast =
            document.querySelector(".laino-toast");

        if (oldToast) {
            oldToast.remove();
        }

        const toast =
            document.createElement("div");

        toast.className = "laino-toast";

        toast.textContent = text;

        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.add("show");
        });

        setTimeout(() => {

            toast.classList.remove("show");

            setTimeout(() => {
                toast.remove();
            }, 250);

        }, 2200);

    }


    // -----------------------------------------
    // Escape HTML
    // -----------------------------------------

    function escapeHtml(value) {

        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");

    }


    // -----------------------------------------
    // Extra styles required by JS viewer/toast
    // -----------------------------------------

    const dynamicStyle =
        document.createElement("style");

    dynamicStyle.textContent = `

        .live-viewer-overlay {
            position: fixed;
            inset: 0;
            z-index: 1000;

            display: flex;
            align-items: stretch;
            justify-content: center;

            background: #000;

            animation: viewerFadeIn 0.2s ease;
        }

        .live-viewer {
            width: 100%;
            max-width: 900px;
            height: 100%;

            display: flex;
            flex-direction: column;

            background: #0d0e13;
            color: #fff;
        }

        .viewer-video {
            position: relative;

            flex: 1;

            min-height: 0;

            display: flex;
            align-items: center;
            justify-content: center;

            overflow: hidden;

            background:
                radial-gradient(
                    circle at 30% 30%,
                    #343746 0%,
                    #1b1d27 35%,
                    #08090d 100%
                );
        }

        .viewer-video::before,
        .viewer-video::after {
            content: "";

            position: absolute;

            width: 220px;
            height: 220px;

            border-radius: 50%;

            filter: blur(55px);

            opacity: 0.3;
        }

        .viewer-video::before {
            top: 10%;
            right: 5%;
            background: #ff304f;
        }

        .viewer-video::after {
            bottom: 5%;
            left: 5%;
            background: #565cff;
        }

        .viewer-play {
            position: relative;
            z-index: 2;

            width: 74px;
            height: 74px;

            border-radius: 50%;

            display: flex;
            align-items: center;
            justify-content: center;

            background: rgba(255,255,255,0.94);
            color: #ff304f;

            font-size: 25px;

            padding-right: 2px;
        }

        .viewer-live-badge {
            position: absolute;

            top: 18px;
            right: 18px;

            z-index: 3;

            padding: 8px 12px;

            border-radius: 11px;

            background: #ff304f;
            color: #fff;

            font-size: 12px;
            font-weight: 900;
        }

        .viewer-title {
            position: absolute;

            top: 18px;
            left: 18px;
            right: 90px;

            z-index: 3;

            font-size: 14px;
            font-weight: 800;

            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .viewer-loading {
            position: absolute;

            bottom: 24px;
            left: 0;
            right: 0;

            z-index: 3;

            text-align: center;

            color: rgba(255,255,255,0.7);

            font-size: 12px;
        }

        .viewer-info {
            display: flex;
            align-items: center;
            justify-content: space-between;

            gap: 14px;

            padding: 16px;

            background: #14151c;
        }

        .viewer-info > div {
            min-width: 0;
        }

        .viewer-info strong {
            display: block;

            margin-bottom: 5px;

            font-size: 15px;

            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .viewer-info span {
            display: block;

            color: #999eaa;

            font-size: 12px;
        }

        .follow-btn {
            flex: 0 0 auto;

            height: 42px;

            padding: 0 14px;

            border: none;
            border-radius: 13px;

            background: #ff304f;
            color: #fff;

            font-size: 12px;
            font-weight: 900;

            cursor: pointer;
        }

        .follow-btn.following {
            background: #2b2d36;
            color: #fff;
        }

        .viewer-actions {
            display: grid;
            grid-template-columns: repeat(3, 1fr);

            padding:
                8px
                max(8px, env(safe-area-inset-right))
                max(8px, env(safe-area-inset-bottom))
                max(8px, env(safe-area-inset-left));

            background: #14151c;
            border-top: 1px solid #292b35;
        }

        .viewer-action {
            min-height: 58px;

            border: none;
            border-radius: 13px;

            background: transparent;
            color: #fff;

            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;

            gap: 5px;

            font-size: 20px;

            cursor: pointer;
        }

        .viewer-action span {
            font-size: 11px;
            color: #a5a9b4;
        }

        .viewer-action:hover {
            background: #20222b;
        }

        .viewer-action.liked {
            background: rgba(255,48,79,0.12);
        }

        .viewer-action.liked span {
            color: #ff304f;
        }

        .laino-toast {
            position: fixed;

            left: 50%;
            bottom: 92px;

            z-index: 3000;

            max-width: calc(100% - 32px);

            padding: 11px 15px;

            border-radius: 13px;

            background: #171820;
            color: #fff;

            font-size: 13px;
            font-weight: 700;

            box-shadow: 0 10px 30px rgba(0,0,0,0.18);

            opacity: 0;
            transform: translate(-50%, 12px);

            pointer-events: none;

            transition:
                opacity 0.2s ease,
                transform 0.2s ease;
        }

        .laino-toast.show {
            opacity: 1;
            transform: translate(-50%, 0);
        }

        @keyframes viewerFadeIn {
            from {
                opacity: 0;
            }

            to {
                opacity: 1;
            }
        }

        @media (min-width: 700px) {

            .live-viewer-overlay {
                align-items: center;

                background: rgba(0,0,0,0.75);

                padding: 20px;
            }

            .live-viewer {
                height: min(820px, 100%);
                border-radius: 24px;
                overflow: hidden;

                box-shadow: 0 25px 80px rgba(0,0,0,0.35);
            }

        }

    `;

    document.head.appendChild(dynamicStyle);

});
