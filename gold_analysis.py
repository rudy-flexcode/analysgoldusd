import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
import requests
from time import time

# Charge les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")

gold_symbol = "GLD"
usd_symbol = "UUP"

# Cache et temps pour limiter les appels API
cache = {}
cache_time = 0
rsi_cache = {}
rsi_cache_time = 0

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

def get_signal():
    gold_price = get_price(gold_symbol)
    usd_price = get_price(usd_symbol)
    
    if gold_price is not None and usd_price is not None:
        if gold_price > usd_price:
            return "Acheter", gold_price, usd_price
        elif gold_price < usd_price:
            return "Vendre", gold_price, usd_price
        else:
            return "Neutre", gold_price, usd_price
    else:
        return None, None, None

def get_rsi(symbol):
    global rsi_cache, rsi_cache_time
    current_time = time()

    if symbol in rsi_cache and current_time - rsi_cache_time < 60:
        return rsi_cache[symbol]

    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1min&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'value' in data:
        rsi_value = float(data['value'])
        rsi_cache[symbol] = rsi_value
        rsi_cache_time = current_time
        return rsi_value
    else:
        return None

def get_rsi_signal(rsi_value):
    if rsi_value is not None:
        if rsi_value > 70:
            return "Vendre"
        elif rsi_value < 30:
            return "Acheter"
        else:
            return "Neutre"
    return "Indisponible"

@app.route('/', methods=['GET'])
def index():
    signal, gold_price, usd_price = get_signal()
    rsi_value = get_rsi(gold_symbol)
    rsi_signal = get_rsi_signal(rsi_value)
    
    return render_template('index.html', 
                           signal=signal, 
                           gold_price=gold_price, 
                           usd_price=usd_price,
                           rsi_value=rsi_value,
                           rsi_signal=rsi_signal)

@app.route('/refresh', methods=['GET'])
def refresh_data():
    signal, gold_price, usd_price = get_signal()
    rsi_value = get_rsi(gold_symbol)
    rsi_signal = get_rsi_signal(rsi_value)
    return jsonify({
        'signal': signal, 
        'gold_price': gold_price, 
        'usd_price': usd_price,
        'rsi_value': rsi_value,
        'rsi_signal': rsi_signal
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
