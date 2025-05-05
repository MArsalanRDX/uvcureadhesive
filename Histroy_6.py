import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time
import plotly.graph_objs as go
import numpy as np
import time as t

st.set_page_config(page_title="Binance Live Viewer", layout="wide")
st.title("📊 Binance Historical & Live Candles Viewer")

# Telegram Settings
TELEGRAM_BOT_TOKEN = '8065449733:AAHqS9CleBCyasg_We5E4Nb4JwHYnBeZnFQ'
TELEGRAM_CHAT_ID = '5530884152'

def send_telegram_alert(message):
    url = f'https://api.telegram.org/bot8065449733:AAHqS9CleBCyasg_We5E4Nb4JwHYnBeZnFQ/sendMessage'
    payload = {'chat_id': 5530884152, 'text': message}
    try:
        requests.post(url, data=payload)
    except:
        pass

# Inputs
symbol = st.text_input("Enter Coin Symbol (e.g., BABYUSDT)", value="BABYUSDT")
interval = st.selectbox("Select Interval", ["1m", "15m", "1h", "1d", "3d", "1M"])
start_date = st.date_input("Start Date", value=date(2025, 4, 20))
end_date = st.date_input("End Date", value=date.today())

# Checkboxes for indicators
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

# Live update option
live_mode = st.checkbox("🔄 Live Update Mode (1 min refresh)")

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

# Indicators — Add Bollinger Bands
def add_bollinger_bands(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['Upper Band'] = df['MA20'] + 2 * df['Close'].rolling(window=20).std()
    df['Lower Band'] = df['MA20'] - 2 * df['Close'].rolling(window=20).std()
    return df

def add_support_resistance(df):
    levels = []
    for i in range(2, len(df) - 2):
        high = df['High'][i]
        low = df['Low'][i]
        if high > df['High'][i - 1] and high > df['High'][i + 1] and high > df['High'][i - 2] and high > df['High'][i + 2]:
            levels.append((df['Open Time'][i], high))
        if low < df['Low'][i - 1] and low < df['Low'][i + 1] and low < df['Low'][i - 2] and low < df['Low'][i + 2]:
            levels.append((df['Open Time'][i], low))
    return levels

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
    df['Buy Volume %'] = df['Taker Buy Base Volume'].astype(float) / df['Volume'].astype(float) * 100
    avg_buy_volume = df['Buy Volume %'].iloc[-10:].mean()
    st.metric("🔄 Avg Buyer Volume Last 10 Candles", f"{avg_buy_volume:.2f}%")
    return df

def detect_candlestick_patterns(df):
    patterns = []
    for i in range(1, len(df)):
        o, h, l, c = df.loc[i, ['Open', 'High', 'Low', 'Close']]
        prev_o, prev_c = df.loc[i-1, ['Open', 'Close']]
        body = abs(c - o)
        range_ = h - l
        if body < (0.3 * range_):
            patterns.append((df.loc[i, 'Open Time'], 'Doji'))
        elif c > o and prev_c < prev_o and c > prev_o and o < prev_c:
            patterns.append((df.loc[i, 'Open Time'], 'Bullish Engulfing'))
        elif c < o and prev_c > prev_o and c < prev_o and o > prev_c:
            patterns.append((df.loc[i, 'Open Time'], 'Bearish Engulfing'))
        elif (h - max(o, c)) <= 0.1 * range_ and (min(o, c) - l) >= 0.5 * range_:
            patterns.append((df.loc[i, 'Open Time'], 'Hammer'))
    return patterns

def detect_volume_spikes(df):
    signals = []
    avg_vol = df['Volume'].rolling(window=20).mean()
    for i in range(1, len(df)):
        if df['Volume'].iloc[i] > 2 * avg_vol.iloc[i]:
            signals.append((df['Open Time'].iloc[i], "⚡ Sudden Volume Spike Detected"))
        elif df['Volume'].iloc[i] < 0.5 * avg_vol.iloc[i]:
            signals.append((df['Open Time'].iloc[i], "⚠️ Low Volume – Weak Breakout Risk"))
    return signals

# Indicators — Add EMA
def add_ema(df):
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

# Indicators — Add VWAP
def add_vwap(df):
    df['Typical Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['Cumulative TPV'] = (df['Typical Price'] * df['Volume']).cumsum()
    df['Cumulative Volume'] = df['Volume'].cumsum()
    df['VWAP'] = df['Cumulative TPV'] / df['Cumulative Volume']
    return df

# Plot Candlestick with optional indicators
def plot_candlestick(df):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(x=df['Open Time'],
                                 open=df['Open'],
                                 high=df['High'],
                                 low=df['Low'],
                                 close=df['Close'],
                                 name='Candlesticks'))

    if show_bollinger:
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Upper Band'],
                                 line=dict(color='orange', width=1), name='Upper Band'))
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Lower Band'],
                                 line=dict(color='orange', width=1), name='Lower Band'))

    if show_ema:
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['EMA20'],
                                 line=dict(color='blue', width=1), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['EMA50'],
                                 line=dict(color='purple', width=1), name='EMA 50'))

    if show_vwap:
        fig.add_trace(go.Scatter(x=df['Open Time'], y=df['VWAP'],
                                 line=dict(color='green', width=1), name='VWAP'))

    if show_volume:
        fig.add_trace(go.Bar(x=df['Open Time'], y=df['Volume'],
                             marker_color='lightblue', name='Volume', yaxis='y2'))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right', title='Volume'))

    return fig

