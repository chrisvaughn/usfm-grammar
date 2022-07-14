import argparse
import json
from enum import Enum
from tree_sitter import Language, Parser
import xml.etree.ElementTree as ET
from xml.dom import minidom

class Filter(str, Enum):
	ALL = "all"
	SCRIPTURE_BCV = "scripture-bcv"
	SCRIPTURE_PARAGRAPHS = "scripture-paragraph"
	NOTES = "notes"
	NOTES_TEXT = "note-text"

class Format(str, Enum):
	JSON = "json"
	CSV = "table"
	AST = "syntax-tree"
	USX = "usx"
	MD = "markdown"

USFM_LANGUAGE = Language('build/my-languages.so', 'usfm')
parser = Parser()
parser.set_language(USFM_LANGUAGE)

PARA_STYLE_MARKERS = ["h", "toc", "toca" #identification 
					"imt", "is", "ip", "ipi", "im", "imi", "ipq", "imq", "ipr", "iq", "ib",
					"ili", "iot", "io", "iex", "imte", "ie", # intro
					"mt", "mte", "cl", "cd", "ms", "mr", "s", "sr", "r", "d", "sp", "sd", #titles
					"q", "qr", "qc", "qa", "qm", "qd", #poetry
					"lh", "li", "lf", "lim", "litl" #lists
					]

NOTE_MARKERS = ["f", "fe", "ef", "efe", "x", "ex"]
CHAR_STYLE_MARKERS = [ "add", "bk", "dc", "ior", "iqt", "k", "litl", "nd", "ord", "pn",
					"png", "qac", "qs", "qt", "rq", "sig", "sls", "tl", "wj", # Special-text
					"em", "bd", "bdit", "it", "no", "sc", "sup", # character styling
					 "rb", "pro", "w", "wh", "wa", "wg", #special-features
					 "lik", "liv", #structred list entries
					 "jmp",
					 "fr", "ft", "fk", "fq", "fqa", "fl", "fw", "fp", "fv", "fdc", #footnote-content
					 "xo", "xop", "xt", "xta", "xk", "xq", "xot", "xnt", "xdc" #crossref-content
					 ]
NESTED_CHAR_STYLE_MARKERS = [item+"Nested" for item in CHAR_STYLE_MARKERS]
DEFAULT_ATTRIB_MAP = {"w":"lemma", "rb":"gloss", "xt":"link-href", "fig":"alt"}
TABLE_CELL_MARKERS = ["tc", "th", "tcr", "thr"]

