FROM python:3.11-slim
WORKDIR /app
RUN pip install flask flask-cors boto3 pycryptodome psutil
COPY write_service.py .
EXPOSE 5001
CMD ["python", "write_service.py"]
