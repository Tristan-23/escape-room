import db


class Puzzle:
    """Represents a room's puzzle with answer checking and hint delivery."""

    def __init__(self, row: dict):
        self.id = row['id']
        self.room_id = row['room_id']
        self.question = row['question']
        self.answer = row['answer'].strip().lower()
        self.hints = [row['hint1'], row['hint2'], row['hint3']]
        self.reward_item = row['reward_item']
        self.required_item = row['required_item']

    def check_answer(self, player_input: str) -> bool:
        """Return True if the normalised player input matches the answer."""
        return player_input.strip().lower() == self.answer

    def get_hint(self, hint_index: int):
        """Return the hint at hint_index (0-based), or None if out of range."""
        if 0 <= hint_index < len(self.hints):
            return self.hints[hint_index]
        return None

    def has_required_item(self) -> bool:
        return self.required_item is not None


class Room:
    """Represents an escape room with its story and puzzle."""

    def __init__(self, room_row: dict, puzzle_row: dict):
        self.id = room_row['id']
        self.name = room_row['name']
        self.description = room_row['description']
        self.order_num = room_row['order_num']
        self.puzzle = Puzzle(puzzle_row)

    def is_unlocked(self, inventory: list) -> bool:
        """Return True if the player has the required item (or none is needed)."""
        if not self.puzzle.has_required_item():
            return True
        return self.puzzle.required_item in inventory

    def get_puzzle(self) -> Puzzle:
        return self.puzzle

    @staticmethod
    def load_from_db(room_id: int) -> 'Room':
        """Load a Room from the database. Raises ValueError if not found."""
        room_row = db.get_room(room_id)
        if room_row is None:
            raise ValueError(f"Room {room_id} not found")
        puzzle_row = db.get_puzzle_for_room(room_id)
        if puzzle_row is None:
            raise ValueError(f"No puzzle for room {room_id}")
        return Room(room_row, puzzle_row)


class Player:
    """Manages a player's identity, inventory and progress."""

    def __init__(self, session_id: str, name: str = 'Explorer'):
        row = db.get_or_create_player(session_id, name)
        self.id = row['id']
        self.session_id = row['session_id']
        self.name = row['name']
        self.started_at = row['started_at']

    # ── Inventory ─────────────────────────────────────────────────────────────

    def get_inventory(self) -> list:
        return db.get_inventory(self.id)

    def add_to_inventory(self, item_name: str, room_id: int) -> None:
        db.add_inventory_item(self.id, item_name, room_id)

    # ── Progress ──────────────────────────────────────────────────────────────

    def get_progress(self, room_id: int) -> dict:
        return db.get_progress(self.id, room_id)

    def record_attempt(self, room_id: int, correct: bool) -> None:
        if correct:
            db.complete_room(self.id, room_id)
        else:
            db.increment_attempts(self.id, room_id)

    def record_hint_used(self, room_id: int) -> None:
        db.increment_hints_used(self.id, room_id)

    def get_total_stats(self) -> dict:
        return db.get_total_stats(self.id)

    @staticmethod
    def from_session(flask_session) -> 'Player | None':
        """Reconstruct a Player from Flask session data. Returns None if not logged in."""
        if 'player_id' not in flask_session or 'sid' not in flask_session:
            return None
        try:
            row = db.get_player_by_id(flask_session['player_id'])
            if row is None:
                return None
            p = Player.__new__(Player)
            p.id = row['id']
            p.session_id = row['session_id']
            p.name = row['name']
            p.started_at = row['started_at']
            return p
        except RuntimeError:
            return None
