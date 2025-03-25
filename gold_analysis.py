import flask
from flask import Flask, jsonify, render_template
import requests
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10000, backupCount=3, encoding='utf-8'),  # Encodage UTF-8
        logging.StreamHandler()
    ]
)

# Charger les variables d'environnement
load_dotenv()
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("🚨 Clé API manquante ! Ajoute-la dans un fichier .env")

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

gold_symbol = "GLD"
cache = {"timestamp": 0, "data": {}}
CACHE_DURATION = 120  # Durée du cache en secondes (2 minutes)

def fetch_api(url, is_price_endpoint=False):
    """Récupère les données depuis l'API et gère les erreurs."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Pour l'endpoint de prix, la structure est différente
        if is_price_endpoint:
            if "price" not in data:
                logging.warning(f"⚠️ Erreur API Prix: Structure inattendue {data}")
                return None
            return data
        
        # Pour les autres endpoints
        if "values" not in data:
            logging.warning(f"⚠️ Erreur API: Structure inattendue {data}")
            return None
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erreur lors de la récupération des données: {e}")
        return None

def get_price(symbol):
    """Récupère le prix d'un symbole."""
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_api(url, is_price_endpoint=True)
    
    if not data:
        return None
    
    try:
        return float(data["price"])
    except (KeyError, ValueError) as e:
        logging.error(f"Erreur de conversion du prix pour {symbol}: {e}")
        return None

def get_technical_analysis(symbol, indicator, period=None):
    """
    Récupère les données techniques génériques avec gestion des périodes.
    Supporte : RSI, SMA, MACD, ATR.
    """
    base_url = f"https://api.twelvedata.com/{indicator}?symbol={symbol}&interval=1min"
    
    # Ajouter la période si spécifiée
    if period:
        base_url += f"&time_period={period}"
    
    base_url += f"&apikey={API_KEY}"
    
    logging.info(f"Appel API pour {indicator} avec période {period} : {base_url}")
    
    data = fetch_api(base_url)

    # Log de la réponse brute pour débogage
    logging.debug(f"Réponse brute pour {indicator} ({period}): {data}")
    
    if not data or "values" not in data:
        logging.warning(f"Impossible de récupérer {indicator} pour {symbol} avec période {period}. Réponse : {data}")
        return None
    
    # Récupérer la première valeur
    first_value = data["values"][0]
    
    # Mapping des indicateurs
    indicator_map = {
        "rsi": "rsi",
        "sma": "sma",
        "macd": "macd",
        "signal_line": "signal",
        "atr": "atr"
    }
    
    try:
        if indicator == "macd":
            # Retourner à la fois MACD et Signal Line
            macd = float(first_value.get("macd", 0))
            signal = float(first_value.get("signal", 0))
            return {"macd": macd, "signal": signal}
        
        # Retourner une valeur unique pour les autres indicateurs
        value = float(first_value.get(indicator_map.get(indicator, indicator), 0))
        logging.info(f"Valeur récupérée pour {indicator} ({period if period else 'N/A'}) : {value}")
        return value
    except (ValueError, TypeError) as e:
        logging.error(f"Erreur de conversion pour {indicator} avec période {period}: {e}")
        return None

def get_macd(symbol):
    """Récupère les valeurs MACD et Signal Line en un seul appel."""
    data = get_technical_analysis(symbol, "macd")
    if not data:
        return None, None
    return data.get("macd"), data.get("signal")

def generate_trading_signal(signals):
    """
    Générer un signal de trading basé sur plusieurs indicateurs avec pondération.
    """
    macd = signals.get('macd', 0)
    signal_line = signals.get('signal_line', 0)
    rsi = signals.get('rsi', 50)
    sma_7 = signals.get('sma_7', 0)
    sma_21 = signals.get('sma_21', 0)
    gold_price = signals.get('gold_price', 0)
    atr = signals.get('atr', 0)

    # Critères d'achat pondérés
    buy_conditions = [
        (macd > signal_line, 2),  # Tendance haussière MACD (poids 2)
        (rsi < 40, 1),            # RSI indiquant survente (poids 1)
        (sma_7 > sma_21, 2),      # Confirmation par moyennes mobiles (poids 2)
        (atr < gold_price * 0.03, 1)  # Volatilité relativement basse (poids 1)
    ]

    # Critères de vente pondérés
    sell_conditions = [
        (macd < signal_line, 2),  # Tendance baissière MACD (poids 2)
        (rsi > 60, 1),            # RSI indiquant suracheté (poids 1)
        (sma_7 < sma_21, 2),      # Confirmation par moyennes mobiles (poids 2)
        (atr > gold_price * 0.04, 1)  # Volatilité élevée (poids 1)
    ]

    # Calcul des scores pondérés
    buy_score = sum(weight for condition, weight in buy_conditions if condition)
    sell_score = sum(weight for condition, weight in sell_conditions if condition)

    # Logs pour débogage
    logging.info(f"MACD: {macd}, Signal Line: {signal_line}")
    logging.info(f"RSI: {rsi}")
    logging.info(f"SMA 7: {sma_7}, SMA 21: {sma_21}")
    logging.info(f"Gold Price: {gold_price}, ATR: {atr}")
    logging.info(f"Buy Score: {buy_score}, Sell Score: {sell_score}")

    # Décision de trading basée sur le score
    if buy_score >= 3:
        signal = "BUY"
    elif sell_score >= 3:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    logging.info(f"Signal généré: {signal} (Buy Score: {buy_score}, Sell Score: {sell_score})")
    return signal

def get_signals():
    """Vérifie le cache et récupère les indicateurs techniques."""
    current_time = time.time()
    if cache["data"] and (current_time - cache["timestamp"] < CACHE_DURATION):
        return cache["data"]
    
    macd, signal_line = get_macd(gold_symbol)
    indicators = {
        "gold_price": get_price(gold_symbol),
        "usd_price": get_price("USD"),
        "macd": macd,
        "signal_line": signal_line,
        "rsi": get_technical_analysis(gold_symbol, "rsi"),
        "sma_7": get_technical_analysis(gold_symbol, "sma", period=7),
        "sma_21": get_technical_analysis(gold_symbol, "sma", period=21),
        "atr": get_technical_analysis(gold_symbol, "atr")
    }
    
    # Filtrer les indicateurs None
    filtered_indicators = {key: val for key, val in indicators.items() if val is not None}
    if len(filtered_indicators) < len(indicators):
        missing_keys = set(indicators.keys()) - set(filtered_indicators.keys())
        logging.warning(f"Certains indicateurs n'ont pas pu être récupérés: {missing_keys}")
    
    critical_keys = ["macd", "signal_line", "sma_7", "sma_21"]
    missing_critical = [key for key in critical_keys if key not in filtered_indicators]
    if missing_critical:
        logging.error(f"Indicateurs critiques manquants : {missing_critical}")
        return None
    
    # Mettre à jour le cache
    cache.update({
        "data": filtered_indicators,
        "timestamp": current_time
    })
    
    return cache["data"]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/refresh')
def refresh_data():
    """Met à jour les données et renvoie les indicateurs avec un signal."""
    signals = get_signals()
    
    if not signals:
        logging.error("Impossible de récupérer les données")
        return jsonify({"error": "Impossible de récupérer certaines données", "details": "Certains indicateurs sont manquants"}), 500
    
    # Ajouter le signal de trading
    signals['signal'] = generate_trading_signal(signals)
    
    return jsonify(signals)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
