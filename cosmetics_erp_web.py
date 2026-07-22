import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import base64
import requests
import hashlib

# -------------------------------------------------------------------
# 🔒 GitHub 연동 설정 (Secrets에서 가져오기)
# -------------------------------------------------------------------
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
except:
    GITHUB_TOKEN = None
    REPO_NAME = None

FILE_PATH = "kil_india_erp.db"  # GitHub에 저장될 파일명

def push_db_to_github():
    """웹에서 DB가 변경될 때마다 GitHub로 자동 백업(Push)하는 함수"""
    if not GITHUB_TOKEN or not REPO_NAME:
        return
    
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(url, headers=headers)
        sha = response.json()['sha'] if response.status_code == 200 else None
    except Exception as e:
        print(f"GitHub 정보 조회 실패: {e}")
        return

    try:
        with open(FILE_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode('utf-8')
    except FileNotFoundError:
        print("백업할 DB 파일을 찾을 수 없습니다.")
        return

    data = {
        "message": f"Auto-backup DB via Streamlit ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        "content": content,
    }
    if sha:
        data["sha"] = sha

    try:
        requests.put(url, headers=headers, json=data)
    except Exception as e:
        print(f"GitHub Push 오류 발생: {e}")


# -------------------------------------------------------------------
# 🛠️ 데이터베이스 및 암호화 설정
# -------------------------------------------------------------------
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def get_db_connection():
    conn = sqlite3.connect('kil_india_erp.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. 파트너(거래처) 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            partner_code TEXT PRIMARY KEY,
            partner_name TEXT NOT NULL,
            type TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            state TEXT,
            address TEXT,
            contact_person TEXT,
            category TEXT,
            registration_date TEXT
        )
    ''')
    
    # 2. 사용자(직원) 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT,
            created_at TEXT
        )
    ''')
    
    # 기본 관리자 계정 생성 (없는 경우)
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        default_pwd = make_hashes("admin123")
        c.execute('''
            INSERT INTO users (username, password, name, role, email, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', default_pwd, '대표/관리자', 'Admin', 'admin@kecindia.in', datetime.now().strftime("%Y-%m-%d")))
    
    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# 🌐 웹 앱 기본 설정
# -------------------------------------------------------------------
st.set_page_config(page_title="KIL INDIA - Moa Beauty ERP", layout="wide")

init_db()

# 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = ''
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ''

# -------------------------------------------------------------------
# 🔑 로그인 화면
# -------------------------------------------------------------------
if not st.session_state['logged_in']:
    st.markdown("<h2 style='text-align: center;'>KIL INDIA TRADE PVT. LTD.</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Moa Beauty ERP System 로그인</h4>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("🔒 User Login")
            username_input = st.text_input("아이디 (Username)")
            password_input = st.text_input("비밀번호 (Password)", type="password")
            login_btn = st.form_submit_button("로그인 (Sign In)", type="primary", use_container_width=True)
            
            if login_btn:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username = ?", (username_input,))
                user = c.fetchone()
                conn.close()
                
                if user and check_hashes(password_input, user['password']):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user['username']
                    st.session_state['user_role'] = user['role']
                    st.session_state['user_name'] = user['name']
                    st.success(f"반갑습니다, {user['name']}님!")
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    st.stop()

# -------------------------------------------------------------------
# 🏢 로그인 성공 후 ERP 메인 화면
# -------------------------------------------------------------------

# 사이드바 (사용자 정보 및 로그아웃)
with st.sidebar:
    st.markdown("### KIL INDIA TRADE")
    st.info(f"👤 **{st.session_state['user_name']}** ({st.session_state['username']})\n\n🎖️ 권한: **{st.session_state['user_role']}**")
    
    if st.button("🚪 로그아웃 (Log Out)", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''
        st.session_state['user_role'] = ''
        st.session_state['user_name'] = ''
        st.rerun()
        
    st.markdown("---")
    lang = st.radio("🌐 Language / 언어 선택", ['한국어 KR', 'English GB'])

# 다국어 설정
languages = {
    'KR': {
        'title': 'KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP',
        'subtitle': '인도 법인 화장품 재고 및 GST/관세 통합 관리 웹 시스템',
        'tab_master': '📋 기초등록 (Master)',
        'tab_users': '👥 직원/계정 관리 (Admin)',
        'tab_purchase': '📦 구매/입고 (Purchase)',
        'tab_sales': '🏷️ 판매/출고 (Sales)',
        'tab_reports': '📊 엑셀 보고서 (Reports)',
    },
    'EN': {
        'title': 'KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP',
        'subtitle': 'Cosmetics Inventory & GST/Customs Web System for India Branch',
        'tab_master': '📋 Master Data',
        'tab_users': '👥 User Admin',
        'tab_purchase': '📦 Purchase/Inbound',
        'tab_sales': '🏷️ Sales/Outbound',
        'tab_reports': '📊 Excel Reports',
    }
}
t = languages['KR'] if 'KR' in lang else languages['EN']

st.title(t['title'])
st.markdown(f"*{t['subtitle']}*")
st.markdown("---")

# 탭 생성 (Admin에게만 직원관리 탭 표시)
if st.session_state['user_role'] == 'Admin':
    tab1, tab_user, tab2, tab3, tab4 = st.tabs([t['tab_master'], t['tab_users'], t['tab_purchase'], t['tab_sales'], t['tab_reports']])
else:
    tab1, tab2, tab3, tab4 = st.tabs([t['tab_master'], t['tab_purchase'], t['tab_sales'], t['tab_reports']])
    tab_user = None

# ==========================================
# 탭 1: 기초 등록 (Master Data)
# ==========================================
with tab1:
    st.subheader("거래처 상세 등록")
    
    # Staff 권한은 등록 제한 (조회만 가능)
    if st.session_state['user_role'] == 'Staff':
        st.warning("⚠️ Staff 권한은 거래처 조회가 가능하며, 등록/수정은 Manager 이상만 가능합니다.")
    else:
        with st.form("partner_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                p_code = st.text_input("거래처코드")
                p_phone = st.text_input("전화번호")
                p_addr = st.text_input("상세주소")
            with col2:
                p_name = st.text_input("상호명")
                p_email = st.text_input("이메일")
                p_contact = st.text_input("담당자명")
            with col3:
                p_type = st.selectbox("구분", ["매출처/Buyer", "매입처/Seller"])
                p_state = st.text_input("State(주)")
                p_category = st.text_input("카테고리")
                
            submitted = st.form_submit_button("거래처 저장", type="primary")
            
            if submitted:
                if not p_code or not p_name:
                    st.error("거래처코드와 상호명은 필수 입력 사항입니다.")
                else:
                    try:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''
                            INSERT OR REPLACE INTO partners 
                            (partner_code, partner_name, type, phone, email, state, address, contact_person, category, registration_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (p_code, p_name, p_type, p_phone, p_email, p_state, p_addr, p_contact, p_category, datetime.now().strftime("%Y-%m-%d")))
                        conn.commit()
                        conn.close()
                        
                        push_db_to_github()  # DB 백업
                        st.success("거래처가 성공적으로 저장되었습니다!")
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")

    st.markdown("---")
    st.markdown("#### 📜 등록된 거래처 목록")
    conn = get_db_connection()
    df_partners = pd.read_sql_query("SELECT * FROM partners", conn)
    conn.close()
    if not df_partners.empty:
        st.dataframe(df_partners, use_container_width=True, hide_index=True)
    else:
        st.info("등록된 거래처가 없습니다.")

# ==========================================
# 탭 Admin: 직원/계정 관리 (Admin 전용)
# ==========================================
if tab_user:
    with tab_user:
        st.subheader("👥 직원 계정 신규 등록 및 관리")
        
        col_u1, col_u2 = st.columns([1, 1])
        
        with col_u1:
            st.markdown("##### ➕ 새 계정 등록")
            with st.form("new_user_form", clear_on_submit=True):
                new_username = st.text_input("아이디 (Username)")
                new_password = st.text_input("비밀번호 (Password)", type="password")
                new_name = st.text_input("직원 이름 (Full Name)")
                new_role = st.selectbox("권한 (Role)", ["Staff", "Manager", "Admin"])
                new_email = st.text_input("이메일 주소")
                
                user_submit = st.form_submit_button("계정 생성", type="primary")
                
                if user_submit:
                    if not new_username or not new_password or not new_name:
                        st.error("아이디, 비밀번호, 이름은 필수입니다.")
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
                            
                            push_db_to_github()  # DB 백업
                            st.success(f"[{new_username}] 계정이 생성되었습니다.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("이미 존재하는 아이디입니다.")
                        except Exception as e:
                            st.error(f"계정 생성 오류: {e}")

        with col_u2:
            st.markdown("##### 📋 등록된 직원 계정 목록")
            conn = get_db_connection()
            df_users = pd.read_sql_query("SELECT username, name, role, email, created_at FROM users", conn)
            conn.close()
            st.dataframe(df_users, use_container_width=True, hide_index=True)

# ==========================================
# 탭 2: 구매/입고
# ==========================================
with tab2:
    st.info("📦 구매/입고 모듈 준비 중입니다.")

# ==========================================
# 탭 3: 판매/출고
# ==========================================
with tab3:
    st.info("🏷️ 판매/출고 모듈 준비 중입니다.")

# ==========================================
# 탭 4: 엑셀 보고서
# ==========================================
with tab4:
    st.subheader(t['tab_reports'])
    if not df_partners.empty:
        csv = df_partners.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📊 거래처 목록 엑셀 다운로드 (CSV)",
            data=csv,
            file_name=f'partner_list_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )
