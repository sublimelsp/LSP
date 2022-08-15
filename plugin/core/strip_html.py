from html.parser import HTMLParser
from .types import List


class MLRemover(HTMLParser):
    def __init__(self) -> None:
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []  # type: List[str]

    def handle_data(self, data: str) -> None:
        self.fed.append(data)

    def handle_entityref(self, name: str) -> None:
        self.fed.append('&{name};'.format(name=name))

    def handle_charref(self, name: str) -> None:
        self.fed.append('&#{name};'.format(name=name))

    def get_data(self) -> str:
        return ''.join(self.fed)


def strip_html(value: str) -> str:
    remover = MLRemover()
    remover.feed(value)
    remover.close()
    return remover.get_data()
