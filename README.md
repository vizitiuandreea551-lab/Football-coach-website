# Coach Name FC website (Flask + SQLite)
1. `pip install -r requirements.txt`
2. Optional: set `ADMIN_PASSWORD` and `SECRET_KEY` environment variables (default admin password is `changeme`, change it!)
3. `python app.py` then open http://127.0.0.1:5000
Admin panel: /login (post news, add fixtures/results, view sign-ups and messages). The SQLite database `coach.db` is created from `schema.sql` on first run.
