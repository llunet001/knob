FROM python:3.11-slim
WORKDIR /app
COPY reencrypt_service.py .
RUN pip install flask flask-cors boto3 pycryptodome psutil
EXPOSE 5003
CMD ["python", "reencrypt_service.py"]
