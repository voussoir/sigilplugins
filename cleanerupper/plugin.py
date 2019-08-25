import re
import sys
import bs4
import os

html_cleaners = []
soup_cleaners = []
global_footnotes = {}

def html_cleaner(function):
    html_cleaners.append(function)

def soup_cleaner(function):
    soup_cleaners.append(function)

def raise_children_and_delete(element):
    children = list(element.children)
    while children:
        element.insert_after(children.pop(-1))
    element.decompose()

def remove_class(element, cls):
    if not hasattr(element, 'class') or element['class'] is None:
        return
    if isinstance(element['class'], str):
        if element['class'] == cls:
            del element['class']
            return
        else:
            element['class'] = element['class'].split()
    try:
        element['class'].remove(cls)
    except IndexError:
        pass
    if len(element['class']) == 0:
        del element['class']

@html_cleaner
def remove_unwanted_stylesheets(html):
    html = re.sub(r'<style type="text/css">\s*@page { margin-bottom: 5.000000pt; margin-top: 5.000000pt; }\s*</style>', '', html)
    return html

@html_cleaner
def merge_neighboring_sametag(html):
    html = re.sub(r'</i><i>', '', html)
    html = re.sub(r'</i>\s*<i>', ' ', html)

    html = re.sub(r'</b><b>', '', html)
    html = re.sub(r'</b>\s*<b>', ' ', html)

    html = re.sub(r'</small><small>', '', html)
    html = re.sub(r'</small>\s*<small>', ' ', html)
    return html

@html_cleaner
def bring_punctuation_into_italics(html):
    for tag in ['i', 'b']:
        for punct in ['.', ',', '-', '—']:
            html = re.sub('\\{punct}<{tag}>'.format(**locals()), '<{tag}>{punct}'.format(**locals()), html)
            html = re.sub('</{tag}>\\{punct}'.format(**locals()), '{punct}</{tag}>'.format(**locals()), html)
    return html

@html_cleaner
def remove_space_around_br(html):
    html = re.sub(r'\s*<br/?>\s*', '<br/>', html)
    return html

@html_cleaner
def replace_smart_quotes(html):
    html = re.sub(r'”|“', '"', html)
    html = re.sub(r'‘|’|ʹ', "'", html)
    return html

@html_cleaner
def remove_empty_elements(html):
    html = re.sub(r'(?s)<(\w+)>(&(nbsp|emsp|ensp|thinsp|#160);|\s|<br/?>)*</\1>', '', html)
    return html

@soup_cleaner
def inject_footnotes(soup):
    footnotes = soup.find_all('blockquote', {'class': 'gcufootnote_content'})
    for footnote in footnotes:
        try:
            footnote_id = next(footnote.stripped_strings)
        except StopIteration:
            print(footnote, 'is malformed. No string contents.')
            continue
        if not footnote_id.startswith('['):
            print(footnote, 'is malformed. Should start with [id].')
            continue
        footnote_id = footnote_id.split('[', 1)[-1].split(']', 1)[0]

        global_footnotes[footnote_id] = footnote

    footnote_links = soup.find_all('span', {'class': 'gcufootnote_link'})
    for footnote_link in reversed(footnote_links):
        if len(footnote_link.contents) != 1:
            print(footnote_link, 'is malformed. Should just be >[id<.')
        footnote_id = footnote_link.contents[0]
        if not footnote_id.startswith('['):
            print(footnote_link, 'is malformed. Should start with [id].')
            continue
        footnote_id = footnote_id.split('[', 1)[-1].split(']', 1)[0]

        if footnote_id not in global_footnotes:
            continue
        footnote = global_footnotes[footnote_id]
        footnote_link.parent.insert_after(footnote)
        footnote_link.insert_before(footnote_link.contents[0])
        footnote_link.decompose()
        remove_class(footnote, 'gcufootnote_content')

@soup_cleaner
def convert_textdivs_p(soup):
    divs = soup.find_all('div')
    for div in divs:
        children = list(div.children)
        if len(children) == 1 and isinstance(children[0], (str, bs4.element.NavigableString)):
            div.name = 'p'

@soup_cleaner
def remove_body_br(soup):
    for br in soup.find_all('br'):
        if br.parent.name == 'body':
            br.decompose()

@soup_cleaner
def remove_empty_paragraphs(soup):
    brs = soup.find_all('br')
    br_parents = set(br.parent for br in brs)
    for br_parent in br_parents:
        if all(child.name == 'br' for child in br_parent.contents):
            br_parent.decompose()

