import streamlit as st
from PIL import Image
import google.generativeai as genai
import re
import sqlite3
import datetime
from io import BytesIO

# --- アプリの基本設定 ---
st.set_page_config(page_title="AIイラストコーチ【完成版】", page_icon="🎨", layout="wide")

# --- カスタムCSSデザイン ---
st.markdown("""
<style>
    /* Google Fontsから柔らかい印象のフォントをインポート */
    @import url('https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@400;700&display=swap');

    /* --- 全体の基本スタイル（アイコン文字化け対策済み） --- */
    body, .stApp, .st-emotion-cache-16txtl3, .stButton, .stTabs {
        font-family: 'M PLUS Rounded 1c', sans-serif;
    }

    /* メインエリアの背景色 */
    .stApp {
        background-color: #FFF8E1; /* クリーム色のような薄い黄色 */
    }

    /* --- サイドバーのデザイン --- */
    .st-emotion-cache-16txtl3 {
        background-color: #FFFFFF; /* サイドバーは白で清潔感を */
    }

    /* --- 見出しのスタイル --- */
    h1, h2, h3 {
        color: #D2691E; /* チョコレート色で見出しを引き締める */
    }
    
    /* --- 親しみやすいボタンのデザイン --- */
    .stButton > button {
        color: #FFFFFF; /* 文字色は白 */
        background-color: #FFC107; /* テーマカラーの優しいオレンジ（黄色寄り）*/
        border-radius: 50px; /* 角を完全に丸くして、円形に近づける */
        border: none; /* 枠線をなくす */
        padding: 12px 24px; /* ボタンの余白を調整 */
        font-weight: 700; /* 文字を太くして視認性を上げる */
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); /* 優しい影をつける */
        transition: all 0.2s ease-in-out; /* ホバー時のアニメーション */
    }

    /* ボタンにマウスを乗せた時のスタイル */
    .stButton > button:hover {
        background-color: #FFA000; /* 少し濃いオレンジに */
        box-shadow: 0 6px 8px rgba(0,0,0,0.15); /* 影を少し大きく */
        transform: translateY(-2px); /* 少しだけボタンを浮かせる */
    }

    /* --- タブのデザイン --- */
    .stTabs [data-baseweb="tab-list"] {
		gap: 5px;
        border-bottom: 2px solid #FFECB3;
	}
    .stTabs [data-baseweb="tab"] {
		height: 50px;
        background-color: transparent;
        border-radius: 8px 8px 0px 0px;
		padding-top: 10px;
		padding-bottom: 10px;
        color: #AF640C;
	}
    .stTabs [aria-selected="true"] {
  		background-color: #FFECB3;
        font-weight: bold;
        color: #D2691E;
	}

    /* --- 情報ボックス（st.infoなど）のスタイル --- */
    .stAlert {
        border-radius: 10px;
        border-left: 5px solid #FFC107;
    }

</style>
""", unsafe_allow_html=True)

st.title("🎨 AIイラストコーチ【完成版】")
st.write("あなたのイラストの上達を、AIが愛をもってサポートします。")

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

# --- ヘルパー関数 ---
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
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    api_key = st.sidebar.text_input("Google AI の APIキーを入力してください", type="password")

app_mode = st.sidebar.radio(
    "モードを選択してください",
    ("通常採点", "模写採点", "二次創作評価", "📈 成長の記録")
)

# --- メイン画面 ---
if app_mode == "通常採点":
    st.subheader("【通常採点モード】")
    st.info("オリジナルのイラストをアップロードすると、AIがプロの視点で評価とアドバイスをします。")
    image = get_image_input()
    if image:
        col1, col2 = st.columns(2)
        with col1:
            st.image(image, caption="分析対象のイラスト", use_column_width=True)
        with col2:
            if api_key:
                if st.button("AIによる採点を開始する"):
                    prompt = """
あなたはプロのイラストレーターであり、イラストの批評家です。
アップロードされたイラストを分析し、以下の項目に従って詳細なレビューと採点を行ってください。
# 評価項目
* 総合評価 (100点満点): 全体的な完成度を点数で評価してください。
* 構図: キャラクターの配置、背景とのバランス、視線誘導など。
* デッサン: 人体のプロポーション、パース、形の正確さなど。
* 色彩: 色の組み合わせ、塗り方、光と影の表現など。
* 魅力と独創性: イラスト全体の魅力、オリジナリティ、コンセプトなど。
# アドバイス
上記の評価項目を踏まえ、このイラストがさらに良くなるための、具体的で実践的なアドバイスを初心者にわかるように、優しい口調で教えてください。
"""
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        with st.spinner("AIコーチがあなたのイラストをじっくり見ています..."):
                            response = model.generate_content([prompt, image])
                        response_text = response.text
                        score = extract_score(response_text)
                        add_history("通常採点", score, response_text, image)
                        st.subheader("🤖 AIコーチからのフィードバック")
                        st.markdown(response_text)
                        if score is not None:
                            st.success(f"スコア: {score}点 をデータベースに記録しました！")
                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
            else:
                st.warning("サイドバーからAPIキーを入力してください。")

