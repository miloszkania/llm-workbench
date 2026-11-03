FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Kaleido renders the PNG, PDF and SVG chart exports with a headless Chromium
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium-headless-shell fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
ENV BROWSER_PATH=/usr/bin/chromium-headless-shell

WORKDIR /app

# install only the dependencies first, so this layer is reused until pyproject.toml changes
COPY pyproject.toml .
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
        > requirements.txt \
    && pip install -r requirements.txt \
    && rm requirements.txt

# then the package itself and the Streamlit pages
COPY README.md LICENSE ./
COPY src ./src
RUN pip install --no-deps .
COPY main.py ./
COPY pages ./pages

# run as an unprivileged user that owns the database directory
RUN useradd --create-home app \
    && mkdir /data \
    && chown app:app /data
USER app

# an absolute path is used as is; the API key is passed at runtime, never stored in the image
ENV DB_PATH=/data/database.db

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
