#FOLDER_ID = '1NpdbS6_xXodFID9fvWCHfjlZC1u98ZJb'

import streamlit as st
import hashlib
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 安全金鑰：必須與監控程式端一致 ---
SECRET_SALT = st.secrets["SECRET_SALT"]

# --- 1. 核心設定區 ---
# 請填入您海象專用 Google 帳號雲端硬碟的資料夾 ID
FOLDER_ID = st.secrets["FOLDER_ID"]

def verify_access(order_id, token):
    if not order_id or not token:
        return False
    expected_token = hashlib.md5(f"{order_id}{SECRET_SALT}".encode()).hexdigest()[:10]
    return expected_token == token

# --- 2. Google Sheets 工具函式 ---
#def get_gspread_client():
#    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
#    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
#    return gspread.authorize(creds)

def get_gspread_client():
    """從 Streamlit Secrets 讀取憑證並建立連線"""
    # 直接從 secrets 中抓取剛剛貼上的 [gcp_service_account] 區塊
    creds_info = st.secrets["gcp_service_account"]
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # 注意：這裡改用 info 而不是 file
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

def get_or_create_daily_tab(client):
    """在總表中，按日期建立分頁"""
    MASTER_SHEET_NAME = "海象淨水_2026配送總表"
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        sh = client.open(MASTER_SHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"❌ 找不到總表：{MASTER_SHEET_NAME}")
        return None

    try:
        return sh.worksheet(today_str)
    except gspread.exceptions.WorksheetNotFound:
        new_ws = sh.add_worksheet(title=today_str, rows="100", cols="20")
        # [新增] 欄位標題增加「簽收狀態」
        new_ws.append_row(["回報時間", "送水單號", "簽收狀態", "實際配送桶數", "回收空桶數", "師傅備註"])
        return new_ws

# --- 3. 介面設定 ---
st.set_page_config(page_title="海象淨水 - 配送回報", page_icon="📦")
st.title("📦 配送回報系統")

# 抓取 URL 參數
query_params = st.query_params
order_id = query_params.get("id", "")
token = query_params.get("token", "")

# 預設值處理
try:
    default_transit = int(query_params.get("transit", 10))
    default_empty = int(query_params.get("empty", 5))
except (ValueError, TypeError):
    default_transit, default_empty = 10, 5

# --- 4. 安全檢查 ---
if not verify_access(order_id, token):
    st.error("🚫 存取拒絕：無效的連結。")
    st.stop()

# --- 5. 表單呈現 ---
if not order_id:
    st.warning("⚠️ 查無單據資訊。")
else:
    st.success(f"📍 正在處理送水單：**{order_id}**")

    with st.form("report_form", clear_on_submit=False):
        st.subheader("填寫回報資訊")
        
        actual_qty = st.number_input("今日實際送達桶數", min_value=0, value=default_transit, step=1)
        empty_qty = st.number_input("現場回收空桶數", min_value=0, value=default_empty, step=1)
        
        st.divider()

        # [新增] 簽收狀態按鈕 (水平排列)
        # 這會以按鈕形式呈現在畫面上，預設為「已簽收」
        delivery_status = st.radio(
            "簽收狀態",
            ["已簽收", "不在家"],
            horizontal=True,
            index=0,
            help="請選擇客戶簽收狀況"
        )

        note = st.text_area("備註說明", placeholder="若有特殊情況請註記...", height=100)
        
        st.divider()
        submitted = st.form_submit_button("確認並傳送至雲端", type="primary", use_container_width=True)

    if submitted:
        with st.spinner('同步中...'):
            try:
                client = get_gspread_client()
                sheet = get_or_create_daily_tab(client)
                
                if sheet:
                    report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # [修改] 寫入資料列，加入 delivery_status
                    row_data = [report_time, order_id, delivery_status, actual_qty, empty_qty, note]
                    
                    sheet.append_row(row_data)
                    
                    st.success(f"✅ 回報成功！狀態：{delivery_status}")
                    st.balloons()
            except Exception as e:
                st.error(f"❌ 儲存失敗：{str(e)}")

st.caption("© 2026 海象淨水 自動化作業系統")