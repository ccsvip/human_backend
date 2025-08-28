call .venv\Scripts\activate
uvicorn app.factory:create_app --host 0.0.0.0 --port 8080 --workers 1 --factory