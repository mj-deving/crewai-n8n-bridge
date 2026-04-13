FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    crewai==1.14.1 \
    'crewai[tools]==1.14.1' \
    fastapi==0.135.3 \
    uvicorn==0.44.0 \
    httpx

# Copy application code
COPY app/ /app/app/
COPY research_crew/src/ /app/research_crew/src/
COPY sales_crew/src/ /app/sales_crew/src/
COPY content_crew/src/ /app/content_crew/src/
COPY strategy_crew/src/ /app/strategy_crew/src/
COPY flows/ /app/flows/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
