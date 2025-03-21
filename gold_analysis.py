import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
import requests
from time import time

# Charge les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)

# Récupère la clé API depuis la variable d'environnement
API_KEY = os.getenv("API_KEY")

gold_symbol = "GLD"
usd_symbol = "UUP"

# Cache et temps de la dernière mise à jour
cache = {}
cache_time = 0  # Temps du dernier cache

def get_price(symbol):
    """Fonction pour récupérer le prix d'un symbole donné depuis l'API TwelveData avec cache."""
    global cache, cache_time
    current_time = time()

    # Si les données sont encore valides dans le cache (par exemple 1 minute max)
    if symbol in cache and current_time - cache_time < 60:  # 60 secondes = 1 minute
        return cache[symbol]

    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'price' in data:
        cache[symbol] = float(data['price'])
        cache_time = current_time  # Met à jour le temps du cache
        return cache[symbol]
    else:
        return None

def get_signal():
    """Fonction pour obtenir le signal basé sur les prix de Gold et USD."""
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

@app.route('/', methods=['GET'])
def index():
    """Route racine pour afficher une interface graphique avec signal calculé."""
    signal, gold_price, usd_price = get_signal()
    
    # Affichage du signal et des prix directement sur la page d'accueil
    return render_template('index.html', signal=signal, gold_price=gold_price, usd_price=usd_price)

@app.route('/refresh', methods=['GET'])
def refresh_data():
    """Route pour rafraîchir les données."""
    signal, gold_price, usd_price = get_signal()
    return jsonify({'signal': signal, 'gold_price': gold_price, 'usd_price': usd_price})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Définit le port à utiliser
    app.run(host="0.0.0.0", port=port, debug=True)
