
# this file is a wrapper to run the server with uvicorn on vercel
import os
import sys
from fastapi import FastAPI
from main import app as fastapi_app


def handler(event, context):
    """
    AWS Lambda handler function to run the FastAPI application.
    """
    # Ensure the FastAPI app is ready
    if not hasattr(fastapi_app, 'state'):
        fastapi_app.state = {}

    # Run the FastAPI app with Uvicorn
    import uvicorn
    uvicorn.run(fastapi_app, host='0.0.0.0', port=8000)


if __name__ == "__main__":
    # Run the FastAPI app directly if this script is executed
    import uvicorn
    uvicorn.run(fastapi_app, host='0.0.0.0', port=8000)
