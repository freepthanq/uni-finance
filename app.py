import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import apology, login_required, lookup, usd



# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
uri = os.getenv("postgres://zmvjimixdkgkyw:b1df9da7ccdaaab21966f7a1d269e20268660a9a9c9d3a03a3eebfefbc4c59c0@ec2-34-242-84-130.eu-west-1.compute.amazonaws.com:5432/dahj2l4vj5gbfc")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    stocks_temp = db.execute("SELECT * FROM stocks WHERE user_id = ? AND amount > 0 ORDER BY symbol", session["user_id"])
    stocks = []
    for i in range(len(stocks_temp)):
        share = lookup(stocks_temp[i]["symbol"])
        stocks.append({"symbol": share["symbol"], "name": share["name"], "shares": stocks_temp[i]["amount"], 
                       "price": share["price"], "total": share["price"] * stocks_temp[i]["amount"]})

    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    total = cash
    for j in stocks:
        total += j["total"]

    for k in stocks:
        k["price"] = usd(k["price"])
        k["total"] = usd(k["total"])

    return render_template("index.html", stocks=stocks, cash=usd(round(cash, 1)), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # If one or more fields are empty -> raise an error
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("You must fill all the fields!", 400)

        # Checking whether number is correct
        amount = request.form.get("shares")
        try:
            float(amount)
        except ValueError:
            return apology("Invalid amount of shares", 400)
        amount = float(amount)
        if amount != int(amount) or amount <= 0:
            return apology("Invalid amount of shares", 400)
        
        # Getting the symbol from the form
        symbol = request.form.get("symbol").upper()

        # Looking it up
        share = lookup(symbol)

        # If there is no such result -> raise an error
        if share == None:
            return apology("Incorrect share symbol :(", 400)

        # Get the price, amount from the form and cash from users table
        price = float(share["price"])
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        # If there is less cash than needed -> raise an error
        needed_cash = price * amount
        if cash < needed_cash:
            return apology("Not enough cash :(", 400)
        
        # Looking for given share in the case
        case = db.execute("SELECT * FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"],  symbol)

        # If there is no such one -> insert a row
        if len(case) != 1:
            db.execute("INSERT INTO stocks (user_id, symbol, amount) VALUES (?, ?, ?)", session["user_id"], symbol, amount)
        else:
            # If there is -> update to a new value
            amount_in = db.execute("SELECT amount FROM stocks WHERE user_id = ? AND symbol = ?", 
                                   session["user_id"], symbol)[0]["amount"]
            db.execute("UPDATE stocks SET amount = ? WHERE user_id = ? AND symbol = ?", 
                       amount_in + amount, session["user_id"], symbol)

        # Lower the cash amount 
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - needed_cash, session["user_id"])

        # Insert a row into history table
        db.execute("INSERT INTO history (user_id, symbol, amount, date, price) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], symbol, amount, str(datetime.now()).split('.')[0], usd(price))

        # Show a message
        if amount == 1:
            flash(f"Bought {int(amount)} share ({symbol})!")
        else:
            flash(f"Bought {int(amount)} shares ({symbol})!")

        return redirect(url_for('index'))
    
    # Get method 
    return render_template("buy.html")
    

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # Post method
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        quoted = lookup(symbol)

        if quoted == None:
            return apology(f"{symbol} stock is not found", 400)
        return render_template("quote.html", quoted=f'A share of {quoted["name"]} ({quoted["symbol"]}) costs {usd(float(quoted["price"]))}')

    # Get method
    return render_template("quote.html")
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Post method
    if request.method == "POST":
        login = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # If some fiels is blank -> raise an apology
        if not login or not password or not confirmation:
            return apology("You must fill all the fields!", 400)

        # If passwords don't match -> raise an apology
        if password != confirmation:
            return apology("Passwords don't match :(", 400)

        # If username is already in db -> raise an apology
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("This username is taken :(", 400)
        
        # Else inert user in db
        db.execute("INSERT INTO users (username, hash, cash) VALUES(?, ?, 10000)", login, generate_password_hash(password))

        # Redirect user to home page
        return redirect("/")
    
    # Get method
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # Post method
    if request.method == "POST":
        # Check whether all fields are filled
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("You must fill all the fields!", 400)

        # Checking whether number is correct
        amount = request.form.get("shares")
        try:
            float(amount)
        except ValueError:
            return apology("Invalid amount of shares", 400)
        amount = float(amount)
        if amount != int(amount) or amount <= 0:
            return apology("Invalid amount of shares", 400)
        
        # Getting the symbol from the form
        symbol = request.values.get("symbol")

        # Getting list of symbols that user has 
        shares_temp = db.execute("SELECT symbol FROM stocks WHERE user_id = ? AND amount > 0 ORDER BY symbol", session["user_id"])
        shares = [shares_temp[i]["symbol"] for i in range(len(shares_temp))]

        # If symbol given is not in user's portfolio -> raise an apology 
        if symbol not in shares:
            return apology("You don't have shares with the symbol given!", 400)

        # Check whether user has needed amount of shares 
        if amount > db.execute("SELECT amount FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)[0]["amount"]:
            return apology("You don't have enough shares to sell :(", 400)

        # Perform the sale
        amount_in = db.execute("SELECT amount FROM stocks WHERE user_id = ? AND symbol = ?",
                               session["user_id"], symbol)[0]["amount"]
        db.execute("UPDATE stocks SET amount = ? WHERE user_id = ? AND symbol = ?", amount_in - amount, session["user_id"], symbol)

        # Raise the cash amount
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        share = lookup(symbol)
        price = float(share["price"])
        add_cash = price * amount
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + add_cash, session["user_id"])

        # Insert a row into history table
        db.execute("INSERT INTO history (user_id, symbol, amount, date, price) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], symbol, -amount, str(datetime.now()).split('.')[0], usd(price))

        # Show a message
        if amount == 1:
            flash(f"Sold {int(amount)} share ({symbol})!")
        else:
            flash(f"Sold {int(amount)} shares ({symbol})!")

        return redirect(url_for('index'))

    # Get method
    shares_temp = db.execute("SELECT symbol FROM stocks WHERE user_id = ? AND amount > 0 ORDER BY symbol", session["user_id"])
    shares = [shares_temp[i]["symbol"] for i in range(len(shares_temp))]
    return render_template("sell.html", shares=shares)


@app.route("/sell_all")
@login_required
def sell_all():
    # Getting list of symbols that user has 
    shares_temp = db.execute("SELECT symbol FROM stocks WHERE user_id = ? ORDER BY symbol", session["user_id"])
    shares = [shares_temp[i]["symbol"] for i in range(len(shares_temp))]

    for i in shares:
        # Get the amount
        amount = db.execute("SELECT amount FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"], i)[0]["amount"]

        # Set the amount in portfolio to zero
        db.execute("UPDATE stocks SET amount = ? WHERE user_id = ? AND symbol = ?", 0, session["user_id"], i)

        # Raise the cash amount
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        share = lookup(i)
        price = float(share["price"])
        add_cash = price * amount
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + add_cash, session["user_id"])

        # Insert a row into history table
        db.execute("INSERT INTO history (user_id, symbol, amount, date, price) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], i, -amount, str(datetime.now()).split('.')[0], usd(price))

    # Show the message
    flash("Sold all!")
    return redirect("/")
