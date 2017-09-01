# encoding: utf-8
from paraer.fields import _get_properties

from yaml import dump


def main():
    response = dict(uv=[dict(a='string'), dict(b='datetime')])
    res = _get_properties(response)
    print(dump(res))


if __name__ == '__main__':
    main()
