# Putting sokosenserw.com online with GoDaddy

This website is a Python (Flask) app. It needs **GoDaddy Web Hosting (cPanel), Linux**,
with **Setup Python App** and **Python 3.9 or newer**.

---

## A. Before you start (on your Mac)

1. `python3 check_install.py` says "Everything is installed correctly".
2. Pictures: `python3 download_images.py` (optional but recommended).
3. Delete test news, reports and messages in your local `/admin`.
4. Make a backup copy of the whole `sokoweb` folder (Google Drive or USB).

## B. Buy and connect

1. Buy the domain **sokosenserw.com** and **Web Hosting (cPanel)**.
   Ask GoDaddy chat first: "Does this plan include Setup Python App with Python 3.9+?"
2. GoDaddy > My Products > Web Hosting > **Manage** > connect the domain sokosenserw.com.
3. Turn on the free **SSL certificate** (padlock) for sokosenserw.com if it is not on already.

## C. Upload the files

1. On your Mac, right-click `sokoweb` > **Compress**. You get `sokoweb.zip`.
2. GoDaddy > Manage > **cPanel Admin** > **File Manager**.
3. Open your home folder (`/home/yourusername/`), NOT `public_html`.
4. **+ Folder** > name it `sokosense`. Open it.
5. **Upload** `sokoweb.zip`, then right-click it > **Extract**.
   Move the files so `app.py` sits directly in `/home/yourusername/sokosense/`.
6. Delete the zip. Also delete from the server: `data/messages.db` (to start clean) if you want.

## D. Create the settings file on the server

1. File Manager > **Settings** (top right) > tick **Show Hidden Files**.
2. Inside `sokosense`: **+ File** > name `.env` > right-click > **Edit**.
3. Paste your settings (same as your Mac) and change these for the live site:
   ```
   FLASK_DEBUG=false
   SECURE_COOKIES=true
   ```
4. Save.

## E. Start the website

1. cPanel > **Setup Python App** > **Create Application**:

   | Field | Value |
   |---|---|
   | Python version | highest available (3.9+) |
   | Application root | `sokosense` |
   | Application URL | `sokosenserw.com` |
   | Application startup file | `passenger_wsgi.py` |
   | Application entry point | `application` |

2. **Create**.
3. Scroll to **Configuration files** > add `requirements.txt` > **Run Pip Install**.
4. Scroll up > **Restart**.
5. Open **https://sokosenserw.com**.

## F. Test

- Every page and picture loads, and the padlock shows.
- Contact form: message arrives at the MAIL_TO inbox (check Spam).
  In `/admin` > Messages, `email_status` should say `sent`.
- `/admin`: log in, publish a test news item with a PDF, try Read / Open / Download, delete it.
- Open the site on a phone.

### If the contact email does not arrive
GoDaddy often blocks Gmail. Open `.env` on the server and use GoDaddy's relay
(see the "Only if Gmail is blocked" lines in `env.example`), then **Restart** in Setup Python App.
Messages are always saved in the database, even if email fails.

### If you see "500 Internal Server Error"
- Setup Python App > **Run Pip Install** again > **Restart**.
- Check the error log: cPanel > **Errors**, or the log file set in Setup Python App.

---

## Updating the website later

1. Change and test the file on your Mac.
2. Upload only that file in File Manager (replace the old one).
3. Setup Python App > **Restart**.

**Never overwrite on the server:** `.env`, `data/messages.db`, `data/uploads/`.

**Backup monthly:** File Manager > right-click `data` > Compress > download the zip.
