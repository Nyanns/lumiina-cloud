FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port 7860 for Hugging Face Spaces healthcheck
EXPOSE 7860

# Run bot
CMD ["python", "bot.py"]
