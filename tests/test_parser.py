from scripts.scrape import amount_analysis_status, balance_candidates_by_implementation, canonical_url, classify, course_key, dedupe_items, extract_detail_links, has_transport_support, implementation_type_for_seed, is_kanto_only, is_science_only, parse_dates, parse_detail, without_kanto_locations

def test_money():
    assert classify('交通費 上限30,000円まで支給') == ('limit', 30000)
    assert classify('交通費 地域別に定額支給（1,000円以上5,000円以内）') == ('limit', 5000)
    assert classify('実費を全額支給') == ('unlimited', None)

def test_dates():
    assert '2026-08-04' in parse_dates('開催日 2026年8月4日')

def test_canonical_dedup():
    a='https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=123&optNo=ABC&utm_source=x'
    b='https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?optNo=ABC&corpId=123'
    assert canonical_url(a) == canonical_url(b)
    assert course_key(a) == course_key(b)

def test_content_dedup():
    base={'company':'A','course':'C','event_dates':['2026-08-04'],'locations':['大阪府'],'last_checked':'2026-01-01'}
    items=[dict(base,id='1'),dict(base,id='2')]
    assert len(dedupe_items(items)) == 1

def test_deadline_and_status():
    from scripts.scrape import detect_status, parse_deadline
    assert parse_deadline('応募締切 2026年8月4日') == '2026-08-04'
    assert detect_status('このコースは満席となりました') == 'closed'
    assert detect_status('現在応募受付中です') == 'open'

def test_transport_population_and_amount_analysis():
    supported = {"transport_available": True, "transport_type": "limit", "transport_amount": 30000, "transport_original": "交通費 上限30,000円まで支給"}
    missing = {"transport_available": False, "transport_type": "unknown", "transport_amount": None, "transport_original": "交通費欄を特定できませんでした。"}
    assert has_transport_support(supported)
    assert amount_analysis_status(supported) == "amount_known"
    assert not has_transport_support(missing)
    assert amount_analysis_status(missing) == "no_transport"

def test_detail_page_uses_mynavi_table_rows():
    html = """
    <html><head><title>テスト企業のインターンシップ</title></head><body>
      <h1>テスト企業(株)</h1>
      <div class="category"><h2>業種</h2><ul><li><span class="noLink">鉄道</span></li></ul></div>
      <div class="dtHead2"><h2 class="txt"><span id="courseName">鉄道技術体験コース</span></h2></div>
      <table class="dataTable02">
        <tr><td class="heading">開催地域</td><td class="sameSize">東京 、 大阪 、 WEB</td></tr>
        <tr><td class="heading">開催時期と実施日数</td><td class="sameSize">2026年8月4日</td></tr>
        <tr><td class="heading">応募締切日</td><td class="sameSize">2026年7月31日</td></tr>
        <tr><td class="heading">参加条件</td><td class="sameSize">文理不問</td></tr>
        <tr><td class="heading">交通費</td><td class="sameSize">支給あり 地域別に定額支給（1,000円以上5,000円以内）</td></tr>
        <tr><td class="heading">宿泊費</td><td class="sameSize">支給なし</td></tr>
      </table>
    </body></html>
    """
    item = parse_detail("https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=1&optNo=A", html, None)
    assert item["company"] == "テスト企業(株)"
    assert item["course"] == "鉄道技術体験コース"
    assert item["transport_original"] == "支給あり 地域別に定額支給（1,000円以上5,000円以内）"
    assert "宿泊費" not in item["transport_original"]
    assert item["industries"] == ["鉄道"]
    assert item["eligibility_text"] == "文理不問"
    assert item["locations"] == ["東京都", "大阪府", "WEB"]
    assert not is_science_only(item)

def test_science_only_detection():
    assert is_science_only({"eligibility_text": "理系", "course": "設計体験"})
    assert is_science_only({"eligibility_text": "土木建設系学生（土木に関する専門知識を要するプログラムのため）", "course": "1Day"})
    assert is_science_only({"eligibility_text": "対象者：工学部の方（機械、化学、電気、電子）", "course": "5days"})
    assert not is_science_only({"eligibility_text": "文理不問", "course": "設計体験"})
    assert not is_science_only({"eligibility_text": "全学部全学科", "course": "技術系"})

def test_kanto_only_detection():
    assert is_kanto_only({"locations": ["東京都", "神奈川県"]})
    assert not is_kanto_only({"locations": ["東京都", "大阪府"]})
    assert not is_kanto_only({"locations": ["WEB"]})
    assert without_kanto_locations({"locations": ["東京都", "大阪府", "WEB"]})["locations"] == ["大阪府", "WEB"]

def test_extract_detail_links_keeps_course_hint():
    html = '<a href="/28/pc/corpinfo/displayInternship/index?corpId=123&optNo=ABC">交通費ありコース</a>'
    assert extract_detail_links("https://job.mynavi.jp/28/pc/search/is_it1.html", html) == [
        ("https://job.mynavi.jp/28/pc/corpinfo/displayInternship/index?corpId=123&optNo=ABC", "交通費ありコース")
    ]

def test_detail_candidates_are_balanced_by_implementation_type():
    catalog = {"urls": {
        "a1": {"implementation_types": ["インターンシップ"]},
        "a2": {"implementation_types": ["インターンシップ"]},
        "b1": {"implementation_types": ["仕事体験"]},
        "c1": {"implementation_types": ["オープン・カンパニー等"]},
    }}
    candidates = [(0, "", "a1", "u1"), (0, "", "a2", "u2"), (0, "", "b1", "u3"), (0, "", "c1", "u4")]
    selected = balance_candidates_by_implementation(candidates, catalog, 3)
    assert [key for _, _, key, _ in selected] == ["a1", "b1", "c1"]

def test_implementation_type_for_seed():
    assert implementation_type_for_seed("https://job.mynavi.jp/28/pc/search/is_it2.html") == "仕事体験"
