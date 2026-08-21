from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

DB = "chisomo_expenses.db"

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "chisomo-expense-tracker-development-secret-change-me"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database():
    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            expense_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            user_id INTEGER
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            monthly_budget REAL DEFAULT 0
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Ensure the original Chisomo account exists.
    existing_user = connection.execute("""
        SELECT id
        FROM users
        WHERE username = ?
    """, ("chisomo",)).fetchone()

    if existing_user is None:
        connection.execute("""
            INSERT INTO users
            (username, password_hash, created_at)
            VALUES (?, ?, ?)
        """, (
            "chisomo",
            generate_password_hash("Chisomo@2026"),
            datetime.now().isoformat()
        ))

        existing_user = connection.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, ("chisomo",)).fetchone()

    chisomo_id = existing_user["id"]

    # Make sure expenses have user_id.
    columns = [
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(expenses)"
        ).fetchall()
    ]

    if "user_id" not in columns:
        connection.execute("""
            ALTER TABLE expenses
            ADD COLUMN user_id INTEGER
        """)

    # Existing expenses belong to Chisomo.
    connection.execute("""
        UPDATE expenses
        SET user_id = ?
        WHERE user_id IS NULL
    """, (chisomo_id,))

    # Give Chisomo a settings record.
    connection.execute("""
        INSERT OR IGNORE INTO settings
        (user_id, monthly_budget)
        VALUES (?, 0)
    """, (chisomo_id,))

    connection.commit()
    connection.close()


def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({
                "error": "Authentication required."
            }), 401

        return function(*args, **kwargs)

    return decorated_function


@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# AUTHENTICATION
# =========================================================

@app.route("/api/signup", methods=["POST"])
def signup():

    data = request.get_json(silent=True) or {}

    username = str(
        data.get("username", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )

    confirm_password = str(
        data.get("confirm_password", "")
    )

    if not username or not password or not confirm_password:
        return jsonify({
            "error": "Username, password and confirmation are required."
        }), 400

    if len(username) < 3:
        return jsonify({
            "error": "Username must be at least 3 characters."
        }), 400

    if len(password) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters."
        }), 400

    if password != confirm_password:
        return jsonify({
            "error": "Passwords do not match."
        }), 400

    connection = db()

    existing = connection.execute("""
        SELECT id
        FROM users
        WHERE username = ?
    """, (username,)).fetchone()

    if existing:
        connection.close()

        return jsonify({
            "error": "Username already exists."
        }), 409

    cursor = connection.execute("""
        INSERT INTO users
        (username, password_hash, created_at)
        VALUES (?, ?, ?)
    """, (
        username,
        generate_password_hash(password),
        datetime.now().isoformat()
    ))

    user_id = cursor.lastrowid

    connection.execute("""
        INSERT INTO settings
        (user_id, monthly_budget)
        VALUES (?, 0)
    """, (user_id,))

    connection.commit()
    connection.close()

    session.clear()
    session["user_id"] = user_id
    session["username"] = username

    return jsonify({
        "message": "Account created successfully.",
        "username": username
    }), 201


