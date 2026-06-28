FROM python:3.11-slim

WORKDIR /edge

RUN pip install --no-cache-dir httpx pymodbus==3.6.3

COPY edge/agent.py .

CMD ["python", "agent.py"]
