#!/bin/bash
# Jenkins Dashboard Environment Setup Script

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up Jenkins Dashboard environment...${NC}"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3 and try again.${NC}"
    exit 1
fi

# Create virtual environment
echo -e "${BLUE}Creating virtual environment...${NC}"
python3 -m venv venv

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip

# Install requirements
echo -e "${BLUE}Installing requirements...${NC}"
pip install -r requirements.txt

# Create directories if they don't exist
echo -e "${BLUE}Creating project directories...${NC}"
mkdir -p static templates

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${BLUE}Creating .env file...${NC}"
    cat > .env << EOL
# Jenkins Dashboard .env file
JENKINS_URL=https://jenkins.screendragon.com
JENKINS_USERNAME=your_username
JENKINS_API_TOKEN=your_api_token
EOL
    echo -e "${GREEN}Created .env file. Please edit it with your Jenkins credentials.${NC}"
else
    echo -e "${GREEN}.env file already exists.${NC}"
fi

# Create a simple .gitignore
if [ ! -f .gitignore ]; then
    echo -e "${BLUE}Creating .gitignore file...${NC}"
    cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env

# Logs
*.log

# IDE
.idea/
.vscode/
*.swp
*.swo
EOL
    echo -e "${GREEN}Created .gitignore file.${NC}"
else
    echo -e "${GREEN}.gitignore file already exists.${NC}"
fi

echo -e "${GREEN}Environment setup complete!${NC}"
echo -e "${BLUE}To activate the virtual environment, run:${NC}"
echo -e "    source venv/bin/activate"
echo ""
echo -e "${BLUE}To run the CLI dashboard:${NC}"
echo -e "    python jenkins_dashboard_cli.py"
echo ""
echo -e "${BLUE}To run the web dashboard:${NC}"
echo -e "    python jenkins_dashboard_web.py"
echo ""
echo -e "${BLUE}Don't forget to edit the .env file with your Jenkins credentials!${NC}"