from backend.course_structure import split_sections, section_for


def test_contents_titles_and_body_page_ranges_ignore_preface_prose():
    pages=[(1,'Contents\n1 Binary Numbers 1\n2 Boolean Algebra 21\n3 Combinational Logic 41'),
           (2,'Chapter 3 presents Combinational Logic with examples.'),
           (5,'1\nChapter 1\nBinary Numbers\n1.1 INTRODUCTION'),
           (25,'21\nChapter 2\nBoolean Algebra\n2.1 INTRODUCTION'),
           (45,'41\nChapter 3\nCombinational Logic\n3.1 INTRODUCTION'),(60,'Last page')]
    result=split_sections(pages)
    assert [s.title for s in result]==['1. Binary Numbers','2. Boolean Algebra','3. Combinational Logic']
    assert [(s.start_page,s.end_page) for s in result]==[(5,24),(25,44),(45,60)]
    assert section_for(result,30)==1


def test_unstructured_pdf_does_not_turn_prose_or_code_into_topics():
    pages=[(i,'Chapter 1 presents the various binary systems.\n# with respect to each other\nModule 5 As mentioned previously, the module is the basic building block for modeling\ny = z or xy = z') for i in range(1,44)]
    result=split_sections(pages)
    assert [s.title for s in result]==['Pages 1–20','Pages 21–40','Pages 41–43']


def test_markdown_sections_on_same_page_have_distinct_offsets():
    text='# Keys\nA key uniquely identifies a row.\n## Transactions\nChanges commit together.'
    result=split_sections([(1,text)],markdown=True)
    assert [s.title for s in result]==['Keys','Transactions']
    assert section_for(result,1,0)==0
    assert section_for(result,1,len(text)-1)==1
