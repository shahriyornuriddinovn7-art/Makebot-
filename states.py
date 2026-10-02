"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    add_channel = State()
    set_key = State()
    bc_wait_msg = State()
    bc_wait_buttons = State()
    bc_confirm = State()


class MakerStates(StatesGroup):
    token = State()
    ai_chat = State()


class MovieStates(StatesGroup):
    video = State()
    fields = State()
    post_channel = State()


class EduStates(StatesGroup):
    sched_text = State()
    note_text = State()
    gen_topic = State()
    quiz_topic = State()
    plan_topic = State()
    student_name = State()
    book_file = State()
    book_title = State()
