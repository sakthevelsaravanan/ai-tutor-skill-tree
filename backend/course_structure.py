"""Deterministic chapters from a contents page, explicit headings, or page groups.
Book-order edges are suggestions, not claims of semantic dependency.
"""
import re
from collections import Counter
from dataclasses import dataclass

@dataclass
class Section:
    title: str
    start_page: int
    end_page: int = 0
    offset: int = 0


def normalized(text):
    return re.sub(r'[^a-z0-9]', '', text.casefold())


def clean_title(text):
    text = re.sub(r'\s+', ' ', text).strip(' .:-')
    words = text.split()
    if not 1 <= len(words) <= 14 or not 3 <= len(text) <= 96:
        return None
    if not text[0].isalpha() or any(c in text for c in '=<>;{}'):
        return None
    if re.match(r'(?i)(presents|introduces|covers|deals|outlines|defines|is |are |we |the following)', text):
        return None
    if text.endswith((',', '-')) or sum(c.isalpha() for c in text) < len(text) / 2:
        return None
    return text


def split_sections(pages, markdown=False):
    if not pages:
        return []
    # Contents pages have multiple numbered titles followed by printed page numbers.
    contents = []
    for number, text in pages[:40]:
        lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines() if line.strip()]
        candidates = []
        for i, line in enumerate(lines):
            if not re.match(r'^(?:Chapter )?\d+ +[A-Z]', line):
                continue
            joined = line
            for j in range(i, min(i + 3, len(lines))):
                if j > i:
                    if re.match(r'^\d', lines[j]):
                        break
                    joined += ' ' + lines[j]
                match = re.match(r'^(?:Chapter )?(\d+) +(.+?) *[. ]+ *(\d+)$', joined)
                if match:
                    title = clean_title(match[2])
                    if title:
                        candidates.append((int(match[1]), title, int(match[3]), number))
                    break
        if ('contents' in text.casefold() or len(candidates) >= 2) and candidates:
            contents.extend(candidates)
    toc = {}
    for chapter, title, printed, toc_page in contents:
        toc.setdefault(chapter, (title, printed, toc_page))
    toc_rows = sorted(toc.items())
    if len(toc_rows) >= 2:
        anchors = {}
        for chapter, (title, printed, toc_page) in toc_rows:
            for page, text in pages:
                if page <= toc_page:
                    continue
                top = text[:400]
                if (re.search(r'(?im)^[ \t]*Chapter[ \t]+' + str(chapter) + r'[ \t]*$', top) or any(normalized(line) == normalized(f'Chapter {chapter} {title}') for line in top.splitlines())) and normalized(title) in normalized(top):
                    anchors[chapter] = page
                    break
        offsets = Counter(anchors[ch] - toc[ch][1] for ch in anchors)
        if offsets:
            offset = offsets.most_common(1)[0][0]
            sections = [Section(f'{ch}. {title}', anchors.get(ch, printed + offset))
                        for ch, (title, printed, _) in toc_rows]
            sections = [s for s in sections if pages[0][0] <= s.start_page <= pages[-1][0]]
            if len(sections) >= 2 and all(a.start_page < b.start_page for a,b in zip(sections, sections[1:])):
                return finish(sections, pages[-1][0])
    # Only explicit heading syntax is accepted; never prose mentioning a chapter.
    sections = []
    seen = set()
    for page, text in pages:
        lines = list(re.finditer(r'(?m)^.*$', text))
        for i, line in enumerate(lines):
            heading = re.match(r'^\s*#{1,3} +(.+?)\s*#*$', line[0])
            chapter = re.match(r'^\s*(?:Chapter|Unit|Module) +(\d+)\s*[:.-]?\s*(.*?)\s*$', line[0], re.I)
            title = None
            if heading and markdown:
                title = clean_title(heading[1])
            elif chapter:
                candidate = chapter[2]
                if not candidate and i + 1 < len(lines):
                    candidate = lines[i+1][0].strip()
                cleaned = clean_title(candidate)
                if cleaned and cleaned[0].isupper() and sum(w[0].isupper() for w in cleaned.split()) >= len(cleaned.split()) * 0.6:
                    title = chapter[1] + '. ' + cleaned
            if title and normalized(title) not in seen:
                seen.add(normalized(title))
                sections.append(Section(title, page, offset=line.start()))
    if sections:
        return finish(sections, pages[-1][0])
    # Honest, stable fallback for unstructured notes: contiguous groups of 20 pages.
    sections = [Section(f'Pages {pages[i][0]}–{pages[min(i+19,len(pages)-1)][0]}', pages[i][0])
                for i in range(0, len(pages), 20)]
    return finish(sections, pages[-1][0])


def finish(sections, last_page):
    for i, section in enumerate(sections):
        section.end_page = max(section.start_page, sections[i+1].start_page - 1) if i+1 < len(sections) else last_page
    return sections


def section_for(sections, page, offset=0):
    return next((i for i in range(len(sections)-1, -1, -1)
                 if (sections[i].start_page, sections[i].offset) <= (page, offset)), 0)


def create_topics(conn, subject_id, file_name, sections):
    existing=conn.execute('SELECT * FROM topics WHERE subject_id=%s AND source_file=%s ORDER BY sort_order,topic_id',(subject_id,file_name)).fetchall()
    by_title={t['topic_name']:t for t in existing}
    topics=[]
    base=min((t['sort_order'] for t in existing),default=0)-1 if existing else conn.execute('SELECT COALESCE(MAX(sort_order),0) AS n FROM topics WHERE subject_id=%s',(subject_id,)).fetchone()['n']
    for i, section in enumerate(sections):
        title=section.title[:100]
        if title in by_title:
            topic=conn.execute('UPDATE topics SET start_page=%s,end_page=%s,sort_order=%s WHERE topic_id=%s RETURNING *',
                (section.start_page,section.end_page,base+i+1,by_title[title]['topic_id'])).fetchone()
        else:
            if conn.execute('SELECT 1 FROM topics WHERE subject_id=%s AND topic_name=%s',(subject_id,title)).fetchone():
                title=f'{title[:75]} (document {base+i+1})'
            topic=conn.execute("""INSERT INTO topics(subject_id,topic_name,difficulty_level,source_file,start_page,end_page,sort_order)
                VALUES(%s,%s,1,%s,%s,%s,%s) RETURNING *""",
                (subject_id,title,file_name,section.start_page,section.end_page,base+i+1)).fetchone()
        topics.append(topic)
    keep=[t['topic_id'] for t in topics]
    conn.execute('DELETE FROM topics WHERE subject_id=%s AND source_file=%s AND NOT(topic_id=ANY(%s))',(subject_id,file_name,keep))
    conn.execute("DELETE FROM topic_prerequisites WHERE basis='book_order' AND topic_id=ANY(%s)",(keep,))
    for previous,current in zip(topics,topics[1:]):
        conn.execute("INSERT INTO topic_prerequisites(topic_id,prereq_topic_id,basis) VALUES(%s,%s,'book_order') ON CONFLICT DO NOTHING",
            (current['topic_id'],previous['topic_id']))
    return topics
