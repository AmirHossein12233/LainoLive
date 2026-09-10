import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# =========================================================
# تنظیمات
# =========================================================

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

BASE_DIR = Path(__file__).resolve().parent

# Token را در Environment Variable قرار بده.
# Windows PowerShell:
#
# $env:AMOOT_API_TOKEN="YOUR_TOKEN"
#
AMOOT_API_TOKEN = os.getenv("AMOOT_API_TOKEN", "").strip()

# طبق مستندات واقعی آمو‌ت
AMOOT_SEND_QUICK_OTP_URL = (
    "https://portal.amootsms.com/rest/SendQuickOTP"
)

OTP_LENGTH = 6
OTP_EXPIRE_SECONDS = 120
OTP_RESEND_SECONDS = 30
OTP_MAX_ATTEMPTS = 5


# =========================================================
# حافظه OTP
# =========================================================

otp_store = {}
otp_lock = threading.Lock()


# =========================================================
# پاسخ JSON
# =========================================================

def send_json(handler, status_code, data):
    body = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")

    handler.send_response(status_code)

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Content-Length",
        str(len(body))
    )

    handler.send_header(
        "Access-Control-Allow-Origin",
        "*"
    )

    handler.send_header(
        "Access-Control-Allow-Methods",
        "GET, POST, OPTIONS"
    )

    handler.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type, Authorization"
    )

    handler.end_headers()

    handler.wfile.write(body)


# =========================================================
# خواندن JSON
# =========================================================

def read_json(handler):
    try:
        content_length = int(
            handler.headers.get(
                "Content-Length",
                "0"
            )
        )
    except ValueError:
        return {}

    if content_length <= 0:
        return {}

    try:
        raw = handler.rfile.read(
            content_length
        )

        return json.loads(
            raw.decode("utf-8")
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError
    ):
        return {}


# =========================================================
# شماره موبایل
# =========================================================

def normalize_phone(phone):
    phone = str(
        phone or ""
    ).strip()

    phone = phone.replace(
        " ",
        ""
    )

    phone = phone.replace(
        "-",
        ""
    )

    phone = phone.replace(
        "(",
        ""
    )

    phone = phone.replace(
        ")",
        ""
    )

    # تبدیل اعداد فارسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"

    for persian, english in zip(
        persian_digits,
        english_digits
    ):
        phone = phone.replace(
            persian,
            english
        )

    # +98912...
    if phone.startswith("+98"):
        phone = (
            "0"
            + phone[3:]
        )

    # 98912...
    elif (
        phone.startswith("98")
        and len(phone) == 12
    ):
        phone = (
            "0"
            + phone[2:]
        )

    return phone


def valid_phone(phone):
    return (
        len(phone) == 11
        and phone.startswith("09")
        and phone[2:].isdigit()
    )


# =========================================================
# تبدیل کد به رشته استاندارد
# =========================================================

def normalize_code(code):
    code = str(
        code or ""
    ).strip()

    # تبدیل اعداد فارسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"

    for persian, english in zip(
        persian_digits,
        english_digits
    ):
        code = code.replace(
            persian,
            english
        )

    return code


# =========================================================
# پاکسازی OTP های قدیمی
# =========================================================

def cleanup_expired_otps():
    now = time.time()

    with otp_lock:

        expired_numbers = []

        for phone, item in otp_store.items():

            if item["expires_at"] <= now:

                expired_numbers.append(
                    phone
                )

        for phone in expired_numbers:

            otp_store.pop(
                phone,
                None
            )


# =========================================================
# ارسال OTP واقعی به آمو‌ت
# =========================================================

