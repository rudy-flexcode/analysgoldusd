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

cache = {
    'gold_price': None,
    'usd_price': None,
    'rsi': None,
    'sma_short': None,
    'sma_long': None,
    'macd': None,
    'signal_line': None,
    'atr': None
}
cache_time = 0

WEIGHTS = {
    "rsi": 0.3,
    "sma": 0.3,
    "macd": 0.25,
    "atr_filter": 0.15
}

def fetch_api(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur API: {e}")
        return None

def get_price(symbol):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_api(url)
    return float(data['price']) if data and 'price' in data else None

def get_rsi(symbol):
    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1min&apikey={API_KEY}"
    data = fetch_api(url)
    return float(data['values'][0]['rsi']) if data and 'values' in data else None

def get_sma(symbol, time_period):
    url = f"https://api.twelvedata.com/sma?symbol={symbol}&interval=1min&time_period={time_period}&apikey={API_KEY}"
    data = fetch_api(url)
    return float(data['values'][0]['sma']) if data and 'values' in data else None

def get_macd(symbol):
    url = f"https://api.twelvedata.com/macd?symbol={symbol}&interval=1min&apikey={API_KEY}"
    data = fetch_api(url)
    if data and 'values' in data:
        return float(data['values'][0]['macd']), float(data['values'][0]['signal'])
    return None, None

def get_atr(symbol):
    url = f"https://api.twelvedata.com/atr?symbol={symbol}&interval=1min&time_period=14&apikey={API_KEY}"
    data = fetch_api(url)
    return float(data['values'][0]['atr']) if data and 'values' in data else None

def calculate_signal(data):
    score = 0

    if data['rsi'] is not None:
        if data['rsi'] < 45:
            score += WEIGHTS['rsi']
        elif data['rsi'] > 55:
            score -= WEIGHTS['rsi']

    if data['sma_short'] and data['sma_long']:
        if data['sma_short'] > data['sma_long']:
            score += WEIGHTS['sma']
        elif data['sma_short'] < data['sma_long']:
            score -= WEIGHTS['sma']

    if data['macd'] and data['signal_line']:
        if data['macd'] > data['signal_line']:
            score += WEIGHTS['macd']
        elif data['macd'] < data['signal_line']:
            score -= WEIGHTS['macd']

    if data['atr'] and data['atr'] > 0.2:
        score += WEIGHTS['atr_filter']

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
        print("Mise à jour des données...")
        cache.update({
            'gold_price': get_price(gold_symbol),
            'usd_price': get_price(usd_symbol),
            'rsi': get_rsi(gold_symbol),
            'sma_short': get_sma(gold_symbol, 7),
            'sma_long': get_sma(gold_symbol, 21),
            'macd': None,
            'signal_line': None,
            'atr': get_atr(gold_symbol)
        })
        cache['macd'], cache['signal_line'] = get_macd(gold_symbol)
        cache_time = current_time
    
    return {**cache, 'signal': calculate_signal(cache)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/refresh', methods=['GET'])
def refresh_data():
    return jsonify(get_signals())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
