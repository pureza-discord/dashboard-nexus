from server.app import app
from server.config import API_HOST, API_PORT


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=API_HOST, port=API_PORT, reload=True)
