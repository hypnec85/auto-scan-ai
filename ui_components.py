import streamlit as st
import pandas as pd
import os
import numpy as np
import altair as alt
from sklearn.linear_model import LinearRegression
from storage import load_data, clear_session_data
from ai_service import generate_engineer_report
from domain_logic import get_row_signature

def render_sidebar(load_csv_file_callback, DEFAULT_COLUMNS, DEFAULT_DATA, auto_save):
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
                        auto_save() # 자동 저장
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
            menu_options = ["📊 전체 리스트", "🤖 AI 엔지니어 리포트", "🏆 Rule-Based 추천", "🚨 Rule-Based 경고", "📈 심층 가격 분석"]
            
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
            
            clear_session_data(st.session_state.session_id) # 세션 파일도 삭제
            
            st.rerun()
        
        with st.expander("Tier 시스템 가이드 보기"):
            st.info("Tier 시스템 가이드")
            st.markdown("""
            - **Tier 1 (구매 금지)**: 휠하우스, 사이드멤버 등 주요 골격 손상.
            - **Tier 2 (경고)**: 리어패널, 인사이드패널 등 2차 골격 손상.
            - **Tier 3 (추천)**: 휀더, 도어 등 단순 외판 교환.
            """)

def render_add_car_form(add_car_callback):
    with st.expander("➕ 신규 매물 직접 추가하기 (Form 입력)", expanded=st.session_state.form_expanded):
        st.info("아래 양식을 작성하여 리스트에 매물을 추가하세요.")
        
        # 성공 메시지가 있으면 표시하고 삭제
        if 'add_success_msg' in st.session_state:
            st.success(st.session_state['add_success_msg'])
            del st.session_state['add_success_msg']

        with st.form("add_car_form", clear_on_submit=False):
            # 1행
            r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)
            with r1_col1:
                new_name = st.text_input("차량명", placeholder="예: 아반떼 (CN7)", key="add_name")
            with r1_col2:
                new_engine = st.text_input("엔진", placeholder="예: 가솔린 1.6", key="add_engine")
            with r1_col3:
                new_trim = st.text_input("트림", placeholder="예: 인스퍼레이션", key="add_trim")
            with r1_col4:
                new_color = st.text_input("색상", placeholder="예: 흰색", key="add_color")
            
            # 2행
            r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)
            with r2_col1:
                new_price = st.number_input("차량가격(만원)", min_value=0, step=10, key="add_price")
            with r2_col2:
                new_year = st.number_input("연식", min_value=1900, max_value=2100, step=1, key="add_year")
            with r2_col3:
                new_km = st.number_input("주행거리(km)", min_value=0, step=1000, key="add_km")
            with r2_col4:
                new_reg_date = st.date_input("최초 등록일", key="add_reg_date")

            # 3행
            r3_col1, r3_col2, r3_col3, r3_col4 = st.columns(4)
            with r3_col1:
                new_special = st.selectbox("특수용도이력", ["X", "O"], key="add_special")
            with r3_col2:
                new_one_owner = st.selectbox("1인소유", ["O", "X"], key="add_one_owner")
            with r3_col3:
                new_my_damage_cnt = st.number_input("내차피해횟수", min_value=0, step=1, key="add_my_damage_cnt")
            with r3_col4:
                new_other_damage_cnt = st.number_input("상대차피해횟수", min_value=0, step=1, key="add_other_damage_cnt")
            
            # 4행 (보증기간)
            
            r4_col1, r4_col2, r4_col3, r4_col4 = st.columns(4)
            with r4_col1:
                st.number_input("일반부품 보증(개월)", min_value=0, step=1, key="add_war_gen_mon")
            with r4_col2:
                st.number_input("일반부품 보증(km)", min_value=0, step=1000, key="add_war_gen_km")
            with r4_col3:
                st.number_input("주요부품 보증(개월)", min_value=0, step=1, key="add_war_maj_mon")
            with r4_col4:
                st.number_input("주요부품 보증(km)", min_value=0, step=1000, key="add_war_maj_km")

            # 나머지 행
            new_my_damage_amt = st.number_input("내차피해액(원)", min_value=0, step=10000, key="add_my_damage_amt")
            new_repair = st.text_area("수리내역 (중요)", placeholder="성능점검기록부의 수리내역을 입력하세요. (예: 후드 교환, 프론트휀더(우) 판금)", key="add_repair")
            new_option = st.text_area("옵션", placeholder="옵션 내용을 자유롭게 입력하세요. (예: 10.25인치 UVO 내비게이션 93만원, 파노라마 선루프 118만원)", key="add_option")

            st.form_submit_button("매물 리스트에 추가", on_click=add_car_callback)

