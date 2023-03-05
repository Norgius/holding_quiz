import os
from environs import Env
from redis import Redis, ConnectionPool


def get_questions_with_onswers(redis_db, files_number):
    question_number, file_number = 0, 0
    quiz_questions = {}
    for questions_file in os.listdir('questions'):
        file_number += 1
        if file_number > files_number:
            return question_number
        with open(os.path.join('questions', questions_file),
                  'r', encoding='KOI8-R') as file:
            splited_file = file.read().split('\n\n')
            for chunk in splited_file:
                if 'Вопрос' in chunk:
                    question_number += 1
                    question = chunk.partition(':\n')[2]
                    quiz_questions[f'question_{question_number}']\
                        = {'question': question}
                elif 'Ответ' in chunk:
                    answer = chunk.partition(':\n')[2]
                    quiz_questions\
                        .get(f'question_{question_number}')['answer'] = answer
                    redis_db.json().set(
                        f'question_{question_number}', '$',
                        {'question': question, 'answer': answer}
                    )
    return question_number


def main():
    env = Env()
    env.read_env()
    pool = ConnectionPool(host=env.str('REDIS_HOST'),
                          port=env.str('REDIS_PORT'),
                          password=env.str('REDIS_PASSWORD')
                          )
    redis_db = Redis(connection_pool=pool)
    files_number = env.int('QUIZ_FILES_NUMBER', 100000)
    question_number = get_questions_with_onswers(redis_db, files_number)
    print('Количество вопросов: ', question_number)


if __name__ == '__main__':
    main()
