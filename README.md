# 🧠 NIO RSI + VWAP Trading Bot

This automated trading bot executes intraday trades on stocks like **NIO, AAPL, and TSLA** using a **momentum strategy based on RSI and VWAP indicators**. It's built in Python and integrates with the Alpaca API for simulation and strategy development.

## 🚀 Features

- 🔄 Trades based on RSI (<35 buy / >70 sell) and VWAP confirmation
- 🛑 Stop-loss and take-profit logic built-in
- 🧮 Tracks daily P/L in a `daily_summary.csv`
- 📊 Live Streamlit dashboard (RSI chart + Portfolio Value)
- 📝 Logs every trade to `trade_log.csv`

## 📂 Project Structure

