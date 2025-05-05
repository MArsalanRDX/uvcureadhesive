import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time
import plotly.graph_objs as go
import numpy as np
import time as t

# Page config
st.set_page_config(page_title="Binance Live Viewer", layout="wide")
st.title("📊 Binance Historical & Live Candles Viewer")

# Telegram Settings
TELEGRAM_BOT_TOKEN = '8065449733:AAHqS9CleBCyasg_We5E4Nb4JwHYnBeZnFQ'
TELEGRAM_CHAT_ID = '5530884152'

def send_telegram_alert(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, data=payload)
    except:
        pass

# Inputs
symbol = st.text_input("Enter Coin Symbol (e.g., BABYUSDT)", value="BABYUSDT")
interval = st.selectbox("Select Interval", ["1m", "15m", "1h", "1d", "3d", "1M"])
start_date = st.date_input("Start Date", value=date(2025, 4, 20))
end_date = st.date_input("End Date", value=date.today())

# Checkboxes
show_bollinger = st.checkbox("Show Bollinger Bands")
show_sr = st.checkbox("Show Support/Resistance Zones")
show_rsi = st.checkbox("Show RSI")
show_macd = st.checkbox("Show MACD")
show_vwap = st.checkbox("Show VWAP")
show_ema = st.checkbox("Show EMA (20, 50)")
show_alerts = st.checkbox("Show Alerts (Overbought/Oversold RSI, MACD Crosses)")
show_money_flow = st.checkbox("Show Money Flow Analysis")
show_volume = st.checkbox("Show Volume Bars")
show_patterns = st.checkbox("Show Candlestick Patterns")
show_volume_spikes = st.checkbox("Highlight Unusual Volume Spikes")
live_mode = st.checkbox("🔄 Live Update Mode (1 min refresh)")

# Binance Data
def get_binance_klines(symbol, interval, start_time, end_time):
    url = "https://fapi.binance.com/fapi/v1/klines"
    start_datetime = datetime.combine(start_time, time.min)
    end_datetime = datetime.now() if end_time == date.today() else datetime.combine(end_time, time.max)

    all_data = []
    while start_datetime < end_datetime:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": int(start_datetime.timestamp() * 1000),
            "endTime": int(end_datetime.timestamp() * 1000),
            "limit": 1000
        }
        response = requests.get(url, params=params)
        data = response.json()
        if not data or isinstance(data, dict):
            break
        all_data.extend(data)
        last_open_time = data[-1][0] / 1000
        start_datetime = datetime.fromtimestamp(last_open_time + 1)
        if len(data) < 1000:
            break

    if not all_data:
        st.warning("No data found or API error.")
        return pd.DataFrame()

    df = pd.DataFrame(all_data, columns=[
        "Open Time", "Open", "High", "Low", "Close", "Volume",
        "Close Time", "Quote Asset Volume", "Number of Trades",
        "Taker Buy Base Volume", "Taker Buy Quote Volume", "Ignore"])

    df["Open Time"] = pd.to_datetime(df["Open Time"], unit="ms")
    df[["Open", "High", "Low", "Close", "Volume", "Taker Buy Base Volume"]] = df[["Open", "High", "Low", "Close", "Volume", "Taker Buy Base Volume"]].astype(float)
    return df

# Indicators
def add_bollinger_bands(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['Upper Band'] = df['MA20'] + 2 * df['Close'].rolling(window=20).std()
    df['Lower Band'] = df['MA20'] - 2 * df['Close'].rolling(window=20).std()
    return df

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df):
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df

def calculate_money_flow(df):
    df['Buy Volume %'] = df['Taker Buy Base Volume'] / df['Volume'] * 100
    avg_buy_volume = df['Buy Volume %'].iloc[-10:].mean()
    st.metric("🔄 Avg Buyer Volume (last 10 candles)", f"{avg_buy_volume:.2f}%")
    return df

def add_vwap(df):
    df['Typical Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TPV'] = df['Typical Price'] * df['Volume']
    df['VWAP'] = df['TPV'].cumsum() / df['Volume'].cumsum()
    return df

def add_ema(df):
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

def detect_volume_spikes(df):
    signals = []
    avg_vol = df['Volume'].rolling(window=20).mean()
    for i in range(1, len(df)):
        if df['Volume'].iloc[i] > 2 * avg_vol.iloc[i]:
            signals.append(f"⚡ Volume Spike at {df['Open Time'].iloc[i]}")
    return signals

# Alerts
def generate_alerts(df):
    alerts = []
    if show_rsi and df['RSI'].iloc[-1] > 70:
        alerts.append("🔴 RSI Overbought (>70) — Possible Sell Signal")
    elif show_rsi and df['RSI'].iloc[-1] < 30:
        alerts.append("🟢 RSI Oversold (<30) — Possible Buy Signal")

    if show_macd and df['MACD'].iloc[-1] > df['Signal Line'].iloc[-1] and df['MACD'].iloc[-2] < df['Signal Line'].iloc[-2]:
        alerts.append("🟢 MACD Bullish Crossover")
    elif show_macd and df['MACD'].iloc[-1] < df['Signal Line'].iloc[-1] and df['MACD'].iloc[-2] > df['Signal Line'].iloc[-2]:
        alerts.append("🔴 MACD Bearish Crossover")

    for msg in alerts:
        send_telegram_alert(f"{symbol} ({interval})\n{msg}")
    return alerts

# Plot
def plot_candlestick(df):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df['Open Time'],
                                 open=df['Open'],
                                 high=df['High'],
                                 low=df['Low'],
                                 close=df['Close'],
                                 name='Candlesticks'))

    if show_bollinger:
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Upper Band'], line=dict(color='orange'), name='Upper Band'))
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Lower Band'], line=dict(color='orange'), name='Lower Band'))

    if show_ema:
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['EMA20'], line=dict(color='blue'), name='EMA20'))
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['EMA50'], line=dict(color='purple'), name='EMA50'))

    if show_vwap:
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['VWAP'], line=dict(color='green'), name='VWAP'))

    if show_volume:
        fig.add_trace(go.Bar(x=df['Open Time'], y=df['Volume'], name='Volume', yaxis='y2'))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right', title='Volume'))

    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    return fig

# Run App
def run_viewer():
    df = get_binance_klines(symbol, interval, start_date, end_date)
    if df.empty:
        return
    if show_bollinger:
        df = add_bollinger_bands(df)
    if show_rsi:
        df = calculate_rsi(df)
    if show_macd:
        df = calculate_macd(df)
    if show_money_flow:
        df = calculate_money_flow(df)
    if show_vwap:
        df = add_vwap(df)
    if show_ema:
        df = add_ema(df)

    st.plotly_chart(plot_candlestick(df), use_container_width=True)

    if show_alerts:
        alerts = generate_alerts(df)
        for a in alerts:
            st.warning(a)

    if show_volume_spikes:
        spikes = detect_volume_spikes(df)
        for s in spikes[-5:]:
            st.info(s)

# Main Logic
if st.button("Fetch Data") or live_mode:
    placeholder = st.empty()
    while True:
        with placeholder.container():
            run_viewer()
        if not live_mode:
            break
        t.sleep(60)  # Wait 60 sec before refresh
