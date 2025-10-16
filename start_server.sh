#!/bin/bash
# Startup script for gunicorn with extended timeout for vesting deployments

exec gunicorn --config gunicorn_config.py main:app
