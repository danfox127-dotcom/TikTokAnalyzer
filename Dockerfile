FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
# We copy the entire root folder because the FastAPI app is inside api/
# and imports modules from sub-packages (e.g., utils.oembed, utils.psychographic)
COPY . .

# Cloud Run (and most PaaS) inject the listen port via $PORT; default to 8005
# for local `docker run` parity. EXPOSE is documentation only.
ENV PORT=8005
EXPOSE 8005

# Shell form so $PORT expands at runtime.
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
