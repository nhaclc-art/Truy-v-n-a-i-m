from scripts.fetch_osm import TAG_FILTERS, build_query


def test_build_query_covers_every_tag_filter_around_the_point():
    query = build_query(10.761357, 106.6821769, 2000)
    for tag_filter in TAG_FILTERS:
        assert f"nwr{tag_filter}(around:2000,10.761357,106.6821769);" in query
    # Way/relation cần tâm đại diện để tính khoảng cách.
    assert query.rstrip().endswith("out center tags;")
