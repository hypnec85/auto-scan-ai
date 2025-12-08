import streamlit as st
import pandas as pd
import uuid

# 분리된 모듈 임포트
from storage import load_data, save_session_data, load_session_data, cleanup_old_sessions
from domain_logic import categorize_car, get_row_signature
from ui_components import render_sidebar, render_add_car_form, render_edit_car_form, render_delete_car_form, render_analysis_results

# 페이지 설정
st.set_page_config(
    page_title="오토 스캔 (Auto Scan AI)",
    page_icon="🚗",
    layout="wide"
)

# 앱 시작 시 오래된 세션 파일 정리
cleanup_old_sessions()

# --- 메인 타이틀 ---
st.title("🚗 오토 스캔 (Auto Scan AI)")
st.markdown("""
**"이 차, 사도 될까요?"**  
오토 스캔 AI는 보수적인 정비 엔지니어의 시각으로 중고차의 성능점검기록부를 분석하여,  
절대 사면 안 되는 차(Tier 1)와 가성비 좋은 차(Tier 3)를 가려드립니다.
""")

# 기본 컬럼 및 데이터 타입 정의
DEFAULT_COLUMNS = {
    '차량명': str,
    '엔진': str,
    '트림': str,
    '색상': str,
    '차량가격(만원)': int,
    '연식': int,
    '최초 등록일': str,
    '주행거리(km)': int,
    '옵션': str,
    '수리내역': str,
    '특수용도이력': str,
    '1인소유': str,
    '내차피해액': int,
    '내차피해횟수': int,
    '상대차피해횟수': int,
    '일반부품보증기간(개월)': int,
    '일반부품보증거리(km)': int,
    '주요부품보증기간(개월)': int,
    '주요부품보증거리(km)': int,
    '_source': str
}

DEFAULT_DATA = {
    '옵션': '',
    '특수용도이력': 'X',
    '1인소유': 'O',
    '내차피해액': 0,
    '내차피해횟수': 0,
    '상대차피해횟수': 0,
    '수리내역': '',
    '일반부품보증기간(개월)': 36,
    '일반부품보증거리(km)': 60000,
    '주요부품보증기간(개월)': 60,
    '주요부품보증거리(km)': 100000,
    '_source': 'manual'
}

def get_session_id():
    """
    현재 사용자의 고유 세션 ID를 생성하거나 가져옵니다.
    Streamlit의 query_params를 활용하여 브라우저 새로고침 시에도 세션 ID를 유지합니다.
    """
    if "session_id" in st.query_params:
        return st.query_params["session_id"]
    else:
        new_session_id = str(uuid.uuid4())
        st.query_params["session_id"] = new_session_id
        return new_session_id

# 세션 상태 초기화 및 복구
session_id = get_session_id()

if 'session_id' not in st.session_state or st.session_state.session_id != session_id:
    st.session_state.session_id = session_id

saved_data = load_session_data(st.session_state.session_id)

if 'df' not in st.session_state or not isinstance(st.session_state.df, pd.DataFrame):
    if saved_data and 'df' in saved_data:
        st.session_state.df = saved_data['df']
    else:
        st.session_state.df = pd.DataFrame(columns=DEFAULT_COLUMNS.keys())
else:
    for col in DEFAULT_COLUMNS.keys():
        if col not in st.session_state.df.columns:
            if col == '_source':
                st.session_state.df[col] = 'manual'
            else:
                st.session_state.df[col] = DEFAULT_DATA.get(col, '')

if 'analyzed_df' not in st.session_state:
    st.session_state.analyzed_df = None
if 'ai_report' not in st.session_state:
    st.session_state.ai_report = None
if 'ai_model_used' not in st.session_state:
    st.session_state.ai_model_used = None
if 'generating_report' not in st.session_state:
    st.session_state.generating_report = False
if 'menu_index' not in st.session_state:
    st.session_state.menu_index = 0
if 'user_preference' not in st.session_state:
    st.session_state.user_preference = "밸런스"
if 'form_expanded' not in st.session_state:
    st.session_state.form_expanded = True
if 'confirm_delete_all' not in st.session_state:
    st.session_state.confirm_delete_all = False
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'deleted_csv_rows' not in st.session_state:
    if saved_data and 'deleted_rows' in saved_data:
        st.session_state.deleted_csv_rows = saved_data['deleted_rows']
    else:
        st.session_state.deleted_csv_rows = set()

