# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
import re

from openapi_codec import encode
from openapi_codec.encode import generate_swagger_object as _generate_swagger_object
from rest_framework.schemas import AutoSchema as Schema
from rest_framework.compat import coreapi
from openapi_codec.encode import _get_links
from django.db import models

from .fields import _get_properties, _callback

RE_PATH = re.compile('\{(\w+)\}')  # extract  /{arg1}/{arg2}  to [arg1, arg2]


class SwaggerSchema(Schema):
    def get_swagger_fields(self, path, method):
        view = getattr(self.view, method.lower(), None)  #APIView
        if not view:
            view = getattr(self.view, self.view.action, None)  # ViewSet
        swagger = getattr(view, '__swagger__',
                          {})  # para_ok_or_400中生成的__swagger__
        path_args = {x for x in RE_PATH.findall(path)}
        parameters = swagger.get('parameters', [])
        fields = tuple(
            coreapi.Field(
                name=x['name'],
                location=(x['name'] in path_args and 'path') or x['in'],
                required=x['name'] in path_args or x.get('required', False),
                description=x['description'],
                type=x['type']) for x in parameters)
        return fields

    def get_link(self, path, method, base_url):
        """
        Return a `coreapi.Link` instance for the given endpoint.
        """
        base_url = None  # 当设置url时，生成的path中应该不带url
        link = super(SwaggerSchema, self).get_link(path, method, base_url)
        swagger_fields = self.get_swagger_fields(path, method)
        nameset = {x.name for x in swagger_fields}
        fields = tuple(
            (x for x in link.fields
             if (x.name not in nameset and x.name != 'id'))) + swagger_fields
        link = coreapi.Link(
            url=link.url,
            action=link.action,
            encoding=link.encoding,
            fields=fields,
            description=link.description)
        link.__serializer__ = getattr(
            self.view, 'serializer_class',
            None)  # Link是不可变的数据结构。。。所以覆盖带下划线的属性,以绕过这个限制
        return link


def wrap_generator(func):
    def inner(document):
        swagger = _generate_swagger_object(document)
        links = _get_links(document)
        result = {}
        [
            serializergeter(link[1].__serializer__, result) for link in links
            if getattr(link[1], '__serializer__', None)
        ]
        swagger['definitions'] = result
        return swagger

    return inner


def _get_serializer_name(serializer):
    if 'Serializer' in serializer.__name__:
        obj_name = serializer.__name__.split('Serializer')[0]
    else:
        obj_name = serializer.__name__
    return obj_name


def serializergeter(serializer, result):
    obj_name = _get_serializer_name(serializer)
    if obj_name in result:
        return
    result[obj_name] = None
    if issubclass(serializer, models.Model):
        model = serializer
    elif hasattr(serializer, 'Meta'):
        if hasattr(serializer.Meta, 'model'):
            model = serializer.Meta.model
    else:  # set user model
        data = serializer().data
        properties = _get_properties(data, [])
        result[obj_name] = properties
        return
    fields = model._meta.get_fields()
    for x in fields:
        if getattr(x, 'remote_field', ''):
            serializergeter(x.related_model, result)

    names = (x.name for x in fields)
    properties = {x: _callback(y) for x, y in zip(names, fields)}
    obj = dict(properties=properties, type='object')
    result[obj_name] = obj


def _get200(link):
    serializer = getattr(link, '__serializer__', None)
    tpl = dict(description='Success')
    if not serializer:
        return tpl
    obj_name = ''
    if hasattr(serializer, '_meta'):
        obj_name = str(serializer._meta.object_name).lower()
    elif hasattr(serializer, 'Meta'):
        obj_name = _get_serializer_name(serializer)
    ref = {"$ref": "#/definitions/{}".format(obj_name)}
    if link.action == 'get' and '{' not in link.url:  # list view
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


def patch_all():
    import rest_framework
    rest_framework.schemas.AutoSchema = SwaggerSchema
    encode._get_responses = _get_responses
    encode.generate_swagger_object = wrap_generator(_generate_swagger_object)
