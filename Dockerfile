# Use an official Python runtime as a parent image
FROM python:3.11-slim
LABEL authors="daviddhc20120601"

WORKDIR /armi

COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip
RUN pip install -e ".[test]"

RUN pip install ruamel.yaml

CMD ["armi"]
