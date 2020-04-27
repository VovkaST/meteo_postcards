import argparse
import pathlib
import re
from datetime import datetime

from weather_maker import WeatherMaker
from database_updater import WeatherDatabase, NotNullValueError, DuplicateKeyError
import weather_postcard

WORK_DIR = pathlib.Path().absolute()


class WeatherConsole:
    """ Консольное приложение печати прогноза погоды """
    RE_DATE = re.compile(pattern=r'(udate|sdate)=(([0-2]\d|3[01])\.(0[1-9]|1[0-2])\.(199\d|20[0-2]\d))',
                         flags=re.IGNORECASE)
    RE_DB = re.compile(pattern=r'(db_save|db_src|db_update)=(true|false)', flags=re.IGNORECASE)
    RE_CITY = re.compile(pattern=r'city=(".*"|[\w\-]*)', flags=re.IGNORECASE)
    DATE_FORMAT = '%d.%m.%Y'

    def __init__(self):
        self.db_save = True
        self.db_update = True
        self.db_src = False
        self._sdate = None
        self._udate = None
        self.parser = None
        self.weather = WeatherMaker()
        self.db = WeatherDatabase()

    def __str__(self):
        _s = 'Параметры работы:\n'
        for attr in ['city', 'sdate', 'udate', 'db_save', 'db_src', 'db_update']:
            _s += f'  {attr} = {getattr(self, attr)}\n'
        return _s

    @property
    def city_id(self):
        return self.weather.city_id or ''

    @property
    def city(self):
        return self.weather.city or ''

    @city.setter
    def city(self, city):
        self.weather.init_city_url(needle_city=city)

    @property
    def sdate(self):
        if self._sdate is not None:
            return self._sdate

    @sdate.setter
    def sdate(self, sdate):
        try:
            self._sdate = datetime.strptime(sdate, self.DATE_FORMAT).date()
        except ValueError as exc:
            print(exc.args[0])

    @property
    def udate(self):
        if self._udate is not None:
            return self._udate

    @udate.setter
    def udate(self, udate):
        try:
            self._udate = datetime.strptime(udate, self.DATE_FORMAT).date()
        except ValueError as exc:
            print(exc.args[0])

    def collect_forecasts(self):
        if self.db_src:
            for row in self.db.get_period_weather(city_id=self.city_id, since_date=self.sdate, until_date=self.udate):
                _f = {row.wdate: self.db.row_to_forecast(row=row), }
                self.weather.daily_forecasts.update(_f)
        else:
            self.weather.get_forecast(needle_city=self.weather.city,
                                      since_date=self.sdate, until_date=self.udate)

    def parse(self):
        """ Парсинг параметров запуска """
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('-city', type=str, help='Город')
        self.parser.add_argument('-sdate', type=str, help='Начало периода прогноза в формате dd.mm.yyyy')
        self.parser.add_argument('-udate', type=str, help='Конец периода прогноза в формате dd.mm.yyyy')
        self.parser.add_argument('-db_src', type=bool, default=False,
                                 help='Пометка, источник - БД')
        self.parser.add_argument('-db_save', type=bool, default=True,
                                 help='Пометка о необходимости сохранения данных в БД')
        self.parser.add_argument('-db_update', type=bool, default=True,
                                 help='Пометка о необходимости обновления данных в БД')
        self.parser.parse_args(namespace=self)
        if self.sdate is None:
            self.cons_parse()
        else:
            self.show_forecast()

    def set_needles(self, command_line):
        """
        Установка значений параметров

        :param str command_line: Консольная команда
        """
        result = False
        match = re.findall(pattern=self.RE_DATE, string=command_line)
        if match:
            result = True
            for attrs in match:
                setattr(self, attrs[0].lower(), attrs[1])
        match = re.findall(pattern=self.RE_DB, string=command_line)
        if match:
            result = True
            for attrs in match:
                setattr(self, attrs[0].lower(), True if attrs[1] == 'true' else False)
        match = re.findall(pattern=self.RE_CITY, string=command_line)
        if match:
            result = True
            self.city = match[0]
        return result

    def show_available_cities(self):
        """ Печать списка доступных городов """
        print('Список доступных городов:')
        for item in self.weather.cities_catalog:
            print(f'  {item["name"]}')

    def save_forecasts(self):
        """ Сохранение прогнозов в БД """
        for date, forecast in self.weather.daily_forecasts.items():
            try:
                self.db.weather_insert_row(wdate=date,
                                           city_translit=forecast.city_translit, city_id=self.city_id, city=self.city,
                                           **forecast.to_dict())
            except DuplicateKeyError:
                if self.db_update:
                    self.db.weather_update_row(wdate=date, city_id=self.city_id, **forecast.to_dict())
            except NotNullValueError:
                pass

    def show_forecast(self):
        """ Печать прогнозов в консоль """
        self.collect_forecasts()
        if self.weather.daily_forecasts:
            print(f'{self.city}: прогноз погоды')
            for date, forecast in self.weather.daily_forecasts.items():
                print(forecast.print())
        else:
            print(f'Данные по прогнозу погоды в городе {self.city} за запрашиваемый период отсутствуют')

    def make_postcards(self):
        """ Печать открытки с прогнозом погоды """

        self.collect_forecasts()
        if self.weather.daily_forecasts:
            cards_path = WORK_DIR / 'postcards'
            if not pathlib.Path.is_dir(cards_path):
                pathlib.Path.mkdir(cards_path)
            for date, forecast in self.weather.daily_forecasts.items():
                _date = datetime.strptime(forecast.date, '%d.%m.%Y').strftime('%Y-%m-%d')
                postcard = weather_postcard.WeatherPostcard()
                postcard.init_postcard(precipitations=forecast.precipitations or forecast.cloudiness)
                postcard.append_date(f'{forecast.date}, {forecast.week_day}')
                postcard.append_max_temp(forecast.day_temp_max)
                postcard.append_min_temp(forecast.day_temp_min)
                postcard.append_precipitations(forecast.cloud_precip)
                postcard.save_file(path=cards_path / f'{forecast.city_translit.capitalize()}_{_date}.png')
        else:
            print(f'Данные по прогнозу погоды в городе {self.city} за запрашиваемый период отсутствуют')

    def help(self):
        self.parser.print_help()
        print('additional interactive mode arguments:')
        print('  show_needles      Показать текущие настройки')
        print('  show_cities       Показать города для получения прогноза')
        print('  forecast          Получить прогноз в соответствии с текущими настройками в текстовом виде')
        print('  postcards         Получить прогноз в соответствии с текущими настройками в виде открыток')
        print('  exit              Завершение работы')
        print('В интерактивном режиме также возможно использование основных аргументов.')
        print()

    def cons_parse(self):
        """ Работа с программой в консоли """
        while True:
            command = input(f'{self.__class__.__name__} > ').strip().lower()
            if command == 'exit':
                print('До свидания! Спасибо за использование приложения!')
                break
            elif command in ('?', 'help'):
                self.help()
            elif command == 'show_needles':
                print(self)
            elif command == 'show_cities':
                self.show_available_cities()
            elif command == 'forecast':
                self.show_forecast()
                if self.db_save and not self.db_src:
                    self.save_forecasts()
            elif command == 'postcards':
                self.make_postcards()
                if self.db_save and not self.db_src:
                    self.save_forecasts()
            else:
                if not self.set_needles(command_line=command):
                    self.help()


if __name__ == '__main__':
    parser = WeatherConsole()
    parser.cons_parse()
