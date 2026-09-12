from flask import Flask, render_template, request, redirect, session, send_from_directory, Response
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "civicfix_local_dev_key")

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")


# ================= FILE UPLOAD =================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif"
}


def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ================= DATABASE =================

def init_db():

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Complaints table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            priority TEXT DEFAULT 'Medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            latitude TEXT,
            longitude TEXT,
            image_path TEXT
        )
    """)

    # Check existing columns
    cursor.execute("PRAGMA table_info(complaints)")
    columns = [row[1] for row in cursor.fetchall()]
    
    

    # Add latitude if missing
    if "latitude" not in columns:
        cursor.execute(
            "ALTER TABLE complaints ADD COLUMN latitude TEXT"
        )

    # Add longitude if missing
    if "longitude" not in columns:
        cursor.execute(
            "ALTER TABLE complaints ADD COLUMN longitude TEXT"
        )

    # Add image_path if missing
    if "image_path" not in columns:
        cursor.execute(
            "ALTER TABLE complaints ADD COLUMN image_path TEXT"
        )
    if "priority" not in columns:
        cursor.execute(
        "ALTER TABLE complaints ADD COLUMN priority TEXT DEFAULT 'Medium'"
   )
       
    conn.commit()
    conn.close()


# ================= HOME =================

@app.route("/")
def home():

    return render_template("home.html")


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:

            return render_template(
                "register.html",
                error="Passwords do not match!"
            )

        conn = sqlite3.connect("civicfix.db")
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO users
                (name, email, phone, password)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                email,
                phone,
                password
            ))

            conn.commit()
            conn.close()

            return render_template(
                "register.html",
                success="Registration successful! You can login now."
            )

        except sqlite3.IntegrityError:

            conn.close()

            return render_template(
                "register.html",
                error="Email already registered!"
            )

    return render_template("register.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("civicfix.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, email
            FROM users
            WHERE email = ? AND password = ?
        """, (
            email,
            password
        ))

        user = cursor.fetchone()

        conn.close()

        if user:

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = user[2]

            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid email or password!"
        )

    return render_template("login.html")


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    # Total complaints
    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ?
    """, (user_id,))

    total = cursor.fetchone()[0]

    # Pending
    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ?
        AND status = 'Pending'
    """, (user_id,))

    pending = cursor.fetchone()[0]

    # In Progress
    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ?
        AND status = 'In Progress'
    """, (user_id,))

    in_progress = cursor.fetchone()[0]

    # Resolved
    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE user_id = ?
        AND status = 'Resolved'
    """, (user_id,))

    resolved = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved
    )


# ================= REPORT COMPLAINT =================

@app.route("/report", methods=["GET", "POST"])
def report():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        user_id = session["user_id"]

        category = request.form["category"]
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]

        priority = request.form.get("priority", "Medium")

        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        photo = request.files.get("photo")

        image_path = None

        if photo and photo.filename != "":

            if allowed_file(photo.filename):

                filename = secure_filename(photo.filename)

                import time

                filename = str(int(time.time())) + "_" + filename

                photo.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        filename
                    )
                )

                image_path = filename

        conn = sqlite3.connect("civicfix.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO complaints
            (
                user_id,
                category,
                title,
                description,
                location,
                priority,
                latitude,
                longitude,
                image_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            category,
            title,
            description,
            location,
            priority,
            latitude,
            longitude,
            image_path
        ))

        conn.commit()

        conn.close()

        return render_template("success.html")

    return render_template("report.html")

# ================= MY COMPLAINTS =================

@app.route("/my-complaints")
def my_complaints():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        category,
        title,
        description,
        location,
        created_at,
        status,
        image_path,
        latitude,
        longitude
    FROM complaints
    WHERE user_id = ?
    ORDER BY id DESC
