import shutil
import sys
from subprocess import PIPE, run

import pytest

import pikepdf
from pikepdf import (
    Dictionary,
    Object,
    Operator,
    Pdf,
    PdfMatrix,
    Stream,
    parse_content_stream,
    unparse_content_stream,
)
from pikepdf._qpdf import StreamParser

# pylint: disable=useless-super-delegation


class PrintParser(StreamParser):
    def __init__(self):
        super().__init__()

    def handle_object(self, obj):
        print(repr(obj))

    def handle_eof(self):
        print("--EOF--")


class ExceptionParser(StreamParser):
    def __init__(self):
        super().__init__()

    def handle_object(self, obj):  # pylint: disable=unused-argument
        raise ValueError("I take exception to this")

    def handle_eof(self):
        print("--EOF--")


def test_open_pdf(resources):
    pdf = Pdf.open(resources / 'graph.pdf')
    page = pdf.pages[0]
    Object._parse_stream(page, PrintParser())


def test_parser_exception(resources):
    pdf = Pdf.open(resources / 'graph.pdf')
    stream = pdf.pages[0]['/Contents']
    with pytest.raises(ValueError):
        Object._parse_stream(stream, ExceptionParser())


@pytest.mark.skipif(shutil.which('pdftotext') is None, reason="poppler not installed")
@pytest.mark.skipif(sys.version_info < (3, 6), reason="subprocess.run on 3.5")
def test_text_filter(resources, outdir):
    input_pdf = resources / 'veraPDF test suite 6-2-10-t02-pass-a.pdf'

    # Ensure the test PDF has detect we can find
    proc = run(
        ['pdftotext', str(input_pdf), '-'], check=True, stdout=PIPE, encoding='utf-8'
    )
    assert proc.stdout.strip() != '', "Need input test file that contains text"

    pdf = Pdf.open(input_pdf)
    page = pdf.pages[0]

    keep = []
    for operands, command in parse_content_stream(
        page, """TJ Tj ' " BT ET Td TD Tm T* Tc Tw Tz TL Tf Tr Ts"""
    ):
        if command == Operator('Tj'):
            print("skipping Tj")
            continue
        keep.append((operands, command))

    new_stream = Stream(pdf, keep)
    print(new_stream.read_bytes())  # pylint: disable=no-member
    page['/Contents'] = new_stream
    page['/Rotate'] = 90

    pdf.save(outdir / 'notext.pdf', True)

    proc = run(
        ['pdftotext', str(outdir / 'notext.pdf'), '-'],
        check=True,
        stdout=PIPE,
        encoding='utf-8',
    )

    assert proc.stdout.strip() == '', "Expected text to be removed"


def test_invalid_stream_object():
    with pytest.raises(TypeError):
        parse_content_stream(Dictionary({"/Hi": 3}))


# @pytest.mark.parametrize(
#     "test_file,expected",
#     [
#         ("fourpages.pdf", True),
#         ("graph.pdf", False),
#         ("veraPDF test suite 6-2-10-t02-pass-a.pdf", True),
#         ("veraPDF test suite 6-2-3-3-t01-fail-c.pdf", False),
#         ('sandwich.pdf', True),
#     ],
# )
# def test_has_text(resources, test_file, expected):
#     pdf = Pdf.open(resources / test_file)
#     for p in pdf.pages:
#         page = Page(p)
#         assert page.has_text() == expected


def test_unparse_cs():
    instructions = [
        ([], Operator('q')),
        ([*PdfMatrix.identity().shorthand], Operator('cm')),
        ([], Operator('Q')),
    ]
    assert unparse_content_stream(instructions).strip() == b'q\n1 0 0 1 0 0 cm\n Q'