def node_2_usx(node, usfm_bytes, parent_xml_node, xml_root_node):
	'''check each node and based on the type convert to corresponding xml element'''
	# print("working with node: ", node, "\n")
	if node.type == "id":
		id_captures = USFM_LANGUAGE.query('''(id (bookcode) @book-code
													(description) @desc)''').captures(node)
		code = None 
		desc = None 
		for tupl in id_captures:
			if tupl[1] == "book-code":
				code = usfm_bytes[tupl[0].start_byte:tupl[0].end_byte].decode('utf-8')
			elif tupl[1] == 'desc':
				desc = usfm_bytes[tupl[0].start_byte:tupl[0].end_byte].decode('utf-8')
		book_xml_node = ET.SubElement(parent_xml_node, "book")
		book_xml_node.set("code", code)
		book_xml_node.set("style", "id")
		if desc is not None and desc.strip() != "":
			book_xml_node.text = desc.strip()
	elif node.type == "chapter":
		chap_cap = USFM_LANGUAGE.query('''(c (chapterNumber) @chap-num)''').captures(node)[0]
		chap_num = usfm_bytes[chap_cap[0].start_byte:chap_cap[0].end_byte].decode('utf-8')
		ref = parent_xml_node.find("book").attrib['code']+" "+chap_num
		chap_xml_node = ET.SubElement(parent_xml_node, "chapter")
		chap_xml_node.set("number", chap_num)
		chap_xml_node.set("style", "c")
		chap_xml_node.set("sid", ref)
		for child in node.children[1:]:
			node_2_usx(child, usfm_bytes, parent_xml_node, xml_root_node)

		prev_verses = xml_root_node.findall(".//verse")
		if len(prev_verses)>0:
			if "sid" in prev_verses[-1].attrib:
				v_end_xml_node = ET.SubElement(parent_xml_node, "verse")
				v_end_xml_node.set('eid', prev_verses[-1].get('sid'))
		chap_end_xml_node = ET.SubElement(parent_xml_node, "chapter")
		chap_end_xml_node.set("eid", ref)
	elif node.type == "v":
		prev_verses = xml_root_node.findall(".//verse")
		if len(prev_verses)>0:
			if "sid" in prev_verses[-1].attrib:
				v_end_xml_node = ET.SubElement(parent_xml_node, "verse")
				v_end_xml_node.set('eid', prev_verses[-1].get('sid'))
		verse_num_cap = USFM_LANGUAGE.query("(v (verseNumber) @vnum)").captures(node)[0]
		verse_num = usfm_bytes[verse_num_cap[0].start_byte:verse_num_cap[0].end_byte].decode('utf-8')
		v_xml_node = ET.SubElement(parent_xml_node, "verse")
		ref = xml_root_node.findall('.//chapter')[-1].get('sid')+ ":"+ verse_num
		v_xml_node.set('number', verse_num.strip())
		v_xml_node.set('sid', ref.strip())
	elif node.type == "verseText":
		for child in node.children:
			node_2_usx(child, usfm_bytes, parent_xml_node, xml_root_node)
	elif node.type == 'paragraph':
		para_tag_cap = USFM_LANGUAGE.query("(paragraph (_) @para-marker)").captures(node)[0]
		para_marker = para_tag_cap[0].type
		para_xml_node = ET.SubElement(parent_xml_node, "para")
		para_xml_node.set("style", para_marker)
		for child in para_tag_cap[0].children[1:]:
			node_2_usx(child, usfm_bytes, para_xml_node, xml_root_node)
	elif node.type in NOTE_MARKERS:
		tag_node = node.children[0]
		caller_node = node.children[1]
		note_xml_node = ET.SubElement(parent_xml_node, "note")
		note_xml_node.set("style",
			usfm_bytes[tag_node.start_byte:tag_node.end_byte].decode('utf-8')
			.replace("\\","").strip())
		note_xml_node.set("caller",
			usfm_bytes[caller_node.start_byte:caller_node.end_byte].decode('utf-8').strip())
		for child in node.children[2:-1]:
			node_2_usx(child, usfm_bytes, note_xml_node, xml_root_node)
	elif node.type in CHAR_STYLE_MARKERS:
		tag_node = node.children[0]
		closing_node = None
		children_range = len(node.children)
		if node.children[-1].type.startswith('\\'):
			closing_node = node.children[-1]
			children_range = children_range-1
		char_xml_node = ET.SubElement(parent_xml_node, "char")
		char_xml_node.set("style",
			usfm_bytes[tag_node.start_byte:tag_node.end_byte].decode('utf-8')
			.replace("\\","").strip())
		if closing_node is None:
			char_xml_node.set("closed", "false")
		else:
			char_xml_node.set("closed", "true")
		for child in node.children[1:children_range]:
			node_2_usx(child, usfm_bytes, char_xml_node, xml_root_node)
	elif node.type.endswith("Attribute"):
		attrib_name_node= node.children[0]
		attrib_name = usfm_bytes[attrib_name_node.start_byte:attrib_name_node.end_byte] \
			.decode('utf-8').strip()
		if attrib_name == "|":
			attrib_name = DEFAULT_ATTRIB_MAP[node.parent.type]

		attrib_val_cap = USFM_LANGUAGE.query("((attributeValue) @attrib-val)").captures(node)[0]
		attrib_value = usfm_bytes[attrib_val_cap[0].start_byte:attrib_val_cap[0].end_byte] \
			.decode('utf-8').strip()
		parent_xml_node.set(attrib_name, attrib_value)
	elif node.type == 'text':
		text_val = usfm_bytes[node.start_byte:node.end_byte].decode('utf-8').strip()
		siblings = parent_xml_node.findall("./*")
		if len(siblings) > 0:
			siblings[-1].tail = text_val
		else:
			parent_xml_node.text = text_val
	elif node.type == "table":
		table_xml_node = ET.SubElement(parent_xml_node, "table")
		for child in node.children:
			node_2_usx(child, usfm_bytes, table_xml_node, xml_root_node)
	elif node.type == "tr":
		row_xml_node = ET.SubElement(parent_xml_node, "row")
		row_xml_node.set("style", "tr")
		for child in node.children[1:]:
			node_2_usx(child, usfm_bytes, row_xml_node, xml_root_node)
	elif node.type in TABLE_CELL_MARKERS:
		tag_node = node.children[0]
		style = usfm_bytes[tag_node.start_byte:tag_node.end_byte].decode('utf-8')\
		.replace("\\","").strip()
		cell_xml_node = ET.SubElement(parent_xml_node, "cell")
		cell_xml_node.set("style", style)
		if "r" in style:
			cell_xml_node.set("align", "end")
		else:
			cell_xml_node.set("align", "start")
		for child in node.children[1:]:
			node_2_usx(child, usfm_bytes, cell_xml_node, xml_root_node)
	elif  node.type == "milestone":
		# print(node.children)
		ms_name_cap = USFM_LANGUAGE.query('''(
			[(milestoneTag)
			 (milestoneStartTag)
			 (milestoneEndTag)
			 ] @ms-name)''').captures(node)[0]
		style = usfm_bytes[ms_name_cap[0].start_byte:ms_name_cap[0].end_byte].decode('utf-8')\
		.replace("\\","").strip()
		ms_xml_node = ET.SubElement(parent_xml_node, "ms")
		ms_xml_node.set('style', style)
		for child in node.children:
			if child.type.endswith("Attribute"):
				node_2_usx(child, usfm_bytes, ms_xml_node, xml_root_node)
	elif node.type == "esb":
		style = "esb"
		sidebar_xml_node = ET.SubElement(parent_xml_node, "sidebar")
		sidebar_xml_node.set("style", style)
		for child in node.children[1:-1]:
			node_2_usx(child, usfm_bytes, sidebar_xml_node, xml_root_node)
	elif node.type == "cat":
		cat_cap = USFM_LANGUAGE.query('((category) @category)').captures(node)[0]
		category = usfm_bytes[cat_cap[0].start_byte:cat_cap[0].end_byte].decode('utf-8').strip()
		parent_xml_node.set('category', category)
	elif node.type == 'fig':
		fig_xml_node = ET.SubElement(parent_xml_node, "figure")
		fig_xml_node.set("style", 'fig')
		for child in node.children[1:-1]:
			node_2_usx(child, usfm_bytes, fig_xml_node, xml_root_node)
	elif node.type == 'b':
		break_xml_node = ET.SubElement(parent_xml_node, "optbreak")
	elif (node.type in PARA_STYLE_MARKERS or 
		  node.type.replace("\\","").strip() in PARA_STYLE_MARKERS):
		tag_node = node.children[0]
		style = usfm_bytes[tag_node.start_byte:tag_node.end_byte].decode('utf-8')
		if style.startswith('\\'):
			style = style.replace('\\','').strip()
		else:
			style = node.type
		children_range_start = 1
		if len(node.children)>1 and node.children[1].type.startswith("numbered"):
			num_node = node.children[1]
			num = usfm_bytes[num_node.start_byte:num_node.end_byte].decode('utf-8')
			style += num
			children_range_start = 2
		para_xml_node = ET.SubElement(parent_xml_node, "para")
		para_xml_node.set("style", style)
		# caps = USFM_LANGUAGE.query('((text) @inner-text)').captures(node)
		# para_xml_node.text = " ".join([usfm_bytes[txt_cap[0].start_byte:txt_cap[0].end_byte].decode('utf-8').strip()
		#  for txt_cap in caps])
		for child in node.children[children_range_start:]:
			node_2_usx(child, usfm_bytes, para_xml_node, xml_root_node)
	elif node.type.strip() in ["","|"]:
		pass # skip white space nodes
	elif len(node.children)>0:
		for child in node.children:
			node_2_usx(child, usfm_bytes, parent_xml_node, xml_root_node)
	else:
		raise Exception("Encountered unknown element ", str(node))






