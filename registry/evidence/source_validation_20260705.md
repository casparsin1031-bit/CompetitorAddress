# Source validation — CompetitorAddress

Validated official/fallback sources for entries that failed the current Playwright scraper.

| Key | Source | Count | Confidence | Notes |
|---|---|---:|---|---|
| `HKM` | official_ajax_blocked / google_maps_fallback: https://mcdonalds.com.hk/en/find-a-restaurant/ | 0 | low | Official page loads but wp-admin admin-ajax.php?action=get_restaurants returns 403 in requests and Playwright; fallback Google Maps scrape found 114 records locally but appears partial vs expected 150-350. |
| `HKS` | official: https://sushirohk.com.hk/tc/shop.php?wid=3&cid=1 | 43 | high | official HTML contains .store-list-box-wrapper cards; expected 15-80; addresses 43/43 |
| `SGS` | official: https://www.sushiro.com.sg/contact-location/ | 23 | high | official Elementor page contains one card per store with maps links; expected 5-80; addresses 23/23 |
| `THM` | official: https://www.mcdonalds.co.th/storeLocations | 233 | high | official HTML contains .store-container cards with lat/lon; expected 50-400; addresses 233/233 |
| `THS` | official: https://sushiro.co.th/branch/ | 47 | high | official HTML contains .box-branch--detail cards; expected 5-80; addresses 47/47 |
| `VNM` | official: https://mcdonalds.vn/restaurants.html | 49 | high | official HTML contains store cards and Google Maps coordinates; expected 10-80; addresses 49/49 |

## Samples

### HKM — McDonald's HK

No deterministic official sample extracted.

### HKS — Sushiro HK

```json
[
  {
    "shop_name": "九龍灣淘大店",
    "address": "九龍九龍灣牛頭角道77號淘大商場1期2樓S150號舖",
    "phone": "2789 8028"
  },
  {
    "shop_name": "黃埔時尚坊店",
    "address": "九龍紅磡黃埔天地時尚坊(第二期)地下G42-G43號舖",
    "phone": "​2365 0888"
  },
  {
    "shop_name": "沙田中心店",
    "address": "新界沙田橫壆街2-16號沙田中心3樓32A及69A號舖",
    "phone": "23100388"
  }
]
```

### SGS — Sushiro SG

```json
[
  {
    "shop_name": "Sushiro Tiong Bahru Plaza",
    "address": "302 Tiong Bahru Road, #02-118 Tiong Bahru Plaza, Singapore 168732",
    "operating_hours": "11:00AM – 10:00PM",
    "source_url": "https://maps.app.goo.gl/uCTvx2GBbFi4w1hN9"
  },
  {
    "shop_name": "Sushiro Wisma Atria",
    "address": "435 Orchard Rd, #02-08 to 13 Wisma Atria, Singapore 238877",
    "operating_hours": "11:00AM – 10:00PM",
    "source_url": "https://maps.app.goo.gl/49gfFijRL55twKPU8"
  },
  {
    "shop_name": "Sushiro Isetan Scotts",
    "address": "350 Orchard Road, #03-K1/K2, part of #03-00 Shaw House, Singapore 238868",
    "operating_hours": "11:00AM – 10:00PM",
    "source_url": "https://maps.app.goo.gl/RZuV1fNMZKxJ5mcM7"
  }
]
```

### THM — McDonald's TH

```json
[
  {
    "shop_name": "CENTER ONE",
    "address": "1001 Soi Lertpanya, Rajvithee Road, Phayathai, Ratchathevi, Bangkok 10400",
    "lat": "13.764251",
    "lon": "100.539441",
    "source_url": "https://www.mcdonalds.co.th/storeLocations/5bd50c0facc28a76f33fe1bd"
  },
  {
    "shop_name": "PACIFIC PARK SRIRACHA",
    "address": "90 Sukhumvit Road, KM. 118, Sriracha, Chonburi 20110",
    "lat": "13.167498",
    "lon": "100.930645",
    "source_url": "https://www.mcdonalds.co.th/storeLocations/5bd51430acc28a4209293d69"
  },
  {
    "shop_name": "BIG C EXTRA SRINAKARIN",
    "address": "425 Moo 5 Srinakarin Road, Sumrong Nua, Muang, Samut Prakarn 10270",
    "lat": "13.649375",
    "lon": "100.640991",
    "source_url": "https://www.mcdonalds.co.th/storeLocations/5bd5d4adacc28a3cfb04e662"
  }
]
```

### THS — Sushiro TH

```json
[
  {
    "shop_name": "สาขา True Digital Park",
    "address": "3rd Floor",
    "operating_hours": "Everyday 10.00 - 22.00",
    "phone": "02-090-9744",
    "source_url": "https://maps.app.goo.gl/SpMA3b83GZQRxvgTA"
  },
  {
    "shop_name": "สาขา Central Bangna",
    "address": "5th Floor",
    "operating_hours": "Mon-Thu 10.30 - 21.00 Fri 10.30 - 22.00 Sat 10.00 - 22.00 Sun ,Holidays 10.00 - 21.00",
    "phone": "02-030-2181",
    "source_url": "https://maps.app.goo.gl/vPD2LZaMy5ApK5Yc9"
  },
  {
    "shop_name": "สาขา Samyan Mitrtown",
    "address": "4th Floor",
    "operating_hours": "Daily 10:00 - 22:00 (Last Order 21:30)",
    "phone": "02-107-2208",
    "source_url": "https://maps.app.goo.gl/1UCpo3saGtVNrW456"
  }
]
```

### VNM — McDonald's VN

```json
[
  {
    "shop_name": "McDonald's Gold Coast",
    "address": "L11-15- Gold Coast Mall, 01 Tran Hung Dao Street, Nha Trang City",
    "phone": "0979794900",
    "operating_hours": "9:00 AM - 10:00 PM",
    "lat": "12.248386",
    "lon": "109.194451",
    "source_url": "https://www.google.com/maps/place/12.248386, 109.194451"
  },
  {
    "shop_name": "McDonald's Long Beach Center",
    "address": "124 Tran Hung Dao Street, Duong Dong Ward, Phu Quoc City",
    "phone": "+84 969992849",
    "operating_hours": "7:00 AM - 11:00 PM",
    "lat": "10.1913192",
    "lon": "103.9639574",
    "source_url": "https://www.google.com/maps/place/10.1913192, 103.9639574"
  },
  {
    "shop_name": "McDonald's Nguyen Van Thoai",
    "address": "229 Nguyen Van Thoai, An Hai Ward, Da Nang City",
    "phone": "0387878566",
    "operating_hours": "7:00 AM - 00:00 AM",
    "lat": "16.0559624",
    "lon": "108.2453241",
    "source_url": "https://www.google.com/maps/place/16.0559624, 108.2453241"
  }
]
```
