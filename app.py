import streamlit as st
import pandas as pd
import os
import streamlit.components.v1 as components
from utils import load_data, categorize_car, generate_engineer_report

# 페이지 설정
st.set_page_config(
    page_title="오토 스캔 (Auto Scan AI)",
    page_icon="🚗",
    layout="wide"
)

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
    '_source': 'manual'
}

# 세션 상태 초기화
if 'df' not in st.session_state or not isinstance(st.session_state.df, pd.DataFrame):
    st.session_state.df = pd.DataFrame(columns=DEFAULT_COLUMNS.keys()) # 빈 DataFrame으로 초기화
else:
    # 기존 세션 데이터에 새로운 컬럼(예: 옵션)이 없는 경우 마이그레이션
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
if 'ai_model_used' not in st.session_state: # 모델명 저장용 세션 변수
    st.session_state.ai_model_used = None
if 'generating_report' not in st.session_state:
    st.session_state.generating_report = False
if 'menu_index' not in st.session_state:
    st.session_state.menu_index = 0
if 'user_preference' not in st.session_state:
    st.session_state.user_preference = "밸런스"
if 'form_expanded' not in st.session_state: # 폼 확장 상태 제어
    st.session_state.form_expanded = True
if 'confirm_delete_all' not in st.session_state:
    st.session_state.confirm_delete_all = False
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'deleted_csv_rows' not in st.session_state: # 삭제된 CSV 행의 고유 시그니처 저장
    st.session_state.deleted_csv_rows = set()

# 콜백 함수
def start_generation():
    st.session_state.generating_report = True
    st.session_state.menu_index = 1 

def reset_generation():
    st.session_state.ai_report = None
    st.session_state.ai_model_used = None
    st.session_state.generating_report = True
    st.session_state.menu_index = 1 

def get_row_signature(row):
    """행 데이터를 기반으로 고유 시그니처 생성 (중복 방지 및 식별용)"""
    # 식별에 사용할 주요 컬럼들
    cols = ['차량명', '차량가격(만원)', '주행거리(km)', '연식', '최초 등록일', '수리내역']
    sig_parts = []
    for c in cols:
        val = row.get(c, '')
        sig_parts.append(str(val))
    return "_".join(sig_parts)

def load_csv_file_callback():
    # 동적 키를 사용하여 파일 객체 가져오기
    key = f"uploaded_csv_files_{st.session_state.uploader_key}"
    uploaded_file_objs = st.session_state.get(key) # key로 직접 접근 (리스트 반환)
    
    # 기존 데이터 중 수기 입력 데이터만 백업
    current_manual_data = pd.DataFrame()
    if not st.session_state.df.empty and '_source' in st.session_state.df.columns:
        current_manual_data = st.session_state.df[st.session_state.df['_source'] == 'manual'].copy()
    
    # 새로 로드된 CSV 데이터 처리
    new_csv_data = pd.DataFrame(columns=DEFAULT_COLUMNS.keys())
    
    if uploaded_file_objs:
        all_dfs = []
        for uploaded_file_obj in uploaded_file_objs:
            loaded_df = load_data(uploaded_file_obj)
            if loaded_df is not None:
                loaded_df = loaded_df.loc[:, ~loaded_df.columns.str.contains('^Unnamed')]
                loaded_df['_source'] = 'csv' # 소스 태그 추가
                all_dfs.append(loaded_df)
        
        if all_dfs:
            combined_csv_df = pd.concat(all_dfs, ignore_index=True)
            
            # 컬럼 타입 맞추기 및 누락 컬럼 처리
            for col in DEFAULT_COLUMNS.keys():
                if col not in combined_csv_df.columns:
                    combined_csv_df[col] = DEFAULT_DATA.get(col, '')
                try:
                    if col == '최초 등록일':
                        combined_csv_df[col] = pd.to_datetime(combined_csv_df[col], errors='coerce').dt.strftime('%Y-%m-%d')
                        combined_csv_df[col] = combined_csv_df[col].fillna('')
                    elif DEFAULT_COLUMNS[col] == int: # DEFAULT_COLUMNS에서 int로 정의된 경우 처리
                        combined_csv_df[col] = pd.to_numeric(combined_csv_df[col], errors='coerce').fillna(0).astype(int)
                    else:
                        combined_csv_df[col] = combined_csv_df[col].astype(DEFAULT_COLUMNS[col])
                except Exception as e:
                    st.warning(f"경고: '{col}' 컬럼의 데이터 타입 변환 중 오류가 발생했습니다. 원인: {e} - 일부 데이터가 유실될 수 있습니다.")
            
            # 삭제된 이력 확인 및 필터링
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

            
    # 수기 데이터와 CSV 데이터 병합
    combined_df = pd.concat([current_manual_data, new_csv_data], ignore_index=True)
    st.session_state.df = combined_df
    st.session_state.analyzed_df = None
    st.session_state.form_expanded = False # CSV 로드 시 폼 접기
    
    if not new_csv_data.empty:
        st.success(f"총 {len(uploaded_file_objs)}개의 파일을 성공적으로 불러와 합쳤습니다. (삭제된 항목 제외, 수기 입력 데이터 {len(current_manual_data)}건 유지됨)")
    elif not current_manual_data.empty:
        st.info(f"업로드된 파일이 제거되었거나 모든 CSV 항목이 삭제 이력에 있습니다. 수기 입력 데이터 {len(current_manual_data)}건만 남았습니다.")
    else:
        st.info("모든 데이터가 초기화되었습니다.")

