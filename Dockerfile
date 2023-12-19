FROM python:3.12-alpine

# Set the working directory inside the container

COPY ./app/ .

# Install any needed packages specified in requirements.txt

RUN ls

RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that Uvicorn will run on
EXPOSE 8000

# Command to run the application using Uvicorn
CMD ["python3", "app.py"]

