import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import base64
import requests
import hashlib

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
# 🛠️ 데이터베이스 자동 업그레이드 및 암호화
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
    
    # DB 자동 업그레이드
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
                        st.success("비밀번호가 성공적으로 변경되었습니다!")
                    else: st.error("현재 비밀번호가 일치하지 않습니다.")
                else: st.error("새 비밀번호가 일치하지 않거나 비어있습니다.")
    
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.update({'logged_in': False, 'username': '', 'user_role': '', 'user_name': ''})
        st.rerun()

st.title('KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP')
st.markdown("---")

if st.session_state['user_role'] == 'Admin':
    tab1, tab_user, tab2, tab3, tab_inv, tab4 = st.tabs(['📋 기초등록', '👥 직원관리', '📦 구매/입고', '🏷️ 판매/출고', '🏢 재고현황', '📊 보고서'])
else:
    tab1, tab2, tab3, tab_inv, tab4 = st.tabs(['📋 기초등록', '📦 구매/입고', '🏷️ 판매/출고', '🏢 재고현황', '📊 보고서'])
    tab_user = None

# 거래처 데이터 로드
conn = get_db_connection()
df_partners = pd.read_sql_query("SELECT * FROM partners", conn)
conn.close()
type_col = 'type' if 'type' in df_partners.columns else ('partner_type' if 'partner_type' in df_partners.columns else None)
if not df_partners.empty and type_col and 'partner_name' in df_partners.columns:
    sellers = df_partners[df_partners[type_col].astype(str).str.contains('매입|Seller', na=False)]['partner_name'].tolist()
    buyers = df_partners[df_partners[type_col].astype(str).str.contains('매출|Buyer', na=False)]['partner_name'].tolist()
else:
    sellers, buyers = [], []
if not sellers: sellers = ["매입처 없음"]
if not buyers: buyers = ["매출처 없음"]

