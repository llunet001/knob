FROM python:3.11-slim
WORKDIR /app
COPY read_service.py .
RUN pip install flask flask-cors boto3 pycryptodome
EXPOSE 5002
CMD ["python", "read_service.py"]