# 사이드바 설정
with st.sidebar:
    st.header("데이터 관리")
    
    # CSV 불러오기
    st.file_uploader("CSV 파일들 불러오기 (현재 데이터 덮어쓰기)", type=['csv'], 
                                         accept_multiple_files=True,
                                         on_change=load_csv_file_callback, 
                                         key=f"uploaded_csv_files_{st.session_state.uploader_key}")
    
    # CSV 내보내기
    if not st.session_state.df.empty:
        csv = st.session_state.df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="현재 데이터 CSV로 내보내기",
            data=csv,
            file_name="used_car_data.csv",
            mime="text/csv",
        )
    
    # 샘플 데이터 로드 버튼
    if os.path.exists("sample_data.csv"):
        if st.button("테스트용 데이터 로드"):
            st.session_state.show_sample_warning = True

    if st.session_state.get('show_sample_warning', False):
        st.warning("⚠️ 테스트 데이터를 로드하면 현재 입력된 모든 정보가 사라집니다. 진행하시겠습니까?")
        col_confirm_1, col_confirm_2 = st.columns(2)
        with col_confirm_1:
            if st.button("✅ 예, 로드합니다"):
                st.session_state.show_sample_warning = False
                loaded_df = load_data("sample_data.csv")
                if loaded_df is not None:
                    loaded_df = loaded_df.loc[:, ~loaded_df.columns.str.contains('^Unnamed')]
                    loaded_df['_source'] = 'manual' # 샘플 데이터는 수기(manual) 취급
                    
                    for col in DEFAULT_COLUMNS.keys():
                        if col not in loaded_df.columns:
                            loaded_df[col] = DEFAULT_DATA.get(col, '')
                        try:
                            if col == '최초 등록일':
                                loaded_df[col] = pd.to_datetime(loaded_df[col], errors='coerce').dt.strftime('%Y-%m-%d')
                                loaded_df[col] = loaded_df[col].fillna('')
                            elif DEFAULT_COLUMNS[col] == int: # DEFAULT_COLUMNS에서 int로 정의된 경우 처리
                                loaded_df[col] = pd.to_numeric(loaded_df[col], errors='coerce').fillna(0).astype(int)
                            else:
                                loaded_df[col] = loaded_df[col].astype(DEFAULT_COLUMNS[col])
                        except Exception as e:
                            st.warning(f"경고: '{col}' 컬럼의 데이터 타입 변환 중 오류가 발생했습니다. 원인: {e} - 일부 데이터가 유실될 수 있습니다.")
                    
                    st.session_state.df = loaded_df
                    st.session_state.analyzed_df = None
                    st.session_state.form_expanded = False
                    st.success("샘플 데이터를 성공적으로 불러왔습니다.")
                    st.rerun()
        with col_confirm_2:
            if st.button("❌ 취소"):
                st.session_state.show_sample_warning = False
                st.rerun()

    st.divider()

    # 사용자 성향 입력 슬라이더
    st.subheader("💡 분석 성향 선택")
    st.session_state.user_preference = st.select_slider(
        "어떤 기준으로 분석할까요?",
        options=["가성비 최우선", "밸런스", "안전 최우선"],
        value=st.session_state.user_preference
    )
    st.markdown(f"현재 선택: **{st.session_state.user_preference}**")

    st.divider()

    # 분석 결과 메뉴 (분석된 데이터가 있을 때만 표시)
    if st.session_state.analyzed_df is not None:
        menu_options = ["📊 전체 리스트", "🤖 AI 엔지니어 리포트", "🏆 Rule-Based 추천", "🚨 Rule-Based 경고"]
        
        selected_menu = st.radio(
            "분석 결과 보기", 
            menu_options, 
            index=st.session_state.menu_index
        )
        if menu_options.index(selected_menu) != st.session_state.menu_index:
             st.session_state.menu_index = menu_options.index(selected_menu)
             st.rerun()
        
        st.divider()

    if st.button("초기화 (모든 데이터 삭제)"):
        st.session_state.df = pd.DataFrame(columns=DEFAULT_COLUMNS.keys())
        st.session_state.analyzed_df = None
        st.session_state.ai_report = None
        st.session_state.ai_model_used = None
        st.session_state.generating_report = False
        st.session_state.menu_index = 0
        st.session_state.form_expanded = True
        st.session_state.uploader_key += 1 # 파일 업로더 초기화
        st.session_state.deleted_csv_rows = set() # 삭제 이력 초기화
        st.rerun()
    
    with st.expander("Tier 시스템 가이드 보기"):
        st.info("Tier 시스템 가이드")
        st.markdown("""
        - **Tier 1 (구매 금지)**: 휠하우스, 사이드멤버 등 주요 골격 손상.
        - **Tier 2 (경고)**: 리어패널, 인사이드패널 등 2차 골격 손상.
        - **Tier 3 (추천)**: 휀더, 도어 등 단순 외판 교환.
        """)

