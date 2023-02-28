import re
import logging
from enum import Enum
from random import choice
from textwrap import dedent
from functools import partial

from environs import Env
from redis import Redis, ConnectionPool
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, ConversationHandler
from telegram.ext import MessageHandler, Filters, CallbackContext

from utils import get_questions_with_onswers

logger = logging.getLogger(__name__)


class State(Enum):
    NEW_QUESTION = 'new_question'
    ATTEMPT = 'attempt'


custom_keyboard = [['Новый вопрос', 'Сдаться']]
reply_markup = ReplyKeyboardMarkup(custom_keyboard)


def start(update: Update, context: CallbackContext) -> None:
    bot = context.bot
    chat_id = update.effective_chat.id
    bot.send_message(chat_id=chat_id,
                     text=dedent('''
                     Приветствую тебя в нашей викторине,
                     нажми "Новый вопрос".
                     '''),
                     reply_markup=reply_markup)
    return State.NEW_QUESTION.value


def handle_new_question_request(update: Update, context: CallbackContext,
                                quiz_questions: dict, redis_db):
    bot = context.bot
    chat_id = update.effective_chat.id
    question = choice(list(quiz_questions))
    redis_db.set(chat_id, question)
    bot.send_message(chat_id=chat_id,
                     text=question,
                     reply_markup=reply_markup)
    return State.ATTEMPT.value


def handle_solution_attempt(update: Update, context: CallbackContext,
                            quiz_questions: dict, redis_db):
    bot = context.bot
    chat_id = update.effective_chat.id
    user_message = update.message.text
    correct_answer = quiz_questions.get(
                        redis_db.get(chat_id).decode())
    regex = re.compile(r'\[.*?\]|\(|\)|\,|\:|\;|\"|\?|\!|\\]')
    correct_answer = regex.sub('', correct_answer)\
        .strip().lower().partition('.')[0]
    user_message = regex.sub('', user_message).strip()\
        .lower().partition('.')[0]
    if correct_answer == user_message:
        message = dedent('''
        Правильно! Поздравляю!
        Для следующего вопроса нажми «Новый вопрос»''')
        bot_state = State.NEW_QUESTION.value
    else:
        message = 'Неправильно… Попробуешь ещё раз?'
        bot_state = State.ATTEMPT.value
    bot.send_message(chat_id=chat_id,
                     text=message,
                     reply_markup=reply_markup)
    return bot_state


def handle_surrender_button(update: Update, context: CallbackContext,
                            quiz_questions: dict, redis_db):
    bot = context.bot
    chat_id = update.effective_chat.id
    correct_answer = quiz_questions.get(
                        redis_db.get(chat_id).decode())
    message = f'Правильный ответ:\n{correct_answer}'
    bot.send_message(chat_id=chat_id,
                     text=message)
    message = 'Попробуйте угадать ответ на следующий вопрос:\n\n'
    question = choice(list(quiz_questions))
    redis_db.set(chat_id, question)
    message += question
    bot.send_message(chat_id=chat_id,
                     text=message,
                     reply_markup=reply_markup)
    return State.ATTEMPT.value


def handle_unknow_message(update: Update, context: CallbackContext):
    bot = context.bot
    chat_id = update.effective_chat.id
    message = 'Я вас не понимаю, пожалуйста нажмите одну из кнопок ниже.'
    bot.send_message(chat_id=chat_id,
                     text=message,
                     reply_markup=reply_markup)
    return State.NEW_QUESTION.value


def cancel(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Пока!')
    return ConversationHandler.END


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def main() -> None:
    env = Env()
    env.read_env()
    pool = ConnectionPool(host=env.str('REDIS_HOST'),
                          port=env.str('REDIS_PORT'),
                          password=env.str('REDIS_PASSWORD')
                          )
    redis_db = Redis(connection_pool=pool)
    quiz_questions = get_questions_with_onswers()
    quiz_bot_tg_token = env.str('QUIZ_BOT_TG_TOKEN')

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
                                                    quiz_questions=quiz_questions,
                                                    redis_db=redis_db),
                                            ),
                             MessageHandler(Filters.text,
                                            handle_unknow_message,
                                            )
                             ],
            'attempt': [MessageHandler(Filters.regex('^(Сдаться)$'),
                                       partial(handle_surrender_button,
                                               quiz_questions=quiz_questions,
                                               redis_db=redis_db),
                                       ),
                        MessageHandler(Filters.text,
                                       partial(handle_solution_attempt,
                                               quiz_questions=quiz_questions,
                                               redis_db=redis_db),
                                       ),
                        ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error)
    logger.info('Телеграм бот запущен')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
