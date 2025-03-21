import os
from dotenv import load_dotenv
from flask import Flask, jsonify
import requests

# Charge les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)

# Récupère la clé API depuis la variable d'environnement
API_KEY = os.getenv("API_KEY")

gold_symbol = "GLD"
usd_symbol = "UUP"

def get_price(symbol):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()
    if 'price' in data:
        return float(data['price'])
    else:
        return None

@app.route('/gold_and_usd', methods=['GET'])
def get_signal():
    gold_price = get_price(gold_symbol)
    usd_price = get_price(usd_symbol)
    
    if gold_price and usd_price:
        signal = "Neutre"
        if gold_price > usd_price:
            signal = "Acheter"
        elif gold_price < usd_price:
            signal = "Vendre"
        return jsonify({'signal': signal, 'gold': gold_price, 'usd': usd_price})
    else:
        return jsonify({'error': 'Données non disponibles'}), 500

if __name__ == "__main__":
    # Remplacer 5000 par la variable d'environnement pour le port
    port = int(os.environ.get("PORT", 5000))  # Définit le port à utiliser
    app.run(host="0.0.0.0", port=port, debug=True)

