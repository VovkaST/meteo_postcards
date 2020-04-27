import pathlib
import textwrap
from PIL import ImageFont, Image, ImageDraw
import cv2
import numpy as np

WORK_DIR = pathlib.Path().absolute()
IMAGES_DIR = WORK_DIR / 'images'

COLOR_YELLOW_BGR = (36, 227, 243)
COLOR_BLUE_BGR = (146, 103, 62)
COLOR_SKYBLUE_BGR = (255, 185, 119)
COLOR_GRAY_BGR = (187, 179, 171)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)

W_THUNDERSTORM = 'icon_thunderstorm'
W_SUNNY = 'icon_sunny'
W_RAINY = 'icon_rainy'
W_SNOW = 'icon_snow'
W_CLOUDY = 'icon_cloudy'


class WeatherPostcard:
    """ Класс создания открытки с прогнозом погоды """
    _icon_height = 158
    _icon_width = 145
    _template = str(IMAGES_DIR / 'template.jpg')
    _icons = str(IMAGES_DIR / 'icons_gismeteo@3x.png')
    _areas = {
        'date':           {'position': (10, 225), 'font_size': 24},
        'max_temp':       {'position': (10, 50), 'font_size': 48},
        'min_temp':       {'position': (40, 120), 'font_size': 30},
        'precipitations': {'position': (320, 100), 'font_size': 28},
    }
    _font_colors = {
        COLOR_YELLOW_BGR:  {'left': (64, 114, 183), 'right': (156, 124, 27)},
        COLOR_BLUE_BGR:    {'left': COLOR_WHITE, 'right': (115, 89, 49)},
        COLOR_SKYBLUE_BGR: {'left': COLOR_WHITE, 'right': (224, 192, 56)},
        COLOR_GRAY_BGR:    {'left': (105, 102, 91), 'right': (105, 102, 91)},
    }

    def __init__(self, font=None):
        self.image = cv2.imread(filename=self._template)
        self.weather_icon = None
        self.background_color = COLOR_WHITE
        try:
            if font is None:
                raise OSError
            self.font_path = font
        except OSError:
            self.font_path = 'arial.ttf'

    def init_postcard(self, precipitations):
        """
        Инициализация открытки:
           - создание шаблона с цветным градиентом
           - вырезание иконки погоды
           - объединение шаблона и иконки
        """
        precipitations = precipitations.lower().strip()
        icons = cv2.imread(filename=self._icons)
        if precipitations == 'гроза':
            self.background_color = COLOR_BLUE_BGR
            y, x = 147, 306
        elif precipitations in ('дождь', 'осадки', 'небольшой'):
            self.background_color = COLOR_GRAY_BGR
            y, x = 147, 3829
        elif precipitations == 'небольшой дождь':
            self.background_color = COLOR_GRAY_BGR
            y, x = 147, 4303
        elif precipitations == 'сильный дождь':
            self.background_color = COLOR_GRAY_BGR
            y, x = 147, 3361
        elif precipitations == 'снег':
            self.background_color = COLOR_SKYBLUE_BGR
            y, x = 147, 537
        elif precipitations == 'небольшой снег':
            self.background_color = COLOR_SKYBLUE_BGR
            y, x = 147, 1474
        elif precipitations == 'сильный снег':
            self.background_color = COLOR_SKYBLUE_BGR
            y, x = 147, 533
        elif precipitations in ('снег с дождём', 'мокрый снег'):
            self.background_color = COLOR_GRAY_BGR
            y, x = 147, 2416
        elif precipitations in ('переменная облачность', 'малооблачно'):
            self.background_color = COLOR_YELLOW_BGR
            y, x = 1165, 782
        elif precipitations in ('пасмурно', 'облачно'):
            self.background_color = COLOR_GRAY_BGR
            y, x = 147, 75
        else:  # Ясно
            self.background_color = COLOR_YELLOW_BGR
            y, x = 485, 320

        _icon = icons[y:y + self._icon_height, x:x + self._icon_width]  # (158, 141, 3)
        _t_img = np.zeros((190, 296, 3), dtype=np.uint8)
        _t_img[_t_img.shape[0] - _icon.shape[0]:_t_img.shape[0],
               _t_img.shape[1] - _icon.shape[1]:_t_img.shape[1]] = _icon
        self.weather_icon = _t_img
        self.draw_gradient(from_color=self.background_color, to_color=COLOR_WHITE)
        self.background_icon_overlay()

    def draw_gradient(self, from_color, to_color):
        """
        Рисование градиента на шаблоне

        :param tuple from_color: BGR-цвет начала градиента
        :param tuple to_color: BGR-цвет конца градиента
        """
        def interpolate(f_co, t_co, interval):
            det_co = [(t - f) / interval for f, t in zip(f_co, t_co)]
            for i in range(interval):
                yield [round(f + det * i) for f, det in zip(f_co, det_co)]

        for i, color in enumerate(interpolate(from_color, to_color, int(self.image.shape[1] * 1.5))):
            cv2.line(img=self.image, pt1=(i, 0), pt2=(0, i), color=tuple(color))

    def background_icon_overlay(self):
        """ Объединяет шаблон и значок погоды """
        rows, cols = self.weather_icon.shape[:2]
        roi = self.image[0:rows, 0:cols]

        img2gray = cv2.cvtColor(self.weather_icon, cv2.COLOR_BGR2GRAY)
        ret, mask = cv2.threshold(img2gray, 200, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)

        img1_bg = cv2.bitwise_and(roi, roi, mask_inv)
        # self.show_various_image(img1_bg, 'img1_bg')
        img2_fg = cv2.bitwise_and(self.weather_icon, self.weather_icon, mask)
        # self.show_various_image(img2_fg, 'img2_fg')
        dst = cv2.add(img1_bg, img2_fg)
        # self.show_various_image(dst, 'dst')
        self.image[0:rows, 0:cols] = dst

    def write_text(self, text, color=COLOR_GRAY_BGR, size=10, position=(0, 0)):
        """
        Написание текста через библиотеку PIL

        :param str text: Текст для размещения
        :param tuple color: BGR-цвет текста
        :param int size: Размер шрифта
        :param tuple position: Координаты размещения (x, y)
        """
        font = ImageFont.truetype(self.font_path, size)
        img_pil = Image.fromarray(self.image)
        draw = ImageDraw.Draw(img_pil)
        draw.text(position, text, font=font, fill=color)
        self.image = np.array(img_pil)

    def append_date(self, date):
        """
        Добавляет дату прогноза в определенную позицию

        :param str date: Дата в виде строки
        """
        self.write_text(text=date, color=self._font_colors[self.background_color]['left'],
                        size=self._areas['date']['font_size'], position=self._areas['date']['position'])

    def append_max_temp(self, temp):
        """
        Добавляет максимальную температуру в определенную позицию

        :param str temp: Температура в виде строки
        """
        self.write_text(text=f'{temp}\u00B0C', color=self._font_colors[self.background_color]['left'],
                        size=self._areas['max_temp']['font_size'], position=self._areas['max_temp']['position'])

    def append_min_temp(self, temp):
        """
        Добавляет минимальную температуру в определенную позицию

        :param str temp: Температура в виде строки
        """
        self.write_text(text=f'{temp}\u00B0C', color=self._font_colors[self.background_color]['left'],
                        size=self._areas['min_temp']['font_size'], position=self._areas['min_temp']['position'])

    def append_precipitations(self, prec):
        """
        Добавляет облачность и осадки в определенную позицию

        :param str prec: Облачность и осадки в виде строки
        """
        wraped = textwrap.wrap(prec, width=11)
        x, y = self._areas['precipitations']['position']
        for row in wraped:
            self.write_text(text=row, color=self._font_colors[self.background_color]['right'],
                            size=self._areas['precipitations']['font_size'],
                            position=(x, y))
            y += self._areas['precipitations']['font_size']

    def show_image(self):
        """ Показать открытку """
        cv2.namedWindow(winname=self.__class__.__name__, flags=cv2.WINDOW_AUTOSIZE)
        cv2.imshow(winname=self.__class__.__name__, mat=self.image)
        cv2.waitKey(delay=0)
        cv2.destroyAllWindows()

    def show_various_image(self, image, window_name=None):
        """
        Показать произвольную картинку

        :param np.array image: Картинка в формате cv2
        """
        cv2.imshow(winname=window_name or self.__class__.__name__, mat=image)
        cv2.waitKey(delay=0)
        cv2.destroyAllWindows()

    def save_file(self, path):
        cv2.imwrite(filename=str(path), img=self.image)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    postcard = WeatherPostcard()
    postcard.init_postcard(precipitations='снег')
    postcard.append_date('08.03.2020, Вс')
    postcard.append_max_temp('+9')
    postcard.append_min_temp('+4')
    postcard.append_precipitations('Переменная облачность, временами дождь')
    # postcard.show_image()
    postcard.save_file(path='2020-03-14_Kirov.png')


