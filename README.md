# SokoSense website (version 3)

Multi-page business website built with **Python (Flask)** and **JavaScript**.
Content is taken from sokosense.dev.

## Run it
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Pages
Every menu item and button opens its own page (no scrolling to a section):

| URL | Page |
|---|---|
| `/` | Home: hero, WhatsApp chat preview, market numbers, testimonials |
| `/about` | The problem, the three pain points, markets, photo gallery |
| `/solution` | Features, how it works, languages, pricing, FAQ |
| `/awards` | Awards and milestones |
| `/events` | Events, filterable by year |
| `/team` | Team members and field photo |
| `/contact` | Contact form (saves to `data/messages.db`) |

## Project structure
```
sokosense/
├── app.py              # Flask routes for every page + JSON API
├── data/content.json   # ALL website text and image links
├── templates/          # base.html (menu + footer) and one file per page
└── static/
    ├── css/style.css   # design; headings use Times New Roman
    ├── js/main.js      # menu, chat animation, awards/events/team loading, form
    └── img/            # logo files
```

## Editing content
Edit `data/content.json` and refresh.
- Team photos: save each photo in `static/img/team/` with exactly these names (square photos look best):
  - `bate-tabenyang-alaine.jpg` (currently loads from sokosense.dev; change his `photo` link to `/static/img/team/bate-tabenyang-alaine.jpg` if you prefer a local copy)
  - `emmanuel-niyonzima.jpg` (already added)
  - `olivier-dusengimana.jpg`
  - `aliane-uwase.jpg`
  - `dative-akimana.jpg`
  Until a photo is added, the person's initials are shown.
- Team LinkedIn: paste each profile link into that person's `"linkedin": ""` in `content.json`. The button appears once it is filled in.
- Team bios (optional): write a short text in `"bio": ""`. It shows in the pop-up when someone selects that person.
- Add an event: add to `"events"` with `year` and optionally `date` (YYYY-MM-DD) and `image`.
- Add an award: add to `"awards"`.
- Add your contact email/phone: fill in `"email"` and `"phone"` under `"company"`. They appear on the Contact page and footer only when filled in.

## Images
Photos load directly from sokosense.dev, so they need internet. To host them yourself,
download them into `static/img/` and change the links in `content.json` to `/static/img/filename.jpeg`.

## Fonts
Headings, quotes and large numbers use Times New Roman. To change which text uses it,
edit `--font-serif` in `static/css/style.css`.

## Deploying
`pip install gunicorn && gunicorn app:app`, and set `debug=False` in `app.py`.
Protect or remove the `/admin/messages` route before going live.
