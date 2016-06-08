import logging

logger = logging.getLogger('aioesl')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s', datefmt='%d/%m/%y %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)