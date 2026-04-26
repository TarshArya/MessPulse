import os
import sys
from datetime import date, timedelta, datetime
from flask import Flask, render_template, redirect, request, session, jsonify
from werkzeug.security import check_password_hash

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SHARED_PATH = os.path.join(PROJECT_ROOT, "shared")

if SHARED_PATH not in sys.path:
    sys.path.append(SHARED_PATH)

from db import get_connection

app = Flask(__name__)
app.secret_key = "messpulse_admin_secret"


def is_admin_logged_in():
    return "admin_id" in session


def get_current_week_monday():
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    return current_monday.strftime("%Y-%m-%d")


def get_week_menu_from_db(week_start_date):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT day_name, breakfast, lunch, snacks, dinner
        FROM weekly_menus
        WHERE week_start_date = ?
    """, (week_start_date,))
    rows = cursor.fetchall()
    conn.close()

    menu = {
        "Monday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
        "Tuesday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
        "Wednesday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
        "Thursday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
        "Friday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
        "Saturday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
        "Sunday": {"breakfast": "", "lunch": "", "snacks": "", "dinner": ""},
    }

    for row in rows:
        menu[row["day_name"]] = {
            "breakfast": row["breakfast"] or "",
            "lunch": row["lunch"] or "",
            "snacks": row["snacks"] or "",
            "dinner": row["dinner"] or "",
        }

    return menu


def get_status_from_rating(rating):
    if rating >= 4.2:
        return "Excellent"
    elif rating >= 3.5:
        return "Good"
    elif rating >= 2.8:
        return "Average"
    return "Poor"


def count_keywords(comments, keywords):
    counts = {keyword: 0 for keyword in keywords}
    for comment in comments:
        if not comment:
            continue
        text = comment.lower()
        for keyword in keywords:
            if keyword in text:
                counts[keyword] += 1
    return counts


def analyze_comments(comments):
    complaint_keywords = [
        "cold", "oily", "spicy", "bland", "stale",
        "salty", "repetitive", "late", "uncooked",
        "less quantity"
    ]

    positive_keywords = [
        "tasty", "good", "fresh", "nice", "delicious", "hot"
    ]

    complaint_counts = count_keywords(comments, complaint_keywords)
    positive_counts = count_keywords(comments, positive_keywords)

    top_issue = max(complaint_counts, key=complaint_counts.get)
    top_issue_count = complaint_counts[top_issue]

    top_positive = max(positive_counts, key=positive_counts.get)
    top_positive_count = positive_counts[top_positive]

    if top_issue_count == 0 and top_positive_count == 0:
        summary = "Not enough comments yet to detect clear feedback patterns."
    elif top_issue_count > top_positive_count:
        summary = f"Most comments mention {top_issue} as the main issue."
    else:
        summary = f"Students mostly appreciated that the food was {top_positive}."

    return summary, complaint_counts, positive_counts, top_issue, top_issue_count, top_positive, top_positive_count


@app.route("/")
def home():
    return redirect("/admin/login")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE email = ?", (email,))
        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_email"] = admin["email"]
            return redirect("/admin/dashboard")
        else:
            return render_template("admin_login.html", error="Invalid admin email or password")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not is_admin_logged_in():
        return redirect("/admin/login")

    today_date = date.today().strftime("%Y-%m-%d")
    week_start = date.today() - timedelta(days=date.today().weekday())

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS total_reviews
        FROM reviews
        WHERE meal_date = ?
    """, (today_date,))
    overall_row = cursor.fetchone()

    avg_rating = overall_row["avg_rating"] if overall_row["avg_rating"] is not None else "N/A"
    total_reviews = overall_row["total_reviews"] if overall_row["total_reviews"] is not None else 0

    cursor.execute("""
        SELECT review_text
        FROM reviews
        WHERE meal_date = ? AND review_text IS NOT NULL AND TRIM(review_text) != ''
    """, (today_date,))
    comments = [row["review_text"] for row in cursor.fetchall()]

    summary, _, _, top_issue, issue_count, top_positive, positive_count = analyze_comments(comments)

    cursor.execute("""
        SELECT meal_type, ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS review_count
        FROM reviews
        WHERE meal_date = ?
        GROUP BY meal_type
    """, (today_date,))
    meal_rows = cursor.fetchall()

    meal_map = {
        "breakfast": {"name": "Breakfast", "rating": "N/A", "status": "No Data", "reviews": 0},
        "lunch": {"name": "Lunch", "rating": "N/A", "status": "No Data", "reviews": 0},
        "snacks": {"name": "Snacks", "rating": "N/A", "status": "No Data", "reviews": 0},
        "dinner": {"name": "Dinner", "rating": "N/A", "status": "No Data", "reviews": 0},
    }

    for row in meal_rows:
        meal_type = row["meal_type"].lower()
        rating = row["avg_rating"]
        meal_map[meal_type] = {
            "name": meal_type.capitalize(),
            "rating": rating,
            "status": get_status_from_rating(float(rating)),
            "reviews": row["review_count"]
        }

    meals = [
        meal_map["breakfast"],
        meal_map["lunch"],
        meal_map["snacks"],
        meal_map["dinner"]
    ]

    trend_labels = []
    trend_values = []

    for i in range(7):
        current_day = week_start + timedelta(days=i)
        current_day_str = current_day.strftime("%Y-%m-%d")
        current_day_label = current_day.strftime("%a")

        cursor.execute("""
            SELECT ROUND(AVG(rating), 1) AS avg_rating
            FROM reviews
            WHERE meal_date = ?
        """, (current_day_str,))
        trend_row = cursor.fetchone()

        trend_labels.append(current_day_label)
        trend_values.append(float(trend_row["avg_rating"]) if trend_row["avg_rating"] is not None else 0)

    cursor.execute("""
        SELECT COUNT(*) AS total_scans
        FROM meal_scans ms
        JOIN qr_codes q ON ms.qr_code_id = q.id
        WHERE q.meal_date = ?
    """, (today_date,))
    scan_row = cursor.fetchone()
    total_scans = scan_row["total_scans"] if scan_row["total_scans"] is not None else 0

    participation_rate = round((total_reviews / total_scans) * 100, 1) if total_scans > 0 else 0

    conn.close()

    data = {
        "avg_rating": avg_rating,
        "summary": summary,
        "meals": meals,
        "total_reviews": total_reviews,
        "total_scans": total_scans,
        "participation_rate": participation_rate,
        "top_issue": top_issue.title() if issue_count > 0 else "No major issue yet",
        "issue_count": issue_count,
        "top_positive": top_positive.title() if positive_count > 0 else "No clear positive pattern yet",
        "positive_count": positive_count,
        "trend_labels": trend_labels,
        "trend_values": trend_values
    }

    return render_template("admin_dashboard.html", data=data)


