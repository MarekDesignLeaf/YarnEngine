# YarnEngine M11.0 Mobile Web Application

YarnEngine is now packaged as a responsive Progressive Web App for Android, iPhone, tablets and desktop browsers.

## Local server
Install Python 3.12+, then:
`pip install -r requirements.txt`
`python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000`

Open `http://127.0.0.1:8000` in a browser.

## Public deployment
The project includes Dockerfile, Procfile and render.yaml. Deploy the repository to a Python/Docker capable HTTPS host. Once deployed, users open the public HTTPS URL in Safari, Chrome or another modern browser. PWA capable browsers can add YarnEngine to the Home Screen.

Railway uses the included Dockerfile and the `PORT` environment variable automatically. The production health check path is `/api/health`.

## Important
The PWA application shell can be cached, but calculations and persistent data still require the YarnEngine server. This package does not pretend to be a fully offline database application.

Production crochet accuracy remains gated by real physical calibration and validation.
