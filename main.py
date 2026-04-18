from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import random
from typing import Optional

app = FastAPI(title="Snake Game API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Game Constants ─────────────────────────────────────────────────────────────
GRID_W = 20
GRID_H = 20

DIRECTIONS = {
    "UP":    (0, -1),
    "DOWN":  (0,  1),
    "LEFT":  (-1, 0),
    "RIGHT": (1,  0),
}

OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}

# ── In-memory game state ───────────────────────────────────────────────────────
game_state: dict = {}


def _spawn_food(snake: list[list[int]]) -> list[int]:
    occupied = {(s[0], s[1]) for s in snake}
    free = [(x, y) for x in range(GRID_W) for y in range(GRID_H)
            if (x, y) not in occupied]
    if not free:
        return [-1, -1]
    pos = random.choice(free)
    return list(pos)


def _fresh_state() -> dict:
    start = [GRID_W // 2, GRID_H // 2]
    snake = [start, [start[0] - 1, start[1]], [start[0] - 2, start[1]]]
    food = _spawn_food(snake)
    return {
        "snake":     snake,
        "direction": "RIGHT",
        "food":      food,
        "score":     0,
        "status":    "running",   # running | paused | game_over
        "event":     None,        # "ate" | "collision" | None
        "grid_w":    GRID_W,
        "grid_h":    GRID_H,
    }


# ── Models ─────────────────────────────────────────────────────────────────────
class DirectionRequest(BaseModel):
    direction: str


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/api/game/start")
def start_game():
    """Start or restart a game session."""
    global game_state
    game_state = _fresh_state()
    return game_state


@app.get("/api/game/state")
def get_state():
    """Return current game state."""
    if not game_state:
        raise HTTPException(404, "No active game. POST /api/game/start first.")
    return game_state


@app.post("/api/game/direction")
def set_direction(req: DirectionRequest):
    """Change the snake's direction (ignored if opposite or game over)."""
    if not game_state:
        raise HTTPException(404, "No active game.")
    if game_state["status"] != "running":
        return game_state
    d = req.direction.upper()
    if d not in DIRECTIONS:
        raise HTTPException(400, f"Invalid direction '{d}'.")
    if d != OPPOSITE.get(game_state["direction"]):
        game_state["direction"] = d
    return game_state


@app.post("/api/game/tick")
def tick():
    """Advance the snake by one step and return new state."""
    if not game_state:
        raise HTTPException(404, "No active game.")
    if game_state["status"] != "running":
        return game_state

    gs = game_state
    dx, dy = DIRECTIONS[gs["direction"]]
    head = gs["snake"][0]
    new_head = [head[0] + dx, head[1] + dy]

    # ── Wall collision ─────────────────────────────────────────────────────
    if not (0 <= new_head[0] < GRID_W and 0 <= new_head[1] < GRID_H):
        gs["status"] = "game_over"
        gs["event"] = "collision"
        return gs

    # ── Self collision ─────────────────────────────────────────────────────
    if new_head in gs["snake"]:
        gs["status"] = "game_over"
        gs["event"] = "collision"
        return gs

    gs["snake"].insert(0, new_head)

    # ── Food check ────────────────────────────────────────────────────────
    if new_head == gs["food"]:
        gs["score"] += 10
        gs["food"] = _spawn_food(gs["snake"])
        gs["event"] = "ate"
    else:
        gs["snake"].pop()
        gs["event"] = None

    return gs


@app.post("/api/game/pause")
def pause_game():
    """Toggle pause/resume."""
    if not game_state:
        raise HTTPException(404, "No active game.")
    if game_state["status"] == "running":
        game_state["status"] = "paused"
    elif game_state["status"] == "paused":
        game_state["status"] = "running"
    return game_state


@app.get("/api/game/highscore")
def highscore():
    """Simple in-memory high score."""
    return {"highscore": getattr(app.state, "highscore", 0)}


@app.post("/api/game/highscore")
def update_highscore():
    """Update high score if current score is greater."""
    score = game_state.get("score", 0)
    current_best = getattr(app.state, "highscore", 0)
    if score > current_best:
        app.state.highscore = score
    return {"highscore": app.state.highscore}


# ── Serve frontend ─────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")
