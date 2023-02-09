import os
import requests
import urllib.parse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

plt.rc('figure', max_open_warning=0)
from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


# Create a plot with the predicted prices of a chosen stock share
def make_predictions(symbol):
    data = pd.read_csv('data/predicted_stock_price.csv')
    days = np.array(data['day'])
    prices = np.array(data[symbol])
    fig, ax = plt.subplots()
    ax.plot(days, prices, label=f'price of {symbol} in $')
    ax.grid()
    ax.set_xlabel('day')
    ax.set_ylabel('price in $')
    plt.title(f'Predicted price of {symbol}')
    plt.savefig(f'static/{symbol}.png')
    plt.clf()
    return render_template("predict.html", img=symbol)


