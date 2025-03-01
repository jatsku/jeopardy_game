from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", engineio_logger=True, async_mode='eventlet')

# Sample questions
questions = [
    {"text": "What is the capital of France?", "answer": "Paris"},
    {"text": "What is 2 + 2?", "answer": "4"},
    {"text": "What planet is known as the Red Planet?", "answer": "Mars"},
    {"text": "Which element has the symbol 'O'?", "answer": "Oxygen"},
    {"text": "What is the largest ocean on Earth?", "answer": "Pacific"},
    {"text": "What is the capital of Japan?", "answer": "Tokyo"},
    {"text": "What gas do plants absorb from the atmosphere?", "answer": "Carbon dioxide"},
    {"text": "Who painted the Mona Lisa?", "answer": "Leonardo da Vinci"},
    {"text": "What is the smallest country in the world by land area?", "answer": "Vatican City"},
    {"text": "What is the main ingredient in guacamole?", "answer": "Avocado"},
    {"text": "What is the chemical symbol for gold?", "answer": "Au"},
    {"text": "Which animal is known as the 'King of the Jungle'?", "answer": "Lion"},
    {"text": "What is the tallest mountain in the world?", "answer": "Everest"},
    {"text": "What language is spoken in Brazil?", "answer": "Portuguese"},
    {"text": "What is the currency of the United Kingdom?", "answer": "Pound"},
    {"text": "Who wrote 'Romeo and Juliet'?", "answer": "William Shakespeare"},
    {"text": "What is the largest desert in the world?", "answer": "Antarctic"},
    {"text": "What is the primary source of energy for Earth?", "answer": "Sun"},
    {"text": "What is the capital of Australia?", "answer": "Canberra"},
    {"text": "What fruit is known as the spiky exterior?", "answer": "Durian"}
]
current_question = None
players = {}  # {player_id: {"username": str, "score": int, "ready": bool}}
buzzer_locked = False
game_started = False

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect(auth):
    sid = request.sid
    print(f"DEBUG: Player {sid} connected. Current players: {list(players.keys())}")
    players[sid] = {"username": sid[:4], "score": 0, "ready": False}
    player_count = len(players)
    print(f"DEBUG: Emitting player_count: {player_count}")
    emit('player_count', player_count, broadcast=True)
    emit('update_lobby', {'players': {k: {'username': v['username'], 'ready': v['ready']} for k, v in players.items()}}, broadcast=True)
    emit('request_username', to=sid)
    if len(players) == 2 and all(p['ready'] for p in players.values()) and not current_question:
        print("DEBUG: All players ready, initiating first question")
        game_started = True
        send_new_question()

@socketio.on('set_username')
def handle_username(data):
    sid = request.sid
    username = data['username'][:20].strip()
    if sid in players and username:
        players[sid]['username'] = username
        print(f"DEBUG: Player {sid} set username to {username}")
        emit('username_set', {'player_id': sid, 'username': username}, broadcast=True)
        emit('update_lobby', {'players': {k: {'username': v['username'], 'ready': v['ready']} for k, v in players.items()}}, broadcast=True)
    if len(players) == 2 and all(p['ready'] for p in players.values()) and not current_question:
        print("DEBUG: All players ready after username, initiating first question")
        game_started = True
        send_new_question()

@socketio.on('set_ready')
def handle_ready():
    sid = request.sid
    if sid in players:
        players[sid]['ready'] = not players[sid]['ready']
        print(f"DEBUG: Player {sid} set ready to {players[sid]['ready']}")
        emit('update_lobby', {'players': {k: {'username': v['username'], 'ready': v['ready']} for k, v in players.items()}}, broadcast=True)
        if len(players) == 2 and all(p['ready'] for p in players.values()) and not current_question:
            print("DEBUG: All players ready, initiating first question")
            game_started = True
            send_new_question()

@socketio.on('disconnect')
def handle_disconnect(sid):
    global game_started
    print(f"DEBUG: Player {sid} disconnected. Remaining players: {list(players.keys())}")
    if sid in players:
        del players[sid]
    player_count = len(players)
    print(f"DEBUG: Emitting player_count: {player_count}")
    emit('player_count', player_count, broadcast=True)
    emit('update_lobby', {'players': {k: {'username': v['username'], 'ready': v['ready']} for k, v in players.items()}}, broadcast=True)
    if len(players) < 2 and game_started:
        game_started = False

@socketio.on('buzz')
def handle_buzz():
    global buzzer_locked
    if not buzzer_locked and current_question:
        buzzer_locked = True
        sid = request.sid
        print(f"DEBUG: Player {sid} buzzed in")
        emit('buzzed', {'player': sid}, broadcast=True)
        emit('answer_prompt', to=sid)

@socketio.on('submit_answer')
def handle_answer(data):
    global buzzer_locked, current_question
    sid = request.sid
    if current_question and data['answer'].lower() == current_question['answer'].lower():
        players[sid]['score'] += 10
        emit('result', {'player': sid, 'correct': True}, broadcast=True)
        print(f"DEBUG: Player {sid} answered correctly. Score: {players[sid]['score']}")
    elif current_question:
        players[sid]['score'] -= 5
        emit('result', {'player': sid, 'correct': False}, broadcast=True)
        print(f"DEBUG: Player {sid} answered incorrectly. Score: {players[sid]['score']}")
    else:
        print("DEBUG: No current question to answer")
    buzzer_locked = False
    current_question = None
    socketio.sleep(2)
    if len(players) >= 2 and questions:
        print("DEBUG: Moving to next question after answer")
        send_new_question()

@socketio.on('timeout')
def handle_timeout():
    global buzzer_locked, current_question
    if buzzer_locked:
        print("DEBUG: Timeout with buzzer locked, waiting")
    else:
        print("DEBUG: Timeout, moving to next question")
    buzzer_locked = False
    current_question = None
    socketio.sleep(1)
    if len(players) >= 2 and questions:
        print("DEBUG: Sending new question after timeout")
        send_new_question()

def send_new_question():
    global current_question
    if questions and len(players) >= 2:
        current_question = random.choice(questions)
        questions.remove(current_question)
        print(f"DEBUG: Sending question: {current_question['text']} to {len(players)} players")
        emit('new_question', current_question['text'], broadcast=True)
    elif not questions:
        print("DEBUG: No more questions, ending game")
        emit('game_over', "No more questions! Game Over!", broadcast=True)

if __name__ == '__main__':
    print("DEBUG: Starting SocketIO server")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)