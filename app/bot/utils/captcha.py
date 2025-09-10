import typing as t
from io import BytesIO

from aiogram.types import BufferedInputFile
from multicolorcaptcha import CaptchaGenerator


async def generate_captcha() -> t.Tuple[BufferedInputFile, str]:
    generator = CaptchaGenerator(2)
    captcha = generator.gen_captcha_image(difficult_level=2, margin=False)
    captcha_image = captcha.image

    buffer = BytesIO()
    captcha_image.save(buffer, format="PNG")
    buffer.seek(0)

    image = BufferedInputFile(buffer.read(), filename="captcha.png")
    characters = captcha.characters
    return image, characters
