import os


def get_questions_with_onswers():
    max_number, number = 10, 0
    questions_with_answers = {}
    for questions_file in os.listdir('questions'):
        number += 1
        if number > max_number:
            break
        with open(os.path.join('questions', questions_file),
                  'r', encoding='KOI8-R') as file:
            splited_file = file.read().split('\n\n')
            for chunk in splited_file:
                if 'Вопрос' in chunk:
                    question = chunk.partition(':\n')[2]
                    questions_with_answers[question] = None
                elif 'Ответ' in chunk:
                    onswer = chunk.partition(':\n')[2]
                    questions_with_answers[question] = onswer
    return questions_with_answers
