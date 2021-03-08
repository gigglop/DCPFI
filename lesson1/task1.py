# 1. Посмотреть документацию к API GitHub,
# разобраться как вывести список репозиториев для конкретного пользователя,
# сохранить JSON-вывод в файле *.json.
import requests
from json import dump

while True:
    user_input = input('Are you looking for repos of organizations/users? (o/u)\n').lower()
    if user_input == 'o':
        id = input('Enter github name: ')
        url = f"https://api.github.com/orgs/{id}/repos"
        break
    if user_input == 'u':
        id = input('Enter github name: ')
        url = f"https://api.github.com/users/{id}/repos"
        break
    else:
        print("Incorrect input. Try again.")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json"
}
r = requests.get(url, headers=headers)
if r.status_code == 200:
    path = f"task1.{id}_repos.json"
    with open(path, "w") as f:
        dump(r.json(), f)