# 메인 컨텐츠
st.subheader("📝 매물 데이터 관리")

# --- 1. 신규 매물 추가 Form ---
with st.expander("➕ 신규 매물 직접 추가하기 (Form 입력)", expanded=st.session_state.form_expanded):
    st.info("아래 양식을 작성하여 리스트에 매물을 추가하세요.")
    with st.form("add_car_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_name = st.text_input("차량명", placeholder="예: 아반떼 CN7")
            new_price = st.number_input("차량가격(만원)", min_value=0, step=10, value=0)
        with col2:
            new_engine = st.text_input("엔진", placeholder="예: 가솔린 1.6")
            new_year = st.number_input("연식", min_value=1900, max_value=2100, step=1, value=2020)
        with col3:
            new_trim = st.text_input("트림", placeholder="예: 인스퍼레이션")
            new_km = st.number_input("주행거리(km)", min_value=0, step=1000, value=0)
        with col4:
            new_color = st.text_input("색상", placeholder="예: 화이트")
            new_reg_date = st.date_input("최초 등록일")

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            new_special = st.selectbox("특수용도이력", ["X", "O"])
        with col6:
            new_one_owner = st.selectbox("1인소유", ["O", "X"])
        with col7:
            new_my_damage_cnt = st.number_input("내차피해횟수", min_value=0, step=1, value=0)
        with col8:
            new_other_damage_cnt = st.number_input("상대차피해횟수", min_value=0, step=1, value=0)
        
        new_my_damage_amt = st.number_input("내차피해액(원)", min_value=0, step=10000, value=0)
        new_repair = st.text_area("수리내역 (중요)", placeholder="성능점검기록부의 수리내역을 입력하세요. (예: 후드 교환, 프론트휀더(우) 판금)")
        new_option = st.text_area("옵션", placeholder="옵션 내용을 자유롭게 입력하세요. (예: 10.25인치 UVO 내비게이션 93만원, 파노라마 선루프 118만원)")

        submitted = st.form_submit_button("매물 리스트에 추가")
        
        if submitted:
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
                '_source': 'manual' # 수기 입력 표시
            }
            # DataFrame에 추가
            new_row = pd.DataFrame([new_data])
            st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
            st.success(f"'{new_name}' 차량이 추가되었습니다!")
            st.rerun()

st.divider()

# --- 2. 현재 매물 리스트 확인 및 삭제 ---
st.subheader(f"📋 현재 등록된 매물 리스트 ({len(st.session_state.df)}대)")