@soup_cleaner
def remove_calibre_classes(soup):
    PATTERNS = [
        r'calibre\d*',
        r'mbppagebreak',
        r'calibre_pb_\d+',
        r'filepos\d*',
    ]
    for tag in soup.descendants:
        try:
            tag['class']
        except (TypeError, KeyError):
            pass
        else:
            if isinstance(tag['class'], str):
                tag['class'] = tag['class'].split()

            for cls in list(tag['class']):
                if any(re.match(pattern, cls) for pattern in PATTERNS):
                    tag['class'].remove(cls)

            if len(tag['class']) == 0 or tag['class'][0] == '':
                del tag['class']

        try:
            tag['id']
        except (TypeError, KeyError):
            pass
        else:
            if any(re.match(pattern, tag['id']) for pattern in PATTERNS):
                del tag['id']
                continue

@soup_cleaner
def remove_header_italic_bold(soup):
    headers = [h for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] for h in soup.find_all(tag)]
    for header in headers:
        children = list(header.children)
        if len(children) > 1:
            continue
        child = children[0]
        if isinstance(child, str):
            continue
        if child.name in ['i', 'b']:
            raise_children_and_delete(child)

@soup_cleaner
def remove_useless_divs(soup):
    divs = soup.find_all('div')
    for div in divs:
        if not div.attrs:
            if all(isinstance(child, bs4.element.Tag) or child.isspace() for child in div.contents):
                raise_children_and_delete(div)

@soup_cleaner
def remove_useless_spans(soup):
    spans = soup.find_all('span')
    for span in spans:
        if span.attrs:
            continue
        raise_children_and_delete(span)

@soup_cleaner
def remove_nested_italic(soup):
    elements = [element for tag in ['b', 'i'] for element in soup.find_all(tag)]
    for element in elements:
        if element.parent.name == element.name:
            raise_children_and_delete(element)

@soup_cleaner
def replace_italic_bold_span(soup):
    tags = {'italic': 'i', 'italics': 'i', 'bold': 'b'}
    spans = set(span for cls in tags for span in soup.find_all('span', {'class': cls}))
    for span in spans:
        if isinstance(span['class'], str):
            span['class'] = span['class'].split()

        if len(span['class']) == 1:
            new_name = tags[span['class'][0]]
            del span['class']
            span.name = new_name

        elif all(cls in tags for cls in span['class']):
            b = soup.new_tag('b')
            del span['class']
            span.name = 'i'
            span.insert_before(b)
            b.insert(0, span)

@soup_cleaner
def replace_pblock_blockquote(soup):
    classes = ['block', 'block1', 'blockquote']
    ptags = set(ptag for cls in classes for ptag in soup.find_all('p', {'class': cls}))
    for ptag in ptags:
        if isinstance(ptag['class'], str):
            span['class'] = span['class'].split()
        if len(ptag['class']) == 1:
            ptag.name = 'blockquote'
            ptag['class'] = []

@soup_cleaner
def strip_ptag_whitespace(soup):
    ps = soup.find_all('p') + soup.find_all('blockquote')

    for p in ps:
        descendants = list(p.descendants)
        while descendants and not isinstance(descendants[0], bs4.element.NavigableString):
            if descendants[0].name == 'br':
                descendants[0].decompose()
            descendants.pop(0)
        while descendants and not isinstance(descendants[-1], bs4.element.NavigableString):
            if descendants[-1].name == 'br':
                descendants[-1].decompose()
            descendants.pop(-1)

        if not descendants:
            continue

        if len(descendants) == 1:
            descendants[0].replace_with(descendants[0].strip())
            continue

        descendants[0].replace_with(descendants[0].lstrip())
        descendants[-1].replace_with(descendants[-1].rstrip())

def cleanup_page(html):
    previous_html = None
    while previous_html != html:
        previous_html = html

        for cleaner in html_cleaners:
            html = cleaner(html)

        soup = bs4.BeautifulSoup(html, 'html.parser')

        for cleaner in soup_cleaners:
            cleaner(soup)

        html = str(soup)

    return html

def run_once(book):
    for (id, href) in book.text_iter():
        if id in ('navid', 'nav.xhtml', 'nav.html'):
            continue
        print('Cleaning', id)
        html = book.readfile(id)
        html = cleanup_page(html)
        book.writefile(id, html)

def run(book):
    run_once(book)

    if global_footnotes:
        run_once(book)

    return 0
