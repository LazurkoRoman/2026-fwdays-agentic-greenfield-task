#!/usr/bin/env python3
"""Production WSGI entry point for the STEP tree comparison web app."""

import os

from waitress import serve

from app import app


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "5000"))
    threads = int(os.environ.get("APP_THREADS", "4"))
    serve(app, host=host, port=port, threads=threads)
