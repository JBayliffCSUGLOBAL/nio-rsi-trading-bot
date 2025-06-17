import alpaca_trade_api as tradeapi
import time
import datetime
import requests
import os
import csv
import pandas as pd
import ta
from threading import Thread

API_KEY = "PK367PPMJF4BXUO1XGSF"
API_SECRET = "sLQjfhXfPDPNz7ZWaywlbKITcriOsQfudZYaLnFk"
BASE_URL = "https://paper-api.alpaca.markets"

LOG_FILE = "C:/TradingBots/trade_log.csv"
SUMMARY_FILE = "C:/TradingBots/daily_summary.csv"

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

STOP_LOSS_PERCENT = 1.0
TAKE_PROFIT_PERCENT = 2.0
VWAP_CONFIRM = True


def market_is_open():
    try:
        return api.get_clock().is_open
    except Exception as e:
        print(f"[!] Error checking market status: {e}")
        return False


def get_last_price(symbol):
    try:
        bars = api.get_bars(symbol, tradeapi.TimeFrame.Minute, limit=1)
        return bars[0].c if bars else None
    except Exception as e:
        print(f"[!] Error fetching price for {symbol}: {e}")
        return None


def rsi_entry_signal(symbol):
    try:
        bars = api.get_bars(symbol, tradeapi.TimeFrame.Minute, limit=30)
        if len(bars) < 14:
            return False

        df = pd.DataFrame({
            'close': [bar.c for bar in bars],
            'high': [bar.h for bar in bars],
            'low': [bar.l for bar in bars],
            'volume': [bar.v for bar in bars]
        })

        df['rsi'] = ta.momentum.RSIIndicator(close=df['close']).rsi()
        rsi = df['rsi'].iloc[-1]
        print(f"{symbol} RSI: {rsi:.2f}")

        if VWAP_CONFIRM:
            vwap = ta.volume.VolumeWeightedAveragePrice(
                high=df['high'], low=df['low'], close=df['close'], volume=df['volume']
            ).volume_weighted_average_price()
            df['vwap'] = vwap
            return rsi < 35 and df['close'].iloc[-1] > df['vwap'].iloc[-1]

        return rsi < 35

    except Exception as e:
        print(f"[!] RSI signal error for {symbol}: {e}")
        return False


def rsi_exit_signal(symbol):
    try:
        bars = api.get_bars(symbol, tradeapi.TimeFrame.Minute, limit=30)
        df = pd.DataFrame({ 'close': [bar.c for bar in bars] })
        rsi = ta.momentum.RSIIndicator(close=df['close']).rsi()
        return rsi.iloc[-1] > 70
    except Exception as e:
        print(f"[!] RSI exit signal error for {symbol}: {e}")
        return False


def log_trade(timestamp, action, symbol, quantity, price, gain):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Timestamp", "Action", "Symbol", "Quantity", "Price", "Gain (%)"])
        writer.writerow([timestamp, action, symbol, quantity, f"{price:.2f}", f"{gain:.2f}" if gain is not None else ""])


def log_daily_summary(date_str, symbol, daily_profit):
    file_exists = os.path.isfile(SUMMARY_FILE)
    with open(SUMMARY_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Date", "Symbol", "Profit/Loss ($)"])
        writer.writerow([date_str, symbol, f"{daily_profit:.2f}"])


def trade_symbol(symbol):
    print(f"Bot launched for {symbol}. Waiting for market data...")

    position = None
    real_entry_price = None
    shares_bought = None
    daily_profit = 0.0
    today = datetime.date.today()

    while True:
        try:
            if not market_is_open():
                if datetime.date.today() != today:
                    log_daily_summary(today.isoformat(), symbol, daily_profit)
                    daily_profit = 0.0
                    today = datetime.date.today()
                print(f"Market is closed. Waiting for {symbol}...")
                time.sleep(60)
                continue

            current_price = get_last_price(symbol)
            if current_price is None:
                time.sleep(60)
                continue

            timestamp = datetime.datetime.now()

            if not position and rsi_entry_signal(symbol):
                order = api.submit_order(
                    symbol=symbol,
                    notional=100,
                    side="buy",
                    type="market",
                    time_in_force="day"
                )
                time.sleep(2)
                filled_order = api.get_order(order.id)
                real_entry_price = float(filled_order.filled_avg_price)
                shares_bought = float(filled_order.filled_qty)
                print(f"{timestamp}: RSI entry triggered. Buying {symbol} at ${real_entry_price:.2f}")
                log_trade(timestamp, "BUY", symbol, shares_bought, real_entry_price, None)
                position = True

            elif position:
                gain = (current_price - real_entry_price) / real_entry_price * 100
                unrealized_profit = (current_price - real_entry_price) * shares_bought
                print(f"{timestamp}: {symbol} position open. Entry: ${real_entry_price:.2f}, Price: ${current_price:.2f}, Gain: {gain:.2f}%")

                if rsi_exit_signal(symbol) or gain >= TAKE_PROFIT_PERCENT or gain <= -STOP_LOSS_PERCENT:
                    sell_order = api.submit_order(
                        symbol=symbol,
                        qty=shares_bought,
                        side="sell",
                        type="market",
                        time_in_force="day"
                    )
                    time.sleep(2)
                    filled_sell = api.get_order(sell_order.id)
                    exit_price = float(filled_sell.filled_avg_price)
                    actual_gain = (exit_price - real_entry_price) / real_entry_price * 100
                    actual_profit = (exit_price - real_entry_price) * shares_bought
                    daily_profit += actual_profit
                    print(f"{timestamp}: Sold {symbol} at ${exit_price:.2f}. Gain: {actual_gain:.2f}%")
                    log_trade(timestamp, "SELL", symbol, shares_bought, exit_price, actual_gain)
                    position = None
                    shares_bought = None
                    real_entry_price = None
                else:
                    log_trade(timestamp, "HOLD", symbol, shares_bought, current_price, gain)

            time.sleep(60)

        except Exception as e:
            print(f"[!] Error in {symbol}: {e}")
            time.sleep(60)


def main_loop():
    symbols = ["NIO", "TSLA", "AAPL"]
    for symbol in symbols:
        Thread(target=trade_symbol, args=(symbol,)).start()


if __name__ == '__main__':
    main_loop()
