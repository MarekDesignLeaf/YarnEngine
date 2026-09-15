@echo off
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
pause