def render_edit_car_form(auto_save):
    with st.expander("✏️ 매물 정보 수정하기"):
        # 수정할 차량 선택
        edit_options = [f"{i} : {row['차량명']} ({row['차량가격(만원)']}만원)" for i, row in st.session_state.df.iterrows()]
        selected_to_edit_str = st.selectbox("수정할 차량을 선택하세요:", edit_options)
        
        if selected_to_edit_str:
            selected_idx = int(selected_to_edit_str.split(" :")[0])
            selected_row = st.session_state.df.iloc[selected_idx]
            
            with st.form("edit_car_form"):
                st.caption(f"선택된 차량: **{selected_row['차량명']}** (Index: {selected_idx})")
                
                # 1행
                er1_col1, er1_col2, er1_col3, er1_col4 = st.columns(4)
                with er1_col1:
                    edit_name = st.text_input("차량명", value=selected_row['차량명'])
                with er1_col2:
                    edit_engine = st.text_input("엔진", value=selected_row['엔진'])
                with er1_col3:
                    edit_trim = st.text_input("트림", value=selected_row['트림'])
                with er1_col4:
                    edit_color = st.text_input("색상", value=selected_row['색상'])
                
                # 2행
                er2_col1, er2_col2, er2_col3, er2_col4 = st.columns(4)
                with er2_col1:
                    edit_price = st.number_input("차량가격(만원)", min_value=0, step=10, value=int(selected_row['차량가격(만원)']))
                with er2_col2:
                    edit_year = st.number_input("연식", min_value=1900, max_value=2100, step=1, value=int(selected_row['연식']))
                with er2_col3:
                    edit_km = st.number_input("주행거리(km)", min_value=0, step=1000, value=int(selected_row['주행거리(km)']))
                with er2_col4:
                    # 날짜 처리: 문자열이거나 Timestamp일 수 있음
                    try:
                        default_date = pd.to_datetime(selected_row['최초 등록일']).date()
                    except:
                        default_date = None
                    edit_reg_date = st.date_input("최초 등록일", value=default_date)

                # 3행
                er3_col1, er3_col2, er3_col3, er3_col4 = st.columns(4)
                with er3_col1:
                    special_idx = 0 if selected_row['특수용도이력'] == "X" else 1
                    edit_special = st.selectbox("특수용도이력", ["X", "O"], index=special_idx)
                with er3_col2:
                    owner_idx = 0 if selected_row['1인소유'] == "O" else 1
                    edit_one_owner = st.selectbox("1인소유", ["O", "X"], index=owner_idx)
                with er3_col3:
                    edit_my_damage_cnt = st.number_input("내차피해횟수", min_value=0, step=1, value=int(selected_row['내차피해횟수']))
                with er3_col4:
                    edit_other_damage_cnt = st.number_input("상대차피해횟수", min_value=0, step=1, value=int(selected_row['상대차피해횟수']))
                
                # 4행 (보증기간)
                st.caption("🛡️ 보증 정보 수정")
                er4_col1, er4_col2, er4_col3, er4_col4 = st.columns(4)
                with er4_col1:
                    edit_war_gen_mon = st.number_input("일반부품 보증(개월)", min_value=0, step=1, value=int(selected_row.get('일반부품보증기간(개월)', 36)))
                with er4_col2:
                    edit_war_gen_km = st.number_input("일반부품 보증(km)", min_value=0, step=1000, value=int(selected_row.get('일반부품보증거리(km)', 60000)))
                with er4_col3:
                    edit_war_maj_mon = st.number_input("주요부품 보증(개월)", min_value=0, step=1, value=int(selected_row.get('주요부품보증기간(개월)', 60)))
                with er4_col4:
                    edit_war_maj_km = st.number_input("주요부품 보증(km)", min_value=0, step=1000, value=int(selected_row.get('주요부품보증거리(km)', 100000)))

                # 나머지 행
                edit_my_damage_amt = st.number_input("내차피해액(원)", min_value=0, step=10000, value=int(selected_row['내차피해액']))
                edit_repair = st.text_area("수리내역 (중요)", value=selected_row['수리내역'])
                edit_option = st.text_area("옵션", value=selected_row['옵션'])

                if st.form_submit_button("수정 내용 저장"):
                    # 데이터 업데이트
                    st.session_state.df.at[selected_idx, '차량명'] = edit_name
                    st.session_state.df.at[selected_idx, '엔진'] = edit_engine
                    st.session_state.df.at[selected_idx, '트림'] = edit_trim
                    st.session_state.df.at[selected_idx, '색상'] = edit_color
                    st.session_state.df.at[selected_idx, '차량가격(만원)'] = edit_price
                    st.session_state.df.at[selected_idx, '연식'] = edit_year
                    st.session_state.df.at[selected_idx, '주행거리(km)'] = edit_km
                    st.session_state.df.at[selected_idx, '최초 등록일'] = str(edit_reg_date)
                    st.session_state.df.at[selected_idx, '특수용도이력'] = edit_special
                    st.session_state.df.at[selected_idx, '1인소유'] = edit_one_owner
                    st.session_state.df.at[selected_idx, '내차피해횟수'] = edit_my_damage_cnt
                    st.session_state.df.at[selected_idx, '상대차피해횟수'] = edit_other_damage_cnt
                    st.session_state.df.at[selected_idx, '내차피해액'] = edit_my_damage_amt
                    st.session_state.df.at[selected_idx, '일반부품보증기간(개월)'] = edit_war_gen_mon
                    st.session_state.df.at[selected_idx, '일반부품보증거리(km)'] = edit_war_gen_km
                    st.session_state.df.at[selected_idx, '주요부품보증기간(개월)'] = edit_war_maj_mon
                    st.session_state.df.at[selected_idx, '주요부품보증거리(km)'] = edit_war_maj_km
                    st.session_state.df.at[selected_idx, '수리내역'] = edit_repair
                    st.session_state.df.at[selected_idx, '옵션'] = edit_option
                    st.session_state.df.at[selected_idx, '_source'] = 'manual' # 수정되면 수기 데이터로 간주

                    st.session_state.analyzed_df = None # 데이터 변경 시 분석 결과 초기화
                    auto_save()
                    st.success(f"'{edit_name}' 정보가 수정되었습니다.")
                    st.rerun()

