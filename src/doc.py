# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
import re
from collections import OrderedDict

import coreschema
from rest_framework.schemas import SchemaGenerator as _SchemaGenerator
from rest_framework.compat import coreapi, urlparse
from openapi_codec.encode import _get_links
from django.db import models

from .settings import swagger_settings

RE_PATH = re.compile('\{(\w+)\}')  # extract  /{arg1}/{arg2}  to [arg1, arg2]


class SchemaGenerator(_SchemaGenerator):
    def get_description(self, path, method, view):
        method_name = getattr(view, 'action', method.lower())
        method = getattr(view, method_name, None)
        doc = method.__doc__
        self.swagger = getattr(method, '__swagger__', {})
        return doc

    def get_swagger_fields(self, path, method, view):
        """获取swagger中的fields, 若 field name 在path中，则localtion=path"""
        path_args = set(RE_PATH.findall(path))
        parameters = self.swagger.get('parameters', {})

        fields = [
            coreapi.Field(
                name=x['name'],
                location=(x['name'] in path_args and 'path') or x['in'],
                required=x['name'] in path_args or x.get('required', False),
                description=x['description'],
                type=x['type']) for x in parameters
        ]
        return fields

    def get_link(self, path, method, view):
        """
        Return a `coreapi.Link` instance for the given endpoint.
        """
        fields = []
        encoding = None

        description = self.get_description(path, method, view)
        fields += self.get_serializer_fields(path, method, view)
        fields += self.get_pagination_fields(path, method, view)
        fields += self.get_filter_fields(path, method, view)
        fields += self.get_swagger_fields(path, method, view)
        if fields and any(
                field.location in ('formData', 'body') for field in fields):
            encoding = self.get_encoding(path, method, view)
            encoding = 'application/x-www-form-urlencoded'  # 返回表单形式
        else:
            encoding = None

        if self.url and path.startswith('/'):
            path = path[1:]

        link = coreapi.Link(
            url=urlparse.urljoin(self.url, path),
            action=method.lower(),
            encoding=encoding,
            fields=fields,
            description=description)
        link.__serializer__ = getattr(view, 'serializer_class',
                                      None)  # Link是不可变的数据结构。。。
        link.__action__ = getattr(view, 'action', None)
        return link

    def get_links(self, request=None):
        """
        Return a dictionary containing all the links that should be
        included in the API schema.
        """
        links = OrderedDict()

        # Generate (path, method, view) given (path, method, callback).
        paths = []
        view_endpoints = []
        for path, method, callback in self.endpoints:
            view = self.create_view(callback, method, request)
            if getattr(view, 'exclude_from_schema', False):
                continue
            paths.append(path)
            view_endpoints.append((path, method, view))

        # Only generate the path prefix for paths that will be included
        if not paths:
            return None
        prefix = self.determine_path_prefix(paths)

        for path, method, view in view_endpoints:
            if not self.has_view_permissions(path, method, view):
                continue
            link = self.get_link(path, method, view)
            subpath = path[len(prefix):]
            keys = self.get_keys(subpath, method, view)
            insert_into(links, keys, link)
        return links

    def get_keys(self, subpath, method, view):
        """
        Return a list of keys that should be used to layout a link within
        the schema document.

        /users/                   ("users", "list"), ("users", "create")
        /users/{pk}/              ("users", "read"), ("users", "update"), ("users", "delete")
        /users/enabled/           ("users", "enabled")  # custom viewset list action
        /users/{pk}/star/         ("users", "star")     # custom viewset detail action
        /users/{pk}/groups/       ("users", "groups", "list"), ("users", "groups", "create")
        /users/{pk}/groups/{pk}/  ("users", "groups", "read"), ("users", "groups", "update"), ("users", "groups", "delete")
        """
        if hasattr(view, 'action'):
            # Viewsets have explicitly named actions.
            action = view.action
        else:
            # Views have no associated action, so we determine one from the method.
            if is_list_view(subpath, method, view):
                action = 'list'
            else:
                action = self.default_mapping[method.lower()]

        named_path_components = [
            component for component in subpath.strip('/').split('/')
            if '{' not in component
        ]

        if is_custom_action(action):
            # Custom action, eg "/users/{pk}/activate/", "/users/active/"
            action = self.default_mapping[method.lower()]
            if action in self.coerce_method_names:
                action = self.coerce_method_names[action]
            return named_path_components + [action]

        if action in self.coerce_method_names:
            action = self.coerce_method_names[action]

        # Default action, eg "/users/", "/users/{pk}/"
        return named_path_components + [action]


