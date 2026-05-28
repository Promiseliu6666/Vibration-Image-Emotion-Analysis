"""
Local face matcher — compares face vectors against a synced gallery
of registered people using cosine similarity.
"""
import numpy as np


class FaceMatcher:
    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold
        self.gallery: list[dict] = []

    def update_gallery(self, items: list[dict]) -> None:
        """Replace the in-memory gallery with normalized vectors."""
        gallery = []
        for p in items:
            vec = np.array(p.get("vector", []), dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm <= 0:
                continue
            gallery.append({
                "id": p["id"],
                "name": p["name"],
                "group_id": p.get("group_id"),
                "vector": vec / norm,
            })
        self.gallery = gallery

    def match(self, face_vector: list[float]) -> dict | None:
        """Return best match {id, name, group_id, similarity} or None."""
        if not self.gallery or not face_vector:
            return None
        query = np.array(face_vector, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm <= 0:
            return None
        query = query / norm

        best = None
        best_sim = -1.0
        for p in self.gallery:
            sim = float(np.dot(query, p["vector"]))
            if sim > best_sim:
                best_sim = sim
                best = p

        print(f"[DEBUG] matcher: best_sim={best_sim:.4f} threshold={self.threshold} gallery_size={len(self.gallery)}", flush=True)
        if best is not None and best_sim >= self.threshold:
            return {
                "id": best["id"],
                "name": best["name"],
                "group_id": best["group_id"],
                "similarity": round(best_sim, 4),
            }
        return None
