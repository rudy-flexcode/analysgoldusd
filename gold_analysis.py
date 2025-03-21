
import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
import requests
from time import time

load_dotenv()
app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
gold_symbol = "GLD"
usd_symbol = "UUP"

cache = {}
cache_time = 0

def get_price(symbol):
    global cache, cache_time
    current_time = time()

    if symbol in cache and current_time - cache_time < 60:
        return cache[symbol]

    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'price' in data:
        cache[symbol] = float(data['price'])
        cache_time = current_time
        return cache[symbol]
    else:
        return None

def get_rsi(symbol):
    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1min&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'values' in data:
        latest_rsi = data['values'][0]['rsi']
        return float(latest_rsi)
    return None

def get_signals():
    gold_price = get_price(gold_symbol)
    usd_price = get_price(usd_symbol)
    rsi_value = get_rsi(gold_symbol)

    if gold_price is not None and usd_price is not None:
        if gold_price > usd_price:
            signal = "Acheter"
        elif gold_price < usd_price:
            signal = "Vendre"
        else:
            signal = "Neutre"
    else:
        signal = "Indisponible"

    if rsi_value is not None:
        if rsi_value > 70:
            rsi_signal = "Vendre"
        elif rsi_value < 30:
            rsi_signal = "Acheter"
        else:
            rsi_signal = "Neutre"
    else:
        rsi_signal = "Indisponible"

    return {
        'signal': signal,
        'gold_price': gold_price,
        'usd_price': usd_price,
        'rsi': rsi_value,
        'rsi_signal': rsi_signal
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/refresh', methods=['GET'])
def refresh_data():
    data = get_signals()
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
