FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    cmake \
    git \
    libsnap7-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5020 102 8102

CMD ["python", "-u", "src/main.py"]