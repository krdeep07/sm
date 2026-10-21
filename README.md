# Travel World — Flask + Vercel demo

A responsive travel-agency demo built with Python Flask, HTML, CSS and JavaScript. It includes destination cards, package cards, mobile navigation, saved-package buttons, quick trip selection, an enquiry form and health endpoint.

## Important demo limitations
- The enquiry form validates input and returns a success response, but does **not** save enquiries permanently or send email. For testing, submissions appear in Vercel function logs.
- Destination photography is loaded from Unsplash; the Google Fonts are loaded from Google Fonts. A live internet connection is needed to load these assets.
- No booking, payment, customer account, or inventory system is configured.

## Deploy on Vercel (GitHub method)

1. Extract `travel-world-vercel.zip` on your computer.
2. Sign in to GitHub and create a new **empty** repository, for example `travel-world-demo`: https://github.com/new
3. Upload the extracted files and folders to the repository root. The root must contain `app.py`, `requirements.txt`, `vercel.json`, `templates/`, and `static/`. Do not upload the ZIP as the only repository file.
4. Open https://vercel.com/new and sign in.
5. Import the GitHub repository.
6. For this Flask project, keep the project root at the repository root. The `vercel.json` file selects Vercel's Python runtime. If Vercel shows a Framework Preset field, choose **Other** if it does not automatically detect the project.
7. Click **Deploy** and wait for the build to finish.
8. Open the generated `https://your-project-name.vercel.app` URL.
9. Check `https://your-project-name.vercel.app/api/health`. It should return JSON with `"status": "ok"`.

If you change files later, commit and push them to GitHub; Vercel will redeploy the connected project.

## Run locally on Windows

Install Python 3.11 or newer, then open Command Prompt in this folder:

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Troubleshooting
- **Build or runtime error:** open the project in Vercel, select **Deployments**, open the latest deployment and inspect **Build Logs** and **Runtime Logs**.
- **Missing module:** confirm `requirements.txt` is at the repository root and contains Flask.
- **404 at `/api/health`:** redeploy and confirm `app.py` and `vercel.json` are in the repository root.
- **Enquiry success but no saved records:** expected for this demo. Add a database or email provider before using it with real customers.

## Files
- `app.py` — Flask routes and demo enquiry API
- `templates/index.html` — website markup
- `static/css/style.css` — responsive styles
- `static/js/main.js` — frontend interactions
- `requirements.txt` — Python dependency
- `vercel.json` — Vercel Python deployment routing
