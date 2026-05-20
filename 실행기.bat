@echo off
chcp 65001 >nul
title 맞춤법 검사기 프리미엄 시스템 실행기
cls

echo ====================================================================
echo             학기말 생기부 맞춤법 검사기 프리미엄 로컬 실행기
echo ====================================================================
echo.
echo [시스템 체크] 파이썬(Python) 환경을 확인하는 중입니다...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] 시스템에 파이썬이 설치되어 있지 않거나 PATH 등록이 누락되었습니다.
    echo       파이썬(Python 3.9 이상)을 설치하신 뒤 다시 실행해 주세요.
    pause
    exit /b
)

echo [시스템 체크] 로컬 가상환경(.venv) 설정 상태를 파악하는 중입니다...
if not exist .venv (
    echo [가상환경 생성] 신규 가상환경(.venv)을 구축하는 중입니다. (약 5초 소요)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [오류] 가상환경 구축에 실패했습니다. 파이썬 권한 또는 버전을 점검해 주세요.
        pause
        exit /b
    )
)

echo [가상환경 활성화] 가상환경 세션을 진입하는 중입니다...
call .venv\Scripts\activate

echo [패키지 검사] 의존성 라이브러리(requirements.txt) 상태를 동기화하는 중입니다...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [오류] 필수 의존성 패키지 설치 중 문제가 발생했습니다. 네트워크 연결을 점검해 주세요.
    pause
    exit /b
)

echo.
echo ====================================================================
echo [알림] 준비가 완료되었습니다! 맞춤법 검사기 웹 프로그램을 가동합니다.
echo        자동으로 웹 브라우저 창이 열리며, 로컬 GUI 크롬 제어를 시작합니다.
echo ====================================================================
echo.
streamlit run app.py --server.port 8501

pause
