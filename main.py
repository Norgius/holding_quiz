import os


max_number = 5
amount = 0
questions_with_onswers = {}
for questions_file in os.listdir('questions'):
    amount += 1
    if amount > max_number:
        break
    with open(os.path.join('questions', questions_file),
              'r', encoding='KOI8-R') as file:
        splited_file = file.read().split('\n\n')
        for chunk in splited_file:
            if 'Вопрос' in chunk:
                question = chunk.partition(':\n')[2]
                questions_with_onswers[question] = None
            elif 'Ответ' in chunk:
                onswer = chunk.partition(':\n')[2]
                questions_with_onswers[question] = onswer
