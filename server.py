import hashlib
import hmac
import json
import mimetypes
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))
BASE_DIR = Path(__file__).resolve().parent

# =========================================================
# حساب پیش‌فرض
# =========================================================
DEFAULT_USERNAME = os.getenv("LAINO_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("LAINO_PASSWORD", "123456")

# رمز را فقط به صورت هش‌شده نگه می‌داریم
PASSWORD_SALT = os.getenv(
    "LAINO_PASSWORD_SALT",
    "lainolive-default-salt"
)

PASSWORD_HASH = hashlib.sha256(
    (PASSWORD_SALT + DEFAULT_PASSWORD).encode("utf-8")
).hexdigest()


# =========================================================
# JSON
# =========================================================
def send_json(handler, status_code, data):
    body = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
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
        "Content-Type"
    )

    handler.end_headers()

    handler.wfile.write(body)


# =========================================================
# JSON REQUEST
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
        raw = handler.rfile.read(content_length)

        return json.loads(
            raw.decode("utf-8")
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError
    ):
        return {}


# =========================================================
# STATIC FILES
# =========================================================
def get_content_type(path):
    content_type, _ = mimetypes.guess_type(
        str(path)
    )

    if not content_type:
        content_type = "application/octet-stream"

    return content_type


def serve_static_file(handler, relative_path):
    requested = Path(relative_path)

    if (
        ".." in requested.parts
        or requested.is_absolute()
    ):
        return send_json(
            handler,
            403,
            {
                "success": False,
                "message": "دسترسی غیرمجاز."
            }
        )

    file_path = (
        BASE_DIR / requested
    ).resolve()

    try:
        file_path.relative_to(BASE_DIR)
    except ValueError:
        return send_json(
            handler,
            403,
            {
                "success": False,
                "message": "دسترسی غیرمجاز."
            }
        )

    if not file_path.is_file():
        return send_json(
            handler,
            404,
            {
                "success": False,
                "message": "فایل پیدا نشد."
            }
        )

    try:
        data = file_path.read_bytes()
    except OSError:
        return send_json(
            handler,
            500,
            {
                "success": False,
                "message": "خواندن فایل ناموفق بود."
            }
        )

    content_type = get_content_type(file_path)

    extension = file_path.suffix.lower()

    if extension == ".html":
        content_type = "text/html; charset=utf-8"

    elif extension == ".css":
        content_type = "text/css; charset=utf-8"

    elif extension == ".js":
        content_type = "application/javascript; charset=utf-8"

    elif extension == ".json":
        content_type = "application/json; charset=utf-8"

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

    handler.wfile.write(data)


# =========================================================
# LOGIN CHECK
# =========================================================
def verify_login(username, password):
    username = str(username or "").strip()
    password = str(password or "")

    if username != DEFAULT_USERNAME:
        return False

    entered_hash = hashlib.sha256(
        (PASSWORD_SALT + password).encode("utf-8")
    ).hexdigest()

    return hmac.compare_digest(
        entered_hash,
        PASSWORD_HASH
    )


# =========================================================
# HTTP HANDLER
# =========================================================
class LainoHandler(BaseHTTPRequestHandler):

    def log_message(self, format_string, *args):
        print(
            f"{self.address_string()} - "
            f"{format_string % args}"
        )

    # -----------------------------------------------------
    # OPTIONS
    # -----------------------------------------------------
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
            "Content-Type"
        )

        self.end_headers()

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------
    def do_GET(self):
        path = self.path.split("?", 1)[0]

        # Health
        if path == "/health":
            return send_json(
                self,
                200,
                {
                    "status": "ok",
                    "service": "LainoLive",
                    "login_method": "username_password"
                }
            )

        # API status
        if path == "/api/status":
            return send_json(
                self,
                200,
                {
                    "service": "LainoLive API",
                    "status": "online",
                    "login_method": "username_password",
                    "sms": False,
                    "otp": False
                }
            )

        # Home
        if path == "/":
            return serve_static_file(
                self,
                "index.html"
            )

        # Favicon
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

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
                "success": False,
                "message": "مسیر پیدا نشد."
            }
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------
    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/login":
            return self.login()

        return send_json(
            self,
            404,
            {
                "success": False,
                "message": "مسیر پیدا نشد."
            }
        )

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------
    def login(self):
        data = read_json(self)

        username = str(
            data.get("username", "")
        ).strip()

        password = str(
            data.get("password", "")
        )

        if not username:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": "نام کاربری را وارد کنید."
                }
            )

        if not password:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": "رمز عبور را وارد کنید."
                }
            )

        if len(username) > 100:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": "نام کاربری نامعتبر است."
                }
            )

        if len(password) > 200:
            return send_json(
                self,
                400,
                {
                    "success": False,
                    "message": "رمز عبور نامعتبر است."
                }
            )

        if not verify_login(
            username,
            password
        ):
            return send_json(
                self,
                401,
                {
                    "success": False,
                    "message": (
                        "نام کاربری یا رمز عبور اشتباه است."
                    )
                }
            )

        return send_json(
            self,
            200,
            {
                "success": True,
                "message": "ورود با موفقیت انجام شد.",
                "username": username
            }
        )


# =========================================================
# MAIN
# =========================================================
def main():
    server = ThreadingHTTPServer(
        (HOST, PORT),
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
        f"Health: http://127.0.0.1:{PORT}/health"
    )

    print(
        f"Status: http://127.0.0.1:{PORT}/api/status"
    )

    print(
        "Login method: username + password"
    )

    print(
        "Username:",
        DEFAULT_USERNAME
    )

    print(
        "SMS:",
        False
    )

    print(
        "OTP:",
        False
    )

    print("=" * 60)

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print()
        print("LainoLive stopped.")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
