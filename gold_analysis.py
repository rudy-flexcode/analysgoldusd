import os
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
import requests
from time import time
import numpy as np
import logging

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='etf_tracker.log'
)
logger = logging.getLogger('etf_tracker')

load_dotenv()
app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
GOLD_SYMBOL = os.getenv("GOLD_SYMBOL", "GLD")
USD_SYMBOL = os.getenv("USD_SYMBOL", "UUP")
TIME_INTERVAL = os.getenv("TIME_INTERVAL", "1h")  # Intervalle plus long
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
RSI_OVERBOUGHT = float(os.getenv("RSI_OVERBOUGHT", "70"))
RSI_OVERSOLD = float(os.getenv("RSI_OVERSOLD", "30"))
SMA_SHORT_PERIOD = int(os.getenv("SMA_SHORT_PERIOD", "50"))
SMA_LONG_PERIOD = int(os.getenv("SMA_LONG_PERIOD", "200"))
MACD_FAST = int(os.getenv("MACD_FAST", "12"))
MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))
CACHE_DURATION = int(os.getenv("CACHE_DURATION", "300"))  # 5 minutes

# Cache global pour toutes les données
cache = {
    'gold_price': None,
    'usd_price': None,
    'gold_history': None,
    'usd_history': None,
    'rsi': None,
    'sma_short': None,
    'sma_long': None,
    'macd': None,
    'macd_signal': None,
    'macd_histogram': None,
    'volume': None,
    'gold_usd_ratio': None,
    'ratio_sma': None,
    'volatility': None,
    'timestamp': None
}
cache_time = 0

def fetch_api(url):
    """Fonction améliorée pour récupérer des données API avec gestion d'erreurs"""
    try:
        logger.info(f"Appel API: {url}")
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Erreur API: {e}")
        return {}
    except ValueError as e:
        logger.error(f"Erreur de parsing JSON: {e}")
        return {}

def get_price(symbol):
    """Récupère le prix actuel d'un symbole"""
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_api(url)
    if 'price' in data:
        return float(data['price'])
    return None

def get_time_series(symbol, interval=TIME_INTERVAL, outputsize=100):
    """Récupère les séries temporelles pour un symbole"""
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={API_KEY}"
    data = fetch_api(url)
    if 'values' in data:
        return data['values']
    return []

def get_rsi(symbol, interval=TIME_INTERVAL, period=RSI_PERIOD):
    """Récupère l'indicateur RSI"""
    url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval={interval}&time_period={period}&apikey={API_KEY}"
    data = fetch_api(url)
    if 'values' in data and data['values']:
        return float(data['values'][0]['rsi'])
    return None

def get_sma(symbol, interval=TIME_INTERVAL, period=50):
    """Récupère la moyenne mobile simple (SMA)"""
    url = f"https://api.twelvedata.com/sma?symbol={symbol}&interval={interval}&time_period={period}&apikey={API_KEY}"
    data = fetch_api(url)
    if 'values' in data and data['values']:
        return float(data['values'][0]['sma'])
    return None

