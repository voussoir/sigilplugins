import tkinter
import tkinter.messagebox
import io
import re
import PIL.Image
import xml.etree.ElementTree

def find_cover_id(book):
    for (id, href, mimetype) in book.manifest_iter():
        properties = book.id_to_properties(id)
        if properties == 'cover-image':
            return id

    metadata = xml.etree.ElementTree.fromstring(book.getmetadataxml())
    cover = [x for x in metadata.findall('meta') if x.get('name') == 'cover']
    if cover:
        return cover[0].get('content')

    return None

def fit_into_bounds(image_width, image_height, frame_width, frame_height, only_shrink=False):
    '''
    Given the w+h of the image and the w+h of the frame,
    return new w+h that fits the image into the frame
    while maintaining the aspect ratio.

    (1920, 1080, 400, 400) -> (400, 225)
    '''
    width_ratio = frame_width / image_width
    height_ratio = frame_height / image_height
    ratio = min(width_ratio, height_ratio)

    new_width = int(image_width * ratio)
    new_height = int(image_height * ratio)

    if only_shrink and (new_width > image_width or new_height > image_height):
        return (image_width, image_height)

    return (new_width, new_height)

def collect_images(book, do_cover=False):
    images = []
    if do_cover:
        cover_id = None
    else:
        cover_id = find_cover_id(book)

    for (id, href, mimetype) in book.manifest_iter():
        if id == cover_id:
            continue

        if mimetype == 'image/jpeg':
            images.append(id)
    return images

def choose_options():
    options = {}
    t = tkinter.Tk()
    t.grid_columnconfigure(1, weight=1)
    t.grid_rowconfigure(3, weight=1)
    t.title('imagecrunch')
    do_cover_intvar = tkinter.IntVar()
    do_cover_intvar.set(1)
    do_cover_checkbox = tkinter.Checkbutton(t, text='Compress the cover?', variable=do_cover_intvar)
    do_cover_checkbox.grid(row=0, column=0, columnspan=2, sticky='w')
    tkinter.Label(t, text='max dimension').grid(row=1, column=0, sticky='w')
    dimension_slider = tkinter.Scale(t, from_=100, to=2000, resolution=10, orient=tkinter.HORIZONTAL)
    dimension_slider.grid(row=1, column=1, sticky='we')
    dimension_slider.set(500)
    tkinter.Label(t, text='jpeg quality').grid(row=2, column=0, sticky='w')
    quality_slider = tkinter.Scale(t, from_=1, to=100, orient=tkinter.HORIZONTAL)
    quality_slider.grid(row=2, column=1, sticky='we')
    quality_slider.set(50)
    def commit():
        options['do_cover'] = do_cover_intvar.get()
        options['quality'] = quality_slider.get()
        options['max_dimension'] = dimension_slider.get()
        t.destroy()
    ok_button = tkinter.Button(t, text='OK', command=commit, bg='#00ff00')
    ok_button.grid(row=3, column=0, columnspan=2, sticky='ews')
    t.mainloop()
    return options

def imagecrunch(book, options):
    total_original_size = 0
    total_new_size = 0

    for id in collect_images(book, do_cover=options['do_cover']):
        data = io.BytesIO(book.readfile(id))
        original_size = len(data.read())
        total_original_size += original_size
        data.seek(0)
        i = PIL.Image.open(data)
        data = io.BytesIO()
        # i = i.convert('L')
        new_dimension = fit_into_bounds(*i.size, options['max_dimension'], options['max_dimension'], only_shrink=True)
        i = i.resize(new_dimension, resample=PIL.Image.LANCZOS)
        i.save(data, format='jpeg', quality=options['quality'])
        data.seek(0)
        new_size = len(data.read())
        if new_size >= original_size:
            total_new_size += original_size
            continue
        total_new_size += new_size
        data.seek(0)
        book.writefile(id, data.read())
        print(id, 'shrunk from', int(original_size / 1024), 'K', 'to', int(new_size / 1024), 'K')

    print('Total shrunk from', int(total_original_size / 1024), 'K', 'to', int(total_new_size / 1024), 'K')

def run(book):
    options = choose_options()
    print(options)
    if not options:
        return 1

    imagecrunch(book, options)
    return 0
