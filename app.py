"""
SokoSense business website - Flask backend.

Run locally:
    pip install -r requirements.txt
    cp .env.example .env      (then fill in your own values in .env)
    python app.py
Open http://127.0.0.1:5000

- Every page has its own URL (/, /about, /solution, /awards, /events, /team, /contact).
- All website text lives in data/content.json.
- All settings and passwords live in the .env file (never in this code).
- Contact messages are saved to the database AND emailed to the company inbox.
- News and yearly reports are managed by admins at /admin (login required).
"""

import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import uuid
from datetime import date, datetime
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # reads settings from the .env file


# ---------- Settings (all read from .env, nothing hardcoded) ----------

def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


CONTENT_FILE = BASE_DIR / "data" / "content.json"
DB_FILE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "data" / "messages.db"))

MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
MAIL_PORT = int(os.environ.get("MAIL_PORT", "465"))
MAIL_USE_SSL = env_bool("MAIL_USE_SSL", MAIL_PORT == 465)   # port 465 uses SSL
MAIL_USE_TLS = env_bool("MAIL_USE_TLS", MAIL_PORT == 587)   # port 587 uses STARTTLS
MAIL_USE_AUTH = env_bool("MAIL_USE_AUTH", True)             # false for GoDaddy's relay (no login)
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
MAIL_TO = os.environ.get("MAIL_TO", MAIL_USERNAME)          # can be several, separated by commas
MAIL_SENDER_NAME = os.environ.get("MAIL_SENDER_NAME", "Website contact form")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
DEBUG = env_bool("FLASK_DEBUG", False)

# Uploaded reports and news images are stored here (outside the code folders)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_PATH", BASE_DIR / "data" / "uploads"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
REPORT_TYPES = {".pdf"}
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}

EMAIL_ENABLED = all([MAIL_SERVER, MAIL_USERNAME, MAIL_TO]) and (MAIL_PASSWORD or not MAIL_USE_AUTH)
ADMIN_ENABLED = all([ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY])

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY or secrets.token_hex(32),  # only used for admin login sessions
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=env_bool("SECURE_COOKIES", False),  # set true on the live https website
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Menu items: (url, label), in the order shown in the navigation bar.
NAV = [
    ("/", "Home"),
    ("/about", "About"),
    ("/solution", "Solution"),
    ("/awards", "Awards"),
    ("/events", "Events"),
    ("/team", "Team"),
    ("/publications", "Publications"),
]

# Page name -> (template, page title)
PAGES = {
    "about": ("about.html", "About us"),
    "solution": ("solution.html", "Our solution"),
    "awards": ("awards.html", "Awards and recognition"),
    "events": ("events.html", "Events"),
    "team": ("team.html", "Our team"),
    "contact": ("contact.html", "Contact us"),
}


# ---------- Helpers ----------

def load_content():
    """Read site content from JSON (re-read each request so edits show instantly)."""
    with open(CONTENT_FILE, encoding="utf-8") as f:
        return json.load(f)


def init_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                business TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                email_status TEXT DEFAULT 'pending'
            )"""
        )
        # Older databases (from earlier versions) do not have email_status: add it.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(messages)")]
        if "email_status" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN email_status TEXT DEFAULT 'pending'")

        # Publications: news articles and yearly reports
        conn.execute(
            """CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                body TEXT NOT NULL,
                image TEXT,
                published_on TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        news_columns = [row[1] for row in conn.execute("PRAGMA table_info(news)")]
        if "pdf" not in news_columns:
            conn.execute("ALTER TABLE news ADD COLUMN pdf TEXT")
        if "pdf_size" not in news_columns:
            conn.execute("ALTER TABLE news ADD COLUMN pdf_size INTEGER")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                description TEXT,
                filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
    for folder in ("reports", "news"):
        (UPLOAD_DIR / folder).mkdir(parents=True, exist_ok=True)


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def one_line(text):
    """Remove line breaks so text is safe to use in an email subject."""
    return " ".join(str(text).split())


def set_email_status(message_id, status):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE messages SET email_status = ? WHERE id = ?", (status, message_id))


