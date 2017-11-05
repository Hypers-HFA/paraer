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


class MethodProxy(object):
    def auto(self, field):
        return dict(format='int64', type='integer')

    def integer(self, field):
        return dict(format='int64', type='integer')

    def smallinteger(self, field):
        return dict(format='int64', type='integer')

    def boolean(self, field):
        return dict(type='string')

    def decimal(self, field):
        return dict(format='int64', type='float')

    def char(self, field):
        return dict(type='string')

    string = char

    def url(self, field):
        return dict(type='string')

    def text(self, field):
        return dict(type='string')

    def file(self, field):
        return dict(type='file')

    def datetime(self, field):
        return dict(format='date-time', type='string')

    date = datetime

    def choice(self, field):
        enum = field.choice_strings_to_values.keys()
        return dict(type='string', enum=enum)

    def nestedserializer(self, field):
        return dict(type='object', description='point to self')

    def email(self, field):
        return dict(type='string', format='email')

    def primarykeyrelated(self, field):
        return {'$ref': '#/definitions/{}'.format(key)}

    serializer = primarykeyrelated

    def onetoone(self, field):
        return {
            '$ref':
            '#/definitions/{}'.format(field.related_model._meta.object_name)
        }

    def manytomanyrel(self, field):
        return {
            '$ref':
            '#/definitions/{}'.format(field.related_model._meta.object_name)
        }

    manytomany = onetoonerel = manytoonerel = foreignkey = onetoone

    def image(self, field):
        return dict(type='file')

    def serializermethod(self, field):
        return dict(type='string')


proxy = MethodProxy()


def _get_description(field):
    description = getattr(field, 'verbose_name', None)
    if description is None:
        description = field.remote_field.verbose_name
    return str(description)


def _callback(field):
    if field:
        name = _namer(field)
    if name == 'onetoonerel':
        field = field.remote_field
    data = getattr(proxy, name, proxy.text)(field)
    if name == 'manytomanyrel':
        field = field.remote_field
    data['description'] = _get_description(field)
    if not isinstance(data['description'], str):
        import ipdb; ipdb.set_trace(context=30)
    if hasattr(field, 'choices') and field.choices:
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
