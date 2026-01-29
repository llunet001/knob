FROM python:3.11-slim
WORKDIR /app
RUN pip install flask flask-cors boto3 pycryptodome psutil
COPY reencrypt_service.py .
EXPOSE 5003
CMD ["python", "reencrypt_service.py"]
