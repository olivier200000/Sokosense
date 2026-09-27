"""
Checks that the SokoSense website files are installed correctly.
Run from inside the website folder:   python3 check_install.py
"""
from pathlib import Path

here = Path(__file__).resolve().parent
problems = []


def need_file(path):
    if not (here / path).exists():
        problems.append(f"Missing file: {path}")
        return False
    return True


def need_text(path, text, why):
    if need_file(path) and text not in (here / path).read_text(encoding="utf-8", errors="ignore"):
        problems.append(f"{path} is an old version ({why})")


print(f"Checking the website folder: {here}\n")

need_text("app.py", "deploy-ready", "replace it with the new app.py")
need_text("passenger_wsgi.py", "application", "GoDaddy needs this start-up file")
for f in ["templates/publications.html", "templates/news_article.html", "templates/report_view.html",
          "templates/_pdf_options.html", "templates/admin/login.html", "templates/admin/dashboard.html",
          "templates/admin/news_form.html", "templates/admin/report_form.html",
          "templates/admin/_flash.html", "templates/admin/_confirm.html", "static/css/publications.css"]:
    need_file(f)
need_text("templates/admin/news_form.html", 'name="pdf"', "the news form has no PDF field")
need_text("templates/news_article.html", "_pdf_options.html", "no Read / Open / Download buttons")
need_text("static/css/publications.css", ".pdf-actions", "missing the new button styles")
need_text("templates/base.html", "publications.css", "add the publications.css line in <head>")

if (here / "sokosense-deploy-ready").exists() or (here / "pdf-news-update").exists() or (here / "publications-update").exists() or (here / "sokosense-publications-pdf").exists():
    problems.append("An update FOLDER was copied into the website folder. Its files must replace the "
                    "website's own files instead (see the instructions). You can delete that folder.")

env = here / ".env"
if not env.exists():
    problems.append("Missing .env file (your email and admin settings)")
else:
    settings = {}
    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            settings[k.strip()] = v.strip()
    for key in ["ADMIN_USERNAME", "ADMIN_PASSWORD", "SECRET_KEY"]:
        if not settings.get(key):
            problems.append(f".env: {key} is empty, so the admin area is switched off")
    if settings.get("FLASK_DEBUG", "false").lower() == "true":
        problems.append(".env: FLASK_DEBUG is true. Set it to false before going live")
    if len(settings.get("ADMIN_PASSWORD", "")) and len(settings.get("ADMIN_PASSWORD", "")) < 12:
        problems.append(".env: ADMIN_PASSWORD is shorter than 12 characters. Use a stronger one")

remote = (here / "data" / "content.json")
if remote.exists() and "https://sokosense.dev/images" in remote.read_text(encoding="utf-8", errors="ignore"):
    print("Note: some pictures still load from sokosense.dev. They will work, but run\n"
          "      python3 download_images.py   to keep your own copies.\n")

if problems:
    print("Problems found:")
    for p in problems:
        print("  -", p)
    print("\nFix these, then restart the website (Ctrl + C, then python3 app.py).")
else:
    print("Everything is installed correctly.")
    print("Restart the website (Ctrl + C, then python3 app.py) if it is running,")
    print("and check that the first line says: SokoSense website version: 2026-09-27 deploy-ready")
