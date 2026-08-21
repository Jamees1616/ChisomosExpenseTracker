from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB = "chisomo_expenses.db"


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
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    connection = db()

    rows = connection.execute("""
        SELECT *
        FROM expenses
        ORDER BY expense_date DESC, id DESC
    """).fetchall()

    connection.close()

    return jsonify([dict(row) for row in rows])


@app.route("/api/expenses", methods=["POST"])
def add_expense():

    data = request.get_json()

    amount = data.get("amount")
    category = data.get("category")
    description = data.get("description", "")
    expense_date = data.get("expense_date")

    if not amount or not category or not expense_date:
        return jsonify({
            "error": "Amount, category and date are required."
        }), 400

    try:
        amount = float(amount)

        if amount <= 0:
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid amount."
        }), 400

    connection = db()

    connection.execute("""
        INSERT INTO expenses
        (amount, category, description, expense_date, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        amount,
        category,
        description,
        expense_date,
        datetime.now().isoformat()
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Expense added successfully."
    }), 201


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def edit_expense(expense_id):

    data = request.get_json()

    amount = data.get("amount")
    category = data.get("category")
    description = data.get("description", "")
    expense_date = data.get("expense_date")

    if not amount or not category or not expense_date:
        return jsonify({
            "error": "Required fields are missing."
        }), 400

    try:
        amount = float(amount)

        if amount <= 0:
            raise ValueError

    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid amount."
        }), 400

    connection = db()

    result = connection.execute("""
        UPDATE expenses
        SET amount = ?,
            category = ?,
            description = ?,
            expense_date = ?
        WHERE id = ?
    """, (
        amount,
        category,
        description,
        expense_date,
        expense_id
    ))

    connection.commit()
    connection.close()

    if result.rowcount == 0:
        return jsonify({
            "error": "Expense not found."
        }), 404

    return jsonify({
        "message": "Expense updated successfully."
    })


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):

    connection = db()

    result = connection.execute(
        "DELETE FROM expenses WHERE id = ?",
        (expense_id,)
    )

    connection.commit()
    connection.close()

    if result.rowcount == 0:
        return jsonify({
            "error": "Expense not found."
        }), 404

    return jsonify({
        "message": "Expense deleted successfully."
    })




@app.route("/api/stats", methods=["GET"])
def get_stats():

    connection = db()

    total = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
    """).fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")

    today_total = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE expense_date = ?
    """, (today,)).fetchone()[0]

    month = datetime.now().strftime("%Y-%m")

    month_total = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE substr(expense_date, 1, 7) = ?
    """, (month,)).fetchone()[0]

    count = connection.execute("""
        SELECT COUNT(*)
        FROM expenses
    """).fetchone()[0]

    categories = connection.execute("""
        SELECT
            category,
            SUM(amount) AS total
        FROM expenses
        GROUP BY category
        ORDER BY total DESC
    """).fetchall()

    connection.close()

    return jsonify({
        "total": total,
        "today": today_total,
        "month": month_total,
        "count": count,
        "categories": [
            dict(row)
            for row in categories
        ]
    })

@app.route("/api/budget", methods=["GET"])
def get_budget():

    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            monthly_budget REAL DEFAULT 0
        )
    """)

    connection.execute("""
        INSERT OR IGNORE INTO settings
        (id, monthly_budget)
        VALUES (1, 0)
    """)

    connection.commit()

    row = connection.execute("""
        SELECT monthly_budget
        FROM settings
        WHERE id = 1
    """).fetchone()

    connection.close()

    return jsonify({
        "monthly_budget": row["monthly_budget"]
    })


@app.route("/api/budget", methods=["PUT"])
def update_budget():

    data = request.get_json()

    try:
        budget = float(
            data.get("monthly_budget", 0)
        )

        if budget < 0:
            raise ValueError

    except (ValueError, TypeError):

        return jsonify({
            "error": "Invalid budget."
        }), 400


    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            monthly_budget REAL DEFAULT 0
        )
    """)

    connection.execute("""
        INSERT OR IGNORE INTO settings
        (id, monthly_budget)
        VALUES (1, 0)
    """)

    connection.execute("""
        UPDATE settings
        SET monthly_budget = ?
        WHERE id = 1
    """, (budget,))

    connection.commit()
    connection.close()

    return jsonify({
        "message": "Budget updated successfully."
    })


if __name__ == "__main__":
    setup_database()
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