def render_delete_car_form(auto_save):
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
                    
                    auto_save() # 자동 저장
                    
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
                    
                    clear_session_data(st.session_state.session_id) # 세션 파일 삭제
                    
                    st.success("모든 매물이 삭제되었습니다.")
                    st.rerun()
            with col_conf_2:
                if st.button("❌ 취소", use_container_width=True):
                    st.session_state.confirm_delete_all = False
                    st.rerun()

def render_analysis_results(start_generation, reset_generation):
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

    # 5. 심층 가격 분석 (Deep Price Analysis)
    elif st.session_state.menu_index == 4:
        st.subheader("📈 심층 가격 분석 (다변량 회귀)")
        st.info("연식, 주행거리, 사고 여부가 가격에 미치는 영향을 분석하여 '진짜 가성비'를 찾습니다.")

        # 1. 차종 선택
        unique_models = df['차량명'].unique()
        selected_model = st.selectbox("분석할 차종을 선택하세요", unique_models)

        # 데이터 필터링
        model_df = df[df['차량명'] == selected_model].copy()

        # 최소 샘플 확인
        if len(model_df) < 10:
            st.error(f"데이터 부족: '{selected_model}'의 매물이 {len(model_df)}개뿐입니다. 정밀 분석을 위해 최소 10개 이상의 데이터가 필요합니다.")
        else:
            # 2. 데이터 전처리 (사고 여부 변수 생성)
            major_accident_keywords = [
                '휠하우스', '인사이드패널', '사이드멤버', '플로어패널', '대쉬패널', '필러', 
                '루프패널', '트렁크플로어', '백판넬', '리어패널', '프런트패널', '리어액슬', 
                '쿼터패널', '패널 앗세이'
            ]
            
            def check_major_accident(repair_history):
                for keyword in major_accident_keywords:
                    if keyword in str(repair_history):
                        return 1
                return 0

            model_df['Is_Major_Accident'] = model_df['수리내역'].apply(check_major_accident)
            
            # 회귀 분석 준비
            X = model_df[['연식', '주행거리(km)', 'Is_Major_Accident']]
            y = model_df['차량가격(만원)']
            
            # 3. 다중 회귀분석 수행
            reg = LinearRegression()
            reg.fit(X, y)
            
            # 계수 추출
            coef_year = reg.coef_[0]
            coef_mileage = reg.coef_[1]
            coef_accident = reg.coef_[2]
            
            # 4. 시장 가치 지표 출력
            m1, m2, m3 = st.columns(3)
            m1.metric("📅 1년의 가치", f"{coef_year:.1f}만원", delta_color="normal")
            m2.metric("🚗 주행의 대가 (1만km)", f"{coef_mileage * 10000:.1f}만원", delta_color="inverse")
            m3.metric("💥 사고의 감가", f"{coef_accident:.1f}만원", delta_color="inverse")
            
            # 5. 시각화 (Altair)
            # 적정가 예측
            model_df['예측가격'] = reg.predict(X)
            model_df['가격차이'] = model_df['차량가격(만원)'] - model_df['예측가격']
            
            # 차트 생성
            chart = alt.Chart(model_df).mark_point(filled=True, size=100).encode(
                x=alt.X('주행거리(km)', title='주행거리 (km)'),
                y=alt.Y('차량가격(만원)', title='가격 (만원)'),
                color=alt.Color('연식', scale=alt.Scale(scheme='viridis'), title='연식'),
                shape=alt.Shape('Is_Major_Accident:N', title='사고 여부', legend=alt.Legend(labelExpr="datum.value == 0 ? '무사고' : '사고'")),
                tooltip=['차량명', '차량가격(만원)', '연식', '주행거리(km)', '수리내역', '가격차이']
            ).interactive()
            
            # 적정가 추세선 (무사고 기준)
            clean_df = model_df[model_df['Is_Major_Accident'] == 0]
            if len(clean_df) > 1:
                # Simple regression for the line: Price ~ Mileage
                reg_clean = LinearRegression()
                reg_clean.fit(clean_df[['주행거리(km)']], clean_df['차량가격(만원)'])
                
                # Line data generation
                x_min = model_df['주행거리(km)'].min()
                x_max = model_df['주행거리(km)'].max()
                # 구간을 잘게 쪼개서 툴팁이 선 위 어디서든 잘 뜨게 함
                x_range = np.linspace(x_min, x_max, 20)
                line_data = pd.DataFrame({'주행거리(km)': x_range})
                line_data['차량가격(만원)'] = reg_clean.predict(line_data[['주행거리(km)']])
                line_data['정보'] = "무사고 기준 적정 시세"
                
                line_chart = alt.Chart(line_data).mark_line(color='red', strokeDash=[5, 5], size=3).encode(
                    x='주행거리(km)',
                    y='차량가격(만원)',
                    tooltip=['정보', alt.Tooltip('차량가격(만원)', format=',.0f')]
                )
                
                st.altair_chart(chart + line_chart, use_container_width=True)
            else:
                st.altair_chart(chart, use_container_width=True)
                st.warning("무사고 차량 데이터가 부족하여 적정 시세선을 그릴 수 없습니다.")

            # 6. 저평가 매물 하이라이트 (적정가보다 실제가가 50만원 이상 낮은 경우)
            # 가격차이 = 실제가 - 예측가 < -50
            good_deals = model_df[model_df['가격차이'] < -50].sort_values(by='가격차이')
            
            st.subheader("💎 발견된 가성비 매물 (Good Deal)")
            if not good_deals.empty:
                st.dataframe(good_deals[['차량명', '차량가격(만원)', '예측가격', '가격차이', '연식', '주행거리(km)', '수리내역']].style.format("{:.1f}", subset=['예측가격', '가격차이']))
            else:
                st.info("현재 기준 현저하게 저평가된 매물이 없습니다.")
