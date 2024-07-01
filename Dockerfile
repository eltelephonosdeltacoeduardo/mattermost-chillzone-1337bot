FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt requirements.txt
# Install dependencies before copying the rest of the files so it can be cached
RUN pip install -r requirements.txt
#RUN python3 -m pip install pipenv
#RUN pipenv sync

COPY . .

CMD ["python", "bot.py"]
