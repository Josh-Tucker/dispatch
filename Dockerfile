FROM python:3.12-alpine

# Set the working directory inside the container

COPY ./dispatch/ .

COPY ./requirements.txt .

COPY ./.env .

# Install any needed packages specified in requirements.txt

RUN ls

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 init_db.py

# Expose the port that Uvicorn will run on
EXPOSE 8000

# Command to run the application using Uvicorn
CMD ["python3", "app.py"]

