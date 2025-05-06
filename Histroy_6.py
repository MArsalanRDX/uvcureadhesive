import streamlit as st

st.title("🪙 Gold Buy/Sell Profit Calculator")

# Input fields
buy_price = st.number_input("💰 Buy Price (per Tola)", format="%.2f", value=0.105890)
sell_price = st.number_input("💸 Sell Price (per Tola)", format="%.2f", value=0.115890)
capital = st.number_input("💵 Your Investment:", value=350000.0)

# Calculation
if buy_price > 0:
    coins = capital / buy_price
    total_sell = coins * sell_price
    profit = total_sell - capital

    # Display Results
    st.markdown("### 📊 Result")
    st.write(f"🔹 **Coins Bought:** {coins:.2f}")
    st.write(f"🔹 **Sell Value:** {total_sell:.2f} USDT")
    st.write(f"✅ **Profit:** {profit:.2f} USDT")
else:
    st.error("Buy price must be greater than 0.")
