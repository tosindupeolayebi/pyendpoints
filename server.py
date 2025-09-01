from fastapi import FastAPI, HTTPException
from ws_routes import register_ws_routes

app = FastAPI()

# Register WebSocket endpoints
register_ws_routes(app)