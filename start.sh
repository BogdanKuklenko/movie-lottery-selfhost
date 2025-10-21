#!/bin/bash
# Startup script for Render.com deployment
# This script runs database migrations before starting the application

echo "=========================================="
echo "Starting Movie Lottery Application"
echo "=========================================="

# Run database migrations
echo "Running database migrations..."
flask db upgrade

# Check if migrations were successful
if [ $? -eq 0 ]; then
    echo "✓ Database migrations completed successfully"
else
    echo "✗ Database migrations failed!"
    exit 1
fi

# Start the application with gunicorn
echo "Starting Gunicorn server..."
exec gunicorn -c gunicorn_config.py "movie_lottery:create_app()"

