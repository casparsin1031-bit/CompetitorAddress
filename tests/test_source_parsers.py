from __future__ import annotations

from scrapers.source_parsers import (
    parse_mcd_th,
    parse_mcd_vn,
    parse_sushiro_hk,
    parse_sushiro_sg,
    parse_sushiro_th,
)


def test_parse_mcd_th_official_cards() -> None:
    html = """
    <div class="store-container" data-lat="13.7563" data-lng="100.5018">
      <h3>McDonald's Siam</h3><p>999 Rama I Road Bangkok</p>
    </div>
    """
    rows = parse_mcd_th(html)
    assert len(rows) == 1
    assert rows[0].shop_name == "McDonald's Siam"
    assert rows[0].address == "999 Rama I Road Bangkok"
    assert rows[0].lat == 13.7563
    assert rows[0].lon == 100.5018


def test_parse_mcd_vn_official_cards() -> None:
    html = """
    <div class="tbox-address-store">
      <h3>McDonald's Ben Thanh</h3>
      <span>Address</span><p>2-2A Tran Hung Dao, District 1</p>
      <span>Opening Time</span><p>07:00 - 23:00</p>
      <span>Hotline</span><p>19009001</p>
      <a href="https://www.google.com/maps/place/10.7717,106.6983">Map</a>
    </div>
    """
    rows = parse_mcd_vn(html)
    assert len(rows) == 1
    assert rows[0].shop_name == "McDonald's Ben Thanh"
    assert rows[0].address == "2-2A Tran Hung Dao, District 1"
    assert rows[0].operating_hours == "07:00 - 23:00"
    assert rows[0].phone == "19009001"
    assert rows[0].lat == 10.7717
    assert rows[0].lon == 106.6983


def test_parse_sushiro_hk_official_cards() -> None:
    html = """
    <div class="store-list-box-wrapper">
      <h3>SUSHIRO Tsim Sha Tsui</h3><p>Shop 1, Example Mall</p><p>TEL: 2888 8888</p>
    </div>
    """
    rows = parse_sushiro_hk(html)
    assert len(rows) == 1
    assert rows[0].shop_name == "SUSHIRO Tsim Sha Tsui"
    assert rows[0].address == "Shop 1, Example Mall"
    assert rows[0].phone == "2888 8888"


def test_parse_sushiro_th_official_cards() -> None:
    html = """
    <div class="box-branch--detail">
      <a href="https://maps.google.com/">เส้นทาง</a>
      <h2>Central World</h2><p>7th Floor, Bangkok</p><p>10:00-22:00</p><p>02-000-0000</p>
    </div>
    """
    rows = parse_sushiro_th(html)
    assert len(rows) == 1
    assert rows[0].shop_name == "Central World"
    assert rows[0].address == "7th Floor, Bangkok"
    assert rows[0].operating_hours == "10:00-22:00"
    assert rows[0].phone == "02-000-0000"


def test_parse_sushiro_sg_official_elementor_cards() -> None:
    html = """
    <div class="e-child">
      <h3>Sushiro Tiong Bahru Plaza</h3>
      <p>302 Tiong Bahru Road</p><p>#02-118</p><p>Singapore 168732</p>
      <p>Operating Hours:</p><p>11:00 - 22:00</p>
      <a href="https://www.google.com/maps/place/1.2863,103.8272">Directions</a>
    </div>
    """
    rows = parse_sushiro_sg(html)
    assert len(rows) == 1
    assert rows[0].shop_name == "Sushiro Tiong Bahru Plaza"
    assert rows[0].address == "302 Tiong Bahru Road, #02-118, Singapore 168732"
    assert rows[0].operating_hours == "11:00 - 22:00"
    assert rows[0].lat == 1.2863
    assert rows[0].lon == 103.8272
