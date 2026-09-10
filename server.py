import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# =========================================================
# تنظیمات
# =========================================================

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

BASE_DIR = Path(__file__).resolve().parent

# این مقدار را فقط در Environment Variable قرار بده
AMOOT_API_TOKEN = os.getenv(
    "AMOOT_API_TOKEN",
    ""
).strip()

# آدرس‌های واقعی آمو‌ت
AMOOT_SEND_QUICK_OTP_URL = (
    "https://portal.amootsms.com/rest/SendQuickOTP"
)

AMOOT_SEND_SIMPLE_URL = (
    "https://portal.amootsms.com/rest/SendSimple"
)

# تنظیمات OTP
OTP_LENGTH = 6
OTP_EXPIRE_SECONDS = 120
OTP_RESEND_SECONDS = 30
OTP_MAX_ATTEMPTS = 5


# =========================================================
# حافظه موقت OTP
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


def amoot_mobile(phone):
    """
    طبق نمونه رسمی SendSimple:
    09120000000
    تبدیل می‌شود به:
    9120000000
    """

    phone = normalize_phone(phone)

    if phone.startswith("0"):
        return phone[1:]

    return phone


# =========================================================
# تبدیل کد
# =========================================================

def normalize_code(code):
    code = str(
        code or ""
    ).strip()

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
# پاکسازی OTP
# =========================================================

def cleanup_expired_otps():
    now = time.time()

    with otp_lock:
        expired = [
            phone
            for phone, item in otp_store.items()
            if item["expires_at"] <= now
        ]

        for phone in expired:
            otp_store.pop(
                phone,
                None
            )


# =========================================================
# درخواست POST فرم به آمو‌ت
# =========================================================

def amoot_post_form(
    url,
    form_data
):
    if not AMOOT_API_TOKEN:
        return False, {
            "message":
                "AMOOT_API_TOKEN تنظیم نشده است."
        }

    body = urllib.parse.urlencode(
        form_data
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method="POST"
    )

    # طبق نمونه رسمی آمو‌ت
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

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            status_code = response.status

            raw = response.read().decode(
                "utf-8",
                errors="replace"
            )

            try:
                response_data = json.loads(
                    raw
                )
            except json.JSONDecodeError:
                response_data = {
                    "raw": raw
                }

            return True, {
                "status_code":
                    status_code,
                "data":
                    response_data
            }

    except urllib.error.HTTPError as error:

        raw = error.read().decode(
            "utf-8",
            errors="replace"
        )

        try:
            response_data = json.loads(
                raw
            )
        except json.JSONDecodeError:
            response_data = {
                "raw": raw
            }

        return False, {
            "status_code":
                error.code,
            "data":
                response_data
        }

    except urllib.error.URLError as error:

        return False, {
            "message":
                "اتصال به سرور آمو‌ت برقرار نشد.",
            "error":
                str(error.reason)
        }

    except Exception as error:

        return False, {
            "message":
                "خطای داخلی هنگام ارتباط با آمو‌ت.",
            "error":
                str(error)
        }


# =========================================================
# SendQuickOTP
# =========================================================

def send_quick_otp(phone):

    form_data = {
        "Mobile":
            phone,

        "CodeLength":
            str(OTP_LENGTH),

        # خالی؛ آمو‌ت خودش کد تولید می‌کند
        "OptionalCode":
            ""
    }

    print()
    print("=" * 60)
    print("AMOOT SendQuickOTP")
    print("=" * 60)
    print("Mobile:", phone)
    print("CodeLength:", OTP_LENGTH)
    print("OptionalCode: EMPTY")
    print("=" * 60)

    success, result = amoot_post_form(
        AMOOT_SEND_QUICK_OTP_URL,
        form_data
    )

    if not success:
        print("OTP request failed:")
        print(result)
        return False, result

    response_data = result.get(
        "data"
    ) or {}

    print("HTTP:", result.get(
        "status_code"
    ))

    print("Status:", response_data.get(
        "Status"
    ))

    print("CampaignID:", response_data.get(
        "CampaignID"
    ))

    if response_data.get(
        "Status"
    ) != "Success":

        return False, {
            "response":
                response_data
        }

    data = response_data.get(
        "Data"
    ) or {}

    amoot_code = normalize_code(
        data.get(
            "Code",
            ""
        )
    )

    # پاسخ ماسک‌شده قابل استفاده برای تایید نیست
    if (
        not amoot_code
        or "*" in amoot_code
    ):

        return False, {
            "response":
                response_data,

            "reason":
                (
                    "آمو‌ت کد واقعی را "
                    "در پاسخ API برنگردانده است."
                )
        }

    if not (
        amoot_code.isdigit()
        and len(amoot_code) == OTP_LENGTH
    ):

        return False, {
            "response":
                response_data,

            "reason":
                "کد OTP معتبر نیست."
        }

    return True, {
        "code":
            amoot_code,

        "response":
            response_data
    }


