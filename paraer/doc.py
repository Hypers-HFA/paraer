# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
import re
import json

from openapi_codec import encode
from openapi_codec.encode import generate_swagger_object as _generate_swagger_object
from coreapi.compat import force_bytes
from rest_framework.schemas import SchemaGenerator as _SchemaGenerator
from rest_framework.compat import coreapi
from rest_framework.renderers import JSONRenderer
from rest_framework_swagger.renderers import OpenAPICodec as _OpenAPICodec, OpenAPIRenderer as _OpenAPIRenderer
from rest_framework import status
from openapi_codec.encode import _get_links
from django.db import models

RE_PATH = re.compile('\{(\w+)\}')  # extract  /{arg1}/{arg2}  to [arg1, arg2]


class SchemaGenerator(_SchemaGenerator):
    def get_description(self, path, method, view):
        method_name = getattr(view, 'action', method.lower())
        method = getattr(view, method_name, None)
        doc = method.__doc__
        self.swagger = getattr(method, '__swagger__',
                               {})  # para_ok_or_400中生成的__swagger__
        return doc

    def get_swagger_fields(self, path, method, view):
        path_args = set(RE_PATH.findall(path))
        parameters = self.swagger.get('parameters', [])
        fields = tuple(
            coreapi.Field(
                name=x['name'],
                location=(x['name'] in path_args and 'path') or x['in'],
                required=x['name'] in path_args or x.get('required', False),
                description=x['description'],
                type=x['type']) for x in parameters)
        return fields

    def get_link(self, path, method, view):
        """
        Return a `coreapi.Link` instance for the given endpoint.
        """
        link = super(SchemaGenerator, self).get_link(path, method, view)
        swagger_fields = self.get_swagger_fields(path, method, view)
        nameset = {x.name for x in swagger_fields}
        fields = tuple((x for x in link.fields if x.name not in nameset)) + swagger_fields
        link = coreapi.Link(
            url=link.url,
            action=link.action,
            encoding=link.encoding,
            fields=fields,
            description=link.description)
        link.__serializer__ = getattr(
            view, 'serializer_class',
            None)  # Link是不可变的数据结构。。。所以覆盖带下划线的属性,以绕过这个限制
        link.__action__ = getattr(view, 'action', None)
        return link


class OpenAPICodec(_OpenAPICodec):
    def encode(self, document, extra=None, **options):
        if not isinstance(document, coreapi.Document):
            raise TypeError('Expected a `coreapi.Document` instance')

        data = generate_swagger_object(document)
        if isinstance(extra, dict):
            data.update(extra)

        return force_bytes(json.dumps(data))


class OpenAPIRenderer(_OpenAPIRenderer):
    media_type = 'application/openapi+json'
    charset = None
    format = 'openapi'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context['response'].status_code != status.HTTP_200_OK:
            return JSONRenderer().render(data)
        extra = self.get_customizations()

        return OpenAPICodec().encode(data, extra=extra)


def generate_swagger_object(document):
    """
    为了生成definitions对象
    """
    swagger = _generate_swagger_object(document)
    links = _get_links(document)
    dataset = dict((serializergeter(link.__serializer__))
                   for operation_id, link, tags in links
                   if (hasattr(link.__serializer__, 'Meta')
                       or hasattr(link.__serializer__, '_meta')))
    swagger['definitions'] = dataset

    return swagger


def _namer(field):
    field = field.__class__.__name__.lower().split('field')[0]
    if field.endswith('serializer'):
        return 'serializer'
    return field


def _callback(field):
    name = _namer(field)
    key = field.name

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

    def url(field):
        return dict(type='string')

    def text(field):
        return dict(type='string')

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
    data['description'] = str(field.verbose_name)
    if field.choices:
        data['enum'] = [x[0] for x in field.choices]
    return data


def serializergeter(serializer):
    if not issubclass(serializer, models.Model):
        model = serializer.Meta.model
    else:
        model = serializer
    obj_name = model._meta.object_name.lower()
    fields = model._meta.fields
    names = (x.name for x in fields)
    properties = {x: _callback(y) for x, y in zip(names, fields)}
    obj = dict(properties=properties, type='object')
    return obj_name, obj


def _get200(link):
    serializer = link.__serializer__
    tpl = dict(description='Success')
    obj_name = ''
    if hasattr(serializer, '_meta'):
        obj_name = str(serializer._meta.object_name).lower()
    elif hasattr(serializer, 'Meta'):
        obj_name = str(serializer.Meta.model._meta.object_name).lower()
    ref = {"$ref": "#/definitions/{}".format(obj_name)}
    if link.__action__ == 'list':
        tpl['schema'] = dict(items=ref, type='array')
    else:
        tpl['schema'] = ref
    return tpl


def _get400(link):
    tpl = dict(description='Bad Request')
    return tpl


def _get403(link):
    tpl = dict(description='Forbidden')
    return tpl


def _get_responses(link):
    """
    Returns minimally acceptable responses object based
    on action / method type.
    """
    response_template = {
        '200': _get200(link),
        '400': _get400(link),
        '403': _get403(link)
    }
    if link.action.lower() == 'delete':
        response_template.pop('200')
        response_template.update({'204': {'description': 'Success'}})

    return response_template


encode._get_responses = _get_responses