def node_2_dict(node, usfm_bytes):
    '''recursive function converting an AST node and its children to dictionary'''
    if len(node.children)>0:
        item = []
        for child in node.children:
            val = node_2_dict(child, usfm_bytes)
            if child.type == val:
                # pass
                item.append(child.type)
            elif isinstance(val, dict) and len(val)==1 and child.type == list(val.keys())[0]:
                item.append({child.type: val[child.type]})
            else:
                item.append({child.type: val})
    else:
        if node.type == usfm_bytes[node.start_byte:node.end_byte].decode('utf-8'):
            item = node.type
        else:
            item = {node.type: 
                    str(usfm_bytes[node.start_byte:node.end_byte], 'utf-8')}
    return item


bookcode_query = USFM_LANGUAGE.query('''(File (book (id (bookcode) @book-code)))''')

chapter_query = USFM_LANGUAGE.query('''(File (chapter) @chapter)''')

chapternum_query = USFM_LANGUAGE.query('''(c (chapterNumber) @chapter-number)''')

versenum_query = USFM_LANGUAGE.query("""(v (verseNumber) @verse)""")

versetext_query = USFM_LANGUAGE.query("""(verseText) @verse-text""")

text_query = USFM_LANGUAGE.query("""(text) @text""")

error_query = USFM_LANGUAGE.query("""(ERROR) @errors""")

