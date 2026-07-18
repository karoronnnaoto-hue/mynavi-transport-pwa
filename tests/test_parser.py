from scripts.scrape import amount_analysis_status, canonical_url, classify, course_key, dedupe_items, has_transport_support, parse_dates

def test_money():
    assert classify('交通費 上限30,000円まで支給') == ('limit', 30000)
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
