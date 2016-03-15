from setuptools import setup, find_packages

setup(
    name="aioesl",
    version="0.1.3.3",
    license='BSD',
    description="asyncio based protocol for the FreeSWITCH's Event Socket",
    author="Alexey Panyovin",
    author_email='a@runtel.ru',
    url="https://github.com/runtel/aioesl",
    packages=['aioesl'],
    # py_modules=["aioesl"],
    zip_safe = False,
)