import streamlit as st
from PIL import Image
import google.generativeai as genai
import re
import sqlite3
import datetime
from io import BytesIO

# --- アプリの基本設定 ---
st.set_page_config(page_title="AIイラストコーチ【真・完成版】", page_icon="🎨", layout="wide")
st.title("🎨 AIイラストコーチ【真・完成版】")
st.write("二次創作評価モードを追加！あなたのキャラクターへの愛をAIが評価します。")

# --- データベースの初期化 ---
DB_NAME = "illustration_history.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            score INTEGER,
            feedback TEXT,
            image_blob BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
init_db()

# --- データベース操作関数 ---
def add_history(mode, score, feedback, image):
    buf = BytesIO()
    image.save(buf, format='PNG')
    image_blob = buf.getvalue()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO history (mode, score, feedback, image_blob) VALUES (?, ?, ?, ?)",
              (mode, score, feedback, image_blob))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT mode, score, feedback, image_blob, created_at FROM history ORDER BY created_at DESC")
    history_data = c.fetchall()
    conn.close()
    return history_data

# --- 画像入力部分とスコア抽出関数 ---
def get_image_input(label="イラストを登録"):
    image_data = None
    tab1, tab2 = st.tabs(["📁 ファイルからアップロード", "📸 カメラで撮影"])
    with tab1:
        uploaded_file = st.file_uploader(label, type=["jpg", "jpeg", "png"], key=label+"_file")
        if uploaded_file:
            image_data = uploaded_file
    with tab2:
        camera_input = st.camera_input("カメラでイラストを撮影", key=label+"_cam")
        if camera_input:
            image_data = camera_input
    if image_data:
        return Image.open(image_data)
    return None

def extract_score(text):
    match = re.search(r"(?:総合評価|再現度|キャラクター再現度)\s*:\s*(\d{1,3})\s*点", text)
    if match:
        return int(match.group(1))
    return None

# --- サイドバー ---
st.sidebar.header("設定")
api_key = st.sidebar.text_input("Google AI の APIキーを入力してください", type="password")
app_mode = st.sidebar.radio("モードを選択してください", ("通常採点", "模写採点", "二次創作評価", "📈 成長の記録"))

# --- メイン画面 ---
if app_mode == "通常採点":
    st.subheader("【通常採点モード】")
    image = get_image_input()
    if image:
        col1, col2 = st.columns(2)
        with col1: st.image(image, caption="分析対象のイラスト", use_column_width=True)
        with col2:
            if api_key:
                if st.button("AIによる採点を開始する"):
                    prompt = "（省略...通常採点プロンプト）" # ここは元のプロンプト
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        with st.spinner("AIコーチが見ています..."): response = model.generate_content([prompt, image])
                        response_text, score = response.text, extract_score(response.text)
                        add_history("通常採点", score, response_text, image)
                        st.subheader("🤖 AIコーチからのフィードバック"); st.markdown(response_text)
                        if score is not None: st.success(f"スコア: {score}点 を記録しました！")
                    except Exception as e: st.error(f"エラーが発生しました: {e}")
            else: st.warning("APIキーを入力してください。")

elif app_mode == "模写採点":
    st.subheader("【模写採点モード】")
    original_image, mosha_image = None, None
    col1, col2 = st.columns(2)
    with col1: st.markdown("##### 1. お手本"); original_image = get_image_input(label="お手本")
    with col2: st.markdown("##### 2. あなたの模写"); mosha_image = get_image_input(label="模写")
    if original_image and mosha_image:
        st.image([original_image, mosha_image], caption=["お手本", "あなたの模写"], width=300)
        if api_key:
            if st.button("AIによる模写の採点を開始する"):
                prompt = "（省略...模写採点プロンプト）" # ここは元のプロンプト
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    with st.spinner("AI先生が見比べています..."): response = model.generate_content([prompt, original_image, mosha_image])
                    response_text, score = response.text, extract_score(response.text)
                    add_history("模写採点", score, response_text, mosha_image)
                    st.subheader("🤖 AI先生からの模写フィードバック"); st.markdown(response_text)
                    if score is not None: st.success(f"再現度: {score}点 を記録しました！")
                except Exception as e: st.error(f"エラーが発生しました: {e}")
        else: st.warning("APIキーを入力してください。")