@app.route("/admin/scan")
def admin_scan():
    if not is_admin_logged_in():
        return redirect("/admin/login")
    return render_template("admin_scan.html")


@app.route("/admin/mark-served", methods=["POST"])
def admin_mark_served():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    qr_token = request.json.get("qr_token", "").strip()
    meal_type = request.json.get("meal_type", "").strip().lower()

    if not qr_token or not meal_type:
        return jsonify({"success": False, "message": "Missing QR token or meal type"}), 400

    today_date = date.today().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    # Find user from scanned user QR
    cursor.execute("SELECT * FROM users WHERE qr_token = ?", (qr_token,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "message": "Invalid student QR"}), 404

    # Find or create today's meal record in qr_codes
    meal_qr_token = f"MEAL-{meal_type.upper()}-{today_date}"

    cursor.execute("""
        SELECT * FROM qr_codes
        WHERE meal_date = ? AND meal_type = ?
        ORDER BY id DESC
        LIMIT 1
    """, (today_date, meal_type))
    meal_qr = cursor.fetchone()

    if not meal_qr:
        cursor.execute("""
            INSERT INTO qr_codes (meal_date, meal_type, qr_token, is_active)
            VALUES (?, ?, ?, 1)
        """, (today_date, meal_type, meal_qr_token))
        conn.commit()

        cursor.execute("""
            SELECT * FROM qr_codes
            WHERE meal_date = ? AND meal_type = ?
            ORDER BY id DESC
            LIMIT 1
        """, (today_date, meal_type))
        meal_qr = cursor.fetchone()

    # Prevent duplicate scan for same meal today
    cursor.execute("""
        SELECT * FROM meal_scans
        WHERE user_id = ? AND qr_code_id = ?
    """, (user["id"], meal_qr["id"]))
    existing_scan = cursor.fetchone()

    if existing_scan:
        conn.close()
        return jsonify({
            "success": True,
            "message": f"{user['full_name']} was already marked served for {meal_type.capitalize()}."
        })

    cursor.execute("""
        INSERT INTO meal_scans (user_id, qr_code_id, meal_served_at)
        VALUES (?, ?, ?)
    """, (user["id"], meal_qr["id"], now_time))
    conn.commit()
    conn.close()

    formatted_time = datetime.strptime(now_time, "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p").lstrip("0")

    return jsonify({
        "success": True,
        "message": f"{user['full_name']} marked served for {meal_type.capitalize()} at {formatted_time}."
    })


