# Pharmacy Medicine Ordering System

A simple college project built with **Python Flask**, **HTML/CSS/JavaScript**, and **SQLite**.

> **Important:** This is a student demonstration project. It is **not a real pharmacy**.
> The medicines are fictional sample data. No real payments or deliveries happen.

---

## Features

### Customer website
- Home page with welcome message and 3 sample medicines
- Products page with availability and Add to Cart buttons
- Shopping cart with quantity changes, item removal and total price
- Customer registration with hashed passwords
- Customer login and logout using secure Flask sessions
- Order checkout with delivery details and unique order IDs
- Order confirmation page and "My Orders" page with order status
- Support contact form (saved to the database for the admin)
- Policies and Terms of Service page

### Admin area (separate login)
- Admin login link next to the customer Login link
- Admin dashboard with summary cards:
  - Total orders
  - Pending orders
  - Completed orders
  - Registered customers
  - Total staff members
- Order Management: view all orders, filter by status, view details, update status
- Staff Management: add, edit and remove staff members
- Customer Management: view registered customers (no passwords shown)
- Support Messages: view messages and mark them as resolved
- Medicine Management: add, edit and remove sample medicines

### Security
- Passwords are hashed with a random salt (never stored as plain text)
- Flask sessions keep the customer logged in
- Role-based access checks protect all admin pages
- CSRF tokens protect every form
- Parameterized SQL queries prevent SQL injection
- Form inputs are validated on the server
- No real payment information is handled

---

## Project structure

```
PharmacyProject/
    app.py
    requirements.txt
    README.md
    pharmacy.db          (created automatically on first run)
    templates/
        base.html
        home.html
        products.html
        register.html
        login.html
        admin_login.html
        cart.html
        checkout.html
        order_confirmation.html
        my_orders.html
        support.html
        policies.html
        admin_dashboard.html
        admin_orders.html
        admin_order_detail.html
        admin_staff.html
        admin_staff_edit.html
        admin_customers.html
        admin_support.html
        admin_medicines.html
        admin_medicine_edit.html
        error.html
    static/
        style.css
        script.js
```

---

## How to install and run (Windows)

### 1. Install Python
Make sure **Python 3.10 or newer** is installed. Check by opening Command Prompt and running:

```
py --version
```

If it is not installed, download it from https://www.python.org/downloads/ and tick
**"Add Python to PATH"** during installation.

### 2. Open the project folder
Unzip/extract the `PharmacyProject` folder and open it in **Visual Studio Code**.

Open a terminal inside VS Code (`Terminal > New Terminal`) or use Command Prompt
and navigate to the project folder, for example:

```
cd C:\Users\YourName\Downloads\PharmacyProject
```

### 3. (Recommended) Create a virtual environment

```
py -m venv venv
venv\Scripts\activate
```

### 4. Install dependencies

```
pip install -r requirements.txt
```

### 5. Set your own admin username and password (optional but recommended)

The default admin account is:

- Username: `admin`
- Password: `admin123`

To change it, set environment variables **before** running the app.
In Command Prompt (CMD):

```
set ADMIN_USERNAME=myadmin
set ADMIN_PASSWORD=mypassword
```

Then run the app in the **same** window.

You can also edit the two lines near the top of `app.py`:

```python
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
```

Admin credentials are **never** shown on the public website.

### 6. Run the application

```
py app.py
```

### 7. Open it in your browser
Go to:

```
http://127.0.0.1:5000
```

The database file `pharmacy.db` and the sample data are created automatically
the first time you run the app.

---

## Default accounts

| Role     | Username / Email | Password   |
|----------|------------------|------------|
| Admin    | `admin`          | `admin123` |
| Customer | (register your own) | (your own) |

> Change the admin credentials before demonstrating the project (see step 5 above).

---

## Notes
- All medicines are **sample/fictional data** for demonstration only.
- No real payments are processed.
- The support email shown on the website is a placeholder you can change later.
- This project is intended to run locally on Windows for a college demonstration.

---

## Troubleshooting

**`py` command not found**
Use `python` instead of `py`, or reinstall Python and tick "Add Python to PATH".

**Port 5000 already in use**
Edit the last line of `app.py` and change the port, for example:

```python
app.run(debug=True, host="127.0.0.1", port=5001)
```

Then open `http://127.0.0.1:5001`.

**Want to reset the database**
Delete the `pharmacy.db` file and run `py app.py` again. It will be recreated
with fresh sample data.
