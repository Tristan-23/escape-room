import mysql.connector

_conn = None
PASSWORD_FILE = '/run/secrets/db-password'


def get_connection():
    global _conn
    try:
        if _conn is None or not _conn.is_connected():
            with open(PASSWORD_FILE) as f:
                pwd = f.read().strip()
            _conn = mysql.connector.connect(
                user='root',
                password=pwd,
                host='db',
                database='example',
                auth_plugin='mysql_native_password'
            )
    except mysql.connector.Error as e:
        raise RuntimeError(f"Database connection failed: {e}")
    return _conn


def get_cursor():
    return get_connection().cursor(dictionary=True)


def init_db():
    try:
        cursor = get_cursor()

        statements = [
            """CREATE TABLE IF NOT EXISTS rooms (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(100) NOT NULL,
                description TEXT NOT NULL,
                order_num   INT NOT NULL
            )""",

            """CREATE TABLE IF NOT EXISTS puzzles (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                room_id       INT NOT NULL,
                question      TEXT NOT NULL,
                answer        VARCHAR(255) NOT NULL,
                hint1         TEXT NOT NULL,
                hint2         TEXT NOT NULL,
                hint3         TEXT NOT NULL,
                reward_item   VARCHAR(100) NOT NULL,
                required_item VARCHAR(100) DEFAULT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id)
            )""",

            """CREATE TABLE IF NOT EXISTS players (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL UNIQUE,
                name       VARCHAR(100) DEFAULT 'Explorer',
                started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""",

            """CREATE TABLE IF NOT EXISTS player_progress (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                player_id  INT NOT NULL,
                room_id    INT NOT NULL,
                completed  TINYINT NOT NULL DEFAULT 0,
                attempts   INT NOT NULL DEFAULT 0,
                hints_used INT NOT NULL DEFAULT 0,
                UNIQUE KEY unique_player_room (player_id, room_id),
                FOREIGN KEY (player_id) REFERENCES players(id),
                FOREIGN KEY (room_id)   REFERENCES rooms(id)
            )""",

            """CREATE TABLE IF NOT EXISTS inventory (
                id        INT AUTO_INCREMENT PRIMARY KEY,
                player_id INT NOT NULL,
                item_name VARCHAR(100) NOT NULL,
                room_id   INT NOT NULL,
                UNIQUE KEY unique_player_item (player_id, item_name),
                FOREIGN KEY (player_id) REFERENCES players(id),
                FOREIGN KEY (room_id)   REFERENCES rooms(id)
            )""",

            """INSERT IGNORE INTO rooms (id, name, description, order_num) VALUES
                (1, 'The Library',
                 'Dust motes drift through shafts of amber light. Floor-to-ceiling shelves groan under the weight of forgotten volumes. A single reading lamp illuminates a leather-bound tome left open on the central table. The door you entered through has swung shut and locked behind you. Somewhere in this silence is the answer...',
                 1),
                (2, 'The Laboratory',
                 'The faint smell of sulfur and old copper hangs in the air. Beakers, burners, and hand-written formulae crowd every surface. A periodic table hangs on the wall, several elements circled in red ink. The previous occupant left in a hurry — their experiment is half-finished on the bench before you.',
                 2),
                (3, 'The Vault',
                 'Steel walls. A single overhead light. In the center of the room sits a heavy combination lock mounted to the vault door itself. Beside it, a note in cramped handwriting: "The mechanism responds only to one who carries the old key and knows the final sequence." The air is cold. The clock is ticking.',
                 3)""",

            """INSERT IGNORE INTO puzzles
                (id, room_id, question, answer, hint1, hint2, hint3, reward_item, required_item)
            VALUES
                (1, 1,
                 'I speak without a mouth and hear without ears. I have no body, but I come alive with the wind. A book on the shelf is titled "Echo of the Ancients" — its page number matches my name. What am I?',
                 'echo',
                 'Think about sound and repetition in nature.',
                 'What do you hear when you shout in a canyon or cave?',
                 'The title of the book on the shelf contains the answer.',
                 'Old Brass Key',
                 NULL),
                (2, 2,
                 'The formula on the blackboard reads: Element #1 in the periodic table + Element #79. The combination of their chemical symbols spells a word. What is the word?',
                 'hau',
                 'Look at the periodic table on the wall — focus on element numbers, not names.',
                 'Element 1 is H. Element 79 is Au.',
                 'H + Au = HAu. Read it aloud as one word.',
                 'Sealed Test Tube',
                 NULL),
                (3, 3,
                 'The vault needs a number. A note reads: "Double the number of atoms in water, then multiply by the atomic number of the primary metal in the key you carry." You have the Old Brass Key — brass is mostly copper, atomic number 29. Water (H2O) has 3 atoms. What is the code?',
                 '174',
                 'Break it into two steps: first calculate double the atoms in water.',
                 'Water is H2O — 2 hydrogen + 1 oxygen = 3 atoms. Double that is 6.',
                 '6 multiplied by 29 (atomic number of Copper, Cu) = 174.',
                 'Vault Certificate',
                 'Old Brass Key')"""
        ]

        for sql in statements:
            cursor.execute(sql)

        get_connection().commit()
        cursor.close()

    except mysql.connector.Error as e:
        raise RuntimeError(f"Database init failed: {e}")


