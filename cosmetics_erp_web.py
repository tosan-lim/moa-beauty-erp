import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import base64
import requests
import hashlib
import io

# -------------------------------------------------------------------
# 🔒 GitHub 연동 설정
# -------------------------------------------------------------------
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
except:
    GITHUB_TOKEN = None
    REPO_NAME = None

FILE_PATH = "kil_india_erp.db"

def push_db_to_github():
    if not GITHUB_TOKEN or not REPO_NAME: return
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.get(url, headers=headers)
        sha = response.json()['sha'] if response.status_code == 200 else None
        with open(FILE_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        data = {"message": f"Auto-backup DB via Streamlit ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})", "content": content}
        if sha: data["sha"] = sha
        requests.put(url, headers=headers, json=data)
    except Exception as e:
        print(f"GitHub Push 오류: {e}")

# -------------------------------------------------------------------
# 🛠️ 데이터베이스 설정 및 자동 업그레이드
# -------------------------------------------------------------------
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

def get_db_connection():
    conn = sqlite3.connect('kil_india_erp.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        partner_code TEXT PRIMARY KEY, partner_name TEXT NOT NULL, type TEXT,
        phone TEXT, email TEXT, state TEXT, address TEXT, contact_person TEXT, category TEXT, registration_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL, email TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, trans_date TEXT, trans_type TEXT, 
        partner_name TEXT, item_name TEXT, qty INTEGER, price REAL, total_amount REAL, manager TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS manual_cashbook (
        id INTEGER PRIMARY KEY AUTOINCREMENT, trans_date TEXT, type TEXT, 
        description TEXT, amount REAL, payment_method TEXT, remarks TEXT, manager TEXT)''')
    
    # 🛒 [E-commerce 테이블 신설]
    c.execute('''CREATE TABLE IF NOT EXISTS ecommerce_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, trans_date TEXT, platform TEXT, trans_type TEXT,
        item_code TEXT, item_name TEXT, qty INTEGER, purchase_price REAL, selling_price REAL, 
        total_amount REAL, remarks TEXT, manager TEXT)''')
    
    # DB 컬럼 자동 업그레이드
    c.execute("PRAGMA table_info(transactions)")
    columns = [info[1] for info in c.fetchall()]
    if 'item_code' not in columns: c.execute("ALTER TABLE transactions ADD COLUMN item_code TEXT")
    if 'image_base64' not in columns: c.execute("ALTER TABLE transactions ADD COLUMN image_base64 TEXT")
    if 'payment_method' not in columns: c.execute("ALTER TABLE transactions ADD COLUMN payment_method TEXT")
    if 'remarks' not in columns: c.execute("ALTER TABLE transactions ADD COLUMN remarks TEXT")
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, name, role, email, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
                  ('admin', make_hashes("admin123"), '대표/관리자', 'Admin', 'admin@kecindia.in', datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# 🌐 웹 앱 설정 및 로그인
# -------------------------------------------------------------------
st.set_page_config(page_title="KIL INDIA - Moa Beauty ERP", layout="wide")
init_db()

for key in ['logged_in', 'username', 'user_role', 'user_name']:
    if key not in st.session_state: st.session_state[key] = False if key == 'logged_in' else ''

if not st.session_state['logged_in']:
    st.markdown("<h2 style='text-align: center;'>KIL INDIA TRADE PVT. LTD.</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Moa Beauty ERP System 로그인</h4>", unsafe_allow_html=True)
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username_input = st.text_input("아이디 (Username)")
            password_input = st.text_input("비밀번호 (Password)", type="password")
            if st.form_submit_button("로그인 (Sign In)", type="primary", use_container_width=True):
                conn = get_db_connection()
                user = conn.cursor().execute("SELECT * FROM users WHERE username = ?", (username_input,)).fetchone()
                conn.close()
                if user and check_hashes(password_input, user['password']):
                    st.session_state.update({'logged_in': True, 'username': user['username'], 'user_role': user['role'], 'user_name': user['name']})
                    st.rerun()
                else: st.error("아이디 또는 비밀번호가 오류입니다.")
    st.stop()

# -------------------------------------------------------------------
# 🏢 ERP 메인 화면 및 사이드바
# -------------------------------------------------------------------
with st.sidebar:
    st.markdown("### KIL INDIA TRADE")
    st.info(f"👤 **{st.session_state['user_name']}**\n\n🎖️ 권한: **{st.session_state['user_role']}**")
    
    with st.expander("🔑 내 비밀번호 변경"):
        with st.form("change_pwd_form", clear_on_submit=True):
            current_pw = st.text_input("현재 비밀번호", type="password")
            new_pw = st.text_input("새 비밀번호", type="password")
            new_pw_confirm = st.text_input("새 비밀번호 확인", type="password")
            if st.form_submit_button("변경하기"):
                if new_pw and new_pw == new_pw_confirm:
                    conn = get_db_connection()
                    user = conn.cursor().execute("SELECT password FROM users WHERE username = ?", (st.session_state['username'],)).fetchone()
                    if user and check_hashes(current_pw, user['password']):
                        conn.execute("UPDATE users SET password=? WHERE username=?", (make_hashes(new_pw), st.session_state['username']))
                        conn.commit(); conn.close(); push_db_to_github(); st.success("비밀번호 변경 완료!")
                    else: st.error("현재 비밀번호 불일치")
                else: st.error("새 비밀번호 불일치")
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.update({'logged_in': False, 'username': '', 'user_role': '', 'user_name': ''})
        st.rerun()

st.title('KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP')
st.markdown("---")

# 🛒 [재고현황 다음에 E-commerce 탭 추가!]
if st.session_state['user_role'] == 'Admin':
    tab1, tab_user, tab2, tab3, tab_inv, tab_ecom, tab_cb, tab4 = st.tabs(['📋 기초등록', '👥 직원관리', '📦 구매/입고', '🏷️ 판매/출고', '🏢 재고현황', '🛒 E-commerce', '💰 입출금장부', '📊 엑셀 관리'])
else:
    tab1, tab2, tab3, tab_inv, tab_ecom, tab_cb, tab4 = st.tabs(['📋 기초등록', '📦 구매/입고', '🏷️ 판매/출고', '🏢 재고현황', '🛒 E-commerce', '💰 입출금장부', '📊 엑셀 관리'])
    tab_user = None

conn = get_db_connection()
df_partners = pd.read_sql_query("SELECT * FROM partners", conn)
conn.close()
type_col = 'type' if 'type' in df_partners.columns else ('partner_type' if 'partner_type' in df_partners.columns else None)
if not df_partners.empty and type_col and 'partner_name' in df_partners.columns:
    sellers = df_partners[df_partners[type_col].astype(str).str.contains('매입|Seller', na=False)]['partner_name'].tolist()
    buyers = df_partners[df_partners[type_col].astype(str).str.contains('매출|Buyer', na=False)]['partner_name'].tolist()
else: sellers, buyers = [], []
if not sellers: sellers = ["매입처 없음"]
if not buyers: buyers = ["매출처 없음"]

PAYMENT_METHODS = ["현금", "예금", "credit", "upi", "기타"]
ECOM_PLATFORMS = ["Amazon", "MoaBeauty", "KoreanShop", "Others"]

# ==========================================
# 탭 1 ~ Admin
# ==========================================
with tab1:
    st.subheader("거래처 상세 등록")
    with st.form("partner_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1: p_code = st.text_input("거래처코드"); p_phone = st.text_input("전화번호")
        with c2: p_name = st.text_input("상호명"); p_email = st.text_input("이메일")
        with c3: p_type = st.selectbox("구분", ["매출처/Buyer", "매입처/Seller"]); p_category = st.text_input("카테고리")
        if st.form_submit_button("저장", type="primary") and p_code and p_name:
            conn = get_db_connection(); conn.execute("INSERT OR REPLACE INTO partners (partner_code, partner_name, type, phone, email, category, registration_date) VALUES (?, ?, ?, ?, ?, ?, ?)", (p_code, p_name, p_type, p_phone, p_email, p_category, datetime.now().strftime("%Y-%m-%d")))
            conn.commit(); conn.close(); push_db_to_github(); st.success("저장 완료!"); st.rerun()
    st.dataframe(df_partners, use_container_width=True, hide_index=True)

if tab_user:
    with tab_user:
        st.subheader("👥 직원 관리")
        col_u1, col_u2 = st.columns([1, 1.5])
        with col_u1:
            with st.form("new_user_form", clear_on_submit=True):
                new_username = st.text_input("아이디 (Username)"); new_password = st.text_input("초기 비밀번호 부여", type="password")
                new_name = st.text_input("이름"); new_role = st.selectbox("권한", ["Staff", "Manager", "Admin"])
                if st.form_submit_button("계정 생성", type="primary") and new_username and new_password:
                    try:
                        conn = get_db_connection(); conn.execute("INSERT INTO users (username, password, name, role, created_at) VALUES (?, ?, ?, ?, ?)", (new_username, make_hashes(new_password), new_name, new_role, datetime.now().strftime("%Y-%m-%d")))
                        conn.commit(); conn.close(); push_db_to_github(); st.success("생성 완료!"); st.rerun()
                    except: st.error("중복된 아이디")
            st.markdown("---")
            conn = get_db_connection()
            user_list = [row['username'] for row in conn.cursor().execute("SELECT username FROM users").fetchall()]
            conn.close()
            target_user = st.selectbox("수정/삭제할 아이디", options=user_list)
            if target_user:
                with st.form("edit_user_form"):
                    edit_role = st.selectbox("새 권한", ["Staff", "Manager", "Admin"]); edit_password = st.text_input("새 비밀번호 (유지시 빈칸)", type="password")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.form_submit_button("정보 수정", type="primary"):
                            conn = get_db_connection()
                            if edit_password: conn.execute("UPDATE users SET password=?, role=? WHERE username=?", (make_hashes(edit_password), edit_role, target_user))
                            else: conn.execute("UPDATE users SET role=? WHERE username=?", (edit_role, target_user))
                            conn.commit(); conn.close(); push_db_to_github(); st.success("수정 완료!"); st.rerun()
                    with b2:
                        if target_user != 'admin' and st.form_submit_button("🚨 삭제"):
                            conn = get_db_connection(); conn.execute("DELETE FROM users WHERE username=?", (target_user,)); conn.commit(); conn.close(); push_db_to_github(); st.rerun()
        with col_u2:
            conn = get_db_connection(); df_users = pd.read_sql_query("SELECT username as 아이디, name as 이름, role as 권한, created_at as 등록일 FROM users", conn); conn.close()
            st.dataframe(df_users, use_container_width=True, hide_index=True)

# ==========================================
# 탭 2: 구매/입고
# ==========================================
with tab2:
    st.subheader("📦 상품 입고 등록")
    with st.form("purchase_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("입고 일자")
            partner_name = st.selectbox("매입처 (Seller)", options=sellers)
            item_code = st.text_input("상품코드")
            payment_method = st.selectbox("결제 수단", options=PAYMENT_METHODS)
        with col2:
            item_name = st.text_input("상품명")
            qty = st.number_input("수량", min_value=1, step=1)
            image_file = st.file_uploader("이미지 첨부", type=['jpg', 'jpeg', 'png'])
            remarks = st.text_input("비고")
        with col3:
            price = st.number_input("단가", min_value=0.0, step=0.1)
            total_amount = qty * price
            st.info(f"총 금액: {total_amount:,.2f}")
            
        if st.form_submit_button("입고 등록", type="primary") and item_name and item_code and partner_name != "매입처 없음":
            img_b64 = base64.b64encode(image_file.read()).decode('utf-8') if image_file else ""
            conn = get_db_connection()
            conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager, image_base64, payment_method, remarks) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (trans_date, "입고", partner_name, item_code, item_name, qty, price, total_amount, st.session_state['user_name'], img_b64, payment_method, remarks))
            conn.commit(); conn.close(); push_db_to_github(); st.success("등록 완료!"); st.rerun()

    conn = get_db_connection()
    df_in_raw = pd.read_sql_query("SELECT id, trans_date, partner_name, item_code, item_name, qty, price, total_amount, payment_method, remarks, manager, image_base64 FROM transactions WHERE trans_type='입고' ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    if not df_in_raw.empty:
        df_in = df_in_raw.copy()
        df_in['사진'] = df_in['image_base64'].apply(lambda x: f"data:image/png;base64,{x}" if pd.notnull(x) and x != "" else None)
        df_in_display = df_in.rename(columns={'id':'ID', 'trans_date':'일자', 'partner_name':'매입처', 'item_code':'코드', 'item_name':'상품명', 'qty':'수량', 'price':'단가', 'total_amount':'총액', 'payment_method':'결제수단', 'remarks':'비고', 'manager':'담당자'}).drop(columns=['image_base64'])
        st.dataframe(df_in_display, column_config={"사진": st.column_config.ImageColumn("사진")}, use_container_width=True, hide_index=True)

# ==========================================
# 탭 3: 판매/출고
# ==========================================
with tab3:
    st.subheader("🏷️ 상품 출고 등록")
    with st.form("sales_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("출고 일자")
            partner_name = st.selectbox("매출처 (Buyer)", options=buyers)
            item_code = st.text_input("상품코드")
            payment_method = st.selectbox("결제 수단", options=PAYMENT_METHODS)
        with col2:
            item_name = st.text_input("상품명")
            qty = st.number_input("출고 수량", min_value=1, step=1)
            remarks = st.text_input("비고")
        with col3:
            price = st.number_input("판매 단가", min_value=0.0, step=0.1)
            total_amount = qty * price
            st.info(f"총 금액: {total_amount:,.2f}")
            
        if st.form_submit_button("출고 등록", type="primary") and item_name and item_code and partner_name != "매출처 없음":
            conn = get_db_connection()
            conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, payment_method, remarks, manager) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (trans_date, "출고", partner_name, item_code, item_name, qty, price, total_amount, payment_method, remarks, st.session_state['user_name']))
            conn.commit(); conn.close(); push_db_to_github(); st.success("등록 완료!"); st.rerun()

    conn = get_db_connection()
    df_out_raw = pd.read_sql_query("SELECT id, trans_date, partner_name, item_code, item_name, qty, price, total_amount, payment_method, remarks, manager FROM transactions WHERE trans_type='출고' ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    if not df_out_raw.empty:
        df_out_display = df_out_raw.rename(columns={'id':'ID', 'trans_date':'일자', 'partner_name':'매출처', 'item_code':'코드', 'item_name':'상품명', 'qty':'수량', 'price':'단가', 'total_amount':'총액', 'payment_method':'결제수단', 'remarks':'비고', 'manager':'담당자'})
        st.dataframe(df_out_display, use_container_width=True, hide_index=True)

# ==========================================
# 탭 재고: 실시간 재고 현황
# ==========================================
with tab_inv:
    st.subheader("🏢 실시간 상품 재고 및 금액 현황")
    conn = get_db_connection()
    df_inv = pd.read_sql_query("SELECT item_code, item_name, SUM(CASE WHEN trans_type='입고' THEN qty ELSE 0 END) AS in_qty, SUM(CASE WHEN trans_type='출고' THEN qty ELSE 0 END) AS out_qty, AVG(CASE WHEN trans_type='입고' THEN price ELSE NULL END) AS avg_price FROM transactions WHERE item_code IS NOT NULL GROUP BY item_code, item_name", conn)
    conn.close()
    if not df_inv.empty:
        df_inv['현재재고'] = df_inv['in_qty'] - df_inv['out_qty']
        df_inv['평균단가'] = df_inv['avg_price'].fillna(0).round(2)
        df_inv['총금액'] = (df_inv['현재재고'] * df_inv['평균단가']).round(2)
        st.dataframe(df_inv[['item_code', 'item_name', '현재재고', '평균단가', '총금액']].rename(columns={'item_code':'상품코드', 'item_name':'상품명'}), use_container_width=True, hide_index=True)

# ==========================================
# 🔥 탭 E-commerce: 🛒 E-commerce 관리 (신규 추가!)
# ==========================================
with tab_ecom:
    st.subheader("🛒 E-commerce Loading & Unloading 관리")
    st.info("Amazon, MoaBeauty, KoreanShop, Others 플랫폼별 상품 Loading 및 Unloading 현황을 등록하고 관리합니다.")

    # 1. 등록 양식
    with st.form("ecom_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ec_date = st.date_input("일자")
            ec_platform = st.selectbox("E-commerce 플랫폼", options=ECOM_PLATFORMS)
            ec_type = st.selectbox("구분", options=["Loading", "Unloading"])
        with col2:
            ec_code = st.text_input("상품코드 (Item Code)")
            ec_name = st.text_input("품목 (Item Name)")
            ec_qty = st.number_input("수량 (Qty)", min_value=1, step=1, value=1)
        with col3:
            ec_purchase_price = st.number_input("구매단가", min_value=0.0, step=0.1)
            ec_selling_price = st.number_input("판매단가", min_value=0.0, step=0.1)
            ec_remarks = st.text_input("비고")
            
        if st.form_submit_button("🛒 E-commerce 내역 등록", type="primary"):
            if ec_code and ec_name:
                total_amt = ec_qty * ec_selling_price
                conn = get_db_connection()
                conn.execute('''INSERT INTO ecommerce_transactions 
                    (trans_date, platform, trans_type, item_code, item_name, qty, purchase_price, selling_price, total_amount, remarks, manager)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (ec_date.strftime("%Y-%m-%d"), ec_platform, ec_type, ec_code, ec_name, ec_qty, ec_purchase_price, ec_selling_price, total_amt, ec_remarks, st.session_state['user_name']))
                conn.commit(); conn.close(); push_db_to_github()
                st.success(f"[{ec_platform}] {ec_type} 내역이 정상 등록되었습니다!")
                st.rerun()
            else:
                st.error("상품코드와 품목명은 필수 입력 항목입니다.")

    st.markdown("---")
    
    # 2. E-commerce 현황 Sheet (표)
    st.markdown("### 📋 E-commerce Loading & Unloading 현황 Sheet")
    
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        filter_platform = st.selectbox("🎯 플랫폼 필터 선택", options=["전체 (All)"] + ECOM_PLATFORMS)
    
    conn = get_db_connection()
    if filter_platform == "전체 (All)":
        df_ec = pd.read_sql_query("""
            SELECT id as ID, trans_date as 일자, platform as 플랫폼, trans_type as 구분, 
                   item_code as 코드, item_name as 품목, qty as 수량, 
                   purchase_price as 구매단가, selling_price as 판매단가, total_amount as 총판매액, 
                   remarks as 비고, manager as 담당자 
            FROM ecommerce_transactions ORDER BY trans_date DESC, id DESC
        """, conn)
    else:
        df_ec = pd.read_sql_query("""
            SELECT id as ID, trans_date as 일자, platform as 플랫폼, trans_type as 구분, 
                   item_code as 코드, item_name as 품목, qty as 수량, 
                   purchase_price as 구매단가, selling_price as 판매단가, total_amount as 총판매액, 
                   remarks as 비고, manager as 담당자 
            FROM ecommerce_transactions WHERE platform=? ORDER BY trans_date DESC, id DESC
        """, conn, params=(filter_platform,))
    conn.close()

    if not df_ec.empty:
        st.dataframe(df_ec, use_container_width=True, hide_index=True)
        
        # 삭제 기능
        with st.expander("⚙️ E-commerce 등록 내역 삭제"):
            opt_ec = ["선택 안함"] + [f"ID: {r['ID']} - [{r['플랫폼']}] {r['구분']} / {r['품목']} ({r['수량']}개)" for i, r in df_ec.iterrows()]
            sel_ec = st.selectbox("삭제할 대상을 선택하세요", options=opt_ec)
            if sel_ec != "선택 안함":
                t_id = int(sel_ec.split("ID: ")[1].split(" -")[0])
                if st.button("🚨 해당 내역 삭제"):
                    conn = get_db_connection()
                    conn.execute("DELETE FROM ecommerce_transactions WHERE id=?", (t_id,))
                    conn.commit(); conn.close(); push_db_to_github()
                    st.success("삭제 완료!"); st.rerun()
    else:
        st.info("등록된 E-commerce 내역이 없습니다.")