def send_notification(message_id, name, email, business, message, sent_at):
    """Email a new contact message to the company inbox, then record whether it worked."""
    if not EMAIL_ENABLED:
        set_email_status(message_id, "not configured")
        return

    msg = EmailMessage()
    msg["Subject"] = f"New website message from {one_line(name)}"
    msg["From"] = f"{MAIL_SENDER_NAME} <{MAIL_USERNAME}>"
    msg["To"] = MAIL_TO
    msg["Reply-To"] = email  # pressing Reply answers the client directly
    msg.set_content(
        f"You have a new message from the website contact form.\n\n"
        f"Name:      {name}\n"
        f"Email:     {email}\n"
        f"Business:  {business or '-'}\n"
        f"Sent at:   {sent_at}\n"
        f"Reference: #{message_id}\n\n"
        f"Message:\n{message}\n\n"
        f"Reply to this email to answer {name} directly."
    )

    try:
        if MAIL_USE_SSL:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=20)
        else:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20)
            if MAIL_USE_TLS:
                server.starttls()
        with server:
            if MAIL_USE_AUTH:
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
        set_email_status(message_id, "sent")
    except Exception as e:  # message is already safe in the database
        app.logger.error("Email for message #%s failed: %s", message_id, e)
        set_email_status(message_id, f"failed: {one_line(e)[:200]}")


def admin_required(view):
    """Only logged-in admins can open these pages. If admin is not set up in .env, they do not exist."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not ADMIN_ENABLED:
            abort(404)
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        if request.method == "POST" and not hmac.compare_digest(
            request.form.get("csrf_token", ""), session.get("csrf_token", "")
        ):
            abort(400)  # blocks forged form submissions from other websites
        return view(*args, **kwargs)
    return wrapper


def save_upload(file, folder, allowed):
    """Save an uploaded file with a safe random name. Returns (filename, size) or raises ValueError."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise ValueError(f"This file type is not allowed. Use: {', '.join(sorted(allowed))}")
    name = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / folder / name
    file.save(path)
    return name, path.stat().st_size


def delete_upload(folder, name):
    if name:
        (UPLOAD_DIR / folder / name).unlink(missing_ok=True)


def valid_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_globals():
    """Values every template can use (menu, company info, current year)."""
    if ADMIN_ENABLED and "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return {
        "nav": NAV,
        "company": load_content()["company"],
        "year": datetime.now().year,
        "current_path": request.path,
        "csrf_token": session.get("csrf_token", ""),
        "is_admin": bool(session.get("admin")),
    }


