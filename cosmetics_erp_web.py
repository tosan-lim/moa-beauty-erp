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
# 🛠️ 데이터베이스 및 암호화 설정
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
    # 1. 거래처 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS partners (
        partner_code TEXT PRIMARY KEY, partner_name TEXT NOT NULL, type TEXT,
        phone TEXT, email TEXT, state TEXT, address TEXT, contact_person TEXT, category TEXT, registration_date TEXT)''')
    
    # 2. 사용자 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL, email TEXT, created_at TEXT)''')
    
    # 3. 입출고 내역 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, trans_date TEXT, trans_type TEXT, 
        partner_name TEXT, item_name TEXT, qty INTEGER, price REAL, total_amount REAL, manager TEXT)''')
    
    # 기본 관리자 생성
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, name, role, email, created_at) VALUES (?, ?, ?, ?, ?, ?)", 
                  ('admin', make_hashes("admin123"), '대표/관리자', 'Admin', 'admin@kecindia.in', datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# 🌐 웹 앱 로그인 및 설정
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
                else: st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    st.stop()

# -------------------------------------------------------------------
# 🏢 ERP 메인 화면
# -------------------------------------------------------------------
with st.sidebar:
    st.markdown("### KIL INDIA TRADE")
    st.info(f"👤 **{st.session_state['user_name']}**\n\n🎖️ 권한: **{st.session_state['user_role']}**")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.update({'logged_in': False, 'username': '', 'user_role': '', 'user_name': ''})
        st.rerun()
    st.markdown("---")

st.title('KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP')
st.markdown("*인도 법인 화장품 재고 및 GST/관세 통합 관리 웹 시스템*")
st.markdown("---")

if st.session_state['user_role'] == 'Admin':
    tab1, tab_user, tab2, tab3, tab4 = st.tabs(['📋 기초등록', '👥 직원관리', '📦 구매/입고', '🏷️ 판매/출고', '📊 보고서'])
else:
    tab1, tab2, tab3, tab4 = st.tabs(['📋 기초등록', '📦 구매/입고', '🏷️ 판매/출고', '📊 보고서'])
    tab_user = None

# DB에서 거래처 불러오기
conn = get_db_connection()
df_partners = pd.read_sql_query("SELECT * FROM partners", conn)
conn.close()

type_col = 'type' if 'type' in df_partners.columns else ('partner_type' if 'partner_type' in df_partners.columns else None)
if not df_partners.empty and type_col and 'partner_name' in df_partners.columns:
    sellers = df_partners[df_partners[type_col].astype(str).str.contains('매입|Seller', na=False)]['partner_name'].tolist()
    buyers = df_partners[df_partners[type_col].astype(str).str.contains('매출|Buyer', na=False)]['partner_name'].tolist()
else:
    sellers, buyers = [], []

if not sellers: sellers = ["등록된 매입처 없음"]
if not buyers: buyers = ["등록된 매출처 없음"]

# ==========================================
# 탭 1: 기초 등록
# ==========================================
with tab1:
    st.subheader("거래처 상세 등록")
    if st.session_state['user_role'] == 'Staff': st.warning("⚠️ Staff 권한은 조회만 가능합니다.")
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
            if st.form_submit_button("거래처 저장", type="primary"):
                if p_code and p_name:
                    conn = get_db_connection()
                    conn.execute("INSERT OR REPLACE INTO partners (partner_code, partner_name, type, phone, email, category, registration_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (p_code, p_name, p_type, p_phone, p_email, p_category, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit(); conn.close(); push_db_to_github()
                    st.success("저장 성공!")
                    st.rerun()
                else: st.error("코드와 상호명은 필수입니다.")
    st.dataframe(df_partners, use_container_width=True, hide_index=True)

# ==========================================
# 탭 Admin: 직원/계정 관리 (신규 양식 추가!)
# ==========================================
if tab_user:
    with tab_user:
        st.subheader("👥 직원 계정 신규 등록 및 권한 관리")
        
        col_u1, col_u2 = st.columns([1, 1])
        
        # 왼쪽: 계정 생성 양식
        with col_u1:
            st.markdown("##### ➕ 새 직원 등록")
            with st.form("new_user_form", clear_on_submit=True):
                new_username = st.text_input("아이디 (Username)")
                new_password = st.text_input("비밀번호 (Password)", type="password")
                new_name = st.text_input("직원 이름 (Full Name)")
                new_role = st.selectbox("권한 부여 (Role)", ["Staff", "Manager", "Admin"])
                new_email = st.text_input("이메일 주소")
                
                user_submit = st.form_submit_button("직원 계정 생성", type="primary")
                
                if user_submit:
                    if not new_username or not new_password or not new_name:
                        st.error("아이디, 비밀번호, 이름은 필수 입력 항목입니다.")
                    else:
                        try:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute('''
                                INSERT INTO users (username, password, name, role, email, created_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (new_username, make_hashes(new_password), new_name, new_role, new_email, datetime.now().strftime("%Y-%m-%d")))
                            conn.commit()
                            conn.close()
                            
                            push_db_to_github()  # GitHub 백업
                            st.success(f"[{new_name}] 직원이 {new_role} 권한으로 등록되었습니다!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("이미 존재하는 아이디입니다.")
                        except Exception as e:
                            st.error(f"계정 생성 오류: {e}")

        # 오른쪽: 기존 직원 목록
        with col_u2:
            st.markdown("##### 📋 등록된 직원 및 권한 목록")
            conn = get_db_connection()
            df_users = pd.read_sql_query("SELECT username as 아이디, name as 이름, role as 권한, email as 이메일, created_at as 등록일 FROM users", conn)
            conn.close()
            st.dataframe(df_users, use_container_width=True, hide_index=True)

# ==========================================
# 탭 2: 구매/입고
# ==========================================
with tab2:
    st.subheader("📦 상품 구매 및 입고 등록 (Purchase/Inbound)")
    with st.form("purchase_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("입고 일자")
            partner_name = st.selectbox("매입처 선택 (Seller)", options=sellers)
        with col2:
            item_name = st.text_input("상품명 (Item Name)")
            qty = st.number_input("입고 수량 (Qty)", min_value=1, step=1)
        with col3:
            price = st.number_input("단가 (Unit Price)", min_value=0.0, step=0.1)
            total_amount = qty * price
            st.info(f"총 금액: {total_amount:,.2f}")
            
        if st.form_submit_button("입고 내역 저장", type="primary"):
            if item_name and partner_name != "등록된 매입처 없음":
                conn = get_db_connection()
                conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_name, qty, price, total_amount, manager) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (trans_date, "입고", partner_name, item_name, qty, price, total_amount, st.session_state['user_name']))
                conn.commit(); conn.close(); push_db_to_github()
                st.success("입고 처리가 완료되었습니다!")
                st.rerun()
            else: st.error("상품명 입력 및 매입처 선택이 필요합니다.")
            
    st.markdown("#### 최근 입고 내역")
    conn = get_db_connection()
    df_in = pd.read_sql_query("SELECT trans_date as 일자, partner_name as 매입처, item_name as 상품명, qty as 수량, price as 단가, total_amount as 총액, manager as 담당자 FROM transactions WHERE trans_type='입고' ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df_in, use_container_width=True, hide_index=True)

# ==========================================
# 탭 3: 판매/출고
# ==========================================
with tab3:
    st.subheader("🏷️ 상품 판매 및 출고 등록 (Sales/Outbound)")
    with st.form("sales_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trans_date = st.date_input("출고 일자")
            partner_name = st.selectbox("매출처 선택 (Buyer)", options=buyers)
        with col2:
            item_name = st.text_input("상품명 (Item Name)")
            qty = st.number_input("출고 수량 (Qty)", min_value=1, step=1)
        with col3:
            price = st.number_input("판매 단가 (Unit Price)", min_value=0.0, step=0.1)
            total_amount = qty * price
            st.info(f"총 금액: {total_amount:,.2f}")
            
        if st.form_submit_button("출고 내역 저장", type="primary"):
            if item_name and partner_name != "등록된 매출처 없음":
                conn = get_db_connection()
                conn.execute("INSERT INTO transactions (trans_date, trans_type, partner_name, item_name, qty, price, total_amount, manager) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (trans_date, "출고", partner_name, item_name, qty, price, total_amount, st.session_state['user_name']))
                conn.commit(); conn.close(); push_db_to_github()
                st.success("출고 처리가 완료되었습니다!")
                st.rerun()
            else: st.error("상품명 입력 및 매출처 선택이 필요합니다.")

    st.markdown("#### 최근 출고 내역")
    conn = get_db_connection()
    df_out = pd.read_sql_query("SELECT trans_date as 일자, partner_name as 매출처, item_name as 상품명, qty as 수량, price as 단가, total_amount as 총액, manager as 담당자 FROM transactions WHERE trans_type='출고' ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df_out, use_container_width=True, hide_index=True)

# ==========================================
# 탭 4: 엑셀 보고서
# ==========================================
with tab4:
    st.subheader("📊 데이터 다운로드")
    conn = get_db_connection()
    df_all_trans = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)
    conn.close()
    if not df_all_trans.empty:
        csv = df_all_trans.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📦 전체 입출고 내역 엑셀 다운로드 (CSV)", data=csv, file_name=f'transactions_{datetime.now().strftime("%Y%m%d")}.csv', mime='text/csv')
    else:
        st.info("아직 입출고 내역이 없습니다.")
