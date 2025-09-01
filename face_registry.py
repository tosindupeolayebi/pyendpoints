import time
import threading
import numpy as np

# known_faces = {}   # {face_id: embedding}
# next_face_id = 1
# lock = threading.Lock()
# last_faces = {}    # {stream_id: [ { "face_id": ..., "embedding": ..., "last_seen": ... } ]}

# def get_face_id(embedding, stream_id, threshold=0.6, cache_ttl=5.0):
#     """Compare embedding to cache + registry. Return stable face_id."""
#     global next_face_id
#     now = time.time()
#     emb = np.array(embedding)

#     if stream_id not in last_faces:
#         last_faces[stream_id] = []

#     # 1. Check per-stream recent cache
#     for entry in last_faces[stream_id]:
#         dist = np.linalg.norm(emb - np.array(entry["embedding"]))
#         if dist < threshold:
#             entry["last_seen"] = now
#             return entry["face_id"]

#     # 2. Cleanup expired cache
#     last_faces[stream_id] = [e for e in last_faces[stream_id] if now - e["last_seen"] < cache_ttl]

#     # 3. Check global registry
#     with lock:
#         for fid, stored_embed in known_faces.items():
#             dist = np.linalg.norm(emb - np.array(stored_embed))
#             if dist < threshold:
#                 last_faces[stream_id].append({"face_id": fid, "embedding": emb, "last_seen": now})
#                 return fid

#         # 4. New face
#         fid = f"person_{next_face_id}"
#         next_face_id += 1
#         known_faces[fid] = emb
#         last_faces[stream_id].append({"face_id": fid, "embedding": emb, "last_seen": now})
#         return fid



known_faces = {}   # {face_id: [embeddings]}
next_face_id = 1
lock = threading.Lock()
last_faces = {}    # {stream_id: [ { "face_id": ..., "embedding": ..., "last_seen": ... } ]}

def get_face_id(embedding, stream_id, threshold=0.6, cache_ttl=5.0):
    """Compare embedding to cache + registry. Return stable face_id."""
    global next_face_id
    now = time.time()
    emb = np.array(embedding)

    if stream_id not in last_faces:
        last_faces[stream_id] = []

    # 1. Check per-stream recent cache
    for entry in last_faces[stream_id]:
        dist = np.linalg.norm(emb - np.array(entry["embedding"]))
        if dist < threshold:
            entry["last_seen"] = now
            return entry["face_id"]

    # Cleanup expired cache
    last_faces[stream_id] = [e for e in last_faces[stream_id] if now - e["last_seen"] < cache_ttl]

    # 2. Check global registry
    with lock:
        for fid, stored_embeds in known_faces.items():
            for stored_embed in stored_embeds:
                dist = np.linalg.norm(emb - np.array(stored_embed))
                if dist < threshold:
                    # Add new angle embedding if not redundant
                    known_faces[fid].append(emb)
                    last_faces[stream_id].append({"face_id": fid, "embedding": emb, "last_seen": now})
                    return fid

        # 3. New face
        fid = f"person_{next_face_id}"
        next_face_id += 1
        known_faces[fid] = [emb]  # store as list
        last_faces[stream_id].append({"face_id": fid, "embedding": emb, "last_seen": now})
        return fid
