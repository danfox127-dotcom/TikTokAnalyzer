FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
# We copy the entire root folder because the FastAPI app is inside api/
# and imports modules from sub-packages (e.g., utils.oembed, utils.psychographic)
COPY . .

# Expose port
EXPOSE 8005

# Start the FastAPI server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8005"]
