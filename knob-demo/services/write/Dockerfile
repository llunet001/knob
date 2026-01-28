FROM python:3.11-slim
WORKDIR /app
COPY write_service.py .
RUN pip install flask flask-cors boto3 pycryptodome psutil
EXPOSE 5001
CMD ["python", "write_service.py"]