# ==========================================
# 탭 장부: 입출금 장부
# ==========================================
with tab_cb:
    st.subheader("💰 통합 입출금 장부")
    with st.form("manual_cb_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1: cb_date = st.date_input("일자"); cb_type = st.selectbox("구분", ["입금", "출금"])
        with col2: cb_desc = st.text_input("적요"); cb_amount = st.number_input("금액", min_value=0.0, step=1.0)
        with col3: cb_pay = st.selectbox("결제 수단", options=PAYMENT_METHODS); cb_remarks = st.text_input("비고")
        if st.form_submit_button("📝 수동 내역 등록", type="primary") and cb_desc and cb_amount > 0:
            conn = get_db_connection()
            conn.execute("INSERT INTO manual_cashbook (trans_date, type, description, amount, payment_method, remarks, manager) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (cb_date.strftime("%Y-%m-%d"), cb_type, cb_desc, cb_amount, cb_pay, cb_remarks, st.session_state['user_name']))
            conn.commit(); conn.close(); push_db_to_github(); st.success("장부 등록 완료!"); st.rerun()

    conn = get_db_connection()
    df_auto = pd.read_sql_query("SELECT trans_date as date, CASE WHEN trans_type='입고' THEN '출금' ELSE '입금' END as type, item_code, item_name as description, total_amount as amount, payment_method, remarks, '자동' as source, id as ref_id FROM transactions", conn)
    df_manual = pd.read_sql_query("SELECT trans_date as date, type, '' as item_code, description, amount, payment_method, remarks, '수동' as source, id as ref_id FROM manual_cashbook", conn)
    conn.close()
    df_cb = pd.concat([df_auto, df_manual], ignore_index=True)
    if not df_cb.empty:
        df_cb.sort_values(by=['date', 'ref_id'], inplace=True)
        df_cb['입금액'] = df_cb.apply(lambda x: x['amount'] if x['type'] == '입금' else 0, axis=1)
        df_cb['출금액'] = df_cb.apply(lambda x: x['amount'] if x['type'] == '출금' else 0, axis=1)
        df_cb['잔액'] = (df_cb['입금액'] - df_cb['출금액']).cumsum()
        df_display = df_cb[['date', 'type', 'item_code', 'description', 'payment_method', '입금액', '출금액', '잔액', 'remarks', 'source']].copy()
        df_display.columns = ['일자', '구분', '상품코드', '적요 (내용)', '결제수단', '입금', '출금', '잔액', '비고', '등록방식']
        st.dataframe(df_display, use_container_width=True, hide_index=True)

# ==========================================
# 탭 4: 엑셀 데이터 관리
# ==========================================
with tab4:
    st.subheader("📊 엑셀 데이터 관리 센터")
    col_d1, col_d2 = st.columns(2)
    with col_d1: start_date = st.date_input("조회 시작일", value=datetime.today().replace(day=1))
    with col_d2: end_date = st.date_input("조회 종료일", value=datetime.today())
        
    conn = get_db_connection()
    df_period = pd.read_sql_query("SELECT id as ID, trans_date as 일자, trans_type as 구분, partner_name as 거래처, item_code as 상품코드, item_name as 상품명, qty as 수량, price as 단가, total_amount as 총금액, payment_method as 결제수단, remarks as 비고, manager as 담당자 FROM transactions WHERE trans_date >= ? AND trans_date <= ? ORDER BY trans_date DESC, id DESC", conn, params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    conn.close()
    st.dataframe(df_period, use_container_width=True, hide_index=True)
    if not df_period.empty:
        buffer_period = io.BytesIO()
        with pd.ExcelWriter(buffer_period, engine='openpyxl') as writer: df_period.to_excel(writer, index=False, sheet_name='입출고내역')
        st.download_button("📥 내역 엑셀 다운로드 (.xlsx)", data=buffer_period.getvalue(), file_name=f"transactions_{start_date}_{end_date}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
