# encoding: utf-8
from __future__ import unicode_literals
from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.renderers import CoreJSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_swagger import renderers


def get_swagger_view(title=None, url=None, patterns=None, urlconf=None):
    """
    Returns schema view which renders Swagger/OpenAPI.
    """

    from .doc import SchemaGenerator

    class SwaggerSchemaView(APIView):
        _ignore_model_permissions = True
        exclude_from_schema = True
        permission_classes = [AllowAny]
        renderer_classes = [
            CoreJSONRenderer, renderers.OpenAPIRenderer,
            renderers.SwaggerUIRenderer
        ]

        def get(self, request, a_url=None):
            url_temp = url
            urlconf_temp = urlconf
            if a_url:
                urlconf_temp = '.'.join([a_url, 'urls'])
                url_temp = '/' + a_url

            generator = SchemaGenerator(
                title=title,
                url=url_temp,
                patterns=patterns,
                urlconf=urlconf_temp)
            schema = generator.get_schema(request=request)

            if not schema:
                raise exceptions.ValidationError(
                    'The schema generator did not return a schema Document')

            return Response(schema)

    return SwaggerSchemaView.as_view()
