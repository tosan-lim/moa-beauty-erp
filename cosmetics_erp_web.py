import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import base64
import requests

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
        # 로컬(내 컴퓨터)에서 테스트할 때는 토큰이 없으므로 백업 건너뜀
        return
    
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. 기존 파일 정보(sha) 가져오기
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            sha = response.json()['sha']
        else:
            sha = None
    except Exception as e:
        print(f"GitHub 정보 조회 실패: {e}")
        return

    # 2. 내 서버에 있는 최신 DB 파일을 읽어서 Base64로 인코딩
    try:
        with open(FILE_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode('utf-8')
    except FileNotFoundError:
        print("백업할 DB 파일을 찾을 수 없습니다.")
        return

    # 3. GitHub로 파일 덮어쓰기 (Push)
    data = {
        "message": f"Auto-backup DB via Streamlit ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
        "content": content,
    }
    if sha:
        data["sha"] = sha

    try:
        put_response = requests.put(url, headers=headers, json=data)
        if put_response.status_code in [200, 201]:
            print("DB 자동 백업 성공!")
        else:
            print(f"DB 자동 백업 실패: {put_response.text}")
    except Exception as e:
         print(f"GitHub Push 오류 발생: {e}")


# -------------------------------------------------------------------
# 🛠️ 데이터베이스 연결 설정
# -------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect('kil_india_erp.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # 파트너(거래처) 테이블 생성
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
    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# 🌐 웹 앱 구성 (Streamlit)
# -------------------------------------------------------------------
st.set_page_config(page_title="KIL INDIA - Moa Beauty ERP", layout="wide")

# 다국어 설정
languages = {
    'KR': {
        'title': 'KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP',
        'subtitle': '인도 법인 화장품 재고 및 GST/관세 통합 관리 웹 시스템',
        'tab_master': '📋 기초등록 (Master)',
        'tab_purchase': '📦 구매/입고 (Purchase)',
        'tab_sales': '🏷️ 판매/출고 (Sales)',
        'tab_reports': '📊 엑셀 보고서 (Reports)',
        'partner_reg': '거래처 상세 등록',
        'p_code': '거래처코드',
        'p_name': '상호명',
        'p_type': '구분',
        'p_type_buyer': '매출처/Buyer',
        'p_type_seller': '매입처/Seller',
        'p_phone': '전화번호',
        'p_email': '이메일',
        'p_state': 'State(주)',
        'p_addr': '상세주소',
        'p_contact': '담당자명',
        'p_category': '카테고리',
        'btn_save': '거래처 저장',
        'msg_success': '거래처가 성공적으로 등록/수정되었습니다!',
        'msg_error': '등록 중 오류가 발생했습니다: '
    },
    'EN': {
         'title': 'KIL INDIA TRADE PVT. LTD. - Moa Beauty ERP',
         'subtitle': 'Cosmetics Inventory & GST/Customs Web System for India Branch',
         'tab_master': '📋 Master Data',
         'tab_purchase': '📦 Purchase/Inbound',
         'tab_sales': '🏷️ Sales/Outbound',
         'tab_reports': '📊 Excel Reports',
         'partner_reg': 'Partner Registration',
         'p_code': 'Partner Code',
         'p_name': 'Company Name',
         'p_type': 'Type',
         'p_type_buyer': 'Buyer',
         'p_type_seller': 'Seller',
         'p_phone': 'Phone No.',
         'p_email': 'Email',
         'p_state': 'State',
         'p_addr': 'Address',
         'p_contact': 'Contact Person',
         'p_category': 'Category',
         'btn_save': 'Save Partner',
         'msg_success': 'Partner successfully registered/updated!',
         'msg_error': 'Error occurred: '
    }
}

# 사이드바 (언어 선택 및 로고)
with st.sidebar:
    # 로고 이미지 삽입 (선택 사항)
    # st.image("logo.png", width=200) 
    st.markdown("### KIL INDIA TRADE")
    st.markdown("---")
    
    lang = st.radio("🌐 Language / 언어 선택", ['한국어 KR', 'English GB'])
    t = languages['KR'] if 'KR' in lang else languages['EN']

# 메인 헤더
st.title(t['title'])
st.markdown(f"*{t['subtitle']}*")
st.markdown("---")

# 앱 시작 시 DB 생성/확인
init_db()

# 상단 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([t['tab_master'], t['tab_purchase'], t['tab_sales'], t['tab_reports']])

# ==========================================
# 탭 1: 기초 등록 (Master Data)
# ==========================================
with tab1:
    st.subheader(t['partner_reg'])
    
    with st.form("partner_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            p_code = st.text_input(t['p_code'])
            p_phone = st.text_input(t['p_phone'])
            p_addr = st.text_input(t['p_addr'])
        with col2:
            p_name = st.text_input(t['p_name'])
            p_email = st.text_input(t['p_email'])
            p_contact = st.text_input(t['p_contact'])
        with col3:
            p_type = st.selectbox(t['p_type'], [t['p_type_buyer'], t['p_type_seller']])
            p_state = st.text_input(t['p_state'])
            p_category = st.text_input(t['p_category'])
            
        submitted = st.form_submit_button(t['btn_save'], type="primary")
        
        if submitted:
            if not p_code or not p_name:
                st.error(t['msg_error'] + " (코드와 상호명은 필수입니다. Code and Name are required.)")
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
                    
                    # 🔥 데이터 저장 후 GitHub로 백업 기능 실행!
                    push_db_to_github()

                    st.success(t['msg_success'])
                except Exception as e:
                    st.error(f"{t['msg_error']} {e}")

    # 현재 등록된 거래처 리스트 보여주기
    st.markdown("---")
    st.markdown("#### Registered Partners List")
    conn = get_db_connection()
    df_partners = pd.read_sql_query("SELECT * FROM partners", conn)
    conn.close()
    if not df_partners.empty:
        st.dataframe(df_partners, use_container_width=True, hide_index=True)
    else:
        st.info("등록된 거래처가 없습니다. (No partners registered yet.)")


# ==========================================
# 탭 2: 구매/입고 (추후 개발)
# ==========================================
with tab2:
    st.info("📦 메뉴 준비 중입니다. (Module under construction)")

# ==========================================
# 탭 3: 판매/출고 (추후 개발)
# ==========================================
with tab3:
    st.info("🏷️ 메뉴 준비 중입니다. (Module under construction)")

# ==========================================
# 탭 4: 엑셀 보고서 다운로드
# ==========================================
with tab4:
    st.subheader(t['tab_reports'])
    st.markdown("클릭 한 번으로 현재 데이터를 엑셀(Excel) 파일로 다운로드 받을 수 있습니다.")
    
    if not df_partners.empty:
        # 데이터프레임을 CSV로 변환
        csv = df_partners.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label="📊 거래처 목록 다운로드 (Download Partner List Excel)",
            data=csv,
            file_name=f'partner_list_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )
