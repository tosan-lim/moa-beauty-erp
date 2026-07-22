import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import base64
import requests
import hashlib
import io  # 엑셀 파일 생성을 위한 라이브러리 추가

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
# 🛠️ 데이터베이스 설정
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
    
    c.execute("PRAGMA table_info(transactions)")
    columns = [info[1] for info in c.fetchall()]
    if 'item_code' not in columns: c.execute("ALTER TABLE transactions ADD COLUMN item_code TEXT")
    if 'image_base64' not in columns: c.execute("ALTER TABLE transactions ADD COLUMN image_base64 TEXT")
    
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
                        conn.commit(); conn.close(); push_db_to_github()
                        st.success("비밀번호 변경 완료!")
                    else: st.error("현재 비밀번호 불일치")
                else: st.error("새 비밀번호 불일치")
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.update({'logged_in': False, 'username': '', 'user_role': '', 'user_name': ''})
        st.rerun()

st.title('KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP')
st.markdown("---")

if st.session_state['user_role'] == 'Admin':
    tab1, tab_user, tab2, tab3, tab_inv, tab4 = st.tabs(['📋 기초등록', '👥 직원관리', '📦 구매/입고', '🏷️ 판매/출고', '🏢 재고현황', '📊 엑셀 데이터 관리'])
else:
    tab1, tab2, tab3, tab_inv, tab4 = st.tabs(['📋 기초등록', '📦 구매/입고', '🏷️ 판매/출고', '🏢 재고현황', '📊 엑셀 데이터 관리'])
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