@app.route("/admin/menu", methods=["GET", "POST"])
def admin_menu():
    if not is_admin_logged_in():
        return redirect("/admin/login")

    week_start_date = get_current_week_monday()
    success_message = None

    if request.method == "POST":
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        conn = get_connection()
        cursor = conn.cursor()

        for day in days:
            breakfast = request.form.get(f"{day.lower()}_breakfast", "").strip()
            lunch = request.form.get(f"{day.lower()}_lunch", "").strip()
            snacks = request.form.get(f"{day.lower()}_snacks", "").strip()
            dinner = request.form.get(f"{day.lower()}_dinner", "").strip()

            cursor.execute("""
                INSERT INTO weekly_menus (
                    week_start_date, day_name, breakfast, lunch, snacks, dinner, created_by_admin_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(week_start_date, day_name)
                DO UPDATE SET
                    breakfast = excluded.breakfast,
                    lunch = excluded.lunch,
                    snacks = excluded.snacks,
                    dinner = excluded.dinner,
                    created_by_admin_id = excluded.created_by_admin_id
            """, (
                week_start_date,
                day,
                breakfast,
                lunch,
                snacks,
                dinner,
                session["admin_id"]
            ))

        conn.commit()
        conn.close()

        success_message = "Weekly menu saved successfully."

    menu = get_week_menu_from_db(week_start_date)

    return render_template(
        "admin_menu.html",
        menu=menu,
        week_start_date=week_start_date,
        success_message=success_message
    )


