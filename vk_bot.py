import re
import logging
from time import sleep
from random import randint
from textwrap import dedent

from environs import Env
from redis import Redis, ConnectionPool
import vk_api as vk
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from requests.exceptions import ReadTimeout, ConnectionError

logger = logging.getLogger(__name__)


def hello(event, vk_api, keyboard):
    vk_api.messages.send(
        user_id=event.user_id,
        keyboard=keyboard.get_keyboard(),
        message='Приветствую тебя в нашей викторине, нажми "Новый вопрос".',
        random_id=randint(1, 1000)
    )


def handle_new_question_request(event, vk_api, keyboard,
                                redis_db, questions_amount: int):
    question_number = f'question_{randint(1, questions_amount)}'
    user_data = redis_db.json().get(f'user_vk_{event.user_id}')
    if not user_data:
        redis_db.json().set(f'user_vk_{event.user_id}', '$',
                            {'last_asked_question': question_number,
                             'successful': 0, 'unsuccessful': 0}
                            )
    else:
        user_data['last_asked_question'] = question_number
        redis_db.json().set(f'user_vk_{event.user_id}', '$', user_data)
    question = redis_db.json().get(question_number).get('question')
    vk_api.messages.send(
        user_id=event.user_id,
        keyboard=keyboard.get_keyboard(),
        message=question,
        random_id=randint(1, 1000)
    )


def handle_solution_attempt(event, vk_api, keyboard, redis_db):
    user_message = event.text
    user_data = redis_db.json().get(f'user_vk_{event.user_id}')
    correct_answer = redis_db.json().get(
        user_data.get('last_asked_question')
    ).get('answer')
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
    else:
        message = 'Неправильно… Попробуешь ещё раз?'
        user_data['unsuccessful'] += 1
    redis_db.json().set(f'user_vk_{event.user_id}', '$', user_data)
    vk_api.messages.send(
        user_id=event.user_id,
        keyboard=keyboard.get_keyboard(),
        message=message,
        random_id=randint(1, 1000)
    )


def handle_surrender_button(event, vk_api, keyboard,
                            redis_db, questions_amount):
    user_data = redis_db.json().get(f'user_vk_{event.user_id}')
    correct_answer = redis_db.json().get(
        user_data.get('last_asked_question')
    ).get('answer')
    message = f'Правильный ответ:\n{correct_answer}'
    vk_api.messages.send(
        user_id=event.user_id,
        keyboard=keyboard.get_keyboard(),
        message=message,
        random_id=randint(1, 1000)
    )
    message = 'Попробуйте угадать ответ на следующий вопрос:\n\n'
    
    question_number = f'question_{randint(1, questions_amount)}'
    user_data['last_asked_question'] = question_number
    redis_db.json().set(f'user_vk_{event.user_id}', '$', user_data)
    question = redis_db.json().get(question_number).get('question')
    message += question
    redis_db.json().set(f'user_vk_{event.user_id}', '$', user_data)
    vk_api.messages.send(
        user_id=event.user_id,
        keyboard=keyboard.get_keyboard(),
        message=message,
        random_id=randint(1, 1000)
    )


def handle_score_button(event, vk_api, keyboard, redis_db):
    user_data = redis_db.json().get(f'user_vk_{event.user_id}')
    if user_data is None:
        message = 'Вы ещё не участвовали в викторине'
    else:
        message = dedent(f'''
        Количество удачных попыток: {user_data.get('successful')}.
        Количество неудачных попыток: {user_data.get('unsuccessful')}.
        ''')
    vk_api.messages.send(
        user_id=event.user_id,
        keyboard=keyboard.get_keyboard(),
        message=message,
        random_id=randint(1, 1000)
    )


def main():
    env = Env()
    env.read_env()
    pool = ConnectionPool(host=env.str('REDIS_HOST'),
                          port=env.str('REDIS_PORT'),
                          password=env.str('REDIS_PASSWORD')
                          )
    redis_db = Redis(connection_pool=pool)

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger.setLevel(logging.INFO)

    questions_amount = env.int('QUESTIONS_AMOUNT')
    vk_session = vk.VkApi(token=env.str('QUIZ_BOT_VK_TOKEN'))
    vk_api = vk_session.get_api()
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('Счёт', color=VkKeyboardColor.PRIMARY)
    longpoll = VkLongPoll(vk_session)
    logger.info('VK бот запущен')
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    if event.text.lower() == "привет":
                        hello(event, vk_api, keyboard)
                    elif event.text == "Сдаться":
                        handle_surrender_button(event, vk_api, keyboard,
                                                redis_db, questions_amount)
                    elif event.text == "Новый вопрос":
                        handle_new_question_request(event, vk_api, keyboard,
                                                    redis_db, questions_amount)
                    elif event.text == 'Счёт':
                        handle_score_button(event, vk_api, keyboard, redis_db)
                    else:
                        handle_solution_attempt(event, vk_api, keyboard,
                                                redis_db)
        except ReadTimeout as timeout:
            logger.warning(f'Превышено время ожидания VK бота\n{timeout}\n')
        except ConnectionError as connect_er:
            logger.warning(f'Произошёл сетевой сбой VK бота\n{connect_er}\n')
            sleep(20)


if __name__ == '__main__':
    main()
