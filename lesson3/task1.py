import os
import requests
import time
from bs4 import BeautifulSoup
import json
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder
from pprint import pprint


class MongoConnection:
    def __init__(self):
        load_dotenv()
        self.mongo_host = os.getenv("MONGO_HOST")
        self.mongo_port = int(os.getenv("MONGO_PORT"))
        self.mongo_db = os.getenv("MONGO_DB")
        self.ssh_address = os.getenv("SERVER_HOST_NAME")
        self.ssh_port = int(os.getenv("SERVER_HOST_PORT"))
        self.ssh_username = os.getenv("SERVER_USERNAME")
        self.ssh_password = os.getenv("SERVER_PASSWORD")
        self.server = SSHTunnelForwarder(
            ssh_address_or_host=self.ssh_address,
            ssh_port=self.ssh_port,
            ssh_username=self.ssh_username,
            ssh_password=self.ssh_password,
            remote_bind_address=(self.mongo_host, int(self.mongo_port))
        )

    def __start_server(self):
        self.server.start()

    def __stop_server(self):
        self.server.stop()

    def insert_objects(self, collection, *objects):
        self.__start_server()
        with MongoClient(self.mongo_host, self.server.local_bind_port) as client:
            for new_object in objects:
                if client[self.mongo_db][collection].find(new_object).count() == 0:
                    client[self.mongo_db][collection].insert(new_object)
        self.__stop_server()

    def find(self, collection, search_condition):
        self.__start_server()
        with MongoClient(self.mongo_host, self.server.local_bind_port) as client:
            search_result = []
            for collection_object in client[self.mongo_db][collection].find(search_condition):
                search_result.append(collection_object)
        self.__stop_server()
        return search_result


class VacanciesParser:
    def __init__(self, start_url, retry_number, sleep):
        self.start_url = start_url
        self.retry_number = retry_number
        self.sleep = sleep
        self.vacancies = []
        self.responses = []
        self.mongo_connection = MongoConnection()

    def _get(self, *args, **kwargs):
        for i in range(self.retry_number):
            try:
                response = requests.get(*args, **kwargs)
                response.raise_for_status()
                return response
            except requests.HTTPError:
                time.sleep(self.sleep)
        return None

    def _post(self, *args, **kwargs):
        for i in range(self.retry_number):
            try:
                response = requests.post(*args, **kwargs)
                response.raise_for_status()
                return response
            except requests.HTTPError:
                time.sleep(self.sleep)
        return None

    def request(self, path="/", params=None, headers=None, method_type='get'):
        if method_type.lower() == 'get':
            self.responses.append(self._get(url=self.start_url + path, params=params, headers=headers))
        elif method_type.lower() == 'post':
            self.responses.append(self._post(url=self.start_url + path, params=params, headers=headers))
        else:
            pass

    @staticmethod
    def vacancy_salary_parser(vacancy_salary, vacancy_salary_frequency="месяц"):
        vacancy_salary_text = re.split(r'\d+', vacancy_salary)
        vacancy_salary_numbers = re.findall(r'\d+', vacancy_salary)
        vacancy_salary_numbers = list(map(int, vacancy_salary_numbers)) if vacancy_salary_numbers != [] else []
        if vacancy_salary_text[0] == 'до':
            return {"min": None, "max": vacancy_salary_numbers[0], "currency": vacancy_salary_text[1],
                    "frequency": vacancy_salary_frequency}
        elif vacancy_salary_text[0] == 'от':
            return {"min": vacancy_salary_numbers[0], "max": None, "currency": vacancy_salary_text.pop(),
                    "frequency": vacancy_salary_frequency}
        elif vacancy_salary_numbers:
            if vacancy_salary_frequency == 'месяц':
                return {"min": vacancy_salary_numbers[0], "max": vacancy_salary_numbers[1],
                        "currency": vacancy_salary_text.pop(), "frequency": vacancy_salary_frequency}
            return {"min": vacancy_salary_numbers[0], "max": None,
                    "currency": vacancy_salary_text.pop(), "frequency": vacancy_salary_frequency}
        else:
            return {}

    def save_data(self, collection, save_into="file"):
        if save_into.lower() == 'file':
            with open(f"{collection}_vacancies.json",
                      "w+" if not os.path.exists(f"{collection}_vacancies.json")
                      else "r+", encoding='utf-8') as f:
                try:
                    f.seek(0)
                    temp_list = json.load(f)
                except json.decoder.JSONDecodeError:
                    temp_list = []
                for el in self.vacancies:
                    if el not in temp_list:
                        temp_list.append(el)
                f.seek(0)
                json.dump(temp_list, f, indent=2, ensure_ascii=False)
        elif save_into.lower() in ('db', 'database'):
            self.mongo_connection.insert_objects(collection, *self.vacancies)

    def search_vacancies_by_salary(self, collection, gt=None, lt=None, only_without_salary=False):
        if only_without_salary:
            return self.mongo_connection.find(collection, {"$and": [{"salary.max": None}, {"salary.min": None}]})
        elif gt is None and lt is None:
            return self.mongo_connection.find(collection, {})
        elif gt is None:
            return self.mongo_connection.find(collection, {
                "$or": [
                        {"salary.min": {"$lt": lt}},
                        {"salary.max": {"$lt": lt}}
                    ]})
        elif lt is None:
            return self.mongo_connection.find(collection, {
                "$or": [
                    {"salary.min": {"$gt": gt}},
                    {"salary.max": {"$gt": gt}}
                ]})
        else:
            return self.mongo_connection.find(collection, {
                "$and": [
                    {"$or": [
                        {"salary.min": {"$gt": gt}},
                        {"salary.max": {"$gt": gt}}
                    ]},
                    {"$or": [
                        {"salary.min": {"$lt": lt}},
                        {"salary.max": {"$lt": lt}}
                    ]}
                ]})


