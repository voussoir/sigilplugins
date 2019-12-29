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

def contains_class(element, cls):
    try:
        element['class']
    except (AttributeError, KeyError):
        return False
    if isinstance(element['class'], str):
        element['class'] = element['class'].split()

    return cls in element['class']

def remove_class(element, cls):
    if not contains_class(element, cls):
        return

    try:
        element['class'].remove(cls)
    except IndexError:
        pass
    if len(element['class']) == 0:
        del element['class']

@html_cleaner
def remove_unwanted_stylesheets(html):
    html = re.sub(r'<style type="text/css">\s*@page { margin-bottom: 5\.000000pt; margin-top: 5\.000000pt; }\s*</style>', '', html)
    html = re.sub(r'style="margin-top: 0px; margin-left: 0px; margin-right: 0px; margin-bottom: 0px; text-align: center;"', '', html)
    return html

@html_cleaner
def merge_neighboring_sametag(html):
    tags = ['i', 'b', 'em', 'strong', 'u', 'small']
    for tag in tags:
        html = re.sub(r'</%s><%s>' % (tag, tag), '', html)
        html = re.sub(r'</%s>\s*<%s>' % (tag, tag), ' ', html)
        html = re.sub(r'</%s>\s*<br/?>\s*<%s>' % (tag, tag), '<br/>', html)

    return html

@html_cleaner
def bring_punctuation_into_italics(html):
    for tag in ['i', 'b', 'em', 'strong']:
        for punct in ['.', ',', '-', '—']:
            html = re.sub('\\{punct}<{tag}>'.format(**locals()), '<{tag}>{punct}'.format(**locals()), html)
            html = re.sub('</{tag}>\\{punct}'.format(**locals()), '{punct}</{tag}>'.format(**locals()), html)
    return html

@html_cleaner
def remove_misc_strings(html):
    html = html.replace('epub:type="pagebreak"', '')
    html = re.sub(r'title="[ivx]+"', '', html)
    html = re.sub(r'title="\d+"', '', html)
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
def remove_empty_attributes(html):
    html = re.sub(r'alt="\s*"', '', html)
    html = re.sub(r'class="\s*"', '', html)
    html = re.sub(r'id="\s*"', '', html)
    html = re.sub(r'title="\s*"', '', html)
    return html

@html_cleaner
def remove_empty_elements(html):
    html = re.sub(r'(?s)<(\w+)>(&(nbsp|emsp|ensp|thinsp|#160);|\s|<br/?>)*</\1>', '', html)
    return html

@soup_cleaner
def collect_footnotes(soup):
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

@soup_cleaner
def inject_footnotes(soup):
    footnote_links = soup.find_all('span', {'class': 'gcufootnote_link'})
    for footnote_link in reversed(footnote_links):
        if contains_class(footnote_link.parent, 'gcufootnote_content'):
            # In the case of nested footnotes, let's place the parent first
            # and come back for this child on the next go around.
            continue
        if len(footnote_link.contents) != 1:
            print(footnote_link, 'is malformed. Should just be >[id]<.')

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
def center_images(soup):
    for img in soup.find_all('img'):
        if img.parent.name == 'body':
            center = soup.new_tag('center')
            img.insert_before(center)
            center.append(img)
        elif img.parent.name in ['div', 'p'] and not img.parent.attrs:
            img.parent.name = 'center'

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
def remove_unwanted_classes_ids(soup):
    PATTERNS = [
        r'big\d+',
        r'blnonindent\d*',
        r'c\d+',
        r'calibre_?\d*',
        r'calibre_pb_\d+',
        r'chapter',
        r'div\d+',
        r'dropcaps',
        r'filepos\d*',
        r'font',
        r'hanging',
        r'indent\d*',
        r'initial\d*',
        r'initialcaps',
        r'large',
        r'mbp_?pagebreak',
        r'morespaceabove',
        r'nonindent\d*',
        r'p_?[ivx]+',
        r'p_?\d+',
        r'page_?[ivx]+',
        r'page_?\d+',
        r'page_top_padding',
        r'pagebreak',
        r'pgepubid\d*',
        r'right',
        r'section',
        r'spaceabove',
        r'squeeze(\d+)?',
        r'stickupcaps',
        r'title',
    ]
    for tag in soup.descendants:
        if not isinstance(tag, bs4.element.Tag):
            continue

        if tag.get('class'):
            if isinstance(tag['class'], str):
                tag['class'] = tag['class'].split()
            else:
                tag['class'] = list(tag['class'])

            # Intentional list() duplicate so we can remove from original.
            for cls in list(tag['class']):
                if any(re.match(pattern, cls) for pattern in PATTERNS):
                    tag['class'].remove(cls)

            if len(tag['class']) == 0 or tag['class'][0] == '':
                del tag['class']

        if tag.get('id'):
            if any(re.match(pattern, tag['id']) for pattern in PATTERNS):
                del tag['id']