def send_quick_otp_to_amoot(phone):
    """
    مطابق مستندات واقعی SendQuickOTP:

    POST
    https://portal.amootsms.com/rest/SendQuickOTP

    Header:
    Authorization: MyToken

    Body:
    Mobile
    CodeLength
    OptionalCode
    """

    if not AMOOT_API_TOKEN:

        return False, {
            "message":
                "AMOOT_API_TOKEN تنظیم نشده است."
        }


    # -----------------------------------------------------
    # Body واقعی مطابق مستندات
    # -----------------------------------------------------

    form_data = {
        "Mobile": phone,
        "CodeLength": str(OTP_LENGTH),
        "OptionalCode": ""
    }


    body = urllib.parse.urlencode(
        form_data
    ).encode("utf-8")


    # -----------------------------------------------------
    # ساخت Request
    # -----------------------------------------------------

    request = urllib.request.Request(
        AMOOT_SEND_QUICK_OTP_URL,
        data=body,
        method="POST"
    )


    # -----------------------------------------------------
    # Header واقعی
    #
    # طبق نمونه cURL آمو‌ت:
    #
    # Authorization: MyToken
    #
    # بنابراین Bearer اضافه نمی‌کنیم.
    # -----------------------------------------------------

    request.add_header(
        "Authorization",
        AMOOT_API_TOKEN
    )

    request.add_header(
        "Content-Type",
        "application/x-www-form-urlencoded"
    )

    request.add_header(
        "Accept",
        "application/json"
    )


    print()
    print("=" * 60)
    print("AMOOT SendQuickOTP")
    print("=" * 60)
    print("URL:", AMOOT_SEND_QUICK_OTP_URL)
    print("Mobile:", phone)
    print("CodeLength:", OTP_LENGTH)
    print("OptionalCode: EMPTY")
    print(
        "Token configured:",
        bool(AMOOT_API_TOKEN)
    )
    print("=" * 60)


    # -----------------------------------------------------
    # ارسال Request
    # -----------------------------------------------------

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            status_code = response.status

            raw_response = response.read().decode(
                "utf-8",
                errors="replace"
            )


            # ---------------------------------------------
            # JSON response
            # ---------------------------------------------

            try:

                response_data = json.loads(
                    raw_response
                )

            except json.JSONDecodeError:

                response_data = {
                    "raw": raw_response
                }


            print()
            print("========== AMOOT RESPONSE ==========")
            print(
                "HTTP:",
                status_code
            )
            print(
                "Status:",
                response_data.get(
                    "Status"
                )
            )
            print(
                "MessageID:",
                response_data.get(
                    "Data",
                    {}
                ).get(
                    "MessageID"
                )
            )
            print(
                "CampaignID:",
                response_data.get(
                    "CampaignID"
                )
            )
            print(
                "====================================")
            print()


            if not (
                200
                <= status_code
                < 300
            ):

                return False, {
                    "status_code":
                        status_code,
                    "response":
                        response_data
                }


            # -------------------------------------------------
            # طبق نمونه آمو‌ت:
            #
            # {
            #   "Status": "Success",
            #   "Data": {
            #       "Code": "******"
            #   }
            # }
            # -------------------------------------------------

            if response_data.get(
                "Status"
            ) != "Success":

                return False, {
                    "status_code":
                        status_code,
                    "response":
                        response_data
                }


            data = response_data.get(
                "Data"
            ) or {}


            # کد واقعی تولیدشده توسط آمو‌ت
            amoot_code = normalize_code(
                data.get(
                    "Code",
                    ""
                )
            )


            # در برخی پاسخ‌ها ممکن است
            # Code ماسک شده باشد.
            if (
                not amoot_code
                or "*" in amoot_code
            ):

                return False, {
                    "status_code":
                        status_code,
                    "response":
                        response_data,
                    "reason":
                        (
                            "کد واقعی در پاسخ API "
                            "در دسترس نیست."
                        )
                }


            if not (
                amoot_code.isdigit()
                and len(amoot_code)
                == OTP_LENGTH
            ):

                return False, {
                    "status_code":
                        status_code,
                    "response":
                        response_data,
                    "reason":
                        (
                            "کد دریافتی از API "
                            "6 رقمی نیست."
                        )
                }


            return True, {
                "response":
                    response_data,
                "code":
                    amoot_code
            }


    except urllib.error.HTTPError as error:

        raw_error = error.read().decode(
            "utf-8",
            errors="replace"
        )


        try:

            error_data = json.loads(
                raw_error
            )

        except json.JSONDecodeError:

            error_data = {
                "raw":
                    raw_error
            }


        print()
        print(
            "========== AMOOT HTTP ERROR =========="
        )
        print(
            "HTTP:",
            error.code
        )
        print(
            "Response:",
            error_data
        )
        print(
            "======================================"
        )
        print()


        return False, {
            "status_code":
                error.code,
            "response":
                error_data
        }


    except urllib.error.URLError as error:

        print()
        print(
            "========== AMOOT URL ERROR =========="
        )
        print(
            "Error:",
            str(error.reason)
        )
        print(
            "====================================="
        )
        print()


        return False, {
            "message":
                "اتصال به سرور آمو‌ت برقرار نشد.",
            "error":
                str(error.reason)
        }


    except Exception as error:

        print()
        print(
            "========== AMOOT ERROR =========="
        )
        print(
            "Error:",
            str(error)
        )
        print(
            "================================="
        )
        print()


        return False, {
            "message":
                "خطای داخلی هنگام ارتباط با آمو‌ت.",
            "error":
                str(error)
        }