# ==========================================
# 탭 1 ~ 3, 재고현황 (이전 코드와 100% 동일하므로 일부 축약 표기하지만 기능은 모두 유지됨)
# ==========================================
with tab1:
    st.subheader("거래처 상세 등록")
    with st.form("partner_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            p_code = st.text_input("거래처코드")
            p_phone = st.text_input("전화번호")
        with col2:
            p_name = st.text_input("상호명")
            p_email = st.text_input("이메일")
        with col3:
            p_type = st.selectbox("구분", ["매출처/Buyer", "매입처/Seller"])
            p_category = st.text_input("카테고리")
        if st.form_submit_button("저장", type="primary") and p_code and p_name:
            conn = get_db_connection()
            conn.execute("INSERT OR REPLACE INTO partners (partner_code, partner_name, type, phone, email, category, registration_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (p_code, p_name, p_type, p_phone, p_email, p_category, datetime.now().strftime("%Y-%m-%d")))
            conn.commit(); conn.close(); push_db_to_github(); st.success("저장 완료!"); st.rerun()
    st.dataframe(df_partners, use_container_width=True, hide_index=True)

if tab_user:
    with tab_user:
        st.subheader("👥 직원 관리 (등록 / 수정 / 삭제)")
        col_u1, col_u2 = st.columns([1, 1.5])
        with col_u1:
            with st.form("new_user_form", clear_on_submit=True):
                new_username = st.text_input("아이디 (Username)")
                new_password = st.text_input("초기 비밀번호 부여", type="password")
                new_name = st.text_input("이름")
                new_role = st.selectbox("권한", ["Staff", "Manager", "Admin"])
                if st.form_submit_button("계정 생성", type="primary") and new_username and new_password:
                    try:
                        conn = get_db_connection()
                        conn.execute("INSERT INTO users (username, password, name, role, created_at) VALUES (?, ?, ?, ?, ?)", 
                                     (new_username, make_hashes(new_password), new_name, new_role, datetime.now().strftime("%Y-%m-%d")))
                        conn.commit(); conn.close(); push_db_to_github(); st.success("생성 완료!"); st.rerun()
                    except: st.error("중복된 아이디")
            st.markdown("---")
            conn = get_db_connection()
            user_list = [row['username'] for row in conn.cursor().execute("SELECT username FROM users").fetchall()]
            conn.close()
            target_user = st.selectbox("수정/삭제할 아이디", options=user_list)
            if target_user:
                with st.form("edit_user_form"):
                    edit_role = st.selectbox("새 권한", ["Staff", "Manager", "Admin"])
                    edit_password = st.text_input("새 비밀번호 (유지시 빈칸)", type="password")
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
            conn = get_db_connection()
            df_users = pd.read_sql_query("SELECT username as 아이디, name as 이름, role as 권한, created_at as 등록일 FROM users", conn)
            conn.close(); st.dataframe(df_users, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📦 상품 입고 등록")
    with st.form("purchase_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("입고 일자")
            partner_name = st.selectbox("매입처 (Seller)", options=sellers)
            item_code = st.text_input("상품코드")
        with col2:
            item_name = st.text_input("상품명")
            qty = st.number_input("수량", min_value=1, step=1)
            image_file = st.file_uploader("이미지 첨부", type=['jpg', 'jpeg', 'png'])
        with col3:
            price = st.number_input("단가", min_value=0.0, step=0.1)
            total_amount = qty * price
        if st.form_submit_button("입고 등록", type="primary") and item_name and item_code and partner_name != "매입처 없음":
            img_b64 = base64.b64encode(image_file.read()).decode('utf-8') if image_file else ""
            conn = get_db_connection()
            conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager, image_base64) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (trans_date, "입고", partner_name, item_code, item_name, qty, price, total_amount, st.session_state['user_name'], img_b64))
            conn.commit(); conn.close(); push_db_to_github(); st.success("등록 완료!"); st.rerun()
            
    conn = get_db_connection()
    df_in_raw = pd.read_sql_query("SELECT id, trans_date, partner_name, item_code, item_name, qty, price, total_amount, manager, image_base64 FROM transactions WHERE trans_type='입고' ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    if not df_in_raw.empty:
        df_in = df_in_raw.copy()
        df_in['사진'] = df_in['image_base64'].apply(lambda x: f"data:image/png;base64,{x}" if pd.notnull(x) and x != "" else None)
        df_in_display = df_in.rename(columns={'id':'ID', 'trans_date':'일자', 'partner_name':'매입처', 'item_code':'코드', 'item_name':'상품명', 'qty':'수량', 'price':'단가', 'total_amount':'총액', 'manager':'담당자'}).drop(columns=['image_base64'])
        st.dataframe(df_in_display, column_config={"사진": st.column_config.ImageColumn("사진")}, use_container_width=True, hide_index=True)
        with st.expander("⚙️ 내역 수정 및 삭제"):
            sel_in = st.selectbox("수정/삭제 대상", options=["선택 안함"] + [f"ID: {r['id']} - {r['item_name']} ({r['qty']}개)" for i, r in df_in_raw.iterrows()])
            if sel_in != "선택 안함":
                t_id = int(sel_in.split("ID: ")[1].split(" -")[0])
                if st.button("🚨 해당 내역 삭제"):
                    conn = get_db_connection(); conn.execute("DELETE FROM transactions WHERE id=?", (t_id,)); conn.commit(); conn.close(); push_db_to_github(); st.rerun()

with tab3:
    st.subheader("🏷️ 상품 출고 등록")
    with st.form("sales_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("출고 일자")
            partner_name = st.selectbox("매출처 (Buyer)", options=buyers)
        with col2:
            item_code = st.text_input("상품코드")
            item_name = st.text_input("상품명")
        with col3:
            qty = st.number_input("출고 수량", min_value=1, step=1)
            price = st.number_input("판매 단가", min_value=0.0, step=0.1)
        if st.form_submit_button("출고 등록", type="primary") and item_name and item_code and partner_name != "매출처 없음":
            conn = get_db_connection()
            conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (trans_date, "출고", partner_name, item_code, item_name, qty, price, qty*price, st.session_state['user_name']))
            conn.commit(); conn.close(); push_db_to_github(); st.success("등록 완료!"); st.rerun()

    conn = get_db_connection()
    df_out_raw = pd.read_sql_query("SELECT id, trans_date, partner_name, item_code, item_name, qty, price, total_amount, manager FROM transactions WHERE trans_type='출고' ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    if not df_out_raw.empty:
        df_out_display = df_out_raw.rename(columns={'id':'ID', 'trans_date':'일자', 'partner_name':'매출처', 'item_code':'코드', 'item_name':'상품명', 'qty':'수량', 'price':'단가', 'total_amount':'총액', 'manager':'담당자'})
        st.dataframe(df_out_display, use_container_width=True, hide_index=True)
        with st.expander("⚙️ 내역 수정 및 삭제"):
            sel_out = st.selectbox("수정/삭제 대상", options=["선택 안함"] + [f"ID: {r['id']} - {r['item_name']} ({r['qty']}개)" for i, r in df_out_raw.iterrows()])
            if sel_out != "선택 안함":
                t_id = int(sel_out.split("ID: ")[1].split(" -")[0])
                if st.button("🚨 해당 내역 삭제 "):
                    conn = get_db_connection(); conn.execute("DELETE FROM transactions WHERE id=?", (t_id,)); conn.commit(); conn.close(); push_db_to_github(); st.rerun()

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
        st.markdown(f"**총 재고 수량:** `{df_inv['현재재고'].sum():,.0f}` 개  |  **총 금액 가치:** `{df_inv['총금액'].sum():,.2f}`")

# ==========================================
# 🔥 탭 4: 엑셀(.xlsx) 데이터 관리 (신규 업데이트)
# ==========================================
with tab4:
    st.subheader("📊 엑셀 데이터 관리 센터 (Excel 전용)")
    
    # 1. 기간별 다운로드 기능 (Excel)
    st.markdown("### 1️⃣ 기간별 입출고 내역 다운로드 (.xlsx)")
    col_d1, col_d2 = st.columns(2)
    with col_d1: start_date = st.date_input("조회 시작일", value=datetime.today().replace(day=1))
    with col_d2: end_date = st.date_input("조회 종료일", value=datetime.today())
        
    conn = get_db_connection()
    df_period = pd.read_sql_query("SELECT id as ID, trans_date as 일자, trans_type as 구분, partner_name as 거래처, item_code as 상품코드, item_name as 상품명, qty as 수량, price as 단가, total_amount as 총금액, manager as 담당자 FROM transactions WHERE trans_date >= ? AND trans_date <= ? ORDER BY trans_date DESC, id DESC", conn, params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    conn.close()
    
    st.dataframe(df_period, use_container_width=True, hide_index=True)
    
    if not df_period.empty:
        buffer_period = io.BytesIO()
        with pd.ExcelWriter(buffer_period, engine='openpyxl') as writer:
            df_period.to_excel(writer, index=False, sheet_name='입출고내역')
        st.download_button("📥 선택 기간 내역 엑셀 다운로드 (.xlsx)", data=buffer_period.getvalue(), file_name=f"transactions_{start_date}_{end_date}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    st.markdown("---")
    
    # 2. 엑셀 데이터 일괄 업로드 기능 (Excel)
    st.markdown("### 2️⃣ 데이터 일괄 등록 (Excel 업로드)")
    st.info("💡 **이용 방법**: 양식을 다운로드하여 엑셀에서 데이터를 작성한 후, 그대로 엑셀 파일(.xlsx)을 업로드하세요.")
    
    col_u1, col_u2 = st.columns(2)
    
    # 2-1. 거래처 엑셀 업로드
    with col_u1:
        with st.expander("📂 거래처 일괄 등록 (Excel)"):
            template_p = pd.DataFrame(columns=['partner_code', 'partner_name', 'type', 'phone', 'email', 'state', 'address', 'contact_person', 'category'])
            buffer_p = io.BytesIO()
            with pd.ExcelWriter(buffer_p, engine='openpyxl') as writer:
                template_p.to_excel(writer, index=False, sheet_name='거래처양식')
            st.download_button("📝 거래처 엑셀 양식 다운로드", data=buffer_p.getvalue(), file_name="partner_template.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            file_p = st.file_uploader("거래처 엑셀 파일 첨부", type=['xlsx', 'xls'], key='file_p')
            if file_p and st.button("거래처 엑셀 일괄 저장"):
                try:
                    df_p = pd.read_excel(file_p).fillna('')
                    conn = get_db_connection()
                    for _, row in df_p.iterrows():
                        p_code = str(row.get('partner_code', '')).strip()
                        p_name = str(row.get('partner_name', '')).strip()
                        if p_code and p_name:
                            conn.execute('''INSERT OR REPLACE INTO partners (partner_code, partner_name, type, phone, email, state, address, contact_person, category, registration_date) 
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                         (p_code, p_name, str(row.get('type','매출처/Buyer')), str(row.get('phone','')), str(row.get('email','')), str(row.get('state','')), str(row.get('address','')), str(row.get('contact_person','')), str(row.get('category','')), datetime.now().strftime("%Y-%m-%d")))
                    conn.commit(); conn.close(); push_db_to_github()
                    st.success("거래처 엑셀 일괄 등록 완료!"); st.rerun()
                except Exception as e: st.error(f"엑셀 오류: {e}")

    # 2-2. 입출고 엑셀 업로드
    with col_u2:
        with st.expander("📂 입출고 내역 일괄 등록 (Excel)"):
            template_t = pd.DataFrame(columns=['trans_date', 'trans_type', 'partner_name', 'item_code', 'item_name', 'qty', 'price'])
            buffer_t = io.BytesIO()
            with pd.ExcelWriter(buffer_t, engine='openpyxl') as writer:
                template_t.to_excel(writer, index=False, sheet_name='입출고양식')
            st.download_button("📝 입출고 엑셀 양식 다운로드", data=buffer_t.getvalue(), file_name="transaction_template.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            file_t = st.file_uploader("입출고 엑셀 파일 첨부", type=['xlsx', 'xls'], key='file_t')
            if file_t and st.button("입출고 엑셀 일괄 저장"):
                try:
                    df_t = pd.read_excel(file_t).fillna('')
                    conn = get_db_connection()
                    for _, row in df_t.iterrows():
                        t_date = str(row.get('trans_date', '')).strip() or datetime.now().strftime("%Y-%m-%d")
                        t_type = str(row.get('trans_type', '입고')).strip()
                        p_name = str(row.get('partner_name', '')).strip()
                        i_code = str(row.get('item_code', '')).strip()
                        i_name = str(row.get('item_name', '')).strip()
                        try: qty = int(float(row.get('qty', 0)) if str(row.get('qty', '')) != '' else 0)
                        except: qty = 0
                        try: price = float(row.get('price', 0)) if str(row.get('price', '')) != '' else 0.0
                        except: price = 0.0
                        
                        if i_code and i_name:
                            conn.execute('''INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager) 
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                         (t_date, t_type, p_name, i_code, i_name, qty, price, qty*price, st.session_state['user_name']))
                    conn.commit(); conn.close(); push_db_to_github()
                    st.success("입출고 엑셀 일괄 등록 완료!"); st.rerun()
                except Exception as e: st.error(f"엑셀 오류: {e}")
