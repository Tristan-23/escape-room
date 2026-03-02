import os
import uuid
from flask import (
    Flask, render_template, request, session,
    redirect, url_for, flash, jsonify, abort
)
import db
from game import Room, Player

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.before_first_request
def startup():
    db.init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_player():
    """Return current Player from session or None."""
    return Player.from_session(session)


def require_player():
    """Return Player or redirect to home if not in session."""
    player = get_player()
    if player is None:
        flash('Please start a new game first.', 'warning')
        return None, redirect(url_for('home'))
    return player, None


def determine_ending(stats: dict) -> str:
    wrong = int(stats['total_attempts'])
    hints = int(stats['total_hints'])
    if wrong <= 3 and hints <= 1:
        return 'legendary'
    elif wrong <= 8 and hints <= 5:
        return 'skilled'
    else:
        return 'survivor'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    has_session = 'player_id' in session
    return render_template('home.html', has_session=has_session)


@app.route('/start', methods=['POST'])
def start():
    try:
        name = request.form.get('player_name', 'Explorer').strip() or 'Explorer'
        sid = str(uuid.uuid4())
        player = Player(session_id=sid, name=name)
        session.clear()
        session['sid'] = sid
        session['player_id'] = player.id
        session['player_name'] = player.name
        return redirect(url_for('room_view', room_id=1))
    except Exception as e:
        app.logger.error(f"Start error: {e}")
        flash('Could not start the game. Please try again.', 'danger')
        return redirect(url_for('home'))


@app.route('/room/<int:room_id>')
def room_view(room_id):
    try:
        player, redir = require_player()
        if redir:
            return redir

        room = Room.load_from_db(room_id)
        inventory = player.get_inventory()

        # Enforce room order — cannot skip ahead
        if room.order_num > 1:
            prev_progress = player.get_progress(room.order_num - 1)
            if not prev_progress['completed']:
                flash('You must complete the previous room first!', 'warning')
                return redirect(url_for('room_view', room_id=room_id - 1))

        # Check inventory gate
        if not room.is_unlocked(inventory):
            flash(f'You need the "{room.puzzle.required_item}" to enter this room.', 'warning')
            return redirect(url_for('room_view', room_id=room_id - 1))

        db.upsert_progress(player.id, room_id)
        progress = player.get_progress(room_id)

        # If already completed, move on
        if progress['completed']:
            next_room = db.get_room(room_id + 1)
            if next_room:
                return redirect(url_for('room_view', room_id=room_id + 1))
            else:
                return redirect(url_for('win'))

        hints_used = int(progress['hints_used'])
        revealed_hints = room.puzzle.hints[:hints_used]
        all_rooms = db.get_all_rooms()

        # Build completed set for sidebar
        completed_ids = set()
        for r in all_rooms:
            p = player.get_progress(r['id'])
            if p['completed']:
                completed_ids.add(r['id'])

        return render_template(
            'room.html',
            room=room,
            puzzle=room.get_puzzle(),
            progress=progress,
            inventory=inventory,
            revealed_hints=revealed_hints,
            can_get_hint=hints_used < 3,
            all_rooms=all_rooms,
            completed_ids=completed_ids,
        )

    except ValueError:
        abort(404)
    except Exception as e:
        app.logger.error(f"Room view error: {e}")
        abort(500)


@app.route('/room/<int:room_id>/solve', methods=['POST'])
def solve(room_id):
    try:
        player, redir = require_player()
        if redir:
            return redir

        room = Room.load_from_db(room_id)
        player_answer = request.form.get('answer', '')
        correct = room.puzzle.check_answer(player_answer)

        db.upsert_progress(player.id, room_id)
        player.record_attempt(room_id, correct)

        session['last_result'] = 'correct' if correct else 'wrong'
        session['last_room'] = room_id
        session['last_room_name'] = room.name

        if correct:
            player.add_to_inventory(room.puzzle.reward_item, room_id)
            session['reward_item'] = room.puzzle.reward_item
            session['room_attempts'] = int(db.get_progress(player.id, room_id)['attempts'])
            # Check if there's a next room
            next_room = db.get_room(room_id + 1)
            session['has_next'] = next_room is not None
            session['next_room_id'] = room_id + 1 if next_room else None
        else:
            session.pop('reward_item', None)
            session['wrong_answer'] = player_answer

        return redirect(url_for('feedback'))

    except ValueError:
        abort(404)
    except Exception as e:
        app.logger.error(f"Solve error: {e}")
        abort(500)


@app.route('/room/<int:room_id>/hint')
def hint(room_id):
    try:
        player, redir = require_player()
        if redir:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Not logged in'}), 403
            return redir

        db.upsert_progress(player.id, room_id)
        progress = player.get_progress(room_id)
        hints_used = int(progress['hints_used'])

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if hints_used >= 3:
            if is_ajax:
                return jsonify({'error': 'No more hints available', 'hint': None})
            flash('No more hints available for this puzzle.', 'warning')
            return redirect(url_for('room_view', room_id=room_id))

        room = Room.load_from_db(room_id)
        hint_text = room.puzzle.get_hint(hints_used)
        player.record_hint_used(room_id)

        if is_ajax:
            return jsonify({
                'hint': hint_text,
                'hints_used': hints_used + 1,
                'max_hints': 3,
            })

        return redirect(url_for('room_view', room_id=room_id))

    except ValueError:
        abort(404)
    except Exception as e:
        app.logger.error(f"Hint error: {e}")
        abort(500)


@app.route('/feedback')
def feedback():
    result = session.get('last_result')
    if not result:
        return redirect(url_for('home'))

    return render_template(
        'feedback.html',
        result=result,
        room_name=session.get('last_room_name', 'Unknown Room'),
        room_id=session.get('last_room'),
        reward_item=session.get('reward_item'),
        has_next=session.get('has_next', False),
        next_room_id=session.get('next_room_id'),
        wrong_answer=session.get('wrong_answer', ''),
        room_attempts=session.get('room_attempts', 0),
    )


@app.route('/win')
def win():
    try:
        player, redir = require_player()
        if redir:
            return redir

        stats = player.get_total_stats()
        rooms_done = int(stats['rooms_completed'])

        # Guard: redirect to last incomplete room if not actually finished
        if rooms_done < 3:
            all_rooms = db.get_all_rooms()
            for r in all_rooms:
                p = player.get_progress(r['id'])
                if not p['completed']:
                    flash('You must complete all rooms first!', 'warning')
                    return redirect(url_for('room_view', room_id=r['id']))

        ending = determine_ending(stats)
        all_rooms = db.get_all_rooms()
        progress_map = {}
        for r in all_rooms:
            progress_map[r['id']] = player.get_progress(r['id'])

        return render_template(
            'win.html',
            player_name=player.name,
            stats=stats,
            ending=ending,
            all_rooms=all_rooms,
            progress_map=progress_map,
        )

    except Exception as e:
        app.logger.error(f"Win error: {e}")
        abort(500)


@app.route('/quit')
def quit_game():
    session.clear()
    return redirect(url_for('home'))


@app.route('/continue')
def continue_game():
    player, redir = require_player()
    if redir:
        return redir
    all_rooms = db.get_all_rooms()
    for r in all_rooms:
        progress = player.get_progress(r['id'])
        if not progress['completed']:
            return redirect(url_for('room_view', room_id=r['id']))
    return redirect(url_for('win'))


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500