@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = str(
        data.get("username", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )

    if not username or not password:
        return jsonify({
            "error": "Username and password are required."
        }), 400

    connection = db()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE username = ?
    """, (username,)).fetchone()

    connection.close()

    if user is None or not check_password_hash(
        user["password_hash"],
        password
    ):
        return jsonify({
            "error": "Invalid username or password."
        }), 401

    session.clear()

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify({
        "message": "Login successful.",
        "username": user["username"]
    })


@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():

    data = request.get_json(silent=True) or {}

    current_password = str(
        data.get("current_password", "")
    )

    new_password = str(
        data.get("new_password", "")
    )

    confirm_password = str(
        data.get("confirm_password", "")
    )

    if not current_password or not new_password or not confirm_password:
        return jsonify({
            "error": "All password fields are required."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "error": "New password must be at least 8 characters."
        }), 400

    if new_password != confirm_password:
        return jsonify({
            "error": "New passwords do not match."
        }), 400

    connection = db()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if user is None:
        connection.close()
        session.clear()

        return jsonify({
            "error": "User account not found."
        }), 404

    if not check_password_hash(
        user["password_hash"],
        current_password
    ):
        connection.close()

        return jsonify({
            "error": "Current password is incorrect."
        }), 401

    connection.execute("""
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    """, (
        generate_password_hash(new_password),
        session["user_id"]
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Password changed successfully."
    })


@app.route("/api/session", methods=["GET"])
def get_session():

    if "user_id" not in session:
        return jsonify({
            "authenticated": False
        })

    return jsonify({
        "authenticated": True,
        "username": session.get("username")
    })


@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "message": "Logged out successfully."
    })


# =========================================================
# EXPENSES
# =========================================================

@app.route("/api/expenses", methods=["GET"])
@login_required
def get_expenses():

    connection = db()

    rows = connection.execute("""
        SELECT *
        FROM expenses
        WHERE user_id = ?
        ORDER BY expense_date DESC, id DESC
    """, (session["user_id"],)).fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route("/api/expenses", methods=["POST"])
@login_required
def add_expense():

    data = request.get_json(silent=True) or {}

    amount = data.get("amount")
    category = str(
        data.get("category", "")
    ).strip()

    description = str(
        data.get("description", "")
    ).strip()

    expense_date = str(
        data.get("expense_date", "")
    ).strip()

    if amount is None or not category or not expense_date:
        return jsonify({
            "error": "Amount, category and date are required."
        }), 400

    try:
        amount = float(amount)

        if amount <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Amount must be a positive number."
        }), 400

    connection = db()

    cursor = connection.execute("""
        INSERT INTO expenses
        (
            amount,
            category,
            description,
            expense_date,
            created_at,
            user_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        amount,
        category,
        description,
        expense_date,
        datetime.now().isoformat(),
        session["user_id"]
    ))

    connection.commit()

    expense_id = cursor.lastrowid

    connection.close()

    return jsonify({
        "message": "Expense added successfully.",
        "id": expense_id
    }), 201


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):

    data = request.get_json(silent=True) or {}

    amount = data.get("amount")
    category = str(
        data.get("category", "")
    ).strip()

    description = str(
        data.get("description", "")
    ).strip()

    expense_date = str(
        data.get("expense_date", "")
    ).strip()

    if amount is None or not category or not expense_date:
        return jsonify({
            "error": "Amount, category and date are required."
        }), 400

    try:
        amount = float(amount)

        if amount <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Amount must be a positive number."
        }), 400

    connection = db()

    cursor = connection.execute("""
        UPDATE expenses
        SET
            amount = ?,
            category = ?,
            description = ?,
            expense_date = ?
        WHERE id = ?
        AND user_id = ?
    """, (
        amount,
        category,
        description,
        expense_date,
        expense_id,
        session["user_id"]
    ))

    connection.commit()

    changed = cursor.rowcount

    connection.close()

    if changed == 0:
        return jsonify({
            "error": "Expense not found."
        }), 404

    return jsonify({
        "message": "Expense updated successfully."
    })


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):

    connection = db()

    cursor = connection.execute("""
        DELETE FROM expenses
        WHERE id = ?
        AND user_id = ?
    """, (
        expense_id,
        session["user_id"]
    ))

    connection.commit()

    deleted = cursor.rowcount

    connection.close()

    if deleted == 0:
        return jsonify({
            "error": "Expense not found."
        }), 404

    return jsonify({
        "message": "Expense deleted successfully."
    })


# =========================================================
# STATISTICS
# =========================================================

@app.route("/api/stats", methods=["GET"])
@login_required
def stats():

    connection = db()

    user_id = session["user_id"]

    total = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")

    today_total = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND expense_date = ?
    """, (
        user_id,
        today
    )).fetchone()[0]

    current_month = datetime.now().strftime("%Y-%m")

    month_total = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND substr(expense_date, 1, 7) = ?
    """, (
        user_id,
        current_month
    )).fetchone()[0]

    count = connection.execute("""
        SELECT COUNT(*)
        FROM expenses
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    categories = connection.execute("""
        SELECT
            category,
            COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
    """, (user_id,)).fetchall()

    connection.close()

    return jsonify({
        "total": total,
        "today": today_total,
        "month": month_total,
        "count": count,
        "categories": [
            {
                "category": row["category"],
                "total": row["total"]
            }
            for row in categories
        ]
    })


# =========================================================
# BUDGET
# =========================================================

@app.route("/api/budget", methods=["GET"])
@login_required
def get_budget():

    connection = db()

    row = connection.execute("""
        SELECT monthly_budget
        FROM settings
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    connection.close()

    budget = row["monthly_budget"] if row else 0

    return jsonify({
        "monthly_budget": budget
    })


@app.route("/api/budget", methods=["PUT"])
@login_required
def update_budget():

    data = request.get_json(silent=True) or {}

    budget = data.get("monthly_budget")

    try:
        budget = float(budget)

        if budget < 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "error": "Budget must be a valid positive number."
        }), 400

    connection = db()

    connection.execute("""
        INSERT INTO settings
        (user_id, monthly_budget)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET monthly_budget = excluded.monthly_budget
    """, (
        session["user_id"],
        budget
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Budget updated successfully.",
        "monthly_budget": budget
    })


if __name__ == "__main__":
    setup_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
