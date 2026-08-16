import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import re
from urllib.parse import quote

# ページの設定
st.set_page_config(page_title="ミネルヴィニ判定アプリ", layout="wide")
st.title("📈 ミネルヴィニ・トレンド・テンプレート判定")

# 履歴を保存する仕組み（Streamlit独自の書き方）
if 'history' not in st.session_state:
    st.session_state.history = []

def get_ticker_symbol(query):
    query = query.strip()
    if query.isdigit() and len(query) == 4: return query + ".T"
    if re.match(r'^[A-Za-z0-9\.]+$', query): return query.upper()
    try:
        url = f"https://finance.yahoo.co.jp/search/?query={quote(query)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            matches = re.findall(r'/quote/(\d{4}(?:\.T)?)', resp.text)
            if matches:
                code = matches[0]
                return code if code.endswith('.T') else code + '.T'
    except Exception: pass
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={quote(query)}&quotesCount=5"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            for q in resp.json().get('quotes', []):
                symbol = q.get('symbol', '')
                if symbol.endswith('.T') or re.match(r'^[A-Z]+$', symbol): return symbol
    except Exception: pass
    return query

# 入力フォーム
with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        raw_input = st.text_input("銘柄コード（例: 7203）または企業名（例: トヨタ）", placeholder="トヨタ")
    with col2:
        st.write("") # ボタンの位置調整
        st.write("")
        submit_button = st.form_submit_button(label='判定する')

if submit_button and raw_input:
    with st.spinner(f"「{raw_input}」を検索中..."):
        ticker_symbol = get_ticker_symbol(raw_input)
        
        try:
            stock = yf.Ticker(ticker_symbol)
            df = stock.history(period="2y")

            if df.empty:
                st.error(f"❌ データが取得できませんでした。入力した名前（{raw_input}）またはコード（{ticker_symbol}）が正しいか確認してください。")
            else:
                company_name = ticker_symbol
                try:
                    info = stock.info
                    company_name = info.get('shortName') or info.get('longName') or ticker_symbol
                except Exception:
                    pass

                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['MA150'] = df['Close'].rolling(window=150).mean()
                df['MA200'] = df['Close'].rolling(window=200).mean()
                df['52W_High'] = df['Close'].rolling(window=250).max()
                df['52W_Low'] = df['Close'].rolling(window=250).min()

                latest = df.iloc[-1]
                current_price = latest['Close']
                ma50 = latest['MA50']
                ma150 = latest['MA150']
                ma200 = latest['MA200']
                high_52w = latest['52W_High']
                low_52w = latest['52W_Low']
                ma200_20days_ago = df['MA200'].iloc[-20]
                is_ma200_uptrend = ma200 > ma200_20days_ago

                cond1 = (current_price > ma150) and (current_price > ma200)
                cond2 = (ma150 > ma200)
                cond3 = is_ma200_uptrend
                cond4 = (ma50 > ma150) and (ma50 > ma200)
                cond5 = (current_price > ma50)
                cond6 = (current_price >= low_52w * 1.30)
                cond7 = (current_price >= high_52w * 0.75)

                score = sum([cond1, cond2, cond3, cond4, cond5, cond6, cond7])

                if score == 7: result_mark = "🌟合格"
                elif score >= 5 and cond1: result_mark = "👀予備軍"
                else: result_mark = "❌不合格"

                # 履歴に追加
                st.session_state.history.append({
                    "コード": ticker_symbol,
                    "企業名": company_name,
                    "判定": result_mark,
                    "スコア": f"{score}/7",
                    "クリア数": score,
                    "株価": round(current_price, 2),
                    "条件1(株価>150,200)": '✅' if cond1 else '❌',
                    "条件2(150>200)": '✅' if cond2 else '❌',
                    "条件3(200上昇)": '✅' if cond3 else '❌',
                    "条件4(50>150,200)": '✅' if cond4 else '❌',
                    "条件5(株価>50)": '✅' if cond5 else '❌',
                    "条件6(安値+30%)": '✅' if cond6 else '❌',
                    "条件7(高値-25%)": '✅' if cond7 else '❌'
                })
                
                st.success(f"【最新の判定結果: {company_name} ({ticker_symbol})】 -> {result_mark} ({score}/7条件達成)")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# 履歴テーブルの表示
if st.session_state.history:
    st.subheader("=== 判定履歴（合格・予備軍順） ===")
    history_df = pd.DataFrame(st.session_state.history)
    history_df = history_df.drop_duplicates(subset=['コード'], keep='last')
    history_df = history_df.sort_values(by="クリア数", ascending=False)
    display_df = history_df.drop(columns=["クリア数"])
    st.dataframe(display_df, use_container_width=True)

# メモの表示（アコーディオン式で隠せるように）
with st.expander("💡 メモ：各条件が重要な理由（第2ステージの証拠）"):
    st.markdown("""
    * **条件1（株価 > 150日＆200日MA）**: 下落トレンドや底練りを脱し、明確な上昇局面（第2ステージ）に入っている大前提。
    * **条件2（150日MA > 200日MA）**: 中期的な勢いが長期を上回っており、上昇に勢いがついている証拠。
    * **条件3（200日MAが1ヶ月以上上昇）**: 長期トレンドが上向き。機関投資家による継続的な資金流入の証拠。
    * **条件4（50日MA > 150日＆200日MA）**: 短期・中期・長期の線が下から順に並ぶ「パーフェクトオーダー」。強い買いの勢い。
    * **条件5（株価 > 50日MA）**: 短期的な調整局面でもトレンドが崩れていないかの確認。
    * **条件6（株価が52週安値から+30%以上）**: 大底から力強く反発しているか（最良の株は底値から大きく上昇している）。
    * **条件7（株価が52週高値から-25%以内）**: 高値圏でのベース固め。「やれやれ売り（しこり玉）」の抵抗が少ない状態。
    """)