notes_query = USFM_LANGUAGE.query('''[(footnote) (crossref)] @note''')

notestext_query = USFM_LANGUAGE.query('''(noteText) @note-text''')

para_query = USFM_LANGUAGE.query("""[(paragraph) (poetry) (table) (list)] @para""")

title_query = USFM_LANGUAGE.query("""(title) @title""")

class USFMParser():
	"""Parser class with usfmstring, AST and methods for JSON convertions"""
	def __init__(self, usfm_string):
		# super(USFMParser, self).__init__()
		self.USFM = usfm_string
		self.USFMbytes = None
		self.AST = None
		self.errors = None

		self.USFMbytes = bytes(self.USFM, "utf8")
		tree = parser.parse(self.USFMbytes)
		self.AST = tree.root_node

		# check for errors in the parse tree and raise them
		errors = error_query.captures(self.AST)
		if len(errors) > 0:
			self.errors = [(f"At {err[0].start_point}", self.USFMbytes[err[0].start_byte:err[0].end_byte].decode('utf-8')) 
									for err in errors]


	def toAST(self):
		return self.AST.sexp()

	def toDict(self, filt=Filter.SCRIPTURE_BCV.value):
		if filt in [Filter.SCRIPTURE_BCV.value, Filter.NOTES.value, Filter.NOTES_TEXT.value,
			Filter.SCRIPTURE_PARAGRAPHS.value, None]:
			dict_output = {}
			captures = bookcode_query.captures(self.AST)
			cap = captures[0]
			dict_output['book'] = {'bookcode': self.USFMbytes[cap[0].start_byte:cap[0].end_byte].decode('utf-8')}
			dict_output['book']['chapters'] = []
			captures = chapter_query.captures(self.AST)
			for cap in captures:
				chap_captures = chapternum_query.captures(cap[0])
				ccap= chap_captures[0]
				dict_output['book']['chapters'].append({"chapterNumber":
					self.USFMbytes[ccap[0].start_byte:ccap[0].end_byte].decode('utf-8'),
					"contents":[]})
				if filt in [Filter.SCRIPTURE_BCV.value, None]:
					'''query for just the chapter, verse and text nodes from the AST'''
					versenum_captures = versenum_query.captures(cap[0])
					versetext_captures = versetext_query.captures(cap[0])
					combined = {item[0].start_byte: item for item in versenum_captures+versetext_captures}
					sorted_combined = [combined[i] for i in  sorted(combined)]
					for vcap in sorted_combined:
						if vcap[1] == "verse":
							dict_output['book']['chapters'][-1]["contents"].append(
								{"verseNumber":self.USFMbytes[vcap[0].start_byte:vcap[0].end_byte].decode('utf-8').strip(),
								 "verseText":""})
						elif vcap[1] == "verse-text":
							text_captures = text_query.captures(vcap[0])
							text_val = "".join([self.USFMbytes[tcap[0].start_byte:tcap[0].end_byte].decode('utf-8').replace("\n", " ")
												for tcap in text_captures])
							dict_output['book']['chapters'][-1]['contents'][-1]['verseText'] += text_val
				elif filt in [Filter.NOTES.value, Filter.NOTES_TEXT.value]:
					'''query for just the chapter, verse and text nodes from the AST'''
					versenum_captures = versenum_query.captures(cap[0])
					notes_captures = notes_query.captures(cap[0])
					if len(notes_captures) == 0:
						continue
					combined = {item[0].start_byte: item for item in versenum_captures+notes_captures}
					sorted_combined = [combined[i] for i in  sorted(combined)]
					for index,vcap in enumerate(sorted_combined):
						if vcap[1] == "verse" and \
							index+1 !=len(sorted_combined) and sorted_combined[index+1][1] =="note":
							'''need to add a verse only if it has notes'''
							dict_output['book']['chapters'][-1]["contents"].append(
								{"verseNumber":self.USFMbytes[vcap[0].start_byte:vcap[0].end_byte].decode('utf-8').strip(),
								 "notes":[]})
						elif vcap[1] == "note":
							note_type = vcap[0].type
							if filt == Filter.NOTES.value:
								note_details = node_2_dict(vcap[0], self.USFMbytes)
							elif filt == Filter.NOTES_TEXT.value:
								notetext_captures = notestext_query.captures(vcap[0])
								note_details = "|".join([self.USFMbytes[ncap[0].start_byte:ncap[0].end_byte].decode('utf-8').strip().replace("\n","") for ncap in notetext_captures])
							dict_output['book']['chapters'][-1]['contents'][-1]['notes'].append({note_type: note_details})
				elif filt in [Filter.SCRIPTURE_PARAGRAPHS.value]:
					'''titles and section information, paragraph breaks
					and also structuring like lists and tables
					along with verse text and versenumber details at the lowest level'''
					title_captures = title_query.captures(cap[0])
					para_captures = para_query.captures(cap[0])
					combined_tit_paras = {item[0].start_byte: item for item in title_captures+para_captures}
					sorted_tit_paras = [combined_tit_paras[i] for i in  sorted(combined_tit_paras)]
					for comp in sorted_tit_paras:
						if comp[1] == "title":
							text_captures = text_query.captures(comp[0])
							title_texts = []
							for tcap in text_captures:
								title_texts.append(self.USFMbytes[tcap[0].start_byte:tcap[0].end_byte].decode('utf-8'))
							dict_output['book']['chapters'][-1]['contents'].append(
								{"title":" ".join(title_texts).strip()})
						elif comp[1] == "para":
							comp_type = comp[0].type
							versenum_captures = versenum_query.captures(comp[0])
							versetext_captures = versetext_query.captures(comp[0])
							combined = {item[0].start_byte: item for item in versenum_captures+versetext_captures}
							sorted_combined = [combined[i] for i in  sorted(combined)]
							inner_contents = []
							for vcap in sorted_combined:
								if vcap[1] == "verse":
									inner_contents.append(
										{"verseNumber":self.USFMbytes[vcap[0].start_byte:vcap[0].end_byte].decode('utf-8').strip(),
										 "verseText":""})
								elif vcap[1] == "verse-text":
									text_captures = text_query.captures(vcap[0])
									text_val = "".join([self.USFMbytes[tcap[0].start_byte:tcap[0].end_byte].decode('utf-8').replace("\n", " ")
														for tcap in text_captures])
									if len(inner_contents) == 0:
										inner_contents.append({"verseText":""})
									inner_contents[-1]['verseText'] += text_val

							dict_output['book']['chapters'][-1]["contents"].append({comp_type:inner_contents})
			return dict_output
		elif filt == Filter.ALL.value:
			'''directly converts the AST to JSON/dict'''
			return node_2_dict(self.AST, self.USFMbytes)
		else:
			raise Exception(f"This filter option, {filt}, is yet to be implemeneted")

	def toTable(self, filt=Filter.SCRIPTURE_BCV.value):
		'''uses the toJSON function and converts JSON to CSV'''
		if filt == Filter.SCRIPTURE_BCV.value or filt is None:
			scripture_json = self.toDict(Filter.SCRIPTURE_BCV.value)
			table_output = [["Book","Chapter","Verse","Text"]]
			book = scripture_json['book']['bookcode']
			for chap in scripture_json['book']['chapters']:
				chapter = chap['chapterNumber']
				for verse in chap['contents']:
					row = [book, chapter, verse['verseNumber'], '"'+verse['verseText']+'"']
					table_output.append(row)
			return table_output
		elif filt == Filter.NOTES.value:
			notes_json = self.toDict(Filter.NOTES_TEXT.value)
			table_output = [["Book","Chapter","Verse","Type", "Note"]]
			book = notes_json['book']['bookcode']
			for chap in notes_json['book']['chapters']:
				chapter = chap['chapterNumber']
				for verse in chap['contents']:
					v_num = verse['verseNumber']
					for note in verse['notes']:
						typ = list(note)[0]
						row = [book, chapter, v_num, typ, '"'+note[typ]+'"']
					table_output.append(row)
			return table_output
		elif filt == Filter.SCRIPTURE_PARAGRAPHS.value:
			notes_json = self.toDict(Filter.SCRIPTURE_PARAGRAPHS.value)
			table_output = [["Book","Chapter","Type", "Contents"]]
			book = notes_json['book']['bookcode']
			for chap in notes_json['book']['chapters']:
				chapter = chap['chapterNumber']
				for comp in chap['contents']:
					typ = list(comp)[0]
					if typ == "title":
						cont = comp[typ]
					else:
						inner_cont = []
						for inner_comp in comp[typ]:
							inner_cont += list(inner_comp.values())
						cont = ' '.join(inner_cont)
					row = [book, chapter, typ, cont]
					table_output.append(row)
			return table_output
			
		else:
			raise Exception(f"This filter option, {filt}, is yet to be implemeneted")

	def toMarkDown(self, filt=Filter.SCRIPTURE_PARAGRAPHS.value):
		'''query for chapter, paragraph, text structure'''
		return "yet to be implemeneted"


	def toUSX(self, filt=Filter.ALL):
		'''convert the AST to the XML format USX'''
		usx_root = ET.Element("usx")
		usx_root.set("version", "3.0")

		node_2_usx(self.AST, self.USFMbytes, usx_root, usx_root)
		return usx_root

