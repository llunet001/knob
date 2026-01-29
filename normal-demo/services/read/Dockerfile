FROM python:3.11-slim
WORKDIR /app
RUN pip install flask flask-cors boto3 pycryptodome
COPY read_service.py .
EXPOSE 5002
CMD ["python", "read_service.py"]