elif app_mode == "模写採点":
    st.subheader("【模写採点モード】")
    st.info("「お手本」と「あなたが描いた模写」の2枚をアップロードしてください。AIが2枚を比較して、改善点をアドバイスします。")
    original_image, mosha_image = None, None
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 1. お手本")
        original_image = get_image_input(label="お手本")
    with col2:
        st.markdown("##### 2. あなたが描いた模写")
        mosha_image = get_image_input(label="模写")
    if original_image and mosha_image:
        st.image([original_image, mosha_image], caption=["お手本", "あなたの模写"], width=300)
        if api_key:
            if st.button("AIによる模写の採点を開始する"):
                prompt = """
あなたは非常に優れたイラストの先生です。
今から2枚の画像を見せます。1枚目は「お手本」、2枚目は生徒がそれを「模写した絵」です。
2枚を詳細に比較し、以下の項目について評価とアドバイスをしてください。
# 評価項目
* 再現度 (100点満点): お手本をどれだけ忠実に再現できているかを点数で評価してください。
* 形の捉え方: 全体的なシルエットやパーツの形の正確さについて評価してください。お手本と大きく違う部分を具体的に指摘してください。
* 線の正確さ: 線の硬さや柔らかさ、勢いなど、線の質がお手本と比べてどうかを評価してください。
* 色の再現性: 使われている色がお手本の印象と近いか、塗り方の再現度はどうかを評価してください。
# 上達へのアドバイス
上記の評価を踏まえ、この生徒の模写がもっとお手本に近づくためには、どこを重点的に練習・修正すれば良いか、具体的で実践的なアドバイスを初心者にわかるように、優しい口調で教えてください。
"""
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    with st.spinner("AI先生がお手本と見比べています..."):
                        response = model.generate_content([prompt, original_image, mosha_image])
                    response_text = response.text
                    score = extract_score(response_text)
                    add_history("模写採点", score, response_text, mosha_image)
                    st.subheader("🤖 AI先生からの模写フィードバック")
                    st.markdown(response_text)
                    if score is not None:
                        st.success(f"再現度: {score}点 をデータベースに記録しました！")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
        else:
            st.warning("サイドバーからAPIキーを入力してください。")

elif app_mode == "二次創作評価":
    st.subheader("【二次創作評価モード】")
    st.info("「キャラクターの公式イラストなど」と「あなたの二次創作イラスト」をアップロードしてください。")
    original_image, fanart_image = None, None
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 1. お手本 (公式イラストなど)")
        original_image = get_image_input(label="お手本")
    with col2:
        st.markdown("##### 2. あなたの二次創作イラスト")
        fanart_image = get_image_input(label="二次創作")
    if original_image and fanart_image:
        st.image([original_image, fanart_image], caption=["お手本", "あなたの二次創作"], width=300)
        if api_key:
            if st.button("AIによる二次創作の評価を開始する"):
                prompt = """
あなたは、アニメやゲームのキャラクターグッズを監修するプロの編集者であり、熱心なファンでもあります。
今から2枚の画像を見せます。1枚目は「キャラクターの公式資料(お手本)」、2枚目はファンが描いた「二次創作イラスト」です。
ファンとしての愛情ある視点と、プロとしての厳しい視点の両方から、2枚を詳細に比較し、以下の項目について評価とアドバイスをしてください。
# 評価項目
* キャラクター再現度 (100点満点): 髪型、顔のパーツ、表情など、そのキャラクター「らしさ」がどれだけ再現できているかを点数で評価してください。
* デザインの正確性: 衣装やアクセサリー、持ち物などのデザインがお手本に忠実か、細部まで描き込まれているかを評価してください。
* 画風とアレンジ: あなたの独自の画風で描かれていますね。そのアレンジが、キャラクターの魅力を損なわずに新しい魅力を引き出せているかを評価してください。
* キャラクターへの愛: イラスト全体から、あなたがこのキャラクターをどれだけ好きで、理解しているかが伝わってきます。その「愛」の深さを評価してください。
# 上達へのアドバイス
上記の評価を踏まえ、この二次創作イラストが、ファンとして「もっと解釈が深まる」、あるいは「もっと多くの人に魅力が伝わる」作品になるためにはどうすれば良いか、具体的で愛のあるアドバイスを、優しい口調で教えてください。
"""
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    with st.spinner("AI編集者が愛の深さをチェックしています..."):
                        response = model.generate_content([prompt, original_image, fanart_image])
                    response_text = response.text
                    score = extract_score(response_text)
                    add_history("二次創作評価", score, response_text, fanart_image)
                    st.subheader("🤖 AI編集者からのファンアートレビュー")
                    st.markdown(response_text)
                    if score is not None:
                        st.success(f"キャラクター再現度: {score}点 をデータベースに記録しました！")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
        else:
            st.warning("サイドバーからAPIキーを入力してください。")

elif app_mode == "📈 成長の記録":
    st.subheader("【📈 成長の記録】")
    st.info("これまでの採点履歴を確認できます。スコアの推移を見て、自分の成長を実感しましょう！")
    history = get_history()
    if not history:
        st.warning("まだ採点履歴がありません。「通常採点」や「模写採点」などのモードで分析を行うと、ここに記録が追加されます。")
    else:
        scores = [h['score'] for h in history if h['score'] is not None]
        scores.reverse()
        if scores:
            average_score = sum(scores) / len(scores)
            st.metric(label="平均スコア", value=f"{average_score:.1f} 点", delta=f"{scores[-1] - scores[0]:.1f} 点 (初回との差)")
            st.line_chart(scores, use_container_width=True)
        st.write("---")
        st.write("### 採点履歴")
        for record in history:
            with st.expander(f"{record['created_at'].split('.')[0]} - スコア: {record['score'] or 'N/A'}点 ({record['mode']})"):
                img = Image.open(BytesIO(record['image_blob']))
                st.image(img, width=200)
                st.markdown(record['feedback'])
