from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import sys
import uuid
import io
import base64
import qrcode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "..", "shared")
sys.path.append(SHARED_DIR)

from db import get_connection

app = Flask(__name__)
app.secret_key = "messpulse_secret_key"


def generate_qr_token():
    return f"USR-{uuid.uuid4().hex[:10].upper()}"


def build_qr_base64(data):
    img = qrcode.make(data)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded


def get_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["user_email"] = user["email"]
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password")
            return redirect(url_for("login"))

    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        if not email.endswith("@bennett.edu.in"):
            flash("Only Bennett University email IDs are allowed")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        qr_token = generate_qr_token()

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash, qr_token)
                VALUES (?, ?, ?, ?)
            """, (full_name, email, password_hash, qr_token))
            conn.commit()
            conn.close()
            flash("Registration successful. Please login.")
            return redirect(url_for("login"))
        except Exception:
            conn.close()
            flash("User already exists or registration failed")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/home")
def home():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("login"))

    today_day = datetime.now().strftime("%A")
    today_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            day_name,
            breakfast,
            lunch,
            snacks,
            dinner
        FROM weekly_menus
        WHERE day_name = ?
        ORDER BY id DESC
        LIMIT 1
    """, (today_day,))
    menu_row = cursor.fetchone()

    if menu_row:
        today_menu = {
            "day": menu_row["day_name"],
            "breakfast": menu_row["breakfast"],
            "lunch": menu_row["lunch"],
            "snacks": menu_row["snacks"],
            "dinner": menu_row["dinner"]
        }
    else:
        today_menu = {
            "day": today_day,
            "breakfast": "Menu not added yet",
            "lunch": "Menu not added yet",
            "snacks": "Menu not added yet",
            "dinner": "Menu not added yet"
        }

    cursor.execute("""
        SELECT q.meal_type, ms.scanned_at, ms.meal_served_at
        FROM meal_scans ms
        JOIN qr_codes q ON ms.qr_code_id = q.id
        WHERE ms.user_id = ? AND q.meal_date = ?
    """, (user["id"], today_date))
    scan_rows = cursor.fetchall()

    served_times = {}
    for row in scan_rows:
        raw_time = row["meal_served_at"] or row["scanned_at"]
        if raw_time:
            dt_obj = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
            formatted_time = dt_obj.strftime("%I:%M %p").lstrip("0")
            served_times[row["meal_type"].lower()] = formatted_time

    cursor.execute("""
        SELECT meal_type FROM reviews
        WHERE user_id = ? AND meal_date = ?
    """, (user["id"], today_date))
    review_rows = cursor.fetchall()

    rated_meals = set()
    for row in review_rows:
        rated_meals.add(row["meal_type"].lower())

    conn.close()

    return render_template(
        "home.html",
        user=user,
        today_menu=today_menu,
        served_times=served_times,
        rated_meals=rated_meals
    )


@app.route("/my_qr")
def my_qr():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("login"))

    qr_token = user["qr_token"]
    qr_image = build_qr_base64(qr_token)

    return render_template(
        "my_qr.html",
        user=user,
        qr_token=qr_token,
        qr_image=qr_image
    )


@app.route("/rate")
def rate_page():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("login"))

    selected_meal = request.args.get("meal")
    if not selected_meal:
        flash("Please select a meal first")
        return redirect(url_for("home"))

    selected_meal = selected_meal.lower()
    meal_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM reviews
        WHERE user_id = ? AND meal_date = ? AND meal_type = ?
    """, (user["id"], meal_date, selected_meal))
    existing_review = cursor.fetchone()
    conn.close()

    return render_template(
        "rate.html",
        user=user,
        selected_meal=selected_meal,
        meal_date=meal_date,
        existing_review=existing_review
    )


@app.route("/submit_review", methods=["POST"])
def submit_review():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("login"))

    meal_type = request.form.get("meal_type", "").lower()
    meal_date = request.form.get("meal_date")
    rating = request.form.get("rating")
    review_text = request.form.get("review_text", "").strip()

    if not meal_type or not meal_date or not rating:
        flash("Please fill all required fields")
        return redirect(url_for("home"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM reviews
        WHERE user_id = ? AND meal_date = ? AND meal_type = ?
    """, (user["id"], meal_date, meal_type))
    existing_review = cursor.fetchone()

    if existing_review:
        conn.close()
        flash("You have already submitted a review for this meal")
        return redirect(url_for("home"))

    cursor.execute("""
        INSERT INTO reviews (user_id, meal_date, meal_type, rating, review_text)
        VALUES (?, ?, ?, ?, ?)
    """, (user["id"], meal_date, meal_type, int(rating), review_text))

    conn.commit()
    conn.close()

    flash("Review submitted successfully")
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, port=5002)