# Alerts with Telegram
def generate_alerts(df):
    alert_msg = []
    if show_rsi and df['RSI'].iloc[-1] > 70:
        alert_msg.append("🔴 RSI Overbought (>70) — Possible Sell Signal")
    elif show_rsi and df['RSI'].iloc[-1] < 30:
        alert_msg.append("🟢 RSI Oversold (<30) — Possible Buy Signal")

    if show_macd and df['MACD'].iloc[-1] > df['Signal Line'].iloc[-1] and df['MACD'].iloc[-2] < df['Signal Line'].iloc[-2]:
        alert_msg.append("🟢 MACD Bullish Crossover — Buy Signal")
    elif show_macd and df['MACD'].iloc[-1] < df['Signal Line'].iloc[-1] and df['MACD'].iloc[-2] > df['Signal Line'].iloc[-2]:
        alert_msg.append("🔴 MACD Bearish Crossover — Sell Signal")

    for msg in alert_msg:
        send_telegram_alert(f"{symbol} ({interval})\n{msg}")

    return alert_msg

# Fetch + Render
if st.button("Fetch Data") or live_mode:
    placeholder = st.empty()
    while True:
        df = get_binance_klines(symbol, interval, start_date, end_date)
        if not df.empty:
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

            with placeholder.container():
                st.success(f"Fetched {len(df)} candles!")
                st.plotly_chart(plot_candlestick(df), use_container_width=True)

                st.subheader("📉 Data Table")
                st.dataframe(df)

                if show_rsi:
                    st.subheader("📈 RSI Chart")
                    fig_rsi = go.Figure()
                    fig_rsi.add_trace(go.Scatter(x=df['Open Time'], y=df['RSI'], name='RSI'))
                    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                    st.plotly_chart(fig_rsi, use_container_width=True)

                if show_macd:
                    st.subheader("📈 MACD Chart")
                    fig_macd = go.Figure()
                    fig_macd.add_trace(go.Scatter(x=df['Open Time'], y=df['MACD'], name='MACD'))
                    fig_macd.add_trace(go.Scatter(x=df['Open Time'], y=df['Signal Line'], name='Signal Line'))
                    st.plotly_chart(fig_macd, use_container_width=True)

                if show_alerts:
                    st.subheader("🚨 Alerts")
                    alerts = generate_alerts(df)
                    if alerts:
                        for msg in alerts:
                            st.warning(msg)
                    else:
                        st.info("📊 No strong signal — Wait for setup.")

        if not live_mode:
            break
        t.sleep(60)