# ── Room queries ──────────────────────────────────────────────────────────────

def get_room(room_id):
    try:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
        row = cursor.fetchone()
        cursor.close()
        return row
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_room failed: {e}")


def get_all_rooms():
    try:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM rooms ORDER BY order_num")
        rows = cursor.fetchall()
        cursor.close()
        return rows
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_all_rooms failed: {e}")


def get_puzzle_for_room(room_id):
    try:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM puzzles WHERE room_id = %s", (room_id,))
        row = cursor.fetchone()
        cursor.close()
        return row
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_puzzle_for_room failed: {e}")


# ── Player queries ────────────────────────────────────────────────────────────

def get_or_create_player(session_id, name='Explorer'):
    try:
        cursor = get_cursor()
        cursor.execute(
            "INSERT IGNORE INTO players (session_id, name) VALUES (%s, %s)",
            (session_id, name)
        )
        get_connection().commit()
        cursor.execute("SELECT * FROM players WHERE session_id = %s", (session_id,))
        row = cursor.fetchone()
        cursor.close()
        return row
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_or_create_player failed: {e}")


def get_player_by_id(player_id):
    try:
        cursor = get_cursor()
        cursor.execute("SELECT * FROM players WHERE id = %s", (player_id,))
        row = cursor.fetchone()
        cursor.close()
        return row
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_player_by_id failed: {e}")


# ── Progress queries ──────────────────────────────────────────────────────────

def upsert_progress(player_id, room_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            "INSERT IGNORE INTO player_progress (player_id, room_id) VALUES (%s, %s)",
            (player_id, room_id)
        )
        get_connection().commit()
        cursor.close()
    except mysql.connector.Error as e:
        raise RuntimeError(f"upsert_progress failed: {e}")


def get_progress(player_id, room_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            "SELECT * FROM player_progress WHERE player_id = %s AND room_id = %s",
            (player_id, room_id)
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return {'completed': 0, 'attempts': 0, 'hints_used': 0}
        return row
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_progress failed: {e}")


def increment_attempts(player_id, room_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            "UPDATE player_progress SET attempts = attempts + 1 WHERE player_id = %s AND room_id = %s",
            (player_id, room_id)
        )
        get_connection().commit()
        cursor.close()
    except mysql.connector.Error as e:
        raise RuntimeError(f"increment_attempts failed: {e}")


def complete_room(player_id, room_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            "UPDATE player_progress SET completed = 1 WHERE player_id = %s AND room_id = %s",
            (player_id, room_id)
        )
        get_connection().commit()
        cursor.close()
    except mysql.connector.Error as e:
        raise RuntimeError(f"complete_room failed: {e}")


def increment_hints_used(player_id, room_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            """UPDATE player_progress
               SET hints_used = LEAST(hints_used + 1, 3)
               WHERE player_id = %s AND room_id = %s""",
            (player_id, room_id)
        )
        get_connection().commit()
        cursor.close()
    except mysql.connector.Error as e:
        raise RuntimeError(f"increment_hints_used failed: {e}")


def get_total_stats(player_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            """SELECT
                COALESCE(SUM(attempts), 0)   AS total_attempts,
                COALESCE(SUM(hints_used), 0) AS total_hints,
                COALESCE(SUM(completed), 0)  AS rooms_completed
               FROM player_progress
               WHERE player_id = %s""",
            (player_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        return row or {'total_attempts': 0, 'total_hints': 0, 'rooms_completed': 0}
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_total_stats failed: {e}")


# ── Inventory queries ─────────────────────────────────────────────────────────

def get_inventory(player_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            "SELECT item_name FROM inventory WHERE player_id = %s ORDER BY id",
            (player_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        return [r['item_name'] for r in rows]
    except mysql.connector.Error as e:
        raise RuntimeError(f"get_inventory failed: {e}")


def add_inventory_item(player_id, item_name, room_id):
    try:
        cursor = get_cursor()
        cursor.execute(
            "INSERT IGNORE INTO inventory (player_id, item_name, room_id) VALUES (%s, %s, %s)",
            (player_id, item_name, room_id)
        )
        get_connection().commit()
        cursor.close()
    except mysql.connector.Error as e:
        raise RuntimeError(f"add_inventory_item failed: {e}")