# 신규 매물 폼 위젯 상태 초기화
if 'add_name' not in st.session_state: st.session_state['add_name'] = ""
if 'add_engine' not in st.session_state: st.session_state['add_engine'] = ""
if 'add_trim' not in st.session_state: st.session_state['add_trim'] = ""
if 'add_color' not in st.session_state: st.session_state['add_color'] = ""
if 'add_price' not in st.session_state: st.session_state['add_price'] = 0
if 'add_year' not in st.session_state: st.session_state['add_year'] = 2020
if 'add_km' not in st.session_state: st.session_state['add_km'] = 0
if 'add_reg_date' not in st.session_state: st.session_state['add_reg_date'] = pd.Timestamp.now().date()
if 'add_special' not in st.session_state: st.session_state['add_special'] = "X"
if 'add_one_owner' not in st.session_state: st.session_state['add_one_owner'] = "O"
if 'add_my_damage_cnt' not in st.session_state: st.session_state['add_my_damage_cnt'] = 0
if 'add_other_damage_cnt' not in st.session_state: st.session_state['add_other_damage_cnt'] = 0
if 'add_my_damage_amt' not in st.session_state: st.session_state['add_my_damage_amt'] = 0
if 'add_repair' not in st.session_state: st.session_state['add_repair'] = ""
if 'add_option' not in st.session_state: st.session_state['add_option'] = ""
if 'add_war_gen_mon' not in st.session_state: st.session_state['add_war_gen_mon'] = 36
if 'add_war_gen_km' not in st.session_state: st.session_state['add_war_gen_km'] = 60000
if 'add_war_maj_mon' not in st.session_state: st.session_state['add_war_maj_mon'] = 60
if 'add_war_maj_km' not in st.session_state: st.session_state['add_war_maj_km'] = 100000

# 데이터 변경 시 자동 저장 함수
def auto_save():
    save_session_data(st.session_state.session_id, st.session_state.df, st.session_state.deleted_csv_rows)

# 콜백 함수들
def start_generation():
    st.session_state.generating_report = True
    st.session_state.menu_index = 1 
    st.session_state.copied_prompt_text = None # Clear copied prompt

def reset_generation():
    st.session_state.ai_report = None
    st.session_state.ai_model_used = None
    st.session_state.generating_report = True
    st.session_state.menu_index = 1 
    st.session_state.copied_prompt_text = None # Clear copied prompt

def load_csv_file_callback():
    key = f"uploaded_csv_files_{st.session_state.uploader_key}"
    uploaded_file_objs = st.session_state.get(key)
    
    current_manual_data = pd.DataFrame()
    if not st.session_state.df.empty and '_source' in st.session_state.df.columns:
        current_manual_data = st.session_state.df[st.session_state.df['_source'] == 'manual'].copy()
    
    new_csv_data = pd.DataFrame(columns=DEFAULT_COLUMNS.keys())
    
    if uploaded_file_objs:
        all_dfs = []
        for uploaded_file_obj in uploaded_file_objs:
            loaded_df = load_data(uploaded_file_obj)
            if loaded_df is not None:
                loaded_df = loaded_df.loc[:, ~loaded_df.columns.str.contains('^Unnamed')]
                loaded_df['_source'] = 'csv'
                all_dfs.append(loaded_df)
        
        if all_dfs:
            combined_csv_df = pd.concat(all_dfs, ignore_index=True)
            
            for col in DEFAULT_COLUMNS.keys():
                if col not in combined_csv_df.columns:
                    combined_csv_df[col] = DEFAULT_DATA.get(col, '')
                try:
                    if col == '최초 등록일':
                        combined_csv_df[col] = pd.to_datetime(combined_csv_df[col], errors='coerce').dt.strftime('%Y-%m-%d')
                        combined_csv_df[col] = combined_csv_df[col].fillna('')
                    elif DEFAULT_COLUMNS[col] == int:
                        combined_csv_df[col] = pd.to_numeric(combined_csv_df[col], errors='coerce').fillna(0).astype(int)
                    else:
                        combined_csv_df[col] = combined_csv_df[col].astype(DEFAULT_COLUMNS[col])
                except Exception as e:
                    st.warning(f"경고: '{col}' 컬럼의 데이터 타입 변환 중 오류가 발생했습니다. 원인: {e} - 일부 데이터가 유실될 수 있습니다.")
            
            if not combined_csv_df.empty:
                rows_to_keep = []
                for idx, row in combined_csv_df.iterrows():
                    sig = get_row_signature(row)
                    if sig not in st.session_state.deleted_csv_rows:
                        rows_to_keep.append(row)
                
                if rows_to_keep:
                    new_csv_data = pd.DataFrame(rows_to_keep)
                else:
                    new_csv_data = pd.DataFrame(columns=DEFAULT_COLUMNS.keys())

    combined_df = pd.concat([current_manual_data, new_csv_data], ignore_index=True)
    st.session_state.df = combined_df
    st.session_state.analyzed_df = None
    st.session_state.form_expanded = False
    
    auto_save()
    
    if not new_csv_data.empty:
        st.success(f"총 {len(uploaded_file_objs)}개의 파일을 성공적으로 불러와 합쳤습니다. (삭제된 항목 제외, 수기 입력 데이터 {len(current_manual_data)}건 유지됨)")
    elif not current_manual_data.empty:
        st.info(f"업로드된 파일이 제거되었거나 모든 CSV 항목이 삭제 이력에 있습니다. 수기 입력 데이터 {len(current_manual_data)}건만 남았습니다.")
    else:
        st.info("모든 데이터가 초기화되었습니다.")