def get_macd(symbol, interval=TIME_INTERVAL, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    """Récupère l'indicateur MACD"""
    url = f"https://api.twelvedata.com/macd?symbol={symbol}&interval={interval}&fast_period={fast}&slow_period={slow}&signal_period={signal}&apikey={API_KEY}"
    data = fetch_api(url)
    if 'values' in data and data['values']:
        return {
            'macd': float(data['values'][0]['macd']),
            'signal': float(data['values'][0]['signal']),
            'histogram': float(data['values'][0]['histogram'])
        }
    return None

def get_volume(symbol, interval=TIME_INTERVAL):
    """Récupère le volume"""
    time_series = get_time_series(symbol, interval, 10)
    if time_series and 'volume' in time_series[0]:
        volumes = [float(entry['volume']) for entry in time_series[:5]]
        avg_volume = sum(volumes) / len(volumes)
        return avg_volume
    return None

def calculate_volatility(price_data, window=14):
    """Calcule la volatilité basée sur l'écart-type des rendements"""
    if not price_data or len(price_data) < window:
        return None
    
    prices = [float(entry['close']) for entry in price_data[:window]]
    returns = [np.log(prices[i] / prices[i+1]) for i in range(len(prices)-1)]
    return np.std(returns) * 100  # Exprimé en pourcentage

def calculate_ratio_trend(gold_price, usd_price, ratio_sma):
    """Détermine la tendance du ratio Gold/USD par rapport à sa moyenne mobile"""
    if gold_price is None or usd_price is None or ratio_sma is None:
        return "Indisponible"
    
    current_ratio = gold_price / usd_price
    
    if current_ratio > ratio_sma * 1.02:  # 2% au-dessus de la moyenne
        return "Fortement haussier"
    elif current_ratio > ratio_sma:
        return "Légèrement haussier"
    elif current_ratio < ratio_sma * 0.98:  # 2% en-dessous de la moyenne
        return "Fortement baissier"
    elif current_ratio < ratio_sma:
        return "Légèrement baissier"
    else:
        return "Neutre"

def calculate_ratio_sma(gold_data, usd_data, period=20):
    """Calcule la moyenne mobile du ratio Gold/USD"""
    if not gold_data or not usd_data or len(gold_data) < period or len(usd_data) < period:
        return None
    
    ratios = []
    for i in range(period):
        gold_price = float(gold_data[i]['close'])
        usd_price = float(usd_data[i]['close'])
        if usd_price > 0:
            ratios.append(gold_price / usd_price)
    
    if ratios:
        return sum(ratios) / len(ratios)
    return None

def calculate_signal_strength(indicators):
    """Calcule la force du signal basée sur plusieurs indicateurs"""
    weight_sum = 0
    strength = 0
    
    weights = {
        'rsi': 0.2,
        'sma_crossover': 0.2,
        'macd': 0.25,
        'volume': 0.15,
        'ratio_trend': 0.2
    }
    
    # RSI
    if indicators['rsi_signal'] == "Acheter":
        strength += weights['rsi']
        weight_sum += weights['rsi']
    elif indicators['rsi_signal'] == "Vendre":
        strength -= weights['rsi']
        weight_sum += weights['rsi']
    elif indicators['rsi_signal'] == "Neutre":
        weight_sum += weights['rsi']
    
    # SMA
    if indicators['sma_signal'] == "Acheter":
        strength += weights['sma_crossover']
        weight_sum += weights['sma_crossover']
    elif indicators['sma_signal'] == "Vendre":
        strength -= weights['sma_crossover']
        weight_sum += weights['sma_crossover']
    elif indicators['sma_signal'] == "Neutre":
        weight_sum += weights['sma_crossover']
    
    # MACD
    if indicators['macd_signal'] == "Acheter":
        strength += weights['macd']
        weight_sum += weights['macd']
    elif indicators['macd_signal'] == "Vendre":
        strength -= weights['macd']
        weight_sum += weights['macd']
    elif indicators['macd_signal'] == "Neutre":
        weight_sum += weights['macd']
    
    # Volume
    if indicators['volume_signal'] == "Fort":
        if strength > 0:
            strength += weights['volume'] * 0.5
        elif strength < 0:
            strength -= weights['volume'] * 0.5
        weight_sum += weights['volume']
    
    # Ratio trend
    if "haussier" in indicators['ratio_trend'].lower():
        strength += weights['ratio_trend'] * (0.5 if "légèrement" in indicators['ratio_trend'].lower() else 1)
        weight_sum += weights['ratio_trend']
    elif "baissier" in indicators['ratio_trend'].lower():
        strength -= weights['ratio_trend'] * (0.5 if "légèrement" in indicators['ratio_trend'].lower() else 1)
        weight_sum += weights['ratio_trend']
    elif indicators['ratio_trend'] == "Neutre":
        weight_sum += weights['ratio_trend']
    
    # Normaliser la force du signal
    if weight_sum > 0:
        normalized_strength = strength / weight_sum
    else:
        normalized_strength = 0
    
    # Transformer la force en recommandation
    if normalized_strength >= 0.7:
        return "Acheter (Signal Fort)", normalized_strength
    elif normalized_strength >= 0.3:
        return "Acheter (Signal Modéré)", normalized_strength
    elif normalized_strength >= 0.1:
        return "Surveillance Achat", normalized_strength
    elif normalized_strength <= -0.7:
        return "Vendre (Signal Fort)", normalized_strength
    elif normalized_strength <= -0.3:
        return "Vendre (Signal Modéré)", normalized_strength
    elif normalized_strength <= -0.1:
        return "Surveillance Vente", normalized_strength
    else:
        return "Neutre", normalized_strength

def get_signals():
    """Fonction principale pour récupérer et analyser les données"""
    global cache, cache_time
    current_time = time()

    # Vérifier si le cache est encore valide
    if current_time - cache_time > CACHE_DURATION:
        logger.info("Rafraîchissement des données...")
        
        # Récupérer toutes les données nécessaires
        gold_price = get_price(GOLD_SYMBOL)
        usd_price = get_price(USD_SYMBOL)
        gold_history = get_time_series(GOLD_SYMBOL)
        usd_history = get_time_series(USD_SYMBOL)
        rsi_value = get_rsi(GOLD_SYMBOL)
        sma_short = get_sma(GOLD_SYMBOL, period=SMA_SHORT_PERIOD)
        sma_long = get_sma(GOLD_SYMBOL, period=SMA_LONG_PERIOD)
        macd_data = get_macd(GOLD_SYMBOL)
        volume_data = get_volume(GOLD_SYMBOL)
        
        # Calculer des métriques supplémentaires
        volatility = calculate_volatility(gold_history) if gold_history else None
        gold_usd_ratio = gold_price / usd_price if gold_price and usd_price and usd_price > 0 else None
        ratio_sma = calculate_ratio_sma(gold_history, usd_history) if gold_history and usd_history else None
        
        # Mettre à jour le cache
        cache = {
            'gold_price': gold_price,
            'usd_price': usd_price,
            'gold_history': gold_history,
            'usd_history': usd_history,
            'rsi': rsi_value,
            'sma_short': sma_short,
            'sma_long': sma_long,
            'macd': macd_data['macd'] if macd_data else None,
            'macd_signal': macd_data['signal'] if macd_data else None,
            'macd_histogram': macd_data['histogram'] if macd_data else None,
            'volume': volume_data,
            'gold_usd_ratio': gold_usd_ratio,
            'ratio_sma': ratio_sma,
            'volatility': volatility,
            'timestamp': current_time
        }
        cache_time = current_time
        logger.info("Données mises à jour avec succès")
    else:
        logger.info("Utilisation des données en cache")

    # Extraire les données du cache
    gold_price = cache['gold_price']
    usd_price = cache['usd_price']
    rsi_value = cache['rsi']
    sma_short = cache['sma_short']
    sma_long = cache['sma_long']
    macd = cache['macd']
    macd_signal = cache['macd_signal']
    macd_histogram = cache['macd_histogram']
    volume = cache['volume']
    gold_usd_ratio = cache['gold_usd_ratio']
    ratio_sma = cache['ratio_sma']
    volatility = cache['volatility']

    # Générer les signaux basés sur les indicateurs

    # 1. Signal RSI
    rsi_signal = "Indisponible"
    if rsi_value is not None:
        if rsi_value > RSI_OVERBOUGHT:
            rsi_signal = "Vendre"
        elif rsi_value < RSI_OVERSOLD:
            rsi_signal = "Acheter"
        else:
            rsi_signal = "Neutre"

    # 2. Signal SMA (Croisement des moyennes mobiles)
    sma_signal = "Indisponible"
    if sma_short is not None and sma_long is not None and gold_price is not None:
        if sma_short > sma_long and gold_price > sma_short:
            sma_signal = "Acheter"
        elif sma_short < sma_long and gold_price < sma_short:
            sma_signal = "Vendre"
        else:
            sma_signal = "Neutre"

    # 3. Signal MACD
    macd_signal_str = "Indisponible"
    if macd is not None and macd_signal is not None and macd_histogram is not None:
        if macd > macd_signal and macd_histogram > 0:
            macd_signal_str = "Acheter"
        elif macd < macd_signal and macd_histogram < 0:
            macd_signal_str = "Vendre"
        else:
            macd_signal_str = "Neutre"

    # 4. Signal de volume
    volume_signal = "Indisponible"
    if volume is not None and cache['gold_history'] and len(cache['gold_history']) > 10:
        # Comparer au volume moyen des 10 dernières périodes
        avg_past_volume = sum([float(entry['volume']) for entry in cache['gold_history'][1:11]]) / 10
        if volume > avg_past_volume * 1.5:
            volume_signal = "Fort"
        elif volume < avg_past_volume * 0.5:
            volume_signal = "Faible"
        else:
            volume_signal = "Moyen"

    # 5. Signal de ratio Gold/USD
    ratio_trend = "Indisponible"
    if gold_price is not None and usd_price is not None and ratio_sma is not None:
        ratio_trend = calculate_ratio_trend(gold_price, usd_price, ratio_sma)

    # Regrouper tous les signaux
    indicators = {
        'rsi_signal': rsi_signal,
        'sma_signal': sma_signal,
        'macd_signal': macd_signal_str,
        'volume_signal': volume_signal,
        'ratio_trend': ratio_trend
    }

    # Calculer la force globale du signal
    final_signal, signal_strength = calculate_signal_strength(indicators)

    # Évaluer le niveau de risque basé sur la volatilité
    risk_level = "Indisponible"
    if volatility is not None:
        if volatility > 3.0:
            risk_level = "Élevé"
        elif volatility > 1.5:
            risk_level = "Moyen"
        else:
            risk_level = "Faible"

    return {
        'gold_price': gold_price,
        'usd_price': usd_price,
        'gold_usd_ratio': gold_usd_ratio,
        'signal': final_signal,
        'signal_strength': signal_strength,
        'rsi': rsi_value,
        'rsi_signal': rsi_signal,
        'sma_short': sma_short,
        'sma_long': sma_long,
        'sma_signal': sma_signal,
        'macd': macd,
        'macd_signal_line': macd_signal,
        'macd_histogram': macd_histogram,
        'macd_signal': macd_signal_str,
        'volume': volume,
        'volume_signal': volume_signal,
        'volatility': volatility,
        'risk_level': risk_level,
        'ratio_trend': ratio_trend,
        'last_update': cache['timestamp']
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/refresh', methods=['GET'])
def refresh_data():
    data = get_signals()
    return jsonify(data)

@app.route('/force_refresh', methods=['GET'])
def force_refresh():
    global cache_time
    # Forcer la mise à jour du cache
    cache_time = 0
    data = get_signals()
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Démarrage de l'application sur le port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)



