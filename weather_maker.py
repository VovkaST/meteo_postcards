import re
from datetime import datetime, timedelta
from time import sleep

import requests
from bs4 import BeautifulSoup


class Forecast:
    """ Прогноз подгоды на дату """
    WEEK_DAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', ]

    def __init__(self):
        self.city = str()
        self.city_translit = str()
        self._cloudiness = str()
        self._precipitations = str()
        self._date = None
        self._temp_list = list()

    def print(self):
        """
        Печать в консоль прогноза суточного прогноза погоды

        :return str: Консольное табличное представление прогноза
        """
        table_width = 17
        if table_width < 1:
            return
        rows_delimiter = '+{:-^{}}+'.format('', table_width)
        s = list()
        s.append(rows_delimiter)
        s.append('|{:^{}s}|'.format(f'{self.date}, {self.week_day}', table_width))
        s.append(str('|' + ' {:^7s}|' * 2).format('t\u00B0C От', 't\u00B0C До'))
        s.append(str('|' + '{:>7s} |' * 2).format(self.day_temp_min, self.day_temp_max))
        s.append('|{:^{}s}|'.format(self.cloud_precip, table_width))
        s.append(rows_delimiter)
        return '\r\n'.join(s)

    @property
    def week_day(self):
        if self.date:
            return self.WEEK_DAYS[int(self._date.strftime('%w'))]

    @property
    def cloudiness(self):
        return self._cloudiness

    @cloudiness.setter
    def cloudiness(self, value):
        if value is not None:
            self._cloudiness = str(value).replace('&nbsp;', ' ')

    @property
    def precipitations(self):
        return self._precipitations

    @precipitations.setter
    def precipitations(self, value):
        if value is not None:
            self._precipitations = str(value).replace('&nbsp;', ' ')

    @property
    def day_temp(self) -> str:
        if not self._temp_list:
            return ''
        t = round(sum(self._temp_list) / len(self._temp_list), 1)
        return f'+{t}' if t > 0 else str(t)

    @day_temp.setter
    def day_temp(self, temp):
        if temp != '':
            self._temp_list.append(int(str(temp).replace(chr(8722), chr(45))))

    @property
    def day_temp_max(self) -> str:
        if not self._temp_list:
            return ''
        _t = max(self._temp_list)
        return f'+{_t}' if _t > 0 else str(_t)

    @property
    def day_temp_min(self) -> str:
        if not self._temp_list:
            return ''
        _t = min(self._temp_list)
        return f'+{_t}' if _t > 0 else str(_t)

    @property
    def date(self) -> datetime.date:
        try:
            return self._date.strftime('%d.%m.%Y')
        except AttributeError:
            return None

    @property
    def cloud_precip(self):
        _s = self.cloudiness
        if self.precipitations:
            _s += f', {self.precipitations}'
        return _s

    def set_date(self, date: datetime.date):
        self._date = date

    def to_dict(self):
        return {'max_temp': self.day_temp_max or None,
                'min_temp': self.day_temp_min or None,
                'cloudiness': self.cloudiness.lower() or None,
                'precipitations': self.precipitations.lower() or None}


