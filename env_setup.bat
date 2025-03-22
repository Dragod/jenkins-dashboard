@echo off
REM Jenkins Dashboard Environment Setup Script for Windows

echo Setting up Jenkins Dashboard environment...

REM Check if Python 3 is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python is not installed. Please install Python 3 and try again.
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Install windows-curses for CLI dashboard
echo Installing windows-curses for CLI dashboard...
pip install windows-curses

REM Create directories if they don't exist
echo Creating project directories...
if not exist static mkdir static
if not exist templates mkdir templates

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    (
        echo # Jenkins Dashboard .env file
        echo JENKINS_URL=https://jenkins.screendragon.com
        echo JENKINS_USERNAME=your_username
        echo JENKINS_API_TOKEN=your_api_token
    ) > .env
    echo Created .env file. Please edit it with your Jenkins credentials.
) else (
    echo .env file already exists.
)

REM Create a simple .gitignore
if not exist .gitignore (
    echo Creating .gitignore file...
    (
        echo # Python
        echo __pycache__/
        echo *.py[cod]
        echo *$py.class
        echo *.so
        echo .Python
        echo venv/
        echo env/
        echo build/
        echo develop-eggs/
        echo dist/
        echo downloads/
        echo eggs/
        echo .eggs/
        echo lib/
        echo lib64/
        echo parts/
        echo sdist/
        echo var/
        echo *.egg-info/
        echo .installed.cfg
        echo *.egg
        echo.
        echo # Environment variables
        echo .env
        echo.
        echo # Logs
        echo *.log
        echo.
        echo # IDE
        echo .idea/
        echo .vscode/
        echo *.swp
        echo *.swo
    ) > .gitignore
    echo Created .gitignore file.
) else (
    echo .gitignore file already exists.
)

echo Environment setup complete!
echo.
echo To activate the virtual environment, run:
echo     venv\Scripts\activate
echo.
echo To run the CLI dashboard:
echo     python jenkins_dashboard_cli.py
echo.
echo To run the web dashboard:
echo     python jenkins_dashboard_web.py
echo.
echo Don't forget to edit the .env file with your Jenkins credentials!

REM Keep the window open
pause