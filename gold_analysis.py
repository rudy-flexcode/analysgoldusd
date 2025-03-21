import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
import requests

# Charge les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)

# Récupère la clé API depuis la variable d'environnement
API_KEY = os.getenv("API_KEY")

gold_symbol = "GLD"
usd_symbol = "UUP"

def get_price(symbol):
    """Fonction pour récupérer le prix d'un symbole donné depuis l'API TwelveData."""
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()
    if 'price' in data:
        return float(data['price'])
    else:
        return None

@app.route('/', methods=['GET'])
def index():
    """Route racine pour afficher une interface graphique simple."""
    return render_template('index.html')

@app.route('/gold_and_usd', methods=['GET'])
def get_signal():
    """Route qui renvoie le signal pour l'ETF Gold et l'ETF USD avec un template HTML."""
    gold_price = get_price(gold_symbol)
    usd_price = get_price(usd_symbol)
    
    signal = "Neutre"
    if gold_price and usd_price:
        if gold_price > usd_price:
            signal = "Acheter"
        elif gold_price < usd_price:
            signal = "Vendre"
        
        # Rendre la page avec les données
        return render_template('gold_and_usd.html', signal=signal, gold_price=gold_price, usd_price=usd_price)
    else:
        # Si les données sont manquantes, renvoyer une erreur
        return jsonify({'error': 'Données non disponibles'}), 500

if __name__ == "__main__":
    # Remplacer 5000 par la variable d'environnement pour le port (si définie)
    port = int(os.environ.get("PORT", 5000))  # Définit le port à utiliser
    app.run(host="0.0.0.0", port=port, debug=True)