@soup_cleaner
def remove_header_italic_bold(soup):
    headers = [h for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] for h in soup.find_all(tag)]
    for header in headers:
        children = list(header.children)
        if len(children) > 1:
            continue
        if len(children) == 0:
            header.extract()
            continue
        child = children[0]
        if isinstance(child, str):
            continue
        if child.name in ['i', 'b', 'em', 'strong']:
            raise_children_and_delete(child)

@soup_cleaner
def remove_useless_divs(soup):
    divs = soup.find_all('div')
    for div in divs:
        if div.attrs:
            continue
        if all(isinstance(child, bs4.element.Tag) or child.isspace() for child in div.contents):
            raise_children_and_delete(div)

@soup_cleaner
def remove_useless_blockquote(soup):
    blocks = soup.find_all('blockquote')
    for block in blocks:
        if block.attrs:
            continue
        if all(child.name == 'blockquote' or (isinstance(child, bs4.element.NavigableString) and child.isspace()) for child in block.contents):
            raise_children_and_delete(block)

@soup_cleaner
def remove_useless_spans(soup):
    spans = soup.find_all('span')
    for span in spans:
        if span.attrs:
            continue
        raise_children_and_delete(span)

@soup_cleaner
def remove_useless_atags(soup):
    atags = soup.find_all('a')
    for atag in atags:
        if atag.attrs:
            continue
        raise_children_and_delete(atag)

@soup_cleaner
def remove_useless_meta(soup):
    selectors = [
        'link[type="application/vnd.adobe-page-template+xml"]',
        'meta[http-equiv="Content-Type"]',
        'meta[name="Adept.expected.resource"]',
        'meta[name="Adept.resource"]',
    ]
    for selector in selectors:
        for item in soup.select(selector):
            item.extract()

@soup_cleaner
def remove_nested_italic(soup):
    elements = [element for tag in ['b', 'i', 'em', 'strong'] for element in soup.find_all(tag)]
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
def replace_classes_real_tags(soup):
    replace = {
        'div.block': 'blockquote',
        'div.block1': 'blockquote',
        'div.block2': 'blockquote',
        'div.block3': 'blockquote',
        'div.blockquote': 'blockquote',
        'div.center': 'center',
        'div.center1': 'center',
        'p.block': 'blockquote',
        'p.block1': 'blockquote',
        'p.block2': 'blockquote',
        'p.block3': 'blockquote',
        'p.blockquote': 'blockquote',
        'p.center': 'center',
        'p.center1': 'center',
        'span.b': 'b',
        'span.i': 'i',
        'span.italic': 'i',
        'span.small': 'small',
        'span.small1': 'small',
        'span.smallcaps': 'small',
        'span.underline': 'u',
    }
    for (selector, new_name) in replace.items():
        for tag in soup.select(selector):
            if isinstance(tag['class'], str):
                tag['class'] = tag['class'].strip().split()
            if len(tag['class']) == 1:
                tag.name = new_name
                tag['class'] = []

@soup_cleaner
def strip_unecessary_whitespace(soup):
    tags = ['p', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    elements = [element for tag in tags for element in soup.find_all(tag)]

    for element in elements:
        descendants = list(element.descendants)
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
