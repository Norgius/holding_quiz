import os
from environs import Env
from redis import Redis, ConnectionPool


def load_quiz_questions_to_redis(redis_db, files_number,
                                 quiz_questions_folder):
    questions_number, file_number = 0, 0
    quiz_questions = {}
    for file_number, questions_file in enumerate(
            os.listdir(quiz_questions_folder), start=1):
        if file_number > files_number:
            return questions_number
        with open(os.path.join(quiz_questions_folder, questions_file),
                  'r', encoding='KOI8-R') as file:
            splited_file = file.read().split('\n\n')
            for chunk in splited_file:
                if 'Вопрос' in chunk:
                    questions_number += 1
                    question = chunk.partition(':\n')[2]
                    quiz_questions[f'question_{questions_number}']\
                        = {'question': question}
                elif 'Ответ' in chunk:
                    answer = chunk.partition(':\n')[2]
                    quiz_questions\
                        .get(f'question_{questions_number}')['answer'] = answer
                    redis_db.json().set(
                        f'question_{questions_number}', '$',
                        {'question': question, 'answer': answer}
                    )
    return questions_number


def main():
    env = Env()
    env.read_env()
    pool = ConnectionPool(host=env.str('REDIS_HOST'),
                          port=env.str('REDIS_PORT'),
                          password=env.str('REDIS_PASSWORD')
                          )
    redis_db = Redis(connection_pool=pool)
    files_number = env.int('QUIZ_FILES_NUMBER', 100000)
    quiz_questions_folder = env.str('QUIZ_QUESTIONS_FOLDER')
    question_number = load_quiz_questions_to_redis(redis_db, files_number,
                                                   quiz_questions_folder)
    print('Количество вопросов: ', question_number)


if __name__ == '__main__':
    main()
