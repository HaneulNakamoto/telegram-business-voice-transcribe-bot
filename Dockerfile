# Use an official Python runtime as a parent image
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libglib2.0-0 \
    tesseract-ocr \
    libgl1-mesa-glx && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run photobot.py when the container launches
CMD ["python", "./photobot.py"]