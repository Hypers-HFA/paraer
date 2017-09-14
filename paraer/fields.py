# encoding: utf-8
from __future__ import unicode_literals, print_function


class Field(object):
    def __init__(self, name, description=None, choices=None, format='string'):
        self.name = name
        self.choices = None
        self.verbose_name = description
        self.format = format
        self.__class__.__name__ = name.capitalize() + 'Field'


def _namer(field):
    field = field.__class__.__name__.lower().split('field')[0]
    if field.endswith('serializer'):
        return 'serializer'
    return field


def _callback(field=None, key=None):
    if field:
        name = _namer(field)
        key = field.name
    else:
        name = key

    def auto(field):
        return dict(format='int64', type='integer')

    def integer(field):
        return dict(format='int64', type='integer')

    def smallinteger(field):
        return dict(format='int64', type='integer')

    def boolean(field):
        return dict(type='string')

    def decimal(field):
        return dict(format='int64', type='float')

    def char(field):
        return dict(type='string')

    string = char

    def url(field):
        return dict(type='string')

    def text(field):
        return dict(type='string')

    def file(field):
        return dict(type='file')

    def datetime(field):
        return dict(format='date-time', type='string')

    date = datetime

    def choice(field):
        enum = field.choice_strings_to_values.keys()
        return dict(type='string', enum=enum)

    def nestedserializer(field):
        return dict(type='object', description='point to self')

    def email(field):
        return dict(type='string', format='email')

    def primarykeyrelated(field):
        return {'$ref': '#/definitions/{}'.format(key)}

    def image(field):
        return dict(type='file')

    onetoone = serializer = foreignkey = primarykeyrelated

    def serializermethod(field):
        return dict(type='string')

    data = locals()[name](field)
    data['description'] = field and str(field.verbose_name) or key
    if field and field.choices:
        data['enum'] = [x[0] for x in field.choices]
    return data


def _get_properties(data, key=None):
    result = {}
    if isinstance(data, dict):
        result = dict(type='object')
        properties = {}
        for key, value in data.items():
            if isinstance(value, dict):
                properties[key] = _get_properties(value)
            elif isinstance(value, list):
                properties[key] = dict(
                    type='array', items=_get_properties(value))
            else:
                if not isinstance(value, Field):
                    field = Field(value, description=value)
                properties[key] = _callback(field)
        result['properties'] = properties
    if isinstance(data, list):
        result = []
        for value in data:
            if isinstance(value, dict):
                result.append(_get_properties(value))
            elif isinstance(value, dict):
                result.append(dict(type='array', items=_get_properties(value)))
            else:
                if not isinstance(value, Field):
                    field = Field(value, description=value)
                result.append(_callback(field))
    return result
