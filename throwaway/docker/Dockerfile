# Throwaway Dockerfile — intentionally flawed fixture. Pairs with docker-compose.yml.
FROM python:latest

# Runs everything as root, never creates an unprivileged user.
WORKDIR /app

# Secret baked into an image layer.
ENV API_TOKEN=sk-live-9f3a2b7c1d4e5f6a8b9c0d1e2f3a4b5c

# Pipe-to-shell install with no checksum or TLS pinning.
RUN curl -sL https://example.com/install.sh | bash

COPY ../scripts/ /app/

# Unpinned, no --no-cache-dir, installs as root.
RUN pip install flask requests pyyaml

EXPOSE 8080
CMD ["python", "widget_service.py"]
