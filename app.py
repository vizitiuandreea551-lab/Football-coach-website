import os, re, sqlite3
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
DB = os.path.join(app.root_path, "coach.db")
# Set ADMIN_PASSWORD in your environment before real use!
ADMIN_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "changeme"))
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    c = sqlite3.connect(DB)
    c.executescript(open(os.path.join(app.root_path, "schema.sql"), encoding="utf-8").read())
    c.commit(); c.close()

@app.before_request
def csrf_check():
    if request.method == "POST" and request.form.get("_t") != session.get("t"):
        abort(400)

@app.context_processor
def inject():
    session.setdefault("t", os.urandom(16).hex())
    return {"tok": session["t"], "admin": session.get("admin")}

def q(sql, *a): return db().execute(sql, a).fetchall()

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"): return redirect(url_for("login"))
        return f(*a, **k)
    return w

@app.route("/")
def index():
    return render_template("index.html", progs=q("SELECT * FROM programmes"),
        news=q("SELECT * FROM news ORDER BY created DESC LIMIT 3"),
        fixtures=q("SELECT * FROM fixtures WHERE score IS NULL ORDER BY match_date LIMIT 3"),
        quotes=q("SELECT * FROM testimonials"))

@app.route("/programmes")
def programmes(): return render_template("programmes.html", progs=q("SELECT * FROM programmes"))

@app.route("/fixtures")
def fixtures(): return render_template("fixtures.html", rows=q("SELECT * FROM fixtures ORDER BY match_date"))

@app.route("/news")
def news(): return render_template("news.html", rows=q("SELECT * FROM news ORDER BY created DESC"))

for _p in ("about", "gallery", "safeguarding"):
    app.add_url_rule("/" + _p, _p, lambda p=_p: render_template(p + ".html"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    f = {}
    if request.method == "POST":
        keys = ("parent_name", "email", "phone", "child_name", "child_age", "age_group", "message")
        f = {k: request.form.get(k, "").strip()[:500] for k in keys}
        errs = []
        if not f["parent_name"] or not f["child_name"]: errs.append("Parent and child names are required.")
        if not EMAIL.match(f["email"]): errs.append("Please enter a valid email address.")
        if not f["child_age"].isdigit() or not 8 <= int(f["child_age"]) <= 16: errs.append("Child age must be between 8 and 16.")
        if f["age_group"] not in ("U14", "U16"): errs.append("Choose U14 or U16.")
        if not request.form.get("consent"): errs.append("Parental consent is required.")
        if errs:
            for e in errs: flash(e, "err")
        else:
            db().execute("INSERT INTO signups(parent_name,email,phone,child_name,child_age,age_group,photo_consent,message) VALUES(?,?,?,?,?,?,?,?)",
                (f["parent_name"], f["email"], f["phone"], f["child_name"], int(f["child_age"]), f["age_group"],
                 1 if request.form.get("photos") else 0, f["message"]))
            db().commit()
            flash("Thanks! The coach will be in touch about your trial session.", "ok")
            return redirect(url_for("signup"))
    return render_template("signup.html", f=f)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        n, e, b = (request.form.get(k, "").strip()[:1000] for k in ("name", "email", "body"))
        if n and EMAIL.match(e) and b:
            db().execute("INSERT INTO messages(name,email,body) VALUES(?,?,?)", (n, e, b)); db().commit()
            flash("Message sent. Thank you!", "ok"); return redirect(url_for("contact"))
        flash("Please fill in every field with a valid email.", "err")
    return render_template("contact.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if check_password_hash(ADMIN_HASH, request.form.get("password", "")):
            session["admin"] = True; return redirect(url_for("admin"))
        flash("Wrong password.", "err")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html", signups=q("SELECT * FROM signups ORDER BY created DESC"),
        msgs=q("SELECT * FROM messages ORDER BY created DESC"), fixtures=q("SELECT * FROM fixtures ORDER BY match_date"))

@app.route("/admin/news", methods=["POST"])
@login_required
def add_news():
    t, b = request.form.get("title", "").strip(), request.form.get("body", "").strip()
    if t and b: db().execute("INSERT INTO news(title,body) VALUES(?,?)", (t, b)); db().commit(); flash("News posted.", "ok")
    return redirect(url_for("admin"))

@app.route("/admin/fixture", methods=["POST"])
@login_required
def add_fixture():
    f = request.form
    if f.get("opponent", "").strip() and f.get("match_date") and f.get("age_group") in ("U14", "U16"):
        db().execute("INSERT INTO fixtures(age_group,opponent,match_date,home,score) VALUES(?,?,?,?,?)",
            (f["age_group"], f["opponent"].strip(), f["match_date"], 1 if f.get("home") else 0, f.get("score", "").strip() or None))
        db().commit(); flash("Fixture saved.", "ok")
    return redirect(url_for("admin"))

init_db()
if __name__ == "__main__":
    app.run(debug=True)