# 데이터 삭제 기능
if not st.session_state.df.empty:
    # 삭제 선택중이거나 전체 삭제 확인 중일 때 확장 유지
    is_expanded = st.session_state.get('confirm_delete_all', False) or bool(st.session_state.get('delete_multiselect', []))
    
    with st.expander("🗑️ 매물 삭제하기", expanded=is_expanded):
        # 인덱스와 차량명으로 선택지 생성
        delete_options = [f"{i} : {row['차량명']} ({row['차량가격(만원)']}만원)" for i, row in st.session_state.df.iterrows()]
        selected_to_delete = st.multiselect("삭제할 차량을 선택하세요:", delete_options, key='delete_multiselect')
        
        col_del_1, col_del_2 = st.columns([1, 1])
        with col_del_1:
            if st.button("선택한 차량 삭제", use_container_width=True):
                if selected_to_delete:
                    indices_to_drop = [int(opt.split(" :")[0]) for opt in selected_to_delete]
                    
                    # 삭제되는 행들 중 CSV 출신인 경우 시그니처 저장
                    for idx in indices_to_drop:
                        if idx < len(st.session_state.df):
                            row = st.session_state.df.iloc[idx]
                            if row.get('_source') == 'csv':
                                sig = get_row_signature(row)
                                st.session_state.deleted_csv_rows.add(sig)

                    st.session_state.df = st.session_state.df.drop(indices_to_drop).reset_index(drop=True)
                    st.success("선택한 차량이 삭제되었습니다.")
                    st.rerun()
                else:
                    st.warning("삭제할 차량을 선택해주세요.")
        with col_del_2:
            if st.button("전체 차량 삭제", type="primary", use_container_width=True):
                st.session_state.confirm_delete_all = True
                st.rerun()

        if st.session_state.get('confirm_delete_all', False):
            st.warning("⚠️ 정말로 모든 매물을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
            col_conf_1, col_conf_2 = st.columns(2)
            with col_conf_1:
                if st.button("✅ 예, 모두 삭제합니다", use_container_width=True):
                    st.session_state.df = pd.DataFrame(columns=DEFAULT_COLUMNS.keys())
                    st.session_state.analyzed_df = None
                    st.session_state.ai_report = None
                    st.session_state.ai_model_used = None
                    st.session_state.generating_report = False
                    st.session_state.confirm_delete_all = False
                    st.session_state.uploader_key += 1
                    st.session_state.deleted_csv_rows = set() # 전체 삭제 시 이력도 초기화
                    st.success("모든 매물이 삭제되었습니다.")
                    st.rerun()
            with col_conf_2:
                if st.button("❌ 취소", use_container_width=True):
                    st.session_state.confirm_delete_all = False
                    st.rerun()

# 읽기 전용 DataFrame 표시
st.dataframe(st.session_state.df, use_container_width=True)


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
            st.session_state.menu_index = 0 # 전체 리스트 뷰로 이동
            st.rerun()

# 분석 결과 뷰
if st.session_state.analyzed_df is not None:
    st.divider()
    st.header("📊 분석 결과")
    
    df = st.session_state.analyzed_df
    
    # 1. 전체 리스트
    if st.session_state.menu_index == 0:
        st.subheader(f"✅ 총 {len(df)}개의 매물 분석 결과")
        st.dataframe(df)

        # AI 리포트 바로가기 버튼
        if st.button("🤖 AI 엔지니어 리포트 메뉴로 이동", help="AI 분석 리포트 화면으로 이동합니다."):
            st.session_state.menu_index = 1 # 탭만 변경
            st.session_state.generating_report = False # 자동 생성 방지
            st.rerun()

    # 2. AI 리포트
    elif st.session_state.menu_index == 1:
        st.subheader("🤖 Gemini 엔지니어의 심층 리포트")
        st.warning("⚠️ AI 리포트는 학습 데이터에 기반하므로, 실제와 다른 정보나 거짓을 포함할 수 있습니다. 반드시 교차 검증하시고 주의하여 참고하십시오.")
        
        
        if st.session_state.generating_report:
            with st.spinner("엔지니어가 매물을 꼼꼼히 살펴보고 보고서를 작성 중입니다..."):
                report_text, model_name = generate_engineer_report(df, st.session_state.user_preference)
                
                st.session_state.ai_report = report_text
                st.session_state.ai_model_used = model_name
                st.session_state.generating_report = False
                st.rerun()
        
        elif st.session_state.ai_report:
            if st.session_state.ai_model_used:
                st.caption(f"💡 AI 분석 모델: **{st.session_state.ai_model_used}**")
            
            st.markdown(st.session_state.ai_report)
            st.divider()
            st.button("🔄 리포트 다시 생성", on_click=reset_generation)
            
        else:
            st.button("AI 리포트 생성하기 (Gemini)", on_click=start_generation)

    # 3. Rule-Based 추천
    elif st.session_state.menu_index == 2:
        st.subheader("가성비 최고의 추천 매물 (Tier 3)")
        st.info("단순 교환으로 감가는 되었으나 뼈대는 튼튼한 차량들입니다.")
        recommendations = df[df['Tier'] == 3].sort_values(by=['연식', '주행거리(km)'], ascending=[False, True]).head(5)
        if recommendations.empty:
            st.warning("Tier 3 (단순 교환 무사고급) 매물이 없습니다.")
        else:
            st.dataframe(recommendations[['차량명', '차량가격(만원)', '주행거리(km)', '연식', '수리내역', '특수용도이력', '분석결과']])

    # 4. Rule-Based 경고
    elif st.session_state.menu_index == 3:
        st.subheader("절대 구매 금지 (Tier 1)")
        st.error("주요 골격(프레임)이 손상된 차량입니다. 안전에 치명적일 수 있습니다.")
        warnings = df[df['Tier'] == 1].head(5)
        if warnings.empty:
            st.success("치명적인 사고 차량(Tier 1)은 발견되지 않았습니다.")
        else:
            for _, row in warnings.iterrows():
                with st.expander(f"🛑 {row['차량명']} ({row['차량가격(만원)']}만원) - 위험!", expanded=True):
                    st.write(f"**사유**: {row['분석결과']}")
                    st.write(f"**수리내역**: {row['수리내역']}")
                    st.write(f"**특수용도이력**: {row['특수용도이력']}")