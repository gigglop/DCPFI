# 2. Изучить список открытых API.
# Найти среди них любое, требующее авторизацию (любого типа).
# Выполнить запросы к нему, пройдя авторизацию.
# Ответ сервера записать в файл.


import requests
from json import dump

# Используя ЛК на https://calendarific.com/account я получил API-ключ:
api_key = "7338084c4a83e1806e46e211817ba24fcfa1b832"
parameters = {
    "api_key": api_key,
    "country": "IT",
    "year": input("Enter year for which you would like to see holidays in Italy: ")
}
host = "https://calendarific.com"
path = "/api/v2/holidays"
# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
#     "X-Accept": "application/json",
#     "Content-Type": "application/json; charset=UTF8"
# }
r = requests.post(host + path, params=parameters)

if r.status_code == 200:
    with open(f"task2.holidays {parameters['country']}-{parameters['year']}", "w") as f:
        dump(r.json(), f)