# ==========================================
# 탭 1: 기초 등록
# ==========================================
with tab1:
    st.subheader("거래처 상세 등록")
    if st.session_state['user_role'] == 'Staff': st.warning("⚠️ Staff는 조회만 가능합니다.")
    else:
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
            if st.form_submit_button("저장", type="primary"):
                if p_code and p_name:
                    conn = get_db_connection()
                    conn.execute("INSERT OR REPLACE INTO partners (partner_code, partner_name, type, phone, email, category, registration_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (p_code, p_name, p_type, p_phone, p_email, p_category, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit(); conn.close(); push_db_to_github()
                    st.success("저장 완료!"); st.rerun()
                else: st.error("코드와 상호명은 필수입니다.")
    st.dataframe(df_partners, use_container_width=True, hide_index=True)

# ==========================================
# 탭 Admin: 직원 관리
# ==========================================
if tab_user:
    with tab_user:
        st.subheader("👥 직원 관리 (등록 / 수정 / 삭제)")
        col_u1, col_u2 = st.columns([1, 1.5])
        with col_u1:
            st.markdown("##### ➕ 새 직원 등록")
            with st.form("new_user_form", clear_on_submit=True):
                new_username = st.text_input("아이디 (Username)")
                new_password = st.text_input("초기 비밀번호 부여", type="password")
                new_name = st.text_input("이름")
                new_role = st.selectbox("권한", ["Staff", "Manager", "Admin"])
                if st.form_submit_button("계정 생성", type="primary"):
                    if new_username and new_password and new_name:
                        try:
                            conn = get_db_connection()
                            conn.execute("INSERT INTO users (username, password, name, role, created_at) VALUES (?, ?, ?, ?, ?)", 
                                         (new_username, make_hashes(new_password), new_name, new_role, datetime.now().strftime("%Y-%m-%d")))
                            conn.commit(); conn.close(); push_db_to_github()
                            st.success(f"{new_name} 생성 완료!"); st.rerun()
                        except sqlite3.IntegrityError: st.error("이미 존재하는 아이디입니다.")
                    else: st.error("필수 항목을 입력하세요.")
            st.markdown("---")
            st.markdown("##### ⚙️ 직원 권한 수정 및 삭제")
            conn = get_db_connection()
            user_list = [row['username'] for row in conn.cursor().execute("SELECT username FROM users").fetchall()]
            conn.close()
            target_user = st.selectbox("수정/삭제할 아이디 선택", options=user_list)
            if target_user:
                with st.form("edit_user_form"):
                    edit_role = st.selectbox("새로운 권한", ["Staff", "Manager", "Admin"])
                    edit_password = st.text_input("새 비밀번호 (유지하려면 비워두세요)", type="password")
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.form_submit_button("정보 수정", type="primary"):
                            conn = get_db_connection()
                            if edit_password: conn.execute("UPDATE users SET password=?, role=? WHERE username=?", (make_hashes(edit_password), edit_role, target_user))
                            else: conn.execute("UPDATE users SET role=? WHERE username=?", (edit_role, target_user))
                            conn.commit(); conn.close(); push_db_to_github()
                            st.success("수정 완료!"); st.rerun()
                    with col_b2:
                        if target_user != 'admin':
                            if st.form_submit_button("🚨 계정 삭제"):
                                conn = get_db_connection()
                                conn.execute("DELETE FROM users WHERE username=?", (target_user,))
                                conn.commit(); conn.close(); push_db_to_github()
                                st.success("삭제 완료!"); st.rerun()
                        else: st.warning("admin은 삭제 불가")
        with col_u2:
            st.markdown("##### 📋 현재 직원 목록")
            conn = get_db_connection()
            df_users = pd.read_sql_query("SELECT username as 아이디, name as 이름, role as 권한, created_at as 등록일 FROM users", conn)
            conn.close()
            st.dataframe(df_users, use_container_width=True, hide_index=True)

# ==========================================
# 탭 2: 구매/입고 (등록 + 리스트 + 수정/삭제 기능)
# ==========================================
with tab2:
    st.subheader("📦 상품 입고 등록")
    with st.form("purchase_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("입고 일자")
            partner_name = st.selectbox("매입처 (Seller)", options=sellers)
            item_code = st.text_input("상품코드 (Item Code)")
        with col2:
            item_name = st.text_input("상품명 (Item Name)")
            qty = st.number_input("입고 수량", min_value=1, step=1)
            image_file = st.file_uploader("상품 이미지 업로드 (선택)", type=['jpg', 'jpeg', 'png'])
        with col3:
            price = st.number_input("단가", min_value=0.0, step=0.1)
            total_amount = qty * price
            
        if st.form_submit_button("입고 등록", type="primary"):
            if item_name and item_code and partner_name != "매입처 없음":
                img_b64 = ""
                if image_file: img_b64 = base64.b64encode(image_file.read()).decode('utf-8')
                conn = get_db_connection()
                conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager, image_base64) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (trans_date, "입고", partner_name, item_code, item_name, qty, price, total_amount, st.session_state['user_name'], img_b64))
                conn.commit(); conn.close(); push_db_to_github()
                st.success("입고 처리가 완료되었습니다!"); st.rerun()
            else: st.error("상품코드, 상품명, 매입처는 필수입니다.")
            
    st.markdown("#### 📋 최근 입고 내역")
    conn = get_db_connection()
    df_in_raw = pd.read_sql_query("SELECT id, trans_date, partner_name, item_code, item_name, qty, price, total_amount, manager, image_base64 FROM transactions WHERE trans_type='입고' ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    
    if not df_in_raw.empty:
        df_in = df_in_raw.copy()
        df_in['사진'] = df_in['image_base64'].apply(lambda x: f"data:image/png;base64,{x}" if pd.notnull(x) and x != "" else None)
        df_in_display = df_in.rename(columns={'id':'ID', 'trans_date':'일자', 'partner_name':'매입처', 'item_code':'상품코드', 'item_name':'상품명', 'qty':'수량', 'price':'단가', 'total_amount':'총액', 'manager':'담당자'}).drop(columns=['image_base64'])
        st.dataframe(df_in_display, column_config={"사진": st.column_config.ImageColumn("사진")}, use_container_width=True, hide_index=True)
        
        # 🔥 [신규] 입고 내역 수정 및 삭제
        st.markdown("---")
        with st.expander("⚙️ 등록된 입고 내역 수정 및 삭제"):
            opt_in = ["선택 안함"] + [f"ID: {row['id']} - {row['trans_date']} / {row['item_name']} / {row['qty']}개" for idx, row in df_in_raw.iterrows()]
            sel_in = st.selectbox("수정/삭제할 대상을 선택하세요", options=opt_in, key="sel_in")
            
            if sel_in != "선택 안함":
                t_id = int(sel_in.split("ID: ")[1].split(" -")[0])
                t_row = df_in_raw[df_in_raw['id'] == t_id].iloc[0]
                
                with st.form("edit_in_form"):
                    e_c1, e_c2, e_c3 = st.columns(3)
                    with e_c1:
                        try: default_date = datetime.strptime(t_row['trans_date'], "%Y-%m-%d").date()
                        except: default_date = datetime.now().date()
                        e_date = st.date_input("입고 일자 (수정)", value=default_date)
                        s_idx = sellers.index(t_row['partner_name']) if t_row['partner_name'] in sellers else 0
                        e_partner = st.selectbox("매입처 (수정)", options=sellers, index=s_idx)
                    with e_c2:
                        e_code = st.text_input("상품코드 (수정)", value=t_row['item_code'])
                        e_name = st.text_input("상품명 (수정)", value=t_row['item_name'])
                    with e_c3:
                        e_qty = st.number_input("수량 (수정)", min_value=1, step=1, value=int(t_row['qty']))
                        e_price = st.number_input("단가 (수정)", min_value=0.0, step=0.1, value=float(t_row['price']))
                        
                    e_b1, e_b2 = st.columns(2)
                    with e_b1:
                        if st.form_submit_button("내역 수정 (Update)", type="primary"):
                            e_total = e_qty * e_price
                            conn = get_db_connection()
                            conn.execute("UPDATE transactions SET trans_date=?, partner_name=?, item_code=?, item_name=?, qty=?, price=?, total_amount=? WHERE id=?", 
                                         (e_date.strftime("%Y-%m-%d"), e_partner, e_code, e_name, e_qty, e_price, e_total, t_id))
                            conn.commit(); conn.close(); push_db_to_github()
                            st.success("성공적으로 수정되었습니다!"); st.rerun()
                    with e_b2:
                        if st.form_submit_button("🚨 내역 삭제 (Delete)"):
                            conn = get_db_connection()
                            conn.execute("DELETE FROM transactions WHERE id=?", (t_id,))
                            conn.commit(); conn.close(); push_db_to_github()
                            st.success("삭제 완료!"); st.rerun()

# ==========================================
# 탭 3: 판매/출고 (등록 + 리스트 + 수정/삭제 기능)
# ==========================================
with tab3:
    st.subheader("🏷️ 상품 출고 등록")
    with st.form("sales_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("출고 일자")
            partner_name = st.selectbox("매출처 (Buyer)", options=buyers)
        with col2:
            item_code = st.text_input("상품코드 (Item Code)")
            item_name = st.text_input("상품명 (Item Name)")
        with col3:
            qty = st.number_input("출고 수량", min_value=1, step=1)
            price = st.number_input("판매 단가", min_value=0.0, step=0.1)
            total_amount = qty * price
            
        if st.form_submit_button("출고 등록", type="primary"):
            if item_name and item_code and partner_name != "매출처 없음":
                conn = get_db_connection()
                conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (trans_date, "출고", partner_name, item_code, item_name, qty, price, total_amount, st.session_state['user_name']))
                conn.commit(); conn.close(); push_db_to_github()
                st.success("출고 처리가 완료되었습니다!"); st.rerun()
            else: st.error("상품코드, 상품명, 매출처는 필수입니다.")

    st.markdown("#### 📋 최근 출고 내역")
    conn = get_db_connection()
    df_out_raw = pd.read_sql_query("SELECT id, trans_date, partner_name, item_code, item_name, qty, price, total_amount, manager FROM transactions WHERE trans_type='출고' ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    
    if not df_out_raw.empty:
        df_out_display = df_out_raw.rename(columns={'id':'ID', 'trans_date':'일자', 'partner_name':'매출처', 'item_code':'상품코드', 'item_name':'상품명', 'qty':'수량', 'price':'단가', 'total_amount':'총액', 'manager':'담당자'})
        st.dataframe(df_out_display, use_container_width=True, hide_index=True)
        
        # 🔥 [신규] 출고 내역 수정 및 삭제
        st.markdown("---")
        with st.expander("⚙️ 등록된 출고 내역 수정 및 삭제"):
            opt_out = ["선택 안함"] + [f"ID: {row['id']} - {row['trans_date']} / {row['item_name']} / {row['qty']}개" for idx, row in df_out_raw.iterrows()]
            sel_out = st.selectbox("수정/삭제할 대상을 선택하세요", options=opt_out, key="sel_out")
            
            if sel_out != "선택 안함":
                t_id = int(sel_out.split("ID: ")[1].split(" -")[0])
                t_row = df_out_raw[df_out_raw['id'] == t_id].iloc[0]
                
                with st.form("edit_out_form"):
                    e_c1, e_c2, e_c3 = st.columns(3)
                    with e_c1:
                        try: default_date = datetime.strptime(t_row['trans_date'], "%Y-%m-%d").date()
                        except: default_date = datetime.now().date()
                        e_date = st.date_input("출고 일자 (수정)", value=default_date)
                        b_idx = buyers.index(t_row['partner_name']) if t_row['partner_name'] in buyers else 0
                        e_partner = st.selectbox("매출처 (수정)", options=buyers, index=b_idx)
                    with e_c2:
                        e_code = st.text_input("상품코드 (수정)", value=t_row['item_code'])
                        e_name = st.text_input("상품명 (수정)", value=t_row['item_name'])
                    with e_c3:
                        e_qty = st.number_input("수량 (수정)", min_value=1, step=1, value=int(t_row['qty']))
                        e_price = st.number_input("단가 (수정)", min_value=0.0, step=0.1, value=float(t_row['price']))
                        
                    e_b1, e_b2 = st.columns(2)
                    with e_b1:
                        if st.form_submit_button("내역 수정 (Update)", type="primary"):
                            e_total = e_qty * e_price
                            conn = get_db_connection()
                            conn.execute("UPDATE transactions SET trans_date=?, partner_name=?, item_code=?, item_name=?, qty=?, price=?, total_amount=? WHERE id=?", 
                                         (e_date.strftime("%Y-%m-%d"), e_partner, e_code, e_name, e_qty, e_price, e_total, t_id))
                            conn.commit(); conn.close(); push_db_to_github()
                            st.success("성공적으로 수정되었습니다!"); st.rerun()
                    with e_b2:
                        if st.form_submit_button("🚨 내역 삭제 (Delete)"):
                            conn = get_db_connection()
                            conn.execute("DELETE FROM transactions WHERE id=?", (t_id,))
                            conn.commit(); conn.close(); push_db_to_github()
                            st.success("삭제 완료!"); st.rerun()

# ==========================================
# 탭 재고: 🏢 실시간 재고 현황
# ==========================================
with tab_inv:
    st.subheader("🏢 실시간 상품 재고 및 금액 현황")
    st.info("입고된 수량에서 출고된 수량을 자동으로 빼서 현재 남은 재고와 총 가치를 계산합니다.")
    
    conn = get_db_connection()
    query = """
    SELECT 
        item_code,
        item_name,
        SUM(CASE WHEN trans_type = '입고' THEN qty ELSE 0 END) AS in_qty,
        SUM(CASE WHEN trans_type = '출고' THEN qty ELSE 0 END) AS out_qty,
        AVG(CASE WHEN trans_type = '입고' THEN price ELSE NULL END) AS avg_price
    FROM transactions
    WHERE item_code IS NOT NULL AND item_code != ''
    GROUP BY item_code, item_name
    """
    df_inv = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df_inv.empty:
        df_inv['현재재고(Qty)'] = df_inv['in_qty'] - df_inv['out_qty']
        df_inv['평균매입단가'] = df_inv['avg_price'].fillna(0).round(2)
        df_inv['재고총금액(Amount)'] = (df_inv['현재재고(Qty)'] * df_inv['평균매입단가']).round(2)
        
        df_result = df_inv[['item_code', 'item_name', '현재재고(Qty)', '평균매입단가', '재고총금액(Amount)']].rename(
            columns={'item_code':'상품코드', 'item_name':'상품명'}
        )
        st.dataframe(df_result, use_container_width=True, hide_index=True)
        
        total_stock = df_result['현재재고(Qty)'].sum()
        total_value = df_result['재고총금액(Amount)'].sum()
        st.markdown(f"**총 보유 재고 수량:** `{total_stock:,.0f}` 개  |  **총 재고 금액 가치:** `{total_value:,.2f}`")
    else:
        st.warning("아직 등록된 입출고 내역(재고)이 없습니다.")

# ==========================================
# 탭 4: 엑셀 보고서
# ==========================================
with tab4:
    st.subheader("📊 데이터 다운로드")
    conn = get_db_connection()
    df_all_trans = pd.read_sql_query("SELECT id, trans_date, trans_type, partner_name, item_code, item_name, qty, price, total_amount, manager FROM transactions ORDER BY id DESC", conn)
    conn.close()
    if not df_all_trans.empty:
        csv = df_all_trans.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📦 전체 입출고 내역 엑셀 다운로드 (CSV)", data=csv, file_name=f'transactions_{datetime.now().strftime("%Y%m%d")}.csv', mime='text/csv')
