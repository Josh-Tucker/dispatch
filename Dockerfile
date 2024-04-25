FROM python:3.12-alpine

# Set the working directory inside the container

COPY ./dispatch/ .

COPY ./requirements.txt .

# Install any needed packages specified in requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Command to run the application using Uvicorn
# ENTRYPOINT ["python3"]

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

