import os
import requests
import time
from bs4 import BeautifulSoup as bs
import json
import re


class Parser:
    def __init__(self, start_url, retry_number, sleep):
        self.start_url = start_url
        self.retry_number = retry_number
        self.sleep = sleep
        self.data = []
        self.responses = []

    def _get(self, *args, **kwargs):
        for i in range(self.retry_number):
            try:
                response = requests.get(*args, **kwargs)
                if response.status_code != 200:
                    raise Exception("Status code != 200")
                return response
            except:
                time.sleep(self.sleep)
        return None

    def _post(self, *args, **kwargs):
        for i in range(self.retry_number):
            try:
                response = requests.post(*args, **kwargs)
                if response.status_code != 200:
                    raise Exception("Status code != 200")
                return response
            except:
                time.sleep(self.sleep)
        return None

    def request(self, path="/", params=None, headers=None, method_type='get'):
        if method_type.lower() == 'get':
            self.responses.append(self._get(url=self.start_url + path, params=params, headers=headers))
        elif method_type.lower() == 'post':
            self.responses.append(self._post(url=self.start_url + path, params=params, headers=headers))
        else:
            pass

    def save(self, search_str):
        with open(f"{'_'.join(str(search_str).split())}_vacancies.json",
                  "w+" if not os.path.exists(f"{'_'.join(str(search_str).split())}_vacancies.json")
                  else "r+", encoding='utf-8') as f:
            try:
                f.seek(0)
                temp_list = json.load(f)
            except json.decoder.JSONDecodeError:
                temp_list = []
            for el in self.data:
                if el not in temp_list:
                    temp_list.append(el)
            f.seek(0)
            json.dump(temp_list, f, indent=2, ensure_ascii=False)


class HeadhunterParser(Parser):
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

    @staticmethod
    def vacancy_salary_parser(vacancy_salary):
        vacancy_salary_text = re.split(r'\d+', vacancy_salary)
        vacancy_salary_numbers = re.findall(r'\d+', vacancy_salary)
        if vacancy_salary_text[0] == 'до':
            return {"min": None, "max": vacancy_salary_numbers[0], "currency": vacancy_salary_text[1],
                    "frequency": "месяц"}
        elif vacancy_salary_text[0] == 'от':
            return {"min": vacancy_salary_numbers[0], "max": None, "currency": vacancy_salary_text.pop(),
                    "frequency": "месяц"}
        elif vacancy_salary_numbers:
            return {"min": vacancy_salary_numbers[0], "max": vacancy_salary_numbers[1],
                    "currency": vacancy_salary_text.pop(), "frequency": "месяц"}
        else:
            return {}

    def parse(self, *search_str):
        i = 0
        if not self.responses:
            self.request(**{"text": "+".join(map(str, search_str))})
        while True:
            resp = bs(self.responses[i].text, "html.parser")
            for el in resp.find_all("div", class_=re.compile("^vacancy-serp-item__row vacancy-serp-item__row_header")):
                vacancy_data = el.find_all(class_=re.compile("^bloko-section-header-3 bloko-section-header-3_lite"))
                vacancy_name = vacancy_data[0].find(class_=re.compile("^bloko-link")).text
                vacancy_ref = vacancy_data[0].find(class_=re.compile("^bloko-link"))["href"]
                if len(vacancy_data) > 1:
                    vacancy_salary = vacancy_data[1].text.\
                        encode("utf8").replace(b"\xc2", b"").replace(b"\xa0", b"").replace(b" ", b"").\
                        decode("utf8")
                else:
                    vacancy_salary = ""
                self.data.append({
                    "name": vacancy_name,
                    "salary": self.vacancy_salary_parser(vacancy_salary),
                    "link": self.start_url + "/" + vacancy_ref.split(".ru/")[1],
                    "source": "hh"
                })
            is_next_page_available = bool(resp.find("a", attrs={'data-qa': 'pager-next'}))
            if is_next_page_available:
                i += 1
                self.request(**{"text": "+".join(map(str, search_str)), "page": i})
            else:
                break
        self.save(*search_str)


class SuperjobParser(Parser):
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

    @staticmethod
    def vacancy_salary_parser(vacancy_salary):
        vacancy_salary_size = vacancy_salary.find(class_=re.compile("^_3mfro _2Wp8I")).text.replace("\xa0", "")
        vacancy_salary_frequency = None if not vacancy_salary.find(class_=re.compile("^_3mfro PlM3e")) else \
            vacancy_salary.find(class_=re.compile("^_3mfro PlM3e")).text.replace("\xa0", "")
        vacancy_salary_text = re.split(r'\d+', vacancy_salary_size)
        vacancy_salary_numbers = re.findall(r'\d+', vacancy_salary_size)
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

    def parse(self, *search_str):
        i = 0
        if not self.responses:
            self.request(**{"keywords": " ".join(map(str, search_str)), "noGeo": 1})
        while True:
            resp = bs(self.responses[i].text, "html.parser")
            for el in resp.find_all(class_=re.compile("^jNMYr GPKTZ _1tH7S")):
                vacancy_name = el.find(class_=re.compile("^icMQ_ _6AfZ9")).text
                vacancy_ref = el.find(class_=re.compile("^icMQ_ _6AfZ9"))["href"]
                vacancy_salary = el.find(class_=re.compile("^_1OuF_ _1qw9T"))
                self.data.append({
                    "name": vacancy_name,
                    "salary": self.vacancy_salary_parser(vacancy_salary),
                    "link": self.start_url + vacancy_ref,
                    "source": "superjob"
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
        self.save(*search_str)


if __name__ == "__main__":
    search_string = input("Введите запрос для поиска вакансий: ")
    hh_search = HeadhunterParser()
    sj_search = SuperjobParser()
    hh_search.parse(search_string)
    sj_search.parse(search_string)
