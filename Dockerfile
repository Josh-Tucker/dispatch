FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (none needed - using Python entrypoint)

# Copy application files
COPY ./dispatch/ .

# Copy requirements file
COPY ./requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Make entrypoint script executable
RUN chmod +x entrypoint.py

# Create data directory
RUN mkdir -p data

# Set entrypoint to run migrations before starting app
ENTRYPOINT ["python3", "-u", "entrypoint.py"]

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