if __name__ == '__main__':
	arg_parser = argparse.ArgumentParser(
		description='Uses the tree-sitter-usfm grammar to parse and convert USFM to Syntax-tree, JSON, CSV or MarkDown.')
	arg_parser.add_argument('infile', type=str, help='input usfm file')
	arg_parser.add_argument('--format', type=str, help='output format',
							choices=[Format.JSON.value, Format.CSV.value, Format.USX.value,
										Format.MD.value, Format.AST.value],
							default=Format.JSON.value)
	arg_parser.add_argument('--filter', type=str, help='the type of contents to be included',
							choices=[Filter.SCRIPTURE_BCV.value, Filter.NOTES.value, Filter.SCRIPTURE_PARAGRAPHS.value])
	arg_parser.add_argument('--csv_col_sep', type=str, help="column separator or delimiter. Only useful with format=table.",
							default="\t")
	arg_parser.add_argument('--csv_row_sep', type=str, help="row separator or delimiter. Only useful with format=table.",
							default="\n")

	infile = arg_parser.parse_args().infile
	output_format = arg_parser.parse_args().format
	output_filter = arg_parser.parse_args().filter
	csv_col_sep = arg_parser.parse_args().csv_col_sep
	csv_row_sep = arg_parser.parse_args().csv_row_sep

	with open(infile, 'r') as usfm_file:
		file_content = usfm_file.read()

	my_parser = USFMParser(file_content)

	if my_parser.errors:
		err_str = "\n\t".join(my_parser.errors)
		print(f"Errors at:{err_str}")

	if output_format == Format.JSON:
		dict_output = my_parser.toDict(filt = output_filter)
		print(json.dumps(dict_output, indent=4, ensure_ascii=False))
	elif output_format == Format.CSV:
		table_output = my_parser.toTable(filt = output_filter)
		print(csv_row_sep.join([csv_col_sep.join(row) for row in table_output]))
	elif output_format == Format.USX:
		xmlstr = ET.tostring(my_parser.toUSX(filt = output_filter),encoding="unicode")	
		print(minidom.parseString(xmlstr).toprettyxml(indent="   "))
	elif output_format == Format.MD:
		print(my_parser.toMarkDown(filt = output_filter))
	elif output_format == Format.AST:
		print(my_parser.toAST())
	else:
		raise Exception(f"Un-recognized output format:{output_format}!")

