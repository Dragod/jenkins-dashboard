# Docker Setup for Jenkins Dashboard

This document explains how to run the Jenkins Dashboard in a Docker container.

## Prerequisites

- Docker
- Docker Compose (optional, but recommended)

## Quick Start

### Using Docker Compose (Recommended)

1. Create a `.env` file with your Jenkins credentials:

```
JENKINS_URL=https://your-jenkins-server.com
JENKINS_USERNAME=your_username
JENKINS_API_TOKEN=your_api_token
JENKINS_VERIFY_SSL=False
```

2. Run the dashboard:

```bash
docker-compose up -d
```

This will start the Jenkins Dashboard in detached mode. You can access it at http://localhost:5000.

### Using Docker Directly

1. Build the Docker image:

```bash
docker build -t jenkins-dashboard .
```

2. Run the container:

```bash
docker run -p 5000:5000 \
  -e JENKINS_URL=https://your-jenkins-server.com \
  -e JENKINS_USERNAME=your_username \
  -e JENKINS_API_TOKEN=your_api_token \
  -e JENKINS_VERIFY_SSL=False \
  jenkins-dashboard
```

## Environment Variables

You can configure the dashboard using the following environment variables:

| Variable             | Description                        | Default                     |
| -------------------- | ---------------------------------- | --------------------------- |
| `JENKINS_URL`        | URL of your Jenkins server         | https://jenkins.example.com |
| `JENKINS_USERNAME`   | Jenkins username                   | your_username               |
| `JENKINS_API_TOKEN`  | Jenkins API token                  | your_api_token              |
| `JENKINS_VERIFY_SSL` | Whether to verify SSL certificates | False                       |

## Viewing Logs

If you're using Docker Compose, the logs are mounted to the `./logs` directory on your host.

To view logs from the container:

```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f <container_id>
```

## Updating the Dashboard

When there are updates to the dashboard code:

```bash
# Docker Compose
docker-compose down
docker-compose build
docker-compose up -d

# Docker
docker stop <container_id>
docker build -t jenkins-dashboard .
# Run the container again with the same parameters
```

## Running in Production

For a production environment, consider:

1. Using a reverse proxy like Nginx or Traefik for SSL termination
2. Setting up proper authentication
3. Configuring health checks and monitoring

Example Traefik labels for Docker Compose:

```yaml
services:
  jenkins-dashboard:
    # ... other configuration
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`dashboard.example.com`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls=true"
```

## Troubleshooting

### Container exits immediately

Check the logs for error messages:

```bash
docker logs <container_id>
```

Common issues:

- Incorrect Jenkins credentials
- Jenkins server is not reachable
- Permission issues with mounted volumes

### Dashboard shows no data

- Verify your Jenkins API token is valid and has sufficient permissions
- Check if the Jenkins URL is accessible from within the container
- Look for timeout errors in the logs
