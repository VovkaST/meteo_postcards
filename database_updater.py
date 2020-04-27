# Добавить класс DatabaseUpdater с методами:
#   Получающим данные из базы данных за указанный диапазон дат.
#   Сохраняющим прогнозы в базу данных (использовать peewee)

import pathlib
from datetime import datetime
import peewee
import weather_maker

DATE_FORMAT = '%d.%m.%Y'
DB_PATH = pathlib.Path().absolute() / 'db'
DB_FILE = DB_PATH / 'Weather.db'

if not pathlib.Path.is_dir(DB_PATH):
    pathlib.Path.mkdir(DB_PATH)

db_handler = peewee.SqliteDatabase(database=DB_FILE)


class DuplicateKeyError(Exception):
    pass


class NotNullValueError(Exception):
    pass


class BaseModel(peewee.Model):
    """ Базовый класс модели таблиц """
    class Meta:
        database = db_handler


class WeatherDatabase:
    """
    Класс работы с БД SQLite.
    По умолчанию 'Weather.db' создается в подкаталоге db каталога запуска скрипта.
    """

    class WeatherTable(BaseModel):
        class Meta:
            db_table = 'weather'
            primary_key = peewee.CompositeKey('city_id', 'wdate')

        city_id = peewee.IntegerField()
        city = peewee.TextField()
        city_translit = peewee.TextField()
        wdate = peewee.DateField()
        max_temp = peewee.SmallIntegerField()
        min_temp = peewee.SmallIntegerField()
        cloudiness = peewee.TextField()
        precipitations = peewee.TextField(null=True)

    def __init__(self):
        self.db = db_handler
        self.db.create_tables([self.WeatherTable])

    def weather_insert_row(self, city_id, city, city_translit, wdate, max_temp, min_temp, cloudiness, precipitations):
        """
        Добавление записи в таблицу погоды. Если запись за дату существует, обновляет показатели.
        """
        try:
            self.WeatherTable.create(city_id=city_id, city=city, city_translit=city_translit, wdate=wdate,
                                     max_temp=max_temp, min_temp=min_temp,
                                     cloudiness=cloudiness, precipitations=precipitations)
        except peewee.IntegrityError as exc:
            if 'UNIQUE constraint failed' in exc.args[0]:
                raise DuplicateKeyError
            elif 'NOT NULL constraint failed' in exc.args[0]:
                raise NotNullValueError

    def weather_update_row(self, city_id, wdate, max_temp, min_temp, cloudiness, precipitations):
        """
        Добавление записи в таблицу погоды. Если запись за дату существует, обновляет показатели.
        """
        try:
            self.WeatherTable \
                .update(max_temp=max_temp, min_temp=min_temp, cloudiness=cloudiness, precipitations=precipitations) \
                .where(self.WeatherTable.city_id == city_id, self.WeatherTable.wdate == wdate) \
                .execute()
        except peewee.IntegrityError as exc:
            if 'NOT NULL constraint failed' in exc.args[0]:
                raise NotNullValueError

    def get_day_weather(self, city_id, wdate):
        """
        Выбрать запись за дату wdate в городе city_id

        :type city_id: int
        :type wdate: datetime.date
        :rtype: peewee.ModelSelect
        """
        return self.WeatherTable\
                   .select()\
                   .where(self.WeatherTable.wdate == wdate,
                          self.WeatherTable.city_id == city_id)

    def get_period_weather(self, city_id, since_date, until_date):
        """
        Выбрать запись за диапазон дат с since_date по until_date в городе city_id

        :type city_id: int
        :type since_date: datetime.date
        :type until_date: datetime.date
        :rtype: peewee.ModelSelect
        """
        return self.WeatherTable\
                   .select() \
                   .where(self.WeatherTable.wdate.between(since_date, until_date),
                          self.WeatherTable.city_id == city_id) \
                   .order_by(self.WeatherTable.wdate)

    @staticmethod
    def row_to_forecast(row):
        """
        Преобразует строку таблицы Weather в объект Forecast

        :param WeatherTable row: Строка таблицы Weather
        :return: Объект Forecast
        """
        _fc = weather_maker.Forecast()
        _fc.city = row.city
        _fc.city_translit = row.city_translit
        _fc.set_date(date=row.wdate)
        _fc.cloudiness = row.cloudiness
        _fc.precipitations = row.precipitations
        _fc.day_temp = row.max_temp
        _fc.day_temp = row.min_temp
        return _fc


if __name__ == '__main__':
    sdate = datetime.strptime('01.01.2020', DATE_FORMAT).date()
    udate = datetime.strptime('30.03.2020', DATE_FORMAT).date()
    db_updater = WeatherDatabase()
    for row in db_updater.get_period_weather(since_date=sdate, until_date=udate, city_id=5233):
        print(row)