def add_car_callback():
    new_name = st.session_state.get('add_name', '')
    new_engine = st.session_state.get('add_engine', '')
    new_trim = st.session_state.get('add_trim', '')
    new_color = st.session_state.get('add_color', '')
    new_price = st.session_state.get('add_price', 0)
    new_year = st.session_state.get('add_year', 2020)
    new_km = st.session_state.get('add_km', 0)
    new_reg_date = st.session_state.get('add_reg_date', pd.Timestamp.now().date())
    new_special = st.session_state.get('add_special', 'X')
    new_one_owner = st.session_state.get('add_one_owner', 'O')
    new_my_damage_cnt = st.session_state.get('add_my_damage_cnt', 0)
    new_other_damage_cnt = st.session_state.get('add_other_damage_cnt', 0)
    new_my_damage_amt = st.session_state.get('add_my_damage_amt', 0)
    new_repair = st.session_state.get('add_repair', '')
    new_option = st.session_state.get('add_option', '')
    new_war_gen_mon = st.session_state.get('add_war_gen_mon', 36)
    new_war_gen_km = st.session_state.get('add_war_gen_km', 60000)
    new_war_maj_mon = st.session_state.get('add_war_maj_mon', 60)
    new_war_maj_km = st.session_state.get('add_war_maj_km', 100000)

    new_data = {
        '차량명': new_name,
        '엔진': new_engine,
        '트림': new_trim,
        '색상': new_color,
        '차량가격(만원)': new_price,
        '연식': new_year,
        '최초 등록일': str(new_reg_date),
        '주행거리(km)': new_km,
        '옵션': new_option,
        '수리내역': new_repair,
        '특수용도이력': new_special,
        '1인소유': new_one_owner,
        '내차피해액': new_my_damage_amt,
        '내차피해횟수': new_my_damage_cnt,
        '상대차피해횟수': new_other_damage_cnt,
        '일반부품보증기간(개월)': new_war_gen_mon,
        '일반부품보증거리(km)': new_war_gen_km,
        '주요부품보증기간(개월)': new_war_maj_mon,
        '주요부품보증거리(km)': new_war_maj_km,
        '_source': 'manual'
    }
    
    new_row = pd.DataFrame([new_data])
    st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
    
    auto_save()
    
    st.session_state['add_success_msg'] = f"✅ 차량 추가 완료: {new_name} ({new_price}만원 / {new_km:,}km / {new_color})"

    st.session_state['add_color'] = ""
    st.session_state['add_price'] = 0
    st.session_state['add_year'] = 2020
    st.session_state['add_km'] = 0
    st.session_state['add_reg_date'] = pd.Timestamp.now().date()
    st.session_state['add_special'] = "X"
    st.session_state['add_one_owner'] = "O"
    st.session_state['add_my_damage_cnt'] = 0
    st.session_state['add_other_damage_cnt'] = 0
    st.session_state['add_my_damage_amt'] = 0
    st.session_state['add_repair'] = ""
    st.session_state['add_option'] = ""

# UI 렌더링 호출
render_sidebar(load_csv_file_callback, DEFAULT_COLUMNS, DEFAULT_DATA, auto_save)

st.subheader("📝 매물 데이터 관리")

render_add_car_form(add_car_callback)

if not st.session_state.df.empty:
    render_edit_car_form(auto_save)
    render_delete_car_form(auto_save)

# 현재 매물 리스트 조회
st.subheader(f"📋 현재 등록된 매물 리스트 ({len(st.session_state.df)}대)")
st.dataframe(st.session_state.df.drop(columns=['_source'], errors='ignore'), use_container_width=True)

st.divider()

# 분석 버튼
if not st.session_state.df.empty:
    if st.button("🔍 현재 데이터로 정밀 분석 시작", type="primary"):
        with st.spinner("데이터를 분석 중입니다..."):
            df_to_analyze = st.session_state.df.copy()
            df_to_analyze['수리내역'] = df_to_analyze['수리내역'].fillna('')
            df_to_analyze[['Tier', '분석결과']] = df_to_analyze.apply(categorize_car, axis=1)
            st.session_state.analyzed_df = df_to_analyze
            st.session_state.ai_report = None 
            st.session_state.ai_model_used = None
            st.session_state.generating_report = False
            st.session_state.menu_index = 0
            st.rerun()

# 분석 결과 뷰
if st.session_state.analyzed_df is not None:
    render_analysis_results(start_generation, reset_generation)