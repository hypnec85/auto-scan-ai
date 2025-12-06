import pickle
import os
import time
import glob
import pandas as pd

def save_session_data(session_id, df, deleted_rows):
    """현재 세션의 데이터(DataFrame, 삭제 이력)를 서버의 임시 파일로 저장합니다."""
    try:
        filename = f"temp_data_{session_id}.pkl"
        data_to_save = {
            'df': df,
            'deleted_rows': deleted_rows,
            'timestamp': time.time()
        }
        with open(filename, 'wb') as f:
            pickle.dump(data_to_save, f)
        # print(f"Session data saved: {filename}") # 디버깅용
    except Exception as e:
        print(f"Error saving session data: {e}")

def load_session_data(session_id):
    """저장된 세션 데이터를 불러옵니다."""
    filename = f"temp_data_{session_id}.pkl"
    if os.path.exists(filename):
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            # print(f"Session data loaded: {filename}") # 디버깅용
            return data
        except Exception as e:
            print(f"Error loading session data: {e}")
            return None
    return None

def clear_session_data(session_id):
    """저장된 세션 파일을 삭제합니다."""
    filename = f"temp_data_{session_id}.pkl"
    if os.path.exists(filename):
        try:
            os.remove(filename)
            # print(f"Session data cleared: {filename}") # 디버깅용
        except Exception as e:
            print(f"Error clearing session data: {e}")

def cleanup_old_sessions(max_age_seconds=3600):
    """오래된(예: 1시간 이상 지난) 세션 파일을 정리합니다."""
    try:
        now = time.time()
        for filename in glob.glob("temp_data_*.pkl"):
            if os.path.getmtime(filename) < now - max_age_seconds:
                os.remove(filename)
                print(f"Old session file removed: {filename}")
    except Exception as e:
        print(f"Error cleaning up old sessions: {e}")

def load_data(file_path):
    """
    CSV 파일을 로드하고 필요한 전처리를 수행합니다.
    """
    try:
        # Streamlit uploaded_file_manager.UploadedFile 객체는 StringIO처럼 동작
        if isinstance(file_path, str):
            df = pd.read_csv(file_path)
        else: # BytesIO 또는 유사 객체
            df = pd.read_csv(file_path)
        # 수리내역 결측치는 빈 문자열로 처리
        df['수리내역'] = df['수리내역'].fillna('')
        # '옵션' 컬럼이 없는 경우 빈 문자열로 초기화
        if '옵션' not in df.columns:
            df['옵션'] = ''
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None