elif app_mode == "二次創作評価":
    st.subheader("【二次創作評価モード】")
    st.info("「キャラクターの公式イラストなど」と「あなたの二次創作イラスト」をアップロードしてください。")
    original_image, fanart_image = None, None
    col1, col2 = st.columns(2)
    with col1: st.markdown("##### 1. お手本 (公式イラストなど)"); original_image = get_image_input(label="お手本")
    with col2: st.markdown("##### 2. あなたの二次創作イラスト"); fanart_image = get_image_input(label="二次創作")
    if original_image and fanart_image:
        st.image([original_image, fanart_image], caption=["お手本", "あなたの二次創作"], width=300)
        if api_key:
            if st.button("AIによる二次創作の評価を開始する"):
                prompt = """
あなたは、アニメやゲームのキャラクターグッズを監修するプロの編集者であり、熱心なファンでもあります。
今から2枚の画像を見せます。1枚目は「キャラクターの公式資料(お手本)」、2枚目はファンが描いた「二次創作イラスト」です。
ファンとしての愛情ある視点と、プロとしての厳しい視点の両方から、2枚を詳細に比較し、以下の項目について評価とアドバイスをしてください。
# 評価項目
* **キャラクター再現度 (100点満点):** 髪型、顔のパーツ、表情など、そのキャラクター「らしさ」がどれだけ再現できているかを点数で評価してください。
* **デザインの正確性:** 衣装やアクセサリー、持ち物などのデザインがお手本に忠実か、細部まで描き込まれているかを評価してください。
* **画風とアレンジ:** あなたの独自の画風で描かれていますね。そのアレンジが、キャラクターの魅力を損なわずに新しい魅力を引き出せているかを評価してください。
* **キャラクターへの愛:** イラスト全体から、あなたがこのキャラクターをどれだけ好きで、理解しているかが伝わってきます。その「愛」の深さを評価してください。
# 上達へのアドバイス
上記の評価を踏まえ、この二次創作イラストが、ファンとして「もっと解釈が深まる」、あるいは「もっと多くの人に魅力が伝わる」作品になるためにはどうすれば良いか、具体的で愛のあるアドバイスを、優しい口調で教えてください。
"""
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    with st.spinner("AI編集者が愛の深さをチェックしています..."):
                        response = model.generate_content([prompt, original_image, fanart_image])
                    response_text, score = response.text, extract_score(response.text)
                    add_history("二次創作評価", score, response_text, fanart_image)
                    st.subheader("🤖 AI編集者からのファンアートレビュー"); st.markdown(response_text)
                    if score is not None: st.success(f"キャラクター再現度: {score}点 を記録しました！")
                except Exception as e: st.error(f"エラーが発生しました: {e}")
        else: st.warning("APIキーを入力してください。")

elif app_mode == "📈 成長の記録":
    st.subheader("【📈 成長の記録】")
    history = get_history()
    if not history: st.warning("まだ採点履歴がありません。")
    else:
        scores = [h['score'] for h in history if h['score'] is not None]
        scores.reverse()
        if scores:
            average_score = sum(scores) / len(scores)
            st.metric(label="平均スコア", value=f"{average_score:.1f} 点", delta=f"{scores[-1] - scores[0]:.1f} 点 (初回との差)")
            st.line_chart(scores, use_container_width=True)
        st.write("---"); st.write("### 採点履歴")
        for record in history:
            with st.expander(f"{record['created_at'].split('.')[0]} - スコア: {record['score'] or 'N/A'}点 ({record['mode']})"):
                img = Image.open(BytesIO(record['image_blob']))
                st.image(img, width=200); st.markdown(record['feedback'])
