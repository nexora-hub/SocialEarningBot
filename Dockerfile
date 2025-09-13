# ─────────────────────────────────────────────────────────────────────────────
# Base Image
# ─────────────────────────────────────────────────────────────────────────────
# Use the official prebuilt image from NΞXØRΛ on Docker Hub.
# This base image is already configured with Python and essential dependencies
# needed for running the SocialEarning Bot stack. Using a base image instead of
# raw python:3.x reduces build time and ensures consistency across deployments.
FROM socialearningbot/dockerfiles:latest


# ─────────────────────────────────────────────────────────────────────────────
# Working Directory
# ─────────────────────────────────────────────────────────────────────────────
# Set the container’s working directory to "/app".
# All subsequent commands (COPY, RUN, CMD) will be executed relative to this path.
# This isolates the application’s files inside the container for easier management.
WORKDIR /app


# ─────────────────────────────────────────────────────────────────────────────
# Virtual Display Configuration
# ─────────────────────────────────────────────────────────────────────────────
# Define the DISPLAY environment variable for Xvfb (a remote desktop server).
# :99 means we are attaching Xvfb to virtual display number 99.
# Without this, GUI-based apps (like headless browsers or Tkinter UIs) would fail.
ENV DISPLAY=:99


# ─────────────────────────────────────────────────────────────────────────────
# Application Files
# ─────────────────────────────────────────────────────────────────────────────
# Copy all local project files (source code, requirements, configs) into "/app".
# This ensures the container always has the latest version of the code.
# NOTE: Use a ".dockerignore" file to avoid copying unnecessary files (e.g., cache).
COPY . .


# ─────────────────────────────────────────────────────────────────────────────
# Xpra Web Client Templates
# ─────────────────────────────────────────────────────────────────────────────
# COPY templates/xpra/ /usr/share/xpra/www/
#
# Purpose:
#   - Override Xpra’s stock HTML5/JS/CSS web client assets with custom versions.
#   - Assets live in /usr/share/xpra/www/ inside the container.
#
# Benefits:
#   • Branding → apply your own logos, colors, titles, or UI messages.
#   • Custom behavior → inject JS logic, shortcuts, or default session options.
#   • Security → disable unused features, add banners, or enforce stricter UI rules.
#
# Notes:
#   - Any file copied here **replaces** the upstream default.
#   - Keep your overrides in version control to track compatibility with future Xpra releases.
#   - After Xpra upgrades, re-check your overrides for breaking changes.
# ─────────────────────────────────────────────────────────────────────────────
COPY templates/xpra/index.html \
     templates/xpra/favicon.ico \
     templates/xpra/favicon.png \
     templates/xpra/connect.html \
     /usr/share/xpra/www/


# ─────────────────────────────────────────────────────────────────────────────
# Nginx Reverse Proxy Configuration
# ─────────────────────────────────────────────────────────────────────────────
# COPY nginx.conf /etc/nginx/nginx.conf
#
# Why?
#   - Places our **custom Nginx configuration** directly into the container,
#     overriding the default Nginx settings shipped with the base image.
#
# Benefits:
#   • Acts as a **reverse proxy**:
#       - Routes external HTTP traffic (port 80) to internal services (Flask on 8080, Xpra on 10000).
#   • Provides **security & optimization**:
#       - Can enforce HTTPS, rate limits, compression, caching, headers.
#   • Enables **port multiplexing**:
#       - Multiple services inside the container can be exposed through a single entrypoint (port 80).
#   • Easier **deployment flexibility**:
#       - We can swap or tune nginx.conf without touching the app code.
#
# NOTE:
#   - Use ".dockerignore" to avoid copying unnecessary files that may overwrite configs.
#   - Always validate nginx.conf with "nginx -t" inside the container for syntax errors.
#   - In production, consider mounting configs externally for live updates without rebuilding.
# ─────────────────────────────────────────────────────────────────────────────
COPY storage/nginx.conf /etc/nginx/nginx.conf


# ─────────────────────────────────────────────────────────────────────────────
# Networking - Exposed Ports
# ─────────────────────────────────────────────────────────────────────────────
# 5000 → Flask web server (REST API / Web UI).
# 10000 → Xpra HTML5 web client (remote GUI access inside the browser).
# Expose these so the host (or cloud provider) can map traffic into the container.
EXPOSE 8080
EXPOSE 5000
EXPOSE 10000


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint - Launch Xvfb (virtual display) + Flask
# ─────────────────────────────────────────────────────────────────────────────
# "Xvfb :99 -screen 0 1280x720x24 &"
#   → Starts Xvfb on display :99 with screen 0
#   → Resolution: 1280x720, Color depth: 24-bit
#   → Ampersand (&) backgrounds the process so the script can continue
#
# "sleep 2"
#   → Wait briefly to ensure Xvfb is fully initialized
#
# "python3 -u app.py"
#   → Starts your Flask app in unbuffered mode
#   → Playwright will detect DISPLAY=:99 and launch Chromium in headed mode
#
# NOTE:
#   - This approach runs Xvfb + Flask in the same shell
#   - Docker only manages the "sh -c ..." process, so if Flask exits,
#     Xvfb stays alive in the background until container stops
#   - For production, consider supervisord or s6-overlay to manage multiple services
# ─────────────────────────────────────────────────────────────────────────────

CMD ["sh", "-c", "service nginx start && Xvfb :99 -screen 0 1280x720x24 & sleep 2 && python3 -u app.py"]
