'''Test the to_usx conversion API'''
from doctest import Example

import pytest
from lxml import etree
from lxml.doctestcompare import LXMLOutputChecker, PARSE_XML

from tests import all_usfm_files, initialise_parser, doubtful_usfms,\
    doubtful_usxs, negative_tests, find_all_markers

lxml_object = etree.Element('Root')
checker = LXMLOutputChecker()

with open("../schemas/usx.rnc", encoding='utf-8') as f:
    usxrnc_doc  = f.read()
relaxng = etree.RelaxNG.from_rnc_string(usxrnc_doc)

test_files = all_usfm_files.copy()
for file in doubtful_usfms+doubtful_usxs+negative_tests:
    if file in test_files:
        test_files.remove(file)

@pytest.mark.parametrize('file_path', test_files)
@pytest.mark.timeout(30)
def test_successful_usx_converion(file_path):
    '''Tests if input parses & converts to usx successfully'''
    test_parser = initialise_parser(file_path)
    assert not test_parser.errors, test_parser.errors
    usx_xml = test_parser.to_usx()
    assert isinstance(usx_xml, type(lxml_object)), test_parser.to_syntax_tree()


@pytest.mark.parametrize('file_path', test_files)
@pytest.mark.timeout(30)
def test_generated_usx_with_rnc_grammar(file_path):
    '''Tests if input parses & converts to usx successfully and validates the usx against schema'''
    test_parser = initialise_parser(file_path)
    assert not test_parser.errors, test_parser.errors
    usx_xml = test_parser.to_usx()
    assert isinstance(usx_xml, type(lxml_object)), test_parser.to_syntax_tree()
    relaxng.assertValid(usx_xml)
        

@pytest.mark.parametrize('file_path', test_files)
@pytest.mark.timeout(30)
def test_compare_usx_with_testsuite_samples(file_path):
    '''Compare the generated USX with the origin.xml in test suite'''
    test_parser = initialise_parser(file_path)
    assert not test_parser.errors, test_parser.errors
    usx_xml = test_parser.to_usx()
    assert isinstance(usx_xml, type(lxml_object)), test_parser.to_syntax_tree()
    usx_file_path = file_path.replace("origin.usfm", "origin.xml")
    origin_xml = etree.parse(usx_file_path)
    message = checker.output_difference(
                    Example("", etree.tostring(origin_xml).decode('utf-8')), 
                    etree.tostring(usx_xml), PARSE_XML)
    assert checker.check_output(etree.tostring(origin_xml), 
                                etree.tostring(usx_xml), PARSE_XML), message


@pytest.mark.parametrize('file_path', test_files)
@pytest.mark.timeout(30)
def test_testsuite_usx_with_rnc_grammar(file_path):
    '''Check the origin.xml files in testsuite, with the rnc grammar'''
    usx_file_path = file_path.replace("origin.usfm", "origin.xml")
    origin_xml = etree.parse(usx_file_path)
    relaxng.assertValid(origin_xml)

def get_styles(element):
    '''Recursive function to traverse all xml nodes and their style attributes'''
    styles = []
    if 'style' in element.attrib:
        styles.append(element.attrib['style'])
    if element.tag in ['figure', 'optbreak']:
        styles.append(element.tag)
    if "altnumber" in element.attrib:
        styles.append("altnumber")
    if "pubnumber" in element.attrib:
        styles.append("pubnumber")
    if "category" in element.attrib:
        styles.append("category")
    if len(element)>0:
        for child in element:
            styles += get_styles(child)
    return styles

@pytest.mark.parametrize('file_path', test_files)
@pytest.mark.timeout(30)
def test_all_markers_are_in_output(file_path):
    '''Tests if all markers in USFM are present in output also'''
    test_parser = initialise_parser(file_path)
    assert not test_parser.errors, test_parser.errors

    all_markers_in_input = find_all_markers(file_path, keep_id=True, keep_number=True)
        
    usx_xml = test_parser.to_usx()
    all_styles = get_styles(usx_xml)
    replacements = {
        "cat":"category",
        "ca":"altnumber",
        "cp":"pubnumber",
        "va":"altnumber",
        "vp":"pubnumber",
        "b":"optbreak",
        "fig":"figure",}
    for marker in all_markers_in_input:
        synonym = marker
        if replacements.get(marker):
            synonym = replacements[marker]
        # if (marker in ["ts", "qt"] or marker.endswith("-s") or \
        #     marker.endswith("-e") or marker.startswith("z")):
        #     marker = "milestone"
        assert marker in all_styles or synonym in all_styles, marker