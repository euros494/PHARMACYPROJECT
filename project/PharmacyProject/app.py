"""
Pharmacy Medicine Ordering System
A college project built with Python Flask and SQLite.

Run on Windows:
    pip install -r requirements.txt
    py app.py

Then open http://127.0.0.1:5000 in your browser.
"""

import os
import sqlite3
import secrets
import hashlib
import hmac
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "pharmacy.db")

# Secret key for Flask sessions. In a real app, keep this in an environment variable.
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key-in-production")

# Admin account. Set your own username and password using environment variables,
# or edit these two lines before running the app for the first time.
# Example (Windows CMD):
#     set ADMIN_USERNAME=myadmin
#     set ADMIN_PASSWORD=mypassword
#     py app.py
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Open a new SQLite connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create all tables and insert sample data if they don't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_ref TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            medicine_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Sample medicines (only inserted the first time)
    cur.execute("SELECT COUNT(*) AS c FROM medicines")
    if cur.fetchone()["c"] == 0:
        sample_medicines = [
            ("Paracetamol 500mg", 2.50,
             "Sample medicine for mild pain and fever relief. College demo product.", 1),
            ("Amoxicillin 250mg", 8.75,
             "Sample antibiotic for common infections. College demo product.", 1),
            ("Cough Syrup 100ml", 5.40,
             "Sample cough relief syrup. College demo product.", 1),
        ]
        cur.executemany(
            "INSERT INTO medicines (name, price, description, available) VALUES (?, ?, ?, ?)",
            sample_medicines
        )

    # Sample staff (only inserted the first time)
    cur.execute("SELECT COUNT(*) AS c FROM staff")
    if cur.fetchone()["c"] == 0:
        sample_staff = [
            ("Dr. John Smith", "john.smith@demo-college.edu", "555-0101", "Pharmacist"),
            ("Mary Johnson", "mary.johnson@demo-college.edu", "555-0102", "Cashier"),
        ]
        cur.executemany(
            "INSERT INTO staff (name, email, phone, role) VALUES (?, ?, ?, ?)",
            sample_staff
        )

    conn.commit()
    conn.close()


with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# Password hashing (SHA-256 with a random salt - simple and beginner friendly)
# ---------------------------------------------------------------------------

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def check_password(password, stored):
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    test = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(test, digest)


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