# =========================================================
# SendSimple
# =========================================================

def send_simple_sms(
    phone,
    message
):
    """
    SendSimple طبق نمونه رسمی:

    Authorization: MyToken

    Body:
    SendDateTime
    SMSMessageText
    LineNumber
    Mobiles
    """

    mobile = amoot_mobile(
        phone
    )

    send_datetime = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    form_data = {
        "SendDateTime":
            send_datetime,

        "SMSMessageText":
            message,

        "LineNumber":
            "public",

        "Mobiles":
            mobile
    }

    print()
    print("=" * 60)
    print("AMOOT SendSimple")
    print("=" * 60)
    print("SendDateTime:", send_datetime)
    print("Mobile:", mobile)
    print("LineNumber:", "public")
    print("Message:", message)
    print("=" * 60)

    success, result = amoot_post_form(
        AMOOT_SEND_SIMPLE_URL,
        form_data
    )

    if not success:
        print("SMS request failed:")
        print(result)
        return False, result

    response_data = result.get(
        "data"
    ) or {}

    print("HTTP:", result.get(
        "status_code"
    ))

    print("Status:", response_data.get(
        "Status"
    ))

    print("CampaignID:", response_data.get(
        "CampaignID"
    ))

    print("Price:", response_data.get(
        "Price"
    ))

    if response_data.get(
        "Status"
    ) != "Success":

        return False, {
            "response":
                response_data
        }

    return True, {
        "response":
            response_data
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

    # جلوگیری از ../
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

    handler.send_response(
        200
    )

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

        self.send_response(
            204
        )

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


        # -------------------------------------------------
        # Health
        # -------------------------------------------------

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


        # -------------------------------------------------
        # API status
        # -------------------------------------------------

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

                    "otp_method":
                        "SendQuickOTP",

                    "normal_sms_method":
                        "SendSimple",

                    "webhook":
                        False,

                    "sandbox":
                        False
                }
            )


        # -------------------------------------------------
        # Home
        # -------------------------------------------------

        if path == "/":

            return serve_static_file(
                self,
                "index.html"
            )


        # -------------------------------------------------
        # favicon
        # -------------------------------------------------

        if path == "/favicon.ico":

            self.send_response(
                204
            )

            self.end_headers()

            return


        # -------------------------------------------------
        # فایل استاتیک
        # -------------------------------------------------

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


        if path == "/api/send-message":

            return self.send_message()


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
        # ارسال OTP
        # -------------------------------------------------

        success, result = (
            send_quick_otp(
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


        amoot_code = normalize_code(
            result.get(
                "code"
            )
        )


        # -------------------------------------------------
        # ذخیره OTP
        # -------------------------------------------------

        with otp_lock:

            otp_store[
                phone
            ] = {

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


        if (
            not entered_code.isdigit()
            or len(entered_code)
            != OTP_LENGTH
        ):

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


        with otp_lock:

            record = otp_store.get(
                phone
            )


            if not record:

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


            if (
                record[
                    "expires_at"
                ]
                <= time.time()
            ):

                otp_store.pop(
                    phone,
                    None
                )

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


            record[
                "attempts"
            ] += 1


            if (
                record[
                    "attempts"
                ]
                > OTP_MAX_ATTEMPTS
            ):

                otp_store.pop(
                    phone,
                    None
                )

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


            saved_code = normalize_code(
                record.get(
                    "code",
                    ""
                )
            )


            if secrets.compare_digest(
                saved_code,
                entered_code
            ):

                otp_store.pop(
                    phone,
                    None
                )

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


    # =====================================================
    # Send normal SMS
    # =====================================================

    def send_message(self):

        data = read_json(
            self
        )


        phone = normalize_phone(
            data.get(
                "phone"
            )
        )


        message = str(
            data.get(
                "message",
                ""
            )
        ).strip()


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


        if not message:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "متن پیام خالی است."
                }
            )


        if len(message) > 1000:

            return send_json(
                self,
                400,
                {
                    "success":
                        False,

                    "message":
                        "متن پیام بیش از حد طولانی است."
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


        success, result = (
            send_simple_sms(
                phone,
                message
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
                        "ارسال پیامک ناموفق بود.",

                    "details":
                        result
                }
            )


        response_data = (
            result.get(
                "response"
            )
            or {}
        )


        return send_json(
            self,
            200,
            {
                "success":
                    True,

                "message":
                    "پیامک ارسال شد.",

                "campaign_id":
                    response_data.get(
                        "CampaignID"
                    ),

                "price":
                    response_data.get(
                        "Price"
                    )
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
    print("LainoLive")
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
        "OTP:",
        "SendQuickOTP"
    )

    print(
        "Normal SMS:",
        "SendSimple"
    )

    print(
        "Webhook:",
        False
    )

    print(
        "Sandbox:",
        False
    )

    print("=" * 60)


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
