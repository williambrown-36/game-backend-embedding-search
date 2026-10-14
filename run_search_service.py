"""Run the game document search API locally."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("game_backend_search.search_service:app", host="127.0.0.1", port=8000)
