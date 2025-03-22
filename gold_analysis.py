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

# Cache global pour toutes les données
cache = {
    'gold_price': None,
    'usd_price': None,
    'rsi': None,
    'sma_short': None,
    'sma_long': None
}
cache_time = 0

# Pondérations
WEIGHTS = {
    "spread": 0.4,
    "rsi": 0.3,
    "sma": 0.3
}

def fetch_api(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'appel API: {e}")
        return None

def get_price(symbol):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_api(url)
    if data and 'price' in data:
        return float(data['price'])
    return None

def get_rsi(symbol):
    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1min&apikey={API_KEY}"
    data = fetch_api(url)
    if data and 'values' in data:
        return float(data['values'][0]['rsi'])
    return None

def get_sma(symbol, time_period):
    url = f"https://api.twelvedata.com/sma?symbol={symbol}&interval=1min&time_period={time_period}&apikey={API_KEY}"
    data = fetch_api(url)
    if data and 'values' in data:
        return float(data['values'][0]['sma'])
    return None

def calculate_signal(gold_price, usd_price, rsi_value, sma_short, sma_long):
    score = 0

    # Spread Gold / USD
    if gold_price and usd_price:
        if gold_price > usd_price:
            score += 1 * WEIGHTS['spread']
        elif gold_price < usd_price:
            score -= 1 * WEIGHTS['spread']

    # RSI
    if rsi_value is not None:
        if rsi_value < 30:
            score += 1 * WEIGHTS['rsi']
        elif rsi_value > 70:
            score -= 1 * WEIGHTS['rsi']

    # SMA court vs long terme
    if sma_short and sma_long:
        if sma_short > sma_long:
            score += 1 * WEIGHTS['sma']
        elif sma_short < sma_long:
            score -= 1 * WEIGHTS['sma']

    # Signal global
    if score >= 0.5:
        return "Acheter"
    elif score <= -0.5:
        return "Vendre"
    else:
        return "Neutre"

def get_signals():
    global cache, cache_time
    current_time = time()

    if current_time - cache_time > 60:
        cache['gold_price'] = get_price(gold_symbol)
        cache['usd_price'] = get_price(usd_symbol)
        cache['rsi'] = get_rsi(gold_symbol)
        cache['sma_short'] = get_sma(gold_symbol, 7)
        cache['sma_long'] = get_sma(gold_symbol, 21)
        cache_time = current_time

    gold_price = cache['gold_price']
    usd_price = cache['usd_price']
    rsi_value = cache['rsi']
    sma_short = cache['sma_short']
    sma_long = cache['sma_long']

    signal = calculate_signal(gold_price, usd_price, rsi_value, sma_short, sma_long)

    return {
        'signal': signal,
        'gold_price': gold_price,
        'usd_price': usd_price,
        'rsi': rsi_value,
        'sma_short': sma_short,
        'sma_long': sma_long
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
