#!/bin/bash

# Activate the virtual environment
source /home/ubuntu/myenv/bin/activate

# Navigate to the backend directory
cd /home/ubuntu/zyke-backend

# Run Gunicorn
exec gunicorn -w 5 app:app -b 127.0.0.1:5000 --timeout 1000