class WeatherMaker:
    """ Парсер сайта GisMeteo.ru """

    SITE = 'https://www.gismeteo.ru'
    URL_DIARY = '{}/diary/{}/{}/{}/'.format(SITE, '{}', '{}', '{}')  # /diary/{city_id}/{year}/{month}/
    DEFAULT_FORECAST_PAGE = '/weather-moscow-4368/'
    DEFAULT_CITY = 'Москва'
    DEFAULT_CITY_TRANSLIT = 'Moscow'

    PERIOD_MONTH = 'month/'
    HUMAN_IMITATE_TIMEOUT = 3

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) '
                                              'Chrome/79.0.3945.117 YaBrowser/20.2.0.1043 Yowser/2.5 Safari/537.36',
                                'accept-language': 'ru,en;q=0.9',
                                }
        self.cities_catalog = []  # [{'name': 'Москва', 'link': '/weather-moscow-4368/'}, ...]
        self.diary_labels = dict()
        self.daily_forecasts = dict()  # {<class 'datetime.date'>: <class 'Forecast'>, ...}
        self._init_regions_catalog()
        self.city_url = ''
        self.city = ''

    @property
    def city_id(self):
        if self.city_url is None:
            return
        try:
            return re.findall(pattern=r'/.*\-(\d*)/', string=self.city_url)[0]
        except IndexError:
            return ''

    @property
    def city_translit(self):
        if self.city_url is None:
            return self.DEFAULT_CITY_TRANSLIT
        try:
            return re.findall(pattern=r'weather\-(.*)\-\d*', string=self.city_url)[0]
        except IndexError:
            return ''

    def _init_regions_catalog(self):
        """ Собирает список словарей с названиями и ссылками популярных городов России """
        html = self._beautiful_soup(url=f'{self.SITE}/catalog/russia/')
        for tag in html.select('.catalog_side:last-child .catalog_item a:first-child'):
            self.cities_catalog.append({'name': tag.text.strip(),
                                        'link': tag['href']})

    def _beautiful_soup(self, url) -> BeautifulSoup:
        """
        Возвращает распарсенную страницу по url

        :param str url: Адресная строка страницы прогноза
        :return: bs4.BeautifulSoup
        """
        response = self.request(url=url)
        return BeautifulSoup(response.text, features='html.parser')

    def _init_forecasts(self, until_date, since_date=datetime.today()):
        """
        Создает список объектов Forecast в атрибуте self.forecast заданной длины в диапазоне дат
        :param datetime.date until_date: Дата - Конец диапазона дней прогнозов
        :param datetime.date since_date: Дата - начало диапазона дней прогнозов
        """
        period_len = (until_date - since_date).days + 1
        for day in range(0, period_len):
            fc = Forecast()
            fc.set_date(since_date + timedelta(day))
            self.daily_forecasts[since_date + timedelta(day)] = fc

    def _init_diary_labels(self, html):
        """
        Инициирует словарь с имененем значка облачности в качестве ключа и понятием облачности в качестве значения

        :param BeautifulSoup html: ОБъект bs4.BeautifulSoup
        """
        if not self.diary_labels:
            for tag in html.select('#cloudness_labels > .label_smallsize, #precipitations_labels > .label_bigsize'):
                for img in tag.select('img'):
                    self.diary_labels[img.get('src').split('/')[-1]] = tag.findNext('dl').text

    @property
    def latest_forecast_day(self) -> datetime.date:
        """
        Возвращает объект date, содержащий дату последнего возможного дня прогноза.
        Определяется относительно понедельника текущей недели + 30 дней
        """
        monday = datetime.today() - timedelta(datetime.today().weekday())
        return (monday + timedelta(30)).date()

    def diary_urls(self, since_date, until_date):
        """
        Формирует итератор по url-адресам дневников за заданный период

        :param datetime.date since_date: Начало периода прогноза
        :param datetime.date until_date: Конец периода прогноза
        """
        if since_date.year != until_date.year:
            for year in range(since_date.year, until_date.year + 1):
                if year == since_date.year:
                    _range = range(since_date.month, 13)
                elif since_date.year < year < until_date.year:
                    _range = range(1, 13)
                elif year == until_date.year:
                    _range = range(1, until_date.month + 1)
                else:
                    continue
                for month in _range:
                    yield self.URL_DIARY.format(self.city_id, year, month), year, month
        else:
            for month in range(since_date.month, until_date.month + 1):
                yield self.URL_DIARY.format(self.city_id, since_date.year, month), since_date.year, month

    def init_city_url(self, needle_city):
        """
        Определяет ссылку на страницу прогноза погода в городе needle_city

        :param str needle_city: Строка искомого города
        """
        for city in self.cities_catalog:
            if city['name'].upper() == needle_city.strip().upper():
                self.city_url = city['link']
                self.city = city['name']
                return
        self.city_url = self.DEFAULT_FORECAST_PAGE
        self.city = self.DEFAULT_CITY

    def request(self, url) -> requests.Response:
        """
        Отправляет GET-запрос на self.SITE с предустановленными заголовками

        :param str url: Строка url-адреса
        :rtype: requests.Response
        """
        sleep(self.HUMAN_IMITATE_TIMEOUT)
        return self.session.get(url=url)

    def get_forecast(self, needle_city, since_date=None, until_date=None) -> dict:
        """
        Получить прогноз погоды конкретного города за диапазон дат.
        Если введенный город не опознан, возвращается прогноз города по умолчанию.

        :param str needle_city: Поисковая строка названия города
        :param datetime.date since_date: Начало периода прогноза
        :param datetime.date until_date: Конец периода прогноза
        :return dict: Словарь прогнозов: {<class 'datetime.date'>: <class 'WeatherMaker'>, ...}
        """
        if since_date is None:
            since_date = datetime.today().date()
        if until_date is None:
            until_date = datetime.today().date()
        self.init_city_url(needle_city=needle_city)
        yesterday = (datetime.today() - timedelta(1)).date()
        if since_date > self.latest_forecast_day:
            since_date = self.latest_forecast_day
        if until_date < since_date:
            until_date = since_date
        elif until_date > self.latest_forecast_day:
            until_date = self.latest_forecast_day
        self._init_forecasts(since_date=since_date, until_date=until_date)
        # Если весь прогноз на будущее
        if since_date >= yesterday:
            self.parse_month_page(since_date=since_date, until_date=until_date)
        # Если весь прогноз из прошлого (дневник)
        elif until_date < yesterday:
            self.parse_history_forecasts(since_date=since_date, until_date=until_date)
        # Если смешанный период
        elif since_date < yesterday < until_date:
            self.parse_history_forecasts(since_date=since_date, until_date=yesterday)
            self.parse_month_page(since_date=datetime.today().date(), until_date=until_date)
        return self.daily_forecasts

    def parse_month_page(self, since_date, until_date):
        """
        Парсит страницу с погодой на месяц

        :param datetime.date since_date: Начало периода прогноза
        :param datetime.date until_date: Конец периода прогноза
        """
        html = self._beautiful_soup(url=f'{self.SITE}{self.city_url}{self.PERIOD_MONTH}')
        _date_re = re.compile(pattern=r'(\d+)')
        forecast_begin = (datetime.now() - timedelta(datetime.now().weekday())).date()
        sel_first_cell = (since_date - forecast_begin).days + 1
        sel_last_cell = (until_date - forecast_begin).days + 1
        sel_cells = f'.weather-cells .cell:not(.empty):nth-child(n+{sel_first_cell}):nth-child(-n+{sel_last_cell})'

        for i, tag in enumerate(html.select(sel_cells)):
            forecast = self.daily_forecasts[since_date + timedelta(i)]
            forecast.city = self.city
            forecast.city_translit = self.city_translit
            if ', ' in tag.get('data-text', ''):
                _s = tag['data-text'].split(', ')
                forecast.cloudiness = _s[0]
                forecast.precipitations = _s[1]
            else:
                forecast.cloudiness = tag.get('data-text', '')
            forecast.day_temp = tag.select('.temp .temp_max .unit_temperature_c')[0].text
            forecast.day_temp = tag.select('.temp .temp_min .unit_temperature_c')[0].text

    def parse_diary_page(self, year, month, since_day=1, until_day=31):
        """
        Парсит одну страницу с дневником погоды
        :param int year: год дневника
        :param int month: месяц дневника
        :param int since_day: День начала периода
        :param int until_day: День окончания периода
        """
        html = self._beautiful_soup(url=self.URL_DIARY.format(self.city_id, year, month))
        since_date = datetime(year=year, month=month, day=since_day)
        self._init_diary_labels(html)
        for tr in html.select(f'tbody tr:nth-child(n+{since_day}):nth-child(-n+{until_day})'):
            cells = tr.select('td')
            handling_date = since_date.replace(day=int(cells[0].text)).date()
            forecast = self.daily_forecasts[handling_date]
            forecast.city = self.city
            forecast.city_translit = self.city_translit
            try:
                forecast.cloudiness = self.diary_labels[cells[3].find('img').get('src').split('/')[-1]]
            except AttributeError:
                pass
            except KeyError as exc:
                if exc.args[0] == 'still.gif':
                    self.daily_forecasts.pop(handling_date)
                    continue
            if cells[4].contents:
                forecast.precipitations = self.diary_labels.get(cells[4].find('img').get('src').split('/')[-1], '')
            forecast.day_temp = cells[1].text
            forecast.day_temp = cells[6].text

    def parse_history_forecasts(self, since_date, until_date):
        """
        Парсит несколько страниц дневника за указанный период
        :param datetime.date since_date: Начало периода прогноза
        :param datetime.date until_date: Конец периода прогноза
        """
        for url, year, month in self.diary_urls(since_date=since_date, until_date=until_date):
            if since_date.year == year and since_date.month == month:
                since_day = since_date.day
            else:
                since_day = 1
            if until_date.year == year and until_date.month == month:
                until_day = until_date.day
            else:
                until_day = 31
            self.parse_diary_page(year=year, month=month, since_day=since_day, until_day=until_day)


if __name__ == '__main__':
    sdate = datetime.strptime('03.02.2020', '%d.%m.%Y').date()
    udate = datetime.strptime('30.03.2020', '%d.%m.%Y').date()
    weather = WeatherMaker()
    weather.get_forecast(needle_city='Сочи', since_date=sdate, until_date=udate)
    for forecast in weather.daily_forecasts:
        print(forecast)


