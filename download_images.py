"""
Downloads every picture the website currently loads from sokosense.dev,
saves it inside this project, and updates data/content.json to use the saved copies.

Run from inside the website folder (the one with app.py):
    python3 download_images.py

- Pictures are saved in:   static/img/site/   (team photos in static/img/team/)
- A backup of content.json is saved first: data/content.backup.json
- Safe to run more than once: pictures already downloaded are skipped.
"""
import json
import re
import shutil
import ssl
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "data" / "content.json"
BACKUP = HERE / "data" / "content.backup.json"
SITE_DIR = HERE / "static" / "img" / "site"
TEAM_DIR = HERE / "static" / "img" / "team"
REMOTE = "https://sokosense.dev/"


def clean_name(url):
    """'Rural%20Kigali%2C%20Rwanda.jpeg' -> 'rural-kigali-rwanda.jpeg'"""
    name = unquote(Path(urlparse(url).path).name)
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return f"{stem}{ext}"


def ssl_context():
    """Use the certifi certificate list if installed (fixes CERTIFICATE_VERIFY_FAILED on Mac)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CONTEXT = ssl_context()


def download(url, target):
    if target.exists() and target.stat().st_size > 0:
        return "already saved"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp, open(target, "wb") as f:
        shutil.copyfileobj(resp, f)
    return "downloaded"


def main():
    if not CONTENT.exists():
        print("Could not find data/content.json. Run this from the website folder (the one with app.py).")
        return
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    TEAM_DIR.mkdir(parents=True, exist_ok=True)

    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Backup saved: data/content.backup.json\n")

    team_photos = {m.get("photo"): m["name"] for m in data.get("team", []) if m.get("photo")}
    done, failed = {}, []

    def fix(value):
        if not (isinstance(value, str) and value.startswith(REMOTE)
                and re.search(r"\.(jpe?g|png|webp|gif|svg)$", value, re.I)):
            return value
        if value in done:
            return done[value]
        if value in team_photos:  # team photo -> static/img/team/firstname-lastname.jpg
            ext = Path(urlparse(value).path).suffix.lower()
            fname = re.sub(r"[^a-z0-9]+", "-", team_photos[value].lower()).strip("-") + ext
            folder, web = TEAM_DIR, "/static/img/team/"
        else:
            fname, folder, web = clean_name(value), SITE_DIR, "/static/img/site/"
        try:
            status = download(value, folder / fname)
            print(f"  {status}: {fname}")
            done[value] = web + fname
            return done[value]
        except Exception as e:
            print(f"  FAILED: {fname}  ({e})")
            if value not in failed:
                failed.append(value)
            return value  # keep the old link so nothing breaks

    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return fix(obj)

    print("Downloading pictures from sokosense.dev ...")
    data = walk(data)
    CONTENT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone: {len(done)} pictures saved in the project, content.json updated.")
    if failed:
        print(f"{len(failed)} could not be downloaded (their old links were kept):")
        for u in failed:
            print("  -", u)
        print("Check your internet connection and run the script again.")
        print("If you see CERTIFICATE_VERIFY_FAILED, run:  pip3 install certifi   and try again.")


if __name__ == "__main__":
    main()