@app.after_request
def security_headers(response):
    """Small safety settings sent with every page."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.path.startswith("/admin"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"  # never list admin pages in Google
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/robots.txt")
def robots_txt():
    body = f"User-agent: *\nDisallow: /admin\n"
    return app.response_class(body, mimetype="text/plain")


@app.template_filter("nice_date")
def nice_date(iso):
    """2026-09-26 -> 26 September 2026"""
    try:
        d = date.fromisoformat(iso[:10])
        return f"{d.day} {d.strftime('%B %Y')}"
    except (TypeError, ValueError):
        return iso


@app.template_filter("file_size")
def file_size(num):
    return f"{num / 1024:.0f} KB" if num < 1024 * 1024 else f"{num / (1024 * 1024):.1f} MB"


@app.template_filter("paragraphs")
def paragraphs(text):
    """Split text on blank lines so the admin can write normal paragraphs."""
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


# ---------- Pages ----------

@app.route("/")
def home():
    return render_template("home.html", c=load_content(), page_title=None)


@app.route("/<page>")
def page(page):
    if page not in PAGES:
        abort(404)
    template, title = PAGES[page]
    return render_template(template, c=load_content(), page_title=title)


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html", page_title="Page not found"), 404


# ---------- JSON API (used by static/js/main.js) ----------

@app.route("/api/awards")
def api_awards():
    return jsonify(sorted(load_content()["awards"], key=lambda a: a["year"], reverse=True))


@app.route("/api/events")
def api_events():
    events = load_content()["events"]
    year = request.args.get("year")
    if year:
        events = [e for e in events if str(e["year"]) == year]
    events = sorted(events, key=lambda e: (e["year"], e.get("date") or ""), reverse=True)
    return jsonify(events)


@app.route("/api/team")
def api_team():
    return jsonify(load_content()["team"])


@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json(silent=True) or {}

    # Spam trap: real visitors never see or fill the hidden "website" field.
    if (data.get("website") or "").strip():
        return jsonify({"ok": True, "message": "Thanks, your message was sent."})

    name = (data.get("name") or "").strip()[:100]
    email = (data.get("email") or "").strip()[:200]
    business = (data.get("business") or "").strip()[:150]
    message = (data.get("message") or "").strip()[:5000]

    errors = {}
    if len(name) < 2:
        errors["name"] = "Enter your name."
    if not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address, like name@example.com."
    if len(message) < 10:
        errors["message"] = "Write a message of at least 10 characters."
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # 1. Save to the database first, so the message is never lost.
    sent_at = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute(
            "INSERT INTO messages (name, email, business, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, business, message, sent_at),
        )
        message_id = cur.lastrowid

    # 2. Email the team in the background, so the visitor does not wait.
    threading.Thread(
        target=send_notification,
        args=(message_id, name, email, business, message, sent_at),
        daemon=True,
    ).start()

    first = name.split()[0]
    return jsonify({"ok": True, "message": f"Thanks {first}, your message was sent. We will reply by email."})


# ---------- Publications (public) ----------

@app.route("/publications")
def publications():
    tab = request.args.get("tab", "news")
    if tab not in ("news", "reports"):
        tab = "news"
    with db() as conn:
        news = conn.execute("SELECT * FROM news ORDER BY published_on DESC, id DESC").fetchall()
        reports = conn.execute("SELECT * FROM reports ORDER BY year DESC, id DESC").fetchall()
    return render_template("publications.html", c=load_content(), page_title="Publications",
                           tab=tab, news=news, reports=reports)


@app.route("/publications/news/<int:news_id>")
def news_article(news_id):
    with db() as conn:
        item = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
    if not item:
        abort(404)
    return render_template("news_article.html", c=load_content(), page_title="Publications",
                           item=item, current_path="/publications")


def pdf_name(title):
    """A readable file name for downloads, e.g. SokoSense-Annual-Report-2025.pdf"""
    return re.sub(r"[^A-Za-z0-9]+", "-", f"SokoSense {title}").strip("-")[:80] + ".pdf"


def wants_download():
    return request.args.get("download") == "1"


@app.route("/publications/reports/<int:report_id>")
def report_view(report_id):
    with db() as conn:
        r = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not r:
        abort(404)
    return render_template("report_view.html", c=load_content(), page_title="Publications",
                           item=r, current_path="/publications")


@app.route("/publications/reports/<int:report_id>/download")
def report_download(report_id):
    """The report PDF. Opens in the browser, or downloads with ?download=1"""
    with db() as conn:
        r = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not r:
        abort(404)
    return send_from_directory(UPLOAD_DIR / "reports", r["filename"],
                               as_attachment=wants_download(), download_name=pdf_name(r["title"]))


@app.route("/publications/news/<int:news_id>/pdf")
def news_pdf(news_id):
    with db() as conn:
        item = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
    if not item or not item["pdf"]:
        abort(404)
    return send_from_directory(UPLOAD_DIR / "news", item["pdf"],
                               as_attachment=wants_download(), download_name=pdf_name(item["title"]))


@app.route("/uploads/news/<path:filename>")
def news_image(filename):
    return send_from_directory(UPLOAD_DIR / "news", filename)


# ---------- Admin area (login required) ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not ADMIN_ENABLED:
        abort(404)
    error = None
    if request.method == "POST":
        ok_user = hmac.compare_digest(request.form.get("username", ""), ADMIN_USERNAME)
        ok_pass = hmac.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD)
        if ok_user and ok_pass:
            session.clear()
            session["admin"] = True
            session["csrf_token"] = secrets.token_hex(16)
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/admin") else url_for("admin_dashboard"))
        error = "Wrong username or password."
    return render_template("admin/login.html", page_title="Admin login", error=error)


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    tab = request.args.get("tab", "news")
    with db() as conn:
        news = conn.execute("SELECT * FROM news ORDER BY published_on DESC, id DESC").fetchall()
        reports = conn.execute("SELECT * FROM reports ORDER BY year DESC, id DESC").fetchall()
        messages = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 200").fetchall()
    return render_template("admin/dashboard.html", page_title="Admin", tab=tab,
                           news=news, reports=reports, messages=messages)


# --- News ---

@app.route("/admin/news/new", methods=["GET", "POST"])
@app.route("/admin/news/<int:news_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_news_form(news_id=None):
    item = None
    if news_id:
        with db() as conn:
            item = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
        if not item:
            abort(404)

    form = dict(item) if item else {"published_on": date.today().isoformat()}
    errors = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("title", "summary", "body", "published_on")}
        if not form["title"]:
            errors["title"] = "Enter a title."
        if not form["summary"]:
            errors["summary"] = "Write a short summary (1-2 sentences)."
        if not valid_date(form["published_on"]):
            errors["published_on"] = "Choose a date."

        image = item["image"] if item else None
        pdf, pdf_size = (item["pdf"], item["pdf_size"]) if item else (None, None)
        image_upload = request.files.get("image")
        pdf_upload = request.files.get("pdf")
        remove_pdf = bool(request.form.get("remove_pdf"))
        has_new_pdf = bool(pdf_upload and pdf_upload.filename)

        # The article needs written text, a PDF, or both
        will_have_pdf = has_new_pdf or (pdf and not remove_pdf)
        if not form["body"] and not will_have_pdf:
            errors["body"] = "Write the article, or attach it as a PDF below."

        if not errors and image_upload and image_upload.filename:
            try:
                new_image, _ = save_upload(image_upload, "news", IMAGE_TYPES)
                if item:
                    delete_upload("news", item["image"])
                image = new_image
            except ValueError as e:
                errors["image"] = str(e)
        if not errors and request.form.get("remove_image") and item:
            delete_upload("news", item["image"])
            image = None

        if not errors and has_new_pdf:
            try:
                new_pdf, new_size = save_upload(pdf_upload, "news", REPORT_TYPES)
                if item:
                    delete_upload("news", item["pdf"])
                pdf, pdf_size = new_pdf, new_size
            except ValueError as e:
                errors["pdf"] = str(e)
        elif not errors and remove_pdf and item:
            delete_upload("news", item["pdf"])
            pdf, pdf_size = None, None

        if not errors:
            with db() as conn:
                if item:
                    conn.execute(
                        "UPDATE news SET title=?, summary=?, body=?, image=?, pdf=?, pdf_size=?, published_on=? WHERE id=?",
                        (form["title"], form["summary"], form["body"], image, pdf, pdf_size,
                         form["published_on"], news_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO news (title, summary, body, image, pdf, pdf_size, published_on, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (form["title"], form["summary"], form["body"], image, pdf, pdf_size,
                         form["published_on"], datetime.now().isoformat(timespec="seconds")),
                    )
            flash("News article saved." if item else "News article published.")
            return redirect(url_for("admin_dashboard", tab="news"))

    return render_template("admin/news_form.html", page_title="Edit news" if item else "Add news",
                           item=item, form=form, errors=errors, max_mb=MAX_UPLOAD_MB)


@app.route("/admin/news/<int:news_id>/delete", methods=["POST"])
@admin_required
def admin_news_delete(news_id):
    with db() as conn:
        item = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,)).fetchone()
        if item:
            conn.execute("DELETE FROM news WHERE id = ?", (news_id,))
            delete_upload("news", item["image"])
            delete_upload("news", item["pdf"])
    flash("News article deleted.")
    return redirect(url_for("admin_dashboard", tab="news"))


# --- Reports ---

@app.route("/admin/reports/new", methods=["GET", "POST"])
@app.route("/admin/reports/<int:report_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_report_form(report_id=None):
    item = None
    if report_id:
        with db() as conn:
            item = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not item:
            abort(404)

    form = dict(item) if item else {"year": date.today().year}
    errors = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("title", "year", "description")}
        if not form["title"]:
            errors["title"] = "Enter a title, for example Annual Report 2026."
        if not form["year"].isdigit() or not 2000 <= int(form["year"]) <= 2100:
            errors["year"] = "Enter a year, for example 2026."

        upload = request.files.get("file")
        filename, size = (item["filename"], item["file_size"]) if item else (None, None)
        if not upload or not upload.filename:
            if not item:
                errors["file"] = "Choose the PDF file of the report."
        elif not errors:
            try:
                new_name, new_size = save_upload(upload, "reports", REPORT_TYPES)
                if item:
                    delete_upload("reports", item["filename"])
                filename, size = new_name, new_size
            except ValueError as e:
                errors["file"] = str(e)

        if not errors:
            with db() as conn:
                if item:
                    conn.execute(
                        "UPDATE reports SET title=?, year=?, description=?, filename=?, file_size=? WHERE id=?",
                        (form["title"], int(form["year"]), form["description"], filename, size, report_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO reports (title, year, description, filename, file_size, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (form["title"], int(form["year"]), form["description"], filename, size,
                         datetime.now().isoformat(timespec="seconds")),
                    )
            flash("Report saved." if item else "Report published.")
            return redirect(url_for("admin_dashboard", tab="reports"))

    return render_template("admin/report_form.html", page_title="Edit report" if item else "Upload report",
                           item=item, form=form, errors=errors, max_mb=MAX_UPLOAD_MB)


@app.route("/admin/reports/<int:report_id>/delete", methods=["POST"])
@admin_required
def admin_report_delete(report_id):
    with db() as conn:
        item = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if item:
            conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
            delete_upload("reports", item["filename"])
    flash("Report deleted.")
    return redirect(url_for("admin_dashboard", tab="reports"))


@app.errorhandler(413)
def too_large(_):
    flash(f"That file is too big. The limit is {MAX_UPLOAD_MB} MB.")
    return redirect(request.referrer or url_for("admin_dashboard"))


init_db()

APP_VERSION = "2026-09-27 deploy-ready"

if __name__ == "__main__":
    print(f"SokoSense website version: {APP_VERSION}")
    if not EMAIL_ENABLED:
        print("Note: email is not set up. Messages will only be saved to the database. See .env.example.")
    if not ADMIN_ENABLED:
        print("Note: admin area is off. Set ADMIN_USERNAME, ADMIN_PASSWORD and SECRET_KEY in .env to use /admin.")
    app.run(debug=DEBUG)
