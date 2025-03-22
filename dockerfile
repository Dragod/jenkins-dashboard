FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY jenkins_connector_docker_docker.py .
COPY jenkins_dashboard_core_docker.py .
COPY jenkins_dashboard_web_docker.py .

# Create necessary directories
RUN mkdir -p static templates

# Copy static files and templates
COPY static/ static/
COPY templates/ templates/

# Expose port
EXPOSE 5000

# Environment variables can be overridden at runtime
ENV JENKINS_URL=https://jenkins.example.com
ENV JENKINS_USERNAME=your_username
ENV JENKINS_API_TOKEN=your_api_token
ENV JENKINS_VERIFY_SSL=False

# Command to run the application
CMD ["python", "jenkins_dashboard_web.py"]