""", (user_id,))

    complaints = cursor.fetchall()

    conn.close()

    return render_template(
        "my_complaints.html",
        complaints=complaints
    )
@app.route("/complaint/<int:complaint_id>")
def complaint_details(complaint_id):

    if "admin" not in session:
        return redirect("/admin-login")

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            complaints.id,
            users.name,
            users.email,
            complaints.category,
            complaints.title,
            complaints.description,
            complaints.location,
            complaints.status,
            complaints.created_at,
            complaints.image_path,
            complaints.latitude,
            complaints.longitude
        FROM complaints
        JOIN users
        ON complaints.user_id = users.id
        WHERE complaints.id = ?
    """, (complaint_id,))

    complaint = cursor.fetchone()

    conn.close()

    if not complaint:
        return "Complaint not found"

    return render_template(
        "complaint_details.html",
        complaint=complaint
    )
@app.route("/my-complaint/<int:complaint_id>")
def my_complaint_details(complaint_id):

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            category,
            title,
            description,
            location,
            created_at,
            status,
            image_path,
            latitude,
            longitude
        FROM complaints
        WHERE id = ? AND user_id = ?
    """, (complaint_id, user_id))

    complaint = cursor.fetchone()

    conn.close()

    if not complaint:
        return "Complaint not found"

    return render_template(
        "my_complaint_details.html",
        complaint=complaint
    )

# ================= ADMIN LOGIN =================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        # Temporary admin credentials
        if email == "admin@civicfix.com" and password == "admin123":

            session["admin"] = True

            return redirect("/admin-dashboard")

        else:

            return render_template(
                "admin_login.html",
                error="Invalid admin email or password!"
            )

    return render_template("admin_login.html")


# ================= UPLOADED FILE =================

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )

# ================= ADMIN DASHBOARD =================

@app.route("/admin-dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin-login")

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            complaints.id,
            users.name,
            users.email,
            complaints.category,
            complaints.priority,
            complaints.title,
            complaints.description,
            complaints.location,
            complaints.status,
            complaints.created_at,
            complaints.image_path,
            complaints.latitude,
            complaints.longitude
        FROM complaints
        JOIN users
        ON complaints.user_id = users.id
        ORDER BY complaints.id DESC
    """)
    complaints = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM complaints")
    total = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
    """)
    pending = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'In Progress'
    """)
    in_progress = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Resolved'
    """)
    resolved = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE priority = 'High'
    """)
    high_priority = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE priority = 'Medium'
    """)
    medium_priority = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE priority = 'Low'
    """)
    low_priority = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority
    )


# ================= UPDATE COMPLAINT STATUS =================

@app.route("/update-status/<int:complaint_id>", methods=["POST"])
def update_status(complaint_id):

    if "admin" not in session:
        return redirect("/admin-login")

    status = request.form.get("status", "Pending")

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE complaints
        SET status = ?
        WHERE id = ?
    """, (status, complaint_id))

    conn.commit()
    conn.close()

    return redirect("/admin-dashboard")


# ================= EXPORT COMPLAINTS =================

@app.route("/export-complaints")
def export_complaints():

    if "admin" not in session:
        return redirect("/admin-login")

    conn = sqlite3.connect("civicfix.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            complaints.id,
            users.name,
            users.email,
            complaints.category,
            complaints.priority,
            complaints.title,
            complaints.description,
            complaints.location,
            complaints.status,
            complaints.created_at
        FROM complaints
        JOIN users
        ON complaints.user_id = users.id
        ORDER BY complaints.id DESC
    """)

    complaints = cursor.fetchall()
    conn.close()

    csv_data = "ID,Citizen Name,Email,Category,Priority,Title,Description,Location,Status,Date\n"

    for complaint in complaints:
        row = [str(value) if value is not None else "" for value in complaint]
        row = ['"' + str(value).replace('"', '""') + '"' for value in row]
        csv_data += ",".join(row) + "\n"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=civicfix_complaints.csv"
        }
    )


# ================= ADMIN LOGOUT =================

@app.route("/admin-logout")
def admin_logout():

    session.pop("admin", None)

    return redirect("/admin-login")


# ================= USER LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ================= RUN APP =================

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)