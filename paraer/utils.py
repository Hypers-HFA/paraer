from __future__ import unicode_literals
try:
    import markdown
    has_markdown = True
except ImportError:
    print('please install markdown')
    print('pip instlal markdown')
    has_markdown = False
from .doc import SchemaGenerator


def doc_creator(title='',
                url=None,
                patterns=None,
                urlconf=None,
                querystring=''):
    from django.test import RequestFactory
    from rest_framework import compat
    request = RequestFactory()
    request = request.request(QUERY_STRING=compat.urlparse.urlencode(querystring))
    schema = SchemaGenerator(
        title=title, url=url, patterns=patterns, urlconfi=urlconf).get_schema(
            request=request)
    MarkdownDocFactory(schema.content, request=request, title=title)


class MarkdownDocFactory(object):
    def __init__(self, links, request, title):
        self.field_string = '|{field}|{dec}|{param_type}|{paramter_type}|{required}|\n'
        self.request = request
        self.title = title
        self.url_md_template = '''
## {url}
### 方法:{action}
### 介绍:
    {description}
|字段|说明|数据类型|HTTP参数类型|是否必填|
|:--:|:--:|:------:|:------:|:------:|
'''
        self.links = links

    def _create_url_md(self):
        url_md_list = []
        filter = self.request.GET.get('filter')
        if filter:
            self.links = [x for x in self.links if filter in x.url]
        no = self.request.GET.get('no')
        if no:
            self.links = [x for x in self.links if no not in x.url]
        for link in self.links:
            if link.fields:
                try:
                    description = link.description.decode('utf-8')
                except Exception:
                    print(description)
                    description = link.description

                url_title = self.url_md_template.format(
                    url=link.url, action=link.action, description=description)
                for field in link.fields:
                    dec = markdown.markdown(
                        field.description,
                        extensions=['markdown.extensions.tables'])
                    dec_no_enter = "".join(dec.split())
                    field_str = self.field_string.format(
                        field=field.name,
                        dec=dec_no_enter,
                        param_type=field.type,
                        paramter_type=field.location,
                        required='是' if field.required else '否')
                    url_title += field_str
                url_md_list.append(url_title)
        return url_md_list

    def create(self, title):
        if not has_markdown:
            return
        url_md_list = self._create_url_md()
        swager_md = self.title
        md = ''.join(url_md_list)
        swager_md += md
        with open('APIdoc.md', 'wb') as f:
            f.write(swager_md.encode('utf-8'))
        return swager_md