class HeadhunterVacanciesParser(VacanciesParser):
    def __init__(self):
        super().__init__(start_url='https://hh.ru', retry_number=10, sleep=5)

    def request(self, **params):
        super().request(
            path="/search/vacancy/",
            headers={
                "user-agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/89.0.4389.82 Safari/537.36"},
            params=params)

    def parse(self, search_str, save_into="file"):
        i = 0
        if not self.responses:
            self.request(**{"text": " ".join(map(str, search_str.split()))})
        while True:
            resp = BeautifulSoup(self.responses[i].text, "html.parser")
            for el in resp.find_all("div", class_=re.compile("^vacancy-serp-item__row vacancy-serp-item__row_header")):
                vacancy_data = el.find_all(class_=re.compile("^bloko-section-header-3 bloko-section-header-3_lite"))
                vacancy_name = vacancy_data[0].find(class_=re.compile("^bloko-link")).text
                vacancy_ref = vacancy_data[0].find(class_=re.compile("^bloko-link"))["href"]
                if len(vacancy_data) > 1:
                    vacancy_salary = vacancy_data[1].text. \
                        encode("utf8").replace(b"\xc2", b"").replace(b"\xa0", b"").replace(b" ", b""). \
                        decode("utf8").replace(" ", "")
                else:
                    vacancy_salary = ""
                self.vacancies.append({
                    "name": vacancy_name,
                    "salary": self.vacancy_salary_parser(vacancy_salary),
                    "link": self.start_url + "/" + vacancy_ref.split(".ru/")[1].split("?")[0]
                })
            is_next_page_available = bool(resp.find("a", attrs={'data-qa': 'pager-next'}))
            if is_next_page_available:
                i += 1
                self.request(**{"text": " ".join(map(str, search_str.split())), "page": i})
            else:
                break
        self.save_data(collection="headhunter", save_into=save_into)


class SuperjobVacanciesParser(VacanciesParser):
    def __init__(self):
        super().__init__(start_url='https://superjob.ru', retry_number=10, sleep=5)

    def request(self, **params):
        super().request(
            path="/vacancy/search/",
            headers={
                "user-agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/89.0.4389.82 Safari/537.36"},
            params=params)

    def parse(self, search_str, save_into="file"):
        i = 0
        if not self.responses:
            self.request(**{"keywords": " ".join(map(str, search_str.split())), "noGeo": 1})
        while True:
            resp = BeautifulSoup(self.responses[i].text, "html.parser")
            for el in resp.find_all(class_=re.compile("^jNMYr GPKTZ _1tH7S")):
                vacancy_name = el.find(class_=re.compile("^icMQ_ _6AfZ9")).text
                vacancy_ref = el.find(class_=re.compile("^icMQ_ _6AfZ9"))["href"]
                vacancy_salary_source = el.find(class_=re.compile("^_1OuF_ _1qw9T"))
                vacancy_salary = vacancy_salary_source.find(
                    class_=re.compile("^_3mfro _2Wp8I")).text.replace("\xa0", "")
                vacancy_salary_frequency = None if not vacancy_salary_source.find(class_=re.compile("^_3mfro PlM3e")) \
                    else vacancy_salary_source.find(class_=re.compile("^_3mfro PlM3e")).text.replace("\xa0", "")
                self.vacancies.append({
                    "name": vacancy_name,
                    "salary": self.vacancy_salary_parser(vacancy_salary, vacancy_salary_frequency),
                    "link": self.start_url + vacancy_ref.split("?")[0]
                })
            pagination = resp.find(class_=re.compile("^_3zucV L1p51"))
            if pagination:
                if pagination.find(attrs={"rel": "next"}):
                    param_list = pagination.find(attrs={"rel": "next"})["href"].split("?")[1].split("&")
                    self.request(**{param.split("=")[0]: param.split("=")[1] for param in param_list})
                    i += 1
                else:
                    break
            else:
                break
        self.save_data(collection="superjob", save_into=save_into)


if __name__ == "__main__":
    search_string = input("Введите запрос для поиска вакансий: ")
    hh_search = HeadhunterVacanciesParser()
    sj_search = SuperjobVacanciesParser()
    hh_search.parse(search_string)
    sj_search.parse(search_string)
    hh_search.save_data("headhunter", save_into="db")
    sj_search.save_data("superjob", save_into="db")
    pprint(hh_search.search_vacancies_by_salary("headhunter", gt=100000, lt=350000))
    pprint(sj_search.search_vacancies_by_salary("superjob", only_without_salary=True))
