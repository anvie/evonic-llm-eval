#!/usr/bin/env python3
"""Check model name from Mars endpoint"""

import requests
import json

url = "http://192.168.1.7:8080/v1/models"

try:
    response = requests.get(url, timeout=10)
    data = response.json()
    print("Response from Mars endpoint:")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