@app.route("/admin/reviews")
def admin_reviews():
    if not is_admin_logged_in():
        return redirect("/admin/login")

    today_date = date.today().strftime("%Y-%m-%d")
    week_start = date.today() - timedelta(days=date.today().weekday())

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS total_reviews
        FROM reviews
    """)
    row = cursor.fetchone()

    cursor.execute("""
        SELECT review_text
        FROM reviews
        WHERE review_text IS NOT NULL AND TRIM(review_text) != ''
    """)
    comments = [r["review_text"] for r in cursor.fetchall()]

    _, complaint_counts, _, top_issue, issue_count, _, _ = analyze_comments(comments)

    labels = []
    values = []
    for key, value in complaint_counts.items():
        if value > 0:
            labels.append(key.title())
            values.append(value)

    if not labels:
        labels = ["No Issues Yet"]
        values = [1]

    trend_labels = []
    trend_values = []

    for i in range(7):
        current_day = week_start + timedelta(days=i)
        current_day_str = current_day.strftime("%Y-%m-%d")
        current_day_label = current_day.strftime("%a")

        cursor.execute("""
            SELECT COUNT(*) AS total_reviews
            FROM reviews
            WHERE meal_date = ?
        """, (current_day_str,))
        trend_row = cursor.fetchone()

        trend_labels.append(current_day_label)
        trend_values.append(trend_row["total_reviews"] if trend_row["total_reviews"] is not None else 0)

    recent_reviews = []
    cursor.execute("""
        SELECT meal_date, meal_type, rating, review_text
        FROM reviews
        WHERE review_text IS NOT NULL AND TRIM(review_text) != ''
        ORDER BY created_at DESC
        LIMIT 5
    """)
    for review in cursor.fetchall():
        recent_reviews.append({
            "meal_date": review["meal_date"],
            "meal_type": review["meal_type"].capitalize(),
            "rating": review["rating"],
            "review_text": review["review_text"]
        })

    conn.close()

    data = {
        "avg_rating": row["avg_rating"] if row["avg_rating"] is not None else "N/A",
        "total_reviews": row["total_reviews"] if row["total_reviews"] is not None else 0,
        "top_issue": top_issue.title() if issue_count > 0 else "No major issue yet",
        "issue_count": issue_count,
        "issue_labels": labels,
        "issue_values": values,
        "trend_labels": trend_labels,
        "trend_values": trend_values,
        "recent_reviews": recent_reviews
    }

    return render_template("admin_reviews.html", data=data)


@app.route("/admin/analytics")
def admin_analytics():
    if not is_admin_logged_in():
        return redirect("/admin/login")

    week_start = date.today() - timedelta(days=date.today().weekday())

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT meal_date, meal_type, ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS total_reviews
        FROM reviews
        GROUP BY meal_date, meal_type
        ORDER BY meal_date DESC, meal_type ASC
        LIMIT 1
    """)
    latest = cursor.fetchone()

    trend_labels = []
    trend_values = []

    for i in range(7):
        current_day = week_start + timedelta(days=i)
        current_day_str = current_day.strftime("%Y-%m-%d")
        current_day_label = current_day.strftime("%a")

        cursor.execute("""
            SELECT ROUND(AVG(rating), 1) AS avg_rating
            FROM reviews
            WHERE meal_date = ?
        """, (current_day_str,))
        trend_row = cursor.fetchone()

        trend_labels.append(current_day_label)
        trend_values.append(float(trend_row["avg_rating"]) if trend_row["avg_rating"] is not None else 0)

    if latest:
        meal_date = latest["meal_date"]
        meal_type = latest["meal_type"]

        cursor.execute("""
            SELECT review_text, rating
            FROM reviews
            WHERE meal_date = ? AND meal_type = ?
        """, (meal_date, meal_type))
        review_rows = cursor.fetchall()

        comments = [r["review_text"] for r in review_rows if r["review_text"]]
        summary, complaint_counts, _, _, _, _, _ = analyze_comments(comments)

        issue_list = [key.title() for key, value in complaint_counts.items() if value > 0]
        if not issue_list:
            issue_list = [summary]

        distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        formatted_reviews = []

        for r in review_rows:
            distribution[int(r["rating"])] += 1
            if r["review_text"]:
                formatted_reviews.append({
                    "rating": r["rating"],
                    "text": r["review_text"]
                })

        cursor.execute("""
            SELECT breakfast, lunch, snacks, dinner, day_name
            FROM weekly_menus
            WHERE day_name = ?
            ORDER BY id DESC
            LIMIT 1
        """, (date.fromisoformat(meal_date).strftime("%A"),))
        menu_row = cursor.fetchone()

        meal_items = "Menu not found"
        if menu_row:
            meal_items = menu_row[meal_type] if menu_row[meal_type] else "Menu not added"

        data = {
            "meal": meal_type.capitalize(),
            "date": meal_date,
            "items": meal_items,
            "avg_rating": latest["avg_rating"],
            "total_reviews": latest["total_reviews"],
            "issues": issue_list,
            "distribution": distribution,
            "reviews": formatted_reviews[:5],
            "trend_labels": trend_labels,
            "trend_values": trend_values
        }
    else:
        data = {
            "meal": "No data",
            "date": "-",
            "items": "-",
            "avg_rating": "N/A",
            "total_reviews": 0,
            "issues": ["No reviews yet"],
            "distribution": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
            "reviews": [],
            "trend_labels": trend_labels,
            "trend_values": trend_values
        }

    conn.close()

    return render_template("admin_analytics.html", data=data)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")


if __name__ == "__main__":
    app.run(debug=True, port=5001)