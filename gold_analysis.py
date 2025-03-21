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
    'sma': None
}
cache_time = 0

def fetch_api(url):
    response = requests.get(url)
    return response.json()

def get_price(symbol):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_api(url)
    if 'price' in data:
        return float(data['price'])
    return None

def get_rsi(symbol):
    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1min&apikey={API_KEY}"
    data = fetch_api(url)
    if 'values' in data:
        return float(data['values'][0]['rsi'])
    return None

def get_sma(symbol):
    url = f"https://api.twelvedata.com/sma?symbol={symbol}&interval=1min&apikey={API_KEY}"
    data = fetch_api(url)
    if 'values' in data:
        return float(data['values'][0]['sma'])
    return None

def get_signals():
    global cache, cache_time
    current_time = time()

    if current_time - cache_time > 60:
        cache['gold_price'] = get_price(gold_symbol)
        cache['usd_price'] = get_price(usd_symbol)
        cache['rsi'] = get_rsi(gold_symbol)
        cache['sma'] = get_sma(gold_symbol)
        cache_time = current_time

    gold_price = cache['gold_price']
    usd_price = cache['usd_price']
    rsi_value = cache['rsi']
    sma_value = cache['sma']

    signal = "Indisponible"
    if gold_price is not None and usd_price is not None:
        if gold_price > usd_price:
            signal = "Acheter"
        elif gold_price < usd_price:
            signal = "Vendre"
        else:
            signal = "Neutre"

    rsi_signal = "Indisponible"
    if rsi_value is not None:
        if rsi_value > 70:
            rsi_signal = "Vendre"
        elif rsi_value < 30:
            rsi_signal = "Acheter"
        else:
            rsi_signal = "Neutre"

    sma_signal = "Indisponible"
    if sma_value is not None:
        if gold_price > sma_value:
            sma_signal = "Acheter"
        elif gold_price < sma_value:
            sma_signal = "Vendre"
        else:
            sma_signal = "Neutre"

    return {
        'signal': signal,
        'gold_price': gold_price,
        'usd_price': usd_price,
        'rsi': rsi_value,
        'rsi_signal': rsi_signal,
        'sma': sma_value,
        'sma_signal': sma_signal
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

