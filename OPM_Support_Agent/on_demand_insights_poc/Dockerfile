FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Render/Fly/etc. inject PORT — must run under sh for substitution
CMD ["/bin/sh", "-c", "exec uvicorn app.main:APP --host 0.0.0.0 --port ${PORT:-8080}"]