def csrf_token():
    """Generate (and cache in session) a CSRF token for the current user."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


@app.context_processor
def inject_template_globals():
    """Make csrf_token, current customer and admin status available in every template."""
    return {
        "csrf_token": csrf_token,
        "current_customer": get_current_customer(),
        "is_admin": session.get("is_admin", False),
    }


def validate_csrf():
    """Compare the submitted CSRF token with the one stored in the session."""
    token = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not token or not expected or not hmac.compare_digest(token, expected):
        flash("Security check failed. Please try again.", "error")
        return False
    return True


# ---------------------------------------------------------------------------
# Session helpers and access control
# ---------------------------------------------------------------------------

def get_current_customer():
    customer_id = session.get("customer_id")
    if not customer_id:
        return None
    db = get_db()
    return db.execute(
        "SELECT id, full_name, email, phone, created_at FROM customers WHERE id = ?",
        (customer_id,)
    ).fetchone()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "customer_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Cart helpers (stored in the Flask session)
# ---------------------------------------------------------------------------

def get_cart():
    return session.get("cart", {})


def save_cart(cart):
    session["cart"] = cart


def cart_count():
    return sum(int(q) for q in get_cart().values())


@app.context_processor
def inject_cart_count():
    return {"cart_count": cart_count()}


def cart_details():
    """Return (items_list, total) for the current session cart."""
    cart = get_cart()
    if not cart:
        return [], 0.0
    db = get_db()
    items = []
    total = 0.0
    for med_id_str, qty in cart.items():
        med = db.execute("SELECT * FROM medicines WHERE id = ?", (med_id_str,)).fetchone()
        if med:
            line_total = med["price"] * qty
            total += line_total
            items.append({
                "id": med["id"],
                "name": med["name"],
                "price": med["price"],
                "quantity": qty,
                "line_total": line_total,
            })
    return items, total


# ---------------------------------------------------------------------------
# Customer-facing routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    db = get_db()
    medicines = db.execute(
        "SELECT * FROM medicines ORDER BY id LIMIT 3"
    ).fetchall()
    return render_template("home.html", medicines=medicines)


@app.route("/products")
def products():
    db = get_db()
    medicines = db.execute("SELECT * FROM medicines ORDER BY id").fetchall()
    items, total = cart_details()
    return render_template("products.html", medicines=medicines, cart_items=items, cart_total=total)


@app.route("/cart")
def cart():
    items, total = cart_details()
    return render_template("cart.html", cart_items=items, cart_total=total)


@app.route("/add-to-cart/<int:medicine_id>", methods=["POST"])
def add_to_cart(medicine_id):
    if not validate_csrf():
        return redirect(request.referrer or url_for("products"))
    db = get_db()
    med = db.execute("SELECT id FROM medicines WHERE id = ?", (medicine_id,)).fetchone()
    if not med:
        flash("Medicine not found.", "error")
        return redirect(url_for("products"))
    cart = get_cart()
    key = str(medicine_id)
    cart[key] = cart.get(key, 0) + 1
    save_cart(cart)
    flash("Added to cart.", "success")
    return redirect(request.referrer or url_for("products"))


@app.route("/update-cart", methods=["POST"])
def update_cart():
    if not validate_csrf():
        return redirect(url_for("cart"))
    cart = get_cart()
    for key, value in request.form.items():
        if key.startswith("qty_"):
            med_id = key[4:]
            try:
                qty = int(value)
            except ValueError:
                continue
            if qty <= 0:
                cart.pop(med_id, None)
            else:
                cart[med_id] = qty
    save_cart(cart)
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/remove-from-cart/<int:medicine_id>", methods=["POST"])
def remove_from_cart(medicine_id):
    if not validate_csrf():
        return redirect(url_for("cart"))
    cart = get_cart()
    cart.pop(str(medicine_id), None)
    save_cart(cart)
    flash("Item removed from cart.", "success")
    return redirect(url_for("cart"))


@app.route("/clear-cart", methods=["POST"])
def clear_cart():
    if not validate_csrf():
        return redirect(url_for("cart"))
    save_cart({})
    flash("Cart cleared.", "success")
    return redirect(url_for("cart"))


# ---------------------------------------------------------------------------
# Customer registration and login
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("register"))
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not password:
            errors.append("Password is required.")
        if password and password != confirm:
            errors.append("Passwords do not match.")
        if len(password) and len(password) < 6:
            errors.append("Password must be at least 6 characters long.")

        db = get_db()
        if email:
            existing = db.execute("SELECT id FROM customers WHERE email = ?", (email,)).fetchone()
            if existing:
                errors.append("An account with that email already exists.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html",
                                   full_name=full_name, email=email, phone=phone)

        db.execute(
            "INSERT INTO customers (full_name, email, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (full_name, email, phone, hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("login"))
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        customer = db.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
        if not customer or not check_password(password, customer["password_hash"]):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session["csrf_token"] = secrets.token_hex(32)
        session["customer_id"] = customer["id"]
        flash(f"Welcome, {customer['full_name']}!", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Checkout and orders
# ---------------------------------------------------------------------------

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items, total = cart_details()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("products"))

    customer = get_current_customer()

    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("checkout"))
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        errors = []
        if not customer_name:
            errors.append("Your name is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not address:
            errors.append("Delivery address is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("checkout.html", cart_items=items, cart_total=total,
                                   customer_name=customer_name, phone=phone, address=address)

        db = get_db()
        order_ref = "ORD-" + secrets.token_hex(4).upper()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = db.execute(
            "INSERT INTO orders (order_ref, customer_id, customer_name, phone, address, total, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)",
            (order_ref, customer["id"], customer_name, phone, address, total, now)
        )
        order_id = cur.lastrowid
        for item in items:
            db.execute(
                "INSERT INTO order_items (order_id, medicine_id, name, price, quantity) VALUES (?, ?, ?, ?, ?)",
                (order_id, item["id"], item["name"], item["price"], item["quantity"])
            )
        db.commit()
        save_cart({})
        return redirect(url_for("order_confirmation", order_ref=order_ref))

    return render_template("checkout.html", cart_items=items, cart_total=total,
                           customer_name=customer["full_name"], phone=customer["phone"], address="")


@app.route("/order-confirmation/<order_ref>")
@login_required
def order_confirmation(order_ref):
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE order_ref = ? AND customer_id = ?",
        (order_ref, session["customer_id"])
    ).fetchone()
    if not order:
        abort(404)
    items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],)).fetchall()
    return render_template("order_confirmation.html", order=order, items=items)


@app.route("/my-orders")
@login_required
def my_orders():
    db = get_db()
    orders = db.execute(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC",
        (session["customer_id"],)
    ).fetchall()
    return render_template("my_orders.html", orders=orders)


@app.route("/my-orders/<int:order_id>")
@login_required
def my_order_detail(order_id):
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND customer_id = ?",
        (order_id, session["customer_id"])
    ).fetchone()
    if not order:
        abort(404)
    items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],)).fetchall()
    return render_template("order_confirmation.html", order=order, items=items)


# ---------------------------------------------------------------------------
# Support and Policies
# ---------------------------------------------------------------------------

@app.route("/support", methods=["GET", "POST"])
def support():
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("support"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if not subject:
            errors.append("Subject is required.")
        if not message:
            errors.append("Message is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("support.html", name=name, email=email, subject=subject, message=message)

        db = get_db()
        db.execute(
            "INSERT INTO support_messages (name, email, subject, message, created_at, resolved) VALUES (?, ?, ?, ?, ?, 0)",
            (name, email, subject, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()
        flash("Your message has been sent. We will get back to you soon.", "success")
        return redirect(url_for("support"))

    return render_template("support.html")


@app.route("/policies")
def policies():
    return render_template("policies.html")


# ---------------------------------------------------------------------------
# Admin login (separate from customer login)
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("admin_login"))
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["csrf_token"] = secrets.token_hex(32)
            session["is_admin"] = True
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
        return render_template("admin_login.html", username=username)

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Admin logged out.", "success")
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------------------------
# Admin dashboard and sections
# ---------------------------------------------------------------------------

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    total_orders = db.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
    pending_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE status = 'Pending'").fetchone()["c"]
    completed_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE status = 'Completed'").fetchone()["c"]
    total_customers = db.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
    total_staff = db.execute("SELECT COUNT(*) AS c FROM staff").fetchone()["c"]

    pending_orders_list = db.execute(
        "SELECT * FROM orders WHERE status = 'Pending' ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        total_customers=total_customers,
        total_staff=total_staff,
        pending_orders_list=pending_orders_list
    )


@app.route("/admin/orders")
@admin_required
def admin_orders():
    db = get_db()
    status_filter = request.args.get("status", "")
    if status_filter:
        orders = db.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
            (status_filter,)
        ).fetchall()
    else:
        orders = db.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    statuses = ["Pending", "Processing", "Ready for Delivery", "Completed", "Cancelled"]
    return render_template("admin_orders.html", orders=orders, statuses=statuses,
                           current_filter=status_filter)


@app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def admin_order_detail(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        abort(404)

    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("admin_order_detail", order_id=order_id))
        new_status = request.form.get("status", "").strip()
        valid_statuses = ["Pending", "Processing", "Ready for Delivery", "Completed", "Cancelled"]
        if new_status not in valid_statuses:
            flash("Invalid status.", "error")
            return redirect(url_for("admin_order_detail", order_id=order_id))
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        db.commit()
        flash("Order status updated.", "success")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],)).fetchall()
    statuses = ["Pending", "Processing", "Ready for Delivery", "Completed", "Cancelled"]
    return render_template("admin_order_detail.html", order=order, items=items, statuses=statuses)


@app.route("/admin/staff", methods=["GET", "POST"])
@admin_required
def admin_staff():
    db = get_db()
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("admin_staff"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if not phone:
            errors.append("Phone is required.")
        if not role:
            errors.append("Job role is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("admin_staff"))

        db.execute(
            "INSERT INTO staff (name, email, phone, role) VALUES (?, ?, ?, ?)",
            (name, email, phone, role)
        )
        db.commit()
        flash("Staff member added.", "success")
        return redirect(url_for("admin_staff"))

    staff = db.execute("SELECT * FROM staff ORDER BY id").fetchall()
    return render_template("admin_staff.html", staff=staff)


@app.route("/admin/staff/<int:staff_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_staff_edit(staff_id):
    db = get_db()
    member = db.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if not member:
        abort(404)

    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("admin_staff_edit", staff_id=staff_id))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if not phone:
            errors.append("Phone is required.")
        if not role:
            errors.append("Job role is required.")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("admin_staff_edit", staff_id=staff_id))

        db.execute(
            "UPDATE staff SET name = ?, email = ?, phone = ?, role = ? WHERE id = ?",
            (name, email, phone, role, staff_id)
        )
        db.commit()
        flash("Staff member updated.", "success")
        return redirect(url_for("admin_staff"))

    return render_template("admin_staff_edit.html", member=member)


@app.route("/admin/staff/<int:staff_id>/delete", methods=["POST"])
@admin_required
def admin_staff_delete(staff_id):
    if not validate_csrf():
        return redirect(url_for("admin_staff"))
    db = get_db()
    db.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
    db.commit()
    flash("Staff member removed.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin/customers")
@admin_required
def admin_customers():
    db = get_db()
    customers = db.execute(
        "SELECT id, full_name, email, phone, created_at FROM customers ORDER BY created_at DESC"
    ).fetchall()
    return render_template("admin_customers.html", customers=customers)


@app.route("/admin/support")
@admin_required
def admin_support():
    db = get_db()
    messages = db.execute(
        "SELECT * FROM support_messages ORDER BY created_at DESC"
    ).fetchall()
    return render_template("admin_support.html", messages=messages)


@app.route("/admin/support/<int:message_id>/resolve", methods=["POST"])
@admin_required
def admin_support_resolve(message_id):
    if not validate_csrf():
        return redirect(url_for("admin_support"))
    db = get_db()
    db.execute("UPDATE support_messages SET resolved = 1 WHERE id = ?", (message_id,))
    db.commit()
    flash("Message marked as resolved.", "success")
    return redirect(url_for("admin_support"))


@app.route("/admin/medicines", methods=["GET", "POST"])
@admin_required
def admin_medicines():
    db = get_db()
    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("admin_medicines"))
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        available = request.form.get("available", "1")

        errors = []
        if not name:
            errors.append("Medicine name is required.")
        try:
            price = float(price)
            if price < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            errors.append("Price must be a valid number.")
            price = 0.0
        if not description:
            errors.append("Description is required.")

        available = 1 if available == "1" else 0

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("admin_medicines"))

        db.execute(
            "INSERT INTO medicines (name, price, description, available) VALUES (?, ?, ?, ?)",
            (name, price, description, available)
        )
        db.commit()
        flash("Medicine added.", "success")
        return redirect(url_for("admin_medicines"))

    medicines = db.execute("SELECT * FROM medicines ORDER BY id").fetchall()
    return render_template("admin_medicines.html", medicines=medicines)


@app.route("/admin/medicines/<int:medicine_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_medicine_edit(medicine_id):
    db = get_db()
    medicine = db.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,)).fetchone()
    if not medicine:
        abort(404)

    if request.method == "POST":
        if not validate_csrf():
            return redirect(url_for("admin_medicine_edit", medicine_id=medicine_id))
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        available = request.form.get("available", "1")

        errors = []
        if not name:
            errors.append("Medicine name is required.")
        try:
            price = float(price)
            if price < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            errors.append("Price must be a valid number.")
            price = 0.0
        if not description:
            errors.append("Description is required.")

        available = 1 if available == "1" else 0

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("admin_medicine_edit", medicine_id=medicine_id))

        db.execute(
            "UPDATE medicines SET name = ?, price = ?, description = ?, available = ? WHERE id = ?",
            (name, price, description, available, medicine_id)
        )
        db.commit()
        flash("Medicine updated.", "success")
        return redirect(url_for("admin_medicines"))

    return render_template("admin_medicine_edit.html", medicine=medicine)


@app.route("/admin/medicines/<int:medicine_id>/delete", methods=["POST"])
@admin_required
def admin_medicine_delete(medicine_id):
    if not validate_csrf():
        return redirect(url_for("admin_medicines"))
    db = get_db()
    db.execute("DELETE FROM medicines WHERE id = ?", (medicine_id,))
    db.commit()
    flash("Medicine removed.", "success")
    return redirect(url_for("admin_medicines"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           message="The page you were looking for could not be found."), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403,
                           message="You do not have permission to view this page."), 403


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("Starting Pharmacy Medicine Ordering System...")
    print("Open http://127.0.0.1:5000 in your browser.")
    print(f"Admin login (default): username='{ADMIN_USERNAME}', password='{ADMIN_PASSWORD}'")
    print("Change these using ADMIN_USERNAME and ADMIN_PASSWORD environment variables.")
    app.run(debug=True, host="127.0.0.1", port=5000)