# =========================================================
# MIME
# =========================================================

def get_content_type(path):

    content_type, _ = mimetypes.guess_type(
        str(path)
    )

    if not content_type:

        content_type = (
            "application/octet-stream"
        )

    return content_type


# =========================================================
# سرو فایل‌های سایت
# =========================================================

def serve_static_file(
    handler,
    relative_path
):

    requested = Path(
        relative_path
    )


    # جلوگیری از Path Traversal
    if (
        ".." in requested.parts
        or requested.is_absolute()
    ):

        return send_json(
            handler,
            403,
            {
                "success":
                    False,
                "message":
                    "دسترسی غیرمجاز."
            }
        )


    file_path = (
        BASE_DIR / requested
    ).resolve()


    try:

        file_path.relative_to(
            BASE_DIR
        )

    except ValueError:

        return send_json(
            handler,
            403,
            {
                "success":
                    False,
                "message":
                    "دسترسی غیرمجاز."
            }
        )


    if not file_path.is_file():

        return send_json(
            handler,
            404,
            {
                "success":
                    False,
                "message":
                    "فایل پیدا نشد."
            }
        )


    try:

        data = file_path.read_bytes()

    except OSError:

        return send_json(
            handler,
            500,
            {
                "success":
                    False,
                "message":
                    "خواندن فایل ناموفق بود."
            }
        )


    content_type = get_content_type(
        file_path
    )


    extension = (
        file_path.suffix.lower()
    )


    if extension == ".html":

        content_type = (
            "text/html; charset=utf-8"
        )

    elif extension == ".css":

        content_type = (
            "text/css; charset=utf-8"
        )

    elif extension == ".js":

        content_type = (
            "application/javascript; "
            "charset=utf-8"
        )

    elif extension == ".json":

        content_type = (
            "application/json; charset=utf-8"
        )


    handler.send_response(200)


    handler.send_header(
        "Content-Type",
        content_type
    )


    handler.send_header(
        "Content-Length",
        str(len(data))
    )


    handler.send_header(
        "Cache-Control",
        "no-cache"
    )


    handler.end_headers()


    handler.wfile.write(
        data
    )


# =========================================================
# HTTP Handler
# =========================================================

