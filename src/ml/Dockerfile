FROM python:3.12-slim

WORKDIR /app

COPY src/ml/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ml ./src/ml

WORKDIR /app/src/ml

CMD ["python", "src/main.py"]
