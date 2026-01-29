FROM python:3.9-slim

WORKDIR /app

RUN pip install flask flask-cors

COPY client_db.py .

EXPOSE 5004

CMD ["python", "client_db.py"]