def generate_swagger_object(document):
    """
    Generates root of the Swagger spec.
    """
    parsed_url = urlparse.urlparse(document.url)

    swagger = OrderedDict()

    swagger['swagger'] = '2.0'
    swagger['info'] = OrderedDict()
    swagger['info']['title'] = document.title
    swagger['info'][
        'version'] = swagger_settings.VERSION or ''  # Required by the spec

    if parsed_url.netloc:
        swagger['host'] = parsed_url.netloc
    if parsed_url.scheme:
        swagger['schemes'] = [parsed_url.scheme]

    swagger['paths'] = _get_paths_object(document)
    links = _get_links(document)
    dataset = dict((serializergeter(link.__serializer__))
                   for operation_id, link, tags in links
                   if (hasattr(link.__serializer__, 'Meta') or hasattr(link.__serializer__, '_meta')))
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


def _get_paths_object(document):
    paths = OrderedDict()

    links = _get_links(document)

    for operation_id, link, tags in links:
        if link.url not in paths:
            paths[link.url] = OrderedDict()

        method = get_method(link)
        operation = _get_operation(operation_id, link, tags)
        paths[link.url].update({method: operation})

    return paths


def _get_operation(operation_id, link, tags):
    encoding = get_encoding(link)
    description = link.description.strip()
    summary = description.splitlines()[0] if description else None

    operation = {
        'operationId': operation_id,
        'responses': _get_responses(link),
        'parameters': _get_parameters(link, encoding)
    }

    if description:
        operation['description'] = description
    if summary:
        operation['summary'] = summary
    if encoding:
        operation['consumes'] = [encoding]
    if tags:
        operation['tags'] = tags
    return operation


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


def _get_parameters(link, encoding):
    """
    Generates Swagger Parameter Item object.
    """
    parameters = []
    properties = {}
    required = []

    for field in link.fields:
        location = field.location
        field_description = _get_field_description(field)
        field_type = _get_field_type(field)
        if location == 'formData':
            if encoding in ('multipart/form-data',
                            'application/x-www-form-urlencoded'):
                # 'formData' in swagger MUST be one of these media types.
                parameter = {
                    'name': field.name,
                    'required': field.required,
                    'in': 'formData',
                    'description': field_description,
                    'type': field_type,
                }
                if field_type == 'array':
                    parameter['items'] = {'type': 'string'}
                parameters.append(parameter)
            else:
                # Expand coreapi fields with location='form' into a single swagger
                # parameter, with a schema containing multiple properties.

                schema_property = {
                    'description': field_description,
                    'type': field_type,
                }
                if field_type == 'array':
                    schema_property['items'] = {'type': 'string'}
                properties[field.name] = schema_property
                if field.required:
                    required.append(field.name)
        elif location == 'body':
            if encoding == 'application/octet-stream':
                # https://github.com/OAI/OpenAPI-Specification/issues/50#issuecomment-112063782
                schema = {'type': 'string', 'format': 'binary'}
            else:
                schema = {}
            parameter = {
                'name': field.name,
                'required': field.required,
                'in': location,
                'description': field_description,
                'schema': schema
            }
            parameters.append(parameter)
        else:
            parameter = {
                'name': field.name,
                'required': field.required,
                'in': location,
                'description': field_description,
                'type': field_type or 'string',
            }
            if field_type == 'array':
                parameter['items'] = {'type': 'string'}
            parameters.append(parameter)

    if properties:
        parameter = {
            'name': 'data',
            'in': 'body',
            'schema': {
                'type': 'object',
                'properties': properties
            }
        }
        if required:
            parameter['schema']['required'] = required
        parameters.append(parameter)

    return parameters


def get_method(link):
    method = link.action.lower()
    if not method:
        method = 'get'
    return method


def get_encoding(link):
    encoding = link.encoding
    has_body = any(
        [field.location in ('formData', 'body') for field in link.fields])
    if not encoding and has_body:
        encoding = 'application/json'
    elif encoding and not has_body:
        encoding = ''
    return encoding


def _get_field_description(field):
    if getattr(field, 'description', None) is not None:
        # Deprecated
        return field.description

    if field.schema is None:
        return ''

    return field.schema.description


def _get_field_type(field):
    if getattr(field, 'type', None) is not None:
        # Deprecated
        return field.type

    if field.schema is None:
        return 'string'

    return {
        coreschema.String: 'string',
        coreschema.Integer: 'integer',
        coreschema.Number: 'number',
        coreschema.Boolean: 'boolean',
        coreschema.Array: 'array',
        coreschema.Object: 'object',
    }.get(field.schema.__class__, 'string')


def insert_into(target, keys, value):
    for key in keys[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]
    target[keys[-1]] = value


def is_custom_action(action):
    return action not in set(
        ['retrieve', 'list', 'create', 'update', 'partial_update', 'destroy'])


def is_list_view(path, method, view):
    """
    Return True if the given path/method appears to represent a list view.
    """
    if hasattr(view, 'action'):
        # Viewsets have an explicitly defined action, which we can inspect.
        return view.action == 'list'

    if method.lower() != 'get':
        return False
    path_components = path.strip('/').split('/')
    if path_components and '{' in path_components[-1]:
        return False
    return True
