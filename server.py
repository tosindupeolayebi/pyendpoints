from fastapi import FastAPI, HTTPException
from ws_routes import register_ws_routes

app = FastAPI()

# Register WebSocket endpoints
register_ws_routes(app)



# from fastapi import FastAPI

# app = FastAPI()

# # ✅ Root route
# @app.get("/")
# def read_root():
#     return {"message": "Hello, FastAPI is running 🎉"}



# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from typing import List

# app = FastAPI(
#     title="My API",
#     description="Endpoints wired with FastAPI",
#     version="1.0.0"
# )

# # -----------------------------
# # Example request/response models
# # -----------------------------
# class Item(BaseModel):
#     id: int
#     name: str
#     price: float

# # In-memory "database"
# items_db: List[Item] = []


# # -----------------------------
# # Endpoints
# # -----------------------------

# # Create an item
# @app.post("/items", response_model=Item)
# def create_item(item: Item):
#     items_db.append(item)
#     return item

# # Get all items
# @app.get("/items", response_model=List[Item])
# def get_items():
#     return items_db

# # Get single item
# @app.get("/items/{item_id}", response_model=Item)
# def get_item(item_id: int):
#     for item in items_db:
#         if item.id == item_id:
#             return item
#     raise HTTPException(status_code=404, detail="Item not found")

# # Update item
# @app.put("/items/{item_id}", response_model=Item)
# def update_item(item_id: int, updated_item: Item):
#     for idx, item in enumerate(items_db):
#         if item.id == item_id:
#             items_db[idx] = updated_item
#             return updated_item
#     raise HTTPException(status_code=404, detail="Item not found")

# # Delete item
# @app.delete("/items/{item_id}")
# def delete_item(item_id: int):
#     for idx, item in enumerate(items_db):
#         if item.id == item_id:
#             del items_db[idx]
#             return {"message": f"Item {item_id} deleted"}
#     raise HTTPException(status_code=404, detail="Item not found")
