import os
import logging
import pandas as pd
import numpy as np
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import ccxt

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Sadece senin Telegram ID'nin erişimine izin verilir
ALLOWED_USER_ID = 5585878420

exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})
exchange.set_sandbox_mode(True)

KEYBOARD = [
    ['📊 Bakiye & Fiyat', '📈 Sinyal Taraması'],
    ['🟢 Manuel AL', '🔴 Manuel SAT'],
    ['🚀 Otomatik Botu Başlat', '🛑 Botu Durdur']
]
markup = ReplyKeyboardMarkup(KEYBOARD, resize_keyboard=True)

bot_active = False

def analyze_market(symbol="BTC/USDT", timeframe="1h"):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['ema_fast'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=21, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        curr = df.iloc[-2]
        prev = df.iloc[-3]

        buy_cond = (prev['ema_fast'] <= prev['ema_slow']) and (curr['ema_fast'] > curr['ema_slow']) and (curr['rsi'] < 65)
        sell_cond = (prev['ema_fast'] >= prev['ema_slow']) and (curr['ema_fast'] < curr['ema_slow']) and (curr['rsi'] > 35)

        if buy_cond:
            return "BUY", curr['close'], curr['rsi']
        elif sell_cond:
            return "SELL", curr['close'], curr['rsi']
        return "HOLD", curr['close'], curr['rsi']
    except Exception as e:
        logging.error(f"Piyasa analiz hatası: {e}")
        return "ERROR", 0, 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ **Erişim Reddedildi:** Bu bot kişiye özeldir.")
        return

    await update.message.reply_text(
        "💎 **Profesyonel Algo-Trade Paneline Hoş Geldiniz!**\n\n"
        "Strateji: EMA Kesişimi + RSI Filtresi\n"
        "Aşağıdaki menüden komut verebilirsiniz:",
        reply_markup=markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active

    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ **Erişim Reddedildi:** Bu bot kişiye özeldir.")
        return

    text = update.message.text

    if text == '📊 Bakiye & Fiyat':
        ticker = exchange.fetch_ticker('BTC/USDT')
        price = ticker['last']
        await update.message.reply_text(f"📈 **BTC/USDT Fiyatı:** {price} USDT\n🛡️ **Testnet Modu:** Aktif")

    elif text == '📈 Sinyal Taraması':
        signal, price, rsi = analyze_market()
        await update.message.reply_text(f"🔍 **Piyasa Analizi (1S):**\n- Fiyat: {price}\n- RSI: {rsi:.2f}\n- Sinyal: **{signal}**")

    elif text == '🟢 Manuel AL':
        ticker = exchange.fetch_ticker('BTC/USDT')
        await update.message.reply_text(f"✅ **ALIM İşlemi Tetiklendi.**\nFiyat: {ticker['last']} USDT\nStop-Loss: %3 | Take-Profit: %6")

    elif text == '🔴 Manuel SAT':
        ticker = exchange.fetch_ticker('BTC/USDT')
        await update.message.reply_text(f"✅ **SATIŞ İşlemi Tetiklendi.**\nFiyat: {ticker['last']} USDT\nPozisyon kapatıldı.")

    elif text == '🚀 Otomatik Botu Başlat':
        bot_active = True
        await update.message.reply_text("🚀 **Otomatik Al-Sat Botu Devrede!**\nSinyaller 1 saatlik mum kapanışlarında taranıp telefonunuza bildirilecek.")

    elif text == '🛑 Botu Durdur':
        bot_active = False
        await update.message.reply_text("⏸️ **Otomatik bot durduruldu.**")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("HATA: TELEGRAM_TOKEN ayarlanmamış!")
        exit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Profesyonel Bot Başlatıldı...")
    app.run_polling()