class LainoHandler(
    BaseHTTPRequestHandler
):


    def log_message(
        self,
        format_string,
        *args
    ):

        print(
            f"{self.address_string()} - "
            f"{format_string % args}"
        )


    # =====================================================
    # OPTIONS
    # =====================================================

    def do_OPTIONS(self):

        self.send_response(204)

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization"
        )

        self.end_headers()


    # =====================================================
    # GET
    # =====================================================

    def do_GET(self):

        cleanup_expired_otps()

        path = self.path.split(
            "?",
            1
        )[0]


        # -----------------------------------------------
        # Health
        # -----------------------------------------------

        if path == "/health":

            return send_json(
                self,
                200,
                {
                    "status":
                        "ok",

                    "sms_configured":
                        bool(
                            AMOOT_API_TOKEN
                        )
                }
            )


        # -----------------------------------------------
        # API information
        # -----------------------------------------------

        if path == "/api/status":

            return send_json(
                self,
                200,
                {
                    "service":
                        "LainoLive API",

                    "status":
                        "online",

                    "sms_configured":
                        bool(
                            AMOOT_API_TOKEN
                        ),

                    "otp_provider":
                        "AmootSMS",

                    "otp_method":
                        "SendQuickOTP",

                    "webhook":
                        False,

                    "sandbox":
                        False
                }
            )


        # -----------------------------------------------
        # صفحه اصلی
        # -----------------------------------------------

        if path == "/":

            return serve_static_file(
                self,
                "index.html"
            )


        # -----------------------------------------------
        # Favicon
        # -----------------------------------------------

        if path == "/favicon.ico":

            self.send_response(204)

            self.end_headers()

            return


        # -----------------------------------------------
        # فایل‌های استاتیک
        # -----------------------------------------------

        relative_path = path.lstrip("/")


        allowed_extensions = {
            ".html",
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
            ".ico",
            ".json",
            ".mp3",
            ".wav",
            ".mp4",
            ".webm"
        }


        extension = Path(
            relative_path
        ).suffix.lower()


        if extension in allowed_extensions:

            return serve_static_file(
                self,
                relative_path
            )


        return send_json(
            self,
            404,
            {
                "success":
                    False,
                "message":
                    "مسیر پیدا نشد."
            }
        )


    # =====================================================
    # POST
    # =====================================================

    def do_POST(self):

        cleanup_expired_otps()

        path = self.path.split(
            "?",
            1
        )[0]


        if path == "/api/request-code":

            return self.request_code()


        if path == "/api/verify-code":

            return self.verify_code()


        return send_json(
            self,
            404,
            {
                "success":
                    False,
                "message":
                    "مسیر پیدا نشد."
            }
        )


    # =====================================================
    # Request OTP
    # =====================================================

    def request_code(self):

        data = read_json(
            self
        )


        phone = normalize_phone(
            data.get(
                "phone"
            )
        )


        if not valid_phone(
            phone
        ):

            return send_json(
                self,
                400,
                {
                    "success":
                        False,
                    "message":
                        "شماره موبایل نامعتبر است."
                }
            )


        if not AMOOT_API_TOKEN:

            return send_json(
                self,
                500,
                {
                    "success":
                        False,
                    "message":
                        "AMOOT_API_TOKEN تنظیم نشده است."
                }
            )


        now = time.time()


        # -------------------------------------------------
        # محدودیت ارسال مجدد
        # -------------------------------------------------

        with otp_lock:

            previous = otp_store.get(
                phone
            )


            if previous:

                remaining = int(
                    previous[
                        "resend_available_at"
                    ] - now
                )


                if remaining > 0:

                    return send_json(
                        self,
                        429,
                        {
                            "success":
                                False,
                            "message":
                                (
                                    f"لطفاً {remaining} "
                                    "ثانیه صبر کنید."
                                ),
                            "retry_after":
                                remaining
                        }
                    )


        # -------------------------------------------------
        # درخواست OTP از آمو‌ت
        # -------------------------------------------------

        success, result = (
            send_quick_otp_to_amoot(
                phone
            )
        )


        if not success:

            return send_json(
                self,
                502,
                {
                    "success":
                        False,
                    "message":
                        (
                            "ارسال کد از طریق "
                            "آمو‌ت ناموفق بود."
                        ),
                    "details":
                        result
                }
            )


        # -------------------------------------------------
        # کد واقعی آمو‌ت
        # -------------------------------------------------

        amoot_code = normalize_code(
            result.get(
                "code",
                ""
            )
        )


        if not (
            amoot_code.isdigit()
            and len(amoot_code)
            == OTP_LENGTH
        ):

            return send_json(
                self,
                502,
                {
                    "success":
                        False,
                    "message":
                        (
                            "کد معتبر از پاسخ آمو‌ت "
                            "دریافت نشد."
                        )
                }
            )


        # -------------------------------------------------
        # ذخیره روی سرور
        # -------------------------------------------------

        with otp_lock:

            otp_store[phone] = {

                "code":
                    amoot_code,

                "created_at":
                    now,

                "expires_at":
                    now
                    + OTP_EXPIRE_SECONDS,

                "resend_available_at":
                    now
                    + OTP_RESEND_SECONDS,

                "attempts":
                    0
            }


        # -------------------------------------------------
        # لاگ تست
        # -------------------------------------------------

        print()
        print(
            "========== OTP SAVED =========="
        )
        print(
            "Phone:",
            phone
        )
        print(
            "Code:",
            amoot_code
        )
        print(
            "Expires:",
            OTP_EXPIRE_SECONDS,
            "seconds"
        )
        print(
            "==============================="
        )
        print()


        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "message":
                    "کد تأیید ارسال شد.",

                "expires_in":
                    OTP_EXPIRE_SECONDS
            }
        )


    # =====================================================
    # Verify OTP
    # =====================================================

    def verify_code(self):

        data = read_json(
            self
        )


        phone = normalize_phone(
            data.get(
                "phone"
            )
        )


        entered_code = normalize_code(
            data.get(
                "code",
                ""
            )
        )


        print()
        print(
            "========== OTP VERIFY =========="
        )
        print(
            "Phone:",
            phone
        )
        print(
            "Entered code:",
            entered_code
        )


        # -------------------------------------------------
        # شماره
        # -------------------------------------------------

        if not valid_phone(
            phone
        ):

            print(
                "Result: INVALID PHONE"
            )
            print(
                "================================"
            )
            print()

            return send_json(
                self,
                400,
                {
                    "success":
                        False,
                    "message":
                        "شماره موبایل نامعتبر است."
                }
            )


        # -------------------------------------------------
        # کد
        # -------------------------------------------------

        if (
            not entered_code.isdigit()
            or len(entered_code)
            != OTP_LENGTH
        ):

            print(
                "Result: INVALID CODE"
            )
            print(
                "================================"
            )
            print()

            return send_json(
                self,
                400,
                {
                    "success":
                        False,
                    "message":
                        "کد تأیید باید 6 رقمی باشد."
                }
            )


        # -------------------------------------------------
        # دریافت رکورد
        # -------------------------------------------------

        with otp_lock:

            record = otp_store.get(
                phone
            )


            if not record:

                print(
                    "Saved code: NOT FOUND"
                )
                print(
                    "Result: CODE NOT FOUND"
                )
                print(
                    "================================"
                )
                print()

                return send_json(
                    self,
                    400,
                    {
                        "success":
                            False,
                        "message":
                            (
                                "کد منقضی شده "
                                "یا وجود ندارد."
                            )
                    }
                )


            saved_code = normalize_code(
                record.get(
                    "code",
                    ""
                )
            )


            print(
                "Saved code:",
                saved_code
            )


            # ---------------------------------------------
            # انقضا
            # ---------------------------------------------

            if (
                record["expires_at"]
                <= time.time()
            ):

                otp_store.pop(
                    phone,
                    None
                )


                print(
                    "Result: EXPIRED"
                )
                print(
                    "================================"
                )
                print()


                return send_json(
                    self,
                    400,
                    {
                        "success":
                            False,
                        "message":
                            "کد منقضی شده است."
                    }
                )


            # ---------------------------------------------
            # تلاش
            # ---------------------------------------------

            record["attempts"] += 1


            if (
                record["attempts"]
                > OTP_MAX_ATTEMPTS
            ):

                otp_store.pop(
                    phone,
                    None
                )


                print(
                    "Result: TOO MANY ATTEMPTS"
                )
                print(
                    "================================"
                )
                print()


                return send_json(
                    self,
                    429,
                    {
                        "success":
                            False,
                        "message":
                            (
                                "تعداد تلاش‌ها "
                                "بیش از حد مجاز است."
                            )
                    }
                )


            # ---------------------------------------------
            # مقایسه امن
            # ---------------------------------------------

            correct = secrets.compare_digest(
                saved_code,
                entered_code
            )


            if correct:

                otp_store.pop(
                    phone,
                    None
                )


                print(
                    "Result: SUCCESS"
                )
                print(
                    "================================"
                )
                print()


                return send_json(
                    self,
                    200,
                    {
                        "success":
                            True,

                        "message":
                            (
                                "ورود با موفقیت "
                                "انجام شد."
                            ),

                        "phone":
                            phone
                    }
                )


            print(
                "Result: WRONG CODE"
            )
            print(
                "================================"
            )
            print()


        return send_json(
            self,
            400,
            {
                "success":
                    False,
                "message":
                    "کد واردشده صحیح نیست."
            }
        )


# =========================================================
# اجرای سرور
# =========================================================

def main():

    cleanup_expired_otps()


    server = ThreadingHTTPServer(
        (
            HOST,
            PORT
        ),
        LainoHandler
    )


    print("=" * 60)
    print("LainoLive API")
    print("=" * 60)

    print(
        f"Home:   http://127.0.0.1:{PORT}/"
    )

    print(
        f"Login:  http://127.0.0.1:{PORT}/login.html"
    )

    print(
        f"Live:   http://127.0.0.1:{PORT}/live.html"
    )

    print(
        f"Health: http://127.0.0.1:{PORT}/health"
    )

    print(
        f"Status: http://127.0.0.1:{PORT}/api/status"
    )

    print(
        "SMS configured:",
        bool(AMOOT_API_TOKEN)
    )

    print(
        "Webhook:",
        False
    )

    print(
        "Sandbox:",
        False
    )

    print(
        "=" * 60
    )


    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print(
            "LainoLive stopped."
        )

    finally:

        server.server_close()


if __name__ == "__main__":

    main()
