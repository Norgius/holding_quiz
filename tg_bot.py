import re
import logging
from enum import Enum
from random import randint
from textwrap import dedent
from functools import partial

from environs import Env
from redis import Redis, ConnectionPool
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler
from telegram.ext import MessageHandler, Filters, CallbackContext


logger = logging.getLogger(__name__)


class State(Enum):
    NEW_QUESTION = 'new_question'
    ATTEMPT = 'attempt'


custom_keyboard = [['Новый вопрос', 'Сдаться'], ['Счёт']]
reply_markup = ReplyKeyboardMarkup(custom_keyboard)


def start(update: Update, context: CallbackContext):
    text = dedent('''
    Приветствую тебя в нашей викторине,
    нажми "Новый вопрос".
    ''')
    context.bot_data['bot_state'] = State.NEW_QUESTION.value
    update.message.reply_text(text=text, reply_markup=reply_markup)
    return State.NEW_QUESTION.value


def handle_new_question_request(update: Update, context: CallbackContext,
                                redis_db, questions_amount: int):
    chat_id = update.effective_chat.id
    context.bot_data['bot_state'] = State.ATTEMPT.value
    question_number = f'question_{randint(1, questions_amount)}'
    user_data = redis_db.json().get(f'user_tg_{chat_id}')
    if not user_data:
        redis_db.json().set(f'user_tg_{chat_id}', '$',
                            {'last_asked_question': question_number,
                             'successful': 0, 'unsuccessful': 0}
                            )
    else:
        user_data['last_asked_question'] = question_number
        redis_db.json().set(f'user_tg_{chat_id}', '$', user_data)
    question = redis_db.json().get(question_number).get('question')
    update.message.reply_text(text=question, reply_markup=reply_markup)
    return State.ATTEMPT.value


def handle_solution_attempt(update: Update, context: CallbackContext,
                            redis_db):
    chat_id = update.effective_chat.id
    user_message = update.message.text
    user_data = redis_db.json().get(f'user_tg_{chat_id}')
    correct_answer = redis_db.json().get(
        user_data.get('last_asked_question')
    ).get('answer')
    # для построения шаблона регулярного выражения re.compile(...),
    # воспользовался ссылкой представленной ниже
    # https://stackoverflow.com/questions/14596884/remove-text-between-and
    regex = re.compile(r'\[.*?\]|\(|\)|\,|\:|\;|\"|\?|\!|\\]')
    correct_answer = regex.sub('', correct_answer)\
        .strip().lower().partition('.')[0]
    user_message = regex.sub('', user_message).strip()\
        .lower().partition('.')[0]

    if correct_answer == user_message:
        message = dedent('''
        Правильно! Поздравляю!
        Для следующего вопроса нажми «Новый вопрос»''')
        user_data['successful'] += 1
        bot_state = State.NEW_QUESTION.value
    else:
        message = 'Неправильно… Попробуешь ещё раз?'
        user_data['unsuccessful'] += 1
        bot_state = State.ATTEMPT.value

    context.bot_data['bot_state'] = bot_state
    redis_db.json().set(f'user_tg_{chat_id}', '$', user_data)
    update.message.reply_text(text=message, reply_markup=reply_markup)
    return bot_state


def handle_surrender_button(update: Update, context: CallbackContext,
                            redis_db, questions_amount: int):
    chat_id = update.effective_chat.id
    context.bot_data['bot_state'] = State.ATTEMPT.value
    user_data = redis_db.json().get(f'user_tg_{chat_id}')
    correct_answer = redis_db.json().get(
        user_data.get('last_asked_question')
    ).get('answer')
    message = f'Правильный ответ:\n{correct_answer}'
    update.message.reply_text(text=message)

    message = 'Попробуйте угадать ответ на следующий вопрос:\n\n'
    question_number = f'question_{randint(1, questions_amount)}'
    user_data['last_asked_question'] = question_number
    redis_db.json().set(f'user_tg_{chat_id}', '$', user_data)
    question = redis_db.json().get(question_number).get('question')
    message += question
    update.message.reply_text(text=message, reply_markup=reply_markup)
    return State.ATTEMPT.value


def handle_unknow_message(update: Update, context: CallbackContext):
    message = 'Я вас не понимаю, пожалуйста нажмите одну из кнопок ниже.'
    update.message.reply_text(text=message, reply_markup=reply_markup)
    return State.NEW_QUESTION.value


def handle_score_button(update: Update, context: CallbackContext,
                        redis_db):
    bot_state = context.bot_data['bot_state']
    chat_id = update.effective_chat.id
    user_data = redis_db.json().get(f'user_tg_{chat_id}')
    if user_data is None:
        message = 'Вы ещё не участвовали в викторине'
    else:
        message = dedent(f'''
        Количество удачных попыток: {user_data.get('successful')}.
        Количество неудачных попыток: {user_data.get('unsuccessful')}.
        ''')
    update.message.reply_text(text=message, reply_markup=reply_markup)
    return bot_state


def handle_exit(update: Update, context: CallbackContext):
    update.message.reply_text('Пока! Надеюсь вы ещё вернётесь в викторину!')
    return ConversationHandler.END


def handle_error(update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    env = Env()
    env.read_env()
    pool = ConnectionPool(host=env.str('REDIS_HOST'),
                          port=env.str('REDIS_PORT'),
                          password=env.str('REDIS_PASSWORD')
                          )
    redis_db = Redis(connection_pool=pool)
    quiz_bot_tg_token = env.str('QUIZ_BOT_TG_TOKEN')
    questions_amount = env.int('QUESTIONS_AMOUNT')
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger.setLevel(logging.INFO)
    updater = Updater(quiz_bot_tg_token)
    dispatcher = updater.dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            'new_question': [MessageHandler(Filters.regex('^(Новый вопрос)$'),
                                            partial(handle_new_question_request,
                                                    redis_db=redis_db,
                                                    questions_amount=questions_amount),
                                            ),
                             MessageHandler(Filters.regex(r'[^/exit|Счёт]'),
                                            handle_unknow_message,
                                            ),
                             ],
            'attempt': [MessageHandler(Filters.regex('^(Сдаться)$'),
                                       partial(handle_surrender_button,
                                               redis_db=redis_db,
                                               questions_amount=questions_amount),

                                       ),
                        MessageHandler(Filters.regex(r'[^/exit|Счёт]'),
                                       partial(handle_solution_attempt,
                                               redis_db=redis_db),
                                       ),
                        ],
        },
        fallbacks=[CommandHandler('exit', handle_exit),
                   MessageHandler(Filters.regex('^(Счёт)$'),
                                  partial(handle_score_button,
                                          redis_db=redis_db),
                                  ),
                   ]
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(handle_error)
    logger.info('Телеграм бот запущен')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
